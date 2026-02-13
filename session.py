"""Session state management for Vibe Harness."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import uuid

import config
from modes import get_friction, get_friction_message, default_mode, validate_mode, get_mode

HISTORY_DIR = Path.home() / ".vibe-harness"
HISTORY_FILE = HISTORY_DIR / "mode-history.jsonl"

# Export schema version — tracks the JSON export format independently of the
# package version. Bump when adding/removing/renaming fields in to_export_dict().
EXPORT_SCHEMA_VERSION = "0.3.0"


@dataclass
class IdleGap:
    """A detected period of inactivity between tool calls."""
    start: datetime
    end: datetime

    @property
    def duration_seconds(self) -> float:
        return (self.end - self.start).total_seconds()

    def to_dict(self) -> dict:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "duration_minutes": round(self.duration_seconds / 60, 1),
        }


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

    # Governance trace (list of evaluation dicts from governor.evaluate_rules)
    governance_trace: list[dict] = field(default_factory=list)

    # Tracks interaction count at last mode switch for per-mode counting
    _interactions_at_last_switch: int = field(default=0, repr=False)

    # Activity tracking for idle gap detection
    last_interaction_at: Optional[datetime] = field(default=None, repr=False)
    _idle_gaps: list[IdleGap] = field(default_factory=list, repr=False)

    # High-friction confirmation state
    _pending_mode: Optional[str] = field(default=None, repr=False)
    _pending_friction: Optional[str] = field(default=None, repr=False)
    _onboarding_shown: bool = field(default=False, repr=False)

    def record_interaction(self) -> None:
        """Increment interaction counter and detect idle gaps.

        Call on every tool invocation. If the gap since the last interaction
        exceeds the idle threshold, records an IdleGap so active duration
        calculations can subtract idle time.
        """
        now = datetime.now(timezone.utc)
        if self.last_interaction_at is not None:
            gap_seconds = (now - self.last_interaction_at).total_seconds()
            threshold_minutes = config.get("activity.idle_threshold_minutes")
            if gap_seconds >= threshold_minutes * 60:
                self._idle_gaps.append(IdleGap(start=self.last_interaction_at, end=now))
        self.last_interaction_at = now
        self.interaction_count += 1

    def record_governance_evaluation(self, evaluations: list[dict]) -> None:
        """Record a governance trace entry from evaluate_rules().

        Each entry is timestamped and contains the full evaluation of all
        rules — which fired, which were defeated, and by what. This is the
        accountability trail for defeasible governance.
        """
        self.governance_trace.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "evaluations": evaluations,
        })

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
        self._interactions_at_last_switch = self.interaction_count

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

    def _total_idle_seconds(self, since: datetime) -> float:
        """Sum idle gap durations that fall after `since`.

        Handles gaps that straddle the `since` boundary by only counting
        the portion after `since`.
        """
        total = 0.0
        for gap in self._idle_gaps:
            if gap.end <= since:
                continue
            effective_start = max(gap.start, since)
            total += (gap.end - effective_start).total_seconds()
        return total

    def active_session_minutes(self) -> float:
        """Session duration minus idle time."""
        elapsed = self.session_duration_minutes()
        idle = self._total_idle_seconds(self.started_at) / 60
        return max(0.0, elapsed - idle)

    def active_mode_minutes(self) -> float:
        """Current mode duration minus idle time since mode started."""
        elapsed = self.mode_duration_minutes()
        idle = self._total_idle_seconds(self.mode_since) / 60
        return max(0.0, elapsed - idle)

    def total_idle_minutes(self) -> float:
        """Total idle time detected across the session."""
        return self._total_idle_seconds(self.started_at) / 60

    def interactions_since_last_switch(self) -> int:
        """Interactions since last mode transition."""
        return self.interaction_count - self._interactions_at_last_switch

    def time_in_mode_summary(self) -> dict[str, float]:
        """Calculate active time spent in each mode during this session.

        Subtracts idle gaps from each mode's time allocation so the summary
        reflects active time, not wall-clock time.
        """
        summary: dict[str, float] = {}
        now = datetime.now(timezone.utc)

        if not self.transitions:
            mode = self.mode
            elapsed = (now - self.started_at).total_seconds() / 60
            idle = self._total_idle_seconds(self.started_at) / 60
            summary[mode] = round(max(0.0, elapsed - idle), 1)
            return summary

        # Build list of (mode, start, end) spans
        spans: list[tuple[str, datetime, datetime]] = []

        # Time from session start to first transition
        first = self.transitions[0]
        spans.append((first.from_mode, self.started_at, first.timestamp))

        # Time between transitions
        for i, t in enumerate(self.transitions):
            end = self.transitions[i + 1].timestamp if i + 1 < len(self.transitions) else now
            spans.append((t.to_mode, t.timestamp, end))

        # Accumulate active time per mode
        for mode, span_start, span_end in spans:
            elapsed = (span_end - span_start).total_seconds() / 60
            idle = self._total_idle_seconds(span_start) / 60
            # Only count idle time within this span
            idle_in_span = 0.0
            for gap in self._idle_gaps:
                if gap.end <= span_start or gap.start >= span_end:
                    continue
                effective_start = max(gap.start, span_start)
                effective_end = min(gap.end, span_end)
                idle_in_span += (effective_end - effective_start).total_seconds() / 60
            active = max(0.0, elapsed - idle_in_span)
            summary[mode] = summary.get(mode, 0) + active

        return {k: round(v, 1) for k, v in summary.items()}

    def to_export_dict(self) -> dict:
        """Full session data for JSON export."""
        return {
            "schema_version": EXPORT_SCHEMA_VERSION,
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat(),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "duration_minutes": round(self.session_duration_minutes(), 1),
            "active_duration_minutes": round(self.active_session_minutes(), 1),
            "current_mode": self.mode,
            "interaction_count": self.interaction_count,
            "nudges_surfaced": self.nudges_surfaced,
            "transitions": [t.to_dict() for t in self.transitions],
            "idle_gaps": [g.to_dict() for g in self._idle_gaps],
            "time_in_mode": self.time_in_mode_summary(),
            "governance_trace": self.governance_trace,
        }
