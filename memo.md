# Daily Macro Brief Agent Memo Draft

## Design Tradeoffs

The prototype starts local-first with sample data before live integrations. This makes the structure testable before API work. Email is the first delivery channel because it matches the user's normal workflow and the assignment allows email or Telegram. Gemini 2.5 Flash-Lite is the default LLM because it is cheap, easy to explain, and sufficient for concise synthesis.

The system separates deterministic data collection from LLM writing. Market numbers must come from APIs or scraping; the LLM is only used for synthesis and style.

The current scaffold keeps tables, chart generation, validation, delivery, and token/cost logging in code. Gemini drafts only the narrative sections from structured facts.

Live market dashboard rows are fetched asset by asset, with cached real-source rows used before scaffold fallback if a free/public source is temporarily unavailable. The dashboard includes Japan 10Y for USD/JPY yield-spread risk and EUR/USD and USD/JPY for FX coverage, plus notes on extraction time, close/prior basis, additional timing information for Hong Kong morning use, linked data sources, Frankfurter's daily reference-rate convention, and BTC's rolling 24-hour change convention. The dashboard uses a "Why it matters" column for daily read-through rather than repeating static instrument definitions. The run log records which assets were live, cached, or scaffold fallback, and the rendered brief includes a concise Source Status section so the evaluator can see fallback behavior without reading debug logs.

The 3 Things section is rendered with the market reasoning first, the `So what:` portfolio implication in a separate paragraph, and a deterministic Yahoo Finance topic-search link for readers who want related news. The LLM does not invent these links; code derives them from the selected item's theme.

Live calendar rows use a free weekly feed with forecast values treated as consensus estimates. The selector targets Asia, Europe, and US coverage when the feed contains usable events. Because public feeds can rate-limit during repeated tests, the prototype keeps a local ignored cache after successful pulls and falls back to sample calendar rows if no live or cached data is available.

Theme Radar uses curated RSS feeds rather than broad web search. The agent parses source titles, links, and descriptions; scores candidates against the assumed book and house themes; then sends only selected source facts to Gemini for synthesis. This keeps the process auditable and reduces hallucination risk.

The LLM output is validated by code for JSON shape, assignment word limits, source reuse, portfolio-logic errors, and a small set of generic wording failures. If Gemini misses a limit or style guardrail, the runner retries once with the exact validation error. The current prompt version adds portfolio semantics so the model treats long USD/JPY, gold overweight, and EM debt exposure consistently.

Scheduling was tested in two ways. GitHub manual workflow execution and email delivery succeeded, but GitHub scheduled triggers did not create runs in short-window tests. A MacBook `launchd` one-shot schedule did run and send successfully, so the documented production scheduler path is local/server scheduling rather than relying on GitHub's own schedule trigger.

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

## V2 Features

1. Add real position/risk exposure import so "so what" can be portfolio-aware.
2. Add more source diversity and freshness checks for non-mainstream research inputs.
3. Add human feedback loop so the PM can rate each brief and improve selection.
4. Replace fragile free feeds with paid or redundant market/calendar providers if production reliability matters.

## One-Month Roadmap

With one month full-time, the project could become a production-grade macro briefing system with live data integrations, robust source monitoring, calibrated ranking, alerting, and PM feedback.

## Actual Hours Spent

To be filled honestly at submission time.
