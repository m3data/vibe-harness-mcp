"""String formatting for MCP tool returns."""

from modes import get_mode


def format_mode_switch(result: dict) -> str:
    """Format the result of a mode switch for tool output."""
    if result["awaiting_confirmation"]:
        return f"## Friction: High\n\n{result['message']}"

    if not result["success"]:
        return f"## Error\n\n{result['message']}"

    mode_def = get_mode(result["mode"])
    emoji = mode_def["emoji"] if mode_def else ""
    return f"## {emoji} {result['message']}"


def format_vibe_check(session) -> str:
    """Format current session state for vibe_check output."""
    mode_def = get_mode(session.mode)
    if not mode_def:
        return "Session state unavailable."

    mode_min = round(session.mode_duration_minutes())
    session_min = round(session.session_duration_minutes())

    lines = [
        f"## {mode_def['emoji']} {mode_def['name']}",
        "",
        mode_def["orientation"],
        "",
        "---",
        "",
        f"**Mode duration:** {mode_min}min",
        f"**Session duration:** {session_min}min",
        f"**Interactions:** {session.interaction_count}",
        f"**Mode switches:** {len(session.transitions)}",
    ]

    if session.nudges_surfaced > 0:
        lines.append(f"**Nudges surfaced:** {session.nudges_surfaced}")

    if session._pending_mode:
        lines.extend([
            "",
            f"**Pending confirmation:** switch to {session._pending_mode} (high friction)",
        ])

    return "\n".join(lines)


def format_status_line(session) -> str:
    """One-line status for vibe://status resource."""
    mode_def = get_mode(session.mode)
    name = mode_def["name"] if mode_def else session.mode
    mode_min = round(session.mode_duration_minutes())
    return f"{name} | {mode_min}min | {session.interaction_count} interactions | {session.nudges_surfaced} nudges"


def format_history(session) -> str:
    """Format mode transition history."""
    if not session.transitions:
        return "No mode transitions yet this session."

    lines = ["## Mode History", ""]

    for t in session.transitions:
        ts = t.timestamp.strftime("%H:%M")
        friction_tag = f" [{t.friction}]" if t.friction != "none" else ""
        lines.append(f"- `{ts}` {t.from_mode} -> {t.to_mode}{friction_tag}")

    # Time-in-mode summary
    summary = session.time_in_mode_summary()
    if summary:
        lines.extend(["", "### Time in Mode", ""])
        for mode, minutes in sorted(summary.items(), key=lambda x: -x[1]):
            mode_def = get_mode(mode)
            name = mode_def["name"] if mode_def else mode
            lines.append(f"- **{name}:** {minutes}min")

    return "\n".join(lines)
