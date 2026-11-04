from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from ...animation.model.animgraph.frames import TrackSnapshot
from ...bartmoss.qs_transform import QsTransform

SNAPSHOT_VERSION = 2


def encode_snapshot(
    armature: Any,
    transforms: Mapping[str, QsTransform],
    tracks: Mapping[str, TrackSnapshot],
    *,
    frame: float = 0.0,
    action_name: str = "",
) -> str:
    payload = {
        "version": SNAPSHOT_VERSION,
        "armature": str(getattr(armature, "name", "") or ""),
        "frame": float(frame),
        "action": str(action_name or ""),
        "bones": {
            name: {
                "translation": list(transform.translation),
                "rotation": list(transform.rotation_xyzw),
                "scale": list(transform.scale),
            }
            for name, transform in transforms.items()
        },
        "tracks": {
            name: {"existed": bool(snapshot.existed), "value": float(snapshot.value)}
            for name, snapshot in tracks.items()
        },
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def decode_snapshot(
    text: str,
) -> tuple[dict[str, Any], dict[str, QsTransform], dict[str, TrackSnapshot]]:
    payload = json.loads(str(text or ""))
    if (
        not isinstance(payload, dict)
        or int(payload.get("version", 0)) != SNAPSHOT_VERSION
    ):
        raise ValueError("Unsupported AnimGraph pose preview snapshot")
    raw_bones = payload.get("bones")
    raw_tracks = payload.get("tracks", {})
    if not isinstance(raw_bones, dict) or not isinstance(raw_tracks, dict):
        raise ValueError("AnimGraph pose preview snapshot is malformed")
    bones = {}
    for name, raw in raw_bones.items():
        if not isinstance(raw, dict):
            continue
        bones[str(name)] = QsTransform.from_components(
            raw.get("translation", (0.0, 0.0, 0.0)),
            raw.get("rotation", (0.0, 0.0, 0.0, 1.0)),
            raw.get("scale", (1.0, 1.0, 1.0)),
        )
    tracks = {}
    for name, raw in raw_tracks.items():
        if not isinstance(raw, dict):
            continue
        tracks[str(name)] = TrackSnapshot(
            bool(raw.get("existed", False)),
            float(raw.get("value", 0.0) or 0.0),
        )
    metadata = {
        "armature": str(payload.get("armature", "") or ""),
        "frame": float(payload.get("frame", 0.0) or 0.0),
        "action": str(payload.get("action", "") or ""),
    }
    return metadata, bones, tracks
