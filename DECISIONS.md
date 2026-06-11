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

Diagnostic rule: stronger Gemini models can be compared with `compare-models`, but the default delivery model remains Gemini 2.5 Flash-Lite unless repeated validation logs show a clear quality benefit from changing it.

First comparison result: a live comparison on 2026-06-11 showed both Gemini 2.5 Flash-Lite and Gemini 2.5 Pro still needed one validation repair. Pro was much slower in that run, so this does not justify changing the default model. The next safety focus is fallback/template design rather than simply using a larger model.

## LLM Scope

Decision: restrict the LLM to narrative synthesis.

LLM-written sections:

- The 3 Things That Matter Today
- Theme Radar summaries and book-impact lines
- Contrarian Corner

Code-owned sections:

- Market dashboard values
- Calendar rows and links
- Topic agenda selection
- Chart and chart reading
- Source status
- Assumptions
- Feedback table
- Email delivery
- Logs and token accounting

Reason: this reduces hallucination risk. The model receives structured facts and the output is validated before rendering.

Validation rule: narrative output is rejected when it inverts core portfolio or macro direction checks, including USD/JPY long semantics, ECB hawkish/dovish euro direction, and hotter/cooler US inflation versus yield direction.

Implementation rule: macro narrative validation uses centralized deterministic rule groups for portfolio semantics, unsupported claims, market-number consistency, market-direction consistency, and common asset-move contradictions.

Implementation rule: Gemini returns each "Three Things" item as structured `body` and `so_what` fields. The application renders the `So what:` label itself, so a missing label is no longer left to model formatting.

Quality-gate rule: each run writes a quality report to the run log. The report records source checks, Gemini validation attempts, validation repairs, repaired validation errors, and whether sending is allowed. If Gemini narrative validation fails after retries, the run writes a failed quality report and blocks email delivery.

Fallback rule: `LLM_FAILURE_MODE=block` remains the safest default. `LLM_FAILURE_MODE=data_only` allows a clearly labeled data-only fallback when Gemini narrative validation fails; the fallback withholds LLM-written interpretation and keeps the failure visible in the quality report.

Diagnostic rule: model-comparison logs record exact validation errors per model, not only repair counts, so model changes can be judged by failure type as well as cost and speed.

## Data Fallback Policy

Decision: sample mode and live mode are separate.

Rules:

- Sample mode can use deterministic sample data for framework demos.
- Live market mode must use live rows or cached real-source rows.
- Live calendar mode must use live rows or cached real-source rows.
- Live Theme Radar mode must use verified source candidates.
- If live mode has no verified source data for a row or section, leave values blank rather than generating replacement facts.

Reason: the assignment requires market numbers to come from real APIs or scraping rather than LLM-generated values.

## Market Sources

Decision: use free/public market sources for the prototype.

Current sources:

- Yahoo Finance chart/quote data for broad equities, US rates, China internet/tech proxy, dollar, gold, oil, and volatility.
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
- China internet / tech basket
- DXY
- EUR/USD
- USD/JPY
- Gold
- Brent oil
- WTI oil
- VIX
- BTC

Reason: this matches the assignment requirement and the assumed macro book. Germany 10Y was removed because a clean free live source was not added in time.

## Calendar Source

Decision: use the Fair Economy / Forex Factory weekly feed for the prototype.

Reason: it provides event names, times, consensus/forecast fields, and prior values in a lightweight format.

Tradeoff: the feed can be thin outside normal market days and can rate-limit repeated tests. The selector targets Asia/Europe/US coverage but does not force a fixed row count.

## Theme Radar Sources

Decision: use curated RSS feeds plus no-key Google News RSS search.

Current sources:

- Liberty Street Economics
- Bank Underground
- FRED Blog when reachable
- Google News RSS search queries tied to the assumed book and macro themes

Reason: curated RSS is easy to audit, but the first public feedback showed that a narrow feed set can repeat the same entries across days. Google News RSS broadens discovery without requiring a paid search API.

