"""Tests for session.py — VibeSession state management."""

import json
from datetime import datetime, timedelta, timezone

from vibe_harness_mcp import config
from vibe_harness_mcp.session import VibeSession, ModeTransition, IdleGap, EXPORT_SCHEMA_VERSION


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

    def test_is_returning_user_snapshot(self):
        """First session with no history is first-use; the session-start write
        creates the file, so the next session is correctly a returning user.
        Snapshotted before the write so it stays a true first-use signal."""
        s1 = VibeSession()
        assert s1._is_returning_user is False  # empty history dir under isolation
        s2 = VibeSession()
        assert s2._is_returning_user is True  # s1's session-start created the file


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


class TestInteractionsSinceSwitch:
    def test_no_transitions(self):
        s = VibeSession()
        s.record_interaction()
        s.record_interaction()
        assert s.interactions_since_last_switch() == 2

    def test_resets_on_switch(self):
        s = VibeSession()
        for _ in range(5):
            s.record_interaction()
        s.set_mode("build")
        assert s.interactions_since_last_switch() == 0

    def test_counts_after_switch(self):
        s = VibeSession()
        for _ in range(5):
            s.record_interaction()
        s.set_mode("build")
        s.record_interaction()
        s.record_interaction()
        assert s.interactions_since_last_switch() == 2

    def test_multiple_switches(self):
        s = VibeSession()
        for _ in range(3):
            s.record_interaction()
        s.set_mode("build")
        for _ in range(4):
            s.record_interaction()
        s.set_mode("think-with")
        s.record_interaction()
        assert s.interactions_since_last_switch() == 1
        assert s.interaction_count == 8  # total preserved


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
        assert data["schema_version"] == EXPORT_SCHEMA_VERSION
        assert data["session_id"] == s.session_id
        assert data["current_mode"] == "build"
        assert "started_at" in data
        assert "exported_at" in data
        assert "duration_minutes" in data
        assert "active_duration_minutes" in data
        assert "idle_gaps" in data
        assert "transitions" in data
        assert "time_in_mode" in data
        assert len(data["transitions"]) == 1
        assert "governance_trace" in data
        assert isinstance(data["governance_trace"], list)


class TestGovernanceTrace:
    def test_record_governance_evaluation(self):
        s = VibeSession()
        evaluations = [
            {"rule": "cooldown_suppression", "fired": False, "defeated": False},
            {"rule": "session_duration", "fired": True, "defeated": False, "message": "test"},
        ]
        s.record_governance_evaluation(evaluations)
        assert len(s.governance_trace) == 1
        assert s.governance_trace[0]["evaluations"] == evaluations
        assert "timestamp" in s.governance_trace[0]

    def test_multiple_evaluations_append(self):
        s = VibeSession()
        s.record_governance_evaluation([{"rule": "a", "fired": False, "defeated": False}])
        s.record_governance_evaluation([{"rule": "b", "fired": True, "defeated": False}])
        assert len(s.governance_trace) == 2

    def test_governance_trace_in_export(self):
        s = VibeSession()
        s.record_governance_evaluation([{"rule": "test", "fired": True, "defeated": False}])
        data = s.to_export_dict()
        assert len(data["governance_trace"]) == 1

    def test_ceremony_phase_default_zero(self):
        s = VibeSession()
        assert s._ceremony_phase == 0


class TestCeremonyState:
    def test_initial_phase_is_zero(self):
        s = VibeSession()
        assert s._ceremony_phase == 0
        assert s.ceremony_active() is True

    def test_advance_from_zero_to_one(self):
        s = VibeSession()
        phase = s.advance_ceremony()
        assert phase == 0
        assert s._ceremony_phase == 1
        assert s.ceremony_active() is True

    def test_advance_from_one_to_none(self):
        s = VibeSession()
        s.advance_ceremony()  # 0 -> 1
        phase = s.advance_ceremony()  # 1 -> None
        assert phase == 1
        assert s._ceremony_phase is None
        assert s.ceremony_active() is False

    def test_advance_past_none_returns_none(self):
        s = VibeSession()
        s.advance_ceremony()  # 0 -> 1
        s.advance_ceremony()  # 1 -> None
        phase = s.advance_ceremony()  # None -> None
        assert phase is None
        assert s._ceremony_phase is None

    def test_ceremony_not_needed(self):
        """When phase is set to None (returning user), ceremony is inactive."""
        s = VibeSession()
        s._ceremony_phase = None
        assert s.ceremony_active() is False
        assert s.advance_ceremony() is None


