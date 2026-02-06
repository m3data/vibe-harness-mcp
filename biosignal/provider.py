"""Abstract biosignal provider interface (Layer 2).

Layer 2 will implement concrete providers (e.g. Polar H10 via BLE).
For now this defines the contract that governor.py will eventually consume.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class BiosignalSnapshot:
    """Point-in-time biosignal reading."""
    hr: Optional[float] = None          # Heart rate (bpm)
    hrv_rmssd: Optional[float] = None   # HRV RMSSD (ms)
    hrv_trend: Optional[str] = None     # "rising", "stable", "declining"
    coherence: Optional[float] = None   # 0.0-1.0 coherence score
    pattern: Optional[str] = None       # "breathing", "locked", "fragmented", "transitional"


class BiosignalProvider(ABC):
    """Interface for biosignal data sources."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Whether a biosignal source is currently connected."""
        ...

    @abstractmethod
    def snapshot(self) -> Optional[BiosignalSnapshot]:
        """Get current biosignal reading, or None if unavailable."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Clean up connection."""
        ...
