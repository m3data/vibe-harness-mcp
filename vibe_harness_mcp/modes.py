"""Mode definitions, validation, and friction lookup."""

import json
from pathlib import Path
from typing import Optional

_PRESETS_DIR = Path(__file__).parent / "presets"
_modes_cache: Optional[dict] = None


def load_modes() -> dict:
    """Load mode definitions from presets/modes.json. Cached after first call."""
    global _modes_cache
    if _modes_cache is None:
        path = _PRESETS_DIR / "modes.json"
        _modes_cache = json.loads(path.read_text())
    return _modes_cache


def valid_modes() -> list[str]:
    """Return list of valid mode names."""
    return list(load_modes()["modes"].keys())


def validate_mode(mode: str) -> bool:
    """Check if a mode name is valid."""
    return mode in load_modes()["modes"]


def get_mode(mode: str) -> Optional[dict]:
    """Get full mode definition, or None if invalid."""
    return load_modes()["modes"].get(mode)


def get_friction(from_mode: str, to_mode: str) -> str:
    """Get friction level for a mode transition.

    Returns "none", "medium", or "high".
    Same-mode transitions always return "none".
    """
    if from_mode == to_mode:
        return "none"
    key = f"{from_mode}->{to_mode}"
    return load_modes()["friction"].get(key, "none")


def get_friction_message(level: str, from_mode: str, to_mode: str) -> Optional[str]:
    """Get the friction message for a transition level, or None for 'none'."""
    if level == "none":
        return None
    messages = load_modes().get("friction_messages", {})
    template = messages.get(level)
    if template is None:
        return None
    from_name = get_mode(from_mode)["name"] if get_mode(from_mode) else from_mode
    to_name = get_mode(to_mode)["name"] if get_mode(to_mode) else to_mode
    return template.format(**{
        "from": from_name,
        "to": to_name,
        "from_key": from_mode,
        "to_key": to_mode,
    })


def default_mode() -> str:
    """Return the default starting mode."""
    return load_modes().get("default_mode", "explore")
