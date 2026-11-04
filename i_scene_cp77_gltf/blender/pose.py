from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import numpy as np
from mathutils import Matrix, Quaternion, Vector

from ..animation.model.animgraph.frames import TrackSnapshot
from ..bartmoss.qs_transform import QsTransform
from ..bartmoss.quaternion import wxyz_from_xyzw
from ..redSpace.contracts import RIG_SPACE_CONTRACT_CURRENT
from ..redSpace.transforms import red_additive_to_rig_contract
from .armature_bones import resolve_pose_bone


def interpolate_matrix_trs(previous, current, factor):
    return Matrix.LocRotScale(
        *interpolate_matrix_trs_components(previous, current, factor)
    )


def blend_matrix_trs(current, target, weight):
    if weight <= 0.0:
        return current.copy()
    if weight >= 1.0:
        return target.copy()
    return interpolate_matrix_trs(current, target, weight)


def interpolate_matrix_trs_components(previous, current, factor):
    previous_location, previous_rotation, previous_scale = previous.decompose()
    current_location, current_rotation, current_scale = current.decompose()
    return (
        previous_location.lerp(current_location, factor),
        previous_rotation.slerp(current_rotation, factor),
        previous_scale.lerp(current_scale, factor),
    )


def interpolate_matrix_components(previous, current, factor):
    return (
        previous.translation.lerp(current.translation, factor),
        previous.to_quaternion().slerp(current.to_quaternion(), factor),
    )


def model_matrix_to_basis_explicit(
    pose_bone,
    desired_matrix,
    *,
    parent_matrix=None,
    parent_matrix_local=None,
):
    bone = getattr(pose_bone, "bone", None)
    if bone is None or not hasattr(bone, "convert_local_to_pose"):
        return None
    if parent_matrix is None:
        return bone.convert_local_to_pose(
            desired_matrix, bone.matrix_local, invert=True
        )
    return bone.convert_local_to_pose(
        desired_matrix,
        bone.matrix_local,
        parent_matrix=parent_matrix,
        parent_matrix_local=parent_matrix_local,
        invert=True,
    )


def model_matrix_to_basis(pose_bone, desired_matrix, parent_matrix=None):
    parent = pose_bone.parent
    return model_matrix_to_basis_explicit(
        pose_bone,
        desired_matrix,
        parent_matrix=parent_matrix if parent is not None else None,
        parent_matrix_local=parent.bone.matrix_local if parent is not None else None,
    )


def apply_model_space_matrix(pose_bone, matrix, parent_matrix=None):
    """Pose a bone so its model-space matrix becomes matrix, given its parent's model-space matrix"""
    basis = model_matrix_to_basis(pose_bone, matrix, parent_matrix)
    if basis is None:
        pose_bone.matrix = matrix
    else:
        pose_bone.matrix_basis = basis


def apply_model_space_matrices(pose_bones, matrices):
    """Pose bones to model-space matrices keyed by bone name"""
    parent_matrices = []
    for pose_bone in pose_bones:
        parent = pose_bone.parent
        parent_matrices.append(
            matrices[parent.name]
            if parent is not None and parent.name in matrices
            else (parent.matrix.copy() if parent is not None else Matrix.Identity(4))
        )
    bases = [
        model_matrix_to_basis(pose_bone, matrices[pose_bone.name], parent_matrix)
        for pose_bone, parent_matrix in zip(pose_bones, parent_matrices)
    ]
    for pose_bone, basis in zip(pose_bones, bases):
        if basis is None:
            pose_bone.matrix = matrices[pose_bone.name]
        else:
            pose_bone.matrix_basis = basis


def pose_bone_subtree_names(pose_bone):
    """Names of a pose bone and all its descendants, depth first in child order"""
    names = []
    stack = [pose_bone]
    while stack:
        current = stack.pop()
        names.append(current.name)
        stack.extend(reversed(current.children))
    return tuple(names)


def pose_bone_collection_indices(arm_obj, pose_bones) -> np.ndarray:
    """Index of each pose bone in arm_obj.pose.bones (-1 for missing bones)"""
    collection = arm_obj.pose.bones
    return np.asarray(
        [
            collection.find(pose_bone.name) if pose_bone is not None else -1
            for pose_bone in pose_bones
        ],
        dtype=np.intp,
    )


def apply_bound_red_local_deltas(
    arm_obj,
    pose_bones,
    bone_indices,
    rotations_xyzw,
    translations,
    collection_indices=None,
) -> int:
    contract = str(
        getattr(arm_obj, "data", {}).get(
            "cp77_rig_space_contract",
            RIG_SPACE_CONTRACT_CURRENT,
        )
    )
    translations, rotations = red_additive_to_rig_contract(
        translations, rotations_xyzw, contract
    )
    if collection_indices is None:
        collection_indices = pose_bone_collection_indices(arm_obj, pose_bones)
    if len(collection_indices) == len(bone_indices):
        return _write_pose_bones_bulk(
            arm_obj, bone_indices, rotations, translations, collection_indices
        )
    written = 0
    for offset, bone_index in enumerate(bone_indices):
        index = int(bone_index)
        pose_bone = pose_bones[offset]
        if pose_bone is None:
            continue
        qx, qy, qz, qw = (float(value) for value in rotations[index])
        tx, ty, tz = (float(value) for value in translations[index])
        pose_bone.rotation_mode = "QUATERNION"
        pose_bone.rotation_quaternion = (qw, qx, qy, qz)
        pose_bone.location = (tx, ty, tz)
        written += 1
    return written


