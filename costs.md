# Costs

This file tracks expected and actual daily run cost.

## Current Estimate

Status: setup scaffold only. No live API calls or LLM calls yet.

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

The runner will log token usage once an LLM provider is connected.

Sample mode records zero actual LLM tokens.

## Actual Runs

No paid runs yet.

