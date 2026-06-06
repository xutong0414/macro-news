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

Outcome: a temporary MacBook `launchd` job ran at 2026-06-06 18:34 Hong Kong/Singapore time. `launchctl` reported `runs = 1` and `last exit code = 0`; the agent log reported run id `20260606T103404Z` and delivery status `sent`; the user confirmed inbox receipt. The temporary LaunchAgent was unloaded and removed after the test.

Repo visibility follow-up: the user switched the GitHub repository back to private after the public API inspection window.

Tradeoff: local/server scheduling requires the machine or server to be on. GitHub Actions does not require a local machine, but its schedule trigger is less controllable and failed our short-window proof in this repo.

## 2026-06-06 - Brief Quality Pass

Decision: polish the generated brief before final memo writing instead of continuing scheduler work.

Reason: delivery and MacBook scheduling are proven; the next evaluator-facing risk is brief credibility.

Changes:

- Add a `Source Status` section to distinguish live rows, scaffold fallback, calendar source status, and Theme Radar source status without exposing raw debug errors.
- Remove contradictory live/sample assumptions and make fallback behavior explicit.
- Label calendar rows as `Today`, `Earlier today`, `Tomorrow`, or dated next-session items.
- Use the live USD/JPY series for the chart when the FX source succeeds.
- Upgrade Gemini narrative prompt to v3 with portfolio semantics and duplicate book-impact validation.
- Prefer Theme Radar source diversity by source and matched theme, including a credit-conditions rule.

Outcome: live dry run `20260606T122512Z` passed with all six sections, chart output, source notes in the log, prompt version `gemini_narrative_v3`, and no contradictory live/sample assumption text.

## 2026-06-06 - Round 2 Brief Revision

Decision: revise the brief against the PDF requirements before memo finalization.

Reason: the Round 1 audit found that the framework was sound, but evaluator-facing risks remained in calendar coverage, market fallback presentation, and generic narrative style.

Changes:

- Calendar selector now targets Asia, Europe, and US coverage when the live weekly feed contains usable events.
- Weekend or thin-feed runs may include nearest source-week events, clearly labeled by date or same-day status, instead of collapsing to one US event.
- Market source handling now uses cached real-source rows before scaffold fallback when public endpoints temporarily fail.
- Market logs and Source Status now distinguish live rows, cached real-source rows, and scaffold fallback rows.
- Gemini prompt upgraded to v4 and rejects generic Theme Radar phrases such as `this piece explores` or `this analysis examines`.

Outcome: live dry run `20260606T130031Z` passed with all six sections, Asia/Europe/US calendar rows, 7 live market rows, 1 cached real-source market row, 1 scaffold fallback row, chart output, prompt version `gemini_narrative_v4`, and all assignment word limits satisfied.

## 2026-06-06 - Dashboard Footnotes And EUR/USD

Decision: add EUR/USD to the market dashboard and render explicit dashboard notes below the table.

Reason: the PDF asks for FX coverage, and EUR/USD is the largest major FX pair. The user also correctly flagged that a Hong Kong morning brief needs a clear cutoff/prior convention, especially because BTC trades 24/7 while US/EU cash markets are already closed and some Asian markets may be open.

Changes:

- Add `EUR/USD` as a live Frankfurter FX row alongside DXY and USD/JPY.
- Add dashboard notes for scope, extraction timestamp, close/prior basis, Hong Kong morning caveat, and source basis.
- State that BTC uses query-time price versus rolling 24-hour change, matching common crypto app/API convention.
- Log `dashboard_notes` with each run.
- Upgrade Gemini prompt to v5 and add validation against the specific portfolio-logic error of treating dollar strength itself as a risk to long USD/JPY.

Outcome: revised send `20260606T132925Z` delivered successfully with 10 dashboard rows, EUR/USD included, dashboard notes rendered, prompt version `gemini_narrative_v5`, 9/10 live market rows, and all assignment word limits satisfied.

## 2026-06-06 - Japan 10Y And Linked Source Notes

Decision: add `Japan 10Y yield` back to the market dashboard and render dashboard source names as clickable Markdown/HTML links.

Reason: the assumed book is long USD/JPY, so Japan rates are a direct portfolio risk factor. The user also flagged that "prior fixing" was unclear for FX rows, and that plain-text source names should be linkable for evaluator review.

Changes:

- Add `Japan 10Y yield` using Japan Ministry of Finance's JGB constant-maturity CSV as the live source.
- Keep scaffold fallback for Japan 10Y if the official CSV is unreachable.
- Clarify that Frankfurter FX rows compare the latest published daily reference rate with the immediately previous published daily reference rate.
- Turn dashboard source names into links for Yahoo Finance, Japan MOF, Frankfurter, and CoinGecko.
- Upgrade Gemini prompt to v7, reject narrative that treats higher Japan yields as generic USD/JPY carry support, and relax one overly strict generic-language blocker that stopped a valid send before Gmail delivery.
- Add tests for the Japan 10Y row and linked dashboard notes.

Outcome: sent run `20260606T135317Z` delivered successfully with 11 dashboard rows, Japan 10Y live from Japan MOF, linked dashboard sources rendered in HTML, prompt version `gemini_narrative_v7`, 10/11 market rows live, Germany 10Y scaffold fallback, and calendar cache fallback after a 429 rate limit.

## 2026-06-06 - Dashboard Tone And Read-Through

Decision: rename the dashboard's final column from `So what` to `Why it matters` and make row text describe the day's market implication rather than repeating static instrument definitions.

Reason: the user correctly flagged that the old column mixed generic instrument explanations with daily read-throughs, which could feel repetitive and AI-written. A PM-facing dashboard should keep the table concise, consistent, and tied to today's moves.

Changes:

- Render the market dashboard header as `Why it matters`.
- Generate live market row read-throughs deterministically from each asset's direction and move type.
- Refresh sample dashboard row text to match the same daily-read-through style.
- Rename `Hong Kong morning caveat` to `Additional information about timing`.
- Remove the unnecessary `Source Status shows live, cached, or scaffold fallback rows` sentence from dashboard notes.

Outcome: full live dry run `20260606T141150Z` passed with the updated dashboard header, cleaner timing/source notes, 10/11 live market rows, Germany 10Y scaffold fallback, prompt version `gemini_narrative_v7`, and delivery status `dry_run`.

## 2026-06-06 - Three Things Paragraphs And Read-More Links

Decision: keep Gemini's `So what:` requirement for the three narrative items, but render each item with a compact sub-title, a smaller `So what:` support line, and a deterministic `Read more: Yahoo Finance` link.

Reason: the user wanted the portfolio implication to breathe visually instead of being embedded in the same paragraph, and wanted a simple clickable path for readers who want related news. Links should be code-owned rather than LLM-invented, so they remain predictable and auditable.

Changes:

- Split each Three Things item at `So what:` during rendering.
- Add deterministic high-level item titles such as `USD/JPY Intervention Risk`, `Rates And Dollar Pressure`, and `Risk Tone Turns Defensive`.
- Render the market fact/reasoning, a smaller `So what:` support line, and a smaller `Read more:` support line.
- Add Yahoo Finance topic-search links based on detected item themes such as USD/JPY, US yields, DXY, EM debt, equities, oil, and gold.
- Add tests that the split paragraph and Yahoo Finance link render in Markdown/HTML output.

Outcome: full live dry run `20260606T143027Z` passed with compact sub-titles, clean HTML `So what:` labels, clickable Yahoo Finance links in Markdown/HTML, prompt version `gemini_narrative_v7`, 10/11 live market rows, Germany 10Y scaffold fallback, and delivery status `dry_run`.
