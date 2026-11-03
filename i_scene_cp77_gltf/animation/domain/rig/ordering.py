from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import TypeVar

T = TypeVar("T")


def rig_base_label_kind(label: str) -> str:
    tokens = set(re.findall(r"[a-z0-9]+", str(label or "").casefold()))
    if "root" in tokens:
        return "root"
    if "base" in tokens:
        return "base"
    return ""


def promote_rig_base(items: Sequence[T], label: Callable[[T], str]) -> list[T]:
    """Stably promote root, then base, while preserving all remaining order"""
    ordered = list(items or ())
    selected = None
    for preferred in ("root", "base"):
        for index, item in enumerate(ordered):
            if rig_base_label_kind(label(item)) == preferred:
                selected = index
                break
        if selected is not None:
            break
    if selected:
        ordered.insert(0, ordered.pop(selected))
    return ordered
