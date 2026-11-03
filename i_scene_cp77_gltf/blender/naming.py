from __future__ import annotations

from typing import Any

# Blender 5 keeps up to 255 UTF-8 bytes of an ID name (MAX_ID_NAME less the type code and terminator).
ID_NAME_MAX_BYTES = 255


def fit_id_name(
    base: Any, suffix: Any = "", *, max_bytes: int = ID_NAME_MAX_BYTES
) -> str:
    """base followed by suffix, cutting base so the whole name fits"""
    base, suffix = str(base), str(suffix)
    suffix_bytes = suffix.encode("utf-8")
    room = int(max_bytes) - len(suffix_bytes)
    if room <= 0:
        return suffix_bytes[: max(0, int(max_bytes))].decode("utf-8", "ignore")
    encoded = base.encode("utf-8")
    if len(encoded) > room:
        base = encoded[:room].decode("utf-8", "ignore")
    return base + suffix
