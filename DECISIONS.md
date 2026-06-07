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
- Sample fallback for failed live sources when no cached real-source row exists.

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

## 2026-06-06 - USD/JPY Chart Reading

Decision: keep the single required chart as a USD/JPY five-day line and rename the rendered note from `Caption:` to `Reading:`.

Reason: the assumed book is long USD/JPY, and the leading narrative item often focuses on USD/JPY intervention or yen-reversal risk. The chart should therefore support that first item directly rather than sit as a generic decorative chart.

Changes:

- Rename the chart title to `USD/JPY in Five Days`.
- Render the image alt text as `USD/JPY in Five Days`.
- Render bold `Reading:` instead of `Caption:`.
- State that the chart supports the first thing that matters today, with a `see above` cue.
- Keep the chart reading code-owned rather than LLM-written.

Outcome: full live dry run `20260606T145317Z` passed with the chart title, bold `Reading:` label in Markdown/HTML, first-thing support sentence, prompt version `gemini_narrative_v7`, 9 live market rows, 1 cached Euro Stoxx 50 row, 1 Germany 10Y scaffold fallback row, and delivery status `dry_run`.

## 2026-06-06 - Remove Germany 10Y From Dashboard

Decision: remove `Germany 10Y yield` from the dashboard until a clean live source is added.

Reason: the row was repeatedly using scaffold fallback, which made the Source Status look weaker and invited unnecessary explanation. For the assignment prototype, a smaller fully sourced dashboard is more credible than keeping a European rates row with placeholder data.

Changes:

- Remove `Germany 10Y yield` from sample market rows.
- Remove `Germany 10Y yield` from the live dashboard target order.
- Change dashboard scope from `rates (US/Germany/Japan 10Y)` to `rates (US/Japan 10Y)`.
- Add tests confirming Germany 10Y is not rendered.

Outcome: full live dry run `20260606T153505Z` passed with 10 dashboard rows, no Germany 10Y row, no scaffold fallback rows, 9/10 live rows, 1 cached real-source S&P 500 row after a Yahoo timeout, prompt version `gemini_narrative_v7`, and delivery status `dry_run`.

## 2026-06-07 - Sunday Morning Factual Guardrail Pass

Decision: change the dashboard's final column from `Why it matters` to `Reading`, tighten factual validation, and treat code-owned market rows as the source of truth for all market-number references.

Reason: the user correctly asked for a careful check that nothing is imagined except the assumed positions from the assignment PDF. A morning-style run exposed small but important model risks: moving a percentage from one asset to another, implying an uncalculated spread direction, using opening-language for prior closes, and leaking source-selection mechanics into Theme Radar.

Changes:

- Render the market dashboard header as `Reading`; keep the calendar header as `Why it matters`.
- Add market-number consistency validation so a generated sentence that mentions an asset move must match that asset's dashboard `Change` value.
- Reject unsupported narrative phrases such as uncalculated spread narrowing/widening, record-high language, market-pricing claims, opening-session claims, and real-rate language when no real-yield data is fetched.
- Remove spread and real-rate wording from deterministic dashboard/sample facts where the code does not calculate those quantities.
- Retry transient Gemini request failures and allow up to four LLM attempts for validation repair.
- Strip embedded Theme Radar `So what:` text and source-selection/debug sentences before rendering.
- Keep Theme Radar source summaries tied to selected live RSS source metadata, while code owns source links and book-impact rendering.

Outcome: timed live dry run `20260607T011658Z` passed with prompt version `gemini_narrative_v24`, all 10 market rows refreshed from live public sources, cached Fair Economy calendar rows after a 429 live refresh, two live Theme Radar selections, no scaffold market fallback rows, runtime `27.44s`, 6,134 input tokens, 1,469 output tokens, 7,605 total tokens, and estimated Gemini cost $0.001201.

Operational note: successful runs can be under one minute, but provider/source failures and validation repair attempts during this pass took roughly 30-80 seconds. A scheduled production send should start at least 10-15 minutes before the target inbox time.

## 2026-06-07 - Freshness Labels, Portfolio Input, And Feedback Rules

Decision: add row-level freshness/status labels, replace generated live-mode fallback values with blanks, move portfolio assumptions into a CSV input, add feedback templates, and disclose Theme Radar source depth.

Reason: the user flagged weekend/holiday ambiguity, portfolio extensibility, feedback-driven relevance, and source-depth transparency as the next hallucination-control layer.

This decision supersedes earlier live-mode sample-fallback decisions for market rows, calendar rows, and Theme Radar source items. Sample mode remains available for framework demos, but live mode should not silently use scaffold/generated content when verified source content is unavailable.

Changes:

- Market dashboard now renders `As of` and `Status` columns.
- Market status rule: `Live` means refreshed from a public source for the run date or query time; `*` means the live source's latest valid date is older than the run date, usually because of weekend, holiday, or publication lag; `†` means cached real-source data was used after a live refresh failed.
- No generated market fallback rule: in live mode, if an asset has neither live nor cached real data, close/prior/change/as-of/status/reading cells are left blank rather than filled with scaffold/sample values.
- Calendar now renders `Event date` and `Status` columns with the same no-color convention.
- No generated calendar fallback rule: in live mode, if neither live nor cached real calendar data exists, the calendar table is left blank rather than filled with scaffold/sample events.
- Portfolio assumptions now come from `inputs/portfolio/positions.csv` by default. Each row is an effective-date update; if no row is entered for a run date, the latest prior row for that asset carries forward.
- Feedback templates now live under `inputs/feedback/`; the intended process is a simple 1-5 rating plus action (`keep`, `deprioritize`, `drop`, `rewrite`) and short comment.
- Theme Radar output now labels source depth, such as `RSS excerpt` or `RSS content field`, so the reader can distinguish feed-level synthesis from full-article reading.
- Theme Radar live mode leaves the section blank rather than using scaffold/sample source items if no verified source candidate is available.
- Gemini prompt/validation advanced to `gemini_narrative_v32` after live-output inspection added guardrails against change-at-price wording, unsupported spread narrowing/widening language, and brittle Theme Radar generic-opener failures.

