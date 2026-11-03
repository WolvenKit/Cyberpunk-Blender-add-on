from __future__ import annotations

_FNV_OFFSET = 0xCBF29CE484222325
_FNV_PRIME = 0x100000001B3
_MASK64 = 0xFFFFFFFFFFFFFFFF


def fnv1a64(text) -> int:
    """64-bit FNV-1a over the UTF-8 text"""
    result = _FNV_OFFSET
    for byte in str(text).encode("utf-8"):
        result ^= byte
        result = (result * _FNV_PRIME) & _MASK64
    return result


def cname_hash(name) -> int:
    """A CName's 64-bit hash"""
    text = str(name or "")
    return 0 if not text or text == "None" else fnv1a64(text)
