from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np

from ...assetio.values import coerce_float, vector2
from ...bartmoss.affine import (
    rotation_matrix_2d,
    scale_matrix_2d,
    shear_matrix_2d,
    translation_matrix_2d,
)
from ..model.document import WidgetRecord, margin

_HORIZONTAL_PANEL = "inkHorizontalPanelWidget"
_VERTICAL_PANEL = "inkVerticalPanelWidget"
_FLEX = "inkFlexWidget"
_GRID = "inkGridWidget"
_UNIFORM_GRID = "inkUniformGridWidget"
_IDENTITY = np.identity(3, dtype=np.float64)
# Containers that place each child in a slot; every other container places its children by anchor.
SLOTTED_CONTAINERS = frozenset(
    {_HORIZONTAL_PANEL, _VERTICAL_PANEL, _FLEX, _GRID, _UNIFORM_GRID}
)
# Canvas anchors by what positions a child: x from the left margin, from the parent's centre, else from the right
# margin; y from the top margin, from the centre, from the bottom edge plus the top margin (BottomCenter), else from
# the bottom margin. Partial fills take their position from the near margin.
HORIZONTAL_FILLS = frozenset(
    {"TopFillHorizontaly", "CenterFillHorizontaly", "BottomFillHorizontaly"}
)
VERTICAL_FILLS = frozenset(
    {"LeftFillVerticaly", "CenterFillVerticaly", "RightFillVerticaly"}
)
FROM_LEFT = (
    frozenset({"TopLeft", "CenterLeft", "BottomLeft", "LeftFillVerticaly"})
    | HORIZONTAL_FILLS
)
FROM_CENTER_X = frozenset(
    {"TopCenter", "Centered", "BottomCenter", "CenterFillVerticaly"}
)
FROM_TOP = (
    frozenset({"TopLeft", "TopCenter", "TopRight", "TopFillHorizontaly"})
    | VERTICAL_FILLS
)
FROM_CENTER_Y = frozenset(
    {"CenterLeft", "Centered", "CenterRight", "CenterFillHorizontaly"}
)


class LayoutFacts(Protocol):
    """What the layout needs beyond the widget records"""

    def bound(self, widget: WidgetRecord) -> dict[str, Any]:
        """Values the widget's style bindings set (tintColor, opacity, visible, ...)"""

    def content_size(self, widget: WidgetRecord) -> tuple[float, float] | None:
        """The size a fit-to-content leaf takes from its content (an image's part, a text's block), or None"""


@dataclass(slots=True, eq=False)
class LaidOutWidget:
    widget: WidgetRecord
    parent: LaidOutWidget | None
    bound: dict
    visible: bool
    keeps_layout: bool
    opacity: float
    tint: tuple[float, float, float, float]
    size: tuple[float, float] = (0.0, 0.0)
    override: dict = field(default_factory=dict)
    desired: tuple[float, float] = (0.0, 0.0)
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    arranged: bool = False
    local: np.ndarray = field(default_factory=lambda: _IDENTITY.copy())
    world: np.ndarray = field(default_factory=lambda: _IDENTITY.copy())
    children: list[LaidOutWidget] = field(default_factory=list)


@dataclass(slots=True)
class LaidOutItem:
    root: LaidOutWidget
    widgets: list[LaidOutWidget]

    @property
    def size(self) -> tuple[float, float]:
        return self.root.width, self.root.height

    def find(self, path: tuple[int, ...]) -> LaidOutWidget | None:
        return next(
            (entry for entry in self.widgets if entry.widget.path == tuple(path)), None
        )


@dataclass(slots=True)
class _Rect:
    x: float
    y: float
    width: float
    height: float


def _align_horizontal(align: str, rect: _Rect, area: _Rect) -> _Rect:
    result = _Rect(rect.x, rect.y, rect.width, rect.height)
    if align == "Left":
        result.x = math.floor(area.x)
    elif align == "Right":
        result.x = math.floor(area.x + area.width - rect.width)
    elif align == "Center":
        result.x = math.floor(area.x + (area.width - rect.width) / 2.0)
    elif align == "Fill":
        result.x, result.width = math.floor(area.x), math.floor(area.width)
    return result


def _align_vertical(align: str, rect: _Rect, area: _Rect) -> _Rect:
    result = _Rect(rect.x, rect.y, rect.width, rect.height)
    if align == "Bottom":
        result.y = math.floor(area.y + area.height - rect.height)
    elif align == "Top":
        result.y = math.floor(area.y)
    elif align == "Center":
        result.y = math.floor(area.y + (area.height - rect.height) / 2.0)
    elif align == "Fill":
        result.y, result.height = math.floor(area.y), math.floor(area.height)
    return result


