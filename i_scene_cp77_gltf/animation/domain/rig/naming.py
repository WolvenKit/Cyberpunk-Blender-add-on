from __future__ import annotations

_BLENDER_BONE_NAME_BYTES = 63


def blender_bone_name(value: str) -> str:
    """The name Blender gives a bone created with value"""
    encoded = value.encode("utf-8")
    if len(encoded) <= _BLENDER_BONE_NAME_BYTES:
        return value
    return encoded[:_BLENDER_BONE_NAME_BYTES].decode("utf-8", "ignore")


def merged_bone_name(name: str) -> str:
    """The Blender bone a source bone name binds to"""
    value = str(name or "")
    return blender_bone_name(f"{value[:-5]}_slot" if value.endswith("_plug") else value)


def source_bone_name(name: str) -> str:
    value = str(name or "")
    return f"{value[:-5]}_plug" if value.endswith("_slot") else value


def bone_name_candidates(name: str):
    value = str(name or "")
    if not value:
        return
    yield value
    merged = merged_bone_name(value)
    if merged != value:
        yield merged
    source = source_bone_name(value)
    if source != value and source != merged:
        yield source
