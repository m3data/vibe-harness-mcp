"""Tests for temporal.py — clock time and cross-session pattern mining."""

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from vibe_harness_mcp import config
from vibe_harness_mcp.temporal import (
    _get_period,
    _is_late_hour,
    _load_history,
    _group_sessions,
    _sessions_on_date,
    _sessions_in_week,
    get_temporal_context,
    HISTORY_FILE,
)


class TestPeriods:
    def test_early_morning(self):
        for h in range(0, 6):
            assert _get_period(h) == "early_morning", f"hour {h}"

    def test_morning(self):
        for h in range(6, 12):
            assert _get_period(h) == "morning", f"hour {h}"

    def test_afternoon(self):
        for h in range(12, 17):
            assert _get_period(h) == "afternoon", f"hour {h}"

    def test_evening(self):
        for h in range(17, 22):
            assert _get_period(h) == "evening", f"hour {h}"

    def test_late_night(self):
        for h in range(22, 24):
            assert _get_period(h) == "late_night", f"hour {h}"


class TestIsLateHour:
    def setup_method(self):
        config._runtime_overrides.clear()

    def test_default_late_hours(self):
        # 22-06 is late by default
        assert _is_late_hour(22) is True
        assert _is_late_hour(23) is True
        assert _is_late_hour(0) is True
        assert _is_late_hour(3) is True
        assert _is_late_hour(5) is True

    def test_default_not_late_hours(self):
        assert _is_late_hour(6) is False
        assert _is_late_hour(12) is False
        assert _is_late_hour(18) is False
        assert _is_late_hour(21) is False

    def test_configurable_late_hours(self):
        config.set_runtime("temporal.late_night_start", "20")
        config.set_runtime("temporal.late_night_end", "8")
        assert _is_late_hour(20) is True
        assert _is_late_hour(7) is True
        assert _is_late_hour(8) is False
        assert _is_late_hour(19) is False


class TestGroupSessions:
    def test_empty_entries(self):
        assert _group_sessions([]) == []

    def test_single_session(self):
        entries = [
            {"session_id": "abc", "timestamp": "2026-03-03T10:00:00+00:00", "to_mode": "build"},
            {"session_id": "abc", "timestamp": "2026-03-03T11:00:00+00:00", "to_mode": "ship"},
        ]
        sessions = _group_sessions(entries)
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == "abc"
        assert sessions[0]["duration_minutes"] == 60.0
        assert sessions[0]["dominant_mode"] in ("build", "ship")

    def test_multiple_sessions(self):
        entries = [
            {"session_id": "aaa", "timestamp": "2026-03-03T09:00:00+00:00", "to_mode": "explore"},
            {"session_id": "bbb", "timestamp": "2026-03-03T14:00:00+00:00", "to_mode": "build"},
        ]
        sessions = _group_sessions(entries)
        assert len(sessions) == 2

    def test_missing_session_id_skipped(self):
        entries = [
            {"timestamp": "2026-03-03T10:00:00+00:00", "to_mode": "build"},
        ]
        sessions = _group_sessions(entries)
        assert len(sessions) == 0

    def test_bad_timestamp_skipped(self):
        entries = [
            {"session_id": "abc", "timestamp": "not-a-date", "to_mode": "build"},
        ]
        sessions = _group_sessions(entries)
        assert len(sessions) == 0


class TestTemporalContext:
    def setup_method(self):
        config._runtime_overrides.clear()

    def test_basic_context_structure(self):
        now = datetime(2026, 3, 3, 14, 30, tzinfo=timezone.utc)
        ctx = get_temporal_context(now=now)
        assert "hour" in ctx
        assert "minute" in ctx
        assert "period" in ctx
        assert "is_late" in ctx
        assert "sessions_today" in ctx
        assert "sessions_this_week" in ctx
        assert "count" in ctx["sessions_today"]
        assert "total_minutes" in ctx["sessions_today"]
        assert "count" in ctx["sessions_this_week"]
        assert "dominant_mode" in ctx["sessions_this_week"]

    def test_late_night_detection(self):
        # 23:00 UTC
        now = datetime(2026, 3, 3, 23, 0, tzinfo=timezone.utc)
        ctx = get_temporal_context(now=now)
        # Whether this is "late" depends on local timezone conversion
        # but the structure should be present
        assert isinstance(ctx["is_late"], bool)

    def test_period_not_empty(self):
        now = datetime(2026, 3, 3, 10, 0, tzinfo=timezone.utc)
        ctx = get_temporal_context(now=now)
        assert ctx["period"] in ("early_morning", "morning", "afternoon", "evening", "late_night")


class TestLateNightGovernorRule:
    """Test the late_night governor rule via the full evaluate_rules path."""

    def setup_method(self):
        config._runtime_overrides.clear()

    def test_late_night_rule_fires(self):
        from vibe_harness_mcp.governor import evaluate_rules
        from vibe_harness_mcp.session import VibeSession

        s = VibeSession()
        # Mock temporal to return is_late=True
        mock_temporal = {
            "hour": 23, "minute": 0, "period": "late_night", "is_late": True,
            "sessions_today": {"count": 0, "total_minutes": 0},
            "sessions_this_week": {"count": 0, "dominant_mode": None, "mode_distribution": {}},
        }
        with patch("vibe_harness_mcp.governor.get_temporal_context", return_value=mock_temporal):
            nudge, trace = evaluate_rules(s)
        assert nudge is not None
        assert "circadian" in nudge
        late_rule = [e for e in trace if e.rule_name == "late_night"][0]
        assert late_rule.fired is True

    def test_late_night_rule_does_not_fire_daytime(self):
        from vibe_harness_mcp.governor import evaluate_rules
        from vibe_harness_mcp.session import VibeSession

        s = VibeSession()
        mock_temporal = {
            "hour": 14, "minute": 0, "period": "afternoon", "is_late": False,
            "sessions_today": {"count": 0, "total_minutes": 0},
            "sessions_this_week": {"count": 0, "dominant_mode": None, "mode_distribution": {}},
        }
        with patch("vibe_harness_mcp.governor.get_temporal_context", return_value=mock_temporal):
            nudge, trace = evaluate_rules(s)
        late_rule = [e for e in trace if e.rule_name == "late_night"][0]
        assert late_rule.fired is False

    def test_late_night_defeated_by_higher_priority(self):
        from vibe_harness_mcp.governor import evaluate_rules
        from vibe_harness_mcp.session import VibeSession

        s = VibeSession()
        s.started_at = datetime.now(timezone.utc) - timedelta(minutes=130)
        mock_temporal = {
            "hour": 23, "minute": 0, "period": "late_night", "is_late": True,
            "sessions_today": {"count": 0, "total_minutes": 0},
            "sessions_this_week": {"count": 0, "dominant_mode": None, "mode_distribution": {}},
        }
        with patch("vibe_harness_mcp.governor.get_temporal_context", return_value=mock_temporal):
            nudge, trace = evaluate_rules(s)
        # Session duration (priority 2) should win over late_night (priority 6)
        assert "step away" in nudge
        late_rule = [e for e in trace if e.rule_name == "late_night"][0]
        assert late_rule.fired is True
        assert late_rule.defeated is True

    def test_early_morning_message(self):
        from vibe_harness_mcp.governor import _late_night_msg

        state = {
            "temporal": {"hour": 4, "period": "early_morning", "is_late": True},
        }
        msg = _late_night_msg(state)
        assert "04:00" in msg
        assert "Early morning" in msg
