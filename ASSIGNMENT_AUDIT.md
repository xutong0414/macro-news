# Assignment Audit

This file maps the original case-study PDF requirements to the current repo state.

Last rechecked: 2026-06-07, using the local PDF in this folder. This recheck did not depend on network access.

## PDF Requirement Summary

The assignment asks for a prototype that automatically sends a Daily Macro Brief at an agreed time each day to a designated email inbox or Telegram.

The PM reader wants a short macro note focused on what changed overnight and what it means for the book. The brief should synthesize and select, not simply regurgitate mainstream news.

The PDF allows reasonable assumptions or sample data for unavailable firm-specific information such as positions, themes, and risk exposures, but market numbers must come from real APIs or scraping rather than LLM-generated values.

## Required Brief Modules

| Requirement | Current status | Evidence / notes |
| --- | --- | --- |
| Overnight market dashboard table across equities, rates, FX, gold, oil, BTC | Done | `README.md` documents sources; `outputs/latest/brief.md` renders the table; market rows come from Yahoo, Japan MOF, Frankfurter, and CoinGecko with no generated live fallback values. |
| 3 things that matter today, each <= 80 words with clear so what | Done | Gemini drafts exactly 3 items; `tests/test_sample_run.py` validates the count, word cap, and `So what:` clause. |
| Today's calendar across Asia/EU/US with consensus | Done, with free-feed caveat | Live Fair Economy / Forex Factory feed is used; rows are variable-length, session-aware, and have consensus/status/link fields. Free source can be thin or rate-limited. |
| One chart worth seeing, with caption <= 30 words | Done | Current chart is USD/JPY, with roughly 3 months of history, latest 5 observations highlighted, code-owned reading line, and a small Frankfurter source link. |
| Theme Radar: 1-3 deep-content summaries tied to assumed positions/themes | Done, with source-depth caveat | Curated RSS feeds are scored against book/themes; source-depth labels disclose whether the item uses RSS excerpt/content rather than full article text. |
| Contrarian Corner, 50-100 words | Done | Gemini drafts and validation enforces the word range. |

## Technical Constraints

| Requirement | Current status | Evidence / notes |
| --- | --- | --- |
| Easy deployment and can run daily after simple setup | Mostly done | Local `.env`, `README.md`, `scripts/run_daily_brief.sh`, `docs/scheduling.md`, and `scheduling/*.plist.example` document setup. Local macOS `launchd` validation succeeded. GitHub schedule tests were unreliable and are documented. |
| Scheduled daily delivery | Proven outside GitHub schedule | Manual GitHub send works. Local macOS `launchd` scheduled send worked and inbox receipt was confirmed. GitHub scheduled triggers produced zero runs in short-window tests. |
| Do not use LLM to generate market data | Done | Code fetches market rows and leaves blanks if no live/cached real row exists. LLM only writes narrative from structured facts. |
| LLM for synthesis and writing only | Done | `llm.py` receives structured facts and output is validated for JSON shape, word limits, market-number consistency, and portfolio logic. |

## Deliverables

| Requirement | Current status | Evidence / notes |
| --- | --- | --- |
| GitHub repo, public or collaborator access | Ready for final access step | GitHub remote exists. Before submission, push the current branch and either keep the repo public or invite the evaluator as a collaborator. |
| Code + README | Done | Source lives under `src/macro_news/`; setup and usage are documented in `README.md`. |
| `costs.md` with daily run cost: tokens + hosting | Done | `costs.md` records token usage, estimated USD cost, runtime, email delivery, and hosting/scheduler notes. |
| 1-page Memo PDF | Done | `memo.md` has been compressed into a one-page memo source, the actual-hours line is filled, and `memo.pdf` has been generated as a one-page PDF. |

## Required Memo Contents

| Memo item | Current status | Notes |
| --- | --- | --- |
| Design tradeoffs | Done | `memo.md` covers local-first setup, Gmail vs Telegram, Gemini role, deterministic data vs LLM writing, data sources, validation, and scheduler tradeoffs. |
| Position/theme assumptions | Done | `inputs/portfolio/positions.csv` and `memo.md` cover long USD/JPY, overweight gold, EM debt exposure, and house themes. |
| 3 v2 features not completed | Done | `memo.md` lists exactly 3 unfinished v2 features. |
| 1-month full-time roadmap | Done | `memo.md` has a concise one-month roadmap paragraph. |
| Actual hours spent | Done | `memo.md` records roughly 3-4 hours for the initial framework plus more than 10 additional hours for checking, revision, and extension planning. |

## Remaining Submission Checklist

1. Push the current local branch to GitHub after final submission approval.
2. Decide repository access: public repo or invite evaluator/collaborators.
3. Review `memo.pdf` if required by the evaluator.
4. Run one final live send or dry run only if another output check is needed; the latest verified sent run is already recorded in `PLAN.md` and `costs.md`.
5. Confirm no secrets, caches, logs, or generated outputs are tracked by Git.

## Current Risk Notes

- Free market/calendar/RSS sources can timeout, rate-limit, or publish with date lag. The brief discloses these statuses.
- Theme Radar uses RSS-level text today, not full-text article reading.
- GitHub scheduled workflows were not dependable in short-window tests; local/server scheduling is the dependable route documented for now.
- Gemini 2.5 Flash-Lite is intentionally chosen for low-cost synthesis because code owns facts, tables, chart, source links, validation, and delivery.
