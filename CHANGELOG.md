# Changelog

All notable public-facing changes are recorded here. Local run logs, cache files, and collaboration notes are intentionally excluded.

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
