from __future__ import annotations

import base64
import binascii
import math
import struct
from dataclasses import dataclass

_SFNT_VERSIONS = frozenset({0x00010000, 0x74727565, 0x4F54544F})


@dataclass(frozen=True, slots=True)
class FontMetrics:
    """Vertical metrics in font units"""

    units_per_em: int
    ascender: int
    descender: int
    line_gap: int

    def pixel_ascent(self, size: float) -> int:
        return math.ceil(self.ascender * float(size) / self.units_per_em - 1.0e-9)

    def pixel_descent(self, size: float) -> int:
        return math.floor(self.descender * float(size) / self.units_per_em + 1.0e-9)

    def line_height(self, size: float) -> int:
        return self.pixel_ascent(size) - self.pixel_descent(size)


def _tables(data: bytes) -> dict[bytes, tuple[int, int]]:
    version, count = struct.unpack_from(">IH", data, 0)
    if version not in _SFNT_VERSIONS:
        return {}
    tables = {}
    for index in range(count):
        tag, _checksum, offset, length = struct.unpack_from(
            ">4sIII", data, 12 + 16 * index
        )
        if offset + length <= len(data):
            tables[tag] = (offset, length)
    return tables


def truetype_metrics(data: bytes) -> FontMetrics | None:
    """Units per em and vertical metrics of a font, or None for data that is not a font"""
    try:
        tables = _tables(bytes(data))
        head, hhea = tables.get(b"head"), tables.get(b"hhea")
        if head is None or hhea is None or head[1] < 20 or hhea[1] < 10:
            return None
        units_per_em = struct.unpack_from(">H", data, head[0] + 18)[0]
        ascender, descender, line_gap = struct.unpack_from(">hhh", data, hhea[0] + 4)
        os2 = tables.get(b"OS/2")
        if ascender == 0 and descender == 0 and os2 is not None and os2[1] >= 78:
            win_ascent, win_descent = struct.unpack_from(">HH", data, os2[0] + 74)
            ascender, descender = win_ascent, -win_descent
    except struct.error:
        return None
    if units_per_em <= 0:
        return None
    return FontMetrics(units_per_em, ascender, descender, line_gap)


def font_buffer_bytes(document) -> bytes:
    """The font file a .fnt.json export embeds"""
    resource = (
        document.get("Data", {}).get("RootChunk", {})
        if isinstance(document, dict)
        else {}
    )
    buffer = resource.get("fontBuffer") if isinstance(resource, dict) else None
    encoded = buffer.get("Bytes") if isinstance(buffer, dict) else None
    if not isinstance(encoded, str) or not encoded:
        return b""
    try:
        return base64.b64decode(encoded)
    except (binascii.Error, ValueError):
        return b""
