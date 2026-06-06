# Costs

This file tracks expected and actual daily run cost.

## Current Estimate

Status: Gemini synthesis, Gmail delivery, live market rows, live calendar rows, and live Theme Radar source collection have been smoke-tested. Free sources are used with fallback.

| Category | Provider | Expected cost | Notes |
| --- | --- | ---: | --- |
| LLM synthesis | Gemini 2.5 Flash-Lite | Near zero for sample mode | Real cost starts when `GEMINI_API_KEY` is used. |
| Optional LLM | DeepSeek V4 Flash | Near zero for expected token volume | Optional comparison provider later. |
| Email delivery | Gmail SMTP | $0 | Uses user's Gmail account and app password. |
| Scheduler | MacBook launchd / GitHub Actions | $0 expected | MacBook `launchd` is proven locally; GitHub manual runs are useful, but GitHub scheduled triggers failed short-window proof. |
| Market data | Yahoo / Japan MOF / Frankfurter / CoinGecko | $0 initially | Current live dashboard sources are free/public, with cached real-source fallback before sample fallback rows. |
| Calendar data | Forex Factory / Fair Economy | $0 initially | Free weekly feed with local cache and sample fallback; can rate-limit during repeated tests. |
| Theme sources | Liberty Street / Bank Underground / FRED Blog | $0 initially | Curated RSS feeds with source-level fallback. |
| Hosting | Local MacBook for proof | $0 expected | Production should use an always-on Mac/workstation/VPS if precise scheduled delivery is required. |

## Token Accounting

The runner logs token usage and estimated LLM cost for `--use-llm` runs.

Plain sample mode records zero actual LLM tokens.

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
