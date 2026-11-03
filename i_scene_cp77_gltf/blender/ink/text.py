from __future__ import annotations

import hashlib
import math
import os

import blf
import bpy
import imbuf
import numpy as np

from ...assetio.atomic import atomic_write_bytes
from ...assetio.files import read_bytes
from ...assetio.fonts import truetype_metrics
from ...core.log import debug_exception, get_logger
from .images import buffer_bytes

_LOG = get_logger(__name__)

_DEFAULT_FONT = 0
# Ascent and descent per em for Blender's default font, whose tables are not read.
_DEFAULT_ASCENT, _DEFAULT_DESCENT = 0.8, -0.2


class BlenderFonts:
    """A text measurer and glyph source for the ink layout and rasterizer"""

    def __init__(self):
        self._ids: dict = {}
        self._metrics: dict = {}

    @staticmethod
    def _key(face):
        if face is None:
            return None
        if face.path:
            return ("path", os.path.normcase(os.path.abspath(face.path)))
        return ("data", hashlib.sha1(face.data).hexdigest())

    def _font(self, face) -> int:
        key = self._key(face)
        if key is None:
            return _DEFAULT_FONT
        if key not in self._ids:
            path, data = face.path, face.data
            if not path and data:
                path = os.path.join(bpy.app.tempdir, f"cp77_ink_font_{key[1][:16]}.ttf")
                if not os.path.isfile(path):
                    atomic_write_bytes(path, data)
            font_id = blf.load(path) if path else -1
            self._ids[key] = font_id if font_id >= 0 else _DEFAULT_FONT
            try:
                self._metrics[key] = truetype_metrics(data or read_bytes(path))
            except OSError:
                debug_exception(
                    _LOG,
                    "Could not read font metrics from %s; the text uses default metrics",
                    path,
                )
                self._metrics[key] = None
        return self._ids[key]

    def advance(self, font, size: float, text: str) -> float:
        if not text:
            return 0.0
        font_id = self._font(font)
        blf.size(font_id, float(size))
        return float(blf.dimensions(font_id, text)[0])

    def vertical(self, font, size: float) -> tuple[int, int]:
        self._font(font)
        metrics = self._metrics.get(self._key(font))
        if metrics is None:
            return math.ceil(_DEFAULT_ASCENT * size), math.floor(
                _DEFAULT_DESCENT * size
            )
        return metrics.pixel_ascent(size), metrics.pixel_descent(size)

    def coverage(
        self,
        block,
        style,
        width: int,
        height: int,
        origin: tuple[float, float],
        density: tuple[float, float],
    ) -> np.ndarray:
        """Glyph coverage (height, width), top row first, for block with its top-left at origin"""
        font_id = self._font(style.font)
        buffer = imbuf.new((int(width), int(height)))
        try:
            blf.size(font_id, float(block.size) * density[1])
            with blf.bind_imbuf(font_id, buffer):
                blf.color(font_id, 1.0, 1.0, 1.0, 1.0)
                for line in block.lines:
                    if not line.text:
                        continue
                    x = (origin[0] + line.x) * density[0]
                    baseline = (origin[1] + line.top + block.ascent) * density[1]
                    y = height - baseline
                    if style.tracking:
                        for character in line.text:
                            blf.position(font_id, x, y, 0.0)
                            blf.draw_buffer(font_id, character)
                            x += (
                                blf.dimensions(font_id, character)[0]
                                + style.tracking * density[0]
                            )
                    else:
                        blf.position(font_id, x, y, 0.0)
                        blf.draw_buffer(font_id, line.text)
            alpha = buffer_bytes(buffer)[..., -1]
        finally:
            buffer.free()
        return alpha[::-1].astype(np.float32) / 255.0
