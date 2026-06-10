# Project Status

This file records the current implementation state and the next public-project milestone.

## Current State

The repo contains a working Daily Macro Brief Agent prototype.

Implemented:

- Local CLI commands for sample dry run, live dry run, and email send.
- Gmail SMTP delivery.
- Gemini 2.5 Flash-Lite narrative synthesis.
- Live market dashboard with source links, freshness labels, and no generated market fallback values.
- Live economic calendar with source links, consensus values when available, and status labels.
- Live Theme Radar from curated RSS sources with source-depth labels.
- Theme Radar recent-link memory and no-key Google News RSS search expansion.
- USD/JPY chart with roughly three months of history and the latest five observations highlighted.
- Portfolio assumptions loaded from `inputs/portfolio/positions.csv`.
- Feedback questionnaire template under `inputs/feedback/`.
- GitHub Actions workflows for sample dry run, live dry run, and manual confirmed send.
- Local/server scheduler documentation for macOS `launchd`, Linux `cron`, and cloud scheduler options.
- Final one-page memo source and PDF.
- Public project working rules in `AGENTS.md`.
- Public change history in `CHANGELOG.md`.

## Latest Verification

Latest recorded live dry run:

- Run id: `20260607T132626Z`
- Mode: live market data, live calendar, live Theme Radar, Gemini narrative
- Delivery: dry run, no email sent
- Runtime: about 42 seconds
- Token use: 8,466 input, 1,739 output, 10,205 total
- Estimated LLM cost: $0.0015422
- Source result: all 10 dashboard rows refreshed from live public sources; calendar used live Fair Economy / Forex Factory rows; Theme Radar selected two live RSS items
- Link audit: 17 external links checked, all returned OK

Latest successful email send:

- Run id: `20260607T120308Z`
- Delivery: sent
- Runtime: 34.33 seconds
- Token use: 4,061 input, 907 output, 4,968 total
- Estimated LLM cost: $0.0007689

Latest local tests:

- `PYTHONPATH=src pytest -q`
- Result: 29 passed

## Scheduling Position

Manual GitHub Actions runs are proven.

Short-window GitHub scheduled-trigger tests did not create scheduled runs, so the project does not rely on GitHub schedules for dependable production timing.

Recommended dependable schedulers:

- macOS `launchd` on an always-on Mac
- Linux `cron` or `systemd` on a workstation or VPS
- Cloud scheduler triggering a deployed job or a manual GitHub workflow

For an email target time such as 08:30 Hong Kong time, schedule the job to start earlier, for example 08:15, unless the intended meaning is explicitly “start work at 08:30.”

## Current Milestone

Milestone: v0.2 Freshness and Source Breadth.

Goal:

- Reduce repeated Theme Radar entries across days.
- Broaden source discovery without adding paid search/data dependencies.
- Keep local headline/search history out of GitHub.

## Maintenance Checklist

Before pushing future changes:

1. Push local commits to GitHub.
2. Confirm no secrets, caches, logs, generated outputs, headline history, collaboration notes, or local assignment PDF are tracked by Git.
3. Run `PYTHONPATH=src pytest -q`.
4. Update `CHANGELOG.md` for public-facing functionality changes.

## Known Caveats

- Free public market, calendar, and RSS sources can timeout, rate-limit, or lag on weekends and holidays.
- Theme Radar currently uses RSS/search-snippet text, not full article text.
- A permanent schedule requires an always-on machine or external scheduler.
- GitHub scheduled workflows are documented but not treated as the dependable scheduler for this prototype.
