from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

import bpy
import numpy as np

from ...animation.domain.clip.root_motion import root_motion_type_for_export
from ...animation.domain.clip.source_rest import source_rest_relative
from ...animation.domain.rig.naming import merged_bone_name
from ...animation.model.clip.binding import create_track_binding
from ...animation.model.clip.metadata import (
    ACTION_FIELDS,
    ANIMATION_EXTRAS_SNAPSHOT_KEY,
    FPS,
    SKIN_EXTRAS_SNAPSHOT_KEY,
    SOURCE_CHANNELS_SNAPSHOT_KEY,
    normalize_animation_extras,
    source_channel_index,
    track_payload_duration,
)
from ...animation.model.events.codec import event_array
from ...animation.services.rig.export_source import load_animation_rig_export_source
from ...assetio.paths import depot_path_key, same_local_path
from ...assetio.values import plain_value
from ...bartmoss.hierarchy import (
    bone_basis_corrections,
    local_matrices_to_model,
    model_matrices_to_local,
)
from ...bartmoss.matrix import as_matrix_4x4
from ...bartmoss.quaternion import normalize_sequence_xyzw
from ...bartmoss.trs import compose_matrices, compose_matrices_wxyz, decompose_matrices
from ...blender.action_metadata import (
    action_export_name,
    action_source_rest,
    ensure_action_defaults,
    load_json_snapshot,
    resolve_action_binding,
)
from ...blender.armature import inheritance_issue, rest_model_matrices
from ...blender.armature_bones import rig_space_contract
from ...blender.event_storage import save_events_to_idproperty
from ...blender.keyframes import (
    action_curve_map,
    curve_key_frames,
    evaluate_property,
    get_action_fcurves,
    property_curve_fingerprint,
    property_sampling,
    transform_curve_fingerprint,
)
from ...blender.rig_metadata import source_rig_paths
from ...blender.tracks import track_payload_from_fcurves, track_payload_needs_resampling
from ...core.log import get_logger, log_once
from ...gltf.anims import animation_channels, anims_document, skin_nodes
from ...gltf.builder import GLBBuilder
from ...gltf.extras import animation_extras_for_export
from ...gltf.provenance import DIRECT_ANIMATION_GENERATOR
from ...redSpace.contracts import RIG_SPACE_CONTRACT_CURRENT
from ...redSpace.transforms import blender_relative_to_gltf, skeleton_relative_to_gltf
from .errors import DirectAnimationExportError

_LOG = get_logger(__name__)


@dataclass(frozen=True)
class SkeletonExportBinding:
    source_names: tuple[str, ...]
    target_names: tuple[str, ...]
    parent_indices: tuple[int, ...]
    target_bones: tuple[Any, ...]
    rest_relative_blender: np.ndarray
    rest_relative_gltf: np.ndarray
    rest_global_gltf: np.ndarray
    basis_corrections: np.ndarray
    skin_extras: dict
    uses_source_rest_snapshot: bool
    authored_node_transforms: tuple = ()


def _sequence_plain(value):
    if value is None or isinstance(value, (str, bytes, dict)):
        return None
    try:
        return [plain_value(item) for item in value]
    except TypeError:
        return None


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


