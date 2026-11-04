from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

ADDITIVE_PREVIEW_SETTINGS = "cp77_additive_preview"

_FULL_BODY_MASKS = frozenset({"", "None", "NONE"})


def canonical_mask_name(value) -> str:
    """Rig part mask name, with the full-body choices mapped to ''"""
    text = str(value or "")
    return "" if text in _FULL_BODY_MASKS else text


class ActionListSlot(IntEnum):
    NORMAL = 0
    PRIMARY = 1
    SECONDARY = 2

    @property
    def selector(self) -> str:
        return _SELECTORS[self]

    @property
    def preview_slot(self) -> int | None:
        return None if self is ActionListSlot.NORMAL else int(self) - 1

    @classmethod
    def from_selector(cls, selector: str) -> ActionListSlot:
        return _SLOTS_BY_SELECTOR.get(str(selector), cls.NORMAL)


_SELECTORS = {
    ActionListSlot.NORMAL: "action_index",
    ActionListSlot.PRIMARY: "additive_index",
    ActionListSlot.SECONDARY: "secondary_index",
}
_SLOTS_BY_SELECTOR = {selector: slot for slot, selector in _SELECTORS.items()}


@dataclass(frozen=True, slots=True)
class AdditiveSlotPlayback:
    weight: float = 1.0
    time_scale: float = 1.0
    time_offset: float = 0.0
    loop: bool = False

    @classmethod
    def from_settings(cls, settings, preview_slot: int) -> AdditiveSlotPlayback:
        if settings is None:
            return cls()
        prefix = "" if preview_slot == 0 else "secondary_"
        return cls(
            weight=min(1.0, max(0.0, float(getattr(settings, prefix + "weight", 1.0)))),
            time_scale=float(getattr(settings, prefix + "time_scale", 1.0)),
            time_offset=float(getattr(settings, prefix + "time_offset", 0.0)),
            loop=bool(getattr(settings, prefix + "loop", False)),
        )


@dataclass(frozen=True, slots=True)
class AdditivePreviewOptions:
    storage_mode: str = "REFERENCE_APPLIED"
    primary_mask: str = ""
    secondary_enabled: bool = False
    secondary_mask: str = ""
    secondary_action: str = "NONE"
    mixer_enabled: bool = False

    @classmethod
    def from_settings(cls, settings) -> AdditivePreviewOptions:
        if settings is None:
            return cls()
        return cls(
            storage_mode=str(getattr(settings, "storage_mode", "REFERENCE_APPLIED")),
            primary_mask=canonical_mask_name(getattr(settings, "mask", "")),
            secondary_enabled=bool(getattr(settings, "secondary_enabled", False)),
            secondary_mask=canonical_mask_name(getattr(settings, "secondary_mask", "")),
            secondary_action=str(
                getattr(settings, "secondary_action", "NONE") or "NONE"
            ),
            mixer_enabled=bool(getattr(settings, "mixer_enabled", False)),
        )
