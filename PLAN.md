# Plan

## Current Stage

Chart-section revision is complete. The latest verified dry run (`20260606T145317Z`) keeps the full live prototype structure, renders the chart as `USD/JPY in Five Days`, replaces `Caption:` with bold `Reading:`, and states that the chart supports the first thing that matters today.

## Whose Turn

Agent turn: wait for user review of the updated chart section in `outputs/latest/brief.html`.

User turn: review the updated chart section in `outputs/latest/brief.html` for title, bold `Reading:` wording, and whether the first-thing reference feels natural.

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
- Market data role: fetch live dashboard rows where available; use cached real-source rows for temporary outages; fall back to sample rows only when neither live nor cached data is available.
- Calendar data role: fetch live economic-calendar rows where available; target Asia/Europe/US session coverage; use ignored cache and sample fallback if the public feed fails or rate-limits.
- Theme Radar role: fetch curated RSS sources, rank them against the assumed book/themes, and let Gemini synthesize only selected source facts.
- LLM validation role: retry once when Gemini output fails strict JSON or word-limit validation.
- Brief quality role: render source-status notes, keep live/cache/scaffold fallback explicit, and use Gemini prompt v7 for sharper PM-facing narrative and portfolio-logic validation.
- Dashboard note role: document dashboard scope, extraction time, close/prior basis, additional timing information, Frankfurter FX reference-rate convention, BTC rolling 24-hour convention, and linked data-source basis in the brief itself.
- Three Things link role: render compact item sub-titles, smaller `So what:` support lines, and deterministic Yahoo Finance topic-search links; the LLM does not invent those links.
- Chart role: use USD/JPY because it is the assumed FX position and the most direct visual support for the intervention-risk item; render the note as bold `Reading:` rather than `Caption:`.

## Next Tasks

1. Keep control files current as the project changes.
2. Review whether the chart and earlier revised sections are assignment-ready enough to continue to calendar, Theme Radar, and contrarian-corner polishing.
3. Improve live data source coverage for Germany 10Y if we want to reduce the last scaffold market row.
4. Add a second calendar provider if the free weekly feed remains thin or stale outside weekday windows.
5. Decide whether to install a permanent weekday MacBook `launchd` schedule or keep it as documented proof only.
6. Generate final `memo.pdf` from `memo.md`.

## Blockers

- GitHub scheduled events created zero runs in short-window tests; manual GitHub runs, email sending, and MacBook `launchd` scheduled sending with inbox receipt are confirmed.
- A permanent MacBook schedule requires the Mac to be on and awake enough at the scheduled time.
- Free public calendar feed can rate-limit or be thin outside market mornings; local cache and sample fallback are implemented.
- Some free RSS feeds can time out; source-level fallback is implemented.

## Acceptance Criteria For Setup

- Repo has clear control docs and no secrets.
- `.env.example` fully documents required environment variables.
- Local dry-run command generates a complete sample brief.
- Sample brief includes all six assignment modules.
- Git is initialized and the first scaffold commit exists.
