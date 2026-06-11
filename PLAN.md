# Project Status

This file records the current implementation state and the next public-project milestone.

## Current State

The repo contains a working Daily Macro Brief Agent prototype.

Implemented:

- Local CLI commands for sample dry run, live dry run, and email send.
- Gmail SMTP delivery.
- Gemini 2.5 Flash-Lite narrative synthesis.
- Live market dashboard with source links, freshness labels, and no generated market fallback values.
- Live economic calendar with source links, consensus values when available, and status labels.
- Live Theme Radar from curated RSS sources with source-depth labels.
- Theme Radar recent-link memory, near-duplicate topic filtering, and no-key Google News RSS search expansion.
- Portfolio-aware topic selector for "The 3 Things That Matter Today."
- Direct portfolio-link preference when candidate topic scores are close.
- Dynamic chart selection tied to the first selected portfolio topic, with roughly three months of history and the latest five observations highlighted when source history is available.
- Contrarian Corner constrained to challenge the first selected topic.
- Run-level quality report with source checks, Gemini validation attempts, repaired validation errors, and a send/no-send decision.
- Email delivery is blocked when Gemini narrative validation fails after retries.
- Centralized deterministic narrative rule groups for macro/portfolio validation.
- Expanded contradiction tests for oil/inflation, gold positioning, dollar pressure, volatility, and EM debt logic.
- Manual Gemini model-comparison command for checking validation repairs, token use, estimated cost, and runtime on the same structured inputs.
- Portfolio assumptions loaded from `inputs/portfolio/positions.csv`.
- Feedback questionnaire template under `inputs/feedback/`.
- GitHub Actions workflows for sample dry run, live dry run, and manual confirmed send.
- Local/server scheduler documentation for macOS `launchd`, Linux `cron`, and cloud scheduler options.
- Final one-page memo source and PDF.
- Public project working rules in `AGENTS.md`.
- Public change history in `CHANGELOG.md`.

## Latest Verification

Latest recorded live dry run after direct-link ranking update:

- Run id: `20260611T074941Z`
- Mode: live market data, live calendar, live Theme Radar, Gemini narrative
- Delivery: dry run, no email sent
- Token use: 19,335 input, 2,124 output, 21,459 total
- Estimated LLM cost: $0.0027831
- Prompt version: `gemini_narrative_v38`
- Quality verdict: warning; Gemini repaired two validation issues before acceptance; one Theme Radar feed timed out
- Source result: live public sources refreshed all 13 dashboard rows; calendar used live Fair Economy / Forex Factory rows; Theme Radar selected two live RSS items
- Topic result: selected `Equity Risk Tone`, `US Inflation Event Risk`, and `EM Debt Conditions`; chart used `S&P 500: 3-Month Trend`; Contrarian Corner challenged equity risk tone

Latest local tests:

- `PYTHONPATH=src pytest -q`
- Result: 59 passed

## Scheduling Position

Manual GitHub Actions runs are proven.

Short-window GitHub scheduled-trigger tests did not create scheduled runs, so the project does not rely on GitHub schedules for dependable production timing.

Recommended dependable schedulers:

- macOS `launchd` on an always-on Mac
- Linux `cron` or `systemd` on a workstation or VPS
- Cloud scheduler triggering a deployed job or a manual GitHub workflow

For an email target time such as 08:30 Hong Kong time, schedule the job to start earlier, for example 08:15, unless the intended meaning is explicitly “start work at 08:30.”

## Current Milestone

Milestone: Portfolio-Aware Relevance.

Goal:

- Make portfolio rows, direct portfolio links, market moves, calendar events, and Theme Radar/news inputs influence the daily topic agenda and chart choice.
- Keep Gemini constrained to selected topics rather than letting it decide the whole agenda.
- Keep Contrarian Corner tied to the first selected topic.
- Preserve the public/private boundary for local run history, headline history, and collaboration notes.

## Maintenance Checklist

Before pushing future changes:

1. Push local commits to GitHub.
2. Confirm no secrets, caches, logs, generated outputs, headline history, collaboration notes, or local assignment PDF are tracked by Git.
3. Run `PYTHONPATH=src pytest -q`.
4. Update `CHANGELOG.md` for public-facing functionality changes.

## Safety Backlog

Next safety improvements before adding major new content features:

- Add a data-only fallback option for production sends: if narrative validation fails, either send no email or send a clearly labeled data-only failure notice.
- Improve Theme Radar source depth by fetching article text or abstracts when allowed, while still labeling RSS/search snippets as snippet-level evidence.
- Add a simple reader-feedback import step so recurring comments can adjust source/topic ranking without fine-tuning the model.
- Use the model-comparison command across several live mornings before deciding whether to change the default Gemini model.

## Known Caveats

- Free public market, calendar, and RSS sources can timeout, rate-limit, or lag on weekends and holidays.
- Theme Radar currently uses RSS/search-snippet text, not full article text.
- Validation catches known unsafe narrative patterns, but it is not a complete macro-reasoning engine.
- A permanent schedule requires an always-on machine or external scheduler.
- GitHub scheduled workflows are documented but not treated as the dependable scheduler for this prototype.
