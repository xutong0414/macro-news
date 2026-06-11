from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .calendar_data import CalendarDataResult, replace_calendar_with_live
from .config import Settings
from .costing import ZERO_TOKEN_USAGE
from .emailer import send_email
from .llm import NarrativeValidationFailure, SynthesisResult, synthesize_with_gemini
from .market_data import MarketDataResult, replace_market_rows_with_live
from .portfolio import apply_portfolio_assumptions
from .render import render_html, render_markdown, utc_run_id, write_outputs
from .sample_data import build_sample_brief_data
from .theme_data import DEFAULT_THEME_SEARCH_QUERIES, ThemeDataResult, replace_theme_radar_with_live
from .topic_selection import select_portfolio_topics


@dataclass(frozen=True)
class RunResult:
    run_id: str
    output_paths: dict[str, Path]
    delivery_status: str
    log_path: Path
    quality_report: dict[str, Any]


def _effective_run_mode(
    settings: Settings,
    *,
    live_market_data: bool,
    live_calendar: bool,
    live_theme_radar: bool,
) -> str:
    live_layers = []
    if live_market_data:
        live_layers.append("market")
    if live_calendar:
        live_layers.append("calendar")
    if live_theme_radar:
        live_layers.append("theme")
    if live_layers:
        return "live_" + "_".join(live_layers)
    return settings.run_mode


def _effective_data_sources(
    data_sources: list[str],
    *,
    live_market_data: bool,
    live_calendar: bool,
    live_theme_radar: bool,
) -> list[str]:
    """Hide scaffold seed labels once a live layer has replaced that section."""
    replaced_sources = set()
    if live_market_data:
        replaced_sources.add("sample_market_data")
    if live_calendar:
        replaced_sources.add("sample_calendar")
    if live_theme_radar:
        replaced_sources.add("sample_deep_content")
    return [source for source in data_sources if source not in replaced_sources]


def _add_quality_check(
    checks: list[dict[str, str]],
    warnings: list[str],
    blockers: list[str],
    *,
    name: str,
    status: str,
    details: str,
) -> None:
    checks.append({"name": name, "status": status, "details": details})
    if status == "warning":
        warnings.append(f"{name}: {details}")
    elif status == "failed":
        blockers.append(f"{name}: {details}")


