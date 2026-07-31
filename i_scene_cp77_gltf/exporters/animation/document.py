from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

import numpy as np

try:
    import bpy
except ImportError:
    bpy = None


from ...animation.binding import resolve_action_binding
from ...animation.keyframes import get_action_fcurves
from ...animation.events import event_array, save_events_to_idproperty
from ...animation.metadata import (
    ACTION_FIELDS,
    ANIMATION_EXTRAS_SNAPSHOT_KEY,
    FPS,
    ensure_action_defaults,
    normalize_animation_extras,
    plain_value as _idprop_plain,
)
from ...animation.rig_binding import merged_bone_name, rig_space_contract
from ...animation.sampling import curve_interpolations, evaluate_property, property_sampling
from ...animation.tracks import track_payload_from_fcurves
from ...bartmoss.hierarchy import local_matrices_to_model, model_matrices_to_local
from ...bartmoss.quaternion import normalize_sequence_xyzw as _normalize_quaternions_xyzw
from ...bartmoss.trs import (
    compose_matrices as compose_trs_batch,
    decompose_matrices as _decompose_trs_batch,
)
from ...redSpace.contracts import (
    RIG_SPACE_CONTRACT_CURRENT as RIG_SPACE_CONTRACT,
    SOURCE_REST_SPACE_CONTRACT,
)
from ...redSpace.transforms import blender_relative_to_gltf as _blender_relative_to_gltf
from ...gltf.provenance import DIRECT_ANIMATION_GENERATOR
from ..common.glb import GLBBuilder



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


def _source_rest_relative_snapshot(
    snapshot,
    source_names: tuple[str, ...],
):
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


def build_skeleton_export_binding(armature, action=None) -> SkeletonExportBinding:
    if armature is None or getattr(armature, "type", None) != "ARMATURE":
        raise DirectAnimationExportError("Animation export requires one armature object.")
    contract = rig_space_contract(armature)
    if contract != RIG_SPACE_CONTRACT:
        raise DirectAnimationExportError(
            "The selected armature was not imported with the supported read_rig coordinate contract."
        )

    action_binding = resolve_action_binding(action, armature)
    snapshot = action_binding.skin
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
        target_name = source_name if armature.data.bones.get(source_name) else merged_bone_name(source_name)
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

    rest_relative_blender = _source_rest_relative_snapshot(
        action_binding.source_rest,
        source_names,
    )
    uses_source_rest_snapshot = rest_relative_blender is not None
    if rest_relative_blender is None:
        model_matrices = np.asarray(
            [_matrix_to_numpy(bone.matrix_local) for bone in target_bones],
            dtype=np.float64,
        )
        rest_relative_blender = model_matrices_to_local(model_matrices, parent_indices)

    rest_relative_gltf = np.empty_like(rest_relative_blender)
    for index, parent_index in enumerate(parent_indices):
        rest_relative_gltf[index] = _blender_relative_to_gltf(
            rest_relative_blender[index], parent_index < 0
        )
    rest_global_gltf = local_matrices_to_model(rest_relative_gltf, parent_indices)

    snapshot = copy.deepcopy(snapshot)
    track_names = action_binding.tracks.names
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