def build_skeleton_export_binding(
    armature, action=None, *, source_rig_path: str = ""
) -> SkeletonExportBinding:
    if armature is None or getattr(armature, "type", None) != "ARMATURE":
        raise DirectAnimationExportError(
            "Animation export requires one armature object."
        )
    contract = rig_space_contract(armature)
    if contract != RIG_SPACE_CONTRACT_CURRENT:
        raise DirectAnimationExportError(
            "The selected armature was not imported with the supported read_rig coordinate contract."
        )

    action_binding = resolve_action_binding(action, armature)
    selected_source = (
        load_animation_rig_export_source(source_rig_path) if source_rig_path else None
    )
    action_skin_snapshot = (
        load_json_snapshot(action, SKIN_EXTRAS_SNAPSHOT_KEY)
        if action is not None
        else {}
    )
    selected_skin = selected_source.skin_extras if selected_source is not None else {}
    action_matches_selected = bool(
        selected_source is not None
        and _action_matches_selected_source(
            armature,
            action_skin_snapshot,
            selected_source,
        )
    )
    if action_matches_selected:
        snapshot = copy.deepcopy(action_skin_snapshot)
    else:
        snapshot = selected_skin if selected_source is not None else action_binding.skin
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
        target_name = (
            source_name
            if armature.data.bones.get(source_name)
            else merged_bone_name(source_name)
        )
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
        issue = inheritance_issue(pose_bone.bone)
        if issue:
            raise DirectAnimationExportError(f"Bone {target_name!r} {issue}.")
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
            if selected_source is not None:
                raise
            parent_indices = _derive_parent_indices(target_bones)
    elif selected_source is not None:
        raise DirectAnimationExportError(
            "The selected source rig/action has no complete boneParentIndexes table."
        )
    else:
        parent_indices = _derive_parent_indices(target_bones)
    _validate_parent_indices(source_names, parent_indices)

    selected_rest = (
        source_rest_relative(
            selected_source.source_rest,
            selected_source.bone_names,
        )
        if selected_source is not None
        else None
    )
    has_pose_payload = bool(
        action is not None and _action_has_pose_payload(action, armature, target_names)
    )
    if selected_source is not None and action_matches_selected and has_pose_payload:
        exact_action_rest = source_rest_relative(
            action_source_rest(action),
            source_names,
        )
        if exact_action_rest is None:
            raise DirectAnimationExportError(
                f"Action {action.name!r} has source-rig identity metadata but no complete "
                "source-rest snapshot. Re-import the animation before exporting it from "
                "a merged MetaRig; substituting the rig A-pose could alter keyed transforms."
            )
    if (
        selected_source is not None
        and not action_skin_snapshot
        and has_pose_payload
        and selected_rest is not None
    ):
        live_model = np.asarray(
            [as_matrix_4x4(bone.matrix_local) for bone in target_bones],
            dtype=np.float64,
        )
        live_relative = model_matrices_to_local(live_model, parent_indices)
        if not np.allclose(
            live_relative,
            selected_rest,
            rtol=0.0,
            atol=1e-7,
        ):
            raise DirectAnimationExportError(
                f"Action {action.name!r} has no source-rig snapshot and its selected "
                "constituent rig uses a different rest basis than the merged MetaRig. "
                "Export cannot reinterpret those Blender pose keys without changing transforms."
            )

    source_rest_snapshot = (
        action_source_rest(action)
        if action_matches_selected
        else selected_source.source_rest
        if selected_source is not None
        else action_binding.source_rest
    )
    rest_relative_blender = source_rest_relative(
        source_rest_snapshot,
        source_names,
    )
    uses_source_rest_snapshot = rest_relative_blender is not None
    if rest_relative_blender is None and selected_source is not None:
        selected_count = len(selected_source.bone_names)
        if (
            selected_rest is not None
            and source_names[:selected_count] == selected_source.bone_names
        ):
            if selected_count != len(source_names):
                raise DirectAnimationExportError(
                    "The selected action contains animation-specific extra joints but "
                    "has no complete source-rest snapshot for those joints. Re-import "
                    "the animation before exporting it from a merged MetaRig."
                )
            rest_relative_blender = selected_rest
            uses_source_rest_snapshot = True
    # The rest bases the animation import binds against: matrix_local without its float32 scale and shear noise.
    rest_model_blender = rest_model_matrices(target_bones)
    if rest_relative_blender is None:
        model_matrices = rest_model_blender
        rest_relative_blender = model_matrices_to_local(model_matrices, parent_indices)

    rest_relative_gltf = skeleton_relative_to_gltf(
        rest_relative_blender, parent_indices
    )
    rest_global_gltf = local_matrices_to_model(rest_relative_gltf, parent_indices)

    snapshot = copy.deepcopy(snapshot)
    track_names = (
        tuple(str(value) for value in snapshot.get("trackNames", ()))
        if action_matches_selected
        else selected_source.track_names
        if selected_source is not None
        else action_binding.tracks.names
    )
    if len(set(track_names)) != len(track_names):
        raise DirectAnimationExportError("Animation skin trackNames must be unique.")
    rig_path = str(snapshot.get("rigPath", "") or "")
    if not rig_path and selected_source is not None:
        rig_path = selected_source.rig_path
    skin_extras = {
        "rigPath": rig_path,
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
        basis_corrections=bone_basis_corrections(
            rest_relative_blender, parent_indices, rest_model_blender
        ),
        skin_extras=skin_extras,
        uses_source_rest_snapshot=uses_source_rest_snapshot,
        authored_node_transforms=_authored_node_transforms(
            source_rest_snapshot, source_names, rest_relative_gltf
        ),
    )


