"""Integration tests for the onboarding ceremony flow through server.py.

Ceremony first-use detection keys on `VibeSession._is_returning_user`, which is
snapshotted at construction (before the session-start write that creates the
history file). These tests drive that flag directly rather than mocking the
history file — the autouse isolation fixture keeps the real file untouched.
"""

from vibe_harness_mcp import server
from vibe_harness_mcp.session import VibeSession


def _fresh_session(returning=False):
    """Reset the server module's session to a fresh state.

    returning=False → first-use (ceremony fires); True → returning user (skipped).
    """
    server._session = VibeSession()
    server._session._is_returning_user = returning
    if not returning:
        assert server._session._ceremony_phase == 0


class TestCeremonyFullFlow:
    """First tool call returns phase 1, second returns phase 2, third returns normal."""

    def test_first_call_returns_phase1(self):
        _fresh_session()
        output = server.vibe_check()
        assert "notice how your body feels" in output
        assert "Shoulders" in output
        assert "FOR THE AI" in output
        # Should NOT contain mode list or normal vibe check output
        assert "Five modes" not in output
        assert "Mode: Explore" not in output

    def test_second_call_returns_phase2(self):
        _fresh_session()
        server.vibe_check()  # phase 1
        output = server.vibe_check()  # phase 2
        assert "pull-only" in output
        assert "Explore" in output
        assert "Build" in output
        assert "Think-With" in output
        assert "Ship" in output
        assert "Cool-Off" in output
        assert "FOR THE AI" in output
        assert "vibe_set_mode" in output

    def test_third_call_returns_normal(self):
        _fresh_session()
        server.vibe_check()  # phase 1
        server.vibe_check()  # phase 2
        output = server.vibe_check()  # normal
        assert "Mode: Explore" in output
        assert "session" in output
        assert "actions" in output


class TestCeremonyDifferentEntryPoints:
    """Ceremony fires regardless of which tool is called first."""

    def test_vibe_nudge_triggers_phase1(self):
        _fresh_session()
        output = server.vibe_nudge()
        assert "notice how your body feels" in output
        assert "All clear" not in output

    def test_vibe_set_mode_triggers_phase1(self):
        _fresh_session()
        output = server.vibe_set_mode("build")
        assert "notice how your body feels" in output
        # Mode should NOT have switched yet
        assert server._session.mode == "explore"

    def test_vibe_history_triggers_phase1(self):
        _fresh_session()
        output = server.vibe_history()
        assert "notice how your body feels" in output
        assert "No mode transitions" not in output

    def test_mixed_entry_points(self):
        """Phase 1 via nudge, phase 2 via set_mode, then normal via check."""
        _fresh_session()
        p1 = server.vibe_nudge()  # phase 1
        assert "notice how your body feels" in p1
        p2 = server.vibe_set_mode("build")  # phase 2
        assert "pull-only" in p2
        assert server._session.mode == "explore"  # still not switched
        normal = server.vibe_check()  # normal
        assert "Mode: Explore" in normal

    def test_configure_triggers_ceremony(self):
        _fresh_session()
        output = server.vibe_configure("nudges.time_check_minutes", "60")
        assert "notice how your body feels" in output
        assert "Updated" not in output


class TestReturningUserSkipsCeremony:
    """When the user is returning (history pre-existed), ceremony is skipped."""

    def test_vibe_check_normal(self):
        _fresh_session(returning=True)
        output = server.vibe_check()
        assert "Mode: Explore" in output
        assert "notice how your body feels" not in output

    def test_vibe_nudge_normal(self):
        _fresh_session(returning=True)
        output = server.vibe_nudge()
        # Should be normal nudge output, not ceremony
        assert "notice how your body feels" not in output

    def test_ceremony_phase_set_to_none(self):
        _fresh_session(returning=True)
        server.vibe_check()
        assert server._session._ceremony_phase is None
