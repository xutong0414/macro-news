# Plan

## Current Stage

GitHub manual email-send workflow is confirmed. GitHub scheduled triggers failed short-window tests, but a MacBook `launchd` one-shot scheduled send succeeded on 2026-06-06 at 18:34 Hong Kong/Singapore time. Controlled local/server scheduling is now the proven scheduled-delivery path.

## Whose Turn

Agent turn: record the successful MacBook `launchd` scheduler proof and keep the temporary test job removed.

User turn: confirm the 18:34 MacBook-scheduled email arrived, and switch the GitHub repo back to private unless public access is still needed.

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
- MacBook scheduler proof: `launchd` ran the send command once at 2026-06-06 18:34 HKT/SGT and reported delivery status `sent`; the temporary LaunchAgent was unloaded and removed.
- First run mode: sample data only.
- Private process notes: keep in ignored `.worklog/`, then delete before final handoff.
- LLM role: draft narrative sections only; code owns facts, tables, chart, validation, and logging.
- Market data role: fetch live dashboard rows where available; fall back to sample rows per asset and log status.
- Calendar data role: fetch live economic-calendar rows where available; use ignored cache and sample fallback if the public feed fails or rate-limits.
- Theme Radar role: fetch curated RSS sources, rank them against the assumed book/themes, and let Gemini synthesize only selected source facts.
- LLM validation role: retry once when Gemini output fails strict JSON or word-limit validation.

## Next Tasks

1. Keep control files current as the project changes.
2. Confirm the user received the MacBook-scheduled email.
3. Decide whether to install a permanent weekday MacBook `launchd` schedule or keep it as documented proof only.
4. Improve calendar source reliability or add a second source if the free feed remains rate-limited.
5. Improve live data source coverage for Germany 10Y and any assets with intermittent Yahoo failures.
6. Improve Theme Radar source diversity if any RSS feed is slow or unavailable.
7. Polish brief assumptions wording so live mode describes source-level fallback instead of implying every market number must be live.
8. Generate final `memo.pdf` from `memo.md`.

## Blockers

- GitHub scheduled events created zero runs in short-window tests; manual GitHub runs, email sending, and MacBook `launchd` scheduled sending are confirmed.
- A permanent MacBook schedule requires the Mac to be on and awake enough at the scheduled time.
- Free public calendar feed can rate-limit during repeated development tests; local cache and sample fallback are implemented.
- Some free RSS feeds can time out; source-level fallback is implemented.

## Acceptance Criteria For Setup

- Repo has clear control docs and no secrets.
- `.env.example` fully documents required environment variables.
- Local dry-run command generates a complete sample brief.
- Sample brief includes all six assignment modules.
- Git is initialized and the first scaffold commit exists.