def _authored_node_transforms(snapshot, source_names, rest_relative_gltf) -> tuple:
    """Retain exact source TRS components when they describe the exported rest matrices"""
    if (
        not isinstance(snapshot, dict)
        or tuple(snapshot.get("boneNames", ())) != source_names
    ):
        return ()
    transforms = snapshot.get("gltfTransforms")
    if not isinstance(transforms, list) or len(transforms) != len(source_names):
        return ()
    result, indices, translations, rotations, scales = [], [], [], [], []
    for index, value in enumerate(transforms):
        node = (
            {
                key: value[key]
                for key in ("translation", "rotation", "scale")
                if key in value
            }
            if isinstance(value, dict)
            else None
        )
        if node is not None:
            try:
                translation = np.asarray(
                    node.get("translation", (0, 0, 0)), dtype=np.float64
                ).reshape(3)
                rotation = np.asarray(
                    node.get("rotation", (0, 0, 0, 1)), dtype=np.float64
                ).reshape(4)
                scale = np.asarray(
                    node.get("scale", (1, 1, 1)), dtype=np.float64
                ).reshape(3)
            except (TypeError, ValueError):
                node = None
            else:
                indices.append(index)
                translations.append(translation)
                rotations.append(rotation)
                scales.append(scale)
        result.append(node)
    if indices:
        matrices = compose_matrices(translations, rotations, scales)
        matches = np.all(
            np.abs(matrices - rest_relative_gltf[indices]) <= 1e-7, axis=(1, 2)
        )
        for index, matches_rest in zip(indices, matches):
            if not matches_rest:
                result[index] = None
    return tuple(result)


def _action_fcurves(action, armature=None):
    curves = get_action_fcurves(action, armature)
    return list(curves) if curves is not None else []


def _basis_at_frames(curve_map, paths, frames):
    locations, _ = evaluate_property(
        curve_map, paths["location"], 3, frames, (0.0, 0.0, 0.0)
    )
    rotations, _ = evaluate_property(
        curve_map, paths["rotation_quaternion"], 4, frames, (1.0, 0.0, 0.0, 0.0)
    )
    scales, _ = evaluate_property(curve_map, paths["scale"], 3, frames, (1.0, 1.0, 1.0))
    lengths = np.linalg.norm(rotations, axis=1)
    invalid = lengths <= 1e-15
    rotations[invalid] = (1.0, 0.0, 0.0, 0.0)
    rotations /= np.maximum(np.linalg.norm(rotations, axis=1)[:, None], 1e-15)
    return compose_matrices_wxyz(locations, rotations, scales)


def _source_property_values(binding, joint_index, basis_matrices, path):
    correction = binding.basis_corrections[joint_index]
    source_basis = correction @ basis_matrices @ np.linalg.inv(correction)
    relative_blender = np.matmul(
        binding.rest_relative_blender[joint_index], source_basis
    )
    relative_gltf = blender_relative_to_gltf(
        relative_blender, binding.parent_indices[joint_index] < 0
    )
    translations, rotations, scales = decompose_matrices(relative_gltf)
    if path == "translation":
        return translations
    if path == "rotation":
        return normalize_sequence_xyzw(rotations)
    if path == "scale":
        return scales
    raise DirectAnimationExportError(f"Unsupported glTF animation path {path!r}.")


def _scale_allows_sparse(binding, joint_index, curves) -> bool:
    axes = binding.rest_relative_blender[joint_index, :3, :3]
    if not np.allclose(axes.T @ axes, np.eye(3), rtol=0.0, atol=1e-7):
        return False
    if np.linalg.det(axes) <= 0.0:
        return False
    for curve in curves:
        if getattr(curve, "mute", False):
            continue
        for frame in curve_key_frames(curve):
            if not float(curve.evaluate(float(frame))) > 1e-8:
                return False
    return True


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
    # Key times round to the nearest float32, as glTF stores them.
    return np.asarray(frame_offsets / FPS, dtype=np.float32).astype(np.float64)


def _gltf_channel_samples(frames, values, action_start: float, *, quaternion=False):
    """Merge equivalent samples that serialize to the same FLOAT timestamp"""
    times = _gltf_times_from_frames(frames, action_start)
    values = np.asarray(values, dtype=np.float64)
    differences = np.diff(times)
    if np.any(differences < 0):
        raise DirectAnimationExportError("Animation sample times are not ordered.")
    collisions = np.flatnonzero(differences == 0)
    if len(collisions):
        error = np.max(np.abs(values[collisions] - values[collisions + 1]), axis=1)
        if quaternion:
            error = np.minimum(
                error,
                np.max(np.abs(values[collisions] + values[collisions + 1]), axis=1),
            )
        if np.any(error > 1e-6):
            raise DirectAnimationExportError(
                "Distinct animation values collapse onto one FLOAT timestamp. "
                "Separate the affected keyframes before exporting."
            )
        keep = np.concatenate((differences > 0, [True]))
        times, values = times[keep], values[keep]
    return times, values


def _direct_integer_array(value, action_name: str, key: str) -> list[int]:
    """Convert a Blender integer IDPropertyArray without changing the Action"""
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


