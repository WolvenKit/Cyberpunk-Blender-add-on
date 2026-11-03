from __future__ import annotations

import math

from ...ink.domain.writeback import WidgetEdit, moved_margin
from ...ink.model.document import LibraryItem
from .hierarchy import BASE_KEY, handles

_TOLERANCE = 1.0e-4


def viewport_edits(root, item: LibraryItem) -> list[WidgetEdit]:
    """Edits for the handles of root moved, turned or scaled since they were placed"""
    records = {widget.path: widget for widget in item.widgets}
    edits = []
    for path, handle in handles(root).items():
        widget, base = records.get(path), handle.get(BASE_KEY)
        if widget is None or base is None or len(base) != 5:
            continue
        x, y, turn, scale_x, scale_y = (float(value) for value in base)
        changes = {}
        dx, dy = handle.location.x - x, handle.location.y - y
        if abs(dx) > _TOLERANCE or abs(dy) > _TOLERANCE:
            # Handles are y up, widgets y down.
            if widget.parent is None:
                translation = widget.render.translation
                changes["translation"] = (translation[0] + dx, translation[1] - dy)
            else:
                changes["margin"] = moved_margin(widget, dx, -dy)
        if abs(handle.rotation_euler.z - turn) > _TOLERANCE:
            changes["rotation"] = -math.degrees(handle.rotation_euler.z)
        if (
            abs(handle.scale.x - scale_x) > _TOLERANCE
            or abs(handle.scale.y - scale_y) > _TOLERANCE
        ):
            changes["scale"] = (handle.scale.x, handle.scale.y)
        if changes:
            edits.append(WidgetEdit(path=path, **changes))
    return edits
