from __future__ import annotations

import copy
import json
import math
import os
import struct
from dataclasses import dataclass
from typing import Any

import numpy as np

try:
    import bpy
except ImportError:
    bpy = None


from ..main.animation_glb import (
    ANIMATION_EXTRAS_SNAPSHOT_KEY,
    FPS,
    RIG_SPACE_CONTRACT,
    SOURCE_REST_SPACE_CONTRACT,
    blender_relative_to_gltf as _blender_relative_to_gltf,
    compose_trs_batch,
    decompose_trs_batch as _decompose_trs_batch,
    normalize_quaternions_xyzw as _normalize_quaternions_xyzw,
)
from ..main.rig_utils import merged_rig_bone_name
from ..main.rig_manifest import (
    active_animation_skin, active_animation_source_rest, rig_space_contract,
    rig_track_names,
)


_ANIMATION_DEFAULTS = {
    "schema": {"type": "wkit.cp2077.gltf.anims", "version": 5},
    "animationType": "Normal",
    "rootMotionType": "Unknown",
    "frameClamping": False,
    "frameClampingStartFrame": -1,
    "frameClampingEndFrame": -1,
    "numExtraJoints": 0,
    "numExtraTracks": 0,
    "constTrackKeys": [],
    "trackKeys": [],
    "fallbackFrameIndices": [],
    "optimizationHints": {"preferSIMD": False, "maxRotationCompression": 0},
    "animEvents": [],
}


class DirectAnimationExportError(RuntimeError):
    pass


@dataclass(frozen=True)
class SkeletonExportBinding:
    source_names: tuple[str, ...]
    target_names: tuple[str, ...]
    parent_indices: tuple[int, ...]
    target_bones: tuple[Any, ...]
    rest_relative_blender: np.ndarray
    rest_relative_gltf: np.ndarray
    rest_global_gltf: np.ndarray
    skin_extras: dict
    uses_source_rest_snapshot: bool