def _selected_source_structure_matches(
    action_skin: dict,
    selected_skin: dict,
) -> bool:
    if not action_skin or not selected_skin:
        return False
    action_names = tuple(str(value) for value in action_skin.get("boneNames", ()))
    selected_names = tuple(str(value) for value in selected_skin.get("boneNames", ()))
    if action_names != selected_names:
        return False

    try:
        action_parents = tuple(
            int(value) for value in action_skin.get("boneParentIndexes", ())
        )
        selected_parents = tuple(
            int(value) for value in selected_skin.get("boneParentIndexes", ())
        )
    except (TypeError, ValueError):
        return False
    if len(action_parents) != len(action_names):
        return False
    if action_parents != selected_parents:
        return False

    action_tracks = tuple(str(value) for value in action_skin.get("trackNames", ()))
    selected_tracks = tuple(str(value) for value in selected_skin.get("trackNames", ()))
    return action_tracks == selected_tracks


def _selected_source_identity_matches(
    action_skin: dict,
    selected_skin: dict,
) -> bool:
    if not _selected_source_structure_matches(action_skin, selected_skin):
        return False
    action_rig_path = str(action_skin.get("rigPath", "") or "")
    selected_rig_path = str(selected_skin.get("rigPath", "") or "")
    return bool(
        action_rig_path
        and selected_rig_path
        and depot_path_key(action_rig_path) == depot_path_key(selected_rig_path)
    )


def _action_matches_selected_source(
    armature,
    action_skin: dict,
    selected_source,
) -> bool:
    if not action_skin or selected_source is None:
        return False
    if _selected_source_identity_matches(action_skin, selected_source.skin_extras):
        return True
    if str(action_skin.get("rigPath", "") or ""):
        return False

    matching_paths = []
    for candidate_path in source_rig_paths(armature):
        try:
            candidate = load_animation_rig_export_source(candidate_path)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            raise DirectAnimationExportError(
                f"Could not verify MetaRig source-rig identity for {candidate_path!r}: {error}"
            ) from error
        if _selected_source_structure_matches(action_skin, candidate.skin_extras):
            matching_paths.append(candidate.source_path)

    return len(matching_paths) == 1 and same_local_path(
        matching_paths[0], selected_source.source_path
    )


def _skin_identity_matches(left: dict, right: dict) -> bool:
    if not left or not right:
        return False
    left_names = tuple(str(value) for value in left.get("boneNames", ()))
    right_names = tuple(str(value) for value in right.get("boneNames", ()))
    if left_names != right_names:
        return False
    try:
        left_parents = tuple(int(value) for value in left.get("boneParentIndexes", ()))
        right_parents = tuple(
            int(value) for value in right.get("boneParentIndexes", ())
        )
    except (TypeError, ValueError):
        return False
    if left_parents != right_parents:
        return False
    left_tracks = tuple(str(value) for value in left.get("trackNames", ()))
    right_tracks = tuple(str(value) for value in right.get("trackNames", ()))
    if left_tracks != right_tracks:
        return False
    left_rig_path = str(left.get("rigPath", "") or "")
    right_rig_path = str(right.get("rigPath", "") or "")
    if left_rig_path and right_rig_path:
        return depot_path_key(left_rig_path) == depot_path_key(right_rig_path)
    return True


def _action_skin_matches_binding(action, binding: SkeletonExportBinding) -> bool:
    snapshot = load_json_snapshot(action, SKIN_EXTRAS_SNAPSHOT_KEY)
    return _skin_identity_matches(snapshot, binding.skin_extras)


def _action_source_channels_match_binding(
    action, binding: SkeletonExportBinding
) -> bool:
    if not _action_skin_matches_binding(action, binding):
        return False
    rest = source_rest_relative(action_source_rest(action), binding.source_names)
    return rest is not None and bool(
        np.allclose(rest, binding.rest_relative_blender, rtol=0.0, atol=1e-7)
    )


def _action_has_source_pose_payload(action) -> bool:
    """Distinguish authored transform samples from preserved channel omissions"""
    return any(
        not channel.get("omitted", False)
        for channel in source_channel_index(
            load_json_snapshot(action, SOURCE_CHANNELS_SNAPSHOT_KEY)
        ).values()
    )


def _has_unbound_preserved_payload(action) -> bool:
    if _action_has_source_pose_payload(action):
        return True
    extras = load_json_snapshot(action, ANIMATION_EXTRAS_SNAPSHOT_KEY)
    return bool(extras.get("trackKeys") or extras.get("constTrackKeys"))