Tradeoff: Theme Radar currently uses RSS/search-snippet text plus best-effort article metadata rather than full article text. Search-derived items must be labeled as snippets, not as full article reading. Full-text reading remains a later feature.

Rule: for curated RSS/Atom feeds, the parser uses richer feed-provided content fields when they are meaningfully longer than short descriptions. The agent may open a limited number of article pages for standard metadata fields such as title, description, and publication time. Search-derived items remain labeled as snippets.

Rule: Theme Radar keeps selected-link history locally under `.cache/theme_radar/`. Links selected before the current run date receive a strong score penalty for the configured recent-day window, but this is not an absolute restriction. Same-day reruns may repeat entries. The current run date is defined by `BRIEF_TIMEZONE`.

Rule: Theme Radar also stores simple headline-topic fingerprints locally. Recently selected near-duplicate topics receive a novelty penalty rather than a hard ban, so a genuinely important current story can still be selected.

Rule: Google News RSS search results are filtered by trusted publisher name before scoring. Curated research feeds bypass this filter because they are already explicitly selected by the project.

## Portfolio Input

Decision: store assumed positions in `inputs/portfolio/positions.csv`.

Rule: each row is an effective-date update. If no new row exists for a run date, the latest prior row carries forward until changed or closed.

Reason: this makes the prototype extendable without hard-coding the book in prompts.

Rule: when Gemini synthesis is enabled, active portfolio rows are scored against live market moves, calendar events, and Theme Radar/news signals before the LLM call. The top selected topics become the required order for "The 3 Things That Matter Today."

Rule: when topic scores are close, direct portfolio links receive a modest ranking preference over broad indirect macro links. For example, an ECB event should attach first to EUR/USD rather than to a high-exposure but indirect USD/JPY position.

Rule: Contrarian Corner must challenge the first selected topic rather than introduce an unrelated risk.

Rule: the run log records selected topics, score components, and selected chart metadata for auditability.

## Feedback Input

Decision: include a feedback questionnaire and local CSV template.

Reason: feedback can improve source/topic ranking without model fine-tuning.

Rule: `FEEDBACK_PATH` points to a local ignored CSV. Matching high-rated items nudge future topic candidates up, matching low-rated or "too generic" items nudge them down, and the adjustment is recorded in topic score components.

## Chart Choice

Decision: select the chart from the top portfolio-aware topic when live history is available.

Reason: the earlier fixed USD/JPY chart made repeated runs too mechanical once the portfolio file expanded. The chart should support the first selected topic, not force the first topic to be USD/JPY.

Chart rule: line charts should usually show more than one month of history when available; the current chart uses roughly three months and highlights the latest five observations.

Fallback: USD/JPY remains the default chart when no selected topic has a usable live series.

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

Rule: the manual-send workflow may carry commented GitHub `schedule:` templates for production and temporary testing, but scheduled email sending stays disabled by default. A maintainer should uncomment only one schedule block after secrets are configured and a manual send has succeeded, then comment any temporary test schedule again after the test.

## Memo And Submission Docs

Decision: keep final submission evidence in tracked Markdown/PDF files.

Files:

- `README.md`: new-user setup and usage guide.
- `ASSIGNMENT_AUDIT.md`: requirement checklist.
- `costs.md`: measured runtime, token, cost, and source notes.
- `memo.md` / `memo.pdf`: one-page assignment memo.
- `PLAN.md`: current project status and submission checklist.

Reason: an evaluator or new implementer should be able to understand the project from the tracked documentation alone.

## Versioning

Decision: use `pyproject.toml` and git tags as the formal version sources.

Reason: version labels drift when repeated across several Markdown files. `PLAN.md` should describe the active milestone, while `CHANGELOG.md` records what changed. Formal releases should update `pyproject.toml`, add a changelog entry, and create a git tag such as `v0.2.0`.

Rule: do not label the project as being at a new version in public docs until the package version and git tag are created.
