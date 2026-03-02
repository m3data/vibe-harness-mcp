"""Tests for formatters.py — output formatting for MCP tools."""

from datetime import datetime, timedelta, timezone

from vibe_harness_mcp.formatters import (
    format_mode_switch,
    format_vibe_check,
    format_status_line,
    format_history,
    format_nudge_output,
    format_ceremony_phase1,
    format_ceremony_phase2,
)
from vibe_harness_mcp.session import VibeSession


class TestFormatModeSwitch:
    def test_successful_switch(self):
        result = {
            "success": True,
            "mode": "build",
            "message": "Build.\n\nConcise, code-first.",
            "friction": "none",
            "awaiting_confirmation": False,
        }
        output = format_mode_switch(result)
        assert "Mode: Build" in output
        assert "Concise, code-first." in output

    def test_high_friction_warning(self):
        result = {
            "success": False,
            "mode": "explore",
            "message": "That's a big shift.",
            "friction": "high",
            "awaiting_confirmation": True,
        }
        output = format_mode_switch(result)
        assert "FRICTION" in output
        assert "big shift" in output

    def test_error(self):
        result = {
            "success": False,
            "mode": "explore",
            "message": "Unknown mode: 'sprint'",
            "friction": "none",
            "awaiting_confirmation": False,
        }
        output = format_mode_switch(result)
        assert "Error" in output


class TestFormatVibeCheck:
    def test_basic_output(self):
        s = VibeSession()
        output = format_vibe_check(s)
        assert "Mode: Explore" in output
        assert "mode" in output
        assert "session" in output
        assert "actions" in output
        assert "switches" in output

    def test_with_nudge(self):
        s = VibeSession()
        output = format_vibe_check(s, nudge="Take a break")
        assert "Nudge: Take a break" in output

    def test_without_nudge_no_nudge_section(self):
        s = VibeSession()
        output = format_vibe_check(s)
        assert "Nudge" not in output

    def test_shows_nudge_count(self):
        s = VibeSession()
        s.nudges_surfaced = 3
        output = format_vibe_check(s)
        assert "nudges" in output
        assert "3" in output

    def test_shows_pending_confirmation(self):
        s = VibeSession()
        s._pending_mode = "ship"
        output = format_vibe_check(s)
        assert "pending" in output
        assert "ship" in output

    def test_with_temporal_context(self):
        s = VibeSession()
        temporal = {
            "hour": 14,
            "minute": 30,
            "period": "afternoon",
            "is_late": False,
            "sessions_today": {"count": 2, "total_minutes": 90.0},
            "sessions_this_week": {"count": 5, "dominant_mode": "build", "mode_distribution": {}},
        }
        output = format_vibe_check(s, temporal=temporal)
        assert "14:30" in output
        assert "afternoon" in output
        assert "session #2" in output
        assert "~90min" in output


class TestFormatStatusLine:
    def test_contains_mode_and_stats(self):
        s = VibeSession()
        s.interaction_count = 5
        output = format_status_line(s)
        assert "Explore" in output
        assert "5 interactions" in output


class TestFormatHistory:
    def test_no_transitions(self):
        s = VibeSession()
        output = format_history(s)
        assert "No mode transitions" in output

    def test_with_transitions(self):
        s = VibeSession()
        s.set_mode("build")
        s.set_mode("ship")
        output = format_history(s)
        assert "Mode History" in output
        assert "explore" in output
        assert "build" in output
        assert "ship" in output

    def test_time_in_mode_summary(self):
        s = VibeSession()
        s.started_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        s.set_mode("build")
        output = format_history(s)
        assert "Time in Mode" in output


class TestFormatNudgeOutput:
    def test_no_nudge(self):
        output = format_nudge_output(None)
        assert "All clear" in output

    def test_with_nudge(self):
        output = format_nudge_output("Time to rest")
        assert "Nudge: Time to rest" in output


class TestFormatCeremonyPhase1:
    def test_somatic_content(self):
        output = format_ceremony_phase1()
        assert "notice how your body feels" in output
        assert "Shoulders" in output
        assert "Jaw" in output
        assert "Breath" in output

    def test_ai_directive(self):
        output = format_ceremony_phase1()
        assert "FOR THE AI" in output
        assert "somatic grounding" in output
        assert "Do not explain what Vibe Harness is yet" in output

    def test_no_mode_list(self):
        output = format_ceremony_phase1()
        assert "Five modes" not in output
        assert "pull-only" not in output

    def test_late_night_temporal(self):
        temporal = {
            "hour": 23,
            "minute": 30,
            "period": "late_night",
            "is_late": True,
            "sessions_today": {"count": 0, "total_minutes": 0},
            "sessions_this_week": {"count": 0, "dominant_mode": None, "mode_distribution": {}},
        }
        output = format_ceremony_phase1(temporal=temporal)
        assert "23:00" in output
        assert "circadian" in output

    def test_early_morning_temporal(self):
        temporal = {
            "hour": 4,
            "minute": 0,
            "period": "early_morning",
            "is_late": True,
            "sessions_today": {"count": 0, "total_minutes": 0},
            "sessions_this_week": {"count": 0, "dominant_mode": None, "mode_distribution": {}},
        }
        output = format_ceremony_phase1(temporal=temporal)
        assert "Early morning" in output

    def test_daytime_no_time_warning(self):
        temporal = {
            "hour": 10,
            "minute": 0,
            "period": "morning",
            "is_late": False,
            "sessions_today": {"count": 0, "total_minutes": 0},
            "sessions_this_week": {"count": 0, "dominant_mode": None, "mode_distribution": {}},
        }
        output = format_ceremony_phase1(temporal=temporal)
        assert "circadian" not in output
        assert "Early morning" not in output


class TestFormatCeremonyPhase2:
    def test_orientation_content(self):
        output = format_ceremony_phase2()
        assert "pull-only" in output
        assert "Vibe Harness" in output

    def test_mode_list(self):
        output = format_ceremony_phase2()
        assert "Explore" in output
        assert "Build" in output
        assert "Think-With" in output
        assert "Ship" in output
        assert "Cool-Off" in output

    def test_ai_directive(self):
        output = format_ceremony_phase2()
        assert "FOR THE AI" in output
        assert "Ask the human which mode" in output
        assert "vibe_set_mode" in output

    def test_no_somatic_content(self):
        output = format_ceremony_phase2()
        assert "Shoulders" not in output
        assert "Jaw" not in output
