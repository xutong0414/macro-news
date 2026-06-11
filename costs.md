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
| Theme sources | Liberty Street / Bank Underground / FRED Blog | $0 initially | Curated RSS feeds, no-key news RSS search, and best-effort article metadata with source-depth labels; live mode leaves Theme Radar blank if no verified candidates exist. |
| Reader feedback | Local CSV | $0 | Optional local preference memory from `FEEDBACK_PATH`; it changes code ranking, not model training. |
| Hosting | Local Mac/server for validation | $0 expected | Production should use an always-on Mac/workstation/VPS if precise scheduled delivery is required. |

## Token Accounting

The runner logs token usage and estimated LLM cost for `--use-llm` runs.

Plain sample mode records zero actual LLM tokens.

The optional `compare-models` command makes one Gemini call per listed model and writes a separate comparison log under `logs/`; use it deliberately because each extra model comparison is an extra paid LLM call. The log records validation errors per model, not only repair counts. Cost estimates are shown only for models present in the local cost table, so unsupported model prices may appear as `n/a` in terminal output.

If `LLM_FAILURE_MODE=data_only` is used, a failed Gemini validation may still consume tokens before the data-only fallback is rendered. The fallback itself does not make a second LLM call.

Latest live model comparison: `model-compare-20260611T113020Z`.

| Model | Status | Repairs | Total tokens | Estimated cost | Elapsed |
| --- | --- | ---: | ---: | ---: | ---: |
| Gemini 2.5 Flash-Lite | warning | 1 | 14,109 | $0.0018783 | 10.00s |
| Gemini 2.5 Pro | warning | 1 | 18,459 | n/a | 170.32s |

Takeaway: this single comparison does not support switching the default model to Pro. Pro was much slower and still needed one validation repair, so the next reliability gains should come from stricter templates, clearer validation logging, and fallback behavior.

## Runtime Accounting

Latest successful live dry run after the narrative stability pass: `20260611T161327Z`, run on Friday at 00:14 HKT.

- Runtime: about one minute in the local validation shell.
- Token use: 25,437 input, 2,889 output, 28,326 total.
- Estimated LLM cost: $0.0036993.
- Prompt version: `gemini_narrative_v43`.
- Source result: 10 market dashboard rows refreshed from live public sources, three rows used cached real-source data, and no sample fallback rows were used. Calendar used the live Fair Economy weekly feed with six rows. Theme Radar selected one Google News RSS item and one Liberty Street Economics item, with one configured Theme Radar source timing out.
- Ranking result: selected EM Debt Conditions, Equity Risk Tone, and US Inflation Event Risk; chart used US 10Y yield; Contrarian Corner challenged the first selected topic.
- Safety note: Gemini narrative validation passed after three attempts with two repairs. The quality gate caught a market-number mismatch and an underweight-S&P direction error before accepting the final brief.

Earlier clean live dry run after the narrative stability pass: `20260611T155900Z`, run on Thursday at 23:59 HKT.

- Runtime: about one minute in the local validation shell.
- Token use: 7,541 input, 978 output, 8,519 total.
- Estimated LLM cost: $0.0011453.
- Prompt version: `gemini_narrative_v43`.
- Source result: all 13 market dashboard rows refreshed from live public sources; no sample fallback rows were used. Calendar used the live Fair Economy weekly feed with six rows. Theme Radar selected one Google News RSS item and one Liberty Street Economics item, with one configured Theme Radar source timing out.
- Ranking result: selected EM Debt Conditions, Equity Risk Tone, and US Inflation Event Risk; chart used US 10Y yield; Contrarian Corner challenged the first selected topic.
- Safety note: Gemini narrative validation passed on the first attempt with zero repairs after the narrative guardrail and validator-precision pass.

Latest successful live send after the Theme Radar metadata and soft-novelty pass: `20260611T150357Z`, run on Thursday at 23:03 HKT.

- Runtime: about 47 seconds in the local validation shell.
- Token use: 20,904 input, 2,886 output, 23,790 total.
- Estimated LLM cost: $0.0032448.
- Prompt version: `gemini_narrative_v40`.
- Source result: all 13 market dashboard rows refreshed from live public sources; no sample fallback rows were used. Calendar used the live Fair Economy weekly feed with six live-source rows. Theme Radar selected one Google News RSS item and one Liberty Street Economics item with `RSS content field + article metadata`; the FRED Blog RSS feed timed out.
- Ranking result: selected Equity Risk Tone, EM Debt Conditions, and US Inflation Event Risk; chart used S&P 500; Contrarian Corner challenged the first selected topic.
- Safety note: an immediately prior normal send was blocked before delivery after Gemini inverted DXY/dollar-pressure logic. The v40 prompt tightened direction checks, and the successful send passed after two validation repairs.