class TestJSONLLogging:
    def test_session_start_writes_jsonl(self):
        if config.history_file().exists():
            before = len(config.history_file().read_text().strip().split("\n"))
        else:
            before = 0

        s = VibeSession()

        lines = config.history_file().read_text().strip().split("\n")
        new_lines = lines[before:]
        assert len(new_lines) == 1

        entry = json.loads(new_lines[0])
        assert entry["from_mode"] == "session-start"
        assert entry["to_mode"] == "explore"
        assert entry["session_id"] == s.session_id

    def test_transition_writes_jsonl(self):
        if config.history_file().exists():
            before = len(config.history_file().read_text().strip().split("\n"))
        else:
            before = 0

        s = VibeSession()
        s.set_mode("build")

        lines = config.history_file().read_text().strip().split("\n")
        new_lines = lines[before:]
        # session-start + explore→build
        assert len(new_lines) == 2

        entry = json.loads(new_lines[1])
        assert entry["from_mode"] == "explore"
        assert entry["to_mode"] == "build"
        assert entry["session_id"] == s.session_id
        assert "timestamp" in entry
        assert "friction" in entry

    def test_high_friction_logs_only_on_confirm(self):
        s = VibeSession()

        # Baseline after session-start line
        if config.history_file().exists():
            before = len(config.history_file().read_text().strip().split("\n"))
        else:
            before = 0

        s.set_mode("ship")  # pending — no log yet

        if config.history_file().exists():
            after_pending = len(config.history_file().read_text().strip().split("\n"))
        else:
            after_pending = 0
        assert after_pending == before  # no new line

        s.set_mode("ship")  # confirm — logs now

        lines = config.history_file().read_text().strip().split("\n")
        after_confirm = len(lines)
        assert after_confirm == before + 1

    def test_session_start_does_not_pollute_in_memory_transitions(self):
        """Guard: session-start is file-only — it must not enter self.transitions,
        so spans/time-in-mode and the history formatter never see it as a mode."""
        s = VibeSession()
        # Nothing in the in-memory list yet — session-start went to the file only.
        assert s.transitions == []
        summary = s.time_in_mode_summary()
        assert "session-start" not in summary
        assert summary == {"explore": summary["explore"]}

        s.set_mode("build")
        # The opening span is attributed to the real starting mode, not session-start.
        summary = s.time_in_mode_summary()
        assert "session-start" not in summary
        assert set(summary.keys()) == {"explore", "build"}


class TestIdleGapDetection:
    def setup_method(self):
        config._runtime_overrides.clear()

    def test_no_gap_on_first_interaction(self):
        s = VibeSession()
        s.record_interaction()
        assert len(s._idle_gaps) == 0
        assert s.last_interaction_at is not None

    def test_short_gap_not_recorded(self):
        s = VibeSession()
        now = datetime.now(timezone.utc)
        s.last_interaction_at = now - timedelta(minutes=5)
        s.record_interaction()
        assert len(s._idle_gaps) == 0

    def test_gap_above_threshold_recorded(self):
        s = VibeSession()
        now = datetime.now(timezone.utc)
        s.last_interaction_at = now - timedelta(minutes=45)
        s.record_interaction()
        assert len(s._idle_gaps) == 1
        gap = s._idle_gaps[0]
        assert gap.duration_seconds >= 45 * 60 - 1  # allow tiny rounding

    def test_gap_at_exact_threshold_recorded(self):
        s = VibeSession()
        now = datetime.now(timezone.utc)
        s.last_interaction_at = now - timedelta(minutes=30)
        s.record_interaction()
        assert len(s._idle_gaps) == 1

    def test_gap_just_below_threshold_not_recorded(self):
        s = VibeSession()
        now = datetime.now(timezone.utc)
        s.last_interaction_at = now - timedelta(minutes=29, seconds=59)
        s.record_interaction()
        assert len(s._idle_gaps) == 0

    def test_multiple_idle_gaps(self):
        s = VibeSession()
        now = datetime.now(timezone.utc)
        # First interaction
        s.last_interaction_at = now - timedelta(hours=3)
        # Simulate a 1-hour gap
        s.last_interaction_at = now - timedelta(hours=3)
        gap1_end = now - timedelta(hours=2)
        s._idle_gaps.append(IdleGap(start=s.last_interaction_at, end=gap1_end))
        s.last_interaction_at = gap1_end
        # Another 1-hour gap
        s.last_interaction_at = now - timedelta(hours=1, minutes=30)
        gap2_start = s.last_interaction_at
        s.record_interaction()  # this is ~90 min after gap1_end; last_interaction_at was set manually
        # Actually, let me test more carefully
        assert len(s._idle_gaps) >= 2

    def test_configurable_threshold(self):
        config.set_runtime("activity.idle_threshold_minutes", "10")
        s = VibeSession()
        now = datetime.now(timezone.utc)
        s.last_interaction_at = now - timedelta(minutes=15)
        s.record_interaction()
        assert len(s._idle_gaps) == 1