def _build_quality_report(
    *,
    use_llm: bool,
    synthesis: SynthesisResult | None,
    llm_error: str | None,
    live_market_data: bool,
    live_calendar: bool,
    live_theme_radar: bool,
    market_data_result: MarketDataResult,
    calendar_data_result: CalendarDataResult,
    theme_data_result: ThemeDataResult,
    llm_failure_mode: str = "block",
    llm_fallback_used: bool = False,
) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    warnings: list[str] = []
    blockers: list[str] = []

    if llm_error and llm_fallback_used and llm_failure_mode == "data_only":
        _add_quality_check(
            checks,
            warnings,
            blockers,
            name="narrative_validation",
            status="warning",
            details=(
                "LLM narrative was not accepted, so the run used a clearly labeled data-only fallback. "
                f"Original error: {llm_error}"
            ),
        )
    elif llm_error:
        _add_quality_check(
            checks,
            warnings,
            blockers,
            name="narrative_validation",
            status="failed",
            details=f"LLM narrative was not accepted: {llm_error}",
        )
    elif use_llm and synthesis is not None:
        status = "warning" if synthesis.validation_repair_count else "passed"
        details = (
            "Gemini narrative passed validation "
            f"after {synthesis.validation_attempts} attempt(s); "
            f"repair_count={synthesis.validation_repair_count}."
        )
        if synthesis.validation_errors:
            details += " Earlier validation failures were repaired and are logged."
        _add_quality_check(
            checks,
            warnings,
            blockers,
            name="narrative_validation",
            status=status,
            details=details,
        )
    elif use_llm:
        _add_quality_check(
            checks,
            warnings,
            blockers,
            name="narrative_validation",
            status="failed",
            details="LLM was requested but no synthesis result was produced.",
        )
    else:
        _add_quality_check(
            checks,
            warnings,
            blockers,
            name="narrative_validation",
            status="not_applicable",
            details="LLM synthesis was not requested; deterministic narrative sections were used.",
        )

    if live_market_data:
        market_status = "warning" if market_data_result.cached_assets or market_data_result.fallback_assets else "passed"
        _add_quality_check(
            checks,
            warnings,
            blockers,
            name="market_sources",
            status=market_status,
            details=(
                f"live={len(market_data_result.live_assets)}, "
                f"cached={len(market_data_result.cached_assets)}, "
                f"blank={len(market_data_result.fallback_assets)}. "
                "Blank rows are left empty rather than filled with generated values."
            ),
        )
    else:
        _add_quality_check(
            checks,
            warnings,
            blockers,
            name="market_sources",
            status="not_applicable",
            details="Live market data was not requested.",
        )

    if live_calendar:
        calendar_status = "warning" if calendar_data_result.errors or not calendar_data_result.live_events else "passed"
        _add_quality_check(
            checks,
            warnings,
            blockers,
            name="calendar_sources",
            status=calendar_status,
            details=(
                f"selected_events={len(calendar_data_result.live_events)}, "
                f"errors={len(calendar_data_result.errors)}. "
                "If no verified calendar rows exist, the table is left blank rather than filled with scaffold events."
            ),
        )
    else:
        _add_quality_check(
            checks,
            warnings,
            blockers,
            name="calendar_sources",
            status="not_applicable",
            details="Live calendar data was not requested.",
        )

    if live_theme_radar:
        theme_status = "warning" if theme_data_result.fallback_used or theme_data_result.errors else "passed"
        _add_quality_check(
            checks,
            warnings,
            blockers,
            name="theme_sources",
            status=theme_status,
            details=(
                f"selected_items={len(theme_data_result.selected_titles)}, "
                f"candidate_count={theme_data_result.candidate_count}, "
                f"errors={len(theme_data_result.errors)}. "
                "RSS text, article text excerpts, article metadata, and search snippets are labeled by source depth; no generated replacement items are used."
            ),
        )
    else:
        _add_quality_check(
            checks,
            warnings,
            blockers,
            name="theme_sources",
            status="not_applicable",
            details="Live Theme Radar was not requested.",
        )

    verdict = "failed" if blockers else "warning" if warnings else "passed"
    validation_errors: list[str] = []
    if llm_error:
        validation_errors = [llm_error]
    elif synthesis is not None:
        validation_errors = list(synthesis.validation_errors)
    return {
        "verdict": verdict,
        "send_allowed": not blockers,
        "llm_failure_mode": llm_failure_mode,
        "llm_fallback_used": llm_fallback_used,
        "checks": checks,
        "warnings": warnings,
        "blockers": blockers,
        "narrative_validation_errors": validation_errors,
    }


def _write_log_event(settings: Settings, run_id: str, log_event: dict[str, Any]) -> Path:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    log_path = settings.log_dir / f"run-{run_id}.jsonl"
    log_path.write_text(json.dumps(log_event, indent=2) + "\n", encoding="utf-8")
    return log_path


def _data_only_fallback(data, error: str):
    note = (
        "Data-only fallback: Gemini narrative failed validation, so LLM-written interpretation sections were "
        "withheld. Use the dashboard, calendar, chart, source notes, and run log; do not treat the placeholder "
        "narrative as a portfolio recommendation."
    )
    fallback_item = (
        "LLM narrative synthesis failed validation, so this brief is data-only. "
        "So what: review the verified tables, chart, source notes, and run log before making any portfolio judgment."
    )
    return replace(
        data,
        three_things=[fallback_item],
        three_thing_titles=["Data-Only Fallback"],
        theme_radar=[],
        contrarian_corner=(
            "Contrarian Corner is withheld because Gemini narrative validation failed. "
            "The brief is still delivered only as a data checkpoint, not as an interpreted PM note."
        ),
        source_notes=[*data.source_notes, note],
        assumptions=[*data.assumptions, note],
        data_sources=[*data.data_sources, "data_only_llm_failure_fallback"],
        topic_candidates=[],
    )


