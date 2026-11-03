from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PhysXCapabilityState(str, Enum):
    UNINITIALIZED = "UNINITIALIZED"
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class PhysXCapability:
    state: PhysXCapabilityState
    reason: str = ""
    bridge_path: str = ""