def _animation_extras(
    action,
    armature,
    binding,
    export_tracks: bool = True,
    *,
    strict_source_binding: bool = False,
) -> dict:
    """Prepare and serialize the individual Action properties used by CP77"""
    source_extras = normalize_animation_extras(
        load_json_snapshot(action, ANIMATION_EXTRAS_SNAPSHOT_KEY),
        label=f"Action {action.name!r} source extras",
        error_type=DirectAnimationExportError,
    )
    ensure_action_defaults(action)

    try:
        save_events_to_idproperty(action)
    except Exception as error:
        raise DirectAnimationExportError(
            f"Action {action.name!r} animation events could not be serialized: {error}"
        ) from error

    # The direct writer controls its extras explicitly, so internal properties
    # cannot leak into the GLB and do not need to be deleted from the Action.
    binding_skin_extras = binding.skin_extras
    source_binding_matches = not strict_source_binding or _action_skin_matches_binding(
        action, binding
    )
    if (
        strict_source_binding
        and not source_binding_matches
        and not export_tracks
        and (source_extras.get("trackKeys") or source_extras.get("constTrackKeys"))
    ):
        raise DirectAnimationExportError(
            f"Action {action.name!r} cannot preserve float-track source payload "
            "without a matching source-rig identity snapshot."
        )
    source_track_keys = (
        source_extras.get("trackKeys", action.get("trackKeys", ()))
        if source_binding_matches
        else ()
    )
    source_const_track_keys = (
        source_extras.get("constTrackKeys", action.get("constTrackKeys", ()))
        if source_binding_matches
        else ()
    )
    if export_tracks:
        track_keys, const_track_keys = track_payload_from_fcurves(
            action,
            armature,
            source_track_keys=source_track_keys,
            source_const_track_keys=source_const_track_keys,
            skin_extras=binding_skin_extras,
            track_binding=create_track_binding(
                binding_skin_extras.get("trackNames", ())
            ),
            prefer_simd=bool(
                (action.get("optimizationHints") or {}).get("preferSIMD", False)
            ),
            duration_seconds=_animation_duration_frames(
                action, source_extras, float(action.frame_range[0])
            )
            / FPS,
            error_type=DirectAnimationExportError,
        )
    else:
        if source_track_keys and track_payload_needs_resampling(
            action,
            source_track_keys=source_track_keys,
            prefer_simd=bool(
                (action.get("optimizationHints") or {}).get("preferSIMD", False)
            ),
            duration_seconds=_animation_duration_frames(
                action, source_extras, float(action.frame_range[0])
            )
            / FPS,
            source_extras=source_extras,
        ):
            raise DirectAnimationExportError(
                f"Action {action.name!r} needs a new SIMD float-track grid. "
                "Import its float tracks and enable float-track synchronization before changing the duration or storage encoding."
            )
        # Keep the imported payload intact but do not rebuild it from live float
        # FCurves. This makes the option non-destructive for untouched clips.
        track_keys = copy.deepcopy(source_track_keys or [])
        const_track_keys = copy.deepcopy(source_const_track_keys or [])
    if "animEvents" in action:
        event_payload = event_array(
            action["animEvents"], action.name, DirectAnimationExportError
        )
        if source_extras.get("animEvents") is None and not event_payload:
            event_payload = None
    else:
        event_payload = copy.deepcopy(source_extras.get("animEvents", []))

    extras = dict(source_extras)
    extras.update(
        {
            "schema": plain_value(action["schema"]),
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
            "optimizationHints": plain_value(action["optimizationHints"]),
            "animEvents": event_payload,
        }
    )

    return animation_extras_for_export(extras)


def _validate_binding_counts(action, binding, extras: dict) -> None:
    track_names = binding.skin_extras.get("trackNames") or ()
    has_track_payload = any(
        extras.get(label, ()) for label in ("trackKeys", "constTrackKeys")
    )
    if has_track_payload and not track_names:
        raise DirectAnimationExportError(
            f"Action {action.name!r} contains track keys, but its skin exposes no trackNames."
        )
    for label in ("trackKeys", "constTrackKeys"):
        for entry in extras.get(label, ()) or ():
            track_index = int(entry.get("trackIndex", -1))
            if track_index >= len(track_names):
                raise DirectAnimationExportError(
                    f"Action {action.name!r} {label} references track {track_index}, "
                    f"but the rig exposes only {len(track_names)} tracks."
                )


def _unchanged_source_channel(
    source_channel, curve_map, data_path: str, width: int, *, transform_fingerprint=None
):
    if not isinstance(source_channel, dict):
        return None
    fingerprint = source_channel.get("curveFingerprint")
    current_fingerprint = transform_fingerprint or property_curve_fingerprint(
        curve_map, data_path, width
    )
    if not isinstance(fingerprint, str) or fingerprint != current_fingerprint:
        return None
    if source_channel.get("omitted") is True:
        return {"omitted": True}
    interpolation = str(source_channel.get("interpolation", "")).upper()
    if interpolation not in {"LINEAR", "STEP"}:
        return None
    try:
        times = np.asarray(source_channel.get("times"), dtype=np.float64).reshape(-1)
        values = np.asarray(source_channel.get("values"), dtype=np.float64).reshape(
            len(times), width
        )
    except (TypeError, ValueError):
        return None
    if (
        not len(times)
        or not np.all(np.isfinite(times))
        or not np.all(np.isfinite(values))
    ):
        return None
    if times[0] < 0.0 or np.any(np.diff(times) <= 0.0):
        return None
    return {
        "interpolation": interpolation,
        "times": times,
        "values": values,
    }


