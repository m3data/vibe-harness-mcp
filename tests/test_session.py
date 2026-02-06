"""Tests for session.py — VibeSession state management."""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from session import VibeSession, ModeTransition, HISTORY_FILE


class TestSessionInit:
    def test_defaults(self):
        s = VibeSession()
        assert s.mode == "explore"
        assert s.interaction_count == 0
        assert s.transitions == []
        assert s.nudges_surfaced == 0
        assert s.last_nudge_at is None
        assert s._pending_mode is None

    def test_session_id_generated(self):
        s1 = VibeSession()
        s2 = VibeSession()
        assert len(s1.session_id) == 12
        assert s1.session_id != s2.session_id


class TestInteractions:
    def test_record_interaction(self):
        s = VibeSession()
        assert s.interaction_count == 0
        s.record_interaction()
        assert s.interaction_count == 1
        s.record_interaction()
        assert s.interaction_count == 2


class TestModeSwitch:
    def test_basic_switch(self):
        s = VibeSession()
        result = s.set_mode("build")
        assert result["success"]
        assert result["mode"] == "build"
        assert s.mode == "build"
        assert len(s.transitions) == 1

    def test_same_mode_noop(self):
        s = VibeSession()
        result = s.set_mode("explore")
        assert result["success"]
        assert result["mode"] == "explore"
        assert len(s.transitions) == 0

    def test_invalid_mode(self):
        s = VibeSession()
        result = s.set_mode("sprint")
        assert not result["success"]
        assert s.mode == "explore"

    def test_high_friction_requires_confirmation(self):
        s = VibeSession()
        # explore -> ship is high friction
        result = s.set_mode("ship")
        assert not result["success"]
        assert result["awaiting_confirmation"]
        assert result["friction"] == "high"
        assert s.mode == "explore"  # not switched yet
        assert s._pending_mode == "ship"

    def test_high_friction_confirm(self):
        s = VibeSession()
        s.set_mode("ship")  # first call — friction warning
        result = s.set_mode("ship")  # second call — confirms
        assert result["success"]
        assert result["mode"] == "ship"
        assert s.mode == "ship"

    def test_high_friction_cancel_by_different_mode(self):
        s = VibeSession()
        s.set_mode("ship")  # pending
        result = s.set_mode("build")  # different mode cancels pending
        assert result["success"]
        assert result["mode"] == "build"
        assert s._pending_mode is None

    def test_medium_friction_proceeds(self):
        s = VibeSession()
        s.set_mode("build")  # explore -> build (none)
        result = s.set_mode("explore")  # build -> explore (medium)
        assert result["success"]
        assert result["mode"] == "explore"

    def test_transition_recorded(self):
        s = VibeSession()
        s.set_mode("build")
        t = s.transitions[0]
        assert t.from_mode == "explore"
        assert t.to_mode == "build"
        assert t.friction == "none"
        assert t.confirmed


class TestDurations:
    def test_mode_duration(self):
        s = VibeSession()
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=10)
        assert 9.9 <= s.mode_duration_minutes() <= 10.1

    def test_session_duration(self):
        s = VibeSession()
        s.started_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        assert 29.9 <= s.session_duration_minutes() <= 30.1

    def test_time_in_mode_summary_no_transitions(self):
        s = VibeSession()
        summary = s.time_in_mode_summary()
        assert "explore" in summary

    def test_time_in_mode_summary_with_transitions(self):
        s = VibeSession()
        s.started_at = datetime.now(timezone.utc) - timedelta(minutes=20)
        s.set_mode("build")
        summary = s.time_in_mode_summary()
        assert "explore" in summary
        assert "build" in summary


class TestExport:
    def test_export_dict_schema(self):
        s = VibeSession()
        s.set_mode("build")
        data = s.to_export_dict()
        assert data["schema_version"] == "0.1.0"
        assert data["session_id"] == s.session_id
        assert data["current_mode"] == "build"
        assert "started_at" in data
        assert "exported_at" in data
        assert "duration_minutes" in data
        assert "transitions" in data
        assert "time_in_mode" in data
        assert len(data["transitions"]) == 1


class TestJSONLLogging:
    def test_transition_writes_jsonl(self):
        # Count existing lines
        if HISTORY_FILE.exists():
            before = len(HISTORY_FILE.read_text().strip().split("\n"))
        else:
            before = 0

        s = VibeSession()
        s.set_mode("build")

        lines = HISTORY_FILE.read_text().strip().split("\n")
        new_lines = lines[before:]
        assert len(new_lines) == 1

        entry = json.loads(new_lines[0])
        assert entry["from_mode"] == "explore"
        assert entry["to_mode"] == "build"
        assert entry["session_id"] == s.session_id
        assert "timestamp" in entry
        assert "friction" in entry

    def test_high_friction_logs_only_on_confirm(self):
        if HISTORY_FILE.exists():
            before = len(HISTORY_FILE.read_text().strip().split("\n"))
        else:
            before = 0

        s = VibeSession()
        s.set_mode("ship")  # pending — no log yet

        if HISTORY_FILE.exists():
            after_pending = len(HISTORY_FILE.read_text().strip().split("\n"))
        else:
            after_pending = 0
        assert after_pending == before  # no new line

        s.set_mode("ship")  # confirm — logs now

        lines = HISTORY_FILE.read_text().strip().split("\n")
        after_confirm = len(lines)
        assert after_confirm == before + 1
