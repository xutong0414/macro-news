# Costs

This file tracks expected and actual daily run cost.

All dollar amounts in this file are USD unless explicitly stated otherwise.

## Current Estimate

Status: Gemini synthesis, Gmail delivery, live market rows, live calendar rows, and live Theme Radar source collection have been smoke-tested. Free sources are used with cached real-source fallback where appropriate; live mode leaves unavailable unsupported content blank rather than using generated scaffold values.

| Category | Provider | Expected cost | Notes |
| --- | --- | ---: | --- |
| LLM synthesis | Gemini 2.5 Flash-Lite | Near zero for sample mode | Real cost starts when `GEMINI_API_KEY` is used. |
| Optional LLM | DeepSeek V4 Flash | Near zero for expected token volume | Optional comparison provider later. |
| Email delivery | Gmail SMTP | $0 | Uses user's Gmail account and app password. |
| Scheduler | MacBook launchd / GitHub Actions | $0 expected | MacBook `launchd` is proven locally; GitHub manual runs are useful, but GitHub scheduled triggers failed short-window proof. |
| Market data | Yahoo / Japan MOF / Frankfurter / CoinGecko | $0 initially | Current live dashboard sources are free/public, with cached real-source fallback and blank rows when no verified data exists. |
| Calendar data | Forex Factory / Fair Economy | $0 initially | Free weekly feed with local cache; can rate-limit during repeated tests, and live mode leaves output blank if no verified rows exist. |
| Theme sources | Liberty Street / Bank Underground / FRED Blog | $0 initially | Curated RSS feeds with source-depth labels; live mode leaves Theme Radar blank if no verified candidates exist. |
| Hosting | Local MacBook for proof | $0 expected | Production should use an always-on Mac/workstation/VPS if precise scheduled delivery is required. |

## Token Accounting

The runner logs token usage and estimated LLM cost for `--use-llm` runs.

Plain sample mode records zero actual LLM tokens.

## Runtime Accounting

Latest successful timed live send: `20260607T110644Z`, measured with `/usr/bin/time -p` on Sunday at 19:06 HKT.

- Runtime: `real 38.84s`, `user 1.04s`, `sys 2.98s`.
- Token use: 4,049 input, 750 output, 4,799 total.
- Estimated LLM cost: $0.0007049.
- Source result: all 10 market dashboard rows refreshed from live public sources; no scaffold fallback rows were used. Calendar used the live Fair Economy weekly feed with `Live` and `*` footnote ingredients and no cached calendar marker. Theme Radar selected two live RSS items with one feed timeout.

Operational note: use at least a 10-15 minute scheduler buffer before the desired inbox time. Successful runs can be under one minute, but quality-control testing saw source timeouts and validation retries up to about two minutes before a clean output.

## Actual Runs

