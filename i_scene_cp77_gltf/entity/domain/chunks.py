from __future__ import annotations

from typing import Any

FULL_MASK = (1 << 64) - 1


def parse_mask(value: Any) -> int:
    """A component's chunk mask"""
    if value is None or value == "":
        return FULL_MASK
    return int(value) & FULL_MASK


def mask_text(mask: int) -> str:
    return str(int(mask) & FULL_MASK)


def part_visible(mask: int, part: int) -> bool:
    return bool((int(mask) >> int(part)) & 1)


def set_part_visible(mask: int, part: int, visible: bool) -> int:
    bit = 1 << int(part)
    return (int(mask) | bit) if visible else (int(mask) & ~bit & FULL_MASK)
