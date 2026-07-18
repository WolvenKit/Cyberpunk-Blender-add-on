from __future__ import annotations

import base64
import json
import zlib

try:
    import bpy
except ImportError:
    bpy = None

MANIFEST_KEY = "cp77_rig_manifest_zlib_b64"


def _armature_object(value):
    if value is None:
        return None
    if getattr(value, "type", None) == "ARMATURE":
        return value
    return None


def _plain(value):
    if isinstance(value, (str, bool, int, float)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, dict) or hasattr(value, "keys"):
        return {str(key): _plain(value[key]) for key in value.keys()}
    try:
        return [_plain(item) for item in value]
    except TypeError:
        return value


def _decode_manifest(data):
    payload = data.get(MANIFEST_KEY) if data is not None else None
    if not payload:
        return None
    try:
        raw = zlib.decompress(base64.b64decode(str(payload))).decode("utf-8")
        value = json.loads(raw)
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _indexed_strings(value):
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    if value is not None and hasattr(value, "keys"):
        keys = list(value.keys())
        try:
            keys.sort(key=lambda key: int(key))
        except (TypeError, ValueError):
            keys.sort(key=str)
        return [str(value[key]) for key in keys]
    return []


def _set_if_missing(owner, key, value):
    if owner is None or value is None or key in owner:
        return
    owner[key] = _plain(value)


def restore_legacy_rig_properties(armature):
    """Restore properties removed by the abandoned manifest experiment."""
    armature = _armature_object(armature)
    if armature is None:
        return False
    data = armature.data
    manifest = _decode_manifest(data)
    if not manifest:
        return False

    space = manifest.get("space") or {}
    _set_if_missing(data, "cp77_rig_space_contract", space.get("contract"))
    _set_if_missing(data, "cp77_model_space_axes", space.get("modelAxes"))
    _set_if_missing(data, "cp77_bone_local_basis", space.get("boneBasis"))
    _set_if_missing(data, "cp77_rig_imported_pose", manifest.get("importedPose"))

    sources = manifest.get("sourceRigs") or []
    source_paths = [str(item.get("path", "")) for item in sources if item.get("path")]
    source_components = [str(item.get("component", "")) for item in sources]
    if source_paths:
        _set_if_missing(armature, "merged_rigs", source_paths)
        _set_if_missing(armature, "rig_merge_order", source_paths)
        _set_if_missing(armature, "source_rig_file", source_paths[0])
        _set_if_missing(data, "source_rig_file", source_paths[0])

    base_source = manifest.get("baseSource") or {}
    base_path = base_source.get("path") or (source_paths[0] if source_paths else None)
    base_component = base_source.get("component")
    _set_if_missing(armature, "base_rig_json", base_path)
    _set_if_missing(armature, "base_rig_component", base_component)
    _set_if_missing(armature, "rig", base_path)

    merge = manifest.get("merge") or {}
    _set_if_missing(armature, "meta_rig_bone_count", merge.get("boneCount"))

    tracks = manifest.get("tracks") or {}
    names = tracks.get("names") or []
    if names:
        indexed = {str(index): str(name) for index, name in enumerate(names)}
        _set_if_missing(armature, "trackNames", indexed)
        _set_if_missing(data, "trackNames", indexed)
    _set_if_missing(data, "referenceTracks", tracks.get("reference"))
    _set_if_missing(data, "rig_extra_tracks", tracks.get("extra"))

    template = manifest.get("exportTemplate") or {}
    _set_if_missing(data, "cp77_rig_export_template_version", template.get("version"))
    _set_if_missing(data, "cp77_rig_export_template_zlib_b64", template.get("payload"))

    animation_sets = manifest.get("animationSets") or []
    active_index = manifest.get("activeAnimationSet", 0)
    try:
        active = animation_sets[int(active_index)] if animation_sets else None
    except (TypeError, ValueError, IndexError):
        active = animation_sets[0] if animation_sets else None
    if isinstance(active, dict):
        _set_if_missing(armature, "animset", active.get("path"))
        _set_if_missing(armature, "animation_source_rig_json", active.get("sourceRig"))
        skin = active.get("skin")
        if isinstance(skin, dict):
            _set_if_missing(
                armature,
                "cp77_skin_extras_json",
                json.dumps(skin, ensure_ascii=False, separators=(",", ":")),
            )
            _set_if_missing(armature, "rigPath", skin.get("rigPath"))
            skin_names = skin.get("trackNames") or []
            if skin_names:
                _set_if_missing(
                    armature,
                    "trackNames",
                    {str(index): str(name) for index, name in enumerate(skin_names)},
                )
        source_rest = active.get("sourceRest")
        if isinstance(source_rest, dict):
            _set_if_missing(
                armature,
                "cp77_animation_source_rest_json",
                json.dumps(source_rest, ensure_ascii=False, separators=(",", ":")),
            )

    del data[MANIFEST_KEY]
    return True


def restore_all_legacy_rig_properties():
    if bpy is None:
        return 0
    restored = 0
    for obj in bpy.data.objects:
        if getattr(obj, "type", None) == "ARMATURE":
            restored += int(restore_legacy_rig_properties(obj))
    return restored


def _json_property(owner, key):
    payload = owner.get(key) if owner is not None else None
    if not payload:
        return {}
    if isinstance(payload, dict):
        return _plain(payload)
    try:
        value = json.loads(str(payload))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def active_animation_skin(armature):
    armature = _armature_object(armature)
    if armature is None:
        return {}
    restore_legacy_rig_properties(armature)
    skin = _json_property(armature, "cp77_skin_extras_json")
    if not skin:
        skin = {}
    skin.setdefault("rigPath", str(armature.get("rigPath", "")))
    bone_names = _indexed_strings(armature.get("boneNames"))
    if bone_names:
        skin.setdefault("boneNames", bone_names)
    parents = armature.get("boneParentIndexes")
    if parents is not None:
        skin.setdefault("boneParentIndexes", [int(value) for value in parents])
    track_names = rig_track_names(armature)
    if track_names:
        skin.setdefault("trackNames", track_names)
    return skin


def active_animation_source_rest(armature):
    armature = _armature_object(armature)
    if armature is None:
        return {}
    restore_legacy_rig_properties(armature)
    return _json_property(armature, "cp77_animation_source_rest_json")


def rig_space_contract(armature):
    armature = _armature_object(armature)
    if armature is None:
        return ""
    restore_legacy_rig_properties(armature)
    return str(armature.data.get("cp77_rig_space_contract", ""))


def rig_track_names(armature):
    armature = _armature_object(armature)
    if armature is None:
        return []
    restore_legacy_rig_properties(armature)
    for owner in (armature, armature.data):
        names = _indexed_strings(owner.get("trackNames"))
        if names:
            return names
    return []
