"""Nudge logic — evaluates session state and surfaces contextual suggestions.

Step 3 will implement full governor with:
- Mode duration checks (45min default)
- Session duration checks (120min default)
- Interaction count checks (100 default)
- Mode drift detection (e.g. explore with high interactions -> suggest build)
- Nudge suppression (max one per 15min)

For now, returns stub responses.
"""

from typing import Optional


def evaluate_nudge(session) -> Optional[str]:
    """Evaluate session state and return a nudge message, or None.

    Step 3 will implement actual logic. For now, always returns None.
    """
    return None


def format_nudge_or_clear(nudge: Optional[str]) -> str:
    """Format a nudge message, or 'all clear' if none."""
    if nudge is None:
        return "All clear. No nudges right now."
    return f"## Nudge\n\n{nudge}"
