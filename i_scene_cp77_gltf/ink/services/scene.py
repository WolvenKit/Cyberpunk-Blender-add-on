from __future__ import annotations

from typing import Any

from ...assetio.values import cname_text, coerce_float
from ..domain.layout import LaidOutItem, LaidOutWidget, solve
from ..domain.raster import DrawCommand, ImageMode, render
from ..domain.text import (
    TextBlock,
    TextStyle,
    block_origin,
    fit_block,
    text_content,
    text_style,
)
from ..model.document import WidgetRecord, margin
from .library import LoadedLibrary, PartSource, text_font

_SHAPES = {
    "inkRectangleWidget": "rect",
    "inkBorderWidget": "border",
    "inkCircleWidget": "ellipse",
}
_TEXT = "inkTextWidget"


class LibraryFacts:
    """Layout facts for a loaded library, with text measured by measurer"""

    def __init__(self, loaded: LoadedLibrary, measurer: Any):
        self.loaded = loaded
        self.measurer = measurer

    def bound(self, widget: WidgetRecord) -> dict[str, Any]:
        return self.loaded.bound(widget)

    def part(self, widget: WidgetRecord) -> PartSource | None:
        atlas = self.loaded.atlas_for(widget)
        name = cname_text(self.bound(widget).get("texturePart")) or cname_text(
            widget.data.get("texturePart")
        )
        return atlas.part_source(name) if atlas is not None and name else None

    def text_style(self, widget: WidgetRecord, size: tuple[float, float]) -> TextStyle:
        family, style = text_font(widget, self.bound(widget))
        return text_style(
            widget.data,
            self.bound(widget),
            font=self.loaded.font(family, style),
            size=size,
            fit_to_content=widget.fit_to_content,
        )

    def text_block(
        self, widget: WidgetRecord, size: tuple[float, float]
    ) -> tuple[TextBlock, TextStyle]:
        style = self.text_style(widget, size)
        box = (0.0, 0.0) if widget.fit_to_content else size
        return fit_block(text_content(widget.data), style, self.measurer, box), style

    def content_size(self, widget: WidgetRecord) -> tuple[float, float] | None:
        if widget.type == _TEXT:
            block, _style = self.text_block(widget, widget.size)
            return block.width, block.height
        if "textureAtlas" in widget.data:
            part = self.part(widget)
            return part.size if part is not None else None
        return None


def _image_mode(widget: WidgetRecord, part: PartSource) -> ImageMode:
    data = widget.data
    nine_slice = None
    if data.get("useNineSliceScale"):
        if part.nine_slice is not None:
            nine_slice = part.nine_slice
        else:
            unit = part.size[0] / part.rect[2] if part.rect[2] else 1.0
            sides = margin(data.get("nineSliceScale"))
            nine_slice = tuple(
                value / unit
                for value in (sides.left, sides.top, sides.right, sides.bottom)
            )
    return ImageMode(
        fit_to_content=widget.fit_to_content,
        content_align=(
            str(data.get("contentHAlign") or "Fill"),
            str(data.get("contentVAlign") or "Fill"),
        ),
        nine_slice=nine_slice,
        tile=str(data.get("tileType") or "NoTile"),
        tile_align=(
            str(data.get("tileHAlign") or "Left"),
            str(data.get("tileVAlign") or "Top"),
        ),
        mirror=str(data.get("mirrorType") or "NoMirror"),
    )


def _command(entry: LaidOutWidget, facts: LibraryFacts) -> DrawCommand | None:
    widget = entry.widget
    base = dict(
        width=entry.width,
        height=entry.height,
        world=entry.world,
        color=entry.tint,
        opacity=entry.opacity,
        path=widget.path,
    )
    kind = _SHAPES.get(widget.type)
    if kind is not None:
        return DrawCommand(
            kind=kind, thickness=coerce_float(widget.data.get("thickness"), 2.0), **base
        )
    if widget.type == _TEXT:
        block, style = facts.text_block(widget, (entry.width, entry.height))
        if not block.lines or not any(line.text for line in block.lines):
            return None
        return DrawCommand(
            kind="text",
            text=block,
            text_style=style,
            text_origin=block_origin(block, (entry.width, entry.height), style),
            **base,
        )
    if "textureAtlas" in widget.data:
        part = facts.part(widget)
        if part is None:
            return None
        return DrawCommand(
            kind="image", part=part, image=_image_mode(widget, part), **base
        )
    return None


def draw_commands(
    laid_out: LaidOutItem, facts: LibraryFacts
) -> tuple[list[DrawCommand], set[str]]:
    """(commands in draw order, types of visible widgets that are not drawn)"""
    commands, undrawn = [], set()
    for entry in laid_out.widgets:
        if not entry.visible or entry.widget.is_compound or entry.opacity <= 0.0:
            continue
        command = _command(entry, facts)
        if command is not None:
            commands.append(command)
        elif (
            entry.widget.type not in _SHAPES
            and entry.widget.type != _TEXT
            and "textureAtlas" not in entry.widget.data
        ):
            undrawn.add(entry.widget.type)
    return commands, undrawn


def solve_library(
    loaded: LoadedLibrary, measurer: Any, overrides: dict | None = None
) -> LaidOutItem:
    return solve(loaded.item, LibraryFacts(loaded, measurer), overrides)


def render_library(
    loaded: LoadedLibrary,
    fonts: Any,
    pixels: Any,
    *,
    overrides: dict | None = None,
    max_dimension: int = 2048,
):
    """(canvas, scale, laid-out item) of the library item laid out and rasterized"""
    facts = LibraryFacts(loaded, fonts)
    laid_out = solve(loaded.item, facts, overrides)
    commands, _undrawn = draw_commands(laid_out, facts)
    canvas, scale = render(
        commands,
        laid_out.size,
        max_dimension=max_dimension,
        pixels=pixels,
        glyphs=fonts,
    )
    return canvas, scale, laid_out
