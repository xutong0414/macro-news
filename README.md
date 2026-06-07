# Daily Macro Brief Agent

Prototype for the case study assignment: a scheduled agent that sends a concise Daily Macro Brief to an email inbox before the market day starts.

The target reader is a macro PM who wants: what changed overnight, why it matters, and what it means for an assumed book. The project starts local-first with sample data, then adds live market/calendar/content APIs and scheduled delivery.

## Current Status

Stage: polished live prototype with Gemini synthesis, Gmail delivery, live market rows including Japan 10Y, EUR/USD, and USD/JPY, row-level `As of`/`Status` labels, dashboard timing/source notes with clickable source links, cached real-source fallback, no generated scaffold values in live market/calendar/theme fallback paths, a USD/JPY chart reading linked to the first thing that matters, live/cached economic-calendar rows with event-date/status labels, live Theme Radar source collection with source-depth labels, factual guardrails for market-number consistency and unsupported narrative claims, portfolio assumptions loaded from `inputs/portfolio/positions.csv`, GitHub manual-send automation, and confirmed MacBook `launchd` scheduled delivery with inbox receipt. Short-window GitHub schedule tests did not produce scheduled runs, so dependable scheduled delivery is routed through the documented local/server scheduler path.

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

Run with live market dashboard data and cached real-source fallback:

```bash
PYTHONPATH=src python -m macro_news run --dry-run --live-market-data
```

Run with live economic calendar data and cached real-source fallback:

```bash
PYTHONPATH=src python -m macro_news run --dry-run --live-calendar
```

Run with live Theme Radar source collection:

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
- `MARKET_DATA_MODE=live` fetches live dashboard rows where available and uses cached real-source rows for temporary outages. If neither live nor cached real data exists, the row's value cells are left blank instead of using scaffold/sample numbers.

Calendar data mode:

- `CALENDAR_MODE=sample` keeps the calendar deterministic.
- `CALENDAR_MODE=live` fetches the weekly economic calendar where available, targets Asia/Europe/US session coverage, uses a local ignored cache after successful pulls, and leaves the calendar blank instead of using scaffold/sample rows if no live or cached real calendar data exists.

Theme source mode:

- `THEME_SOURCE_MODE=sample` keeps Theme Radar deterministic.
- `THEME_SOURCE_MODE=live` fetches curated RSS feeds, scores items against the assumed book/themes, and leaves Theme Radar blank instead of using scaffold/sample source items if no verified source candidates are available.

Portfolio input:

- `PORTFOLIO_PATH=inputs/portfolio/positions.csv` points to the position-assumption CSV.
- Each row is an effective-date update. If no row is entered for the run date, the latest prior row for that asset carries forward.
- Use `position=flat`, `closed`, `none`, or `0` to remove an asset from the active book.

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
- Dashboard row read-throughs use the `Reading` label and describe the day's implication rather than repeating the instrument definition.
- The dashboard includes `As of` and `Status` columns. `Live` means refreshed from a public source for the run date or query time; `*` means the live source's latest valid date is older than the run date, usually because of weekend, holiday, or publication lag; `†` means cached real-source data was used after a live refresh failed.
- Cached real-source rows when a temporary source outage occurs.
- Blank value cells rather than scaffold/sample market numbers when no live or cached real row exists.

The calendar currently uses:

- Forex Factory/Fair Economy weekly JSON feed for event names, impact, forecast/consensus, and previous values.
- Session-aware selection that targets Asia, Europe, and US coverage when the feed contains usable events.
- Local ignored cache under `.cache/calendar/` after successful pulls.
- Event-date and status labels using the same `Live`, `*`, and `†` no-color convention.
- Blank calendar output rather than scaffold/sample calendar rows when no live or cached real calendar rows exist.

Theme Radar currently uses:

- Liberty Street Economics RSS.
- Bank Underground RSS.
- FRED Blog RSS when reachable.
- Keyword scoring against the assumed book and house themes.
- Source-depth labels in the rendered brief, such as `RSS excerpt` or `RSS content field`. This tells the reader whether the summary is based on feed-level text rather than a full article.
- Blank live-mode output rather than scaffold/sample source items when no relevant verified source candidates are found.

## Portfolio And Feedback Inputs

Tracked assignment assumptions live in `inputs/portfolio/positions.csv`. The format is documented in `inputs/portfolio/README.md`, with `positions.example.csv` as a template.

Human feedback is documented in `inputs/feedback/README.md`, with `daily_feedback.example.csv` as the questionnaire template. The current rule is to record feedback locally first; later versions can load high-rated and low-rated patterns into source ranking and prompt construction. This is local preference memory, not model fine-tuning.

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
