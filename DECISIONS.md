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

## 2026-06-06 - Live Theme Radar Source Scope

Decision: add curated RSS source collection for Theme Radar before broad web search.

Reason: the assignment rewards real source selection and synthesis, but broad web search is noisy and hard to audit. A small curated list gives the agent real inputs while keeping the selection process explainable.

Current sources:

- Liberty Street Economics.
- Bank Underground.
- FRED Blog when reachable.

Selection rule:

- Parse RSS title/link/description.
- Score source candidates against the assumed book and house themes.
- Select the highest-scoring items, preferring source diversity.
- Fall back to sample Theme Radar items if no relevant live candidates are available.

Tradeoff: curated RSS is less comprehensive than web search, but it is more stable, cheaper, and easier to explain for a take-home prototype.

## 2026-06-06 - LLM Validation Repair

Decision: retry Gemini once when its JSON output fails code validation.

Reason: the agent enforces strict word limits and required JSON shape. Gemini can occasionally miss by a few words, so the safer pattern is deterministic validation followed by one targeted repair instruction.

Tradeoff: a retry can roughly double token use for that run, but the absolute cost remains well below one cent for this prototype.

## 2026-06-06 - GitHub Secret Workflow Staging

Decision: add a manual GitHub live dry-run workflow before any scheduled email-send workflow.

Reason: repository secrets should be tested in GitHub Actions without risking accidental email delivery. The manual live dry run proves Gemini access, live-source fetching, logs, and artifact upload first.

Tradeoff: this adds one extra workflow stage, but it keeps the automation safer and easier to debug.

## 2026-06-06 - Manual Send Safety

Decision: add a manual email-send workflow before any scheduled send workflow, with a required `SEND` confirmation input.

Reason: email delivery should be proven from GitHub Actions, but only when the user explicitly triggers it. The confirmation input reduces accidental sends while preserving a simple one-click test path.

Tradeoff: this adds one small manual step before sending, but it keeps the workflow controlled.

Outcome: confirmed on GitHub Actions; the workflow passed and the user received the email.

## 2026-06-06 - Temporary Schedule Test

Decision: add a temporary scheduled-send workflow before enabling the permanent weekday schedule.

Reason: manual workflow success does not prove that GitHub's scheduler will trigger as expected. A near-term scheduled test proves the automation path without waiting until the next weekday morning.

Initial test time: 2026-06-06 15:30 Hong Kong time, equal to 2026-06-06 07:30 UTC.

Update: the exact-minute test and guarded scheduled-send test did not trigger during the short test window. Replace the scheduled email test with a scheduler-only smoke test that prints timestamps and uses no secrets or email. GitHub recognized the smoke-test workflow as active, but the public Actions API still showed zero runs after multiple five-minute ticks. Remove the temporary smoke test and treat the short-window scheduler test as inconclusive.

Second update: because scheduled delivery is a core requirement, add a temporary scheduled email proof for 2026-06-06 17:40-18:15 Hong Kong time. The workflow tries every five minutes in that window and checks for prior successful proof runs so it sends at most once.

Checkpoint: GitHub recognized the temporary proof workflow as active, but API checks at 2026-06-06 17:48, 17:52, 17:55, 18:02, 18:07, and 18:16 Hong Kong time all showed zero scheduled runs. This suggests the current issue is GitHub's scheduled trigger, not Python, Gemini, or Gmail delivery.

Outcome: remove the temporary proof workflow. Keep manual GitHub send as the proven GitHub automation path, and use local/server scheduling for dependable scheduled delivery.

## 2026-06-06 - Scheduler Fallback Strategy

Decision: add a local/server scheduler path alongside GitHub Actions.

Reason: manual GitHub workflow execution and email delivery are confirmed, but GitHub scheduled triggers did not fire in short-window tests. Scheduled delivery is core to the assignment, so the project needs a scheduler path that can be controlled directly.

Supported paths:

- macOS `launchd` for an always-on Mac.
- Linux `cron` or `systemd` for a workstation or VPS.
- Cloud scheduler triggering a GitHub manual workflow or deployed endpoint.

Default operational recommendation: start the job around 07:15 Hong Kong time for a 07:30 inbox target, then adjust earlier if measured runtime grows.

Tradeoff: local/server scheduling requires the machine or server to be on. GitHub Actions does not require a local machine, but its schedule trigger is less controllable and failed our short-window proof in this repo.
