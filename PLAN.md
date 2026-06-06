# Plan

## Current Stage

GitHub manual email-send workflow is confirmed. GitHub recognized the scheduler smoke-test workflow as active, but no scheduled run appeared; the short-window scheduler test is inconclusive.

## Whose Turn

Agent turn: remove the temporary scheduler smoke test and record the scheduler finding.

User turn: switch the repository back to private if desired, then decide whether to rely on GitHub's weekday schedule or keep manual send for the assignment demo.

## Locked Setup Choices

- Delivery: Gmail SMTP first.
- LLM: Gemini 2.5 Flash-Lite default.
- DeepSeek: optional provider later.
- GitHub: remote created and `main` pushed.
- GitHub Actions first stage: sample dry-run workflow first, no secrets or email.
- GitHub Actions second stage: manual live dry-run workflow with secrets, still no email.
- GitHub Actions third stage: manual email-send workflow with a `SEND` confirmation input.
- GitHub Actions fourth stage: scheduled email-send workflow after explicit timing confirmation, but short-window GitHub scheduler test was inconclusive.
- First run mode: sample data only.
- Private process notes: keep in ignored `.worklog/`, then delete before final handoff.
- LLM role: draft narrative sections only; code owns facts, tables, chart, validation, and logging.
- Market data role: fetch live dashboard rows where available; fall back to sample rows per asset and log status.
- Calendar data role: fetch live economic-calendar rows where available; use ignored cache and sample fallback if the public feed fails or rate-limits.
- Theme Radar role: fetch curated RSS sources, rank them against the assumed book/themes, and let Gemini synthesize only selected source facts.
- LLM validation role: retry once when Gemini output fails strict JSON or word-limit validation.

## Next Tasks

1. Keep control files current as the project changes.
2. Decide whether to add the permanent weekday schedule despite the inconclusive short-window test.
3. Confirm the automatic weekday send time, currently proposed as 07:15 Hong Kong time to target 07:30 inbox arrival.
4. Consider an external scheduler alternative if precise timing is required.
5. Improve calendar source reliability or add a second source if the free feed remains rate-limited.
6. Improve live data source coverage for Germany 10Y and any assets with intermittent Yahoo failures.
7. Improve Theme Radar source diversity if any RSS feed is slow or unavailable.
8. Polish brief assumptions wording so live mode describes source-level fallback instead of implying every market number must be live.
9. Generate final `memo.pdf` from `memo.md`.

## Blockers

- Free public calendar feed can rate-limit during repeated development tests; local cache and sample fallback are implemented.
- Some free RSS feeds can time out; source-level fallback is implemented.

## Acceptance Criteria For Setup

- Repo has clear control docs and no secrets.
- `.env.example` fully documents required environment variables.
- Local dry-run command generates a complete sample brief.
- Sample brief includes all six assignment modules.
- Git is initialized and the first scaffold commit exists.
