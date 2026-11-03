from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from ...bartmoss.affine import scale_matrix_2d


class PixelSource(Protocol):
    def pixels(self, part: Any) -> np.ndarray | None:
        """A part's pixels, (height, width, 4) linear straight RGBA, top row first"""


class GlyphSource(Protocol):
    def coverage(
        self,
        block: Any,
        style: Any,
        width: int,
        height: int,
        origin: tuple[float, float],
        density: tuple[float, float],
    ) -> np.ndarray | None:
        """Glyph coverage for a text block"""


@dataclass(frozen=True, slots=True)
class ImageMode:
    fit_to_content: bool
    content_align: tuple[str, str]
    nine_slice: tuple[float, float, float, float] | None
    tile: str
    tile_align: tuple[str, str]
    mirror: str


@dataclass(frozen=True, slots=True)
class DrawCommand:
    """One widget's drawing"""

    kind: str
    width: float
    height: float
    world: Any
    color: tuple[float, float, float, float]
    opacity: float
    thickness: float = 0.0
    part: Any = None
    image: ImageMode | None = None
    text: Any = None
    text_style: Any = None
    text_origin: tuple[float, float] = (0.0, 0.0)
    path: tuple[int, ...] = ()


def _over(
    canvas: np.ndarray,
    source: np.ndarray,
    x: int,
    y: int,
    mask: np.ndarray | None = None,
) -> None:
    height, width = canvas.shape[:2]
    rows, columns = source.shape[:2]
    left, top = max(0, x), max(0, y)
    right, bottom = min(width, x + columns), min(height, y + rows)
    if right <= left or bottom <= top:
        return
    piece = source[top - y : bottom - y, left - x : right - x]
    if mask is not None:
        piece = piece * mask[top - y : bottom - y, left - x : right - x, None]
    target = canvas[top:bottom, left:right]
    target *= 1.0 - piece[..., 3:4]
    target += piece


def _ellipse(width: int, height: int) -> np.ndarray:
    x = ((np.arange(width) + 0.5) / width - 0.5) * 2.0
    y = ((np.arange(height) + 0.5) / height - 0.5) * 2.0
    return (y[:, None] ** 2 + x[None, :] ** 2 <= 1.0).astype(np.float32)


def _frame(width: int, height: int, thickness: tuple[int, int]) -> np.ndarray:
    across, down = thickness
    coverage = np.zeros((height, width), dtype=np.float32)
    if across > 0 or down > 0:
        coverage[:down, :] = 1.0
        coverage[max(0, height - down) :, :] = 1.0
        coverage[:, :across] = 1.0
        coverage[:, max(0, width - across) :] = 1.0
    return coverage


def _aligned_offset(align: str, area: float, size: float) -> float:
    if align in ("Center",):
        return float(math.floor((area - size) / 2.0))
    if align in ("Right", "Bottom"):
        return float(math.floor(area - size))
    return 0.0


def _axis(
    units: np.ndarray,
    extent: float,
    length: int,
    unit: float,
    border: tuple[float, float] | None,
    tiled: bool,
    tile_align: str,
    cropped: bool,
) -> tuple[np.ndarray, np.ndarray]:
    """Source pixel coordinates and coverage for positions along one axis of an image part"""
    tile = length * unit
    valid = (units >= 0.0) & (units < (min(extent, tile) if cropped else extent))
    if border is not None:
        near, far = border[0] * unit, border[1] * unit
        if near + far > extent > 0.0:
            factor = extent / (near + far)
            near, far = near * factor, far * factor
        middle = max(extent - near - far, 1.0e-9)
        source_middle = max(length - border[0] - border[1], 0.0)
        coordinates = np.where(
            units < near,
            units / max(near, 1.0e-9) * border[0],
            np.where(
                units >= extent - far,
                length - (extent - units) / max(far, 1.0e-9) * border[1],
                border[0] + (units - near) / middle * source_middle,
            ),
        )
    elif tiled and tile_align != "Fill" and tile > 0.0:
        if tile_align in ("Right", "Bottom"):
            offset = extent % tile
        elif tile_align == "Center":
            offset = (extent % tile) / 2.0
        else:
            offset = 0.0
        coordinates = np.mod(units - offset, tile) / unit
    elif cropped:
        coordinates = units / unit
    else:
        coordinates = units / max(extent, 1.0e-9) * length
    return np.clip(np.floor(coordinates), 0, length - 1).astype(np.int64), valid


