"""Tests for governor.py — nudge evaluation logic."""

import importlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from governor import evaluate_nudge, format_nudge_or_clear
from session import VibeSession


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
        assert "cool-off" in nudge

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
        assert "exploring" in nudge
        assert "build" in nudge.lower()

    def test_build_duration_nudge(self):
        s = VibeSession()
        s.mode = "build"
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=50)
        nudge = evaluate_nudge(s)
        assert "Building" in nudge

    def test_think_with_duration_nudge(self):
        s = VibeSession()
        s.mode = "think-with"
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=50)
        nudge = evaluate_nudge(s)
        assert "crystallised" in nudge

    def test_ship_duration_nudge(self):
        s = VibeSession()
        s.mode = "ship"
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=50)
        nudge = evaluate_nudge(s)
        assert "Shipping" in nudge

    def test_cool_off_duration_nudge(self):
        s = VibeSession()
        s.mode = "cool-off"
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=50)
        nudge = evaluate_nudge(s)
        assert "cooling off" in nudge

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
        assert "building without naming" in nudge

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
        assert "build" in nudge.lower()


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
        assert "cool-off" in nudge  # session duration, not mode duration

    def test_cooldown_suppresses_everything(self):
        """Cooldown (rule 1) blocks all other rules."""
        s = VibeSession()
        s.started_at = datetime.now(timezone.utc) - timedelta(minutes=130)
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=50)
        s.interaction_count = 200
        s.last_nudge_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        assert evaluate_nudge(s) is None


class TestFormatting:
    def test_format_none(self):
        msg = format_nudge_or_clear(None)
        assert "All clear" in msg

    def test_format_nudge(self):
        msg = format_nudge_or_clear("Take a break")
        assert "Take a break" in msg
        assert "Nudge" in msg