class TestActiveDurations:
    def test_no_gaps_active_equals_elapsed(self):
        s = VibeSession()
        s.started_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        s.mode_since = datetime.now(timezone.utc) - timedelta(minutes=10)
        assert abs(s.active_session_minutes() - s.session_duration_minutes()) < 0.1
        assert abs(s.active_mode_minutes() - s.mode_duration_minutes()) < 0.1

    def test_active_session_subtracts_idle(self):
        s = VibeSession()
        now = datetime.now(timezone.utc)
        s.started_at = now - timedelta(hours=10)
        s.mode_since = now - timedelta(hours=10)
        # Add a 9-hour idle gap
        s._idle_gaps.append(IdleGap(
            start=now - timedelta(hours=9, minutes=30),
            end=now - timedelta(minutes=30),
        ))
        # 10h elapsed - 9h idle = ~1h active
        active = s.active_session_minutes()
        assert 55 <= active <= 65

    def test_active_mode_only_counts_gaps_after_mode_since(self):
        s = VibeSession()
        now = datetime.now(timezone.utc)
        s.started_at = now - timedelta(hours=5)
        s.mode_since = now - timedelta(hours=1)
        # Add a gap that happened BEFORE mode_since — should not affect active mode minutes
        s._idle_gaps.append(IdleGap(
            start=now - timedelta(hours=4),
            end=now - timedelta(hours=3),
        ))
        # Mode is 60 min, no gaps after mode_since
        assert abs(s.active_mode_minutes() - 60) < 1

    def test_active_mode_subtracts_gap_after_mode_since(self):
        s = VibeSession()
        now = datetime.now(timezone.utc)
        s.started_at = now - timedelta(hours=5)
        s.mode_since = now - timedelta(hours=2)
        # Add a 1-hour gap that falls after mode_since
        s._idle_gaps.append(IdleGap(
            start=now - timedelta(hours=1, minutes=30),
            end=now - timedelta(minutes=30),
        ))
        # 2h elapsed - 1h idle = ~1h active
        active = s.active_mode_minutes()
        assert 55 <= active <= 65

    def test_gap_straddling_mode_since_partially_counted(self):
        s = VibeSession()
        now = datetime.now(timezone.utc)
        s.started_at = now - timedelta(hours=5)
        s.mode_since = now - timedelta(hours=2)
        # Gap that starts before mode_since and ends after
        s._idle_gaps.append(IdleGap(
            start=now - timedelta(hours=3),
            end=now - timedelta(hours=1),
        ))
        # Mode is 2h. Gap overlaps with 1h of it (from mode_since to gap.end).
        # Active = 2h - 1h = 1h
        active = s.active_mode_minutes()
        assert 55 <= active <= 65

    def test_total_idle_minutes(self):
        s = VibeSession()
        now = datetime.now(timezone.utc)
        s.started_at = now - timedelta(hours=5)
        s._idle_gaps.append(IdleGap(
            start=now - timedelta(hours=4),
            end=now - timedelta(hours=3),
        ))
        s._idle_gaps.append(IdleGap(
            start=now - timedelta(hours=2),
            end=now - timedelta(hours=1),
        ))
        idle = s.total_idle_minutes()
        assert 115 <= idle <= 125  # ~2 hours

    def test_active_never_negative(self):
        s = VibeSession()
        now = datetime.now(timezone.utc)
        s.started_at = now - timedelta(minutes=10)
        s.mode_since = now - timedelta(minutes=10)
        # Idle gap longer than elapsed (shouldn't happen normally, but guard)
        s._idle_gaps.append(IdleGap(
            start=now - timedelta(minutes=15),
            end=now,
        ))
        assert s.active_session_minutes() >= 0
        assert s.active_mode_minutes() >= 0


