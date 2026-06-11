from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timezone
from pathlib import Path

from .calendar_data import replace_calendar_with_live
from .config import Settings
from .llm import synthesize_with_gemini
from .market_data import replace_market_rows_with_live
from .portfolio import apply_portfolio_assumptions
from .render import utc_run_id
from .sample_data import BriefData, build_sample_brief_data
from .theme_data import DEFAULT_THEME_SEARCH_QUERIES, replace_theme_radar_with_live
from .topic_selection import select_portfolio_topics


@dataclass(frozen=True)
class ModelComparisonResult:
    model: str
    status: str
    validation_attempts: int
    validation_repair_count: int
    validation_errors: tuple[str, ...]
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    elapsed_seconds: float
    error: str = ""


def build_comparison_input(
    settings: Settings,
    *,
    run_date: date,
    live_market_data: bool = False,
    live_calendar: bool = False,
    live_theme_radar: bool = False,
) -> BriefData:
    data = build_sample_brief_data()
    data = apply_portfolio_assumptions(data, run_date=run_date, path=settings.portfolio_path)
    if live_market_data:
        data = replace_market_rows_with_live(data, run_date=run_date, timezone_name=settings.timezone).data
    if live_calendar:
        data = replace_calendar_with_live(data, run_date=run_date, timezone_name=settings.timezone).data
    if live_theme_radar:
        data = replace_theme_radar_with_live(
            data,
            run_date=run_date,
            history_path=None,
            recent_days=settings.theme_recent_days,
            search_queries=DEFAULT_THEME_SEARCH_QUERIES,
        ).data
    return select_portfolio_topics(
        data,
        run_date=run_date,
        portfolio_path=settings.portfolio_path,
        feedback_path=settings.feedback_path,
    )


def compare_gemini_models(
    settings: Settings,
    *,
    models: list[str],
    run_date: date,
    live_market_data: bool = False,
    live_calendar: bool = False,
    live_theme_radar: bool = False,
) -> tuple[list[ModelComparisonResult], Path]:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is required for compare-models")
    if not models:
        raise RuntimeError("At least one Gemini model name is required for compare-models")

    data = build_comparison_input(
        settings,
        run_date=run_date,
        live_market_data=live_market_data,
        live_calendar=live_calendar,
        live_theme_radar=live_theme_radar,
    )
    results: list[ModelComparisonResult] = []
    for model in models:
        model_settings = replace(settings, gemini_model=model)
        started = time.perf_counter()
        try:
            synthesis = synthesize_with_gemini(model_settings, data)
        except RuntimeError as exc:
            elapsed = round(time.perf_counter() - started, 2)
            results.append(
                ModelComparisonResult(
                    model=model,
                    status="failed",
                    validation_attempts=0,
                    validation_repair_count=0,
                    validation_errors=(str(exc),),
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    estimated_cost_usd=0.0,
                    elapsed_seconds=elapsed,
                    error=str(exc),
                )
            )
            continue
        elapsed = round(time.perf_counter() - started, 2)
        status = "warning" if synthesis.validation_repair_count else "passed"
        results.append(
            ModelComparisonResult(
                model=model,
                status=status,
                validation_attempts=synthesis.validation_attempts,
                validation_repair_count=synthesis.validation_repair_count,
                validation_errors=synthesis.validation_errors,
                input_tokens=synthesis.token_usage.input_tokens,
                output_tokens=synthesis.token_usage.output_tokens,
                total_tokens=synthesis.token_usage.total_tokens,
                estimated_cost_usd=synthesis.estimated_cost_usd,
                elapsed_seconds=elapsed,
            )
        )

    settings.log_dir.mkdir(parents=True, exist_ok=True)
    log_path = settings.log_dir / f"model-compare-{utc_run_id()}.jsonl"
    log_event = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "run_date": run_date.isoformat(),
        "models": models,
        "live_market_data": live_market_data,
        "live_calendar": live_calendar,
        "live_theme_radar": live_theme_radar,
        "cost_estimate_note": "Cost is estimated only for models present in the local cost table; unsupported model prices may be recorded as 0.0.",
        "topic_titles": data.three_thing_titles,
        "results": [asdict(result) for result in results],
    }
    log_path.write_text(json.dumps(log_event, indent=2) + "\n", encoding="utf-8")
    return results, log_path
