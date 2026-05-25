"""Temporal awareness — clock time and cross-session pattern mining.

Reads ~/.vibe-harness/mode-history.jsonl to detect:
- Time-of-day context (period, is_late flag)
- Sessions today (count, total minutes)
- Sessions this week (count, dominant mode)
- Mode distribution across recent history

All analysis is read-only against the existing JSONL file.
"""

import json
from collections import Counter
from datetime import datetime, date, timedelta, timezone
from typing import Optional

from vibe_harness_mcp import config

# History path resolves through config.history_file() (per-call, honours the
# VIBE_HARNESS_HISTORY_DIR override) — no module-level path constant here.

# Period definitions (local time hours)
_PERIODS = [
    (0, 6, "early_morning"),
    (6, 12, "morning"),
    (12, 17, "afternoon"),
    (17, 22, "evening"),
    (22, 24, "late_night"),
]


def _get_period(hour: int) -> str:
    """Map an hour (0-23) to a named period."""
    for start, end, name in _PERIODS:
        if start <= hour < end:
            return name
    return "late_night"


def _is_late_hour(hour: int) -> bool:
    """Check if the current hour falls in late-night or early-morning range."""
    late_start = config.get("temporal.late_night_start")
    late_end = config.get("temporal.late_night_end")
    if late_start is None:
        late_start = 22
    if late_end is None:
        late_end = 6
    # Handle wrap-around (e.g., 22:00 to 06:00)
    if late_start > late_end:
        return hour >= late_start or hour < late_end
    return late_start <= hour < late_end


def _load_history() -> list[dict]:
    """Load all entries from mode-history.jsonl. Returns empty list on error."""
    try:
        history_file = config.history_file()
        if not history_file.exists():
            return []
        entries = []
        for line in history_file.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries
    except Exception:
        return []


def _parse_timestamp(ts_str: str) -> Optional[datetime]:
    """Parse an ISO timestamp string, returning None on failure."""
    try:
        return datetime.fromisoformat(ts_str)
    except (ValueError, TypeError):
        return None


def _group_sessions(entries: list[dict]) -> list[dict]:
    """Group history entries by session_id, calculating start/end/duration.

    Returns a list of session summaries sorted by start time.
    """
    sessions: dict[str, dict] = {}
    for entry in entries:
        sid = entry.get("session_id")
        if not sid:
            continue
        ts = _parse_timestamp(entry.get("timestamp", ""))
        if ts is None:
            continue

        if sid not in sessions:
            sessions[sid] = {
                "session_id": sid,
                "start": ts,
                "end": ts,
                "modes": [],
            }
        else:
            if ts < sessions[sid]["start"]:
                sessions[sid]["start"] = ts
            if ts > sessions[sid]["end"]:
                sessions[sid]["end"] = ts

        to_mode = entry.get("to_mode")
        if to_mode:
            sessions[sid]["modes"].append(to_mode)

    # Calculate duration and find dominant mode
    result = []
    for s in sessions.values():
        duration_min = (s["end"] - s["start"]).total_seconds() / 60
        mode_counts = Counter(s["modes"])
        dominant = mode_counts.most_common(1)[0][0] if mode_counts else None
        result.append({
            "session_id": s["session_id"],
            "start": s["start"],
            "end": s["end"],
            "duration_minutes": round(duration_min, 1),
            "dominant_mode": dominant,
            "mode_counts": dict(mode_counts),
        })

    result.sort(key=lambda x: x["start"])
    return result


def _sessions_on_date(sessions: list[dict], target_date: date) -> list[dict]:
    """Filter sessions that started on a given date (local time)."""
    return [
        s for s in sessions
        if s["start"].astimezone().date() == target_date
    ]


def _sessions_in_week(sessions: list[dict], reference: date) -> list[dict]:
    """Filter sessions from the same ISO week as the reference date."""
    ref_year, ref_week, _ = reference.isocalendar()
    return [
        s for s in sessions
        if s["start"].astimezone().date().isocalendar()[:2] == (ref_year, ref_week)
    ]


def get_temporal_context(now: Optional[datetime] = None) -> dict:
    """Build temporal context for the current moment.

    Returns a dict with:
        hour: int (local)
        minute: int (local)
        period: str (early_morning, morning, afternoon, evening, late_night)
        is_late: bool
        sessions_today: {count, total_minutes}
        sessions_this_week: {count, dominant_mode, mode_distribution}
    """
    if now is None:
        now = datetime.now(timezone.utc)

    local_now = now.astimezone()
    hour = local_now.hour
    minute = local_now.minute
    today = local_now.date()

    period = _get_period(hour)
    is_late = _is_late_hour(hour)

    # Cross-session patterns from history
    entries = _load_history()
    sessions = _group_sessions(entries)

    # Today's sessions
    today_sessions = _sessions_on_date(sessions, today)
    today_count = len(today_sessions)
    today_minutes = sum(s["duration_minutes"] for s in today_sessions)

    # This week's sessions
    week_sessions = _sessions_in_week(sessions, today)
    week_count = len(week_sessions)

    # Aggregate mode distribution for the week
    week_modes: Counter = Counter()
    for s in week_sessions:
        week_modes.update(s["mode_counts"])

    week_dominant = week_modes.most_common(1)[0][0] if week_modes else None
    week_distribution = dict(week_modes)

    return {
        "hour": hour,
        "minute": minute,
        "period": period,
        "is_late": is_late,
        "sessions_today": {
            "count": today_count,
            "total_minutes": round(today_minutes, 1),
        },
        "sessions_this_week": {
            "count": week_count,
            "dominant_mode": week_dominant,
            "mode_distribution": week_distribution,
        },
    }
