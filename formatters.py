"""String formatting for MCP tool returns."""

from typing import Optional

from modes import get_mode

# ── ASCII banners per mode ────────────────────────────────────────────

MODE_BANNERS = {
    "explore": r"""
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ~        E X P L O R E        ~
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~""",

    "build": r"""
    >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    >          B U I L D          >
    >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>""",

    "think-with": r"""
    ???????????????????????????????
    ?      T H I N K - W I T H    ?
    ???????????????????????????????""",

    "ship": r"""
    !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    !           S H I P           !
    !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!""",

    "cool-off": r"""
    ...............................
    .       C O O L - O F F       .
    ...............................""",
}

FRICTION_BANNER = r"""
    ╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳
    ╳       F R I C T I O N       ╳
    ╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳╳"""

NUDGE_BANNER = r"""
    - - - - - - - - - - - - - - - -
    -          N U D G E           -
    - - - - - - - - - - - - - - - -"""


def _bar(char: str, width: int = 35) -> str:
    return "    " + char * width


# ── Tool formatters ───────────────────────────────────────────────────


def format_mode_switch(result: dict) -> str:
    """Format the result of a mode switch for tool output."""
    if result["awaiting_confirmation"]:
        return f"{FRICTION_BANNER}\n\n{result['message']}"

    if not result["success"]:
        return f"## Error\n\n{result['message']}"

    mode = result["mode"]
    banner = MODE_BANNERS.get(mode, "")
    return f"{banner}\n\n{result['message']}"


def format_vibe_check(session, *, nudge: Optional[str] = None) -> str:
    """Format current session state for vibe_check output."""
    mode_def = get_mode(session.mode)
    if not mode_def:
        return "Session state unavailable."

    mode_min = round(session.mode_duration_minutes())
    session_min = round(session.session_duration_minutes())
    banner = MODE_BANNERS.get(session.mode, "")

    lines = [
        banner,
        "",
        f"  {mode_def['orientation']}",
        "",
        _bar("─"),
        "",
        f"    mode      {mode_min}min",
        f"    session   {session_min}min",
        f"    actions   {session.interaction_count}",
        f"    switches  {len(session.transitions)}",
    ]

    if session.nudges_surfaced > 0:
        lines.append(f"    nudges    {session.nudges_surfaced}")

    if session._pending_mode:
        lines.extend([
            "",
            f"    ** pending: switch to {session._pending_mode} (high friction) **",
        ])

    if nudge:
        lines.extend(["", NUDGE_BANNER, "", f"  {nudge}"])

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
        return "    No mode transitions yet this session."

    lines = [
        _bar("─"),
        "    M O D E   H I S T O R Y",
        _bar("─"),
        "",
    ]

    for t in session.transitions:
        ts = t.timestamp.strftime("%H:%M")
        friction_tag = f"  [{t.friction}]" if t.friction != "none" else ""
        arrow = "───>"
        lines.append(f"    {ts}  {t.from_mode} {arrow} {t.to_mode}{friction_tag}")

    # Time-in-mode summary
    summary = session.time_in_mode_summary()
    if summary:
        lines.extend(["", _bar("─"), "    T I M E   I N   M O D E", _bar("─"), ""])
        for mode, minutes in sorted(summary.items(), key=lambda x: -x[1]):
            mode_def = get_mode(mode)
            emoji = mode_def["emoji"] if mode_def else " "
            name = mode_def["name"] if mode_def else mode
            bar_len = max(1, int(minutes / 2))
            bar = emoji * min(bar_len, 30)
            lines.append(f"    {name:<12} {minutes:>5.1f}min  {bar}")

    return "\n".join(lines)


def format_nudge_output(nudge: Optional[str]) -> str:
    """Format nudge for standalone vibe_nudge tool output."""
    if nudge is None:
        return "    All clear. No nudges right now."
    return f"{NUDGE_BANNER}\n\n  {nudge}"