def _target_pose_paths(armature, target_names) -> set[str]:
    paths = set()
    for target_name in target_names:
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


def _is_pose_transform_path(data_path: str) -> bool:
    value = str(data_path or "")
    return value.startswith("pose.bones[") and value.endswith(
        (".location", ".rotation_quaternion", ".scale")
    )


def _action_pose_curve_paths(action, armature=None) -> set[str]:
    return {
        str(curve.data_path)
        for curve in _action_fcurves(action, armature)
        if _is_pose_transform_path(curve.data_path)
    }


def _action_has_pose_payload(action, armature, target_names) -> bool:
    target_paths = _target_pose_paths(armature, target_names)
    if _action_pose_curve_paths(action, armature) & target_paths:
        return True
    return _action_has_source_pose_payload(action)


def _action_has_cp77_payload(action, target_paths: set[str], armature=None) -> bool:
    for curve in _action_fcurves(action, armature):
        if curve.data_path in target_paths:
            return True
    if any(key in action for key in ACTION_FIELDS):
        return True
    return bool(action.get(ANIMATION_EXTRAS_SNAPSHOT_KEY))


def _bindings_match(left, right) -> bool:
    if left.source_names != right.source_names:
        return False
    if left.parent_indices != right.parent_indices:
        return False
    if plain_value(left.skin_extras) != plain_value(right.skin_extras):
        return False
    return bool(
        np.allclose(
            left.rest_relative_blender,
            right.rest_relative_blender,
            rtol=0.0,
            atol=1e-7,
        )
    )


def _binding_for_action(armature, action, *, source_rig_path: str = ""):
    binding = build_skeleton_export_binding(
        armature, action=action, source_rig_path=source_rig_path
    )
    if source_rig_path:
        action_skin = load_json_snapshot(action, SKIN_EXTRAS_SNAPSHOT_KEY)
        if action_skin:
            selected_source = load_animation_rig_export_source(source_rig_path)
            if not _action_matches_selected_source(
                armature,
                action_skin,
                selected_source,
            ):
                raise DirectAnimationExportError(
                    f"Action {action.name!r} cannot be uniquely bound to the selected source rig."
                )
        if not action_skin and _has_unbound_preserved_payload(action):
            raise DirectAnimationExportError(
                f"Action {action.name!r} contains preserved source animation data but "
                "has no source-rig identity snapshot. Re-import the animation before "
                "exporting it from a merged MetaRig."
            )
        if not action_skin:
            target_paths = _target_pose_paths(armature, binding.target_names)
            pose_curve_paths = _action_pose_curve_paths(action, armature)
            if pose_curve_paths and not (pose_curve_paths & target_paths):
                raise DirectAnimationExportError(
                    f"Action {action.name!r} has pose keys, but none target the selected "
                    "MetaRig constituent."
                )
    target_paths = _target_pose_paths(armature, binding.target_names)
    if not _action_has_cp77_payload(action, target_paths, armature):
        raise DirectAnimationExportError(
            f"Action {action.name!r} has no CP77 animation payload for this armature."
        )
    return binding


def _action_bindings_for_export(
    armature,
    active_action_only=False,
    selected_action_names=None,
    source_rig_path: str = "",
):
    animation_data = getattr(armature, "animation_data", None)
    active_action = getattr(animation_data, "action", None)

    if active_action_only:
        if active_action is None:
            raise DirectAnimationExportError(
                "The selected armature has no active action."
            )
        return [
            (
                active_action,
                _binding_for_action(
                    armature, active_action, source_rig_path=source_rig_path
                ),
            )
        ]

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
                binding = _binding_for_action(
                    armature, action, source_rig_path=source_rig_path
                )
            except DirectAnimationExportError:
                incompatible.append(name)
                continue
            actions.append((action, binding))
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
            binding = _binding_for_action(
                armature, action, source_rig_path=source_rig_path
            )
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
        (action, binding)
        for action, binding in compatible
        if _bindings_match(anchor_binding, binding)
    ]


def compatible_actions_for_export(armature, *, source_rig_path: str = ""):
    """Return actions compatible with one explicit source rig binding"""
    return tuple(
        action
        for action, _ in _action_bindings_for_export(
            armature, source_rig_path=source_rig_path
        )
    )


