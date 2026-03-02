"""String formatting for MCP tool returns."""

from typing import Optional

from vibe_harness_mcp.modes import get_mode


# -- Tool formatters ---


def format_mode_switch(result: dict) -> str:
    """Format the result of a mode switch for tool output."""
    if result["awaiting_confirmation"]:
        return f"[FRICTION] {result['message']}"

    if not result["success"]:
        return f"Error: {result['message']}"

    mode = result["mode"]
    mode_def = get_mode(mode)
    name = mode_def["name"] if mode_def else mode
    return f"Mode: {name}\n\n{result['message']}"


def format_vibe_check(session, *, nudge: Optional[str] = None, temporal: Optional[dict] = None) -> str:
    """Format current session state for vibe_check output."""
    mode_def = get_mode(session.mode)
    if not mode_def:
        return "Session state unavailable."

    mode_min = round(session.active_mode_minutes())
    session_min = round(session.active_session_minutes())
    idle_min = round(session.total_idle_minutes())

    lines = [
        f"Mode: {mode_def['name']}",
        "",
        mode_def["orientation"],
        "",
        f"  mode      {mode_min}min",
        f"  session   {session_min}min",
        f"  actions   {session.interaction_count}",
        f"  switches  {len(session.transitions)}",
    ]

    # Temporal context
    if temporal:
        hour = temporal.get("hour", 0)
        minute = temporal.get("minute", 0)
        period = temporal.get("period", "")
        period_label = period.replace("_", " ")
        lines.append(f"  clock     {hour:02d}:{minute:02d} ({period_label})")

        sessions_today = temporal.get("sessions_today", {})
        count = sessions_today.get("count", 0)
        total_min = sessions_today.get("total_minutes", 0)
        if count > 0:
            lines.append(f"  today     session #{count}, ~{round(total_min)}min total")

    if idle_min > 0:
        hours = idle_min / 60
        if hours >= 1:
            lines.append(f"  away      {hours:.1f}h detected")
        else:
            lines.append(f"  away      {idle_min}min detected")

    if session.nudges_surfaced > 0:
        lines.append(f"  nudges    {session.nudges_surfaced}")

    if session._pending_mode:
        lines.extend([
            "",
            f"  pending: switch to {session._pending_mode} (high friction)",
        ])

    if nudge:
        lines.extend(["", f"Nudge: {nudge}"])

    return "\n".join(lines)


def format_status_line(session) -> str:
    """One-line status for vibe://status resource."""
    mode_def = get_mode(session.mode)
    name = mode_def["name"] if mode_def else session.mode
    mode_min = round(session.active_mode_minutes())
    return f"{name} | {mode_min}min | {session.interaction_count} interactions | {session.nudges_surfaced} nudges"


def format_history(session) -> str:
    """Format mode transition history."""
    if not session.transitions:
        return "No mode transitions yet this session."

    lines = ["Mode History", ""]

    for t in session.transitions:
        ts = t.timestamp.strftime("%H:%M")
        friction_tag = f"  [{t.friction}]" if t.friction != "none" else ""
        lines.append(f"  {ts}  {t.from_mode} > {t.to_mode}{friction_tag}")

    # Time-in-mode summary
    summary = session.time_in_mode_summary()
    if summary:
        lines.extend(["", "Time in Mode", ""])
        for mode, minutes in sorted(summary.items(), key=lambda x: -x[1]):
            mode_def = get_mode(mode)
            name = mode_def["name"] if mode_def else mode
            lines.append(f"  {name:<12} {minutes:>5.1f}min")

    return "\n".join(lines)


def format_nudge_output(nudge: Optional[str]) -> str:
    """Format nudge for standalone vibe_nudge tool output."""
    if nudge is None:
        return "All clear. No nudges right now."
    return f"Nudge: {nudge}"


# -- Onboarding ---


def format_onboarding(temporal: Optional[dict] = None) -> str:
    """First-run onboarding — phased structure for AI-mediated delivery.

    Returns sections with embedded AI directives. The AI assistant should
    present these one at a time, pausing between sections rather than
    dumping everything at once.
    """
    sections = []

    # 1. Somatic check
    sections.append(
        "## Welcome to Vibe Harness\n\n"
        "Before anything else: notice how your body feels right now.\n"
        "Shoulders. Jaw. Breath. Just notice — no need to change anything.\n\n"
        "[FOR THE AI: Pause here. Let the human sit with this for a moment. "
        "Don't rush to the next section. If they respond, acknowledge what they share "
        "before continuing.]"
    )

    # 2. Time-of-day context (if available)
    if temporal:
        is_late = temporal.get("is_late", False)
        period = temporal.get("period", "")
        hour = temporal.get("hour", 0)
        if period == "early_morning" and is_late:
            sections.append(
                f"Early morning ({hour:02d}:00). Fresh start energy — or residual from last night? "
                "Only your body knows.\n\n"
                "[FOR THE AI: Light touch. Don't labour this point.]"
            )
        elif is_late:
            sections.append(
                f"It's {hour:02d}:00. Late hours can feel productive, but your body "
                "has circadian preferences. Worth noting as you begin.\n\n"
                "[FOR THE AI: This is not a judgment. Just a data point. "
                "If they want to continue, that's their call.]"
            )

    # 3. How this works
    sections.append(
        "## How this works\n\n"
        "Vibe Harness adjusts AI behaviour to match your working state. "
        "Everything is pull-only — nothing interrupts, nothing monitors you in the background. "
        "You set the tempo.\n\n"
        "Check in when you want to (`vibe_check`). "
        "Ask for a nudge when you want one (`vibe_nudge`). "
        "Switch modes when your energy shifts (`vibe_set_mode`)."
    )

    # 4. Mode selection
    sections.append(
        "## Five modes\n\n"
        "  **Explore**     Open, divergent, follow threads\n"
        "  **Build**       Concise, code-first, action-biased\n"
        "  **Think-With**  Reflective, holds complexity\n"
        "  **Ship**        Decisive, catches scope creep\n"
        "  **Cool-Off**    Minimal output, wind-down\n\n"
        "[FOR THE AI: Ask the human which mode matches where they are right now. "
        "Don't pick for them. If they're unsure, suggest Explore as a starting point.]"
    )

    # 5. You're set
    sections.append(
        "That's it. No setup, no configuration required.\n\n"
        "The governor will offer gentle check-ins based on time and activity — "
        "but only when you ask. Your body's signals come first, the tool's signals second."
    )

    return "\n\n---\n\n".join(sections)


def format_governance_trace(evaluations: list[dict]) -> str:
    """Format governance evaluations for display."""
    fired = [e for e in evaluations if e.get("fired")]
    if not fired:
        return "No governance rules triggered."
    lines = ["Governance:"]
    for e in fired:
        status = "defeated" if e.get("defeated") else "active"
        line = f"  {e['rule']}: {status}"
        if e.get("defeated_by"):
            line += f" (by {e['defeated_by']})"
        lines.append(line)
    return "\n".join(lines)