Tradeoff: the brief may show blank cells or cached/calendar caveats more visibly, but that is preferable to silently generating unsupported values.

Outcome: timed live dry run `20260607T030050Z` passed with prompt version `gemini_narrative_v32`, 5 live market rows plus 5 cached real-source market rows after Yahoo SSL handshake timeouts, no scaffold fallback rows, Sunday/older source dates labeled with `*` or cached rows labeled with `†`, live Fair Economy calendar rows, two live Theme Radar selections with `RSS excerpt` source-depth labels, portfolio assumptions loaded from `inputs/portfolio/positions.csv`, runtime `126.03s`, 11,813 input tokens, 2,437 output tokens, 14,250 total tokens, and estimated Gemini cost $0.0021561.

## 2026-06-07 - Brief Presentation And Feedback Revision

Decision: make the brief more reader-facing by moving dashboard status into the asset label, making calendar events and source-status rows linkable, grouping assumptions, shortening Theme Radar book-impact labels, and rendering a feedback questionnaire.

Reason: the user flagged that the dashboard status column consumed too much space, that calendar/source/contrarian links help prove the brief is sourced, and that flat assumption bullets mix portfolio assumptions with data-handling rules.

Rules:

- Dashboard status is not a separate column. Non-live status markers attach to the asset label: `*` for older source date and `†` for cached real-source row; no marker means refreshed for the run date or query time.
- Calendar keeps its `Status` column because event timing/status is decision-relevant; each event name should link to the calendar source.
- Source Status should include reader-facing links to the source families, not only plain-text source names.
- Assumptions render under categories such as `Portfolio / Book`, `Data Handling`, and `Source Coverage`.
- Theme Radar book-impact lines render as bold `For Our Book:` to reduce template-like wording.
- The email/brief includes a compact feedback questionnaire whose rows can be copied into `inputs/feedback/daily_feedback.example.csv`.

Outcome: sent run `20260607T045752Z` delivered successfully with dashboard status markers inside asset labels, no separate dashboard status column, clickable calendar event names, linked Source Status notes, Contrarian Corner further-reading links, grouped assumptions, bold `For Our Book:` Theme Radar impact lines, and the feedback questionnaire rendered in the email. Runtime was `58.02s`, token use was 11,923 input / 2,513 output / 14,436 total, and estimated Gemini cost was $0.0021975.

## 2026-06-07 - Timestamp, Calendar Footnotes, Feedback Form, And Chart Context

Decision: make the report timestamp, calendar status symbols, feedback form, and USD/JPY chart more self-explanatory.

Reason: the reader should not need to guess when the brief was updated, why a calendar row has `*`, how to give feedback, or whether the chart is only a toy five-day example.

Rules:

- Render a top `Data/query as of` line immediately under the title. Use a single as-of/update timestamp rather than separate start/end times because reader-facing market notes commonly use an as-of convention.
- If calendar statuses appear, render a short footnote below the calendar table explaining `Live`, `*`, and `†`.
- Put the feedback questionnaire before `Source Status` because feedback is reader action, while Source Status and Assumptions are audit/appendix material.
- Feedback rows should be item-level where practical and use `Usefulness 1-5` plus `Comment`; avoid a vague `Action` column.
- For line charts, prefer more than one month of history when the source supports it. Highlight the latest five observations instead of plotting only five points.

Implementation note: the live USD/JPY chart now requests roughly three months of Frankfurter reference-rate history and highlights the latest five observations.

Outcome: sent run `20260607T052959Z` delivered successfully with the top `Data/query as of` timestamp, calendar status footnotes, item-level feedback questionnaire before Source Status, a 3-month USD/JPY chart with the latest five observations highlighted, and no scaffold fallback rows. Runtime was `36.10s`, token use was 7,585 input / 1,685 output / 9,270 total, and estimated Gemini cost was $0.0014325.

## 2026-06-07 - Email Typography And Link Disclosure Revision

Decision: revise the email HTML typography and source-link disclosure after Outlook inspection.

Reason: Outlook made dashboard/calendar notes and body-level explanatory lines look too similar. The reader should see normal body emphasis for actual portfolio implications, smaller text for footnotes and `Read more`, and links whenever data/source logic names an external feed.

Rules:

- Render `So what`, `For Our Book`, and chart `Reading` at normal body size.
- Keep `Read more`, dashboard notes, and calendar status notes small.
- Keep dashboard feedback to one row, while other sections can use item-level rows.
- In Data Handling and source logic, whenever an external data, web, or RSS source is named, include a reader-facing link whenever possible.

Outcome: sent run `20260607T054634Z` delivered successfully with the revised HTML classes, one dashboard feedback row, linked Data Handling assumptions, plain-language calendar status footnotes, all 10 dashboard rows refreshed from live public sources, runtime `30.44s`, token use 3,785 input / 866 output / 4,651 total, and estimated Gemini cost $0.0007249.
