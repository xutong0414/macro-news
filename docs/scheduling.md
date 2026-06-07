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

GitHub Actions manual runs are useful and controlled. GitHub scheduled workflows use UTC and can be delayed, skipped, or affected by runner availability, so this repo does not treat GitHub schedules as a stable or trustworthy delivery mechanism for time-sensitive daily email.

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

Temporary local schedule test:

If the machine timezone is Hong Kong time, testing starts at 12:30, and the goal is to test a scheduled email around 12:36, use:

```cron
36 12 * * * cd /ABSOLUTE/PATH/TO/macro_news && /bin/bash scripts/run_daily_brief.sh >> logs/scheduler.out.log 2>> logs/scheduler.err.log
```

Remove or comment this test line immediately after one successful email. Cron repeats it daily until it is removed.

## macOS launchd

For macOS, use the helper scripts for the common cases below. The file `scheduling/com.macro-news.daily-brief.plist.example` is kept as a manual template.

In `launchd`, `0` and `7` are Sunday, so the template's `Weekday` values `1-5` mean Monday-Friday.

### Quick macOS Schedule Test: Run In 5 Minutes

After manual email sending works, use the helper script to schedule one test run a few minutes from now:

```bash
/bin/bash scripts/install_launchd_test_send.sh 5
```

What this does:

- Creates `~/Library/LaunchAgents/com.macro-news.test-send.plist`.
- Sets the launch time to about 5 minutes from the current Mac time.
- Uses `.venv/bin/python` when available.
- Loads the temporary job with `launchctl`.
- Prints the exact command for unloading the test schedule.

After the email arrives, unload the test job with the printed command:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.macro-news.test-send.plist
```

This test job is not one-time by itself. If it is not unloaded, macOS will run it again at the same time on later days.

### Production macOS Setup: Weekday Morning HKT

For a normal weekday morning schedule, use:

```bash
/bin/bash scripts/install_launchd_weekday_hk.sh 08:15
```

This installs a Monday-Friday schedule targeting 08:15 Hong Kong time. That is the recommended default if the desired inbox time is around 08:30 HKT, because the agent needs time to fetch data, draft, render, and send.

If the requirement is exactly “start at 08:30 HKT,” use:

```bash
/bin/bash scripts/install_launchd_weekday_hk.sh 08:30
```

The helper script:

- Creates `~/Library/LaunchAgents/com.macro-news.weekday-send.plist`.
- Uses `.venv/bin/python` when available.
- Loads the job with `launchctl`.
- Prints commands for checking and unloading the schedule.

Hong Kong time is UTC+8, so 08:15 HKT is 00:15 UTC. The helper converts HKT to the Mac's current local timezone when it writes the `launchd` file. If the scheduled Mac changes timezone or moves across daylight-saving boundaries, rerun the helper.

### Manual Production macOS Setup

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

GitHub schedules use UTC.

Use this option for cloud-run convenience and testing, not as the primary dependable scheduler. For production-style morning delivery, prefer `launchd`, `cron`, `systemd`, a VPS, or a cloud scheduler you control.

Production weekday morning send:

A weekday 08:30 Hong Kong schedule would be:

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

Temporary GitHub schedule test:

If testing starts at 12:30 Hong Kong time and the goal is to test a scheduled run around 12:36 Hong Kong time, convert 12:36 HKT to 04:36 UTC:

```yaml
on:
  schedule:
    - cron: "36 4 * * *"
```

This test schedule is not one-time. It repeats daily until commented or removed. Use GitHub schedules only after accepting that they may be delayed, skipped, or not trigger reliably in short test windows. Manual `workflow_dispatch` remains the proven GitHub path.

The send workflow includes disabled production and test schedule templates in `.github/workflows/daily-brief-manual-send.yml`. The `schedule:` lines are commented out so a clone of the repo does not start sending email automatically. To enable GitHub scheduled sending, uncomment only one block after repository secrets are configured and one manual send has succeeded.

## Cloud Scheduler Option

A cloud scheduler can wake the workflow without keeping a laptop on. Two common patterns:

- Trigger GitHub `workflow_dispatch` using a GitHub token stored in the scheduler.
- Trigger a deployed endpoint that runs the agent or queues the job.

This adds setup complexity, but it is often more reliable than relying on a personal laptop.
