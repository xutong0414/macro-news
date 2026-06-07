# Feedback Input Rules

This folder is for the human feedback loop.

For now, feedback is recorded as a managed CSV template. Later versions can load this file before source ranking and prompt construction.

Suggested questionnaire after each brief:

1. Which sections were useful?
   - `5`: very useful, keep this pattern.
   - `3`: acceptable, but not especially valuable.
   - `1`: not useful, avoid this pattern.
2. What action should the agent take next time?
   - `keep`: preserve similar item/source/style.
   - `deprioritize`: lower priority unless strongly supported.
   - `drop`: avoid this topic/source/style.
   - `rewrite`: keep the topic but change wording or framing.
3. What short comment explains the rating?

CSV columns:

- `date`: brief date.
- `section`: Dashboard, Three Things, Calendar, Chart, Theme Radar, Contrarian Corner, or Source Status.
- `item`: item title or asset/event/source name.
- `rating`: 1-5.
- `action`: keep, deprioritize, drop, or rewrite.
- `comment`: short human note.

Planned incorporation rule:

- High-rated repeated patterns increase ranking weight.
- Low-rated patterns reduce ranking weight or trigger prompt warnings.
- `drop` comments become explicit avoid rules after user confirmation.
- Feedback remains local project memory; it is not model fine-tuning.