def _image(
    command: DrawCommand,
    width: int,
    height: int,
    density: tuple[float, float],
    pixels: PixelSource,
) -> np.ndarray | None:
    """The part drawn over the widget area"""
    mode, part = command.image, command.part
    source = pixels.pixels(part) if part is not None else None
    if mode is None or source is None or source.size == 0:
        return None
    if mode.mirror in ("Horizontal", "Both"):
        source = source[:, ::-1]
    if mode.mirror in ("Vertical", "Both"):
        source = source[::-1]
    rows, columns = source.shape[:2]
    size_x, size_y = part.size
    unit_x, unit_y = size_x / max(columns, 1), size_y / max(rows, 1)
    draw_x, draw_y, draw_width, draw_height = 0.0, 0.0, command.width, command.height
    if not mode.fit_to_content:
        h_align, v_align = mode.content_align
        if h_align != "Fill":
            draw_x, draw_width = _aligned_offset(h_align, command.width, size_x), size_x
        if v_align != "Fill":
            draw_y, draw_height = (
                _aligned_offset(v_align, command.height, size_y),
                size_y,
            )
    units_x = (np.arange(width) + 0.5) / density[0] - draw_x
    units_y = (np.arange(height) + 0.5) / density[1] - draw_y
    border = mode.nine_slice
    tile = mode.tile
    tiled_x, tiled_y = tile in ("Horizontal", "Both"), tile in ("Vertical", "Both")
    index_x, valid_x = _axis(
        units_x,
        draw_width,
        columns,
        unit_x,
        (border[0], border[2]) if border else None,
        tiled_x,
        mode.tile_align[0],
        tile == "Vertical",
    )
    index_y, valid_y = _axis(
        units_y,
        draw_height,
        rows,
        unit_y,
        (border[1], border[3]) if border else None,
        tiled_y,
        mode.tile_align[1],
        tile == "Horizontal",
    )
    result = source[index_y[:, None], index_x[None, :]].astype(np.float32, copy=True)
    result[~(valid_y[:, None] & valid_x[None, :])] = 0.0
    return result


def _local(
    command: DrawCommand,
    width: int,
    height: int,
    density: tuple[float, float],
    pixels: PixelSource,
    glyphs: GlyphSource,
) -> np.ndarray | None:
    """The command drawn in its own area"""
    red, green, blue, tint_alpha = (float(value) for value in command.color)
    strength = max(0.0, min(1.0, tint_alpha * float(command.opacity)))
    if strength <= 0.0:
        return None
    kind = command.kind
    if kind == "image":
        straight = _image(command, width, height, density, pixels)
        if straight is None:
            return None
        alpha = straight[..., 3] * strength
        result = np.empty_like(straight)
        result[..., 0] = straight[..., 0] * red * alpha
        result[..., 1] = straight[..., 1] * green * alpha
        result[..., 2] = straight[..., 2] * blue * alpha
        result[..., 3] = alpha
        return result
    if kind == "rect":
        coverage = np.ones((height, width), dtype=np.float32)
    elif kind == "ellipse":
        coverage = _ellipse(width, height)
    elif kind == "border":
        coverage = _frame(
            width,
            height,
            (
                int(round(command.thickness * density[0])),
                int(round(command.thickness * density[1])),
            ),
        )
    elif kind == "text" and command.text is not None:
        coverage = glyphs.coverage(
            command.text,
            command.text_style,
            width,
            height,
            command.text_origin,
            density,
        )
        if coverage is None:
            return None
    else:
        return None
    alpha = coverage.astype(np.float32) * strength
    return np.stack((alpha * red, alpha * green, alpha * blue, alpha), axis=-1)


