# Scheduling

This project has two separate automation questions:

1. Can the brief run and send email?
2. Who wakes the brief at the right time?

The first question is already proven locally and through the manual GitHub Actions send workflow. The second question is proven on the user's MacBook with `launchd`: a one-shot scheduled job ran at 2026-06-06 18:34 Hong Kong/Singapore time and reported delivery status `sent`.

Short-window GitHub scheduled tests were recognized as active workflows, but did not create scheduled runs during the test windows.

## Recommended Direction

For the assignment demo, keep the proven manual GitHub send workflow and document scheduled delivery clearly.

For dependable daily use, run the project from a scheduler that you control:

- macOS always-on machine: `launchd`
- Linux workstation or VPS: `cron` or `systemd`
- Cloud scheduler: a scheduler service that triggers a small server endpoint or a GitHub `workflow_dispatch`

GitHub Actions can still be useful, but scheduled workflows are not a precise alarm clock. They use UTC, can be delayed, and in our short-window proof attempts did not fire.

The confirmed local scheduled path is macOS `launchd`.

## Timing Rule

If the target inbox time is 07:30 Hong Kong time, schedule the agent around 07:15 Hong Kong time. That gives the agent time to fetch data, call Gemini, render outputs, and send email.

If the job grows more complex later, move the start time earlier, for example 07:00. The command logs each run under `logs/`, so we can adjust from measured runtime rather than guessing.

## Command To Schedule

The scheduler should call:

```bash
/bin/bash /ABSOLUTE/PATH/TO/macro_news/scripts/run_daily_brief.sh
```

The script changes into the project folder, loads `.env` through the Python app, and runs:

```bash
macro-news run --send --use-llm --live-market-data --live-calendar --live-theme-radar
```

Secrets stay in `.env` on the scheduled machine or in the scheduler platform's secret store. Do not put secrets in scheduler files.

## macOS launchd

Use `scheduling/com.macro-news.daily-brief.plist.example` as the template.

In `launchd`, `0` and `7` are Sunday, so the template's `Weekday` values `1-5` mean Monday-Friday.

Manual setup:

1. Copy the example to `~/Library/LaunchAgents/com.macro-news.daily-brief.plist`.
2. Replace `/ABSOLUTE/PATH/TO/macro_news` with this repo's absolute path.
3. Replace `/ABSOLUTE/PATH/TO/python3` with the output of `command -v python3`.
4. Confirm the scheduled Mac has a valid `.env`.
5. Load the job:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.macro-news.daily-brief.plist
```

6. Check the job:

```bash
launchctl print gui/$(id -u)/com.macro-news.daily-brief
```

The Mac must be on and awake enough for `launchd` to run the job. For a laptop, sleep settings matter.

## Linux cron

If the server or workstation timezone is set to Hong Kong time, add this to `crontab -e`:

```cron
15 7 * * 1-5 cd /ABSOLUTE/PATH/TO/macro_news && /bin/bash scripts/run_daily_brief.sh >> logs/scheduler.out.log 2>> logs/scheduler.err.log
```

If the server is in UTC and the target is 07:15 Hong Kong time on Monday-Friday, use 23:15 UTC on Sunday-Thursday:

```cron
15 23 * * 0-4 cd /ABSOLUTE/PATH/TO/macro_news && /bin/bash scripts/run_daily_brief.sh >> logs/scheduler.out.log 2>> logs/scheduler.err.log
```

The Linux machine must be on. A VPS is usually the simplest always-on option.

## GitHub Actions Schedule

GitHub schedules use UTC. A weekday 07:15 Hong Kong schedule would be:

```yaml
on:
  schedule:
    - cron: "15 23 * * 0-4"
```

That means 23:15 UTC Sunday-Thursday, which maps to 07:15 Hong Kong time Monday-Friday.

Use this only after accepting that GitHub's schedule may be delayed or may not trigger reliably in short test windows. Manual `workflow_dispatch` remains the proven GitHub path.

## Cloud Scheduler Option

A cloud scheduler can wake the workflow without keeping a local machine on. Two common patterns:

- Trigger GitHub `workflow_dispatch` using a GitHub token stored in the scheduler.
- Trigger a small deployed endpoint that runs the agent or queues the job.

This adds setup complexity, but it is often more reliable than relying on a personal laptop.