def _basis_at_frames(curve_map, paths, frames):
    locations, _ = evaluate_property(
        curve_map, paths["location"], 3, frames, (0.0, 0.0, 0.0)
    )
    rotations, _ = evaluate_property(
        curve_map, paths["rotation_quaternion"], 4, frames, (1.0, 0.0, 0.0, 0.0)
    )
    scales, _ = evaluate_property(
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
    # glTF stores animation input accessors as float32 seconds. Encode by normal
    # round-to-nearest float32 conversion; forcing every value downward changes a
    # large fraction of untouched WolvenKit key times by one ULP and can shift the
    # final sample relative to track/event timing.
    return np.asarray(frame_offsets / FPS, dtype=np.float32).astype(np.float64)


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
    action_binding = resolve_action_binding(action, armature)
    source_extras = normalize_animation_extras(
        action_binding.extras,
        label=f"Action {action.name!r} source extras",
        error_type=DirectAnimationExportError,
    )
    ensure_action_defaults(action)

    try:
        save_events_to_idproperty(action)
    except Exception as error:
        print(
            f"[CP77] Warning: could not save animation events for "
            f"{action.name!r}: {error}"
        )

    # The direct writer controls its extras explicitly, so internal properties
    # cannot leak into the GLB and do not need to be deleted from the Action.
    binding_skin_extras = action_binding.skin
    if export_tracks:
        track_keys, const_track_keys = track_payload_from_fcurves(
            action,
            armature,
            source_track_keys=source_extras.get(
                "trackKeys", action.get("trackKeys", ())
            ),
            source_const_track_keys=source_extras.get(
                "constTrackKeys",
                action.get("constTrackKeys", ()),
            ),
            skin_extras=binding_skin_extras,
            track_binding=action_binding.tracks,
            error_type=DirectAnimationExportError,
        )
    else:
        # Keep the imported payload intact but do not rebuild it from live float
        # FCurves. This makes the option non-destructive for untouched clips.
        track_keys = copy.deepcopy(
            source_extras.get("trackKeys", action.get("trackKeys", ())) or []
        )
        const_track_keys = copy.deepcopy(
            source_extras.get(
                "constTrackKeys", action.get("constTrackKeys", ())
            ) or []
        )
    action["trackKeys"] = track_keys
    action["constTrackKeys"] = const_track_keys
    if "animEvents" in action:
        event_payload = event_array(action["animEvents"], action.name, DirectAnimationExportError)
        if source_extras.get("animEvents") is None and not event_payload:
            event_payload = None
    else:
        event_payload = copy.deepcopy(source_extras.get("animEvents", []))

    extras = copy.deepcopy(source_extras)
    extras.update({
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
        "animEvents": event_payload,
    })

    return normalize_animation_extras(
        extras,
        label=f"Action {action.name!r} export extras",
        error_type=DirectAnimationExportError,
    )






def _action_has_cp77_payload(action, target_paths: set[str], armature=None) -> bool:
    for curve in _action_fcurves(action, armature):
        if curve.data_path in target_paths:
            return True
    if any(key in action for key in ACTION_FIELDS):
        return True
    return bool(action.get(ANIMATION_EXTRAS_SNAPSHOT_KEY))


def _binding_target_paths(armature, binding) -> set[str]:
    paths = set()
    for target_name in binding.target_names:
        pose_bone = armature.pose.bones.get(target_name)
        if pose_bone is None:
            continue
        paths.update(
            {
                pose_bone.path_from_id("location"),
                pose_bone.path_from_id("rotation_quaternion"),
                pose_bone.path_from_id("scale"),
            }
        )
    return paths


def _bindings_match(left, right) -> bool:
    if left.source_names != right.source_names:
        return False
    if left.parent_indices != right.parent_indices:
        return False
    if _idprop_plain(left.skin_extras) != _idprop_plain(right.skin_extras):
        return False
    return bool(
        np.allclose(
            left.rest_relative_blender,
            right.rest_relative_blender,
            rtol=0.0,
            atol=1e-7,
        )
    )


def _binding_for_action(armature, action):
    binding = build_skeleton_export_binding(armature, action=action)
    target_paths = _binding_target_paths(armature, binding)
    if not _action_has_cp77_payload(action, target_paths, armature):
        raise DirectAnimationExportError(
            f"Action {action.name!r} has no CP77 animation payload for this armature."
        )
    return binding


def _actions_for_export(
    armature,
    active_action_only=False,
    selected_action_names=None,
):
    animation_data = getattr(armature, "animation_data", None)
    active_action = getattr(animation_data, "action", None)

    if active_action_only:
        if active_action is None:
            raise DirectAnimationExportError("The selected armature has no active action.")
        _binding_for_action(armature, active_action)
        return [active_action]

    if selected_action_names is not None:
        requested_names = list(
            dict.fromkeys(str(name) for name in selected_action_names if name)
        )
        if not requested_names:
            raise DirectAnimationExportError("No actions were selected for export.")
        actions = []
        missing = []
        incompatible = []
        for name in requested_names:
            action = bpy.data.actions.get(name)
            if action is None:
                missing.append(name)
                continue
            try:
                _binding_for_action(armature, action)
            except DirectAnimationExportError:
                incompatible.append(name)
                continue
            actions.append(action)
        if missing or incompatible:
            details = []
            if missing:
                details.append("missing: " + ", ".join(missing))
            if incompatible:
                details.append("incompatible: " + ", ".join(incompatible))
            raise DirectAnimationExportError(
                "Selected actions could not be exported (" + "; ".join(details) + ")."
            )
        return actions

    compatible = []
    for action in bpy.data.actions:
        try:
            binding = _binding_for_action(armature, action)
        except DirectAnimationExportError:
            continue
        compatible.append((action, binding))
    if not compatible:
        raise DirectAnimationExportError(
            "No compatible CP77 actions were found for the selected armature."
        )

    anchor_index = 0
    if active_action is not None:
        for index, (action, _) in enumerate(compatible):
            if action is active_action:
                anchor_index = index
                break
    anchor_binding = compatible[anchor_index][1]
    # One glTF skin is shared by every animation in a .anims.glb. Only return
    # actions from the active action's source binding so importing a facial set
    # after a locomotion set does not make the default export mix both rigs.
    return [
        action
        for action, binding in compatible
        if _bindings_match(anchor_binding, binding)
    ]


def compatible_actions_for_export(armature):
    """Return the active source-binding group accepted by the direct exporter."""
    if bpy is None:
        raise RuntimeError("Blender is required for action discovery.")
    return tuple(_actions_for_export(armature))


def _animation_duration_frames(action, extras: dict, action_start: float) -> float:
    imported_duration_seconds = action.get("cp77_direct_anim_duration_seconds")
    try:
        # Pose sampler duration and float-track timing are independent in WolvenKit
        # GLBs. Some untouched clips deliberately contain trackKeys later than the
        # final pose key, so the imported sampler duration must remain authoritative.
        return max(0.0, float(imported_duration_seconds) * FPS)
    except (TypeError, ValueError):
        pass

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

    # Legacy/manually-created actions have no exact source sampler duration. Keep
    # their historical behavior by ensuring float-track keys are still representable.
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
            sampling = property_sampling(
                curves,
                action,
                force_dense=(
                    gltf_path == "rotation"
                    and any(
                        mode not in {"LINEAR", "CONSTANT"}
                        for curve in curves
                        for mode in curve_interpolations(curve)
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
    actions = _actions_for_export(
        armature,
        active_action_only=active_action_only,
        selected_action_names=selected_action_names,
    )
    binding = build_skeleton_export_binding(armature, action=actions[0])
    for action in actions[1:]:
        action_binding = build_skeleton_export_binding(armature, action=action)
        if not _bindings_match(binding, action_binding):
            raise DirectAnimationExportError(
                "The selected actions originate from different animation skins or "
                "source rest poses. A .anims.glb has one shared skin; export each "
                "source action set separately."
            )

    builder = GLBBuilder()
    nodes, skin = build_gltf_skeleton(binding, builder)
    animations = [
        build_animation_document(action, armature, binding, builder, export_tracks)
        for action in actions
    ]
    document = {
        "asset": {
            "copyright": "",
            "generator": DIRECT_ANIMATION_GENERATOR,
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
