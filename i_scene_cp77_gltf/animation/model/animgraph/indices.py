from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ....assetio.values import cname_entry


def cname(value: str) -> dict:
    """A CName entry, with an empty name written as the null name 'None'"""
    return cname_entry(str(value or "None"))


def transform_index(value: str) -> dict:
    return {"$type": "animTransformIndex", "name": cname(value or "None")}


def track_index(value: str) -> dict:
    return {"$type": "animNamedTrackIndex", "name": cname(value or "None")}


def index_name(value: Any, expected_type: str, *, allow_text: bool = False) -> str:
    if allow_text and isinstance(value, str):
        return "" if value == "None" else value
    if not isinstance(value, Mapping) or value.get("$type") != expected_type:
        return ""
    name = value.get("name")
    if not isinstance(name, Mapping):
        return ""
    text = str(name.get("$value", "") or "")
    return "" if text == "None" else text
