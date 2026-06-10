# Agent Working Rules

This file is the standing guide for future agent sessions in this repo.

## Startup Checklist

At the start of a session:

1. Read `AGENTS.md`, `PLAN.md`, `DECISIONS.md`, and `CHANGELOG.md`.
2. Run `git status --short --branch`.
3. Treat `memo.md`, `memo.pdf`, and `ASSIGNMENT_AUDIT.md` as historical assignment artifacts unless the user explicitly asks to revise them.

## Public vs Local Boundary

Tracked files should explain the project, record durable decisions, or provide safe examples.

Never commit:

- `.env` or any secret-bearing file.
- `.cache/`, especially Theme Radar headline/search history.
- `logs/` run logs except `logs/.gitkeep`.
- `outputs/` generated briefs/charts except `outputs/.gitkeep`.
- `.worklog/` collaboration notes or scratch files.
- Private/local portfolio or feedback CSV files.
- The local assignment PDF unless explicitly approved.

Use `.worklog/` for local collaboration notes. Use `CHANGELOG.md`, `PLAN.md`, and `DECISIONS.md` for public project progress.

## Documentation Roles

- `README.md`: how a new user installs, configures, runs, and schedules the agent.
- `PLAN.md`: current project state and next milestone.
- `DECISIONS.md`: durable design choices and tradeoffs.
- `CHANGELOG.md`: concise public history of functionality changes.
- `costs.md`: measured or expected cost/runtime notes.

## Change Discipline

Prefer small, focused changes. After a functionality change:

1. Add or update tests.
2. Update `CHANGELOG.md`.
3. Update `PLAN.md` or `DECISIONS.md` only when the public project state or durable policy changes.
4. Run tests and safety checks before pushing.

## Content Freshness Rule

Theme Radar should avoid repeating links selected before the current run date. The current run date is defined by `BRIEF_TIMEZONE`. Same-day reruns may repeat entries.
