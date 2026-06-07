# Daily Macro Brief Agent

This repo contains a prototype agent for the case-study assignment. It generates a Daily Macro Brief for a macro PM, renders Markdown/HTML plus a chart, and can send the brief by email through Gmail SMTP.

The brief answers three practical questions:

- What changed overnight?
- Why does it matter for the assumed book?
- What should the reader watch next?

The LLM is deliberately constrained. Code owns market data, calendar data, charting, source links, validation, logging, and email delivery. Gemini drafts only the narrative sections from structured inputs.

## What You Need

- Python 3.11 or newer.
- Internet access for live market/calendar/RSS sources.
- A Gemini API key if you want LLM-written narrative sections.
- A Gmail account with 2-Step Verification and an app password if you want email delivery.
- An always-on machine, VPS, or scheduler service if you want automatic daily delivery.

You can run the sample dry run without any secrets.

## Install

Clone the repo, then from the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Run the test suite:

```bash
PYTHONPATH=src pytest -q
```

## Configure

Create a local `.env` file:

```bash
cp .env.example .env
```

Fill only the values you need. Do not commit `.env`.

Required for Gemini narrative synthesis:

```bash
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash-lite
```

Required for Gmail delivery:

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_gmail_address
SMTP_PASSWORD=your_16_character_gmail_app_password
BRIEF_FROM_EMAIL=your_gmail_address
BRIEF_TO_EMAIL=recipient@example.com
```

Recommended run settings:

```bash
BRIEF_TIMEZONE=Asia/Hong_Kong
PORTFOLIO_PATH=inputs/portfolio/positions.csv
OUTPUT_DIR=outputs
LOG_DIR=logs
```

## Run Locally

Sample dry run, no secrets required:

```bash
PYTHONPATH=src python -m macro_news run --dry-run
```

Live data plus Gemini narrative, no email:

```bash
PYTHONPATH=src python -m macro_news run --dry-run --live-market-data --live-calendar --live-theme-radar --use-llm
```

Send one live brief by email:

```bash
PYTHONPATH=src python -m macro_news run --send --live-market-data --live-calendar --live-theme-radar --use-llm
```

Expected local outputs:

- `outputs/latest/brief.md`
- `outputs/latest/brief.html`
- `outputs/latest/chart.png`
- `outputs/archive/YYYY-MM-DD/`
- `logs/run-*.jsonl`

Generated outputs and logs are ignored by git.

## Brief Contents

The generated brief includes the six required assignment modules:

1. Overnight market dashboard.
2. The 3 Things That Matter Today.
3. Today's Calendar / Next Session.
4. One Chart Worth Seeing.
5. Theme Radar.
6. Contrarian Corner.

It also includes a feedback questionnaire, source status, and assumptions so the reader can audit what was used.

## Data Sources

Current live sources:

- Market dashboard: Yahoo Finance quote/chart data, Japan MOF JGB yield CSV, Frankfurter FX reference rates, and CoinGecko BTC data.
- Calendar: Fair Economy / Forex Factory weekly calendar feed.
- Theme Radar: curated RSS feeds from Liberty Street Economics, Bank Underground, and FRED Blog when reachable.
- Chart: USD/JPY daily reference-rate history from Frankfurter.

Live mode does not use generated/sample market, calendar, or Theme Radar fallback content. If a live source and cached real row are both unavailable, the relevant value cells or section are left blank rather than filled with invented values.

## Portfolio And Feedback Inputs

Portfolio assumptions live in:

```text
inputs/portfolio/positions.csv
```

Each row is an effective-date update. If there is no new row for a run date, the latest prior row carries forward. See `inputs/portfolio/README.md`.

Human feedback is tracked with:

```text
inputs/feedback/daily_feedback.example.csv
```

The current feedback loop is local preference memory, not model fine-tuning. See `inputs/feedback/README.md`.

## Scheduling

The command can be scheduled by any system that can run a shell command and access the `.env` file.

Recommended production-style path:

```bash
/bin/bash /ABSOLUTE/PATH/TO/macro_news/scripts/run_daily_brief.sh
```

For a 07:30 Hong Kong inbox target, schedule the job around 07:15 Hong Kong time so there is buffer for data fetching, Gemini synthesis, rendering, and email delivery.

### Weekday Schedule Examples

Cron has five time fields:

```text
minute hour day-of-month month day-of-week
```

For this project, the important fields are usually minute, hour, and day-of-week. In cron, `1-5` means Monday-Friday.

If the machine timezone is already set to Hong Kong time and the agent should **start working at 08:30 Monday-Friday**, use:

```cron
30 8 * * 1-5 cd /ABSOLUTE/PATH/TO/macro_news && /bin/bash scripts/run_daily_brief.sh >> logs/scheduler.out.log 2>> logs/scheduler.err.log
```

If the machine timezone is UTC and the target is **08:30 Hong Kong time Monday-Friday**, use 00:30 UTC Monday-Friday:

```cron
30 0 * * 1-5 cd /ABSOLUTE/PATH/TO/macro_news && /bin/bash scripts/run_daily_brief.sh >> logs/scheduler.out.log 2>> logs/scheduler.err.log
```

If the goal is for the email to **arrive around 08:30**, start earlier, for example 08:15 Hong Kong time:

```cron
15 8 * * 1-5 cd /ABSOLUTE/PATH/TO/macro_news && /bin/bash scripts/run_daily_brief.sh >> logs/scheduler.out.log 2>> logs/scheduler.err.log
```

For GitHub Actions schedules, cron is always UTC. The same 08:30 Hong Kong weekday start would be:

```yaml
on:
  schedule:
    - cron: "30 0 * * 1-5"
