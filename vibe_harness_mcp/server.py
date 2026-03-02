"""Vibe Harness — MCP server that tunes human-AI interaction rhythm.

Layer 1: Manual mode switching with research-informed presets.
Layer 2 (future): Polar H10 BLE integration for biosignal.
Layer 3 (future): Full loop with semantic coupling + session history.

Humans are variable and models are adjustable.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from vibe_harness_mcp._version import __version__
from vibe_harness_mcp.session import VibeSession
from vibe_harness_mcp.modes import valid_modes, get_mode
from vibe_harness_mcp.formatters import format_mode_switch, format_vibe_check, format_status_line, format_history, format_nudge_output, format_onboarding
from vibe_harness_mcp.governor import evaluate_rules
from vibe_harness_mcp.session import HISTORY_FILE
from vibe_harness_mcp.temporal import get_temporal_context
from vibe_harness_mcp import config

# ---------------------------------------------------------------------------
# Session (single instance per MCP process)
# ---------------------------------------------------------------------------

_session = VibeSession()

EXPORT_DIR = Path.home() / ".vibe-harness" / "sessions"


def _get_onboarding_message():
    """Return onboarding text on first run (no history file), or None."""
    if _session._onboarding_shown or HISTORY_FILE.exists():
        return None
    _session._onboarding_shown = True
    temporal = get_temporal_context()
    return format_onboarding(temporal=temporal)

# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP("Vibe Harness")


# --- Tools ---


@mcp.tool()
def vibe_set_mode(mode: str) -> str:
    """Switch working mode. Returns orientation text + session stats.

    High-friction transitions (e.g. explore->ship) return a warning;
    call again with the same mode to confirm.

    Available modes: explore, build, think-with, ship, cool-off

    Args:
        mode: The mode to switch to.
    """
    _session.record_interaction()
    result = _session.set_mode(mode)
    return format_mode_switch(result)


@mcp.tool()
def vibe_check() -> str:
    """Current state: mode, duration, interaction count, pending nudges.

    Call this to understand the human's current working context.
    """
    _session.record_interaction()
    nudge, evaluations = evaluate_rules(_session)
    if nudge:
        _session.nudges_surfaced += 1
        _session.last_nudge_at = datetime.now(timezone.utc)
    _session.record_governance_evaluation(
        [e.to_dict() for e in evaluations]
    )
    onboarding = _get_onboarding_message()
    temporal = get_temporal_context()
    output = format_vibe_check(_session, nudge=nudge, temporal=temporal)
    if onboarding:
        output = onboarding + "\n\n---\n\n" + output
    return output


@mcp.tool()
def vibe_nudge() -> str:
    """Request a contextual nudge. Governor evaluates session state and returns
    a suggestion (e.g. take a break, switch modes) or 'all clear'.
    """
    _session.record_interaction()
    nudge, evaluations = evaluate_rules(_session)
    if nudge:
        _session.nudges_surfaced += 1
        _session.last_nudge_at = datetime.now(timezone.utc)
    _session.record_governance_evaluation(
        [e.to_dict() for e in evaluations]
    )
    return format_nudge_output(nudge)


@mcp.tool()
def vibe_history() -> str:
    """Mode transition timeline + time-in-mode summary for current session."""
    _session.record_interaction()
    return format_history(_session)


@mcp.tool()
def vibe_session_export() -> str:
    """Export session data as JSON to ~/.vibe-harness/sessions/.

    Returns file path + summary.
    """
    _session.record_interaction()

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    filename = f"{now.strftime('%Y-%m-%d_%H%M')}_{_session.session_id}.json"
    path = EXPORT_DIR / filename

    data = _session.to_export_dict()
    path.write_text(json.dumps(data, indent=2))

    summary = _session.time_in_mode_summary()
    mode_summary = ", ".join(f"{k}: {v}min" for k, v in summary.items())

    return (
        f"Session exported to: {path}\n\n"
        f"**Duration:** {round(_session.session_duration_minutes())}min\n"
        f"**Interactions:** {_session.interaction_count}\n"
        f"**Mode switches:** {len(_session.transitions)}\n"
        f"**Time in mode:** {mode_summary}"
    )


@mcp.tool()
def vibe_configure(setting: str, value: str) -> str:
    """Adjust runtime configuration.

    Available settings:
    - nudges.time_check_minutes (default: 45)
    - nudges.session_max_minutes (default: 120)
    - nudges.interaction_threshold (default: 100)
    - nudges.cooldown_minutes (default: 15)
    - friction.enabled (default: true)
    - export.auto_export (default: false)
    - temporal.late_night_start (default: 22)
    - temporal.late_night_end (default: 6)

    Args:
        setting: The config key to change.
        value: The new value (will be coerced to appropriate type).
    """
    _session.record_interaction()
    success, message = config.set_runtime(setting, value)
    if success:
        return f"Updated: {message}"
    return f"Error: {message}"


# --- Resources ---


@mcp.resource("vibe://context")
def vibe_context() -> str:
    """Current mode orientation text. Inject into system prompt for mode-aware AI behavior."""
    mode_def = get_mode(_session.mode)
    if not mode_def:
        return ""
    return (
        f"[Vibe Harness] Mode: {mode_def['name']}\n\n"
        f"{mode_def['orientation']}\n\n"
        f"Behavioral guidance: {', '.join(mode_def['ai_behavior'])}"
    )


@mcp.resource("vibe://status")
def vibe_status() -> str:
    """One-line session status."""
    return format_status_line(_session)
