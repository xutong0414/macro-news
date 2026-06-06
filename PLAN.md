# Plan

## Current Stage

Setup scaffold in progress.

## Whose Turn

Agent turn: create the repo scaffold, run a sample dry run, initialize git, and make the first commit if verification passes.

User turn after setup: create local credentials for Gmail SMTP and Gemini, then decide when to create the GitHub remote.

## Locked Setup Choices

- Delivery: Gmail SMTP first.
- LLM: Gemini 2.5 Flash-Lite default.
- DeepSeek: optional provider later.
- GitHub: create/push after the local scaffold and dry run work.
- First run mode: sample data only.

## Next Tasks

1. Keep control files current as the project changes.
2. Add live market data APIs for equities, rates, FX, gold, oil, and BTC.
3. Add economic calendar source with consensus estimates.
4. Add Gemini synthesis layer with tracked token usage.
5. Add Gmail SMTP send path after local `.env` is configured.
6. Add GitHub Actions schedule after local send works.
7. Generate final `memo.pdf` from `memo.md`.

## Blockers

- Gmail app password is not configured yet.
- Gemini API key is not configured yet.
- GitHub remote is not created yet.

## Acceptance Criteria For Setup

- Repo has clear control docs and no secrets.
- `.env.example` fully documents required environment variables.
- Local dry-run command generates a complete sample brief.
- Sample brief includes all six assignment modules.
- Git is initialized and the first scaffold commit exists.

