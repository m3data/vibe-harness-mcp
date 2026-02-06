"""Tests for formatters.py — output formatting for MCP tools."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from formatters import (
    format_mode_switch,
    format_vibe_check,
    format_status_line,
    format_history,
    format_nudge_output,
    MODE_BANNERS,
    FRICTION_BANNER,
    NUDGE_BANNER,
)
from session import VibeSession


class TestBanners:
    def test_all_modes_have_banners(self):
        for mode in ["explore", "build", "think-with", "ship", "cool-off"]:
            assert mode in MODE_BANNERS, f"Missing banner for {mode}"

    def test_banners_use_mode_character(self):
        chars = {"explore": "~", "build": ">", "think-with": "?", "ship": "!", "cool-off": "."}
        for mode, char in chars.items():
            assert char in MODE_BANNERS[mode]


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
        assert ">>>" in output
        assert "Build" in output

    def test_high_friction_warning(self):
        result = {
            "success": False,
            "mode": "explore",
            "message": "That's a big shift.",
            "friction": "high",
            "awaiting_confirmation": True,
        }
        output = format_mode_switch(result)
        assert "F R I C T I O N" in output
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
        assert "E X P L O R E" in output
        assert "mode" in output
        assert "session" in output
        assert "actions" in output
        assert "switches" in output

    def test_with_nudge(self):
        s = VibeSession()
        output = format_vibe_check(s, nudge="Take a break")
        assert "N U D G E" in output
        assert "Take a break" in output

    def test_without_nudge_no_nudge_section(self):
        s = VibeSession()
        output = format_vibe_check(s)
        assert "N U D G E" not in output

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
        assert "M O D E   H I S T O R Y" in output
        assert "explore" in output
        assert "build" in output
        assert "ship" in output
        assert "───>" in output

    def test_time_in_mode_bars(self):
        s = VibeSession()
        s.started_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        s.set_mode("build")
        output = format_history(s)
        assert "T I M E   I N   M O D E" in output


class TestFormatNudgeOutput:
    def test_no_nudge(self):
        output = format_nudge_output(None)
        assert "All clear" in output

    def test_with_nudge(self):
        output = format_nudge_output("Time to rest")
        assert "N U D G E" in output
        assert "Time to rest" in output
