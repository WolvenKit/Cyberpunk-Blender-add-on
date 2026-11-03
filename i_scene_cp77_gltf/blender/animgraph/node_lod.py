from __future__ import annotations

from . import sm_overlay

# Blender's ``uiItemS_ex`` spaces a separator by ``0.3 * UI_UNIT_X`` (20 at UI scale 1) per factor.
_SEPARATOR_UNIT = 0.3 * 20.0
# Node body text is about 11 view units high at UI scale 1; below this many pixels it cannot be read.
_MIN_TEXT_PIXELS = 5.0
_BODY_TEXT_UNITS = 11.0
# View units kept around the region at UI scale 1, so nodes entering at an edge are already full.
_MARGIN_UNITS = 60.0

# node pointer -> (layout signature, full height in view units, separator factor last drawn or None)
_STATES: dict[int, tuple] = {}


def reset() -> None:
    _STATES.clear()


def _signature(node) -> tuple:
    properties = getattr(node, "red_properties", None)
    return (
        len(node.inputs),
        len(node.outputs),
        len(properties) if properties is not None else 0,
        float(node.width),
    )


def _shows_detail(node, region, scale: float) -> bool:
    view = region.view2d
    left, bottom = view.region_to_view(0.0, 0.0)
    right, top = view.region_to_view(float(region.width), float(region.height))
    width = right - left
    if (
        width <= 0.0
        or region.width / width * _BODY_TEXT_UNITS * scale < _MIN_TEXT_PIXELS
    ):
        return False
    margin = _MARGIN_UNITS * scale
    location = node.location_absolute
    node_left = location.x * scale
    node_top = location.y * scale
    dimensions = node.dimensions
    return (
        node_left - margin <= right
        and node_left + dimensions.x + margin >= left
        and node_top + margin >= bottom
        and node_top - dimensions.y - margin <= top
    )


def _initial_factor(node, full_height: float, scale: float) -> float:
    frame = (
        sm_overlay.HEADER_DY
        + sm_overlay.ROW_DY
        * (
            len(sm_overlay.drawn_sockets(node.outputs))
            + len(sm_overlay.drawn_sockets(node.inputs))
        )
        + sm_overlay.FOOTER_DY
    ) * scale
    return max(0.0, (full_height - frame) / (_SEPARATOR_UNIT * scale))


def draw_placeholder(node, context, layout) -> bool:
    """Draw a spacer instead of the node body when the body cannot be seen"""
    region = getattr(context, "region", None)
    if region is None or region.type != "WINDOW" or node.hide:
        return False
    key = node.as_pointer()
    scale = sm_overlay.ui_scale(node)
    signature = _signature(node)
    state = _STATES.get(key)
    if _shows_detail(node, region, scale):
        # The previous layout was a full body when no spacer was drawn, so its height is the full height.
        full_height = (
            float(node.dimensions.y) if state is None or state[2] is None else None
        )
        if full_height is None and state[0] == signature:
            full_height = state[1]
        _STATES[key] = (signature, full_height if full_height else 0.0, None)
        return False
    if state is None or state[0] != signature:
        _STATES[key] = (signature, 0.0, None)
        return False
    _, full_height, factor = state
    if factor is None:
        full_height = float(node.dimensions.y)
        if full_height <= 0.0:
            return False
        factor = _initial_factor(node, full_height, scale)
    else:
        factor = max(
            0.0,
            factor
            + (full_height - float(node.dimensions.y)) / (_SEPARATOR_UNIT * scale),
        )
    _STATES[key] = (signature, full_height, factor)
    layout.separator(factor=factor)
    return True
