# Decision Log

This file records durable project decisions and tradeoffs.

## Delivery Channel

Decision: use Gmail SMTP first.

Reason: the assignment allows email or Telegram, and email is a natural daily-brief workflow. Gmail SMTP is simple to configure for a prototype and has no direct per-email cost at this scale.

Tradeoff: Gmail app passwords are less elegant than a production email API, but they keep setup lightweight.

## LLM Provider

Decision: use Gemini 2.5 Flash-Lite as the default LLM provider.

Reason: the LLM task is narrow: summarize structured inputs into concise narrative sections. Code owns facts, tables, charting, links, validation, logging, and delivery. A low-cost model is enough for that constrained role.

Tradeoff: a stronger model may help later if the system reads longer source texts, handles richer portfolio context, or performs deeper article comparison.

## LLM Scope

Decision: restrict the LLM to narrative synthesis.

LLM-written sections:

- The 3 Things That Matter Today
- Theme Radar summaries and book-impact lines
- Contrarian Corner

Code-owned sections:

- Market dashboard values
- Calendar rows and links
- Chart and chart reading
- Source status
- Assumptions
- Feedback table
- Email delivery
- Logs and token accounting

Reason: this reduces hallucination risk. The model receives structured facts and the output is validated before rendering.

## Data Fallback Policy

Decision: sample mode and live mode are separate.

Rules:

- Sample mode can use deterministic scaffold data for framework demos.
- Live market mode must use live rows or cached real-source rows.
- Live calendar mode must use live rows or cached real-source rows.
- Live Theme Radar mode must use verified source candidates.
- If live mode has no verified source data for a row or section, leave values blank rather than generating replacement facts.

Reason: the assignment requires market numbers to come from real APIs or scraping rather than LLM-generated values.

## Market Sources

Decision: use free/public market sources for the prototype.

Current sources:

- Yahoo Finance chart/quote data for broad equities, US rates, dollar, gold, and oil.
- Japan MOF JGB yield CSV for Japan 10Y.
- Frankfurter for EUR/USD and USD/JPY reference-rate rows.
- CoinGecko for BTC.

Reason: these sources are accessible without paid credentials and cover the assignment dashboard categories.

Tradeoff: free sources can timeout, rate-limit, or lag on weekends/holidays. The brief discloses freshness markers and source status.

## Dashboard Scope

Decision: include equities, rates, FX, gold, oil, and BTC.

Current dashboard rows:

- S&P 500
- Euro Stoxx 50
- US 10Y yield
- Japan 10Y yield
- DXY
- EUR/USD
- USD/JPY
- Gold
- WTI oil
- BTC

Reason: this matches the assignment requirement and the assumed macro book. Germany 10Y was removed because a clean free live source was not added in time.

## Calendar Source

Decision: use the Fair Economy / Forex Factory weekly feed for the prototype.

Reason: it provides event names, times, consensus/forecast fields, and prior values in a lightweight format.

Tradeoff: the feed can be thin outside normal market days and can rate-limit repeated tests. The selector targets Asia/Europe/US coverage but does not force a fixed row count.

## Theme Radar Sources

Decision: use curated RSS feeds before broad web search.

Current sources:

- Liberty Street Economics
- Bank Underground
- FRED Blog when reachable

Reason: curated RSS is easier to audit than broad search and reduces the chance of noisy source selection.

Tradeoff: Theme Radar currently uses RSS-level text rather than full article text. Full-text reading is a planned v2 feature.

## Portfolio Input

Decision: store assumed positions in `inputs/portfolio/positions.csv`.

Rule: each row is an effective-date update. If no new row exists for a run date, the latest prior row carries forward until changed or closed.

Reason: this makes the prototype extendable without hard-coding the book in prompts.

## Feedback Input

Decision: include a feedback questionnaire and local CSV template.

Reason: feedback can later improve source ranking and prompt construction. This is local preference memory, not model fine-tuning.

## Chart Choice

Decision: use USD/JPY as the default chart.

Reason: the assumed book is long USD/JPY, so the chart directly supports the intervention-risk and yen-reversal discussion.

Chart rule: line charts should usually show more than one month of history when available; the current chart uses roughly three months and highlights the latest five observations.

## Email And Typography

Decision: render both Markdown and HTML, then send HTML email with the chart attached inline.

Rules:

- `So what`, `For Our Book`, and chart `Reading` use normal body size.
- `Read more`, dashboard notes, and calendar status notes use smaller supporting text.
- Links are code-owned where practical, not invented by the LLM.

## Scheduling

Decision: document local/server schedulers as the dependable scheduled-delivery path.

Supported paths:

- macOS `launchd`
- Linux `cron`
- Linux `systemd`
- Cloud scheduler

Reason: manual GitHub Actions runs worked, but short-window GitHub scheduled-trigger tests did not create scheduled runs. GitHub schedules use UTC and can be delayed, so they are not treated as the primary dependable scheduler.

Operational rule: schedule the job earlier than the desired inbox time. For example, for an 08:30 Hong Kong email target, start around 08:15 unless the intended requirement is “start work at 08:30.”

## GitHub Actions

Decision: keep GitHub workflows staged by risk.

Workflows:

- Sample dry run: no secrets, no email.
- Live dry run: uses secrets, no email.
- Manual send: uses secrets, sends email only when `SEND` is typed.

Reason: this keeps evaluation and debugging controlled.

Rule: the manual-send workflow may carry a commented GitHub `schedule:` template, but scheduled email sending stays disabled by default. A maintainer should uncomment that block only after secrets are configured and a manual send has succeeded.

## Memo And Submission Docs

Decision: keep final submission evidence in tracked Markdown/PDF files.

Files:

- `README.md`: new-user setup and usage guide.
- `ASSIGNMENT_AUDIT.md`: requirement checklist.
- `costs.md`: measured runtime, token, cost, and source notes.
- `memo.md` / `memo.pdf`: one-page assignment memo.
- `PLAN.md`: current project status and submission checklist.

Reason: an evaluator or new implementer should be able to understand the project from the tracked documentation alone.
