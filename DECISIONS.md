# Decisions

## 2026-06-06 - Delivery Channel

Decision: use Gmail SMTP first.

Reason: the user uses email frequently, and the assignment allows email or Telegram. Gmail SMTP is fast to set up and nearly free for one daily recipient.

Alternatives considered:

- Telegram: simple bot delivery, but less aligned with the user's workflow.
- Resend: cleaner production email API, but requires verifying a custom domain to send beyond the account owner's email.

## 2026-06-06 - LLM Provider

Decision: use Gemini 2.5 Flash-Lite as the default LLM.

Reason: it is cheap, easy to explain in the memo, and has a straightforward API path for a take-home prototype.

Alternatives considered:

- DeepSeek V4 Flash: strong raw price story and should remain an optional provider.
- Provider-neutral first: useful later, but adds setup complexity before the dry run proves the framework.

## 2026-06-06 - GitHub Timing

Decision: initialize local git after the scaffold exists, then create/push the GitHub remote after the first local dry run.

Reason: the project should be locally coherent before external setup and secrets.

## 2026-06-06 - First Run Mode

Decision: start with sample data mode.

Reason: this proves output structure, word limits, chart rendering, logs, and delivery shape before real API integration.

## 2026-06-06 - Learning And Interaction Notes

Decision: keep durable assignment-facing state in tracked control docs, and keep temporary learning/session notes in ignored `.worklog/`.

Reason: the user wants explanations and continuity during the learning process, but wants interaction-derived material removed before the final assignment handoff.

Working rule:

- `PLAN.md` records the public resume point and next tasks.
- `DECISIONS.md` records durable choices and alternatives.
- `.worklog/session_notes.md` records private session breadcrumbs.
- `.worklog/learning_notes.md` records plain-language concepts explained during development.
- `.worklog/` is ignored by git and should be deleted before final submission.

## 2026-06-06 - LLM Scope

Decision: Gemini drafts only the narrative sections from structured facts.

Reason: market numbers, chart output, source links, validation, token accounting, and delivery status should remain deterministic and auditable. This keeps the LLM from inventing data and makes the agent easier to test.

Current LLM-written sections:

- The 3 things that matter today.
- Theme radar summaries and book-impact lines.
- Contrarian corner.

## 2026-06-06 - Live Market Data Scope

Decision: add live market dashboard data with asset-level sample fallback.

Reason: the assignment requires market numbers from real APIs or scraping, but public/free endpoints can fail, rate-limit, or lack specific instruments. The agent should still produce a brief while logging which rows are live and which rows are fallback.

Current sources:

- Yahoo Finance chart endpoint for S&P 500, Euro Stoxx 50, US 10Y, DXY, gold, and WTI oil.
- Frankfurter for USD/JPY.
- CoinGecko for BTC.
- Sample fallback for Germany 10Y and any failed live source.

## 2026-06-06 - Live Calendar Data Scope

Decision: add live economic-calendar rows with feed cache and sample fallback.

Reason: the assignment requires a calendar with consensus estimates, but free public calendar feeds can rate-limit or become unavailable. The agent should still produce a complete brief and log whether rows came from live data, cached data, or sample fallback.

Current source:

- Forex Factory/Fair Economy weekly JSON feed for event title, currency, impact, forecast/consensus, and previous values.
- Ignored local cache under `.cache/calendar/` after successful pulls.
- Sample fallback if the feed fails and no cache is available.

Tradeoff: this is good enough for a local assignment prototype, but a production version should add a second calendar provider or use a paid calendar API.