def _animation_duration_frames(action, extras: dict, action_start: float) -> float:
    duration = max(0.0, track_payload_duration(extras) * FPS)
    imported_duration_seconds = action.get("cp77_direct_anim_duration_seconds")
    try:
        duration = max(duration, float(imported_duration_seconds) * FPS)
    except (TypeError, ValueError):
        pass

    try:
        frame_end = float(action.frame_range[1])
    except (AttributeError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_animation_duration_frames", type(error).__name__),
            "animation duration frames: fell back after %s",
            error,
            exc_info=True,
        )
        frame_end = action_start
    frame_duration = frame_end - action_start
    frame_precision = 2.0 * max(
        abs(float(np.spacing(np.float32(duration)))),
        abs(float(np.spacing(np.float32(frame_end)))),
        abs(float(np.spacing(np.float32(action_start)))),
    )
    if frame_duration > duration + frame_precision:
        duration = frame_duration

    if imported_duration_seconds is None:
        imported_frame_count = action.get("cp77_direct_anim_frame_count")
        try:
            duration = max(duration, float(imported_frame_count) - 1.0)
        except (TypeError, ValueError):
            pass

    return duration


def _validate_track_times(action, extras: dict, duration_frames: float) -> None:
    duration_seconds = max(0.0, float(duration_frames) / FPS)
    tolerance = max(1e-6, duration_seconds * 1e-6)
    for label in ("trackKeys", "constTrackKeys"):
        for index, entry in enumerate(extras.get(label, ()) or ()):
            time_value = float(entry.get("time", 0.0))
            if time_value > duration_seconds + tolerance:
                raise DirectAnimationExportError(
                    f"Action {action.name!r} {label}[{index}] occurs at {time_value:.9g}s, "
                    f"after the animation duration {duration_seconds:.9g}s."
                )


def _append_duration_hold(
    channel_payloads: list[dict], binding, duration_frames: float
) -> None:
    if duration_frames <= 0.0 and channel_payloads:
        return
    duration_seconds = float(_gltf_times_from_frames((duration_frames,), 0.0)[0])
    current_end = max(
        (
            float(payload["times"][-1])
            for payload in channel_payloads
            if len(payload["times"])
        ),
        default=-1.0,
    )
    if current_end >= duration_seconds:
        return

    if channel_payloads:
        payload = channel_payloads[0]
        payload["times"] = np.concatenate(
            (
                np.asarray(payload["times"], dtype=np.float64),
                np.asarray([duration_seconds]),
            )
        )
        payload["values"] = np.concatenate(
            (
                np.asarray(payload["values"], dtype=np.float64),
                np.asarray(payload["values"][-1:], dtype=np.float64),
            ),
            axis=0,
        )
        return

    translation, _, _ = decompose_matrices(
        binding.rest_relative_gltf[0].reshape(1, 4, 4)
    )
    times = np.asarray(
        (0.0, duration_seconds) if duration_seconds > 0.0 else (0.0,), dtype=np.float64
    )
    channel_payloads.append(
        {
            "joint_index": 0,
            "path": "translation",
            "interpolation": "LINEAR",
            "times": times,
            "values": np.repeat(translation, len(times), axis=0),
        }
    )


