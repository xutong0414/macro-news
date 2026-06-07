# Plan

## Current Stage

Freshness/status input pass and presentation/link revision are implemented and verified. The project now renders dashboard `As of` fields with compact status markers in the asset label, event-date/status fields for the calendar, clickable calendar/source/contrarian links, source-depth labels for Theme Radar, grouped assumptions, a feedback questionnaire, and portfolio assumptions from `inputs/portfolio/positions.csv`.

The latest verified send (`20260607T045752Z`) rendered the dashboard with a `Reading` column, compact status markers on asset names, 9 live market rows plus 1 cached real-source row after a Yahoo SSL handshake timed out, event-date/status calendar labels with clickable event links from the live Fair Economy weekly feed, live Theme Radar selections with source-depth labels, grouped assumptions, a rendered feedback questionnaire, prompt version `gemini_narrative_v32`, and no generated scaffold rows in live market/calendar/theme fallback paths.

Measured runtime for that successful send was `58.02s` wall-clock, with 11,923 input tokens, 2,513 output tokens, 14,436 total tokens, and estimated Gemini cost of $0.0021975.

## Whose Turn

Agent turn: no active implementation pending after this checkpoint.

User turn: review the latest email or `outputs/latest/brief.html`, especially the dashboard markers, source links, grouped assumptions, and feedback questionnaire.

## Locked Setup Choices

- Delivery: Gmail SMTP first.
- LLM: Gemini 2.5 Flash-Lite default.
- DeepSeek: optional provider later.
- GitHub: remote created and `main` pushed.
- GitHub Actions first stage: sample dry-run workflow first, no secrets or email.
- GitHub Actions second stage: manual live dry-run workflow with secrets, still no email.
- GitHub Actions third stage: manual email-send workflow with a `SEND` confirmation input.
- GitHub Actions fourth stage: scheduled email-send workflow is not treated as reliable after short-window scheduler tests created zero scheduled runs.
- Temporary scheduled proof: removed after the 2026-06-06 17:40-18:15 HKT window produced zero scheduled runs.
- Scheduler fallback: document and support local/server scheduling with `scripts/run_daily_brief.sh`, macOS `launchd`, Linux `cron`, and cloud-scheduler options.
- MacBook scheduler proof: `launchd` ran the send command once at 2026-06-06 18:34 HKT/SGT, reported delivery status `sent`, and the user confirmed inbox receipt; the temporary LaunchAgent was unloaded and removed.
- GitHub visibility: repo returned to private after the public API inspection window.
- First run mode: sample data only.
- Private process notes: keep in ignored `.worklog/`, then delete before final handoff.
- LLM role: draft narrative sections only; code owns facts, tables, chart, validation, and logging.
- Market data role: fetch live dashboard rows where available; use cached real-source rows for temporary outages; leave live-mode value cells blank rather than using scaffold/sample rows when neither live nor cached data is available.
- Calendar data role: fetch live economic-calendar rows where available; target Asia/Europe/US session coverage; use ignored cache after rate limits; leave live-mode calendar output blank rather than using scaffold rows when no verified calendar data exists.
- Theme Radar role: fetch curated RSS sources, rank them against the assumed book/themes, label source depth (`RSS excerpt` or `RSS content field`), and let Gemini synthesize only selected source facts; in live mode, leave Theme Radar blank rather than using scaffold items when no verified candidates exist.
- Portfolio input role: read `inputs/portfolio/positions.csv`; each row is an effective-date update, and the latest prior row carries forward until changed or closed.
- Feedback input role: keep the human-rating questionnaire in `inputs/feedback/`; feedback is local preference memory for future ranking/prompt rules, not model fine-tuning.
- LLM validation role: retry up to four attempts when Gemini output fails strict JSON, word-limit, market-number, or portfolio-logic validation; retry transient Gemini request failures instead of failing immediately.
- Brief quality role: render source-status notes, keep live/cache/blank fallback explicit, use Gemini prompt v32, validate market-number consistency, reject unsupported market-positioning language in narrative sections, and strip or rewrite Theme Radar source-mechanics/style text before rendering.
- Dashboard note role: document dashboard scope, extraction time, close/prior basis, additional timing information, Frankfurter FX reference-rate convention, BTC rolling 24-hour convention, and linked data-source basis in the brief itself.
- Three Things link role: render compact item sub-titles, smaller `So what:` support lines, and deterministic Yahoo Finance topic-search links; the LLM does not invent those links.
- Chart role: use USD/JPY because it is the assumed FX position and the most direct visual support for the intervention-risk item; render the note as bold `Reading:` rather than `Caption:`.
- Dashboard status role: keep the dashboard compact by placing non-live markers (`*` and `†`) on the asset label instead of adding a separate status column.
- Feedback role: render a compact questionnaire so email replies can be transferred into `inputs/feedback/daily_feedback.example.csv`.

## Next Tasks

1. Keep control files current as the project changes.
2. User review latest `outputs/latest/brief.html` and the delivered email for the new links, grouping, and questionnaire.
3. Add a second calendar provider if the free weekly feed remains thin or stale outside weekday windows.
4. Decide whether to install a permanent weekday MacBook `launchd` schedule or keep it as documented proof only.
5. Generate final `memo.pdf` from `memo.md`.

## Blockers

- GitHub scheduled events created zero runs in short-window tests; manual GitHub runs, email sending, and MacBook `launchd` scheduled sending with inbox receipt are confirmed.
- A permanent MacBook schedule requires the Mac to be on and awake enough at the scheduled time.
- Free public calendar feed can rate-limit or be thin outside market mornings; local cache is implemented, and live mode leaves the calendar blank rather than using scaffold events when no verified rows exist.
- Some free RSS feeds can time out; live mode logs feed-level errors and leaves Theme Radar blank if no verified source candidates remain.

## Acceptance Criteria For Setup

- Repo has clear control docs and no secrets.
- `.env.example` fully documents required environment variables.
- Local dry-run command generates a complete sample brief.
- Sample brief includes all six assignment modules.
- Git is initialized and the first scaffold commit exists.
