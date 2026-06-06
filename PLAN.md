# Plan

## Current Stage

Brief quality pass is complete after scheduler proof. The latest live dry run (`20260606T122512Z`) uses Gemini prompt v3, shows source-status notes, labels next-session calendar items clearly, removes contradictory live/sample assumptions, and renders the chart successfully.

## Whose Turn

Agent turn: commit and push the brief quality pass.

User turn: review the latest `outputs/latest/brief.md` or `outputs/latest/brief.html` and decide whether to continue data-source improvements or move to memo/finalization.

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
- Market data role: fetch live dashboard rows where available; fall back to sample rows per asset and log status.
- Calendar data role: fetch live economic-calendar rows where available; use ignored cache and sample fallback if the public feed fails or rate-limits.
- Theme Radar role: fetch curated RSS sources, rank them against the assumed book/themes, and let Gemini synthesize only selected source facts.
- LLM validation role: retry once when Gemini output fails strict JSON or word-limit validation.
- Brief quality role: render source-status notes, keep live/scaffold fallback explicit, and use Gemini prompt v3 for sharper PM-facing narrative.

## Next Tasks

1. Keep control files current as the project changes.
2. Review whether the latest brief is assignment-ready enough to start final memo writing.
3. Improve live data source coverage for Germany 10Y and intermittent Yahoo timeouts.
4. Add a second calendar provider if the free feed remains thin or rate-limited.
5. Improve Theme Radar source diversity if any RSS feed is slow or unavailable.
6. Decide whether to install a permanent weekday MacBook `launchd` schedule or keep it as documented proof only.
7. Generate final `memo.pdf` from `memo.md`.

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