_QUATERNION_MODE = 0  # bpy.types.PoseBone.bl_rna.properties["rotation_mode"].enum_items["QUATERNION"].value


def _write_pose_bones_bulk(
    arm_obj, bone_indices, rotations, translations, collection_indices
) -> int:
    # One foreach_get/foreach_set pair for all pose bones instead of three RNA writes per bone;
    # the stored float32 values are identical to the per-bone assignments.
    present = np.asarray(collection_indices) >= 0
    targets = np.asarray(collection_indices)[present]
    sources = np.asarray(bone_indices, dtype=np.intp)[present]
    if not len(targets):
        return 0
    collection = arm_obj.pose.bones
    count = len(collection)
    modes = np.empty(count, dtype=np.int32)
    collection.foreach_get("rotation_mode", modes)  # enum as int; QUATERNION is 0
    for index in targets[modes[targets] != _QUATERNION_MODE]:
        collection[int(index)].rotation_mode = "QUATERNION"
    rotation_buffer = np.empty(count * 4, dtype=np.float32)
    location_buffer = np.empty(count * 3, dtype=np.float32)
    collection.foreach_get("rotation_quaternion", rotation_buffer)
    collection.foreach_get("location", location_buffer)
    rotation_buffer.reshape(-1, 4)[targets] = wxyz_from_xyzw(
        np.asarray(rotations)[sources]
    )
    location_buffer.reshape(-1, 3)[targets] = np.asarray(translations)[sources]
    collection.foreach_set("rotation_quaternion", rotation_buffer)
    collection.foreach_set("location", location_buffer)
    # foreach_set skips the per-property RNA update, so tag the pose for re-evaluation.
    arm_obj.update_tag(refresh={"DATA"})
    return len(targets)


def qs_from_matrix(matrix: Any) -> QsTransform:
    location, rotation, scale = matrix.decompose()
    rotation.normalize()
    return QsTransform.from_components(
        tuple(location),
        (rotation.x, rotation.y, rotation.z, rotation.w),
        tuple(scale),
    )


def matrix_from_qs(transform: QsTransform) -> Matrix:
    x, y, z, w = transform.rotation_xyzw
    return Matrix.LocRotScale(
        Vector(transform.translation),
        Quaternion((w, x, y, z)),
        Vector(transform.scale),
    )


def capture_reference_pose_ls(
    armature: Any, names: Iterable[str]
) -> dict[str, QsTransform]:
    result = {}
    pose_bones = getattr(getattr(armature, "pose", None), "bones", None)
    for name in names:
        pose_bone = pose_bones.get(str(name)) if pose_bones is not None else None
        if pose_bone is None:
            raise KeyError(f"Bound armature is missing pose bone {name!r}")
        rest_ms = pose_bone.bone.matrix_local
        parent = getattr(pose_bone, "parent", None)
        rest_ls = (
            parent.bone.matrix_local.inverted_safe() @ rest_ms
            if parent is not None
            else rest_ms
        )
        result[str(pose_bone.name)] = qs_from_matrix(rest_ls)
    return result


def capture_engine_pose_bones(
    pose_bones: Mapping[str, Any],
    reference_pose_ls: Mapping[str, QsTransform],
) -> dict[str, QsTransform]:
    result = {}
    for name, pose_bone in pose_bones.items():
        reference = reference_pose_ls.get(name)
        if reference is None:
            raise KeyError(f"Reference pose is missing bone {name!r}")
        local_matrix = matrix_from_qs(reference) @ pose_bone.matrix_basis
        result[name] = qs_from_matrix(local_matrix)
    return result


def apply_engine_pose(
    armature: Any,
    transforms: Mapping[str, QsTransform],
    reference_pose_ls: Mapping[str, QsTransform],
) -> int:
    written = 0
    for name, transform in transforms.items():
        pose_bone = resolve_pose_bone(armature, name)
        reference = reference_pose_ls.get(name)
        if pose_bone is None or reference is None:
            continue
        basis = matrix_from_qs(reference).inverted_safe() @ matrix_from_qs(transform)
        pose_bone.matrix_basis = basis
        written += 1
    return written


def qs_from_pose_bone(pose_bone: Any) -> QsTransform:
    location, rotation, scale = pose_bone.matrix_basis.decompose()
    rotation.normalize()
    return QsTransform.from_components(
        tuple(location),
        (rotation.x, rotation.y, rotation.z, rotation.w),
        tuple(scale),
    )


