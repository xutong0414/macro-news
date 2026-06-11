# Portfolio Input Rules

`positions.csv` is the current portfolio-assumption file used by the agent.

Rules:

- Each row is a position update with an `effective_date`.
- On a run date, the agent uses the latest row at or before that date for each `asset`.
- If no new row is entered for an asset, the prior position carries forward.
- Use `position=flat`, `closed`, `none`, or `0` to remove an asset from the active book.
- Keep private real-book files out of git by using a separate local file and setting `PORTFOLIO_PATH`.

Columns:

- `effective_date`: ISO date, for example `2026-06-01`.
- `asset`: position name used in brief logic.
- `position`: plain-language direction, for example `long`, `overweight`, `exposed`, `neutral`, or `flat`.
- `exposure`: optional size bucket, for example `high`, `medium`, or `low`.
- `quantity`: optional numeric amount.
- `unit`: optional unit for `quantity`.
- `notes`: optional source or explanation.

## Position vs Exposure

`position` means direction or stance. It answers: what are we doing or watching?

Examples:

- `long`: the book benefits if the asset rises.
- `short`: the book benefits if the asset falls.
- `overweight`: the book holds more than its neutral or benchmark allocation.
- `underweight`: the book holds less than its neutral or benchmark allocation.
- `exposed`: the book has meaningful sensitivity, but the exact direction may be broad or basket-like.
- `watch`: not necessarily a trade; the asset is a signal the PM wants monitored.
- `flat`, `closed`, `none`, or `0`: no active position; the agent should ignore it.

For this project, `overweight Gold` means gold strength helps the assumed book and gold weakness hurts it. The neutral or benchmark allocation is not modeled exactly; this is a plain-language portfolio tilt.

`exposure` means size or importance. It answers: how much should the agent care?

Examples:

- `high`: a major risk or high-conviction position.
- `medium`: meaningful, but not the dominant risk.
- `low`: a smaller position or supporting signal.

In a real fund, exposure might be measured with `% NAV`, notional, DV01, beta, or risk contribution. This project uses `high`, `medium`, and `low` because the default book is fictional and public-safe.

## Watch Items

A row with `position=watch` can be useful even if it is not a real trade. It gives the agent more macro context and can help the daily brief rotate away from the same few assets.

Example:

```csv
2026-06-11,Brent oil,watch,medium,,,Inflation and geopolitical risk proxy
```

Plain English: Brent oil is not necessarily held directly, but a large oil move matters for inflation, rates, and risk appetite.

## How The Agent Uses This File

The file is not only shown in the assumptions section. When LLM synthesis is enabled, the agent uses active rows to choose the topic agenda before Gemini writes.

The simplified workflow is:

1. Load active positions as of the run date.
2. Match each position to relevant dashboard rows, calendar events, and Theme Radar/news inputs.
3. Score candidates using live move size, event/source importance, freshness/status, `exposure`, and simple diversification rules.
4. Select the top topics for "The 3 Things That Matter Today."
5. Select a chart that supports the first selected topic when a live series is available.
6. Ask Gemini to explain the selected topics and write a Contrarian Corner that challenges the first selected topic.

This means adding a watched asset can help the brief rotate, especially when the agent has a live or cached market row, an important calendar event, or a relevant Theme Radar/news item that can support it. If an asset has no supporting data, it may appear in assumptions but will not strongly drive the main topics.
