# Feedback Input Rules

This folder defines the human feedback format used by the project.

The tracked file `daily_feedback.example.csv` is only a template.

For real use, copy it to a local ignored file:

```bash
cp inputs/feedback/daily_feedback.example.csv inputs/feedback/daily_feedback.local.csv
```

Then set this in `.env`:

```bash
FEEDBACK_PATH=inputs/feedback/daily_feedback.local.csv
```

The agent reads this local CSV before topic ranking. It does not train the model. It only nudges code-ranked candidate scores up or down when the feedback item matches a future topic, source, asset, or evidence line.

Suggested questionnaire after each brief:

1. Which item was useful?
   - `5`: very useful, keep this pattern.
   - `3`: acceptable, but not especially valuable.
   - `1`: not useful, avoid this pattern.
2. What short comment explains the rating?

CSV columns:

- `date`: brief date.
- `section`: Dashboard, Three Things, Calendar, Chart, Theme Radar, Contrarian Corner, or Source Status.
- `item`: item title or asset/event/source name.
- `usefulness`: 1-5 usefulness score.
- `comment`: short human note.

Current incorporation rule:

- High-rated repeated patterns increase ranking weight.
- Low-rated repeated patterns reduce ranking weight.
- Comments that include wording such as "avoid", "too generic", "not useful", or "irrelevant" are treated as negative signals.
- Feedback remains local project memory; it is not model fine-tuning.
