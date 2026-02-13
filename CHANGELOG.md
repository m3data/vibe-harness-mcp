# Changelog

All notable changes to Vibe Harness are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Export schema version is tracked independently — it describes the JSON export
format, not the software release. Schema version is noted in each release when
it changes.

## [Unreleased]

## [0.3.0] - 2026-02-13

Activity-aware duration tracking. The governor now distinguishes "terminal open"
from "human working" by detecting idle gaps between tool calls.

### Added
- `IdleGap` dataclass for recording detected idle periods
- `active_session_minutes()` and `active_mode_minutes()` on `VibeSession` — elapsed minus idle time
- `total_idle_minutes()` for total detected idle time
- `activity.idle_threshold_minutes` config setting (default: 30)
- `away Xh detected` line in `vibe_check()` output when idle time exists
- `active_duration_minutes` and `idle_gaps` fields in session export
- `_version.py` as single source of truth for package version
- `EXPORT_SCHEMA_VERSION` constant in `session.py`
- `CHANGELOG.md` (this file), retro-filled from commit history
- Git tags for all releases (`v0.1.0`, `v0.2.0`, `v0.3.0`)
- 26 new tests (116 total)

### Changed
- Governor evaluates rules against active durations, not raw elapsed time
- `vibe_check()` and status line display active durations
- `time_in_mode_summary()` subtracts idle gaps per mode span
- Export schema version: `0.2.0` → `0.3.0`

### Fixed
- Overnight/idle terminal no longer triggers false "step away" nudge

## [0.2.0] - 2026-02-06

Defeasible governance with full accountability trace.

### Added
- `GovernanceRule` and `RuleEvaluation` dataclasses
- Five priority-ordered rules: cooldown suppression, session duration, mode duration, mode drift, interaction count
- Full governance trace recorded on every evaluation — which rules fired, which were defeated, and by what
- `evaluate_rules()` returns `(message, trace)` tuple
- Governance trace included in session export
- ESL-A v0.1 license
- Slash commands: `/vibe`, `/vibe-mode`, `/vibe-history`

### Changed
- Governor architecture: from simple threshold checks to defeasible rule engine
- Export schema version: `0.1.0` → `0.2.0`

## [0.1.0] - 2026-02-05

Initial release. Layer 1: manual mode switching with research-informed presets.

### Added
- FastMCP server with stdio transport
- 5 working modes: explore, build, think-with, ship, cool-off
- Transition friction matrix (none/medium/high) with double-call confirmation for high friction
- `vibe_set_mode()`, `vibe_check()`, `vibe_nudge()`, `vibe_history()`, `vibe_session_export()`, `vibe_configure()` tools
- `vibe://context` and `vibe://status` MCP resources
- Three-layer config resolution: defaults < user < project < runtime
- JSONL mode history at `~/.vibe-harness/mode-history.jsonl`
- Versioned JSON session export
- Onboarding message for first-time users
- 73 unit tests

[Unreleased]: https://github.com/m3data/vibe-harness-mcp/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/m3data/vibe-harness-mcp/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/m3data/vibe-harness-mcp/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/m3data/vibe-harness-mcp/releases/tag/v0.1.0
