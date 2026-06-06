# Plan

## Current Stage

Three Things formatting revision is complete. The latest verified dry run (`20260606T142216Z`) keeps the full live prototype structure, moves each `So what:` into its own paragraph, and adds a deterministic Yahoo Finance read-more link for each of the three items.

## Whose Turn

Agent turn: wait for user review of the updated `The 3 Things That Matter Today` section in `outputs/latest/brief.html`.

User turn: review the updated 3 Things section in `outputs/latest/brief.html` for readability, link usefulness, and PM-quality taste.

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
- Three Things link role: render `So what:` as a separate paragraph and add deterministic Yahoo Finance topic-search links; the LLM does not invent those links.

## Next Tasks

1. Keep control files current as the project changes.
2. Review whether the next corrected email is assignment-ready enough to start final memo writing.
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
