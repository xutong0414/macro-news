# Daily Macro Brief Agent

Prototype for the case study assignment: a scheduled agent that sends a concise Daily Macro Brief to an email inbox before the market day starts.

The target reader is a macro PM who wants: what changed overnight, why it matters, and what it means for an assumed book. The project starts local-first with sample data, then adds live market/calendar/content APIs and scheduled delivery.

## Current Status

Stage: polished live prototype with Gemini synthesis, Gmail delivery, live market rows including Japan 10Y, EUR/USD, and USD/JPY, dashboard timing/source notes with clickable source links, cached real-source market fallback, live economic-calendar rows with Asia/Europe/US session targeting, live Theme Radar source collection with fallback, GitHub manual-send automation, and confirmed MacBook `launchd` scheduled delivery with inbox receipt. Short-window GitHub schedule tests did not produce scheduled runs, so dependable scheduled delivery is routed through the documented local/server scheduler path.

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

Run with live Theme Radar source collection and sample fallback:

```bash
PYTHONPATH=src python -m macro_news run --dry-run --live-theme-radar
```

Run with all live data layers and Gemini narrative synthesis:

```bash
PYTHONPATH=src python -m macro_news run --dry-run --live-market-data --live-calendar --live-theme-radar --use-llm
```

Send a sample brief by email:

```bash
PYTHONPATH=src python -m macro_news run --send --use-llm
```

Send the fuller prototype brief by email:

```bash
PYTHONPATH=src python -m macro_news run --send --live-market-data --live-calendar --live-theme-radar --use-llm
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
- `MARKET_DATA_MODE=live` fetches live dashboard rows where available, uses cached real-source rows for temporary outages, and falls back to sample rows asset by asset only when neither live nor cached data is available.

Calendar data mode:

- `CALENDAR_MODE=sample` keeps the calendar deterministic.
- `CALENDAR_MODE=live` fetches the weekly economic calendar where available, targets Asia/Europe/US session coverage, uses a local ignored cache after successful pulls, and falls back to sample rows if the public feed is unavailable or rate-limited.

Theme source mode:

- `THEME_SOURCE_MODE=sample` keeps Theme Radar deterministic.
- `THEME_SOURCE_MODE=live` fetches curated RSS feeds, scores items against the assumed book/themes, and falls back to sample Theme Radar items if source collection fails.

Do not commit `.env`.

## Assignment Modules

The final brief must include:

1. Overnight market dashboard as a table.
2. The 3 things that matter today, each with a clear "so what" paragraph and a reader-facing news link.
3. Today's calendar across Asia, EU, and US sessions with consensus.
4. One chart worth seeing with a caption under 30 words.
5. Theme radar summaries tied to assumed positions/themes.
6. Contrarian corner.

The 3 Things section keeps Gemini responsible for concise PM-facing narrative, while rendering code adds compact item sub-titles, styles `So what:` as a smaller support line, and adds deterministic Yahoo Finance topic-search links. The LLM does not invent news links.

## Current Data Sources

The market dashboard currently uses:

- [Yahoo Finance chart endpoint](https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC) for broad equity, US rate, dollar, gold, and oil instruments.
- [Japan MOF JGB yield CSV](https://www.mof.go.jp/jgbs/reference/interest_rate/jgbcm.csv) for Japan 10Y.
- [Frankfurter](https://frankfurter.dev/) for EUR/USD and USD/JPY daily reference-rate rows.
- [CoinGecko](https://www.coingecko.com/en/api) for BTC.
- Dashboard notes explaining extraction time, close/prior basis, additional timing information for Hong Kong morning use, Frankfurter's latest-versus-immediately-previous published daily reference-rate convention, and BTC rolling 24-hour change convention.
- Dashboard row read-throughs use the `Why it matters` label and describe the day's implication rather than repeating the instrument definition.
- Cached real-source rows when a temporary source outage occurs.
- Sample fallback rows when a source fails and no cached real-source row exists.

The calendar currently uses:

- Forex Factory/Fair Economy weekly JSON feed for event names, impact, forecast/consensus, and previous values.
- Session-aware selection that targets Asia, Europe, and US coverage when the feed contains usable events.
- Local ignored cache under `.cache/calendar/` after successful pulls.
- Sample fallback rows when the feed fails or is rate-limited.

Theme Radar currently uses:

- Liberty Street Economics RSS.
- Bank Underground RSS.
- FRED Blog RSS when reachable.
- Keyword scoring against the assumed book and house themes.
- Sample fallback items when no relevant source candidates are found.

## GitHub Actions

The first workflow is intentionally safe:

- `.github/workflows/daily-brief-dry-run.yml`
- Runs on manual trigger and weekday schedule.
- Installs dependencies.
- Runs tests.
- Generates a sample dry-run brief.
- Uploads generated outputs/logs as workflow artifacts.
- Uses no secrets and sends no email.

The second workflow tests the live prototype without sending email:

- `.github/workflows/daily-brief-live-dry-run.yml`
- Runs only on manual trigger.
- Reads GitHub Secrets for Gemini and Gmail configuration.
- Runs tests.
- Generates a live-source dry-run brief with Gemini narrative synthesis.
- Uploads generated outputs/logs as workflow artifacts.
- Sends no email.

The third workflow sends one real live brief only when manually confirmed:

- `.github/workflows/daily-brief-manual-send.yml`
- Runs only on manual trigger.
- Requires typing `SEND` in the confirmation input.
- Reads GitHub Secrets for Gemini and Gmail configuration.
- Runs tests.
- Sends one live-source email brief.
- Uploads generated outputs/logs as workflow artifacts.

The temporary scheduler smoke test was removed after an inconclusive short-window test. GitHub recognized the workflow as active, but no scheduled run appeared during the test window.

The temporary scheduled email proof workflow was also removed after the proof window ended:

- GitHub recognized the workflow as active.
- The 2026-06-06 17:40-18:15 Hong Kong test window produced zero scheduled runs.
- Because no workflow run was created, the failure was at GitHub's scheduled trigger layer, not in Python, Gemini, or Gmail delivery.

The next workflow step is to keep the proven manual GitHub send workflow and use an external or local/server scheduler when precise timing is required.

## Scheduling

See `docs/scheduling.md` for the scheduler plan.

Key idea: the brief command is proven, but a separate scheduler must wake it. Manual GitHub send is confirmed; GitHub scheduled events failed our short-window proof; a MacBook `launchd` one-shot scheduled send succeeded. For dependable daily delivery, use an always-on Mac with `launchd`, a Linux workstation/VPS with `cron` or `systemd`, or a cloud scheduler.

The reusable scheduler command is:

```bash
/bin/bash /ABSOLUTE/PATH/TO/macro_news/scripts/run_daily_brief.sh
```

## Repo Control Files

- `PLAN.md`: live control tower and handoff state.
- `DECISIONS.md`: decision log.
- `costs.md`: expected and measured run costs.
- `memo.md`: working source for the final 1-page memo.
