"""Configuration loading with three-layer resolution.

Resolution order: defaults < ~/.vibe-harness/config.json < .vibe-harness.json < runtime overrides.

Step 4 will implement full config loading. For now, returns defaults with
runtime override support.
"""

from typing import Any, Optional

DEFAULTS = {
    "nudges.time_check_minutes": 45,
    "nudges.session_max_minutes": 120,
    "nudges.interaction_threshold": 100,
    "nudges.cooldown_minutes": 15,
    "friction.enabled": True,
    "export.auto_export": False,
}

_runtime_overrides: dict[str, Any] = {}


def get(key: str) -> Any:
    """Get config value with resolution: runtime > project > user > defaults."""
    if key in _runtime_overrides:
        return _runtime_overrides[key]
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


def list_config() -> dict[str, Any]:
    """Return all effective config values."""
    result = {}
    for key in DEFAULTS:
        result[key] = get(key)
    return result