def apply_qs_to_pose_bone(pose_bone: Any, transform: QsTransform) -> None:
    x, y, z, w = transform.rotation_xyzw
    pose_bone.matrix_basis = Matrix.LocRotScale(
        Vector(transform.translation),
        Quaternion((w, x, y, z)),
        Vector(transform.scale),
    )


def capture_pose(armature: Any, names: Iterable[str]) -> dict[str, QsTransform]:
    pose_bones = {}
    for name in names:
        pose_bone = resolve_pose_bone(armature, str(name))
        if pose_bone is None:
            raise KeyError(f"Bound armature is missing pose bone {name!r}")
        pose_bones[pose_bone.name] = pose_bone
    return capture_pose_bones(pose_bones)


def capture_pose_bones(pose_bones: Mapping[str, Any]) -> dict[str, QsTransform]:
    return {
        name: qs_from_pose_bone(pose_bone) for name, pose_bone in pose_bones.items()
    }


def capture_reference_pose_ms(
    armature: Any, names: Iterable[str]
) -> dict[str, QsTransform]:
    result = {}
    pose_bones = getattr(getattr(armature, "pose", None), "bones", None)
    for name in names:
        pose_bone = pose_bones.get(str(name)) if pose_bones is not None else None
        if pose_bone is None:
            raise KeyError(f"Bound armature is missing pose bone {name!r}")
        result[str(pose_bone.name)] = qs_from_matrix(pose_bone.bone.matrix_local)
    return result


def apply_pose(armature: Any, transforms: Mapping[str, QsTransform]) -> int:
    written = 0
    for name, transform in transforms.items():
        pose_bone = resolve_pose_bone(armature, name)
        if pose_bone is None:
            continue
        apply_qs_to_pose_bone(pose_bone, transform)
        written += 1
    return written


def capture_tracks(armature: Any, names: Iterable[str]) -> dict[str, TrackSnapshot]:
    result = {}
    for raw_name in names:
        name = str(raw_name or "")
        if not name:
            continue
        existed = name in armature
        value = float(armature.get(name, 0.0) or 0.0)
        result[name] = TrackSnapshot(existed, value)
    return result


def apply_tracks(armature: Any, values: Mapping[str, float]) -> int:
    written = 0
    for name, value in values.items():
        if not name:
            continue
        armature[str(name)] = float(value)
        written += 1
    return written


def restore_tracks(armature: Any, snapshots: Mapping[str, TrackSnapshot]) -> int:
    restored = 0
    for name, snapshot in snapshots.items():
        if snapshot.existed:
            armature[str(name)] = float(snapshot.value)
        elif name in armature:
            del armature[name]
        restored += 1
    return restored


def _resolves(owner: Any, data_path: str) -> bool:
    try:
        owner.path_resolve(data_path, False)
    except ValueError:
        return False
    return True


def _channel_group(keying_set: Any, path: Any) -> str:
    if path.group_method == "NAMED":
        return path.group
    return keying_set.bl_label if path.group_method == "KEYINGSET" else ""


def keying_set_channels(
    context: Any, bl_idname: str
) -> tuple[tuple[Any, str, int, str], ...]:
    """(ID, data path, index, group) for each channel the keying set bl_idname keys in context"""
    keying_set = next(
        item for item in context.scene.keying_sets_all if item.bl_idname == bl_idname
    )
    keying_set.refresh()
    return tuple(
        (
            path.id,
            path.data_path,
            -1 if path.use_entire_array else path.array_index,
            _channel_group(keying_set, path),
        )
        for path in keying_set.paths
        if _resolves(path.id, path.data_path)
    )


def insert_channel_keys(context: Any, channels, frame: float) -> int:
    """Key each keying_set_channels channel at frame as Blender's own keying does"""
    edit, tool_settings = context.preferences.edit, context.scene.tool_settings
    options = {
        option
        for option, enabled in (
            ("INSERTKEY_VISUAL", edit.use_visual_keying),
            ("INSERTKEY_NEEDED", edit.use_keyframe_insert_needed),
            ("INSERTKEY_CYCLE_AWARE", tool_settings.use_keyframe_cycle_aware),
        )
        if enabled
    }
    return sum(
        bool(
            owner.keyframe_insert(
                data_path,
                index=index,
                frame=frame,
                group=group,
                options=options,
                keytype=tool_settings.keyframe_type,
            )
        )
        for owner, data_path, index, group in channels
    )


def reset_pose_bones(armature: Any, names: Iterable[str] | None = None) -> None:
    """Return pose bones (all of them by default) to their rest transform"""
    bones = armature.pose.bones
    if names is None:
        for pose_bone in bones:
            pose_bone.matrix_basis.identity()
        return
    for name in names:
        pose_bone = bones.get(name)
        if pose_bone is not None:
            pose_bone.matrix_basis.identity()
