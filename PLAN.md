# Plan

## Current Stage

Sample data brief with Gemini narrative synthesis and Gmail delivery smoke-tested.

## Whose Turn

Agent turn: maintain `PLAN.md`, `DECISIONS.md`, and local `.worklog/` notes as implementation progresses.

User turn: confirm the Gemini-written sample email looks acceptable, then decide when to create the GitHub remote.

## Locked Setup Choices

- Delivery: Gmail SMTP first.
- LLM: Gemini 2.5 Flash-Lite default.
- DeepSeek: optional provider later.
- GitHub: create/push after the local scaffold and dry run work.
- First run mode: sample data only.
- Private process notes: keep in ignored `.worklog/`, then delete before final handoff.
- LLM role: draft narrative sections only; code owns facts, tables, chart, validation, and logging.

## Next Tasks

1. Keep control files current as the project changes.
2. Add live market data APIs for equities, rates, FX, gold, oil, and BTC.
3. Add economic calendar source with consensus estimates.
4. Add non-mainstream source collection for theme radar.
5. Add GitHub remote and push when the user is ready.
6. Add GitHub Actions schedule after live/local send works.
7. Generate final `memo.pdf` from `memo.md`.

## Blockers

- GitHub remote is not created yet.

## Acceptance Criteria For Setup

- Repo has clear control docs and no secrets.
- `.env.example` fully documents required environment variables.
- Local dry-run command generates a complete sample brief.
- Sample brief includes all six assignment modules.
- Git is initialized and the first scaffold commit exists.
