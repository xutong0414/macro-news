# Scheduling

This project separates two questions:

1. Can the brief command run and send email?
2. What scheduler wakes the command at the desired time?

The brief command can run locally, from GitHub Actions, or from another server. For dependable daily sending, use a scheduler that can reliably wake a machine or job at the intended time.

## Recommended Direction

For production-style use, run the project from one of these schedulers:

- macOS always-on machine: `launchd`
- Linux workstation or VPS: `cron` or `systemd`
- Cloud scheduler: a scheduler service that triggers a small server endpoint or a GitHub `workflow_dispatch`

GitHub Actions manual runs are useful and controlled. GitHub scheduled workflows use UTC and can be delayed or skipped, so this repo does not treat GitHub schedules as the dependable delivery mechanism.

## Command To Schedule

The scheduler should call:

```bash
/bin/bash /ABSOLUTE/PATH/TO/macro_news/scripts/run_daily_brief.sh
```

The script changes into the project folder and runs:

```bash
macro-news run --send --use-llm --live-market-data --live-calendar --live-theme-radar
```

Secrets should stay in `.env` on the scheduled machine or in the scheduler platform's secret store. Do not put secrets in scheduler files.

## Start Time Versus Email Time

The scheduled time is the time the agent starts working. The email is sent only after data fetching, Gemini synthesis, rendering, and SMTP delivery finish.

If the desired inbox time is 08:30 Hong Kong time, a practical first setting is 08:15 Hong Kong time. If the requirement is literally “start the program at 08:30,” then schedule 08:30.

Use the run logs under `logs/` to adjust the buffer. Current successful runs are usually under one minute, but live sources and validation retries can occasionally take longer.

## Cron Examples

Cron format:

```text
minute hour day-of-month month day-of-week
```

Common symbols:

- `*` means any value.
- `1-5` in day-of-week means Monday-Friday.
- The hour is based on the machine's local timezone.

Start at 08:30 Monday-Friday on a machine set to Hong Kong time:

```cron
30 8 * * 1-5 cd /ABSOLUTE/PATH/TO/macro_news && /bin/bash scripts/run_daily_brief.sh >> logs/scheduler.out.log 2>> logs/scheduler.err.log
```

Start at 08:15 Monday-Friday on a machine set to Hong Kong time, for an approximately 08:30 inbox target:

```cron
15 8 * * 1-5 cd /ABSOLUTE/PATH/TO/macro_news && /bin/bash scripts/run_daily_brief.sh >> logs/scheduler.out.log 2>> logs/scheduler.err.log
```

Start at 08:30 Hong Kong time from a machine set to UTC:

```cron
30 0 * * 1-5 cd /ABSOLUTE/PATH/TO/macro_news && /bin/bash scripts/run_daily_brief.sh >> logs/scheduler.out.log 2>> logs/scheduler.err.log
```

Start at 07:15 Hong Kong time from a UTC machine:

```cron
15 23 * * 0-4 cd /ABSOLUTE/PATH/TO/macro_news && /bin/bash scripts/run_daily_brief.sh >> logs/scheduler.out.log 2>> logs/scheduler.err.log
```

The last example uses Sunday-Thursday UTC because 23:15 UTC maps to 07:15 Hong Kong time on the following Monday-Friday.

## macOS launchd

Use `scheduling/com.macro-news.daily-brief.plist.example` as the template.

In `launchd`, `0` and `7` are Sunday, so the template's `Weekday` values `1-5` mean Monday-Friday.

Manual setup:

1. Copy the example to `~/Library/LaunchAgents/com.macro-news.daily-brief.plist`.
2. Replace `/ABSOLUTE/PATH/TO/macro_news` with this repo's absolute path.
3. Replace `/ABSOLUTE/PATH/TO/python3` with the output of `command -v python3`.
4. Confirm the scheduled machine has a valid `.env`.
5. Load the job:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.macro-news.daily-brief.plist
```

6. Check the job:

```bash
launchctl print gui/$(id -u)/com.macro-news.daily-brief
```

The Mac must be on and awake enough for `launchd` to run the job. For a laptop, sleep settings matter.

## GitHub Actions Schedule

GitHub schedules use UTC. A weekday 08:30 Hong Kong schedule would be:

```yaml
on:
  schedule:
    - cron: "30 0 * * 1-5"
```

A weekday 08:15 Hong Kong schedule would be:

```yaml
on:
  schedule:
    - cron: "15 0 * * 1-5"
```

Use GitHub schedules only after accepting that they may be delayed or may not trigger reliably in short test windows. Manual `workflow_dispatch` remains the proven GitHub path.

The send workflow includes a disabled schedule template in `.github/workflows/daily-brief-manual-send.yml`. The `schedule:` lines are commented out so a clone of the repo does not start sending email automatically. To enable GitHub scheduled sending, uncomment only that block after repository secrets are configured and one manual send has succeeded.

## Cloud Scheduler Option

A cloud scheduler can wake the workflow without keeping a laptop on. Two common patterns:

- Trigger GitHub `workflow_dispatch` using a GitHub token stored in the scheduler.
- Trigger a deployed endpoint that runs the agent or queues the job.

This adds setup complexity, but it is often more reliable than relying on a personal laptop.
