# Daily Macro Brief Agent Memo Draft

## Design Tradeoffs

The prototype starts local-first with sample data before live integrations. This makes the structure testable before API work. Email is the first delivery channel because it matches the user's normal workflow and the assignment allows email or Telegram. Gemini 2.5 Flash-Lite is the default LLM because it is cheap, easy to explain, and sufficient for concise synthesis.

The system separates deterministic data collection from LLM writing. Market numbers must come from APIs or scraping; the LLM is only used for synthesis and style.

The current scaffold keeps tables, chart generation, validation, delivery, and token/cost logging in code. Gemini drafts only the narrative sections from structured facts.

Live market dashboard rows are fetched asset by asset, with sample fallback if a free/public source is unavailable. The run log records which assets were live and which fell back, making the prototype auditable despite using free data sources.

Live calendar rows use a free weekly feed with forecast values treated as consensus estimates. Because public feeds can rate-limit during repeated tests, the prototype keeps a local ignored cache after successful pulls and falls back to sample calendar rows if no live or cached data is available.

Theme Radar uses curated RSS feeds rather than broad web search. The agent parses source titles, links, and descriptions; scores candidates against the assumed book and house themes; then sends only selected source facts to Gemini for synthesis. This keeps the process auditable and reduces hallucination risk.

The LLM output is validated by code for JSON shape and assignment word limits. If Gemini misses a limit, the runner retries once with the exact validation error.

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

## One-Month Roadmap

With one month full-time, the project could become a production-grade macro briefing system with live data integrations, robust source monitoring, calibrated ranking, alerting, and PM feedback.

## Actual Hours Spent

To be filled honestly at submission time.
