# Plan

## Current Stage

Freshness/status input pass and presentation/link revision are implemented and verified. The project now renders a top `Updated as of` timestamp, dashboard `As of` fields with compact status markers in the asset label, event-date/status fields for the calendar, variable-length calendar rows, small dashboard/calendar footnotes, clickable calendar/chart/source/contrarian links, source-depth labels for Theme Radar, grouped assumptions with source links, an item-level feedback questionnaire before Source Status, and portfolio assumptions from `inputs/portfolio/positions.csv`.

The latest verified send (`20260607T110644Z`) rendered body-sized `So what`, `For Our Book`, and chart `Reading` lines, small `Read more` and footnote text, one dashboard feedback row, linked data-handling assumptions, all 10 market rows refreshed from live public sources, variable-length calendar rows with same-time event clusters de-duplicated, calendar status footnotes for `Live` and `*` with no cached `†` note, a 3-month USD/JPY chart with the latest five observations highlighted and a small Frankfurter source line, live Theme Radar selections with source-depth labels, prompt version `gemini_narrative_v32`, and no generated scaffold rows in live market/calendar/theme fallback paths.

Measured runtime for that successful send was `38.84s` wall-clock, with 4,049 input tokens, 750 output tokens, 4,799 total tokens, and estimated Gemini cost of $0.0007049.

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
- Three Things link role: render compact item sub-titles, body-sized `So what:` support lines, and deterministic smaller Yahoo Finance topic-search links; the LLM does not invent those links.
- Chart role: use USD/JPY because it is the assumed FX position and the most direct visual support for the intervention-risk item; render the note as bold `Reading:` rather than `Caption:`.
- Dashboard status role: keep the dashboard compact by placing non-live markers (`*` and `†`) on the asset label instead of adding a separate status column.
- Calendar status role: render only verified calendar rows, do not force a fixed row count, de-duplicate same-currency same-time event clusters, explain the regular `Live` and `*` status labels, and add the `†` footnote only when cached calendar rows actually appear.
- Chart history role: line charts should prefer more than one month of history when available, with the latest five observations highlighted; current USD/JPY chart uses roughly three months.
- Email typography role: render `So what`, `For Our Book`, and chart `Reading` at normal body size; keep `Read more`, dashboard notes, and calendar status notes small.
- Feedback role: render an item-level usefulness/comment questionnaire before Source Status, but keep the dashboard to one row rather than one row per dashboard asset.
- Link disclosure role: when data handling or source logic mentions a data feed or web/RSS source, include a reader-facing link whenever possible.

## Next Tasks

1. Keep control files current as the project changes.
2. User review latest `outputs/latest/brief.html` and the delivered email for Outlook typography, footnote size, data-handling links, and questionnaire size.
3. Compress `memo.md` into a true 1-page memo and fill actual hours spent.
4. Generate final `memo.pdf`.
5. Push unpushed local commits to GitHub after explicit approval, then decide public repo vs collaborator invite for submission.
6. Add a second calendar provider if the free weekly feed remains thin or stale outside weekday windows.
7. Decide whether to install a permanent weekday MacBook `launchd` schedule or keep it as documented proof only.

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
