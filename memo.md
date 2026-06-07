# Daily Macro Brief Agent Memo Draft

## Design Tradeoffs

The prototype starts local-first with sample data before live integrations. This makes the structure testable before API work. Email is the first delivery channel because it matches the user's normal workflow and the assignment allows email or Telegram. Gemini 2.5 Flash-Lite is the default LLM because it is cheap, easy to explain, and sufficient for concise synthesis.

The system separates deterministic data collection from LLM writing. Market numbers must come from APIs or scraping; the LLM is only used for synthesis and style.

The current scaffold keeps tables, chart generation, validation, delivery, and token/cost logging in code. Gemini drafts only the narrative sections from structured facts.

Live market dashboard rows are fetched asset by asset, with cached real-source rows used for temporary outages. The dashboard includes Japan 10Y for Japan-rate risk to USD/JPY and EUR/USD and USD/JPY for FX coverage, while Germany 10Y is excluded until a clean live source is added. The brief includes a top `Updated as of` timestamp plus notes on extraction time, close/prior basis, additional timing information for Hong Kong morning use, linked data sources, Frankfurter's daily reference-rate convention, and BTC's rolling 24-hour change convention. The dashboard uses a "Reading" column plus `As of` labels, with stale or cached status shown as compact markers on the asset name. In live mode, if neither live nor cached real data is available for a row, value cells are left blank rather than filled with scaffold numbers.

The 3 Things section is rendered with compact item sub-titles, the market reasoning first, the `So what:` portfolio implication at body size, and a smaller deterministic Yahoo Finance topic-search link for readers who want related news. The LLM does not invent these links; code derives them from the selected item's theme.

The single chart is a contextual USD/JPY line because the assumed book is long USD/JPY and intervention risk is one of the most direct portfolio risks. The chart prefers more than one month of history when the source supports it; the current version uses roughly three months and highlights the latest five observations. The brief labels the chart note with bold `Reading:` text and says the chart supports the first thing that matters today. This keeps the visual tied to the portfolio story rather than making it feel like a generic market chart.

Live calendar rows use a free weekly feed with forecast values treated as consensus estimates. The selector targets Asia, Europe, and US coverage when the feed contains usable events, but it does not force a fixed row count. It also de-duplicates same-currency same-time event clusters so one CPI release window does not become several near-identical calendar rows. Calendar status footnotes explain the regular `Live` and `*` labels, and add `†` only when cached calendar rows appear. Because public feeds can rate-limit during repeated tests, the prototype keeps a local ignored cache after successful pulls. In live mode, if no live or cached real calendar data is available, the calendar is left blank rather than filled with scaffold events.

Theme Radar uses curated RSS feeds rather than broad web search. The agent parses source titles, links, and descriptions; scores candidates against the assumed book and house themes; then sends only selected source facts to Gemini for synthesis. The rendered brief labels whether the summary is based on an `RSS excerpt` or `RSS content field`, so the reader can see that this is not full-article reading yet. In live mode, if no verified RSS candidates are available, the section is left blank rather than filled with scaffold source items.

Portfolio assumptions are read from `inputs/portfolio/positions.csv`. Each row is an effective-date update, and the latest prior row for each asset carries forward until changed or closed. This keeps the PDF assumptions explicit while making later portfolio updates simple.

Human feedback is prepared through `inputs/feedback/daily_feedback.example.csv` and rendered as a compact questionnaire in the email. The dashboard remains one feedback row, while narrative/calendar/theme items get item-level rows. The intended loop is a 1-5 usefulness score and a short comment. This is local preference memory for future ranking/prompt rules, not model fine-tuning.

The LLM output is validated by code for JSON shape, assignment word limits, source reuse, portfolio-logic errors, market-number consistency, and a small set of generic wording failures. If Gemini misses a limit or style guardrail, the runner retries with the exact validation error. The current prompt version adds portfolio semantics so the model treats long USD/JPY, gold overweight, and EM debt exposure consistently, while the validator prevents unsupported market-number transfers, uncalculated spread-direction claims, opening-session claims, and real-rate language when no real-yield data is fetched. Theme Radar source-mechanics text is stripped before rendering so the brief reads like an investment note rather than a debug log.

Scheduling was tested in two ways. GitHub manual workflow execution and email delivery succeeded, but GitHub scheduled triggers did not create runs in short-window tests. A MacBook `launchd` one-shot schedule did run and send successfully, so the documented production scheduler path is local/server scheduling rather than relying on GitHub's own schedule trigger.

The latest Sunday live email proof completed in 38.84 seconds and used 4,799 Gemini tokens, with estimated LLM cost around $0.0007. During validation tuning, provider/source failures and repair attempts sometimes took around 30-120 seconds, so a production schedule should start the job at least 10-15 minutes before the target inbox time.

## Position And Theme Assumptions

Initial assumed book:

- Long USD/JPY.
- Overweight gold.
- Exposure to an EM debt basket.

Initial house themes:

- Higher-for-longer rates.
- Fiscal pressure and term premium.
- China demand weakness.
- Policy divergence across major central banks.

## Possible Extensions

1. Load feedback history into ranking and prompt construction so the PM can improve selection over time.
2. Add more source diversity and freshness checks for non-mainstream research inputs.
3. Fetch and cite richer article text where source permissions and reliability allow it.
4. Replace fragile free feeds with paid or redundant market/calendar providers if production reliability matters.

## One-Month Roadmap

With one month full-time, the project could become a production-grade macro briefing system with live data integrations, robust source monitoring, calibrated ranking, alerting, and PM feedback.

## Actual Hours Spent

To be filled honestly at submission time.
