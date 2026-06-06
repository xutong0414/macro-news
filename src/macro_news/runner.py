from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from .config import Settings
from .costing import ZERO_TOKEN_USAGE
from .emailer import send_email
from .llm import synthesize_with_gemini
from .market_data import MarketDataResult, replace_market_rows_with_live
from .render import render_html, render_markdown, utc_run_id, write_outputs
from .sample_data import build_sample_brief_data


@dataclass(frozen=True)
class RunResult:
    run_id: str
    output_paths: dict[str, Path]
    delivery_status: str
    log_path: Path


def run_brief(
    settings: Settings,
    *,
    send: bool = False,
    run_date: date | None = None,
    use_llm: bool = False,
    live_market_data: bool = False,
) -> RunResult:
    run_date = run_date or date.today()
    run_id = utc_run_id()
    data = build_sample_brief_data()
    market_data_result = MarketDataResult(data=data, live_assets=[], fallback_assets=[], errors={}, sources=[])
    token_usage = ZERO_TOKEN_USAGE
    llm_status = "not_used"
    llm_model = "none"
    estimated_llm_cost_usd = 0.0
    prompt_version = "none"

    if live_market_data:
        market_data_result = replace_market_rows_with_live(data, run_date=run_date)
        data = market_data_result.data

    if use_llm:
        if settings.llm_provider != "gemini":
            raise RuntimeError("Only Gemini synthesis is implemented for --use-llm right now")
        synthesis = synthesize_with_gemini(settings, data)
        data = synthesis.data
        token_usage = synthesis.token_usage
        llm_status = "used"
        llm_model = synthesis.model
        estimated_llm_cost_usd = synthesis.estimated_cost_usd
        prompt_version = synthesis.prompt_version

    output_paths = write_outputs(data, settings.output_dir, run_date)

    delivery_status = "dry_run"
    if send:
        send_email(
            settings,
            subject=f"Daily Macro Brief - {run_date.isoformat()}",
            text_body=render_markdown(data, run_date),
            html_body=render_html(data, run_date),
            chart_path=output_paths["latest_chart"],
        )
        delivery_status = "sent"

    settings.log_dir.mkdir(parents=True, exist_ok=True)
    log_path = settings.log_dir / f"run-{run_id}.jsonl"
    log_event = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "run_date": run_date.isoformat(),
        "run_mode": settings.run_mode,
        "llm_provider": settings.llm_provider,
        "llm_model": llm_model,
        "llm_status": llm_status,
        "prompt_version": prompt_version,
        "delivery_status": delivery_status,
        "data_sources": data.data_sources,
        "market_data": {
            "mode": "live_with_fallback" if live_market_data else "sample",
            "live_assets": market_data_result.live_assets,
            "fallback_assets": market_data_result.fallback_assets,
            "errors": market_data_result.errors,
            "sources": market_data_result.sources,
        },
        "token_usage": {
            "input_tokens": token_usage.input_tokens,
            "output_tokens": token_usage.output_tokens,
            "total_tokens": token_usage.total_tokens,
            "provider": token_usage.provider,
        },
        "estimated_llm_cost_usd": estimated_llm_cost_usd,
        "outputs": {key: str(value) for key, value in output_paths.items()},
    }
    log_path.write_text(json.dumps(log_event, indent=2) + "\n", encoding="utf-8")

    return RunResult(run_id=run_id, output_paths=output_paths, delivery_status=delivery_status, log_path=log_path)
