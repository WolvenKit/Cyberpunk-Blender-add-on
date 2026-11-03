from __future__ import annotations

import json
from collections.abc import Iterable

from ...assetio.atomic import atomic_write_json
from ...assetio.files import read_bytes
from ...assetio.json_style import JsonStyle, json_style
from ..domain.writeback import WidgetEdit, apply_edits


def edited_document(
    widget_path: str, item_name: str, edits: Iterable[WidgetEdit]
) -> tuple[dict, JsonStyle]:
    """The library at widget_path with edits written to its item named item_name"""
    text = read_bytes(widget_path).decode("utf-8-sig")
    document = json.loads(text)
    apply_edits(document, item_name, edits)
    return document, json_style(text)


def export_library(
    widget_path: str, item_name: str, edits: Iterable[WidgetEdit], target_path: str = ""
) -> str:
    """Write edits to the item named item_name and save the library to target_path"""
    document, style = edited_document(widget_path, item_name, edits)
    target = target_path or widget_path
    atomic_write_json(target, document, style=style)
    return target
