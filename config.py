"""Configuration loading with three-layer resolution.

Resolution order: defaults < ~/.vibe-harness/config.json < .vibe-harness.json < runtime overrides.

File configs are loaded once at import time. Runtime overrides via vibe_configure() take priority.
"""

import json
from pathlib import Path
from typing import Any

DEFAULTS = {
    "nudges.time_check_minutes": 45,
    "nudges.session_max_minutes": 120,
    "nudges.interaction_threshold": 100,
    "nudges.cooldown_minutes": 15,
    "friction.enabled": True,
    "export.auto_export": False,
    "activity.idle_threshold_minutes": 30,
}

USER_CONFIG = Path.home() / ".vibe-harness" / "config.json"
PROJECT_CONFIG = Path(".vibe-harness.json")

_user_config: dict[str, Any] = {}
_project_config: dict[str, Any] = {}
_runtime_overrides: dict[str, Any] = {}


def _load_file(path: Path) -> dict[str, Any]:
    """Load a JSON config file, returning only keys that exist in DEFAULTS."""
    try:
        if not path.is_file():
            return {}
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            return {}
        return {k: v for k, v in data.items() if k in DEFAULTS}
    except Exception:
        return {}


def _load_configs() -> None:
    """Load user and project config files."""
    global _user_config, _project_config
    _user_config = _load_file(USER_CONFIG)
    _project_config = _load_file(PROJECT_CONFIG)


# Load on import
_load_configs()


def get(key: str) -> Any:
    """Get config value with resolution: runtime > project > user > defaults."""
    if key in _runtime_overrides:
        return _runtime_overrides[key]
    if key in _project_config:
        return _project_config[key]
    if key in _user_config:
        return _user_config[key]
    return DEFAULTS.get(key)


def set_runtime(key: str, value: str) -> tuple[bool, str]:
    """Set a runtime config override.

    Returns (success, message).
    """
    if key not in DEFAULTS:
        valid_keys = ", ".join(sorted(DEFAULTS.keys()))
        return False, f"Unknown config key: '{key}'. Valid keys: {valid_keys}"

    # Coerce value to match default type
    default_val = DEFAULTS[key]
    try:
        if isinstance(default_val, bool):
            coerced = value.lower() in ("true", "1", "yes")
        elif isinstance(default_val, int):
            coerced = int(value)
        elif isinstance(default_val, float):
            coerced = float(value)
        else:
            coerced = value
    except (ValueError, TypeError):
        return False, f"Invalid value '{value}' for {key} (expected {type(default_val).__name__})"

    old = get(key)
    _runtime_overrides[key] = coerced
    return True, f"{key}: {old} -> {coerced}"


def reload() -> None:
    """Re-read config files from disk. Runtime overrides are preserved."""
    _load_configs()


def list_config() -> dict[str, Any]:
    """Return all effective config values with source annotation."""
    result = {}
    for key in DEFAULTS:
        result[key] = get(key)
    return result


def list_config_sources() -> dict[str, dict]:
    """Return config values with their resolution source."""
    result = {}
    for key in DEFAULTS:
        if key in _runtime_overrides:
            source = "runtime"
        elif key in _project_config:
            source = "project"
        elif key in _user_config:
            source = "user"
        else:
            source = "default"
        result[key] = {"value": get(key), "source": source}
    return result
