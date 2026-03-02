# Changelog

All notable changes to Vibe Harness are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Export schema version is tracked independently — it describes the JSON export
format, not the software release. Schema version is noted in each release when
it changes.

## [Unreleased]

## [0.4.1] - 2026-03-03

Active onboarding ceremony. First-time users get a two-phase welcome that
respects the soma: body notice first, orientation second. Fires on any
vibe tool call, not just `vibe_check()`.

### Changed
- **Active onboarding ceremony**: replaces passive `format_onboarding()` dump with two-phase ceremony
  - Phase 1: somatic notice — "notice how your body feels" + AI directive to pause and wait
  - Phase 2: orientation + mode pick — how it works, five modes, AI directive to ask for choice
  - Ceremony intercepts **all** tool calls (not just `vibe_check`), guaranteeing it fires on first use
  - Normal tool output withheld during ceremony phases
  - Mode switch from human's choice completes the ceremony
- Gating unchanged: ceremony only fires when `mode-history.jsonl` doesn't exist (first-ever use)
- `VibeSession._onboarding_shown` replaced with `_ceremony_phase` (0 / 1 / None state machine)
- `format_onboarding()` replaced with `format_ceremony_phase1()` and `format_ceremony_phase2()`
- `_get_onboarding_message()` replaced with `_check_ceremony()` in server

### Added
- `VibeSession.ceremony_active()` and `advance_ceremony()` helper methods
- `tests/test_ceremony_integration.py` — full flow integration tests
- New formatter and session tests for ceremony phases

## [0.4.0] - 2026-03-03

Installable package, temporal awareness, and phased onboarding. The one-liner
install makes Vibe Harness usable by anyone with `uvx` or `pip`.

### Added
- **Package restructuring**: `vibe_harness_mcp/` proper Python package with `__main__.py` entry point
- **One-liner install**: `claude mcp add vibe-harness -- uvx --from "git+https://github.com/m3data/vibe-harness-mcp.git" vibe-harness-mcp`
- **Temporal awareness** (`temporal.py`): clock-time context and cross-session pattern mining from `mode-history.jsonl`
  - Time-of-day period detection (early_morning, morning, afternoon, evening, late_night)
  - Sessions today count and total minutes
  - Sessions this week with dominant mode and mode distribution
  - Session boundary detection via `session_id` grouping
- **Late-night governor rule** (priority 6): gentle circadian nudge when working past configurable hours (default 22:00-06:00)
- **Temporal context in `vibe_check()`**: clock time and session count displayed
- `temporal.late_night_start` and `temporal.late_night_end` config settings
- **Phased onboarding**: rewritten `format_onboarding()` with somatic check, time-of-day context, AI-mediated delivery directives (`[FOR THE AI: ...]` blocks)
- 25 new tests (141 total): temporal module, late-night governor rule, onboarding formatting, temporal vibe_check integration

### Changed
- Source files moved from root into `vibe_harness_mcp/` package
- All imports converted to absolute package imports
- `pyproject.toml` rewritten: hatchling build system, `vibe-harness-mcp` package name, console script entry point
- Governor now has 6 rules (was 5) — late_night added at priority 6
- Onboarding now time-aware: different messages for late night vs early morning vs daytime
- Export schema version: `0.3.0` -> `0.4.0`

### Removed
- `sys.path.insert` hacks in test files (replaced by proper package imports)
- Root-level `server.py` entry point replaced by `python -m vibe_harness_mcp`

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
- Export schema version: `0.2.0` -> `0.3.0`

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
- Export schema version: `0.1.0` -> `0.2.0`

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

[Unreleased]: https://github.com/m3data/vibe-harness-mcp/compare/v0.4.1...HEAD
[0.4.1]: https://github.com/m3data/vibe-harness-mcp/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/m3data/vibe-harness-mcp/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/m3data/vibe-harness-mcp/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/m3data/vibe-harness-mcp/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/m3data/vibe-harness-mcp/releases/tag/v0.1.0
