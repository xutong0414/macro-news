# Costs

This file tracks expected and actual daily run cost.

## Current Estimate

Status: sample Gemini synthesis and Gmail delivery smoke test completed. Live market/calendar APIs are not connected yet.

| Category | Provider | Expected cost | Notes |
| --- | --- | ---: | --- |
| LLM synthesis | Gemini 2.5 Flash-Lite | Near zero for sample mode | Real cost starts when `GEMINI_API_KEY` is used. |
| Optional LLM | DeepSeek V4 Flash | Near zero for expected token volume | Optional comparison provider later. |
| Email delivery | Gmail SMTP | $0 | Uses user's Gmail account and app password. |
| Scheduler | GitHub Actions | $0 expected | Public standard runners are free; private repos have included minutes. |
| Market data | TBD | $0 initially | Prefer free/public APIs where reliable. |
| Calendar data | TBD | $0 initially | Need source with consensus estimates. |
| Hosting | GitHub Actions | $0 expected | No server planned for v1. |

## Token Accounting

The runner logs token usage and estimated LLM cost for `--use-llm` runs.

Plain sample mode records zero actual LLM tokens.

## Actual Runs

| Date | Run id | Mode | Input tokens | Output tokens | Estimated LLM cost | Delivery |
| --- | --- | --- | ---: | ---: | ---: | --- |
| 2026-06-06 | `20260606T044327Z` | Gemini dry run | 1,631 | 561 | $0.0003875 | Not sent |
| 2026-06-06 | `20260606T044351Z` | Gemini + email smoke test | 1,631 | 625 | $0.0004131 | Sent |
