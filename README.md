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

You can run the first sample dry run without any secrets.

## 1. Install

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

## 2. Configure From The Sample Env File

The sample environment file is `.env.example`. Copy it to `.env`:

```bash
cp .env.example .env
```

Then edit `.env`. Do not commit `.env`.

Some projects call this file `.env_sample`; this repo uses the common `.env.example` name so GitHub and new users can see the required variables without seeing any secrets.

Minimum values for Gemini narrative synthesis:

```bash
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash-lite
```

Minimum values for Gmail delivery:

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

Notes:

- For Gmail, use an app password, not the normal Google login password.
- Gmail app passwords are usually shown in groups of four characters; remove spaces in `.env`.
- Keep optional providers such as DeepSeek blank unless you add provider support.

## 3. Run Locally

Start with the safe sample dry run:

```bash
PYTHONPATH=src python -m macro_news run --dry-run
```

Then test live sources and Gemini without sending email:

```bash
PYTHONPATH=src python -m macro_news run --dry-run --live-market-data --live-calendar --live-theme-radar --use-llm
```

Finally, send one live email:

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

## 4. Run On A Schedule

The scheduled time is the time the agent starts working. The email is sent only after data fetching, Gemini synthesis, rendering, and SMTP delivery finish.

If the desired inbox time is 08:30 Hong Kong time, schedule the job around 08:15 Hong Kong time. If the intended requirement is literally "start working at 08:30," schedule 08:30.

The reusable scheduled command is:

```bash
/bin/bash /ABSOLUTE/PATH/TO/macro_news/scripts/run_daily_brief.sh
```

### Cron Examples

Cron has five time fields:

```text
minute hour day-of-month month day-of-week
```

In cron, `1-5` means Monday-Friday.

Start at 08:30 Monday-Friday on a machine set to Hong Kong time:

```cron
30 8 * * 1-5 cd /ABSOLUTE/PATH/TO/macro_news && /bin/bash scripts/run_daily_brief.sh >> logs/scheduler.out.log 2>> logs/scheduler.err.log
```

Start at 08:15 Monday-Friday on a machine set to Hong Kong time, for an approximately 08:30 inbox target:

```cron
15 8 * * 1-5 cd /ABSOLUTE/PATH/TO/macro_news && /bin/bash scripts/run_daily_brief.sh >> logs/scheduler.out.log 2>> logs/scheduler.err.log
```

Start at 08:30 Hong Kong time from a machine set to UTC:

```cron
30 0 * * 1-5 cd /ABSOLUTE/PATH/TO/macro_news && /bin/bash scripts/run_daily_brief.sh >> logs/scheduler.out.log 2>> logs/scheduler.err.log
```

Start at 07:15 Hong Kong time from a UTC machine:

```cron
15 23 * * 0-4 cd /ABSOLUTE/PATH/TO/macro_news && /bin/bash scripts/run_daily_brief.sh >> logs/scheduler.out.log 2>> logs/scheduler.err.log
```

The last example uses Sunday-Thursday UTC because 23:15 UTC maps to 07:15 Hong Kong time on the following Monday-Friday.

Temporary local schedule test:

If the machine timezone is Hong Kong time, testing starts at 12:30, and you want to prove a scheduled email around 12:36, use:

```cron
36 12 * * * cd /ABSOLUTE/PATH/TO/macro_news && /bin/bash scripts/run_daily_brief.sh >> logs/scheduler.out.log 2>> logs/scheduler.err.log
```

Remove or comment this test line immediately after one successful email. Cron repeats it daily until it is removed.

### macOS launchd

Use:

```text
scheduling/com.macro-news.daily-brief.plist.example
```

Copy it to `~/Library/LaunchAgents/`, replace the placeholder paths, and load it with `launchctl`. See `docs/scheduling.md` for details.

### GitHub Actions Schedule

GitHub cron uses UTC. There are two common patterns.

Production weekday morning send:

A weekday 08:15 Hong Kong schedule is:

```yaml
on:
  schedule:
    - cron: "15 0 * * 1-5"
```

Temporary GitHub schedule test:

If testing starts at 12:30 Hong Kong time and you want a run around 12:36 Hong Kong time, convert 12:36 HKT to 04:36 UTC:

```yaml
on:
  schedule:
    - cron: "36 4 * * *"
```

This test schedule is not one-time. It repeats daily until you comment or remove it, and GitHub may still delay or skip the scheduled trigger.

The real email-send workflow already contains both schedules as commented templates in:

```text
.github/workflows/daily-brief-manual-send.yml
```

They are commented out on purpose. The file is in place as a template, but automatic email sending is disabled until a maintainer explicitly uncomments one `schedule:` block. Use only one scheduled-send block at a time, and comment it again after a temporary test. The reliable GitHub path in this repo is the manual send workflow.

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

## GitHub Actions

The repo includes three active workflows:

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
- Scheduled delivery requires an always-on machine or external scheduler.
- GitHub scheduled events are documented but not treated as the dependable production scheduler for this prototype.