class TestContinuousActiveMinutes:
    """continuous_active_minutes() = the current unbroken stretch; a real break resets it."""

    def test_no_gaps_equals_session_duration(self):
        s = VibeSession()
        s.started_at = datetime.now(timezone.utc) - timedelta(minutes=90)
        # No breaks → the whole session is one unbroken stretch.
        assert abs(s.continuous_active_minutes() - 90) < 1

    def test_resets_after_a_break(self):
        s = VibeSession()
        now = datetime.now(timezone.utc)
        s.started_at = now - timedelta(hours=5)
        # A 40-min break that ended 20 min ago.
        s._idle_gaps.append(IdleGap(
            start=now - timedelta(minutes=60),
            end=now - timedelta(minutes=20),
        ))
        # The stretch is 20 min (since the break ended), not the 5h cumulative.
        assert abs(s.continuous_active_minutes() - 20) < 1
        # And it is strictly less than cumulative active time.
        assert s.continuous_active_minutes() < s.active_session_minutes()

    def test_uses_most_recent_break(self):
        s = VibeSession()
        now = datetime.now(timezone.utc)
        s.started_at = now - timedelta(hours=8)
        s._idle_gaps.append(IdleGap(
            start=now - timedelta(hours=6), end=now - timedelta(hours=5),
        ))
        s._idle_gaps.append(IdleGap(
            start=now - timedelta(hours=3), end=now - timedelta(minutes=45),
        ))
        # Most recent break ended 45 min ago — that anchors the stretch.
        assert abs(s.continuous_active_minutes() - 45) < 1

    def test_never_negative(self):
        s = VibeSession()
        now = datetime.now(timezone.utc)
        s.started_at = now - timedelta(minutes=10)
        s._idle_gaps.append(IdleGap(start=now - timedelta(minutes=5), end=now))
        assert s.continuous_active_minutes() >= 0


class TestTimeInModeSummaryWithIdleGaps:
    def test_single_mode_subtracts_idle(self):
        s = VibeSession()
        now = datetime.now(timezone.utc)
        s.started_at = now - timedelta(hours=10)
        s._idle_gaps.append(IdleGap(
            start=now - timedelta(hours=9),
            end=now - timedelta(hours=1),
        ))
        summary = s.time_in_mode_summary()
        # 10h elapsed - 8h idle = ~2h active
        assert summary["explore"] < 150  # well under 10h

    def test_multi_mode_idle_gap_attributed_correctly(self):
        s = VibeSession()
        now = datetime.now(timezone.utc)
        s.started_at = now - timedelta(hours=4)
        # Explore for 1h, then switch to build
        transition_time = now - timedelta(hours=3)
        s.transitions.append(ModeTransition(
            from_mode="explore", to_mode="build",
            timestamp=transition_time, friction="none", confirmed=True,
        ))
        s.mode = "build"
        s.mode_since = transition_time
        # 2-hour idle gap falls entirely in build span
        s._idle_gaps.append(IdleGap(
            start=now - timedelta(hours=2, minutes=30),
            end=now - timedelta(minutes=30),
        ))
        summary = s.time_in_mode_summary()
        # Explore: 1h (no gaps), Build: 3h - 2h = 1h
        assert 55 <= summary["explore"] <= 65
        assert 55 <= summary["build"] <= 65


class TestIdleGapInExport:
    def test_idle_gaps_in_export(self):
        s = VibeSession()
        now = datetime.now(timezone.utc)
        s.started_at = now - timedelta(hours=2)
        s._idle_gaps.append(IdleGap(
            start=now - timedelta(hours=1, minutes=30),
            end=now - timedelta(minutes=30),
        ))
        data = s.to_export_dict()
        assert len(data["idle_gaps"]) == 1
        assert "start" in data["idle_gaps"][0]
        assert "end" in data["idle_gaps"][0]
        assert "duration_minutes" in data["idle_gaps"][0]
        assert data["active_duration_minutes"] < data["duration_minutes"]

    def test_no_idle_gaps_export(self):
        s = VibeSession()
        data = s.to_export_dict()
        assert data["idle_gaps"] == []
        assert abs(data["active_duration_minutes"] - data["duration_minutes"]) < 0.2
