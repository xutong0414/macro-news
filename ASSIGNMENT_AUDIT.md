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
| Easy deployment and can run daily after simple setup | Mostly done | Local `.env`, `README.md`, `scripts/run_daily_brief.sh`, `docs/scheduling.md`, and `scheduling/*.plist.example` document setup. MacBook `launchd` proof succeeded. GitHub schedule tests were unreliable and are documented. |
| Scheduled daily delivery | Proven outside GitHub schedule | Manual GitHub send works. MacBook `launchd` scheduled send worked and user confirmed inbox receipt. GitHub scheduled triggers produced zero runs in short-window tests. |
| Do not use LLM to generate market data | Done | Code fetches market rows and leaves blanks if no live/cached real row exists. LLM only writes narrative from structured facts. |
| LLM for synthesis and writing only | Done | `llm.py` receives structured facts and output is validated for JSON shape, word limits, market-number consistency, and portfolio logic. |

## Deliverables

| Requirement | Current status | Evidence / notes |
| --- | --- | --- |
| GitHub repo, public or collaborator access | Local repo exists; push/access pending | GitHub remote exists, but the local branch has unpushed commits. Before submission, push and either keep repo public or invite the evaluator as collaborator. |
| Code + README | Done | Source lives under `src/macro_news/`; setup and usage are documented in `README.md`. |
| `costs.md` with daily run cost: tokens + hosting | Done | `costs.md` records token usage, estimated USD cost, runtime, email delivery, and hosting/scheduler notes. |
| 1-page Memo PDF | Not done yet | `memo.md` has the required content scaffold, but it still needs compression into a true 1-page memo and export to PDF. |

## Required Memo Contents

| Memo item | Current status | Notes |
| --- | --- | --- |
| Design tradeoffs | Drafted | `memo.md` covers local-first setup, Gmail vs Telegram, Gemini role, deterministic data vs LLM writing, data sources, validation, and scheduler tradeoffs. |
| Position/theme assumptions | Drafted | `inputs/portfolio/positions.csv` and `memo.md` cover long USD/JPY, overweight gold, EM debt exposure, and house themes. |
| 3 v2 features not completed | Drafted but needs final wording | `memo.md` has possible extensions; final memo should pick exactly 3 and keep them concise. |
| 1-month full-time roadmap | Drafted but needs compression | `memo.md` has a roadmap paragraph. |
| Actual hours spent | Needs user input | `memo.md` keeps this as a submission-time honest answer. |

## Remaining Submission Checklist

1. Push unpushed local commits to GitHub after explicit approval.
2. Decide repository access: public repo or invite evaluator/collaborators.
3. Compress `memo.md` into a true 1-page memo.
4. Fill in actual hours spent.
5. Generate `memo.pdf`.
6. Run one final live send or dry run and record the final run id in `PLAN.md` and `costs.md`.
7. Confirm no secrets, caches, logs, or generated outputs are tracked by Git.

## Current Risk Notes

- Free market/calendar/RSS sources can timeout, rate-limit, or publish with date lag. The brief discloses these statuses.
- Theme Radar uses RSS-level text today, not full-text article reading.
- GitHub scheduled workflows were not dependable in short-window tests; local/server scheduling is the dependable route documented for now.
- Gemini 2.5 Flash-Lite is intentionally chosen for low-cost synthesis because code owns facts, tables, chart, source links, validation, and delivery.
