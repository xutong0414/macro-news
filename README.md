# Daily Macro Brief Agent

Prototype for the case study assignment: a scheduled agent that sends a concise Daily Macro Brief to an email inbox before the market day starts.

The target reader is a macro PM who wants: what changed overnight, why it matters, and what it means for an assumed book. The project starts local-first with sample data, then adds live market/calendar/content APIs and scheduled delivery.

## Current Status

Stage: local agent loop with Gemini synthesis, Gmail delivery, live market rows, and live economic-calendar rows with fallback.

Locked defaults:

- Delivery: Gmail SMTP first.
- LLM: Gemini 2.5 Flash-Lite first.
- DeepSeek: optional provider later.
- GitHub: after the local scaffold and dry run work.

The assignment PDF is kept local and is intentionally not committed to git.

## Quickstart

Run the first sample dry run without secrets:

```bash
PYTHONPATH=src python -m macro_news run --dry-run
```

Run a sample dry run with Gemini drafting the narrative sections:

```bash
PYTHONPATH=src python -m macro_news run --dry-run --use-llm
```

Run with live market dashboard data and sample fallbacks:

```bash
PYTHONPATH=src python -m macro_news run --dry-run --live-market-data
```

Run with live economic calendar data and sample fallback:

```bash
PYTHONPATH=src python -m macro_news run --dry-run --live-calendar
```

Run with live market dashboard data, live calendar data, and Gemini narrative synthesis:

```bash
PYTHONPATH=src python -m macro_news run --dry-run --live-market-data --live-calendar --use-llm
```

Send a sample brief by email:

```bash
PYTHONPATH=src python -m macro_news run --send --use-llm
```

Send the fuller prototype brief by email:

```bash
PYTHONPATH=src python -m macro_news run --send --live-market-data --live-calendar --use-llm
```

Expected local outputs:

- `outputs/latest/brief.md`
- `outputs/latest/brief.html`
- `outputs/latest/chart.png`
- `outputs/archive/YYYY-MM-DD/`
- `logs/run-*.jsonl`

Install for command-line use after dependencies are ready:

```bash
python -m pip install -e .
macro-news run --dry-run
```

## Email And LLM Setup

Create a local `.env` file from `.env.example`.

Required for sending:

- `SMTP_HOST=smtp.gmail.com`
- `SMTP_PORT=587`
- `SMTP_USER`
- `SMTP_PASSWORD` from a Gmail app password
- `BRIEF_FROM_EMAIL`
- `BRIEF_TO_EMAIL`

Required for Gemini synthesis:

- `LLM_PROVIDER=gemini`
- `GEMINI_API_KEY`
- `GEMINI_MODEL=gemini-2.5-flash-lite`

Market data mode:

- `MARKET_DATA_MODE=sample` keeps the dashboard fully deterministic.
- `MARKET_DATA_MODE=live` fetches live dashboard rows where available and falls back to sample rows asset by asset.

Calendar data mode:

- `CALENDAR_MODE=sample` keeps the calendar deterministic.
- `CALENDAR_MODE=live` fetches the weekly economic calendar where available, uses a local ignored cache after successful pulls, and falls back to sample rows if the public feed is unavailable or rate-limited.

Do not commit `.env`.

## Assignment Modules

The final brief must include:

1. Overnight market dashboard as a table.
2. The 3 things that matter today, each with a clear "so what."
3. Today's calendar across Asia, EU, and US sessions with consensus.
4. One chart worth seeing with a caption under 30 words.
5. Theme radar summaries tied to assumed positions/themes.
6. Contrarian corner.

## Current Data Sources

The market dashboard currently uses:

- Yahoo Finance chart endpoint for broad equity, rate, dollar, gold, and oil instruments.
- Frankfurter for USD/JPY.
- CoinGecko for BTC.
- Sample fallback rows when a source fails or is not yet connected.

The calendar currently uses:

- Forex Factory/Fair Economy weekly JSON feed for event names, impact, forecast/consensus, and previous values.
- Local ignored cache under `.cache/calendar/` after successful pulls.
- Sample fallback rows when the feed fails or is rate-limited.

The next missing live piece is non-mainstream source collection for Theme Radar.

## Repo Control Files

- `PLAN.md`: live control tower and handoff state.
- `DECISIONS.md`: decision log.
- `costs.md`: expected and measured run costs.
- `memo.md`: working source for the final 1-page memo.
