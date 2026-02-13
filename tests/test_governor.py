"""Tests for governor.py — nudge evaluation logic."""

import importlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from governor import evaluate_nudge, evaluate_rules, format_nudge_or_clear, RULES, GovernanceRule, RuleEvaluation
from session import VibeSession, IdleGap


def _fresh_config():
    """Reset config to defaults."""
    config._runtime_overrides.clear()
    config._user_config.clear()
    config._project_config.clear()


class TestCooldownSuppression:
    def setup_method(self):
        _fresh_config()

    def test_no_nudge_during_cooldown(self):
        s = VibeSession()
        s.mode = "explore"
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=50)
        s.last_nudge_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        assert evaluate_nudge(s) is None

    def test_nudge_fires_after_cooldown(self):
        s = VibeSession()
        s.mode = "explore"
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=50)
        s.last_nudge_at = datetime.now(timezone.utc) - timedelta(minutes=20)
        assert evaluate_nudge(s) is not None

    def test_no_cooldown_on_first_nudge(self):
        s = VibeSession()
        s.mode = "explore"
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=50)
        assert s.last_nudge_at is None
        assert evaluate_nudge(s) is not None


class TestSessionDuration:
    def setup_method(self):
        _fresh_config()

    def test_session_duration_nudge(self):
        s = VibeSession()
        s.started_at = datetime.now(timezone.utc) - timedelta(minutes=130)
        nudge = evaluate_nudge(s)
        assert nudge is not None
        assert "step away" in nudge

    def test_no_nudge_within_session_limit(self):
        s = VibeSession()
        s.started_at = datetime.now(timezone.utc) - timedelta(minutes=60)
        assert evaluate_nudge(s) is None


class TestModeDuration:
    def setup_method(self):
        _fresh_config()

    def test_explore_duration_nudge(self):
        s = VibeSession()
        s.mode = "explore"
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=50)
        nudge = evaluate_nudge(s)
        assert "explore" in nudge
        assert "curious" in nudge

    def test_build_duration_nudge(self):
        s = VibeSession()
        s.mode = "build"
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=50)
        nudge = evaluate_nudge(s)
        assert "build" in nudge

    def test_think_with_duration_nudge(self):
        s = VibeSession()
        s.mode = "think-with"
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=50)
        nudge = evaluate_nudge(s)
        assert "think-with" in nudge

    def test_ship_duration_nudge(self):
        s = VibeSession()
        s.mode = "ship"
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=50)
        nudge = evaluate_nudge(s)
        assert "ship" in nudge

    def test_cool_off_duration_nudge(self):
        s = VibeSession()
        s.mode = "cool-off"
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=50)
        nudge = evaluate_nudge(s)
        assert "cool-off" in nudge

    def test_no_nudge_below_threshold(self):
        s = VibeSession()
        s.mode = "build"
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=10)
        assert evaluate_nudge(s) is None

    def test_configurable_threshold(self):
        config.set_runtime("nudges.time_check_minutes", "5")
        s = VibeSession()
        s.mode = "build"
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=6)
        assert evaluate_nudge(s) is not None


class TestModeDrift:
    def setup_method(self):
        _fresh_config()

    def test_explore_high_interactions(self):
        s = VibeSession()
        s.mode = "explore"
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=35)
        s.interaction_count = 60
        nudge = evaluate_nudge(s)
        assert nudge is not None
        assert "feel like building" in nudge

    def test_explore_low_interactions_no_drift(self):
        s = VibeSession()
        s.mode = "explore"
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=35)
        s.interaction_count = 10
        # Below time_check threshold (45min), so no mode duration nudge either
        assert evaluate_nudge(s) is None

    def test_ship_over_60min(self):
        s = VibeSession()
        s.mode = "ship"
        # 65min but below time_check (45min already fires mode duration)
        # Set mode_since past time_check so mode duration fires first
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=40)
        # Under time_check, so no mode duration nudge — check drift at 60min
        config.set_runtime("nudges.time_check_minutes", "120")  # disable mode duration
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=65)
        nudge = evaluate_nudge(s)
        assert nudge is not None
        assert "shipping" in nudge.lower()


