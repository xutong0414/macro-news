# Feedback Input Rules

This folder is for the human feedback loop.

For now, feedback is recorded as a managed CSV template. Later versions can load this file before source ranking and prompt construction.

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

Planned incorporation rule:

- High-rated repeated patterns increase ranking weight.
- Low-rated patterns reduce ranking weight or trigger prompt warnings.
- Comments that ask to avoid or rewrite a pattern become explicit avoid/rewrite rules after reviewer confirmation.
- Feedback remains local project memory; it is not model fine-tuning.