| Date | Run id | Mode | Input tokens | Output tokens | Estimated LLM cost | Delivery |
| --- | --- | --- | ---: | ---: | ---: | --- |
| 2026-06-06 | `20260606T044327Z` | Gemini dry run | 1,631 | 561 | $0.0003875 | Not sent |
| 2026-06-06 | `20260606T044351Z` | Gemini + email smoke test | 1,631 | 625 | $0.0004131 | Sent |
| 2026-06-06 | `20260606T045635Z` | Live market data + Gemini dry run | 1,667 | 693 | $0.0004439 | Not sent |
| 2026-06-06 | `20260606T045801Z` | Live market data + Gemini + email smoke test | 1,678 | 655 | $0.0004298 | Sent |
| 2026-06-06 | `20260606T050702Z` | Live market + live calendar + Gemini dry run | 1,727 | 659 | $0.0004363 | Not sent |
| 2026-06-06 | `20260606T050824Z` | Live market + calendar fallback + Gemini dry run | 1,681 | 623 | $0.0004173 | Not sent |
| 2026-06-06 | `20260606T052801Z` | Live market + live calendar + live Theme Radar + Gemini dry run | 3,601 | 1,393 | $0.0009173 | Not sent |
| 2026-06-06 | `20260606T053032Z` | Full live prototype + Gemini email smoke test | 1,773 | 677 | $0.0004481 | Sent |
| 2026-06-06 | `20260606T103404Z` | MacBook launchd scheduled send proof | 1,770 | 706 | $0.0004594 | Sent |
| 2026-06-06 | `20260606T122512Z` | Brief quality pass live dry run | 1,818 | 682 | $0.0004546 | Not sent |
| 2026-06-06 | `20260606T130031Z` | Round 2 brief revision live dry run | 2,092 | 703 | $0.0004904 | Not sent |
| 2026-06-06 | `20260606T132711Z` | Dashboard footnote + EUR/USD revision send | 2,400 | 699 | $0.0005196 | Sent |
| 2026-06-06 | `20260606T132925Z` | Corrected dashboard revision send with prompt v5 guardrail | 2,433 | 723 | $0.0005325 | Sent |
| 2026-06-06 | `20260606T134645Z` | Japan 10Y + linked source note dry run | 5,353 | 1,451 | $0.0011157 | Not sent |
| 2026-06-06 | `20260606T134951Z` | Japan 10Y + prompt v6 dry run | 2,674 | 752 | $0.0005682 | Not sent |
| 2026-06-06 | `20260606T135317Z` | Japan 10Y + linked source note send with prompt v7 | 2,670 | 766 | $0.0005734 | Sent |
| 2026-06-06 | `20260606T141150Z` | Dashboard tone revision full live dry run | 2,703 | 705 | $0.0005523 | Not sent |
| 2026-06-06 | `20260606T142216Z` | Three Things paragraph + read-more link dry run | 2,706 | 752 | $0.0005714 | Not sent |
| 2026-06-06 | `20260606T143027Z` | Three Things subtitle layout dry run | 2,706 | 766 | $0.0005770 | Not sent |
| 2026-06-06 | `20260606T144542Z` | USD/JPY chart reading dry run | 2,704 | 700 | $0.0005504 | Not sent |
| 2026-06-06 | `20260606T145317Z` | Bold chart reading wording dry run | 2,707 | 697 | $0.0005495 | Not sent |
| 2026-06-06 | `20260606T153505Z` | Remove Germany 10Y dashboard row dry run | 2,583 | 657 | $0.0005320 | Not sent |
| 2026-06-07 | `20260607T011658Z` | Sunday morning factual-guardrail v24 live dry run, 27.44s real | 6,134 | 1,469 | $0.0012010 | Not sent |
| 2026-06-07 | `20260607T023726Z` | Freshness labels, portfolio input, feedback template, source-depth disclosure v27 live dry run, 34.40s real | 3,517 | 808 | $0.0006749 | Not sent |
| 2026-06-07 | `20260607T030050Z` | Final freshness/status no-generated-data guardrail v32 live dry run, 126.03s real | 11,813 | 2,437 | $0.0021561 | Not sent |
| 2026-06-07 | `20260607T045752Z` | Presentation/link/feedback revision send, 58.02s real | 11,923 | 2,513 | $0.0021975 | Sent |
| 2026-06-07 | `20260607T052959Z` | Timestamp/calendar-footnote/chart-context revision send, 36.10s real | 7,585 | 1,685 | $0.0014325 | Sent |
| 2026-06-07 | `20260607T054242Z` | Email typography, feedback, and data-handling link revision send, 35.74s real | 7,912 | 1,560 | $0.0014152 | Sent |
| 2026-06-07 | `20260607T054634Z` | Final email typography and plain-language footnote revision send, 30.44s real | 3,785 | 866 | $0.0007249 | Sent |
| 2026-06-07 | `20260607T090600Z` | Conditional calendar-footnote revision send, 85.39s real | 4,059 | 895 | $0.0007639 | Sent |
| 2026-06-07 | `20260607T090925Z` | Variable calendar and same-time event de-duplication send, 31.77s real | 4,049 | 918 | $0.0007721 | Sent |
| 2026-06-07 | `20260607T110644Z` | Timestamp wording, calendar note, and chart source revision send, 38.84s real | 4,049 | 750 | $0.0007049 | Sent |
