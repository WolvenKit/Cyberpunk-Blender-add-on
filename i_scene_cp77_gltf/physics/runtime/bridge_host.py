from __future__ import annotations

from typing import Protocol


class BridgeHost(Protocol):
    @property
    def blender_version(self) -> tuple[int, ...]:
        """The running Blender version"""

    def mark_scene_runtime_stale(self, *, initialized: bool | None = None) -> None:
        """Scene state that referred to native actors no longer does"""