def anchor_rect(parent_size: tuple[float, float], child: LaidOutWidget) -> _Rect:
    """A canvas child's area"""
    width, height = parent_size
    layout = child.widget.layout
    left, top, right, bottom = (
        layout.margin.left,
        layout.margin.top,
        layout.margin.right,
        layout.margin.bottom,
    )
    size_x, size_y = child.desired
    point_x, point_y = layout.anchor_point
    anchor = layout.anchor
    if anchor == "Fill":
        return _Rect(left, top, width - (right + left), height - (bottom + top))
    horizontal_fill = anchor in HORIZONTAL_FILLS
    vertical_fill = anchor in VERTICAL_FILLS
    if anchor in FROM_LEFT:
        x = left
    elif anchor in FROM_CENTER_X:
        x = width / 2.0 + (left - right)
    else:
        x = width - right
    if anchor in FROM_TOP:
        y = top
    elif anchor in FROM_CENTER_Y:
        y = height / 2.0 + (top - bottom)
    elif anchor == "BottomCenter":
        y = height + (top - bottom)
    else:
        y = height - bottom
    if horizontal_fill:
        size_x = width - right
    if vertical_fill:
        size_y = height - bottom
    x -= 0.0 if horizontal_fill else point_x * size_x
    y -= 0.0 if vertical_fill else point_y * size_y
    return _Rect(x, y, size_x, size_y)


def _ordered(node: LaidOutWidget) -> list[LaidOutWidget]:
    return (
        list(reversed(node.children))
        if node.widget.child_order == "Backward"
        else list(node.children)
    )


def _grid_step(
    size: tuple[float, float], step: tuple[float, float]
) -> tuple[float, float]:
    width, height = size
    if step[0]:
        width = math.ceil(width / step[0]) * step[0]
    if step[1]:
        height = math.ceil(height / step[1]) * step[1]
    return width, height


def _grid_layout(node: LaidOutWidget) -> tuple[dict[int, _Rect], _Rect | None]:
    """Child areas of a grid"""
    data = node.widget.data
    padding = node.widget.layout.padding
    child_padding = margin(data.get("childPadding"))
    step = vector2(data.get("childSizeStep"))
    vertical = str(data.get("orientation") or "Horizontal") == "Vertical"
    grid_width = node.size[0] - padding.horizontal
    grid_height = node.size[1] - padding.vertical
    current_x, current_y, longest = padding.left, padding.top, 0.0
    rects: dict[int, _Rect] = {}
    last = None
    for child in _ordered(node):
        if not child.keeps_layout:
            continue
        child_margin = child.widget.layout.margin
        width, height = _grid_step(child.desired, step)
        outer_width = width + child_margin.horizontal + child_padding.horizontal
        outer_height = height + child_margin.vertical + child_padding.vertical
        offset_x, offset_y = (
            child_margin.left + child_padding.left,
            child_margin.top + child_padding.top,
        )
        if vertical:
            if current_x + outer_width > grid_width:
                current_x = outer_width + padding.left
                current_y += longest
                rect = _Rect(
                    offset_x + padding.left, current_y + offset_y, width, height
                )
                longest = outer_height
            else:
                rect = _Rect(current_x + offset_x, current_y + offset_y, width, height)
                current_x += outer_width
                longest = max(longest, outer_height)
        else:
            if current_y + outer_height > grid_height:
                current_y = outer_height + padding.top
                current_x += longest
                rect = _Rect(
                    current_x + offset_x + padding.top, offset_y, width, height
                )
                longest = outer_width
            else:
                rect = _Rect(current_x + offset_x, current_y + offset_y, width, height)
                current_y += outer_height
                longest = max(longest, outer_width)
        rects[id(child)] = rect
        last = rect
    return rects, last


def _uniform_dimension(node: LaidOutWidget) -> tuple[float, float]:
    count = float(len(node.children))
    wrapping = max(
        1.0,
        float(
            math.ceil(coerce_float(node.widget.data.get("wrappingWidgetCount"), 0.0))
        ),
    )
    span = float(math.ceil(count / wrapping))
    if str(node.widget.data.get("orientation") or "Horizontal") == "Horizontal":
        return wrapping, span
    return span, wrapping