```

GitHub schedules can be delayed or skipped, so this repo treats GitHub manual runs as the reliable GitHub path and recommends `cron`, `launchd`, `systemd`, or a cloud scheduler for dependable daily sending.

Supported scheduler options:

- macOS `launchd` on an always-on Mac.
- Linux `cron` or `systemd` on a workstation or VPS.
- A cloud scheduler that triggers a deployed job or GitHub manual workflow.

See `docs/scheduling.md` and `scheduling/com.macro-news.daily-brief.plist.example`.

Note: manual GitHub Actions sends are proven, but short-window GitHub scheduled-trigger tests were unreliable in this repo. For dependable timing, use a scheduler you control.

## GitHub Actions

The repo includes three workflows:

- `daily-brief-dry-run.yml`: safe sample dry run, no secrets and no email. This is the only enabled GitHub scheduled workflow, and it runs a sample dry run on weekdays.
- `daily-brief-live-dry-run.yml`: manual live-source dry run with secrets, no email.
- `daily-brief-manual-send.yml`: manual live email send, requiring `SEND` confirmation.

For GitHub live runs or sends, add repository secrets matching `.env.example`:

- `GEMINI_API_KEY`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `BRIEF_FROM_EMAIL`
- `BRIEF_TO_EMAIL`
- `BRIEF_TIMEZONE`

## Assignment Files

- `memo.pdf`: final one-page memo for the assignment.
- `memo.md`: memo source.
- `costs.md`: token, runtime, delivery, source, and scheduler cost notes.
- `ASSIGNMENT_AUDIT.md`: requirement checklist against the assignment PDF.
- `PLAN.md`: current project status and submission checklist.
- `DECISIONS.md`: decision log and implementation rationale.

The assignment PDF is intentionally kept local and ignored by git.

## Current Caveats

- Free public data sources can timeout, rate-limit, or lag on weekends and holidays.
- Theme Radar currently uses RSS-level text, not full article text.
- Scheduled delivery requires an always-on machine or scheduler service.
- GitHub scheduled events are not treated as the dependable production scheduler for this prototype.
