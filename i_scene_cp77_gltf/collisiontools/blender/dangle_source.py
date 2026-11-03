from __future__ import annotations

import bpy

from ...assetio import animgraph_json as json_io
from ...exporters.animgraph.dangle_patch import AnimGraphPatchError


def source_text(rig: bpy.types.Object) -> bpy.types.Text | None:
    name = str(getattr(rig.dangle_state, "animgraph_source_text", "") or "")
    return bpy.data.texts.get(name) if name else None


def decode_graph_json(raw: str) -> dict:
    value = json_io.loads(raw)
    if not isinstance(value, dict):
        raise AnimGraphPatchError("AnimGraph JSON root must be an object")
    return value


def load_source_payload(rig: bpy.types.Object) -> dict:
    text = source_text(rig)
    if text is None:
        raise AnimGraphPatchError(
            "This Dangle rig has no imported AnimGraph source document. Import a .animgraph.json first."
        )
    raw = text.as_string()
    try:
        return decode_graph_json(raw)
    except Exception as exc:
        raise AnimGraphPatchError(
            f"Stored AnimGraph source JSON is invalid: {exc}"
        ) from exc
