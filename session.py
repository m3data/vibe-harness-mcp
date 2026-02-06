"""Session state management for Vibe Harness."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import uuid

from modes import get_friction, get_friction_message, default_mode, validate_mode, get_mode

HISTORY_DIR = Path.home() / ".vibe-harness"
HISTORY_FILE = HISTORY_DIR / "mode-history.jsonl"


@dataclass
class ModeTransition:
    """Record of a single mode transition."""
    from_mode: str
    to_mode: str
    timestamp: datetime
    friction: str  # "none", "medium", "high"
    confirmed: bool  # False if high-friction and awaiting confirmation

    def to_dict(self) -> dict:
        return {
            "from": self.from_mode,
            "to": self.to_mode,
            "timestamp": self.timestamp.isoformat(),
            "friction": self.friction,
            "confirmed": self.confirmed,
        }


@dataclass
class VibeSession:
    """In-memory session state. Authoritative during the MCP process lifetime."""

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    mode: str = field(default_factory=default_mode)
    mode_since: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    interaction_count: int = 0
    transitions: list[ModeTransition] = field(default_factory=list)
    nudges_surfaced: int = 0
    last_nudge_at: Optional[datetime] = None

    # High-friction confirmation state
    _pending_mode: Optional[str] = field(default=None, repr=False)
    _pending_friction: Optional[str] = field(default=None, repr=False)

    def record_interaction(self) -> None:
        """Increment interaction counter. Call on every tool invocation."""
        self.interaction_count += 1

    def set_mode(self, new_mode: str) -> dict:
        """Attempt a mode transition.

        Returns a dict with:
            success: bool
            mode: str (current mode after attempt)
            message: str (orientation or friction warning)
            friction: str
            awaiting_confirmation: bool
        """
        if not validate_mode(new_mode):
            return {
                "success": False,
                "mode": self.mode,
                "message": f"Unknown mode: '{new_mode}'. Valid modes: explore, build, think-with, ship, cool-off",
                "friction": "none",
                "awaiting_confirmation": False,
            }

        # Check if this completes a pending high-friction confirmation
        if self._pending_mode == new_mode and self._pending_friction == "high":
            return self._confirm_transition(new_mode)

        # If there's a different pending mode, cancel it
        if self._pending_mode and self._pending_mode != new_mode:
            self._pending_mode = None
            self._pending_friction = None

        # Same mode — no-op
        if new_mode == self.mode:
            mode_def = get_mode(new_mode)
            return {
                "success": True,
                "mode": self.mode,
                "message": f"Already in {mode_def['name']}.\n\n{mode_def['orientation']}",
                "friction": "none",
                "awaiting_confirmation": False,
            }

        friction = get_friction(self.mode, new_mode)

        # High friction — require double-call
        if friction == "high":
            self._pending_mode = new_mode
            self._pending_friction = "high"
            friction_msg = get_friction_message("high", self.mode, new_mode)
            return {
                "success": False,
                "mode": self.mode,
                "message": friction_msg,
                "friction": "high",
                "awaiting_confirmation": True,
            }

        # Medium friction — proceed with acknowledgment
        if friction == "medium":
            friction_msg = get_friction_message("medium", self.mode, new_mode)
            result = self._execute_transition(new_mode, friction)
            result["message"] = f"{friction_msg}\n\n{result['message']}"
            return result

        # No friction — just go
        return self._execute_transition(new_mode, friction)

    def _confirm_transition(self, new_mode: str) -> dict:
        """Complete a high-friction transition after confirmation."""
        self._pending_mode = None
        self._pending_friction = None
        return self._execute_transition(new_mode, "high")

    def _execute_transition(self, new_mode: str, friction: str) -> dict:
        """Actually switch modes."""
        old_mode = self.mode
        now = datetime.now(timezone.utc)

        transition = ModeTransition(
            from_mode=old_mode,
            to_mode=new_mode,
            timestamp=now,
            friction=friction,
            confirmed=True,
        )
        self.transitions.append(transition)

        self.mode = new_mode
        self.mode_since = now

        self._log_transition(old_mode, new_mode, friction, now)

        mode_def = get_mode(new_mode)
        return {
            "success": True,
            "mode": new_mode,
            "message": f"{mode_def['name']}.\n\n{mode_def['orientation']}",
            "friction": friction,
            "awaiting_confirmation": False,
        }

    def _log_transition(self, from_mode: str, to_mode: str, friction: str, timestamp: datetime) -> None:
        """Append transition to JSONL history file. Failures are silently swallowed."""
        try:
            HISTORY_DIR.mkdir(parents=True, exist_ok=True)
            entry = {
                "timestamp": timestamp.isoformat(),
                "session_id": self.session_id,
                "from_mode": from_mode,
                "to_mode": to_mode,
                "friction": friction,
            }
            with HISTORY_FILE.open("a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def mode_duration_minutes(self) -> float:
        """Minutes in current mode."""
        delta = datetime.now(timezone.utc) - self.mode_since
        return delta.total_seconds() / 60

    def session_duration_minutes(self) -> float:
        """Minutes since session started."""
        delta = datetime.now(timezone.utc) - self.started_at
        return delta.total_seconds() / 60

    def interactions_since_last_switch(self) -> int:
        """Interactions since last mode transition."""
        if not self.transitions:
            return self.interaction_count
        # Count interactions that happened after the last transition
        # (approximate — we track total, not per-mode)
        return self.interaction_count

    def time_in_mode_summary(self) -> dict[str, float]:
        """Calculate time spent in each mode during this session."""
        summary: dict[str, float] = {}
        now = datetime.now(timezone.utc)

        if not self.transitions:
            mode = self.mode
            minutes = (now - self.started_at).total_seconds() / 60
            summary[mode] = round(minutes, 1)
            return summary

        # Time from session start to first transition
        first = self.transitions[0]
        start_minutes = (first.timestamp - self.started_at).total_seconds() / 60
        initial_mode = first.from_mode
        summary[initial_mode] = summary.get(initial_mode, 0) + start_minutes

        # Time between transitions
        for i, t in enumerate(self.transitions):
            if i + 1 < len(self.transitions):
                end = self.transitions[i + 1].timestamp
            else:
                end = now
            minutes = (end - t.timestamp).total_seconds() / 60
            summary[t.to_mode] = summary.get(t.to_mode, 0) + minutes

        return {k: round(v, 1) for k, v in summary.items()}

    def to_export_dict(self) -> dict:
        """Full session data for JSON export."""
        return {
            "schema_version": "0.1.0",
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat(),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "duration_minutes": round(self.session_duration_minutes(), 1),
            "current_mode": self.mode,
            "interaction_count": self.interaction_count,
            "nudges_surfaced": self.nudges_surfaced,
            "transitions": [t.to_dict() for t in self.transitions],
            "time_in_mode": self.time_in_mode_summary(),
        }