def _uniform_cell(node: LaidOutWidget) -> tuple[float, float]:
    if node.widget.fit_to_content:
        child_margin = node.widget.child_margin
        width = height = 0.0
        for child in node.children:
            if child.keeps_layout:
                layout_margin = child.widget.layout.margin
                width = max(
                    width,
                    child.desired[0]
                    + layout_margin.horizontal
                    + child_margin.horizontal,
                )
                height = max(
                    height,
                    child.desired[1] + layout_margin.vertical + child_margin.vertical,
                )
        return width, height
    columns, rows = _uniform_dimension(node)
    return node.size[0] / max(columns, 1.0), node.size[1] / max(rows, 1.0)


def _desired(node: LaidOutWidget, facts: LayoutFacts) -> tuple[float, float]:
    widget = node.widget
    kind = widget.type
    if kind in (_HORIZONTAL_PANEL, _VERTICAL_PANEL):
        if not widget.fit_to_content:
            return node.size
        child_margin = widget.child_margin
        main = cross = 0.0
        for child in node.children:
            if not child.keeps_layout:
                continue
            layout_margin = child.widget.layout.margin
            width = (
                child.desired[0] + layout_margin.horizontal + child_margin.horizontal
            )
            height = child.desired[1] + layout_margin.vertical + child_margin.vertical
            if kind == _HORIZONTAL_PANEL:
                main, cross = main + width, max(cross, height)
            else:
                main, cross = main + height, max(cross, width)
        padding = widget.layout.padding
        size = (main, cross) if kind == _HORIZONTAL_PANEL else (cross, main)
        return size[0] + padding.horizontal, size[1] + padding.vertical
    if kind == _FLEX:
        if not node.children:
            return node.size
        width = height = 0.0
        for child in node.children:
            if not child.keeps_layout:
                continue
            layout = child.widget.layout
            if layout.h_align != "Fill":
                width = max(width, child.desired[0] + layout.margin.horizontal)
            if layout.v_align != "Fill":
                height = max(height, child.desired[1] + layout.margin.vertical)
        return width, height
    if kind == _GRID:
        if not node.children:
            return node.size
        _rects, last = _grid_layout(node)
        padding = widget.layout.padding
        width, height = (
            node.size[0] - padding.horizontal,
            node.size[1] - padding.vertical,
        )
        if last is not None:
            if str(widget.data.get("orientation") or "Horizontal") == "Horizontal":
                width = last.x + last.width
            else:
                height = last.y + last.height
        final = node.children[-1].widget.layout.margin
        child_padding = margin(widget.data.get("childPadding"))
        return (
            width + final.right + child_padding.right + padding.right,
            height + final.bottom + child_padding.bottom + padding.bottom,
        )
    if kind == _UNIFORM_GRID:
        if not widget.fit_to_content:
            return node.size
        columns, rows = _uniform_dimension(node)
        cell = _uniform_cell(node)
        return columns * cell[0], rows * cell[1]
    if widget.is_compound or not widget.fit_to_content:
        return node.size
    content = facts.content_size(widget)
    return content if content is not None else node.size


def _place(child: LaidOutWidget, rect: _Rect, arranged: bool) -> None:
    child.x, child.y, child.width, child.height = (
        rect.x,
        rect.y,
        rect.width,
        rect.height,
    )
    child.arranged = arranged