def run_brief(
    settings: Settings,
    *,
    send: bool = False,
    run_date: date | None = None,
    use_llm: bool = False,
    live_market_data: bool = False,
    live_calendar: bool = False,
    live_theme_radar: bool = False,
    llm_failure_mode: str | None = None,
) -> RunResult:
    try:
        configured_zone = ZoneInfo(settings.timezone)
    except Exception:  # noqa: BLE001 - config normalization handles common aliases.
        configured_zone = ZoneInfo("Asia/Hong_Kong")
    run_date = run_date or datetime.now(configured_zone).date()
    run_id = utc_run_id()
    llm_failure_mode = llm_failure_mode or settings.llm_failure_mode
    data = build_sample_brief_data()
    data = apply_portfolio_assumptions(data, run_date=run_date, path=settings.portfolio_path)
    market_data_result = MarketDataResult(data=data, live_assets=[], cached_assets=[], fallback_assets=[], errors={}, sources=[])
    calendar_data_result = CalendarDataResult(data=data, live_events=[], fallback_events=[], errors={}, sources=[])
    theme_data_result = ThemeDataResult(data=data, selected_titles=[], candidate_count=0, fallback_used=False, errors={}, sources=[])
    token_usage = ZERO_TOKEN_USAGE
    llm_status = "not_used"
    llm_model = "none"
    estimated_llm_cost_usd = 0.0
    prompt_version = "none"
    synthesis: SynthesisResult | None = None
    llm_error: str | None = None
    llm_fallback_used = False
    llm_failure_diagnostics: dict[str, Any] = {}

    if live_market_data:
        market_data_result = replace_market_rows_with_live(data, run_date=run_date, timezone_name=settings.timezone)
        data = market_data_result.data

    if live_calendar:
        calendar_data_result = replace_calendar_with_live(data, run_date=run_date, timezone_name=settings.timezone)
        data = calendar_data_result.data

    if live_theme_radar:
        theme_data_result = replace_theme_radar_with_live(
            data,
            run_date=run_date,
            history_path=settings.theme_history_path,
            recent_days=settings.theme_recent_days,
            search_queries=DEFAULT_THEME_SEARCH_QUERIES,
            metadata_fetch_limit=settings.theme_metadata_fetch_limit,
            article_fetch_limit=settings.theme_article_fetch_limit,
        )
        data = theme_data_result.data

    if use_llm:
        data = select_portfolio_topics(
            data,
            run_date=run_date,
            portfolio_path=settings.portfolio_path,
            feedback_path=settings.feedback_path,
        )
        if settings.llm_provider != "gemini":
            raise RuntimeError("Only Gemini synthesis is implemented for --use-llm right now")
        try:
            synthesis = synthesize_with_gemini(settings, data)
        except RuntimeError as exc:
            llm_error = str(exc)
            if isinstance(exc, NarrativeValidationFailure):
                token_usage = exc.token_usage
                prompt_version = exc.prompt_version
                llm_failure_diagnostics = {
                    "prompt_version": exc.prompt_version,
                    "token_usage": {
                        "input_tokens": exc.token_usage.input_tokens,
                        "output_tokens": exc.token_usage.output_tokens,
                        "total_tokens": exc.token_usage.total_tokens,
                        "provider": exc.token_usage.provider,
                    },
                    "validation_errors": list(exc.validation_errors),
                    "failed_responses": list(exc.failed_responses),
                }
            if llm_failure_mode == "data_only":
                data = _data_only_fallback(data, llm_error)
                llm_status = "data_only_fallback"
                llm_model = settings.gemini_model
                if not prompt_version or prompt_version == "none":
                    prompt_version = "unknown"
                llm_fallback_used = True
            else:
                quality_report = _build_quality_report(
                    use_llm=use_llm,
                    synthesis=None,
                    llm_error=str(exc),
                    live_market_data=live_market_data,
                    live_calendar=live_calendar,
                    live_theme_radar=live_theme_radar,
                    market_data_result=market_data_result,
                    calendar_data_result=calendar_data_result,
                    theme_data_result=theme_data_result,
                    llm_failure_mode=llm_failure_mode,
                    llm_fallback_used=False,
                )
                _write_log_event(
                    settings,
                    run_id,
                    {
                        "run_id": run_id,
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "run_date": run_date.isoformat(),
                        "run_mode": _effective_run_mode(
                            settings,
                            live_market_data=live_market_data,
                            live_calendar=live_calendar,
                            live_theme_radar=live_theme_radar,
                        ),
                        "llm_provider": settings.llm_provider,
                        "llm_model": settings.gemini_model,
                        "llm_status": "failed_synthesis",
                        "prompt_version": prompt_version if prompt_version != "none" else "unknown",
                        "delivery_status": "blocked_quality_gate" if send else "failed_quality_gate",
                        "quality_report": quality_report,
                        "llm_failure_diagnostics": llm_failure_diagnostics,
                        "delivery_attempted": False,
                        "data_sources": data.data_sources,
                        "source_notes": data.source_notes,
                        "outputs": {},
                    },
                )
                raise RuntimeError(f"Quality gate blocked run before delivery: {exc}") from exc
        if synthesis is not None:
            data = synthesis.data
            token_usage = synthesis.token_usage
            llm_status = "used"
            llm_model = synthesis.model
            estimated_llm_cost_usd = synthesis.estimated_cost_usd
            prompt_version = synthesis.prompt_version

    data = replace(
        data,
        data_sources=_effective_data_sources(
            data.data_sources,
            live_market_data=live_market_data,
            live_calendar=live_calendar,
            live_theme_radar=live_theme_radar,
        ),
        report_time=datetime.now(configured_zone).strftime("%Y-%m-%d %H:%M %Z"),
    )

    output_paths = write_outputs(data, settings.output_dir, run_date)

    quality_report = _build_quality_report(
        use_llm=use_llm,
        synthesis=synthesis,
        llm_error=llm_error,
        live_market_data=live_market_data,
        live_calendar=live_calendar,
        live_theme_radar=live_theme_radar,
        market_data_result=market_data_result,
        calendar_data_result=calendar_data_result,
        theme_data_result=theme_data_result,
        llm_failure_mode=llm_failure_mode,
        llm_fallback_used=llm_fallback_used,
    )

    delivery_status = "dry_run_data_only" if llm_fallback_used else "dry_run"
    if send:
        if not quality_report["send_allowed"]:
            delivery_status = "blocked_quality_gate"
            log_path = _write_log_event(
                settings,
                run_id,
                {
                    "run_id": run_id,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "run_date": run_date.isoformat(),
                    "run_mode": _effective_run_mode(
                        settings,
                        live_market_data=live_market_data,
                        live_calendar=live_calendar,
                        live_theme_radar=live_theme_radar,
                    ),
                    "llm_provider": settings.llm_provider,
                    "llm_model": llm_model,
                    "llm_status": llm_status,
                    "prompt_version": prompt_version,
                    "delivery_status": delivery_status,
                    "quality_report": quality_report,
                    "delivery_attempted": False,
                    "outputs": {key: str(value) for key, value in output_paths.items()},
                },
            )
            blockers = "; ".join(str(blocker) for blocker in quality_report["blockers"])
            raise RuntimeError(f"Quality gate blocked email send: {blockers}. Log: {log_path}") from None
        send_email(
            settings,
            subject=f"Daily Macro Brief - {run_date.isoformat()}",
            text_body=render_markdown(data, run_date),
            html_body=render_html(data, run_date),
            chart_path=output_paths["latest_chart"],
        )
        delivery_status = "sent_data_only" if llm_fallback_used else "sent"

    log_event = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "run_date": run_date.isoformat(),
        "run_mode": _effective_run_mode(
            settings,
            live_market_data=live_market_data,
            live_calendar=live_calendar,
            live_theme_radar=live_theme_radar,
        ),
        "llm_provider": settings.llm_provider,
        "llm_model": llm_model,
        "llm_status": llm_status,
        "prompt_version": prompt_version,
        "delivery_status": delivery_status,
        "quality_report": quality_report,
        "delivery_attempted": send,
        "data_sources": data.data_sources,
        "source_notes": data.source_notes,
        "dashboard_notes": data.dashboard_notes,
        "market_data": {
            "mode": "live_with_fallback" if live_market_data else "sample",
            "live_assets": market_data_result.live_assets,
            "cached_assets": market_data_result.cached_assets,
            "fallback_assets": market_data_result.fallback_assets,
            "errors": market_data_result.errors,
            "sources": market_data_result.sources,
        },
        "calendar_data": {
            "mode": "live_with_fallback" if live_calendar else "sample",
            "live_events": calendar_data_result.live_events,
            "fallback_events": calendar_data_result.fallback_events,
            "errors": calendar_data_result.errors,
            "sources": calendar_data_result.sources,
        },
        "theme_data": {
            "mode": "live_with_fallback" if live_theme_radar else "sample",
            "selected_titles": theme_data_result.selected_titles,
            "candidate_count": theme_data_result.candidate_count,
            "fallback_used": theme_data_result.fallback_used,
            "recent_repeat_titles": theme_data_result.recent_repeat_titles or [],
            "recent_topic_repeat_titles": theme_data_result.recent_topic_repeat_titles or [],
            "errors": theme_data_result.errors,
            "sources": theme_data_result.sources,
        },
        "topic_selection": {
            "selected_titles": data.three_thing_titles,
            "selected_topics": data.topic_candidates,
            "selected_chart": {
                "title": data.chart_title,
                "source_label": data.chart_source_label,
                "source_url": data.chart_source_url,
            },
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
    log_path = _write_log_event(settings, run_id, log_event)

    return RunResult(
        run_id=run_id,
        output_paths=output_paths,
        delivery_status=delivery_status,
        log_path=log_path,
        quality_report=quality_report,
    )
