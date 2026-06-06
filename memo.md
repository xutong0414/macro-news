# Daily Macro Brief Agent Memo Draft

## Design Tradeoffs

The prototype starts local-first with sample data before live integrations. This makes the structure testable before API work. Email is the first delivery channel because it matches the user's normal workflow and the assignment allows email or Telegram. Gemini 2.5 Flash-Lite is the default LLM because it is cheap, easy to explain, and sufficient for concise synthesis.

The system separates deterministic data collection from LLM writing. Market numbers must come from APIs or scraping; the LLM is only used for synthesis and style.

The current scaffold keeps tables, chart generation, validation, delivery, and token/cost logging in code. Gemini drafts only the narrative sections from structured facts.

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
2. Add source ranking and freshness checks for non-mainstream research inputs.
3. Add human feedback loop so the PM can rate each brief and improve selection.

## One-Month Roadmap

With one month full-time, the project could become a production-grade macro briefing system with live data integrations, robust source monitoring, calibrated ranking, alerting, and PM feedback.

## Actual Hours Spent

To be filled honestly at submission time.
