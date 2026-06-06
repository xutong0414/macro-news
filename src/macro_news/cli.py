from __future__ import annotations

import argparse
import sys
from datetime import date

from .config import Settings
from .runner import run_brief


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="macro-news", description="Daily Macro Brief Agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Generate the daily macro brief")
    mode = run_parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Generate outputs without sending email")
    mode.add_argument("--send", action="store_true", help="Generate outputs and send email via SMTP")
    run_parser.add_argument("--use-llm", action="store_true", help="Use Gemini to draft narrative sections from sample facts")
    run_parser.add_argument("--live-market-data", action="store_true", help="Fetch live market dashboard data with sample fallback rows")
    run_parser.add_argument("--date", help="Run date in YYYY-MM-DD format. Defaults to today.")
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
            result = run_brief(
                settings,
                send=args.send,
                run_date=run_date,
                use_llm=args.use_llm,
                live_market_data=live_market_data,
            )
        except RuntimeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        print(f"Run id: {result.run_id}")
        print(f"Delivery status: {result.delivery_status}")
        print(f"Markdown: {result.output_paths['latest_markdown']}")
        print(f"HTML: {result.output_paths['latest_html']}")
        print(f"Chart: {result.output_paths['latest_chart']}")
        print(f"Log: {result.log_path}")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2
