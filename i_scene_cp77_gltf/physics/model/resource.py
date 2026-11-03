from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class PhysicsResource:
    root: dict
    bodies: tuple
    handles: dict
    source_path: str


def cooked_data_signature(value):
    raw = str(value or "").encode("ascii", "ignore")
    return sha256(raw).hexdigest() if raw else ""
