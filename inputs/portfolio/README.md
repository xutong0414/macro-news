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