def _arrange_panel(node: LaidOutWidget) -> None:
    widget = node.widget
    horizontal = widget.type == _HORIZONTAL_PANEL
    padding, child_margin = widget.layout.padding, widget.child_margin
    available = _Rect(
        padding.left,
        padding.top,
        node.width - padding.horizontal,
        node.height - padding.vertical,
    )
    stretch_total = fixed_total = 0.0
    for child in node.children:
        if not child.keeps_layout:
            continue
        layout = child.widget.layout
        if layout.size_rule == "Stretch":
            stretch_total += layout.size_coefficient
        elif horizontal:
            fixed_total += (
                layout.margin.horizontal + child_margin.horizontal + child.desired[0]
            )
        else:
            fixed_total += (
                layout.margin.vertical + child_margin.vertical + child.desired[1]
            )
    if stretch_total < 0.00001:
        stretch_total = 1.0
    free = max(0.0, (available.width if horizontal else available.height) - fixed_total)
    next_x, next_y = padding.left, padding.top
    for child in _ordered(node):
        layout = child.widget.layout
        outer_width = (
            child.desired[0] + layout.margin.horizontal + child_margin.horizontal
        )
        outer_height = child.desired[1] + layout.margin.vertical + child_margin.vertical
        rect = _Rect(
            next_x,
            next_y,
            min(outer_width, available.width),
            min(outer_height, available.height),
        )
        advance = 0.0
        if horizontal:
            rect = _align_vertical(layout.v_align, rect, available)
            if layout.size_rule == "Stretch":
                share = free * layout.size_coefficient / stretch_total
                if layout.h_align != "Fill":
                    helper = _align_horizontal(
                        layout.h_align, rect, _Rect(0.0, 0.0, share, share)
                    )
                    rect.x += max(0.0, helper.x)
                    rect.width = min(rect.width, share)
                else:
                    rect.width = share
                advance = share
            else:
                advance = rect.width
        else:
            rect = _align_horizontal(layout.h_align, rect, available)
            if layout.size_rule == "Stretch":
                share = free * layout.size_coefficient / stretch_total
                if layout.v_align != "Fill":
                    helper = _align_vertical(
                        layout.v_align, rect, _Rect(0.0, 0.0, share, share)
                    )
                    rect.y += max(0.0, helper.y)
                    rect.height = min(rect.height, share)
                else:
                    rect.height = share
                advance = share
            else:
                advance = rect.height
        area = _Rect(
            rect.x + layout.margin.left + child_margin.left,
            rect.y + layout.margin.top + child_margin.top,
            rect.width - layout.margin.horizontal - child_margin.horizontal,
            rect.height - layout.margin.vertical - child_margin.vertical,
        )
        _place(child, area, child.keeps_layout)
        if child.keeps_layout:
            if horizontal:
                next_x += advance
            else:
                next_y += advance


def _arrange_flex(node: LaidOutWidget) -> None:
    area = _Rect(node.x, node.y, node.width, node.height)
    for child in node.children:
        layout = child.widget.layout
        outer = _Rect(
            0.0,
            0.0,
            child.desired[0] + layout.margin.horizontal,
            child.desired[1] + layout.margin.vertical,
        )
        vertical = _align_vertical(layout.v_align, outer, area)
        horizontal = _align_horizontal(layout.h_align, outer, area)
        width = horizontal.width if layout.h_align == "Fill" else outer.width
        height = vertical.height if layout.v_align == "Fill" else outer.height
        _place(
            child,
            _Rect(
                horizontal.x + layout.margin.left - area.x,
                vertical.y + layout.margin.top - area.y,
                width - layout.margin.horizontal,
                height - layout.margin.vertical,
            ),
            child.keeps_layout,
        )


def _arrange_uniform_grid(node: LaidOutWidget) -> None:
    padding, child_margin = node.widget.layout.padding, node.widget.child_margin
    cell_width, cell_height = _uniform_cell(node)
    wrapping = max(
        1,
        int(math.ceil(coerce_float(node.widget.data.get("wrappingWidgetCount"), 0.0))),
    )
    horizontal = (
        str(node.widget.data.get("orientation") or "Horizontal") == "Horizontal"
    )
    next_x, next_y = padding.left, padding.top
    for index, child in enumerate(_ordered(node)):
        layout = child.widget.layout
        if not child.keeps_layout:
            _place(
                child,
                _Rect(
                    next_x + layout.margin.left,
                    next_y + layout.margin.top,
                    *child.desired,
                ),
                False,
            )
            continue
        margins_x = layout.margin.horizontal + child_margin.horizontal
        margins_y = layout.margin.vertical + child_margin.vertical
        if layout.size_rule == "Stretch":
            area = _Rect(
                next_x + layout.margin.left + child_margin.left,
                next_y + layout.margin.top + child_margin.top,
                cell_width - margins_x,
                cell_height - margins_y,
            )
        else:
            cell = _Rect(next_x, next_y, cell_width, cell_height)
            rect = _Rect(
                next_x,
                next_y,
                min(child.desired[0] + margins_x, cell_width),
                min(child.desired[1] + margins_y, cell_height),
            )
            rect = _align_vertical(
                layout.v_align, _align_horizontal(layout.h_align, rect, cell), cell
            )
            area = _Rect(
                rect.x + layout.margin.left + child_margin.left,
                rect.y + layout.margin.top + child_margin.top,
                rect.width - margins_x,
                rect.height - margins_y,
            )
        _place(child, area, True)
        if (index + 1) % wrapping == 0:
            if horizontal:
                next_x, next_y = 0.0, next_y + cell_height
            else:
                next_x, next_y = next_x + cell_width, 0.0
        elif horizontal:
            next_x += cell_width
        else:
            next_y += cell_height


