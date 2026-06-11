from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

from .config import Settings
from .model_compare import compare_gemini_models
from .runner import run_brief


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="macro-news", description="Daily Macro Brief Agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Generate the daily macro brief")
    mode = run_parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Generate outputs without sending email")
    mode.add_argument("--send", action="store_true", help="Generate outputs and send email via SMTP")
    run_parser.add_argument("--use-llm", action="store_true", help="Use Gemini to draft narrative sections from sample facts")
    run_parser.add_argument("--live-market-data", action="store_true", help="Fetch live market dashboard data with cached real-source fallback and blank rows for unavailable data")
    run_parser.add_argument("--live-calendar", action="store_true", help="Fetch live economic-calendar rows with cached real-source fallback and blank output if unavailable")
    run_parser.add_argument("--live-theme-radar", action="store_true", help="Fetch live Theme Radar source candidates and leave the section blank if unavailable")
    run_parser.add_argument("--date", help="Run date in YYYY-MM-DD format. Defaults to today.")

    compare_parser = subparsers.add_parser("compare-models", help="Compare Gemini models on the same brief inputs without sending email")
    compare_parser.add_argument(
        "--models",
        nargs="+",
        help="Gemini model names to compare. Defaults to GEMINI_MODEL and gemini-2.5-pro.",
    )
    compare_parser.add_argument("--live-market-data", action="store_true", help="Use live market data in the comparison input")
    compare_parser.add_argument("--live-calendar", action="store_true", help="Use live calendar data in the comparison input")
    compare_parser.add_argument("--live-theme-radar", action="store_true", help="Use live Theme Radar data in the comparison input")
    compare_parser.add_argument("--date", help="Run date in YYYY-MM-DD format. Defaults to today.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        settings = Settings.from_env()
        run_date = date.fromisoformat(args.date) if args.date else None

        if args.send:
            missing = settings.missing_for_send()
            if missing:
                parser.error("Missing required email environment variables for --send: " + ", ".join(missing))
        if args.use_llm and not settings.gemini_api_key:
            parser.error("GEMINI_API_KEY is required for --use-llm")

        try:
            live_market_data = args.live_market_data or settings.market_data_mode == "live"
            live_calendar = args.live_calendar or settings.calendar_mode == "live"
            live_theme_radar = args.live_theme_radar or settings.theme_source_mode == "live"
            result = run_brief(
                settings,
                send=args.send,
                run_date=run_date,
                use_llm=args.use_llm,
                live_market_data=live_market_data,
                live_calendar=live_calendar,
                live_theme_radar=live_theme_radar,
            )
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Run id: {result.run_id}")
        print(f"Delivery status: {result.delivery_status}")
        print(f"Quality verdict: {result.quality_report.get('verdict', 'unknown')}")
        print(f"Markdown: {result.output_paths['latest_markdown']}")
        print(f"HTML: {result.output_paths['latest_html']}")
        print(f"Chart: {result.output_paths['latest_chart']}")
        print(f"Log: {result.log_path}")
        return 0

    if args.command == "compare-models":
        settings = Settings.from_env()
        if not settings.gemini_api_key:
            parser.error("GEMINI_API_KEY is required for compare-models")
        run_date = date.fromisoformat(args.date) if args.date else datetime.now(ZoneInfo(settings.timezone)).date()
        models = args.models or [settings.gemini_model, "gemini-2.5-pro"]

        try:
            results, log_path = compare_gemini_models(
                settings,
                models=models,
                run_date=run_date,
                live_market_data=args.live_market_data,
                live_calendar=args.live_calendar,
                live_theme_radar=args.live_theme_radar,
            )
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        print("Model comparison:")
        for result in results:
            cost_label = f"${result.estimated_cost_usd:.8f}"
            if result.total_tokens and result.estimated_cost_usd == 0.0 and result.model != "gemini-2.5-flash-lite":
                cost_label = "n/a"
            print(
                f"- {result.model}: {result.status}; "
                f"repairs={result.validation_repair_count}; "
                f"tokens={result.total_tokens}; "
                f"cost={cost_label}; "
                f"elapsed={result.elapsed_seconds:.2f}s"
                + (f"; error={result.error}" if result.error else "")
            )
        print(f"Log: {log_path}")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2
