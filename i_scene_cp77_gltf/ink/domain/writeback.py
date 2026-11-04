from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, fields, replace
from typing import Any

from ...assetio.values import cname_entry, cname_or_empty, float32_entry
from ..model.document import Margin, WidgetRecord, read_library, widget_data
from .layout import (
    FROM_CENTER_X,
    FROM_CENTER_Y,
    FROM_LEFT,
    FROM_TOP,
    SLOTTED_CONTAINERS,
)

_LOCALIZATION_KEY = "LocKey#"
_PAIRS = ("size", "translation", "scale", "tint")


@dataclass(frozen=True, slots=True)
class WidgetEdit:
    """New values for the widget at path"""

    path: tuple[int, ...]
    margin: Margin | None = None
    size: tuple[float, float] | None = None
    translation: tuple[float, float] | None = None
    scale: tuple[float, float] | None = None
    rotation: float | None = None
    visible: bool | None = None
    opacity: float | None = None
    tint: tuple[float, float, float, float] | None = None
    text: str | None = None
    font_size: float | None = None


def moved_margin(widget: WidgetRecord, dx: float, dy: float) -> Margin:
    """The margin that moves widget by (dx, dy) in its parent's area"""
    margin = widget.layout.margin
    if widget.parent is None:
        return margin
    left, top, right, bottom = margin.left, margin.top, margin.right, margin.bottom
    anchor = widget.layout.anchor
    if widget.parent.type in SLOTTED_CONTAINERS or anchor == "Fill":
        return Margin(left + dx, top + dy, right - dx, bottom - dy)
    if anchor in FROM_LEFT or anchor in FROM_CENTER_X:
        left += dx
    else:
        right -= dx
    if anchor in FROM_TOP or anchor in FROM_CENTER_Y or anchor == "BottomCenter":
        top += dy
    else:
        bottom -= dy
    return Margin(left, top, right, bottom)


def _changes(edit: WidgetEdit) -> dict[str, Any]:
    return {
        field.name: value
        for field in fields(edit)
        if field.name != "path" and (value := getattr(edit, field.name)) is not None
    }


def merged(edits: Iterable[WidgetEdit]) -> list[WidgetEdit]:
    """One edit per widget, in the order the widgets were first edited, later values replacing earlier ones"""
    by_path: dict[tuple[int, ...], WidgetEdit] = {}
    for edit in edits:
        earlier = by_path.get(edit.path)
        by_path[edit.path] = (
            edit if earlier is None else replace(earlier, **_changes(edit))
        )
    return list(by_path.values())


def edits_to_json(edits: Iterable[WidgetEdit]) -> str:
    """Edits as JSON text, to keep with a scene"""
    entries = []
    for edit in edits:
        entry: dict[str, Any] = {"path": list(edit.path)}
        for name, value in _changes(edit).items():
            if isinstance(value, Margin):
                value = [value.left, value.top, value.right, value.bottom]
            entry[name] = list(value) if isinstance(value, tuple) else value
        entries.append(entry)
    return json.dumps(entries)


def edits_from_json(text: str) -> list[WidgetEdit]:
    """Edits from edits_to_json text"""
    names = {field.name for field in fields(WidgetEdit)} - {"path"}
    edits = []
    for entry in json.loads(text) if text else ():
        values: dict[str, Any] = {}
        for name, value in entry.items():
            if name not in names:
                continue
            if name == "margin":
                value = Margin(*(float(side) for side in value))
            elif name in _PAIRS:
                value = tuple(float(component) for component in value)
            elif name == "visible":
                value = bool(value)
            elif name == "text":
                value = str(value)
            else:
                value = float(value)
            values[name] = value
        edits.append(
            WidgetEdit(path=tuple(int(index) for index in entry["path"]), **values)
        )
    return edits


def _vector2(data: dict, key: str, value: tuple[float, float]) -> None:
    entry = data.get(key)
    if not isinstance(entry, dict):
        entry = data[key] = {"$type": "Vector2"}
    entry["X"], entry["Y"] = float32_entry(value[0]), float32_entry(value[1])


def _render_transform(data: dict) -> dict:
    entry = data.get("renderTransform")
    if not isinstance(entry, dict):
        entry = data["renderTransform"] = {"$type": "inkUITransform", "rotation": 0}
        for key, default in (
            ("scale", (1.0, 1.0)),
            ("shear", (0.0, 0.0)),
            ("translation", (0.0, 0.0)),
        ):
            _vector2(entry, key, default)
    return entry


def _margin(data: dict, margin: Margin) -> None:
    layout = data.get("layout")
    if not isinstance(layout, dict):
        layout = data["layout"] = {"$type": "inkWidgetLayout"}
    entry = layout.get("margin")
    if not isinstance(entry, dict):
        entry = layout["margin"] = {
            "$type": "inkMargin",
            "bottom": 0,
            "left": 0,
            "right": 0,
            "top": 0,
        }
    for side in ("left", "top", "right", "bottom"):
        entry[side] = float32_entry(getattr(margin, side))


def _tint(data: dict, tint: tuple[float, float, float, float]) -> None:
    entry = data.get("tintColor")
    if not isinstance(entry, dict) or entry.get("$type") != "HDRColor":
        entry = data["tintColor"] = {
            "$type": "HDRColor",
            "Alpha": 1,
            "Blue": 1,
            "Green": 1,
            "Red": 1,
        }
    for key, value in zip(("Red", "Green", "Blue", "Alpha"), tint):
        entry[key] = float32_entry(value)


def _text(data: dict, text: str) -> None:
    """Set the text a text widget shows"""
    localization = data.get("localizationString")
    if text.startswith(_LOCALIZATION_KEY):
        if not isinstance(localization, dict):
            localization = data["localizationString"] = {"unk1": "0", "value": ""}
        localization["value"] = text
        return
    data["text"] = text
    if isinstance(localization, dict) and localization.get("value"):
        localization["value"] = ""
    if cname_or_empty(data.get("textIdKey")):
        data["textIdKey"] = cname_entry("None", data.get("textIdKey"))


def _write(data: dict, edit: WidgetEdit) -> None:
    if edit.margin is not None:
        _margin(data, edit.margin)
    if edit.size is not None:
        _vector2(data, "size", edit.size)
    if edit.translation is not None:
        _vector2(_render_transform(data), "translation", edit.translation)
    if edit.scale is not None:
        _vector2(_render_transform(data), "scale", edit.scale)
    if edit.rotation is not None:
        _render_transform(data)["rotation"] = float32_entry(edit.rotation)
    if edit.visible is not None:
        data["visible"] = 1 if edit.visible else 0
    if edit.opacity is not None:
        data["opacity"] = float32_entry(edit.opacity)
    if edit.tint is not None:
        _tint(data, edit.tint)
    if edit.text is not None:
        _text(data, edit.text)
    if edit.font_size is not None:
        data["fontSize"] = max(0, int(round(edit.font_size)))


def apply_edits(document: dict, item_name: str, edits: Iterable[WidgetEdit]) -> int:
    """Write edits into every buffer of the named item of a widget library document"""
    edits = tuple(edits)
    trees = read_library(document).item_trees(item_name)
    for _buffer, tree in trees:
        for edit in edits:
            _write(widget_data(tree, edit.path), edit)
    return len(trees)
