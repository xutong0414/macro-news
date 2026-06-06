# Plan

## Current Stage

Local agent loop with Gemini synthesis, Gmail delivery, live market rows, live economic-calendar rows, and live Theme Radar source collection with fallback.

## Whose Turn

Agent turn: Theme Radar source layer is implemented, smoke-tested, emailed, and committed.

User turn: confirm the full live-generated email looks acceptable, then decide when to create the GitHub remote.

## Locked Setup Choices

- Delivery: Gmail SMTP first.
- LLM: Gemini 2.5 Flash-Lite default.
- DeepSeek: optional provider later.
- GitHub: create/push after the local scaffold and dry run work.
- First run mode: sample data only.
- Private process notes: keep in ignored `.worklog/`, then delete before final handoff.
- LLM role: draft narrative sections only; code owns facts, tables, chart, validation, and logging.
- Market data role: fetch live dashboard rows where available; fall back to sample rows per asset and log status.
- Calendar data role: fetch live economic-calendar rows where available; use ignored cache and sample fallback if the public feed fails or rate-limits.
- Theme Radar role: fetch curated RSS sources, rank them against the assumed book/themes, and let Gemini synthesize only selected source facts.
- LLM validation role: retry once when Gemini output fails strict JSON or word-limit validation.

## Next Tasks

1. Keep control files current as the project changes.
2. Add GitHub remote and push when the user is ready.
3. Add GitHub Actions schedule after live/local send works.
4. Improve calendar source reliability or add a second source if the free feed remains rate-limited.
5. Improve live data source coverage for Germany 10Y and any assets with intermittent Yahoo failures.
6. Improve Theme Radar source diversity if any RSS feed is slow or unavailable.
7. Generate final `memo.pdf` from `memo.md`.

## Blockers

- GitHub remote is not created yet.
- Free public calendar feed can rate-limit during repeated development tests; local cache and sample fallback are implemented.
- Some free RSS feeds can time out; source-level fallback is implemented.

## Acceptance Criteria For Setup

- Repo has clear control docs and no secrets.
- `.env.example` fully documents required environment variables.
- Local dry-run command generates a complete sample brief.
- Sample brief includes all six assignment modules.
- Git is initialized and the first scaffold commit exists.
