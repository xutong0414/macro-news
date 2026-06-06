from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from .config import Settings
from .emailer import send_email
from .render import render_html, render_markdown, utc_run_id, write_outputs
from .sample_data import build_sample_brief_data


@dataclass(frozen=True)
class RunResult:
    run_id: str
    output_paths: dict[str, Path]
    delivery_status: str
    log_path: Path


def run_brief(settings: Settings, *, send: bool = False, run_date: date | None = None) -> RunResult:
    run_date = run_date or date.today()
    run_id = utc_run_id()
    data = build_sample_brief_data()
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
        "llm_model": settings.gemini_model if settings.llm_provider == "gemini" else settings.deepseek_model,
        "delivery_status": delivery_status,
        "data_sources": data.data_sources,
        "token_usage": {"input_tokens": 0, "output_tokens": 0, "provider": "none_sample_mode"},
        "outputs": {key: str(value) for key, value in output_paths.items()},
    }
    log_path.write_text(json.dumps(log_event, indent=2) + "\n", encoding="utf-8")

    return RunResult(run_id=run_id, output_paths=output_paths, delivery_status=delivery_status, log_path=log_path)

