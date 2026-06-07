# Costs

This file tracks expected and actual daily run cost.

All dollar amounts in this file are USD unless explicitly stated otherwise.

## Current Cost Estimate

Status: Gemini synthesis, Gmail delivery, live market rows, live calendar rows, and live Theme Radar source collection have been tested. Free sources are used with cached real-source fallback where appropriate. In live mode, unavailable unsupported content is left blank rather than filled with generated sample values.

| Category | Provider | Expected cost | Notes |
| --- | --- | ---: | --- |
| LLM synthesis | Gemini 2.5 Flash-Lite | Near zero for sample mode | Real cost starts when `GEMINI_API_KEY` is used. |
| Optional LLM | DeepSeek V4 Flash | Near zero for expected token volume | Optional comparison provider later. |
| Email delivery | Gmail SMTP | $0 | Uses the sender's Gmail account and app password. |
| Scheduler | Local/server scheduler / GitHub Actions | $0 expected | Local `launchd` scheduling is proven; GitHub manual runs are useful, but GitHub scheduled triggers are not dependable for time-sensitive delivery. |
| Market data | Yahoo / Japan MOF / Frankfurter / CoinGecko | $0 initially | Current live dashboard sources are free/public, with cached real-source fallback and blank rows when no verified data exists. |
| Calendar data | Forex Factory / Fair Economy | $0 initially | Free weekly feed with local cache; can rate-limit during repeated tests, and live mode leaves output blank if no verified rows exist. |
| Theme sources | Liberty Street / Bank Underground / FRED Blog | $0 initially | Curated RSS feeds with source-depth labels; live mode leaves Theme Radar blank if no verified candidates exist. |
| Hosting | Local Mac/server for validation | $0 expected | Production should use an always-on Mac/workstation/VPS if precise scheduled delivery is required. |

## Token Accounting

The runner logs token usage and estimated LLM cost for `--use-llm` runs.

Plain sample mode records zero actual LLM tokens.

## Runtime Accounting

Latest recorded live dry run: `20260607T132626Z`, run on Sunday at 21:26 HKT.

- Approximate runtime: about 42s from run id timestamp to final log timestamp.
- Token use: 8,466 input, 1,739 output, 10,205 total.
- Estimated LLM cost: $0.0015422.
- Source result: all 10 market dashboard rows refreshed from live public sources; no sample fallback rows were used. Calendar used the live Fair Economy weekly feed with six live-source rows. Theme Radar selected two live RSS items, with the FRED Blog RSS feed timing out.
- Link check: 17 unique external URLs in the final rendered brief were checked with public GET requests; all returned OK status.

Latest successful timed live send: `20260607T120308Z`, measured with `/usr/bin/time -p` on Sunday at 20:03 HKT.

- Runtime: `real 34.33s`, `user 0.86s`, `sys 3.10s`.
- Token use: 4,061 input, 907 output, 4,968 total.
- Estimated LLM cost: $0.0007689.
- Source result: all 10 market dashboard rows refreshed from live public sources; no sample fallback rows were used. Calendar used the live Fair Economy weekly feed with six live-source rows. Theme Radar selected two live RSS items, with the FRED Blog RSS feed timing out.
- Link check: 17 unique external URLs in the final rendered brief were checked with public GET requests; all returned OK status.

Operational note: use at least a 10-15 minute scheduler buffer before the desired inbox time. Successful runs can be under one minute, but quality-control testing saw source timeouts and validation retries up to about two minutes before a clean output.

## Representative Measured Runs

These rows are enough to estimate daily operating cost. The development process produced additional test runs, but those are not representative of normal daily use.

| Date | Run id | Mode | Runtime | Input tokens | Output tokens | Estimated LLM cost | Delivery |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 2026-06-06 | `20260606T044327Z` | Sample Gemini dry run | n/a | 1,631 | 561 | $0.0003875 | Not sent |
| 2026-06-06 | `20260606T053032Z` | Full live brief email smoke test | n/a | 1,773 | 677 | $0.0004481 | Sent |
| 2026-06-06 | `20260606T103404Z` | Local `launchd` scheduled-send validation | n/a | 1,770 | 706 | $0.0004594 | Sent |
| 2026-06-07 | `20260607T120308Z` | Live brief email with link validation | 34.33s | 4,061 | 907 | $0.0007689 | Sent |
| 2026-06-07 | `20260607T132626Z` | Live dry run with link audit | about 42s | 8,466 | 1,739 | $0.0015422 | Not sent |

## Daily Cost Takeaway

At the measured token volumes, Gemini 2.5 Flash-Lite cost is well below one US cent per daily brief. Gmail SMTP and the current public data sources add no direct per-run cost. A production deployment may add hosting cost if the agent runs on a VPS, cloud job, or always-on workstation.
