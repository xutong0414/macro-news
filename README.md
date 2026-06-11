# Daily Macro Brief Agent

This repo contains a prototype agent for the case-study assignment. It generates a Daily Macro Brief for a macro PM, renders Markdown/HTML plus a chart, and can send the brief by email through Gmail SMTP.

The brief answers three practical questions:

- What changed overnight?
- Why does it matter for the assumed book?
- What should the reader watch next?

The LLM is deliberately constrained. Code owns market data, calendar data, portfolio-aware topic selection, charting, source links, validation, logging, and email delivery. Gemini drafts only the narrative sections from structured inputs.

When `--use-llm` is enabled, the run validates Gemini's narrative before sending. The log includes a quality report with source checks, validation attempts, repaired validation errors, and a send/no-send decision. By default, failed narrative validation blocks email delivery. Users can opt into a clearly labeled data-only fallback with `LLM_FAILURE_MODE=data_only`.

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
LLM_FAILURE_MODE=block
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
THEME_HISTORY_PATH=.cache/theme_radar/history.json
THEME_RECENT_DAYS=7
THEME_METADATA_FETCH_LIMIT=8
PORTFOLIO_PATH=inputs/portfolio/positions.csv
FEEDBACK_PATH=inputs/feedback/daily_feedback.local.csv
OUTPUT_DIR=outputs
LOG_DIR=logs
```

Notes:

- For Gmail, use an app password, not the normal Google login password.
- Gmail app passwords are usually shown in groups of four characters; remove spaces in `.env`.
- Keep optional providers such as DeepSeek blank unless you add provider support.
- Keep `LLM_FAILURE_MODE=block` for the safest default. Use `data_only` only if you prefer receiving a clearly labeled data checkpoint when Gemini narrative validation fails.
- `FEEDBACK_PATH` should usually point to a local ignored file such as `inputs/feedback/daily_feedback.local.csv`.
- `THEME_METADATA_FETCH_LIMIT` controls how many Theme Radar article pages the agent tries to open for basic page metadata. Use `0` for RSS/search-snippet-only behavior.

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
- Terminal output includes a quality verdict; sample dry runs should normally show `passed`.

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
- The run log records source quality, LLM validation attempts, validation repairs, and the final quality verdict.

### Step 3.3: Send One Email

Run in Terminal after `.env` has both Gemini and Gmail SMTP values:

```bash
PYTHONPATH=src python -m macro_news run --send --live-market-data --live-calendar --live-theme-radar --use-llm
```

Expected outcome:

- One email is sent to `BRIEF_TO_EMAIL`.
- The same local output files and logs are updated.
- If Gemini narrative validation fails and `LLM_FAILURE_MODE=block`, the email is not sent and the run log records a failed quality report.
- If `LLM_FAILURE_MODE=data_only`, the run can send a clearly labeled data-only fallback instead of an interpreted PM note.
- If delivery fails, check the Gmail app password, sender email, recipient email, and `.env` spelling.

### Optional: Compare Gemini Models

Run in Terminal after `.env` has a valid Gemini API key:

```bash
PYTHONPATH=src python -m macro_news compare-models --models gemini-2.5-flash-lite gemini-2.5-pro
```

Expected outcome:

- No email is sent.
- The same structured brief input is sent to each listed Gemini model.
- Terminal output shows validation repairs, token use, estimated cost when the model is in the local cost table, and runtime for each model.
- The comparison log records the exact validation errors for each model so warnings can be diagnosed by failure type.
- A comparison log is written under `logs/model-compare-*.jsonl`.

Add `--live-market-data --live-calendar --live-theme-radar` if you want the comparison to use live inputs instead of sample inputs.

Expected output files:

- `outputs/latest/brief.md`
- `outputs/latest/brief.html`
- `outputs/latest/chart.png`
- `outputs/archive/YYYY-MM-DD/`
- `logs/run-*.jsonl`

Generated outputs and logs are ignored by git.

## 4. Run On A Schedule

Scheduling means macOS, Linux, GitHub, or another service runs the send command for you at a chosen time.

Important idea:

- The schedule time is when the agent starts working.
- The email is sent after data fetching, Gemini synthesis, rendering, and SMTP delivery finish.
- If the target inbox time is 08:30 Hong Kong time, start around 08:15.
- Closing VS Code and Terminal does not matter after the schedule is installed.
- For a local Mac schedule, the Mac must be powered on and awake enough to run.

The recommended macOS path has two commands.

### Test In 5 Minutes

```bash
/bin/bash scripts/install_launchd_test_send.sh 5
```

Expected outcome:

- One email should arrive around 5 minutes later.
- After the email arrives, run the `launchctl bootout ...` command printed by the script.

This test schedule repeats daily if you do not unload it.

### Install Weekday Morning HKT Schedule

For a target inbox time around 08:30 HKT, start the agent at 08:15 HKT:

```bash
/bin/bash scripts/install_launchd_weekday_hk.sh 08:15
```

If the assignment expects the agent to start exactly at 08:30 HKT, use:

```bash
/bin/bash scripts/install_launchd_weekday_hk.sh 08:30
```

The script prints how to check or unload the schedule.

### Changing The Time

Change the final time argument:

- `08:15` means Monday-Friday at 08:15 Hong Kong time.
- `08:30` means Monday-Friday at 08:30 Hong Kong time.
- Hong Kong time is UTC+8, so 08:15 HKT is 00:15 UTC.

The macOS helper writes a `launchd` file under `~/Library/LaunchAgents/`. If you move the repo, recreate the virtual environment, or change the Mac timezone, rerun the helper command.

For Linux, Windows, GitHub Actions, and more detailed `launchd` notes, see `docs/scheduling.md`. GitHub Actions is useful for manual cloud runs, but it is not a dependable scheduler for time-sensitive morning email.

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
- Theme Radar: curated RSS feeds from Liberty Street Economics, Bank Underground, FRED Blog, and no-key Google News RSS search queries when reachable.
- Chart: selected from the portfolio-aware topic selector when live market history is available; common sources include Yahoo Finance chart data and Frankfurter FX reference rates.

Live mode does not use generated/sample market, calendar, or Theme Radar fallback content. If a live source and cached real row are both unavailable, the relevant value cells or section are left blank rather than filled with invented values.

Theme Radar uses feed-provided RSS excerpts or content fields when available, and can make a small best-effort metadata pass over article pages for standard fields such as page title, description, and publication time. This is not full article scraping. Google News RSS search rows remain labeled as search snippets. Theme Radar keeps recent selected links and headline-topic fingerprints under `.cache/theme_radar/`. Links and near-duplicate topics selected before the current run date receive novelty penalties for `THEME_RECENT_DAYS`, but they are not banned; an important current story can still rank highly enough to appear again. Same-day reruns may repeat entries. This local headline history is ignored by git. Google News RSS search results are filtered to trusted publisher names before selection.

## Portfolio And Feedback Inputs

Portfolio assumptions live in:

```text
inputs/portfolio/positions.csv
```

Each row is an effective-date update. If there is no new row for a run date, the latest prior row carries forward.

When `--use-llm` is enabled, the portfolio file also affects "The 3 Things That Matter Today," "One Chart Worth Seeing," and "Contrarian Corner." The agent ranks market moves, calendar events, and Theme Radar/news signals against active positions, gives a modest preference to direct portfolio links when scores are close, chooses the top topics, and then asks Gemini to write to those selected topics in order. The run log records the selected topics and score components. See `inputs/portfolio/README.md`.

Human feedback is tracked with:

```text
inputs/feedback/daily_feedback.example.csv
```

To use it, copy the example to the local ignored path configured by `FEEDBACK_PATH`, then edit the ratings/comments there. The topic selector reads this local CSV before ranking candidates. High-rated matching items nudge similar future topics up; low-rated matching items nudge them down. This is local preference memory, not model fine-tuning. See `inputs/feedback/README.md`.

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
- Theme Radar uses RSS excerpts/content fields, article metadata when reachable, and search snippets; it is not guaranteed full article text.
- Scheduled delivery requires an always-on machine or external scheduler.
- GitHub scheduled events are documented but not treated as the dependable production scheduler for this prototype.