def build_animation_document(
    action,
    armature,
    binding,
    builder,
    export_tracks: bool,
    *,
    strict_source_binding: bool = False,
    root_motion: str = "CLIP",
):
    extras = _animation_extras(
        action,
        armature,
        binding,
        export_tracks,
        strict_source_binding=strict_source_binding,
    )
    curve_map = action_curve_map(
        action, armature, error_type=DirectAnimationExportError
    )
    source_channels = source_channel_index(
        load_json_snapshot(action, SOURCE_CHANNELS_SNAPSHOT_KEY)
        if (
            not strict_source_binding
            or _action_source_channels_match_binding(action, binding)
        )
        else {}
    )
    _validate_binding_counts(action, binding, extras)
    action_start = float(action.frame_range[0])
    duration_frames = _animation_duration_frames(action, extras, action_start)
    _validate_track_times(action, extras, duration_frames)
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
        coupled_pivot = bool(
            np.any(np.abs(binding.basis_corrections[joint_index, :3, 3]) > 1e-8)
        )
        transform_fingerprint = (
            transform_curve_fingerprint(curve_map, paths) if coupled_pivot else None
        )
        property_specs = (
            ("translation", "location", 3),
            ("rotation", "rotation_quaternion", 4),
            ("scale", "scale", 3),
        )
        for gltf_path, blender_property, width in property_specs:
            source_payload = _unchanged_source_channel(
                source_channels.get((joint_index, gltf_path)),
                curve_map,
                paths[blender_property],
                width,
                transform_fingerprint=transform_fingerprint,
            )
            if source_payload is not None:
                if not source_payload.get("omitted"):
                    channel_payloads.append(
                        {
                            "joint_index": joint_index,
                            "path": gltf_path,
                            **source_payload,
                        }
                    )
                continue
            curves = [
                curve_map[(paths[blender_property], component)]
                for component in range(width)
                if (paths[blender_property], component) in curve_map
            ]
            if coupled_pivot and gltf_path == "translation":
                curves = [
                    curve
                    for (path, _), curve in curve_map.items()
                    if path in paths.values()
                ]
            sampling = property_sampling(
                curves,
                action,
                force_dense=(
                    gltf_path == "rotation"
                    or (coupled_pivot and gltf_path == "translation")
                    or (
                        gltf_path == "scale"
                        and not _scale_allows_sparse(binding, joint_index, curves)
                    )
                ),
                frame_start=action_start,
                frame_end=action_start + duration_frames,
            )
            if sampling is None:
                continue
            frames, interpolation = sampling
            basis = _basis_at_frames(curve_map, paths, frames)
            values = _source_property_values(binding, joint_index, basis, gltf_path)
            rest_translation, rest_rotation, rest_scale = decompose_matrices(
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
                times, values = _gltf_channel_samples(
                    frames, values, action_start, quaternion=(gltf_path == "rotation")
                )
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

    try:
        extras["rootMotionType"] = root_motion_type_for_export(
            extras["rootMotionType"],
            root_motion,
            has_root_transforms=any(
                payload["joint_index"] == 0
                and payload["path"] in {"translation", "rotation"}
                for payload in channel_payloads
            ),
        )
        if extras["rootMotionType"] not in {"Unknown", "None"}:
            for payload in channel_payloads:
                if payload["joint_index"] != 0 or payload["path"] not in {
                    "translation",
                    "rotation",
                }:
                    continue
                if payload["interpolation"] == "STEP":
                    if not _values_are_default(
                        payload["values"],
                        payload["values"][0],
                        quaternion=(payload["path"] == "rotation"),
                    ):
                        raise ValueError(
                            "WolvenKit root motion requires linear interpolation. Change the stepped root channels to linear or disable root motion."
                        )
                    payload["interpolation"] = "LINEAR"
    except ValueError as error:
        raise DirectAnimationExportError(f"Action {action.name!r}: {error}") from error
    _append_duration_hold(channel_payloads, binding, duration_frames)
    samplers, channels = animation_channels(channel_payloads, builder)

    return {
        "name": action_export_name(action),
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
    source_rig_path: str = "",
    root_motion: str = "CLIP",
):
    rig_sources = source_rig_paths(armature)
    if len(rig_sources) > 1 and not source_rig_path:
        raise DirectAnimationExportError(
            "Merged MetaRig animation export requires one constituent source rig selection."
        )
    if (
        source_rig_path
        and rig_sources
        and not any(
            same_local_path(source_rig_path, candidate) for candidate in rig_sources
        )
    ):
        raise DirectAnimationExportError(
            "The selected animation source rig is not part of this MetaRig."
        )
    action_bindings = _action_bindings_for_export(
        armature,
        active_action_only=active_action_only,
        selected_action_names=selected_action_names,
        source_rig_path=source_rig_path,
    )
    actions = [action for action, _ in action_bindings]
    export_names = [action_export_name(action) for action in actions]
    if len(set(export_names)) != len(export_names):
        raise DirectAnimationExportError(
            "The selected actions contain duplicate game clip names. Select one copy "
            "of each clip or rename the duplicate actions before exporting."
        )
    binding = action_bindings[0][1]
    for action, action_binding in action_bindings[1:]:
        if not _bindings_match(binding, action_binding):
            raise DirectAnimationExportError(
                "The selected actions originate from different animation skins or "
                "source rest poses. A .anims.glb has one shared skin; export each "
                "source action set separately."
            )

    builder = GLBBuilder(error_type=DirectAnimationExportError)
    nodes, skin = skin_nodes(
        binding.source_names,
        binding.parent_indices,
        binding.rest_relative_gltf,
        binding.rest_global_gltf,
        binding.skin_extras,
        builder,
        authored_transforms=binding.authored_node_transforms,
    )
    animations = [
        build_animation_document(
            action,
            armature,
            binding,
            builder,
            export_tracks,
            strict_source_binding=bool(source_rig_path),
            root_motion=root_motion,
        )
        for action in actions
    ]
    document = anims_document(
        nodes, skin, animations, builder, DIRECT_ANIMATION_GENERATOR
    )
    return (
        document,
        bytes(builder.binary),
        {
            "animation_count": len(animations),
            "joint_count": len(binding.source_names),
            "accessor_count": len(builder.accessors),
            "binary_bytes": len(builder.binary),
            "source_rest_snapshot": bool(binding.uses_source_rest_snapshot),
            "source_rig_path": str(source_rig_path or ""),
            "root_motion": root_motion,
            "root_motion_types": {
                motion_type: sum(
                    animation["extras"]["rootMotionType"] == motion_type
                    for animation in animations
                )
                for motion_type in sorted(
                    {animation["extras"]["rootMotionType"] for animation in animations}
                )
            },
        },
    )
