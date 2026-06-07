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

Run these commands in Terminal from the project root. Keep the virtual environment active if you created one with `source .venv/bin/activate`.

### Step 3.1: Sample Dry Run

Run in Terminal:

```bash
PYTHONPATH=src python -m macro_news run --dry-run
```

Expected outcome:

- No secrets are needed.
- No email is sent.
- The project creates or updates `outputs/latest/brief.md`, `outputs/latest/brief.html`, `outputs/latest/chart.png`, and a run log under `logs/`.
- The content uses sample data, so this step only checks that the framework runs.

### Step 3.2: Live Dry Run

Run in Terminal after `.env` has a valid Gemini API key:

```bash
PYTHONPATH=src python -m macro_news run --dry-run --live-market-data --live-calendar --live-theme-radar --use-llm
```

Expected outcome:

- Live market, calendar, and RSS sources are queried.
- Gemini writes the narrative sections from structured inputs.
- No email is sent.
- Inspect `outputs/latest/brief.html` and `outputs/latest/brief.md`.

### Step 3.3: Send One Email

Run in Terminal after `.env` has both Gemini and Gmail SMTP values:

```bash
PYTHONPATH=src python -m macro_news run --send --live-market-data --live-calendar --live-theme-radar --use-llm
```

Expected outcome:

- One email is sent to `BRIEF_TO_EMAIL`.
- The same local output files and logs are updated.
- If delivery fails, check the Gmail app password, sender email, recipient email, and `.env` spelling.

Expected output files:

- `outputs/latest/brief.md`
- `outputs/latest/brief.html`
- `outputs/latest/chart.png`
- `outputs/archive/YYYY-MM-DD/`
- `logs/run-*.jsonl`

Generated outputs and logs are ignored by git.

## 4. Run On A Schedule

Scheduling means another program wakes up this agent at a chosen time and runs the send command for you.

Important idea:

- The schedule time is when the agent starts working.
- The email is sent after data fetching, Gemini synthesis, rendering, and SMTP delivery finish.
- If the target inbox time is 08:30 Hong Kong time, start around 08:15.
- Closing VS Code does not matter for `cron`, `launchd`, or GitHub Actions.
- For local schedulers, the computer must be powered on and awake enough to run the job.
- For GitHub Actions, your local computer does not need to be on, but GitHub scheduled triggers can be delayed or skipped.

The command that the scheduler should run is:

```bash
/bin/bash /ABSOLUTE/PATH/TO/macro_news/scripts/run_daily_brief.sh
```

This is not something you type every morning. You put this command into a scheduler once.

### Linux Or Server Cron

Use this if the project runs on Linux, a VPS, or another Unix-like server.

Run in Terminal:

```bash
crontab -e
```

Then paste one schedule line into the editor.

Cron has five timing fields:

```text
minute hour day-of-month month day-of-week
```

Production weekday morning example:

To start at 08:15 Hong Kong time Monday-Friday on a machine using UTC, paste:

```cron
15 0 * * 1-5 cd /ABSOLUTE/PATH/TO/macro_news && /bin/bash scripts/run_daily_brief.sh >> logs/scheduler.out.log 2>> logs/scheduler.err.log
```

Why this works:

- `15` means minute 15.
- `0` means hour 00 in UTC.
- Hong Kong is UTC+8, so 00:15 UTC is 08:15 HKT.
- `* *` means any day of month and any month.
- `1-5` means Monday-Friday.
- The `cd ...` part moves into the project folder before running the script.
- The `>> logs/...` parts save scheduler output and errors.

Temporary cron test:

If testing starts at 12:30 HKT and you want one test run around 12:36 HKT, convert 12:36 HKT to 04:36 UTC, then paste:

```cron
36 4 * * * cd /ABSOLUTE/PATH/TO/macro_news && /bin/bash scripts/run_daily_brief.sh >> logs/scheduler.out.log 2>> logs/scheduler.err.log
```

Remove this test line after one successful email. It repeats daily until removed.

### macOS

Use macOS `launchd`.

Quick schedule test:

After the manual send command works, run this in Terminal from the repo folder to schedule one test run about 5 minutes from now:

```bash
/bin/bash scripts/install_launchd_test_send.sh 5
```

Expected outcome:

- The script creates and loads a temporary macOS schedule.
- One email should arrive around 5 minutes later.
- After the email arrives, run the `launchctl bootout ...` command printed by the script.

This test schedule repeats daily if you do not unload it.

Production weekday schedule:

Edit this file, not in Terminal:

```text
scheduling/com.macro-news.daily-brief.plist.example
```

Replace the placeholder paths, copy it to `~/Library/LaunchAgents/`, and load it with `launchctl`. The exact Terminal commands are in `docs/scheduling.md`.

VS Code does not need to stay open. The Mac does need to be on and awake enough for `launchd` to run.

### Windows

Windows uses Task Scheduler, which is different from macOS `launchd` and Linux `cron`.

This repo does not include a Windows Task Scheduler template. The simplest Windows path is to run the project inside WSL and use the Linux `cron` approach above. Otherwise, create a Windows Task Scheduler job that runs the same scheduled command through a shell that can execute `.sh` scripts.

### GitHub Actions

Use this if you want GitHub to provide the computer power.

Important: GitHub Actions is useful for manual cloud runs, but it is not a stable or fully trustworthy scheduler for a time-sensitive daily email. Scheduled runs can be delayed, skipped, or affected by GitHub runner availability. For dependable weekday morning delivery, use `launchd`, `cron`, `systemd`, a VPS, or a cloud scheduler you control.

Do not run the schedule examples in Terminal. Edit this workflow file:

```text
.github/workflows/daily-brief-manual-send.yml
```

Before enabling a schedule:

1. Add GitHub repository secrets listed in `.env.example`.
2. Run the manual send workflow once from the GitHub Actions page.
3. Confirm the email arrives.

The workflow file contains two commented schedule templates. Uncomment only one at a time.

Production weekday morning send:

This starts around 08:15 HKT Monday-Friday:

```yaml
on:
  schedule:
    - cron: "15 0 * * 1-5"
```

Temporary GitHub schedule test:

If testing starts at 12:30 HKT and you want a test run around 12:36 HKT, use:

```yaml
on:
  schedule:
    - cron: "36 4 * * *"
```

This test is not one-time. Comment it again after the test run. Treat GitHub schedule as a convenience check, not the primary production scheduler. The dependable GitHub path is manual `workflow_dispatch`.

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
