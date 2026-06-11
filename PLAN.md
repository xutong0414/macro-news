# Project Status

This file records the current implementation state and the next public-project milestone.

## Current State

The repo contains a working Daily Macro Brief Agent prototype.

Implemented:

- Local CLI commands for sample dry run, live dry run, and email send.
- Gmail SMTP delivery.
- Gemini 2.5 Flash-Lite narrative synthesis.
- Live market dashboard with source links, freshness labels, and no generated market fallback values.
- Live economic calendar with source links, consensus values when available, and status labels.
- Live Theme Radar from curated RSS/search sources with source-depth labels; feed-provided content fields, best-effort article text excerpts, and limited article metadata are used when available.
- Theme Radar recent-link memory, near-duplicate topic scoring penalties, and no-key Google News RSS search expansion.
- Portfolio-aware topic selector for "The 3 Things That Matter Today."
- Direct portfolio-link preference when candidate topic scores are close.
- Code-generated topic and global dashboard narrative guardrails, so Gemini receives safe read-through guidance and explicit claims to avoid before drafting.
- Local reader-feedback CSV import that nudges topic ranking up or down without fine-tuning the model.
- Dynamic chart selection tied to the first selected portfolio topic, with roughly three months of history and the latest five observations highlighted when source history is available.
- Contrarian Corner constrained to challenge the first selected topic.
- Run-level quality report with source checks, Gemini validation attempts, repaired validation errors, and a send/no-send decision.
- Local failed-validation diagnostics in ignored run logs, so blocked drafts can be inspected without committing local run history.
- Email delivery is blocked when Gemini narrative validation fails after retries.
- Optional data-only fallback mode for failed Gemini validation, controlled by `LLM_FAILURE_MODE=data_only`.
- Centralized deterministic narrative rule groups for macro/portfolio validation.
- Expanded contradiction tests for oil/inflation, gold positioning, dollar pressure, volatility, and EM debt logic.
- Structured Gemini narrative template for "The 3 Things That Matter Today"; code renders required `So what:` labels after Gemini provides `body` and `so_what`.
- Manual Gemini model-comparison command for checking validation repairs, exact validation errors, token use, estimated cost, and runtime on the same structured inputs.
- Portfolio assumptions loaded from `inputs/portfolio/positions.csv`.
- Feedback questionnaire template and local-feedback rules under `inputs/feedback/`.
- GitHub Actions workflows for sample dry run, live dry run, and manual confirmed send.
- Local/server scheduler documentation for macOS `launchd`, Linux `cron`, and cloud scheduler options.
- Final one-page memo source and PDF.
- Public project working rules in `AGENTS.md`.
- Public change history in `CHANGELOG.md`.

## Latest Verification

Latest recorded live dry run after the narrative stability pass:

- Run id: `20260611T161327Z`
- Mode: live market data, live calendar, live Theme Radar, Gemini narrative
- Delivery: dry run only
- Token use: 25,437 input, 2,889 output, 28,326 total
- Estimated LLM cost: $0.0036993
- Prompt version: `gemini_narrative_v43`
- Quality verdict: warning; Gemini narrative passed after three attempts with two repairs; the rejected drafts included a market-number mismatch and an underweight-S&P direction error, both caught before rendering the final brief
- Source result: 10 dashboard rows refreshed from live public sources, three rows used cached real-source data, and no generated market fallback rows were used; calendar used six live Fair Economy / Forex Factory rows; Theme Radar selected one Google News RSS item and one Liberty Street Economics item, with one configured Theme Radar source timing out
- Topic result: selected `EM Debt Conditions`, `Equity Risk Tone`, and `US Inflation Event Risk`; chart used `US 10Y yield: 3-Month Trend`; Contrarian Corner challenged EM debt conditions

Latest Theme Radar source-depth smoke check:

- Run id: `20260611T233800Z`
- Mode: live Theme Radar only, no Gemini, no email
- Result: warning; selected two live Theme Radar items from 27 candidates, with one FRED Blog timeout
- Source-depth result: Google News remained labeled as `search result snippet`; Liberty Street Economics was labeled as `RSS content field + article text excerpt`

Latest local tests:

- `PYTHONPATH=src pytest -q`
- Result: 86 passed

Latest model comparison:

- Run id: `model-compare-20260611T113020Z`
- Input mode: live market data, live calendar, live Theme Radar
- Compared models: `gemini-2.5-flash-lite` and `gemini-2.5-pro`
- Result: both models returned `warning` and needed one validation repair
- Timing: Flash-Lite took 10.00 seconds; Pro took 170.32 seconds
- Token use: Flash-Lite used 14,109 total tokens; Pro used 18,459 total tokens
- Decision implication: this single test does not justify switching the default model to Pro. The repeated warning is more likely a template/validation/fallback issue than simply a weak-model issue.

## Scheduling Position

Manual GitHub Actions runs are proven.

Short-window GitHub scheduled-trigger tests did not create scheduled runs, so the project does not rely on GitHub schedules for dependable production timing.

Recommended dependable schedulers:

- macOS `launchd` on an always-on Mac
- Linux `cron` or `systemd` on a workstation or VPS
- Cloud scheduler triggering a deployed job or a manual GitHub workflow

For an email target time such as 08:30 Hong Kong time, schedule the job to start earlier, for example 08:15, unless the intended meaning is explicitly “start work at 08:30.”

## Current Milestone

Milestone: Theme Source Depth.

Goal:

- Improve Theme Radar evidence quality by using best-effort direct article text excerpts when available.
- Keep source-depth labels honest: RSS/search snippets must stay labeled as snippets unless real article text or metadata was actually used.
- Keep article-page fetching bounded and optional through `THEME_ARTICLE_FETCH_LIMIT`.
- Preserve the public/private boundary for local run history, headline history, and collaboration notes.

## Maintenance Checklist

Before pushing future changes:

1. Push local commits to GitHub.
2. Confirm no secrets, caches, logs, generated outputs, headline history, collaboration notes, or local assignment PDF are tracked by Git.
3. Run `PYTHONPATH=src pytest -q`.
4. Update `CHANGELOG.md` for public-facing functionality changes.

## Safety Backlog

Next safety improvements before adding major new content features:

- Broaden Theme Radar coverage only through auditable source additions or provider APIs; keep RSS/search snippets clearly labeled when no article text or abstract is available.
- Repeat model comparisons only after prompt/fallback changes or when source complexity materially increases.

## Known Caveats

- Free public market, calendar, and RSS sources can timeout, rate-limit, or lag on weekends and holidays.
- Theme Radar uses RSS excerpts/content fields, best-effort article text excerpts or metadata when reachable, and search snippets, not guaranteed full article text.
- Validation catches known unsafe narrative patterns, but it is not a complete macro-reasoning engine.
- A permanent schedule requires an always-on machine or external scheduler.
- GitHub scheduled workflows are documented but not treated as the dependable scheduler for this prototype.
