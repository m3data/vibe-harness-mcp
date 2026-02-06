"""Tests for modes.py — mode definitions, validation, friction."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from modes import valid_modes, validate_mode, get_mode, get_friction, get_friction_message, default_mode


class TestModeDefinitions:
    def test_five_modes_defined(self):
        assert set(valid_modes()) == {"explore", "build", "think-with", "ship", "cool-off"}

    def test_validate_known_modes(self):
        for m in ["explore", "build", "think-with", "ship", "cool-off"]:
            assert validate_mode(m), f"{m} should be valid"

    def test_validate_unknown_mode(self):
        assert not validate_mode("sprint")
        assert not validate_mode("")

    def test_get_mode_returns_dict(self):
        mode = get_mode("build")
        assert mode is not None
        assert mode["name"] == "Build"
        assert "orientation" in mode
        assert "ai_behavior" in mode
        assert "emoji" in mode

    def test_get_mode_unknown_returns_none(self):
        assert get_mode("nonexistent") is None

    def test_default_mode_is_explore(self):
        assert default_mode() == "explore"

    def test_every_mode_has_required_fields(self):
        for m in valid_modes():
            mode = get_mode(m)
            assert "name" in mode, f"{m} missing name"
            assert "emoji" in mode, f"{m} missing emoji"
            assert "orientation" in mode, f"{m} missing orientation"
            assert "ai_behavior" in mode, f"{m} missing ai_behavior"
            assert isinstance(mode["ai_behavior"], list), f"{m} ai_behavior should be list"


class TestFriction:
    def test_same_mode_is_none(self):
        for m in valid_modes():
            assert get_friction(m, m) == "none"

    def test_explore_to_ship_is_high(self):
        assert get_friction("explore", "ship") == "high"

    def test_explore_to_build_is_none(self):
        assert get_friction("explore", "build") == "none"

    def test_build_to_explore_is_medium(self):
        assert get_friction("build", "explore") == "medium"

    def test_cool_off_to_ship_is_high(self):
        assert get_friction("cool-off", "ship") == "high"

    def test_any_to_cool_off_is_none(self):
        for m in valid_modes():
            if m != "cool-off":
                assert get_friction(m, "cool-off") == "none", f"{m}->cool-off should be none"

    def test_unknown_transition_defaults_none(self):
        assert get_friction("explore", "unknown") == "none"

    def test_friction_message_high(self):
        msg = get_friction_message("high", "explore", "ship")
        assert msg is not None
        assert "Explore" in msg
        assert "Ship" in msg

    def test_friction_message_medium(self):
        msg = get_friction_message("medium", "build", "explore")
        assert msg is not None

    def test_friction_message_none_returns_none(self):
        assert get_friction_message("none", "explore", "build") is None
