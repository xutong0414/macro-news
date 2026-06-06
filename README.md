# Daily Macro Brief Agent

Prototype for the case study assignment: a scheduled agent that sends a concise Daily Macro Brief to an email inbox before the market day starts.

The target reader is a macro PM who wants: what changed overnight, why it matters, and what it means for an assumed book. The project starts local-first with sample data, then adds live market/calendar/content APIs and scheduled delivery.

## Current Status

Stage: setup scaffold.

Locked defaults:

- Delivery: Gmail SMTP first.
- LLM: Gemini 2.5 Flash-Lite first.
- DeepSeek: optional provider later.
- GitHub: after the local scaffold and dry run work.

The assignment PDF is kept local and is intentionally not committed to git.

## Quickstart

Run the first sample dry run without secrets:

```bash
PYTHONPATH=src python -m macro_news run --dry-run
```

Expected local outputs:

- `outputs/latest/brief.md`
- `outputs/latest/brief.html`
- `outputs/latest/chart.png`
- `outputs/archive/YYYY-MM-DD/`
- `logs/run-*.jsonl`

Install for command-line use after dependencies are ready:

```bash
python -m pip install -e .
macro-news run --dry-run
```

## Email Setup Placeholder

Create a local `.env` file from `.env.example`.

Required for sending:

- `SMTP_HOST=smtp.gmail.com`
- `SMTP_PORT=587`
- `SMTP_USER`
- `SMTP_PASSWORD` from a Gmail app password
- `BRIEF_FROM_EMAIL`
- `BRIEF_TO_EMAIL`

Do not commit `.env`.

## Assignment Modules

The final brief must include:

1. Overnight market dashboard as a table.
2. The 3 things that matter today, each with a clear "so what."
3. Today's calendar across Asia, EU, and US sessions with consensus.
4. One chart worth seeing with a caption under 30 words.
5. Theme radar summaries tied to assumed positions/themes.
6. Contrarian corner.

## Repo Control Files

- `PLAN.md`: live control tower and handoff state.
- `DECISIONS.md`: decision log.
- `costs.md`: expected and measured run costs.
- `memo.md`: working source for the final 1-page memo.

