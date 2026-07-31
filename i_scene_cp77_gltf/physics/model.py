from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PhysicsResource:
    root: dict
    bodies: tuple
    handles: dict
    source_path: str
