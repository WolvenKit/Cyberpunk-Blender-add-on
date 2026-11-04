from __future__ import annotations

import os
import tempfile
from collections import OrderedDict

import bpy
import imbuf
import numpy as np

from ...bartmoss.scalar import linear_channel_to_srgb, srgb_channel_to_linear
from ...core.log import debug_exception, get_logger
from ..transactions import new_tracked_datablock

_LOG = get_logger(__name__)

_BUDGET_BYTES = 512 * 1024 * 1024
_decoded: OrderedDict = OrderedDict()
_decoded_bytes = 0


def _read_back(path: str) -> np.ndarray:
    """The 8-bit pixel rows of the image file at path, bottom row first"""
    image = bpy.data.images.load(path, check_existing=False)
    try:
        width, height = (int(value) for value in image.size)
        pixels = np.empty(width * height * 4, dtype=np.float32)
        image.pixels.foreach_get(pixels)
        is_float = image.is_float
    finally:
        bpy.data.images.remove(image)
    pixels = pixels.reshape(height, width, 4)
    if is_float:
        alpha = pixels[..., 3:]
        np.divide(pixels[..., :3], alpha, out=pixels[..., :3], where=alpha > 0.0)
        pixels[..., :3] = linear_channel_to_srgb(pixels[..., :3])
    return np.floor(np.clip(pixels, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def buffer_bytes(buffer) -> np.ndarray:
    """The 8-bit pixel rows of an image buffer holding bytes, bottom row first"""
    if hasattr(buffer, "with_buffer"):
        with buffer.with_buffer() as data:
            return np.array(data, copy=True)
    handle, path = tempfile.mkstemp(suffix=".png", dir=bpy.app.tempdir or None)
    os.close(handle)
    try:
        imbuf.write(buffer, filepath=path)
        return _read_back(path)
    finally:
        os.remove(path)


def _decode(path: str) -> np.ndarray:
    if hasattr(imbuf.types.ImBuf, "with_buffer"):
        buffer = imbuf.load(path)
        try:
            if buffer.buffer_type != "BYTE":
                buffer.convert_buffer_type("BYTE")
            pixels = buffer_bytes(buffer)
        finally:
            buffer.free()
    else:
        pixels = _read_back(path)
    if pixels.ndim == 2:
        pixels = pixels[..., None]
    channels = pixels.shape[2]
    color = pixels[..., :3] if channels >= 3 else np.repeat(pixels[..., :1], 3, axis=2)
    if channels in (2, 4):
        alpha = pixels[..., channels - 1 : channels]
    else:
        alpha = np.full(pixels.shape[:2] + (1,), 255, dtype=pixels.dtype)
    result = np.concatenate((color, alpha), axis=2)[::-1].astype(np.float32) / 255.0
    result[..., :3] = srgb_channel_to_linear(result[..., :3])
    return result


def decoded_image(path: str) -> np.ndarray:
    """The image at path as linear straight RGBA, top row first"""
    global _decoded_bytes
    try:
        stamp = os.stat(path).st_mtime_ns
    except OSError:
        debug_exception(
            _LOG,
            "Could not read the time of %s; the decoded image is not cached by time",
            path,
        )
        stamp = 0
    key = (os.path.normcase(os.path.abspath(path)), stamp)
    if key in _decoded:
        _decoded.move_to_end(key)
        return _decoded[key]
    pixels = _decode(path)
    _decoded[key] = pixels
    _decoded_bytes += pixels.nbytes
    while _decoded_bytes > _BUDGET_BYTES and len(_decoded) > 1:
        _old_key, old = _decoded.popitem(last=False)
        _decoded_bytes -= old.nbytes
    return pixels


def clear_decoded_images() -> None:
    global _decoded_bytes
    _decoded.clear()
    _decoded_bytes = 0


class PartPixels:
    """A pixel source for the ink rasterizer"""

    def pixels(self, part) -> np.ndarray | None:
        try:
            image = decoded_image(part.path)
        except (OSError, RuntimeError, ValueError):
            return None
        x, y, width, height = part.rect
        crop = image[y : y + height, x : x + width]
        return crop if crop.size else None


def update_texture(image, canvas: np.ndarray) -> None:
    """Write canvas into image row for row"""
    height, width = canvas.shape[:2]
    if tuple(int(value) for value in image.size) != (width, height):
        image.scale(width, height)
    image.pixels.foreach_set(np.ascontiguousarray(canvas, dtype=np.float32).reshape(-1))
    image.update()


def pack_texture(image) -> None:
    """Keep the render texture's current pixels in the file"""
    try:
        image.pack()
    except RuntimeError:
        pass


def render_texture(name: str, canvas: np.ndarray):
    """A new packed float image holding canvas"""
    height, width = canvas.shape[:2]
    image = new_tracked_datablock(
        "images", name, width=width, height=height, alpha=True, float_buffer=True
    )
    image.colorspace_settings.name = "Non-Color"
    image.alpha_mode = "CHANNEL_PACKED"
    update_texture(image, canvas)
    image.file_format = "OPEN_EXR"
    pack_texture(image)
    return image