class TestInteractionCount:
    def setup_method(self):
        _fresh_config()

    def test_high_interactions_no_switches(self):
        s = VibeSession()
        s.interaction_count = 110
        nudge = evaluate_nudge(s)
        assert nudge is not None
        assert "mode switch" in nudge

    def test_high_interactions_with_switches_no_nudge(self):
        s = VibeSession()
        s.interaction_count = 110
        s.set_mode("build")  # adds a transition
        assert evaluate_nudge(s) is None

    def test_below_threshold_no_nudge(self):
        s = VibeSession()
        s.interaction_count = 50
        assert evaluate_nudge(s) is None


class TestPriorityOrder:
    def setup_method(self):
        _fresh_config()

    def test_session_duration_before_mode_duration(self):
        """Session duration (rule 2) fires before mode duration (rule 3)."""
        s = VibeSession()
        s.started_at = datetime.now(timezone.utc) - timedelta(minutes=130)
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=50)
        nudge = evaluate_nudge(s)
        assert "step away" in nudge  # session duration, not mode duration

    def test_cooldown_suppresses_everything(self):
        """Cooldown (rule 1) blocks all other rules."""
        s = VibeSession()
        s.started_at = datetime.now(timezone.utc) - timedelta(minutes=130)
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=50)
        s.interaction_count = 200
        s.last_nudge_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        assert evaluate_nudge(s) is None


class TestRuleStructure:
    """Verify rules are well-formed data objects."""

    def test_five_rules_defined(self):
        assert len(RULES) == 5

    def test_rules_have_unique_names(self):
        names = [r.name for r in RULES]
        assert len(names) == len(set(names))

    def test_rules_have_unique_priorities(self):
        priorities = [r.priority for r in RULES]
        assert len(priorities) == len(set(priorities))

    def test_rule_types_valid(self):
        for r in RULES:
            assert r.rule_type in ("suppress", "nudge", "drift")

    def test_cooldown_has_no_defeaters(self):
        cooldown = [r for r in RULES if r.name == "cooldown_suppression"][0]
        assert cooldown.defeated_by == []

    def test_defeated_by_references_valid_rules(self):
        names = {r.name for r in RULES}
        for r in RULES:
            for d in r.defeated_by:
                assert d in names, f"{r.name} references unknown defeater: {d}"

    def test_defeated_by_only_references_higher_priority(self):
        priority_of = {r.name: r.priority for r in RULES}
        for r in RULES:
            for d in r.defeated_by:
                assert priority_of[d] < r.priority, (
                    f"{r.name} (pri {r.priority}) claims defeated by "
                    f"{d} (pri {priority_of[d]}) which is not higher priority"
                )