def _draw(
    canvas: np.ndarray,
    command: DrawCommand,
    matrix: np.ndarray,
    pixels: PixelSource,
    glyphs: GlyphSource,
) -> None:
    if command.width <= 0.0 or command.height <= 0.0:
        return
    if (
        abs(matrix[0, 1]) < 1.0e-9
        and abs(matrix[1, 0]) < 1.0e-9
        and matrix[0, 0] > 0.0
        and matrix[1, 1] > 0.0
    ):
        left, top = round(matrix[0, 2]), round(matrix[1, 2])
        right = round(matrix[0, 0] * command.width + matrix[0, 2])
        bottom = round(matrix[1, 1] * command.height + matrix[1, 2])
        width, height = right - left, bottom - top
        if width <= 0 or height <= 0:
            return
        local = _local(
            command,
            width,
            height,
            (width / command.width, height / command.height),
            pixels,
            glyphs,
        )
        if local is not None:
            _over(canvas, local, left, top)
        return
    across = math.hypot(matrix[0, 0], matrix[1, 0])
    down = math.hypot(matrix[0, 1], matrix[1, 1])
    width, height = (
        max(1, round(command.width * across)),
        max(1, round(command.height * down)),
    )
    local = _local(
        command,
        width,
        height,
        (width / command.width, height / command.height),
        pixels,
        glyphs,
    )
    if local is None:
        return
    corners = matrix @ np.array(
        (
            (0.0, command.width, command.width, 0.0),
            (0.0, 0.0, command.height, command.height),
            (1.0, 1.0, 1.0, 1.0),
        )
    )
    left, top = (
        max(0, math.floor(corners[0].min())),
        max(0, math.floor(corners[1].min())),
    )
    right = min(canvas.shape[1], math.ceil(corners[0].max()))
    bottom = min(canvas.shape[0], math.ceil(corners[1].max()))
    if right <= left or bottom <= top:
        return
    try:
        inverse = np.linalg.inv(matrix)
    except np.linalg.LinAlgError:
        return
    grid_x, grid_y = np.meshgrid(
        np.arange(left, right) + 0.5, np.arange(top, bottom) + 0.5
    )
    local_x = inverse[0, 0] * grid_x + inverse[0, 1] * grid_y + inverse[0, 2]
    local_y = inverse[1, 0] * grid_x + inverse[1, 1] * grid_y + inverse[1, 2]
    inside = (
        (local_x >= 0.0)
        & (local_x < command.width)
        & (local_y >= 0.0)
        & (local_y < command.height)
    )
    column = np.clip(np.floor(local_x / command.width * width), 0, width - 1).astype(
        np.int64
    )
    row = np.clip(np.floor(local_y / command.height * height), 0, height - 1).astype(
        np.int64
    )
    warped = local[row, column]
    warped[~inside] = 0.0
    _over(canvas, warped, left, top)


def render(
    commands,
    size: tuple[float, float],
    *,
    max_dimension: int = 2048,
    pixels: PixelSource,
    glyphs: GlyphSource,
) -> tuple[np.ndarray, float]:
    """(canvas, scale) with the commands drawn in order"""
    full_width, full_height = max(1.0, float(size[0])), max(1.0, float(size[1]))
    scale = min(1.0, float(max_dimension) / max(full_width, full_height))
    canvas = np.zeros(
        (max(1, round(full_height * scale)), max(1, round(full_width * scale)), 4),
        dtype=np.float32,
    )
    screen = scale_matrix_2d(scale, scale)
    for command in commands:
        _draw(
            canvas,
            command,
            screen @ np.asarray(command.world, dtype=np.float64),
            pixels,
            glyphs,
        )
    return canvas, scale