def _arrange(node: LaidOutWidget) -> None:
    kind = node.widget.type
    if kind in (_HORIZONTAL_PANEL, _VERTICAL_PANEL):
        _arrange_panel(node)
    elif kind == _FLEX:
        _arrange_flex(node)
    elif kind == _GRID:
        rects, _last = _grid_layout(node)
        for child in node.children:
            rect = rects.get(id(child))
            _place(child, rect or _Rect(0.0, 0.0, *child.desired), rect is not None)
    elif kind == _UNIFORM_GRID:
        _arrange_uniform_grid(node)
    else:
        for child in node.children:
            _place(
                child, anchor_rect((node.width, node.height), child), child.keeps_layout
            )
    for child in node.children:
        _arrange(child)


def render_matrix(
    widget: WidgetRecord,
    x: float,
    y: float,
    width: float,
    height: float,
    override: dict[str, Any] | None = None,
) -> np.ndarray:
    """The widget area to parent area transform"""
    render = widget.render
    override = override or {}
    translation = (
        vector2(override["translation"])
        if "translation" in override
        else render.translation
    )
    scale = (
        vector2(override["scale"], (1.0, 1.0)) if "scale" in override else render.scale
    )
    shear = vector2(override["shear"]) if "shear" in override else render.shear
    rotation = (
        coerce_float(override["rotation"], 0.0)
        if "rotation" in override
        else render.rotation
    )
    pivot_x, pivot_y = render.pivot[0] * width, render.pivot[1] * height
    return (
        translation_matrix_2d(
            x + translation[0] + pivot_x, y + translation[1] + pivot_y
        )
        @ rotation_matrix_2d(rotation)
        @ shear_matrix_2d(shear[0], shear[1])
        @ scale_matrix_2d(scale[0], scale[1])
        @ translation_matrix_2d(-pivot_x, -pivot_y)
    )


def _appearance(
    widget: WidgetRecord, bound: dict[str, Any], override: dict[str, Any]
) -> tuple[bool, float, tuple]:
    visible = bound.get("visible", widget.visible)
    opacity = override.get("opacity", bound.get("opacity", widget.opacity))
    tint = override.get("color", bound.get("tintColor", widget.tint))
    return bool(visible), float(opacity), tuple(float(value) for value in tint)


def _build(
    widget: WidgetRecord,
    parent: LaidOutWidget | None,
    facts: LayoutFacts,
    overrides: dict,
) -> LaidOutWidget:
    bound = facts.bound(widget) or {}
    override = overrides.get(widget.path) or {}
    visible, opacity, tint = _appearance(widget, bound, override)
    node = LaidOutWidget(
        widget=widget,
        parent=parent,
        bound=bound,
        visible=visible and (parent.visible if parent is not None else True),
        keeps_layout=visible or widget.affects_layout_when_hidden,
        opacity=max(
            0.0, min(1.0, (parent.opacity if parent is not None else 1.0) * opacity)
        ),
        tint=tint,
        size=vector2(override["size"], widget.size)
        if "size" in override
        else widget.size,
        override=override,
    )
    node.children = [_build(child, node, facts, overrides) for child in widget.children]
    node.desired = _desired(node, facts)
    return node


def _draw_order(node: LaidOutWidget, out: list[LaidOutWidget]) -> None:
    """The order children draw in"""
    out.append(node)
    children = list(node.children) if node.widget.type == _FLEX else _ordered(node)
    for child in [child for child in children if child.arranged] + [
        child for child in children if not child.arranged
    ]:
        _draw_order(child, out)


def _transform(node: LaidOutWidget) -> None:
    node.local = render_matrix(
        node.widget, node.x, node.y, node.width, node.height, node.override
    )
    node.world = (
        node.parent.world @ node.local if node.parent is not None else node.local
    )
    node.visible = node.visible and (node.arranged or node.parent is None)
    for child in node.children:
        if not node.visible:
            child.visible = False
        _transform(child)


def solve(item, facts: LayoutFacts, overrides: dict | None = None) -> LaidOutItem:
    """Lay out a library item the way the game arranges it"""
    root = _build(item.root, None, facts, overrides or {})
    root.width, root.height = root.desired
    root.arranged = True
    _arrange(root)
    _transform(root)
    widgets: list[LaidOutWidget] = []
    _draw_order(root, widgets)
    return LaidOutItem(root, widgets)
