# Changelog

All notable public-facing changes are recorded here. Local run logs, cache files, and collaboration notes are intentionally excluded.

## 2026-06-12

### Added

- Added best-effort Theme Radar article-text extraction for direct RSS article pages, with source-depth labels only upgraded when useful page text is actually extracted.
- Added `THEME_ARTICLE_FETCH_LIMIT` as the preferred control for Theme Radar article-page enrichment, with `THEME_METADATA_FETCH_LIMIT` retained as a backward-compatible fallback.
- Added optional portfolio `significance` labels so strategic monitoring importance can influence topic ranking separately from assumed exposure size.
- Added public-safe AI and current macro-theme portfolio assumptions, including US AI semiconductors, Nasdaq/growth, data-center power, copper, European defense, and stablecoin/crypto infrastructure monitors.
- Added live Yahoo Finance proxy rows for Nasdaq 100, US AI semiconductors, US data-center power, and copper.
- Added readable topic-selection reasons to run logs, alongside score components and selected chart metadata.
- Added JSON parsing hardening for Gemini responses that contain one valid JSON object followed by stray trailing text; content validation still runs after parsing.
- Added deterministic repair for common generic Theme Radar openers, including `This analysis explores`, before final narrative validation.
- Added `LLM_FAILURE_MODE=section_fallback` so scheduled emails can still send verified sections while explicitly withholding failed narrative sections.
- Added an explicit Theme Radar empty-state note when no verified Theme Radar source items are available.

### Changed

- Theme Radar source scoring now gives a modest preference to usable article text excerpts over metadata-only or search-snippet evidence.
- Theme Radar documentation now distinguishes RSS excerpts, RSS content fields, article text excerpts, article metadata, and search result snippets more explicitly.
- Topic selection now recognizes AI semiconductor, AI power, copper/electrification, defense, and stablecoin/crypto-plumbing themes when supported by market rows or Theme Radar inputs.
- Contrarian Corner prompting now asks for a clearer simple-read challenge, trigger, and book implication while keeping existing validation boundaries.

## 2026-06-11

### Added

- Added portfolio-aware topic selection before Gemini narrative synthesis.
- Added dynamic chart metadata so "One Chart Worth Seeing" can follow the selected top topic instead of always using USD/JPY.
- Added live dashboard coverage for China internet / tech basket, Brent oil, and VIX using public Yahoo Finance chart data.
- Added calendar-event and Theme Radar/news candidates to the code-ranked topic selector.
- Added selected-topic and score-component details to run logs.
- Added narrative validation guardrails for ECB direction, USD/JPY portfolio semantics, and US inflation/yield direction.
- Added a run-level quality report with source checks, Gemini validation attempts, repaired validation errors, and a send/no-send decision.
- Added a safe-send gate so failed Gemini narrative validation blocks email delivery and writes a failed quality log.
- Added centralized deterministic narrative rule groups for portfolio semantics, unsupported claims, market-number consistency, market-direction consistency, and asset-move contradictions.
- Added contradiction tests for oil/inflation, gold positioning, dollar pressure, volatility, and EM debt logic.
- Added Theme Radar near-duplicate topic filtering using ignored local headline history.
- Added a `compare-models` CLI command for checking Gemini model repairs, token use, estimated cost, and runtime on the same structured inputs.
- Added exact validation-error capture to `compare-models` logs so model warnings can be diagnosed by failure type.
- Added optional `LLM_FAILURE_MODE=data_only` support so failed Gemini narrative validation can produce a clearly labeled data-only fallback instead of an interpreted brief.
- Added local reader-feedback CSV import so recurring comments can nudge topic ranking without fine-tuning the model.
- Added best-effort Theme Radar article-metadata enrichment for selected RSS candidates.
- Added code-generated narrative guardrails and avoid-claims to selected topics before Gemini drafts the brief.
- Added global dashboard guardrails so cross-cutting DXY, VIX, and oil direction checks are attached to every selected topic.
- Added validation for underweight S&P 500 direction, so rising S&P is not described as helping an underweight position.
- Added ignored local diagnostics for failed Gemini validation drafts, including prompt version, token usage, validation errors, and failed responses.

### Changed

- Gemini now receives a code-selected topic agenda and must write "The 3 Things That Matter Today" in that order.
- Contrarian Corner now has to challenge the first selected topic instead of drifting to an unrelated theme.
- The chart source, title, feedback row, image alt text, and rendered chart title now come from chart metadata rather than hard-coded USD/JPY text.
- Theme Radar summaries now strip prompt-mechanics wording such as source-input notes before rendering.
- Theme Radar now avoids both repeated links and recently selected near-duplicate topics when enough alternatives exist.
- Topic ranking now gives close-score preference to direct portfolio links over broad indirect macro links.
- CLI output now includes the run quality verdict.
- Macro narrative validation now lives in a dedicated rule module instead of being embedded directly in the Gemini parser.
- Gemini now returns "Three Things" items as structured `body` and `so_what` fields; the application renders the `So what:` label consistently.
- Theme Radar now uses richer feed-provided content fields when available, while search-derived items remain labeled as snippets.
- Theme Radar recent-link and near-duplicate memory now applies score penalties rather than hard restrictions, so highly important repeated stories can still be selected.
- Gemini narrative prompt direction checks now explicitly cover DXY and oil moves after a blocked send exposed a recurring dollar-direction failure.
- Gemini now receives selected-topic guardrails for common repair-prone logic such as EM debt under stronger dollar pressure and USD/JPY long semantics.
- Narrative validation now distinguishes true contradictions from nearby but separate claims, such as lower-yield relief versus firmer-dollar pressure.
- Theme Radar generic "examines" openers are normalized before validation, reducing avoidable style-only quality-gate failures.

## 2026-06-10

### Added

- Added `AGENTS.md` to document repo working rules and public/local file boundaries.
- Added Theme Radar recent-link memory under the local `.cache/` tree.
- Added no-key Google News RSS search queries to broaden Theme Radar candidate discovery.
- Added trusted-publisher filtering for Google News RSS search results.
- Added a versioning convention: formal versions live in `pyproject.toml` and git tags, not scattered milestone labels.

### Changed

- Theme Radar now avoids links selected before the current run date for the configured recent-day window.
- Same-day reruns may repeat Theme Radar entries because the current run date is defined by `BRIEF_TIMEZONE`.
- Source Status now reports the actual Theme Radar sources selected in each run.

### Fixed

- Ignored generated Python package metadata (`*.egg-info/`) so local installs do not appear as pending git changes.
