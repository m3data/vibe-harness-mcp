"""Nudge logic — evaluates session state and surfaces contextual suggestions.

Checks in priority order:
1. Cooldown suppression (one nudge per cooldown window)
2. Session duration (full session too long)
3. Mode duration (stuck in one mode)
4. Mode drift (behavior doesn't match declared mode)
5. Interaction count (high activity without mode reflection)

All thresholds pulled from config.get() so runtime overrides work.
"""

from datetime import datetime, timezone
from typing import Optional

import config


def evaluate_nudge(session) -> Optional[str]:
    """Evaluate session state and return a nudge message, or None."""

    # 1. Cooldown suppression
    cooldown_min = config.get("nudges.cooldown_minutes")
    if session.last_nudge_at is not None:
        since_last = (datetime.now(timezone.utc) - session.last_nudge_at).total_seconds() / 60
        if since_last < cooldown_min:
            return None

    mode = session.mode
    mode_min = session.mode_duration_minutes()
    session_min = session.session_duration_minutes()
    interactions = session.interaction_count
    switches = len(session.transitions)

    # 2. Session duration
    session_max = config.get("nudges.session_max_minutes")
    if session_min >= session_max:
        return (
            f"You've been in session for {round(session_min)}min "
            f"(limit: {session_max}min). Consider cool-off."
        )

    # 3. Mode duration
    time_check = config.get("nudges.time_check_minutes")
    if mode_min >= time_check:
        n = round(mode_min)
        nudge = _mode_duration_nudge(mode, n)
        if nudge:
            return nudge

    # 4. Mode drift heuristics
    drift_nudge = _mode_drift_nudge(mode, mode_min, interactions)
    if drift_nudge:
        return drift_nudge

    # 5. Interaction count without mode reflection
    interaction_threshold = config.get("nudges.interaction_threshold")
    if interactions >= interaction_threshold and switches == 0:
        return (
            f"{interactions} interactions without a mode switch. "
            "Worth checking: is the current mode still right?"
        )

    return None


def _mode_duration_nudge(mode: str, minutes: int) -> Optional[str]:
    """Mode-specific nudge for extended time in one mode."""
    messages = {
        "explore": f"You've been exploring for {minutes}min. Ready to build something?",
        "build": f"Building for {minutes}min. Ready to ship, or need to step back?",
        "think-with": f"Sitting with this for {minutes}min. Has anything crystallised?",
        "ship": f"Shipping for {minutes}min. Is this still the right mode, or is build more honest?",
        "cool-off": f"You've been cooling off for {minutes}min. Ready to gently re-engage?",
    }
    return messages.get(mode)


def _mode_drift_nudge(mode: str, mode_min: float, interactions: int) -> Optional[str]:
    """Detect when behavior doesn't match declared mode."""
    if mode == "explore" and mode_min >= 30 and interactions > 50:
        return (
            "High interaction count in explore. "
            "Might be building without naming it."
        )
    if mode == "ship" and mode_min >= 60:
        return (
            "Shipping for over an hour. "
            "If it's not shipping, build might be more honest."
        )
    return None


def format_nudge_or_clear(nudge: Optional[str]) -> str:
    """Format a nudge message, or 'all clear' if none."""
    if nudge is None:
        return "All clear. No nudges right now."
    return f"## Nudge\n\n{nudge}"