class GLBBuilder:
    def __init__(self):
        self.binary = bytearray()
        self.buffer_views: list[dict] = []
        self.accessors: list[dict] = []

    def _align(self, alignment: int = 4) -> None:
        padding = (-len(self.binary)) % alignment
        if padding:
            self.binary.extend(b"\x00" * padding)

    def add_float_accessor(
        self,
        values,
        accessor_type: str,
        *,
        name: str | None = None,
        matrix_column_major: bool = False,
        include_bounds: bool = True,
    ) -> int:
        array = np.asarray(values, dtype=np.float32)
        if accessor_type == "SCALAR":
            array = array.reshape(-1)
            count = len(array)
            width = 1
            payload_array = array
            bounds_array = array.reshape(-1, 1)
        else:
            widths = {"VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
            width = widths.get(accessor_type)
            if width is None:
                raise DirectAnimationExportError(
                    f"Unsupported accessor type {accessor_type!r}."
                )
            if accessor_type == "MAT4":
                array = array.reshape(-1, 4, 4)
                count = len(array)
                payload_array = (
                    np.swapaxes(array, 1, 2).reshape(count, 16)
                    if matrix_column_major
                    else array.reshape(count, 16)
                )
                bounds_array = payload_array
            else:
                array = array.reshape(-1, width)
                count = len(array)
                payload_array = array
                bounds_array = array

        self._align(4)
        byte_offset = len(self.binary)
        payload = np.asarray(payload_array, dtype="<f4").tobytes(order="C")
        self.binary.extend(payload)
        view_index = len(self.buffer_views)
        self.buffer_views.append(
            {
                "buffer": 0,
                "byteOffset": byte_offset,
                "byteLength": len(payload),
            }
        )

        accessor = {
            "bufferView": view_index,
            "componentType": 5126,
            "count": count,
            "type": accessor_type,
        }
        if name:
            accessor["name"] = name
        if include_bounds and count:
            accessor["min"] = [float(value) for value in np.min(bounds_array, axis=0)]
            accessor["max"] = [float(value) for value in np.max(bounds_array, axis=0)]
            if width == 1:
                accessor["min"] = accessor["min"][:1]
                accessor["max"] = accessor["max"][:1]

        accessor_index = len(self.accessors)
        self.accessors.append(accessor)
        return accessor_index


def _plain_mapping(value):
    keys = list(value.keys())
    if keys:
        indexed = []
        for key in keys:
            try:
                index = int(key)
            except (TypeError, ValueError):
                indexed = []
                break
            if index < 0 or str(index) != str(key):
                indexed = []
                break
            indexed.append((index, key))
        if indexed:
            indexed.sort(key=lambda item: item[0])
            if [index for index, _ in indexed] == list(range(len(indexed))):
                return [_idprop_plain(value[key]) for _, key in indexed]
    return {str(key): _idprop_plain(value[key]) for key in keys}


def _idprop_plain(value):
    if isinstance(value, (str, bool, int, float)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_idprop_plain(item) for item in value]
    if isinstance(value, dict) or hasattr(value, "keys"):
        return _plain_mapping(value)
    if hasattr(value, "__iter__"):
        return [_idprop_plain(item) for item in value]
    return str(value)


def _list_field_plain(value, *, single_object_keys=()):
    plain = _idprop_plain(value)
    if plain is None:
        return []
    if isinstance(plain, list):
        return plain
    if isinstance(plain, dict):
        if not plain:
            return []
        if single_object_keys and set(single_object_keys).issubset(plain):
            return [plain]
        values = list(plain.values())
        if values and all(isinstance(item, dict) for item in values):
            return values
    return plain


def _sequence_plain(value):
    if value is None or isinstance(value, (str, bytes, dict)):
        return None
    try:
        return [_idprop_plain(item) for item in value]
    except TypeError:
        return None


def _json_snapshot(idblock, key: str) -> dict:
    payload = idblock.get(key) if idblock is not None else None
    if not payload:
        return {}
    try:
        decoded = json.loads(str(payload))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _ordered_track_names(armature, skin: dict | None = None) -> list[str]:
    skin = skin or active_animation_skin(armature)
    track_names = skin.get("trackNames") if isinstance(skin, dict) else None
    if isinstance(track_names, list):
        return [str(name) for name in track_names]
    return rig_track_names(armature)

def _source_rest_relative_snapshot(armature, source_names: tuple[str, ...]):
    snapshot = active_animation_source_rest(armature)
    if not snapshot or snapshot.get("space") != SOURCE_REST_SPACE_CONTRACT:
        return None
    names = tuple(str(name) for name in snapshot.get("boneNames", ()))
    if names != source_names:
        return None
    matrices = snapshot.get("matrices")
    try:
        values = np.asarray(matrices, dtype=np.float64).reshape(len(source_names), 4, 4)
    except (TypeError, ValueError):
        return None
    if not np.all(np.isfinite(values)):
        return None
    determinants = np.linalg.det(values[:, :3, :3])
    if np.any(np.abs(determinants) <= 1e-10):
        return None
    return values

def _matrix_to_numpy(matrix) -> np.ndarray:
    return np.asarray(
        tuple(tuple(float(component) for component in row) for row in matrix),
        dtype=np.float64,
    )


def _compose_basis_trs_batch(translations, rotations_wxyz, scales) -> np.ndarray:
    rotations_wxyz = np.asarray(rotations_wxyz, dtype=np.float64)
    return compose_trs_batch(
        translations,
        rotations_wxyz[..., (1, 2, 3, 0)],
        scales,
    )


def _validate_parent_indices(names: tuple[str, ...], parents: tuple[int, ...]) -> None:
    if len(names) != len(parents):
        raise DirectAnimationExportError(
            "Skin boneParentIndexes length does not match boneNames."
        )
    for index, parent in enumerate(parents):
        if parent == -1:
            continue
        if parent < 0 or parent >= index:
            raise DirectAnimationExportError(
                f"Invalid parent index {parent} for source joint {names[index]!r}."
            )


def _derive_parent_indices(target_bones: tuple[Any, ...]) -> tuple[int, ...]:
    index_by_name = {bone.name: index for index, bone in enumerate(target_bones)}
    parents = []
    for bone in target_bones:
        parent = bone.parent
        while parent is not None and parent.name not in index_by_name:
            parent = parent.parent
        parents.append(index_by_name.get(parent.name, -1) if parent is not None else -1)
    return tuple(parents)


def build_skeleton_export_binding(armature) -> SkeletonExportBinding:
    if armature is None or getattr(armature, "type", None) != "ARMATURE":
        raise DirectAnimationExportError("Animation export requires one armature object.")
    contract = rig_space_contract(armature)
    if contract != RIG_SPACE_CONTRACT:
        raise DirectAnimationExportError(
            "The selected armature was not imported with the supported read_rig coordinate contract."
        )

    snapshot = active_animation_skin(armature)
    source_names_value = _sequence_plain(snapshot.get("boneNames"))
    if not source_names_value:
        raise DirectAnimationExportError(
            "The rig manifest has no animation skin boneNames. Import an .anims.glb first or provide rig source metadata."
        )
    source_names = tuple(str(name) for name in source_names_value)
    if len(set(source_names)) != len(source_names):
        raise DirectAnimationExportError("Animation skin boneNames must be unique.")

    target_names = []
    target_bones = []
    used_targets = set()
    for source_name in source_names:
        target_name = source_name if armature.data.bones.get(source_name) else merged_rig_bone_name(source_name)
        bone = armature.data.bones.get(target_name)
        if bone is None:
            raise DirectAnimationExportError(
                f"The selected MetaRig is missing source animation joint {source_name!r} "
                f"(resolved target {target_name!r})."
            )
        if target_name in used_targets:
            raise DirectAnimationExportError(
                f"Multiple source joints resolve to target bone {target_name!r}."
            )
        pose_bone = armature.pose.bones.get(target_name)
        if pose_bone is None:
            raise DirectAnimationExportError(
                f"The selected MetaRig has no pose bone for {target_name!r}."
            )
        inherit_scale = getattr(pose_bone.bone, "inherit_scale", "FULL")
        if inherit_scale != "FULL":
            raise DirectAnimationExportError(
                f"Bone {target_name!r} uses unsupported inherit_scale={inherit_scale!r}."
            )
        if not getattr(pose_bone.bone, "use_inherit_rotation", True):
            raise DirectAnimationExportError(
                f"Bone {target_name!r} disables inherited rotation."
            )
        if not getattr(pose_bone.bone, "use_local_location", True):
            raise DirectAnimationExportError(
                f"Bone {target_name!r} disables local location."
            )
        if getattr(pose_bone, "rotation_mode", "QUATERNION") != "QUATERNION":
            raise DirectAnimationExportError(
                f"Bone {target_name!r} is not using quaternion rotation mode."
            )
        used_targets.add(target_name)
        target_names.append(target_name)
        target_bones.append(bone)
    target_names = tuple(target_names)
    target_bones = tuple(target_bones)

    parents_value = _sequence_plain(snapshot.get("boneParentIndexes"))
    if parents_value and len(parents_value) == len(source_names):
        parent_indices = tuple(int(value) for value in parents_value)
        try:
            _validate_parent_indices(source_names, parent_indices)
        except DirectAnimationExportError:
            parent_indices = _derive_parent_indices(target_bones)
    else:
        parent_indices = _derive_parent_indices(target_bones)
    _validate_parent_indices(source_names, parent_indices)

    rest_relative_blender = _source_rest_relative_snapshot(armature, source_names)
    uses_source_rest_snapshot = rest_relative_blender is not None
    if rest_relative_blender is None:
        model_matrices = np.asarray(
            [_matrix_to_numpy(bone.matrix_local) for bone in target_bones],
            dtype=np.float64,
        )
        rest_relative_blender = np.empty_like(model_matrices)
        for index, parent_index in enumerate(parent_indices):
            rest_relative_blender[index] = (
                model_matrices[index]
                if parent_index < 0
                else np.linalg.inv(model_matrices[parent_index]) @ model_matrices[index]
            )

    rest_relative_gltf = np.empty_like(rest_relative_blender)
    rest_global_gltf = np.empty_like(rest_relative_blender)
    for index, parent_index in enumerate(parent_indices):
        rest_relative_gltf[index] = _blender_relative_to_gltf(
            rest_relative_blender[index], parent_index < 0
        )
        rest_global_gltf[index] = (
            rest_relative_gltf[index]
            if parent_index < 0
            else rest_global_gltf[parent_index] @ rest_relative_gltf[index]
        )

    snapshot = copy.deepcopy(snapshot)
    track_names = _ordered_track_names(armature, snapshot)
    skin_extras = {
        "rigPath": str(snapshot.get("rigPath", "")),
        "boneNames": list(source_names),
        "boneParentIndexes": list(parent_indices),
        "trackNames": list(track_names),
    }
    for key, value in snapshot.items():
        if key not in skin_extras:
            skin_extras[key] = value

    return SkeletonExportBinding(
        source_names=source_names,
        target_names=target_names,
        parent_indices=parent_indices,
        target_bones=target_bones,
        rest_relative_blender=rest_relative_blender,
        rest_relative_gltf=rest_relative_gltf,
        rest_global_gltf=rest_global_gltf,
        skin_extras=skin_extras,
        uses_source_rest_snapshot=uses_source_rest_snapshot,
    )


def _node_trs(matrix: np.ndarray) -> dict:
    translation, rotation, scale = _decompose_trs_batch(np.asarray(matrix).reshape(1, 4, 4))
    translation = translation[0]
    rotation = rotation[0]
    scale = scale[0]
    node = {}
    if not np.allclose(translation, 0.0, atol=1e-8):
        node["translation"] = [float(value) for value in translation]
    if not np.allclose(rotation, (0.0, 0.0, 0.0, 1.0), atol=1e-8):
        node["rotation"] = [float(value) for value in rotation]
    if not np.allclose(scale, 1.0, atol=1e-8):
        node["scale"] = [float(value) for value in scale]
    return node


def build_gltf_skeleton(binding: SkeletonExportBinding, builder: GLBBuilder):
    inverse_bind = np.linalg.inv(binding.rest_global_gltf)
    inverse_bind_accessor = builder.add_float_accessor(
        inverse_bind,
        "MAT4",
        name="Bind Matrices",
        matrix_column_major=True,
        include_bounds=False,
    )

    child_lists = [[] for _ in binding.source_names]
    root_indices = []
    for index, parent_index in enumerate(binding.parent_indices):
        if parent_index < 0:
            root_indices.append(index)
        else:
            child_lists[parent_index].append(index)

    nodes = [{"name": "Armature", "children": [index + 1 for index in root_indices]}]
    for index, source_name in enumerate(binding.source_names):
        node = {"name": source_name}
        node.update(_node_trs(binding.rest_relative_gltf[index]))
        if child_lists[index]:
            node["children"] = [child + 1 for child in child_lists[index]]
        nodes.append(node)

    skin = {
        "name": "Armature",
        "inverseBindMatrices": inverse_bind_accessor,
        "joints": [index + 1 for index in range(len(binding.source_names))],
        "extras": binding.skin_extras,
    }
    return nodes, skin


def _action_fcurves(action, armature=None):
    from ..animtools.compat import get_action_fcurves

    curves = get_action_fcurves(action, armature)
    return list(curves) if curves is not None else []


def _curve_map(action, armature=None) -> dict[tuple[str, int], Any]:
    result = {}
    for curve in _action_fcurves(action, armature):
        key = (str(curve.data_path), int(curve.array_index))
        if key in result:
            raise DirectAnimationExportError(
                f"Action {action.name!r} has duplicate FCurves for {key}."
            )
        result[key] = curve
    return result


def _curve_key_frames(curve) -> np.ndarray:
    points = curve.keyframe_points
    if not len(points):
        return np.empty(0, dtype=np.float64)
    coordinates = np.empty(len(points) * 2, dtype=np.float64)
    points.foreach_get("co", coordinates)
    return coordinates[0::2]


def _curve_interpolations(curve) -> set[str]:
    return {str(point.interpolation) for point in curve.keyframe_points}


def _property_sampling(curves: list[Any], action, *, force_dense=False):
    if not curves:
        return None
    interpolations = set()
    frame_arrays = []
    for curve in curves:
        interpolations.update(_curve_interpolations(curve))
        frames = _curve_key_frames(curve)
        if len(frames):
            frame_arrays.append(frames)
    if not frame_arrays:
        return None

    exact_mode = interpolations.issubset({"CONSTANT"}) or interpolations.issubset({"LINEAR"})
    if force_dense or not exact_mode:
        start, end = (float(value) for value in action.frame_range)
        first = int(math.floor(start + 1e-7))
        last = int(math.ceil(end - 1e-7))
        frames = np.arange(first, max(first, last) + 1, dtype=np.float64)
        interpolation = "LINEAR"
    else:
        frames = np.unique(np.concatenate(frame_arrays))
        interpolation = "STEP" if interpolations == {"CONSTANT"} else "LINEAR"
    return frames, interpolation


def _evaluate_property(curve_map, data_path, width, frames, defaults):
    result = np.broadcast_to(np.asarray(defaults, dtype=np.float64), (len(frames), width)).copy()
    curves = []
    for component in range(width):
        curve = curve_map.get((data_path, component))
        if curve is None:
            continue
        curves.append(curve)
        result[:, component] = np.fromiter(
            (float(curve.evaluate(float(frame))) for frame in frames),
            dtype=np.float64,
            count=len(frames),
        )
    return result, curves


def _basis_at_frames(curve_map, paths, frames):
    locations, _ = _evaluate_property(
        curve_map, paths["location"], 3, frames, (0.0, 0.0, 0.0)
    )
    rotations, _ = _evaluate_property(
        curve_map, paths["rotation_quaternion"], 4, frames, (1.0, 0.0, 0.0, 0.0)
    )
    scales, _ = _evaluate_property(
        curve_map, paths["scale"], 3, frames, (1.0, 1.0, 1.0)
    )
    lengths = np.linalg.norm(rotations, axis=1)
    invalid = lengths <= 1e-15
    rotations[invalid] = (1.0, 0.0, 0.0, 0.0)
    rotations /= np.maximum(np.linalg.norm(rotations, axis=1)[:, None], 1e-15)
    return _compose_basis_trs_batch(locations, rotations, scales)


def _source_property_values(binding, joint_index, basis_matrices, path):
    relative_blender = np.matmul(binding.rest_relative_blender[joint_index], basis_matrices)
    relative_gltf = _blender_relative_to_gltf(
        relative_blender, binding.parent_indices[joint_index] < 0
    )
    translations, rotations, scales = _decompose_trs_batch(relative_gltf)
    if path == "translation":
        return translations
    if path == "rotation":
        return _normalize_quaternions_xyzw(rotations)
    if path == "scale":
        return scales
    raise DirectAnimationExportError(f"Unsupported glTF animation path {path!r}.")


def _values_are_default(values, defaults, *, quaternion=False) -> bool:
    values = np.asarray(values, dtype=np.float64)
    default = np.asarray(defaults, dtype=np.float64)
    if quaternion:
        direct = np.max(np.abs(values - default), axis=1)
        negated = np.max(np.abs(values + default), axis=1)
        return bool(np.all(np.minimum(direct, negated) <= 1e-7))
    return bool(np.all(np.abs(values - default) <= 1e-7))


def _gltf_times_from_frames(frames, action_start: float) -> np.ndarray:
    frame_offsets = np.asarray(frames, dtype=np.float64) - float(action_start)
    if np.any(frame_offsets < -1e-7):
        raise DirectAnimationExportError(
            "Animation contains keys before its frame range start."
        )
    frame_offsets = np.maximum(frame_offsets, 0.0)
    encoded = np.asarray(frame_offsets / FPS, dtype=np.float32)
    overshoot = encoded.astype(np.float64) * FPS > frame_offsets + 1e-12
    if np.any(overshoot):
        encoded[overshoot] = np.nextafter(
            encoded[overshoot],
            np.float32(-np.inf),
            dtype=np.float32,
        )
    return encoded.astype(np.float64)


def _track_payload_from_fcurves(action, armature):
    """Serialize live track FCurves using skin.extras.trackNames as the index map."""
    track_names = _ordered_track_names(armature)
    if len(set(track_names)) != len(track_names):
        raise DirectAnimationExportError(
            "The animation skin extras contain duplicate trackNames."
        )

    track_index_by_path = {
        f'["{track_name}"]': track_index
        for track_index, track_name in enumerate(track_names)
    }
    indexed_curves = []
    seen_indices = set()
    for curve in _action_fcurves(action, armature):
        data_path = str(curve.data_path)
        track_index = track_index_by_path.get(data_path)
        if track_index is None:
            continue
        if track_index in seen_indices:
            raise DirectAnimationExportError(
                f"Action {action.name!r} has multiple FCurves for track "
                f"{track_names[track_index]!r}."
            )
        seen_indices.add(track_index)
        indexed_curves.append((track_index, curve))
    indexed_curves.sort(key=lambda item: item[0])

    action_start = float(action.frame_range[0])
    track_keys = []
    const_track_keys = []
    for track_index, curve in indexed_curves:
        points = curve.keyframe_points
        if not len(points):
            continue
        coordinates = np.empty(len(points) * 2, dtype=np.float64)
        points.foreach_get("co", coordinates)
        frames = coordinates[0::2]
        values = coordinates[1::2]
        order = np.argsort(frames, kind="stable")
        frames = frames[order]
        values = values[order]

        if np.all(np.abs(values - values[0]) <= 1e-9):
            const_track_keys.append(
                {
                    "trackIndex": int(track_index),
                    "time": 0.0,
                    "value": float(values[0]),
                }
            )
            continue

        for frame, value in zip(frames, values):
            relative_frame = float(frame) - action_start
            if relative_frame < -1e-7:
                raise DirectAnimationExportError(
                    f"Action {action.name!r} track "
                    f"{track_names[track_index]!r} contains a key before its "
                    "frame range start."
                )
            track_keys.append(
                {
                    "trackIndex": int(track_index),
                    "time": max(0.0, relative_frame) / FPS,
                    "value": float(value),
                }
            )
    return track_keys, const_track_keys


def _direct_event_array(value, action_name: str) -> list:
    """Convert the prepared animEvents IDProperty to the GLB JSON array."""
    if value is None:
        return []

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            value = json.loads(stripped)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise DirectAnimationExportError(
                f"Action {action_name!r} property 'animEvents' contains invalid JSON."
            ) from error

    if hasattr(value, "to_list"):
        value = value.to_list()

    plain = _idprop_plain(value)
    if plain is None:
        return []
    if isinstance(plain, list):
        return plain
    if isinstance(plain, dict):
        if not plain:
            return []
        if "type" in plain or "eventName" in plain:
            return [plain]

        indexed = []
        for key, item in plain.items():
            try:
                index = int(key)
            except (TypeError, ValueError):
                indexed = []
                break
            indexed.append((index, item))
        if indexed:
            indexed.sort(key=lambda pair: pair[0])
            return [item for _, item in indexed]

        values = list(plain.values())
        if values and all(isinstance(item, dict) for item in values):
            return values

    raise DirectAnimationExportError(
        f"Action {action_name!r} property 'animEvents' could not be converted "
        f"from {type(value).__name__} to a JSON array."
    )


def _direct_integer_array(value, action_name: str, key: str) -> list[int]:
    """Convert a Blender integer IDPropertyArray without changing the Action."""
    if value is None:
        return []
    if hasattr(value, "to_list"):
        value = value.to_list()
    try:
        return [int(item) for item in value]
    except (TypeError, ValueError) as error:
        raise DirectAnimationExportError(
            f"Action {action_name!r} property {key!r} must be an integer array."
        ) from error

def _animation_extras(action, armature, export_tracks: bool = True) -> dict:
    """Prepare and serialize the individual Action properties used by CP77."""
    # Preserve the legacy pre-export contract. Defaults are written to the
    # Action itself because every property is part of the editable round trip.
    schema = action.get("schema") if "schema" in action else None
    if not schema or not hasattr(schema, "get"):
        action["schema"] = {"type": "wkit.cp2077.gltf.anims", "version": 5}
    elif int(schema.get("version", 0) or 0) < 5:
        action["schema"] = {"type": "wkit.cp2077.gltf.anims", "version": 5}

    defaults = {
        "animationType": "Normal",
        "rootMotionType": "Unknown",
        "frameClamping": False,
        "frameClampingStartFrame": -1,
        "frameClampingEndFrame": -1,
        "numExtraJoints": 0,
        "numExtraTracks": 0,
        "constTrackKeys": [],
        "trackKeys": [],
        "fallbackFrameIndices": [],
        "optimizationHints": {
            "preferSIMD": False,
            "maxRotationCompression": 0,
        },
    }
    for key, default in defaults.items():
        if key not in action:
            action[key] = copy.deepcopy(default)

    try:
        from ..animtools.anim_events import save_events_to_idproperty

        save_events_to_idproperty(action)
    except Exception as error:
        print(
            f"[CP77] Warning: could not save animation events for "
            f"{action.name!r}: {error}"
        )

    if "animEvents" not in action:
        action["animEvents"] = []

    # The direct writer controls its extras explicitly, so internal properties
    # cannot leak into the GLB and do not need to be deleted from the Action.
    track_keys, const_track_keys = _track_payload_from_fcurves(action, armature)
    action["trackKeys"] = track_keys
    action["constTrackKeys"] = const_track_keys

    extras = {
        "schema": _idprop_plain(action["schema"]),
        "animationType": str(action["animationType"]),
        "rootMotionType": str(action["rootMotionType"]),
        "frameClamping": bool(action["frameClamping"]),
        "frameClampingStartFrame": int(action["frameClampingStartFrame"]),
        "frameClampingEndFrame": int(action["frameClampingEndFrame"]),
        "numExtraJoints": int(action["numExtraJoints"]),
        "numExtraTracks": int(action["numExtraTracks"]),
        "constTrackKeys": list(const_track_keys),
        "trackKeys": list(track_keys),
        "fallbackFrameIndices": _direct_integer_array(
            action["fallbackFrameIndices"],
            action.name,
            "fallbackFrameIndices",
        ),
        "optimizationHints": _idprop_plain(action["optimizationHints"]),
        "animEvents": _direct_event_array(action["animEvents"], action.name),
    }

    if not isinstance(extras["schema"], dict):
        raise DirectAnimationExportError(
            f"Action {action.name!r} property 'schema' is not an object."
        )
    if not isinstance(extras["optimizationHints"], dict):
        raise DirectAnimationExportError(
            f"Action {action.name!r} property 'optimizationHints' is not an object."
        )

    # Remove only the abandoned duplicate snapshot. Individual Action
    # properties above remain authoritative and untouched.
    if ANIMATION_EXTRAS_SNAPSHOT_KEY in action:
        del action[ANIMATION_EXTRAS_SNAPSHOT_KEY]
    return extras






def _action_has_cp77_payload(action, target_paths: set[str], armature=None) -> bool:
    for curve in _action_fcurves(action, armature):
        if curve.data_path in target_paths:
            return True
    if any(key in action for key in _ANIMATION_DEFAULTS):
        return True
    # Recovery only: actions from the abandoned build are admitted once so
    # _animation_extras can restore the individual properties and delete it.
    return bool(action.get(ANIMATION_EXTRAS_SNAPSHOT_KEY))





def _actions_for_export(
    armature,
    binding,
    active_action_only=False,
    selected_action_names=None,
):
    animation_data = getattr(armature, "animation_data", None)
    if active_action_only:
        action = getattr(animation_data, "action", None)
        if action is None:
            raise DirectAnimationExportError("The selected armature has no active action.")
        return [action]

    target_paths = set()
    for target_name in binding.target_names:
        pose_bone = armature.pose.bones.get(target_name)
        if pose_bone is None:
            continue
        target_paths.update(
            {
                pose_bone.path_from_id("location"),
                pose_bone.path_from_id("rotation_quaternion"),
                pose_bone.path_from_id("scale"),
            }
        )
    actions = [
        action for action in bpy.data.actions
        if _action_has_cp77_payload(action, target_paths, armature)
    ]
    if not actions:
        raise DirectAnimationExportError(
            "No compatible CP77 actions were found for the selected armature."
        )

    if selected_action_names is not None:
        requested_names = list(dict.fromkeys(str(name) for name in selected_action_names if name))
        if not requested_names:
            raise DirectAnimationExportError("No actions were selected for export.")
        by_name = {action.name: action for action in actions}
        missing = [name for name in requested_names if name not in by_name]
        if missing:
            raise DirectAnimationExportError(
                "Selected actions are no longer compatible or no longer exist: "
                + ", ".join(missing)
            )
        actions = [by_name[name] for name in requested_names]

    return actions


def compatible_actions_for_export(armature):
    """Return the actions accepted by the direct exporter for one armature."""
    if bpy is None:
        raise RuntimeError("Blender is required for action discovery.")
    binding = build_skeleton_export_binding(armature)
    return tuple(_actions_for_export(armature, binding))


def _animation_duration_frames(action, extras: dict, action_start: float) -> float:
    try:
        frame_end = float(action.frame_range[1])
    except (AttributeError, TypeError, ValueError):
        frame_end = action_start
    duration = max(0.0, frame_end - action_start)

    imported_frame_count = action.get("cp77_direct_anim_frame_count")
    try:
        duration = max(duration, float(imported_frame_count) - 1.0)
    except (TypeError, ValueError):
        pass

    for entry in extras.get("trackKeys", ()) or ():
        if not isinstance(entry, dict):
            continue
        try:
            duration = max(duration, float(entry.get("time", 0.0)) * FPS)
        except (TypeError, ValueError):
            continue
    return duration


def _append_duration_hold(channel_payloads: list[dict], binding, duration_frames: float) -> None:
    if duration_frames <= 1e-7:
        return
    duration_seconds = float(_gltf_times_from_frames((duration_frames,), 0.0)[0])
    current_end = max(
        (float(payload["times"][-1]) for payload in channel_payloads if len(payload["times"])),
        default=-1.0,
    )
    if current_end >= duration_seconds - 1e-7:
        return

    if channel_payloads:
        payload = channel_payloads[0]
        payload["times"] = np.concatenate(
            (np.asarray(payload["times"], dtype=np.float64), np.asarray([duration_seconds]))
        )
        payload["values"] = np.concatenate(
            (
                np.asarray(payload["values"], dtype=np.float64),
                np.asarray(payload["values"][-1:], dtype=np.float64),
            ),
            axis=0,
        )
        return

    translation, _, _ = _decompose_trs_batch(
        binding.rest_relative_gltf[0].reshape(1, 4, 4)
    )
    channel_payloads.append(
        {
            "joint_index": 0,
            "path": "translation",
            "interpolation": "LINEAR",
            "times": np.asarray((0.0, duration_seconds), dtype=np.float64),
            "values": np.repeat(translation, 2, axis=0),
        }
    )


def build_animation_document(action, armature, binding, builder, export_tracks: bool):
    extras = _animation_extras(action, armature, export_tracks)
    curve_map = _curve_map(action, armature)
    action_start = float(action.frame_range[0])
    duration_frames = _animation_duration_frames(action, extras, action_start)
    channel_payloads: list[dict] = []

    for joint_index, target_name in enumerate(binding.target_names):
        pose_bone = armature.pose.bones.get(target_name)
        if pose_bone is None:
            raise DirectAnimationExportError(
                f"Action export target bone {target_name!r} no longer exists."
            )
        paths = {
            "location": pose_bone.path_from_id("location"),
            "rotation_quaternion": pose_bone.path_from_id("rotation_quaternion"),
            "scale": pose_bone.path_from_id("scale"),
        }
        property_specs = (
            ("translation", "location", 3),
            ("rotation", "rotation_quaternion", 4),
            ("scale", "scale", 3),
        )
        for gltf_path, blender_property, width in property_specs:
            curves = [
                curve_map[(paths[blender_property], component)]
                for component in range(width)
                if (paths[blender_property], component) in curve_map
            ]
            sampling = _property_sampling(
                curves,
                action,
                force_dense=(
                    gltf_path == "rotation"
                    and any(
                        mode not in {"LINEAR", "CONSTANT"}
                        for curve in curves
                        for mode in _curve_interpolations(curve)
                    )
                ),
            )
            if sampling is None:
                continue
            frames, interpolation = sampling
            basis = _basis_at_frames(curve_map, paths, frames)
            values = _source_property_values(binding, joint_index, basis, gltf_path)
            rest_translation, rest_rotation, rest_scale = _decompose_trs_batch(
                binding.rest_relative_gltf[joint_index].reshape(1, 4, 4)
            )
            default = {
                "translation": rest_translation[0],
                "rotation": rest_rotation[0],
                "scale": rest_scale[0],
            }[gltf_path]
            if _values_are_default(
                values,
                default,
                quaternion=(gltf_path == "rotation"),
            ):
                continue

            try:
                times = _gltf_times_from_frames(frames, action_start)
            except DirectAnimationExportError as error:
                raise DirectAnimationExportError(
                    f"Action {action.name!r}: {error}"
                ) from error
            channel_payloads.append(
                {
                    "joint_index": joint_index,
                    "path": gltf_path,
                    "interpolation": interpolation,
                    "times": times,
                    "values": values,
                }
            )

    _append_duration_hold(channel_payloads, binding, duration_frames)
    samplers = []
    channels = []
    for payload in channel_payloads:
        joint_index = int(payload["joint_index"])
        gltf_path = str(payload["path"])
        input_accessor = builder.add_float_accessor(
            payload["times"],
            "SCALAR",
            name=f"{action.name}:{binding.source_names[joint_index]}:{gltf_path}:time",
        )
        output_accessor = builder.add_float_accessor(
            payload["values"],
            "VEC4" if gltf_path == "rotation" else "VEC3",
            name=f"{action.name}:{binding.source_names[joint_index]}:{gltf_path}",
        )
        sampler_index = len(samplers)
        samplers.append(
            {
                "input": input_accessor,
                "output": output_accessor,
                "interpolation": str(payload["interpolation"]),
            }
        )
        channels.append(
            {
                "sampler": sampler_index,
                "target": {"node": joint_index + 1, "path": gltf_path},
            }
        )

    return {
        "name": str(action.name),
        "channels": channels,
        "samplers": samplers,
        "extras": extras,
    }


def build_direct_animation_glb(
    armature,
    *,
    export_tracks: bool = True,
    active_action_only: bool = False,
    selected_action_names=None,
):
    if bpy is None:
        raise RuntimeError("Blender is required for direct animation export.")
    binding = build_skeleton_export_binding(armature)
    builder = GLBBuilder()
    nodes, skin = build_gltf_skeleton(binding, builder)
    actions = _actions_for_export(
        armature,
        binding,
        active_action_only=active_action_only,
        selected_action_names=selected_action_names,
    )
    animations = [
        build_animation_document(action, armature, binding, builder, export_tracks)
        for action in actions
    ]
    document = {
        "asset": {
            "copyright": "",
            "generator": "Cyberpunk 2077 IO Suite direct animation exporter",
            "version": "2.0",
        },
        "accessors": builder.accessors,
        "animations": animations,
        "bufferViews": builder.buffer_views,
        "buffers": [{"byteLength": len(builder.binary)}],
        "nodes": nodes,
        "scenes": [{"nodes": [0]}],
        "skins": [skin],
    }
    return document, bytes(builder.binary), {
        "animation_count": len(animations),
        "joint_count": len(binding.source_names),
        "accessor_count": len(builder.accessors),
        "binary_bytes": len(builder.binary),
        "source_rest_snapshot": bool(binding.uses_source_rest_snapshot),
    }


_REQUIRED_ANIMATION_EXTRA_KEYS = tuple(_ANIMATION_DEFAULTS)
_ACCESSOR_WIDTHS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def _validate_track_entries(entries, label: str) -> None:
    if not isinstance(entries, list):
        raise DirectAnimationExportError(f"{label} must be a list.")
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise DirectAnimationExportError(f"{label}[{index}] must be an object.")
        missing = {"trackIndex", "time", "value"} - set(entry)
        if missing:
            raise DirectAnimationExportError(
                f"{label}[{index}] is missing: {', '.join(sorted(missing))}."
            )
        try:
            int(entry["trackIndex"])
            float(entry["time"])
            float(entry["value"])
        except (TypeError, ValueError) as error:
            raise DirectAnimationExportError(
                f"{label}[{index}] contains invalid numeric values."
            ) from error


def _validate_cp77_animation_extras(extras, animation_name: str) -> None:
    if not isinstance(extras, dict):
        raise DirectAnimationExportError(
            f"Animation {animation_name!r} does not contain a glTF extras object."
        )
    missing = [key for key in _REQUIRED_ANIMATION_EXTRA_KEYS if key not in extras]
    if missing:
        raise DirectAnimationExportError(
            f"Animation {animation_name!r} extras are missing: {', '.join(missing)}."
        )
    schema = extras.get("schema")
    if not isinstance(schema, dict) or schema.get("type") != "wkit.cp2077.gltf.anims":
        raise DirectAnimationExportError(
            f"Animation {animation_name!r} has an invalid CP77 schema extras entry."
        )
    try:
        schema_version = int(schema.get("version", 0))
    except (TypeError, ValueError) as error:
        raise DirectAnimationExportError(
            f"Animation {animation_name!r} schema version is not an integer."
        ) from error
    if schema_version < 5:
        raise DirectAnimationExportError(
            f"Animation {animation_name!r} schema version must be at least 5."
        )
    _validate_track_entries(extras.get("trackKeys"), f"{animation_name}.extras.trackKeys")
    _validate_track_entries(
        extras.get("constTrackKeys"),
        f"{animation_name}.extras.constTrackKeys",
    )
    if not isinstance(extras.get("fallbackFrameIndices"), list):
        raise DirectAnimationExportError(
            f"{animation_name}.extras.fallbackFrameIndices must be a list."
        )
    if extras.get("animEvents") is not None and not isinstance(extras.get("animEvents"), list):
        raise DirectAnimationExportError(
            f"{animation_name}.extras.animEvents must be a list or null."
        )
    if not isinstance(extras.get("optimizationHints"), dict):
        raise DirectAnimationExportError(
            f"{animation_name}.extras.optimizationHints must be an object."
        )


def validate_direct_animation_document(document: dict, binary: bytes) -> dict:
    """Validate the complete glTF 2.0 document and CP77 extras before encoding."""
    if not isinstance(document, dict):
        raise DirectAnimationExportError("The GLB JSON document is not an object.")
    asset = document.get("asset")
    if not isinstance(asset, dict) or str(asset.get("version")) != "2.0":
        raise DirectAnimationExportError("The GLB asset version must be 2.0.")

    buffers = document.get("buffers")
    if not isinstance(buffers, list) or len(buffers) != 1:
        raise DirectAnimationExportError("The animation GLB must contain exactly one embedded buffer.")
    if int(buffers[0].get("byteLength", -1)) != len(binary):
        raise DirectAnimationExportError("The GLB buffer byteLength does not match the BIN payload.")

    views = document.get("bufferViews")
    accessors = document.get("accessors")
    if not isinstance(views, list) or not isinstance(accessors, list):
        raise DirectAnimationExportError("The GLB must contain bufferViews and accessors arrays.")
    for index, view in enumerate(views):
        if not isinstance(view, dict) or int(view.get("buffer", -1)) != 0:
            raise DirectAnimationExportError(f"bufferViews[{index}] does not reference buffer 0.")
        offset = int(view.get("byteOffset", 0))
        length = int(view.get("byteLength", -1))
        if offset < 0 or length < 0 or offset + length > len(binary):
            raise DirectAnimationExportError(f"bufferViews[{index}] exceeds the BIN payload.")
        if offset % 4:
            raise DirectAnimationExportError(f"bufferViews[{index}] is not 4-byte aligned.")

    for index, accessor in enumerate(accessors):
        if not isinstance(accessor, dict):
            raise DirectAnimationExportError(f"accessors[{index}] is not an object.")
        view_index = int(accessor.get("bufferView", -1))
        if not 0 <= view_index < len(views):
            raise DirectAnimationExportError(f"accessors[{index}] has an invalid bufferView.")
        if int(accessor.get("componentType", -1)) != 5126:
            raise DirectAnimationExportError(f"accessors[{index}] must use FLOAT componentType 5126.")
        accessor_type = str(accessor.get("type", ""))
        width = _ACCESSOR_WIDTHS.get(accessor_type)
        count = int(accessor.get("count", -1))
        if width is None or count < 0:
            raise DirectAnimationExportError(f"accessors[{index}] has invalid type/count metadata.")
        accessor_offset = int(accessor.get("byteOffset", 0))
        required = accessor_offset + count * width * 4
        if accessor_offset < 0 or required > int(views[view_index]["byteLength"]):
            raise DirectAnimationExportError(f"accessors[{index}] exceeds its bufferView.")

    nodes = document.get("nodes")
    skins = document.get("skins")
    scenes = document.get("scenes")
    if not isinstance(nodes, list) or not nodes:
        raise DirectAnimationExportError("The animation GLB contains no nodes.")
    if not isinstance(skins, list) or len(skins) != 1:
        raise DirectAnimationExportError("The animation GLB must contain exactly one skin.")
    if not isinstance(scenes, list) or not scenes:
        raise DirectAnimationExportError("The animation GLB contains no scene.")
    for node_index, node in enumerate(nodes):
        for child in node.get("children", ()) if isinstance(node, dict) else ():
            if not isinstance(child, int) or not 0 <= child < len(nodes):
                raise DirectAnimationExportError(
                    f"nodes[{node_index}] contains an invalid child index."
                )

    skin = skins[0]
    joints = skin.get("joints")
    extras = skin.get("extras")
    if not isinstance(joints, list) or not joints:
        raise DirectAnimationExportError("The skin contains no joints.")
    if any(not isinstance(index, int) or not 0 <= index < len(nodes) for index in joints):
        raise DirectAnimationExportError("The skin contains an invalid joint node index.")
    if not isinstance(extras, dict):
        raise DirectAnimationExportError("The skin is missing its CP77 extras object.")
    bone_names = extras.get("boneNames")
    parent_indices = extras.get("boneParentIndexes")
    track_names = extras.get("trackNames", [])
    if not isinstance(bone_names, list) or len(bone_names) != len(joints):
        raise DirectAnimationExportError("skin.extras.boneNames does not match the joint count.")
    if not isinstance(parent_indices, list) or len(parent_indices) != len(joints):
        raise DirectAnimationExportError(
            "skin.extras.boneParentIndexes does not match the joint count."
        )
    if not isinstance(track_names, list):
        raise DirectAnimationExportError("skin.extras.trackNames must be a list.")
    for index, joint_node in enumerate(joints):
        if str(nodes[joint_node].get("name", "")) != str(bone_names[index]):
            raise DirectAnimationExportError(
                f"Joint {index} node name does not match skin.extras.boneNames."
            )
        parent = int(parent_indices[index])
        if parent >= index or parent < -1:
            raise DirectAnimationExportError(
                f"skin.extras.boneParentIndexes[{index}] is invalid."
            )
        if parent >= 0 and joint_node not in nodes[joints[parent]].get("children", ()):
            raise DirectAnimationExportError(
                f"Joint {index} hierarchy disagrees with boneParentIndexes."
            )
    inverse_bind_accessor = int(skin.get("inverseBindMatrices", -1))
    if not 0 <= inverse_bind_accessor < len(accessors):
        raise DirectAnimationExportError("The skin has no valid inverseBindMatrices accessor.")
    inverse_accessor = accessors[inverse_bind_accessor]
    if inverse_accessor.get("type") != "MAT4" or int(inverse_accessor.get("count", -1)) != len(joints):
        raise DirectAnimationExportError(
            "The inverseBindMatrices accessor must contain one MAT4 per joint."
        )

    animations = document.get("animations")
    if not isinstance(animations, list) or not animations:
        raise DirectAnimationExportError("The GLB contains no animations.")
    for animation_index, animation in enumerate(animations):
        if not isinstance(animation, dict):
            raise DirectAnimationExportError(f"animations[{animation_index}] is not an object.")
        name = str(animation.get("name", f"animation_{animation_index}"))
        _validate_cp77_animation_extras(animation.get("extras"), name)
        samplers = animation.get("samplers")
        channels = animation.get("channels")
        if not isinstance(samplers, list) or not isinstance(channels, list):
            raise DirectAnimationExportError(
                f"Animation {name!r} must contain samplers and channels arrays."
            )
        for sampler_index, sampler in enumerate(samplers):
            input_index = int(sampler.get("input", -1))
            output_index = int(sampler.get("output", -1))
            if not 0 <= input_index < len(accessors) or not 0 <= output_index < len(accessors):
                raise DirectAnimationExportError(
                    f"Animation {name!r} sampler {sampler_index} has invalid accessors."
                )
            if sampler.get("interpolation", "LINEAR") not in {"LINEAR", "STEP"}:
                raise DirectAnimationExportError(
                    f"Animation {name!r} sampler {sampler_index} uses unsupported interpolation."
                )
            if accessors[input_index].get("type") != "SCALAR":
                raise DirectAnimationExportError(
                    f"Animation {name!r} sampler {sampler_index} input must be SCALAR."
                )
            if int(accessors[input_index].get("count", -1)) != int(
                accessors[output_index].get("count", -2)
            ):
                raise DirectAnimationExportError(
                    f"Animation {name!r} sampler {sampler_index} input/output counts differ."
                )
        for channel_index, channel in enumerate(channels):
            sampler_index = int(channel.get("sampler", -1))
            target = channel.get("target")
            if not 0 <= sampler_index < len(samplers) or not isinstance(target, dict):
                raise DirectAnimationExportError(
                    f"Animation {name!r} channel {channel_index} is invalid."
                )
            node_index = int(target.get("node", -1))
            path = target.get("path")
            if node_index not in joints or path not in {"translation", "rotation", "scale"}:
                raise DirectAnimationExportError(
                    f"Animation {name!r} channel {channel_index} targets an invalid joint/path."
                )
            output_accessor = accessors[int(samplers[sampler_index]["output"])]
            expected_type = "VEC4" if path == "rotation" else "VEC3"
            if output_accessor.get("type") != expected_type:
                raise DirectAnimationExportError(
                    f"Animation {name!r} channel {channel_index} output must be {expected_type}."
                )

    json.dumps(document, ensure_ascii=False, separators=(",", ":"))
    return {
        "valid": True,
        "animation_count": len(animations),
        "joint_count": len(joints),
        "accessor_count": len(accessors),
        "skin_extra_keys": tuple(extras.keys()),
        "animation_extra_keys": tuple(animations[0]["extras"].keys()),
    }


def validate_glb_payload(payload: bytes) -> dict:
    """Parse and validate an encoded GLB 2.0 payload, including CP77 extras."""
    if len(payload) < 20:
        raise DirectAnimationExportError("GLB payload is truncated.")
    magic, version, total_length = struct.unpack_from("<4sII", payload, 0)
    if magic != b"glTF" or version != 2 or total_length != len(payload):
        raise DirectAnimationExportError("GLB header is invalid.")
    offset = 12
    json_document = None
    binary = b""
    chunk_order = []
    while offset < len(payload):
        if offset + 8 > len(payload):
            raise DirectAnimationExportError("GLB chunk header is truncated.")
        chunk_length, chunk_type = struct.unpack_from("<II", payload, offset)
        offset += 8
        end = offset + chunk_length
        if chunk_length % 4 or end > len(payload):
            raise DirectAnimationExportError("GLB chunk length or alignment is invalid.")
        chunk = payload[offset:end]
        offset = end
        chunk_order.append(chunk_type)
        if chunk_type == 0x4E4F534A:
            if json_document is not None:
                raise DirectAnimationExportError("GLB contains multiple JSON chunks.")
            try:
                json_document = json.loads(chunk.decode("utf-8").rstrip(" \t\r\n\0"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise DirectAnimationExportError("GLB JSON chunk is invalid.") from error
        elif chunk_type == 0x004E4942:
            if binary:
                raise DirectAnimationExportError("GLB contains multiple BIN chunks.")
            binary = chunk
    if not chunk_order or chunk_order[0] != 0x4E4F534A or json_document is None:
        raise DirectAnimationExportError("The first GLB chunk must be JSON.")
    declared_binary_length = int(json_document.get("buffers", [{}])[0].get("byteLength", -1))
    if declared_binary_length < 0 or len(binary) - declared_binary_length not in {0, 1, 2, 3}:
        raise DirectAnimationExportError("The BIN chunk padding does not match buffers[0].byteLength.")
    validation = validate_direct_animation_document(
        json_document,
        binary[:declared_binary_length],
    )
    validation["file_bytes"] = len(payload)
    validation["json_chunk_bytes"] = next(
        length for length, chunk_type in _iter_glb_chunk_headers(payload) if chunk_type == 0x4E4F534A
    )
    validation["binary_chunk_bytes"] = len(binary)
    return validation


def _iter_glb_chunk_headers(payload: bytes):
    offset = 12
    while offset < len(payload):
        chunk_length, chunk_type = struct.unpack_from("<II", payload, offset)
        yield chunk_length, chunk_type
        offset += 8 + chunk_length


def validate_direct_animation_glb_file(filepath: str) -> dict:
    with open(filepath, "rb") as stream:
        return validate_glb_payload(stream.read())


def _encode_glb(document: dict, binary: bytes) -> bytes:
    json_payload = json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    json_padding = (-len(json_payload)) % 4
    if json_padding:
        json_payload += b" " * json_padding
    binary_padding = (-len(binary)) % 4
    padded_binary = binary + (b"\x00" * binary_padding)
    total_length = 12 + 8 + len(json_payload)
    if padded_binary:
        total_length += 8 + len(padded_binary)

    output = bytearray(struct.pack("<4sII", b"glTF", 2, total_length))
    output.extend(struct.pack("<II", len(json_payload), 0x4E4F534A))
    output.extend(json_payload)
    if padded_binary:
        output.extend(struct.pack("<II", len(padded_binary), 0x004E4942))
        output.extend(padded_binary)
    return bytes(output)


def export_anims_glb_direct(
    filepath: str,
    armature,
    *,
    export_tracks: bool = True,
    active_action_only: bool = False,
    selected_action_names=None,
) -> dict:
    document, binary, summary = build_direct_animation_glb(
        armature,
        export_tracks=export_tracks,
        active_action_only=active_action_only,
        selected_action_names=selected_action_names,
    )
    summary["document_validation"] = validate_direct_animation_document(document, binary)
    filepath = os.path.abspath(filepath)
    if not filepath.lower().endswith(".glb"):
        filepath += ".glb"
    directory = os.path.dirname(filepath)
    if directory:
        os.makedirs(directory, exist_ok=True)
    temporary = filepath + ".tmp"
    payload = _encode_glb(document, binary)
    try:
        with open(temporary, "wb") as stream:
            stream.write(payload)
        summary["file_validation"] = validate_direct_animation_glb_file(temporary)
        os.replace(temporary, filepath)
    except Exception:
        try:
            if os.path.exists(temporary):
                os.remove(temporary)
        finally:
            raise
    summary["filepath"] = filepath
    summary["file_bytes"] = len(payload)
    return summary
