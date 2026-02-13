"""Defeasible governance — rules that can be overridden by higher-priority evidence.

Each rule has a condition, a priority, and a list of rules that can defeat it.
All rules are evaluated every time (no short-circuit) to produce a complete
governance trace. The highest-priority firing rule wins; lower-priority rules
that also fired are marked as defeated.

This is like screen time alerts on your phone: the alert fires based on a rule,
but other rules can override it. The first rule's conclusion is defeated by
the second rule's higher priority. Making this explicit means you can see
why a nudge did or didn't appear.

Rule priority (highest first):
1. Cooldown suppression — one nudge per cooldown window
2. Session duration — full session too long
3. Mode duration — stuck in one mode
4. Mode drift — behaviour doesn't match declared mode
5. Interaction count — high activity without mode reflection

All thresholds pulled from config.get() so runtime overrides work.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

import config


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class GovernanceRule:
    """A single governance rule with explicit defeasibility."""

    name: str
    priority: int  # lower = higher priority (1 is highest)
    rule_type: str  # "suppress", "nudge", or "drift"
    condition: Callable[[dict], bool]
    message: Callable[[dict], str]
    defeated_by: list[str] = field(default_factory=list)


@dataclass
class RuleEvaluation:
    """Record of a single rule evaluation within a governance trace."""

    rule_name: str
    fired: bool
    defeated: bool
    defeated_by: Optional[str] = None
    message: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
            "rule": self.rule_name,
            "fired": self.fired,
            "defeated": self.defeated,
        }
        if self.defeated_by:
            d["defeated_by"] = self.defeated_by
        if self.message:
            d["message"] = self.message
        return d


# ---------------------------------------------------------------------------
# Session state extraction (decouples rules from VibeSession internals)
# ---------------------------------------------------------------------------


def _build_session_state(session) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "mode": session.mode,
        "mode_minutes": session.active_mode_minutes(),
        "session_minutes": session.active_session_minutes(),
        "interactions": session.interaction_count,
        "switches": len(session.transitions),
        "last_nudge_at": session.last_nudge_at,
        "now": now,
        # Thresholds from config
        "cooldown_minutes": config.get("nudges.cooldown_minutes"),
        "session_max_minutes": config.get("nudges.session_max_minutes"),
        "time_check_minutes": config.get("nudges.time_check_minutes"),
        "interaction_threshold": config.get("nudges.interaction_threshold"),
    }


# ---------------------------------------------------------------------------
# Rule conditions
# ---------------------------------------------------------------------------


def _cooldown_active(state: dict) -> bool:
    if state["last_nudge_at"] is None:
        return False
    since_last = (state["now"] - state["last_nudge_at"]).total_seconds() / 60
    return since_last < state["cooldown_minutes"]


def _session_too_long(state: dict) -> bool:
    return state["session_minutes"] >= state["session_max_minutes"]


def _mode_too_long(state: dict) -> bool:
    return state["mode_minutes"] >= state["time_check_minutes"]


def _mode_drifting(state: dict) -> bool:
    mode = state["mode"]
    mode_min = state["mode_minutes"]
    interactions = state["interactions"]
    if mode == "explore" and mode_min >= 30 and interactions > 50:
        return True
    if mode == "ship" and mode_min >= 60:
        return True
    return False


def _too_many_interactions(state: dict) -> bool:
    return (
        state["interactions"] >= state["interaction_threshold"]
        and state["switches"] == 0
    )


# ---------------------------------------------------------------------------
# Rule messages
# ---------------------------------------------------------------------------

_MODE_DURATION_MESSAGES = {
    "explore": "Notice your body. Still curious, or starting to spin? ({minutes}min in explore)",
    "build": "Check in: are your shoulders tense? Breathing shallow? ({minutes}min in build)",
    "think-with": "Has something landed, or are you circling? Trust what your body knows. ({minutes}min in think-with)",
    "ship": "Pause. Is this shipping energy or grinding energy? Your body knows the difference. ({minutes}min in ship)",
    "cool-off": "How do you feel? Ready to re-engage, or does your body want more rest? ({minutes}min in cool-off)",
}

_MODE_DRIFT_MESSAGES = {
    "explore": (
        "Lots of activity for explore mode. "
        "Notice: does this feel like building? Name it if so."
    ),
    "ship": (
        "Over an hour in ship. "
        "Notice whether you're actually shipping or pushing through. Your body will tell you."
    ),
}


def _cooldown_msg(state: dict) -> str:
    return ""  # suppress rules produce no output


def _session_too_long_msg(state: dict) -> str:
    return (
        f"It's been {round(state['session_minutes'])} minutes. "
        "How does your body feel? This might be a good time to step away."
    )


def _mode_too_long_msg(state: dict) -> str:
    minutes = round(state["mode_minutes"])
    template = _MODE_DURATION_MESSAGES.get(state["mode"], "")
    return template.format(minutes=minutes)


def _mode_drift_msg(state: dict) -> str:
    return _MODE_DRIFT_MESSAGES.get(state["mode"], "")


def _too_many_interactions_msg(state: dict) -> str:
    return (
        f"{state['interactions']} interactions without a mode switch. "
        "Pause and notice: does this mode still match how you feel?"
    )


# ---------------------------------------------------------------------------
# Rules registry
# ---------------------------------------------------------------------------

RULES: list[GovernanceRule] = [
    GovernanceRule(
        name="cooldown_suppression",
        priority=1,
        rule_type="suppress",
        condition=_cooldown_active,
        message=_cooldown_msg,
        defeated_by=[],
    ),
    GovernanceRule(
        name="session_duration",
        priority=2,
        rule_type="nudge",
        condition=_session_too_long,
        message=_session_too_long_msg,
        defeated_by=["cooldown_suppression"],
    ),
    GovernanceRule(
        name="mode_duration",
        priority=3,
        rule_type="nudge",
        condition=_mode_too_long,
        message=_mode_too_long_msg,
        defeated_by=["cooldown_suppression", "session_duration"],
    ),
    GovernanceRule(
        name="mode_drift",
        priority=4,
        rule_type="drift",
        condition=_mode_drifting,
        message=_mode_drift_msg,
        defeated_by=["cooldown_suppression", "session_duration", "mode_duration"],
    ),
    GovernanceRule(
        name="interaction_count",
        priority=5,
        rule_type="nudge",
        condition=_too_many_interactions,
        message=_too_many_interactions_msg,
        defeated_by=[
            "cooldown_suppression",
            "session_duration",
            "mode_duration",
            "mode_drift",
        ],
    ),
]


# ---------------------------------------------------------------------------
# Evaluation engine
# ---------------------------------------------------------------------------


def evaluate_rules(session) -> tuple[Optional[str], list[RuleEvaluation]]:
    """Evaluate all governance rules. Returns (winning_message, full_trace).

    Every rule is evaluated against the session state. The highest-priority
    rule that fires wins. Lower-priority rules that also fired are marked
    as defeated. This is defeasible governance: conclusions can be overridden
    by higher-priority evidence.
    """
    state = _build_session_state(session)
    evaluations: list[RuleEvaluation] = []
    winner_name: Optional[str] = None
    winner_message: Optional[str] = None

    for rule in sorted(RULES, key=lambda r: r.priority):
        fired = rule.condition(state)

        if not fired:
            evaluations.append(RuleEvaluation(
                rule_name=rule.name, fired=False, defeated=False
            ))
            continue

        # Rule fired — is it defeated by an already-winning rule?
        if winner_name is not None:
            evaluations.append(RuleEvaluation(
                rule_name=rule.name,
                fired=True,
                defeated=True,
                defeated_by=winner_name,
            ))
            continue

        # This rule wins
        if rule.rule_type == "suppress":
            winner_name = rule.name
            evaluations.append(RuleEvaluation(
                rule_name=rule.name, fired=True, defeated=False
            ))
        else:
            msg = rule.message(state)
            winner_name = rule.name
            winner_message = msg
            evaluations.append(RuleEvaluation(
                rule_name=rule.name, fired=True, defeated=False, message=msg
            ))

    return winner_message, evaluations


def evaluate_nudge(session) -> Optional[str]:
    """Evaluate session state and return a nudge message, or None.

    Thin wrapper around evaluate_rules() for backwards compatibility.
    Use evaluate_rules() directly when you need the governance trace.
    """
    message, _ = evaluate_rules(session)
    return message


# ---------------------------------------------------------------------------
# Formatting (kept for backwards compatibility)
# ---------------------------------------------------------------------------


def format_nudge_or_clear(nudge: Optional[str]) -> str:
    """Format a nudge message, or 'all clear' if none."""
    if nudge is None:
        return "All clear. No nudges right now."
    return f"## Nudge\n\n{nudge}"