class TestGovernanceTrace:
    def setup_method(self):
        _fresh_config()

    def test_evaluate_rules_returns_tuple(self):
        s = VibeSession()
        result = evaluate_rules(s)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_trace_has_all_rules(self):
        s = VibeSession()
        _, trace = evaluate_rules(s)
        assert len(trace) == 5

    def test_trace_records_fired_rule(self):
        s = VibeSession()
        s.mode = "explore"
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=50)
        _, trace = evaluate_rules(s)
        mode_duration = [e for e in trace if e.rule_name == "mode_duration"][0]
        assert mode_duration.fired is True
        assert mode_duration.defeated is False

    def test_cooldown_defeats_other_rules(self):
        s = VibeSession()
        s.started_at = datetime.now(timezone.utc) - timedelta(minutes=130)
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=130)
        s.last_nudge_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        _, trace = evaluate_rules(s)
        cooldown = [e for e in trace if e.rule_name == "cooldown_suppression"][0]
        assert cooldown.fired is True
        session_dur = [e for e in trace if e.rule_name == "session_duration"][0]
        assert session_dur.fired is True
        assert session_dur.defeated is True
        assert session_dur.defeated_by == "cooldown_suppression"

    def test_no_rules_fired_trace(self):
        s = VibeSession()
        _, trace = evaluate_rules(s)
        assert all(not e.fired for e in trace)

    def test_backwards_compat_evaluate_nudge(self):
        """evaluate_nudge still works and returns same results."""
        s = VibeSession()
        s.mode = "explore"
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=50)
        nudge = evaluate_nudge(s)
        message, _ = evaluate_rules(s)
        assert nudge == message

    def test_rule_evaluation_to_dict(self):
        e = RuleEvaluation(
            rule_name="test_rule",
            fired=True,
            defeated=True,
            defeated_by="cooldown_suppression",
            message="test message",
        )
        d = e.to_dict()
        assert d["rule"] == "test_rule"
        assert d["fired"] is True
        assert d["defeated"] is True
        assert d["defeated_by"] == "cooldown_suppression"
        assert d["message"] == "test message"

    def test_rule_evaluation_to_dict_minimal(self):
        e = RuleEvaluation(rule_name="test", fired=False, defeated=False)
        d = e.to_dict()
        assert "defeated_by" not in d
        assert "message" not in d


class TestActiveDurationsInGovernor:
    """Governor should use active (not elapsed) durations, so idle gaps prevent false nudges."""

    def setup_method(self):
        _fresh_config()

    def test_overnight_session_no_nudge_when_active_time_short(self):
        """A 24h session with only 5min active should NOT trigger session duration nudge."""
        s = VibeSession()
        now = datetime.now(timezone.utc)
        s.started_at = now - timedelta(hours=24)
        s.mode_since = now - timedelta(hours=24)
        # 23h 55min idle gap
        s._idle_gaps.append(IdleGap(
            start=now - timedelta(hours=23, minutes=55),
            end=now,
        ))
        # Active session time: ~5 min (well under 120 min threshold)
        nudge = evaluate_nudge(s)
        assert nudge is None

    def test_long_active_session_still_nudges(self):
        """A 3h session with no idle gaps should still fire session duration nudge."""
        s = VibeSession()
        s.started_at = datetime.now(timezone.utc) - timedelta(hours=3)
        nudge = evaluate_nudge(s)
        assert nudge is not None
        assert "step away" in nudge

    def test_mode_duration_uses_active_time(self):
        """Mode duration nudge should not fire if most of mode time was idle."""
        s = VibeSession()
        now = datetime.now(timezone.utc)
        s.mode = "build"
        s.mode_since = now - timedelta(hours=2)
        # 1h 50min idle during build
        s._idle_gaps.append(IdleGap(
            start=now - timedelta(hours=1, minutes=50),
            end=now,
        ))
        # Active mode time: ~10 min (under 45 min threshold)
        nudge = evaluate_nudge(s)
        assert nudge is None

    def test_mode_duration_fires_when_active_time_exceeds_threshold(self):
        """Mode duration nudge fires when active time exceeds threshold."""
        s = VibeSession()
        now = datetime.now(timezone.utc)
        s.mode = "build"
        s.mode_since = now - timedelta(hours=2)
        # Only 30 min idle during build
        s._idle_gaps.append(IdleGap(
            start=now - timedelta(hours=1, minutes=30),
            end=now - timedelta(hours=1),
        ))
        # Active mode time: 2h - 0.5h = 1.5h (90 min, above 45 min threshold)
        nudge = evaluate_nudge(s)
        assert nudge is not None
        assert "build" in nudge


class TestFormatting:
    def test_format_none(self):
        msg = format_nudge_or_clear(None)
        assert "All clear" in msg

    def test_format_nudge(self):
        msg = format_nudge_or_clear("Take a break")
        assert "Take a break" in msg
        assert "Nudge" in msg