Latest live dry run after the safety fallback and feedback pass: `20260611T120030Z`, run on Thursday at 20:02 HKT.

- Runtime: about 104 seconds in the local validation shell.
- Token use: 13,249 input, 2,212 output, 15,461 total.
- Estimated LLM cost: $0.0022097.
- Prompt version: `gemini_narrative_v39`.
- Source result: live public sources refreshed 9/13 market dashboard rows; cached real-source rows covered four rows; no sample fallback rows were used. Calendar used the live Fair Economy weekly feed with six live-source rows. Theme Radar selected two live Google News RSS items, with the FRED Blog RSS feed timing out.
- Ranking result: selected EM Debt Conditions, Equity Risk Tone, and US Inflation Event Risk; chart used US 10Y yield; Contrarian Corner challenged the first selected topic.

Latest successful live send after the safety fallback and feedback pass: `20260611T120459Z`, run on Thursday at 20:06 HKT.

- Runtime: about 87 seconds in the local validation shell.
- Token use: 13,254 input, 2,066 output, 15,320 total.
- Estimated LLM cost: $0.0021518.
- Prompt version: `gemini_narrative_v39`.
- Source result: live public sources refreshed 11/13 market dashboard rows; cached real-source rows covered two rows; no sample fallback rows were used. Calendar used the live Fair Economy weekly feed with six live-source rows. Theme Radar selected two live Google News RSS items, with the FRED Blog RSS feed timing out.
- Ranking result: selected Equity Risk Tone, EM Debt Conditions, and US Inflation Event Risk; chart used S&P 500; Contrarian Corner challenged the first selected topic.
- Safety note: a prior normal send attempt was blocked by the quality gate after Gemini failed validation; the later fallback-enabled run sent a validated normal brief, not a data-only fallback.

Earlier successful timed live send: `20260611T063208Z`, run on Thursday at 14:32 HKT.

- Runtime: `real 33.64s`, `user 0.58s`, `sys 0.08s`.
- Token use: 5,838 input, 791 output, 6,629 total.
- Estimated LLM cost: $0.0009002.
- Prompt version: `gemini_narrative_v38`.
- Source result: live public sources refreshed 11/13 market dashboard rows; cached real-source rows were used for S&P 500 and DXY; no sample fallback rows were used. Calendar used the live Fair Economy weekly feed with six live-source rows. Theme Radar selected two live RSS items, with the FRED Blog RSS feed timing out.
- Ranking result: selected Equity Risk Tone, ECB Policy Event Risk, and US Inflation Event Risk; chart used S&P 500; Contrarian Corner challenged the first selected topic.

Earlier successful timed live send retained for comparison: `20260607T120308Z`, measured with `/usr/bin/time -p` on Sunday at 20:03 HKT.

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
| 2026-06-11 | `20260611T052916Z` | Portfolio-aware live dry run | about 34s | 11,276 | 1,562 | $0.0017524 | Not sent |
| 2026-06-11 | `20260611T054059Z` | Combined market/calendar/news ranking dry run | about 59s | 5,696 | 778 | $0.0008808 | Not sent |
| 2026-06-11 | `20260611T063208Z` | Portfolio-aware live email validation | 33.64s | 5,838 | 791 | $0.0009002 | Sent |
| 2026-06-11 | `20260611T150357Z` | Metadata-enriched Theme Radar email validation | about 47s | 20,904 | 2,886 | $0.0032448 | Sent |
| 2026-06-11 | `20260611T073855Z` | Portfolio-aware live email validation | about 45s | 12,195 | 1,407 | $0.0017823 | Sent |
| 2026-06-11 | `20260611T074941Z` | Direct-link ranking live dry run | about 50s | 19,335 | 2,124 | $0.0027831 | Not sent |
| 2026-06-11 | `20260611T120030Z` | Safety fallback / feedback live dry run | about 104s | 13,249 | 2,212 | $0.0022097 | Not sent |
| 2026-06-11 | `20260611T120459Z` | Safety fallback / feedback live email validation | about 87s | 13,254 | 2,066 | $0.0021518 | Sent |
| 2026-06-11 | `20260611T155900Z` | Narrative stability live dry run | about 1m | 7,541 | 978 | $0.0011453 | Not sent |
| 2026-06-12 | `20260611T161327Z` | Narrative stability guardrail dry run | about 1m | 25,437 | 2,889 | $0.0036993 | Not sent |

## Daily Cost Takeaway

At the measured token volumes, Gemini 2.5 Flash-Lite cost is well below one US cent per daily brief. Gmail SMTP and the current public data sources add no direct per-run cost. A production deployment may add hosting cost if the agent runs on a VPS, cloud job, or always-on workstation.
