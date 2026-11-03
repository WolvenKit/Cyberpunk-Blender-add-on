from __future__ import annotations

from ...assetio.paths import local_path_key
from ...blender.rig_metadata import source_rig_part_bindings, source_rig_paths


def animation_rig_export_entries(armature) -> tuple[tuple[str, str], ...]:
    bindings = source_rig_part_bindings(armature)
    labels_by_path = {}
    for binding in bindings:
        label = str(binding.get("component", "") or "")
        if not label:
            continue
        for key in ("path", "source_path"):
            path = str(binding.get(key, "") or "")
            if path:
                labels_by_path.setdefault(local_path_key(path), label)

    entries = []
    for path in source_rig_paths(armature):
        normalized = str(path).replace("\\", "/")
        filename = normalized.rsplit("/", 1)[-1]
        if filename.casefold().endswith(".rig.json"):
            filename = filename[:-9]
        label = labels_by_path.get(local_path_key(path), "")
        display_name = (
            f"{label} — {filename}"
            if label and label != filename
            else (label or filename)
        )
        entries.append((str(path), display_name))
    return tuple(entries)
