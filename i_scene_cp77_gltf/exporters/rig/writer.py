from __future__ import annotations

import copy
import heapq
import json
import os
from datetime import UTC, datetime
from typing import Any

import bpy
from mathutils import Matrix, Quaternion, Vector

from ...animation.domain.rig.metadata import (
    RIG_EXPORT_TEMPLATE_KEY,
    RIG_IMPORT_MATRIX_KEY,
    RIG_IMPORT_SOURCE_MODEL_KEY,
    decode_rig_export_template,
)
from ...animation.domain.rig.naming import blender_bone_name
from ...animation.services.rig.repository import rig_source_document
from ...assetio.atomic import atomic_write_text
from ...assetio.paths import strip_json_suffix
from ...assetio.rig_documents import minimal_rig_document
from ...assetio.values import cname_entry
from ...bartmoss.matrix import RIGID_TOLERANCE, rigid_matrices
from ...bartmoss.trs import compose_matrix
from ...blender.armature import rest_model_matrices
from ...blender.context import safe_mode_switch
from ...blender.matrix import matrix_from_flat
from ...blender.operator_results import OperationResult
from ...redSpace.contracts import RIG_SPACE_CONTRACT_CURRENT
from ...redSpace.transforms import (
    current_bone_model_transform_to_red,
    red_model_transform_to_current_bone,
)


def _imported_bone_matrix(bone) -> Matrix | None:
    return matrix_from_flat(bone.get(RIG_IMPORT_MATRIX_KEY))


def _imported_source_model_matrix(bone) -> Matrix | None:
    return matrix_from_flat(bone.get(RIG_IMPORT_SOURCE_MODEL_KEY))


def _to_list_of_strings(seq) -> list[str]:
    if not isinstance(seq, (list, tuple)):
        return []
    result = []
    for value in seq:
        if isinstance(value, dict) and "$value" in value:
            result.append(str(value.get("$value", "")))
        elif isinstance(value, str):
            result.append(value)
    return result


def _rig_export_template_from_armature(arm_obj) -> dict:
    arm_data = arm_obj.data
    stored = decode_rig_export_template(str(arm_data.get(RIG_EXPORT_TEMPLATE_KEY, "")))
    if stored is not None:
        return stored

    source = str(arm_data.get("cp77_source_rig_file", ""))
    if source and ";" not in source and os.path.isfile(source):
        loaded = rig_source_document(source)
        if loaded is not None:
            return loaded
    return minimal_rig_document(source)


def _source_name_index(source_names):
    index = {}
    for source_index, source_name in enumerate(source_names or ()):
        index.setdefault(str(source_name), source_index)
    return index


def _bone_source_index(bone, source_names=None, source_index_by_name=None):
    source_index = bone.get("cp77_rig_index")
    if isinstance(source_index, int) and source_index >= 0:
        return source_index
    if source_index_by_name is None:
        if not source_names:
            return None
        source_index_by_name = _source_name_index(source_names)
    source_name = str(bone.get("cp77_rig_source_name", bone.name))
    source_index = source_index_by_name.get(source_name)
    if source_index is not None:
        return source_index
    return source_index_by_name.get(str(bone.name))


def _ordered_export_bones(arm_data, lod_counts=()):
    """The bones in export order, parents first, and each bone's LOD rank"""
    bones = list(arm_data.bones)
    if not bones:
        return [], {}

    legacy_names = [str(value) for value in arm_data.get("boneNames", [])]
    source_index_by_name = _source_name_index(legacy_names)
    bone_by_name = {}
    priority_by_name = {}
    rank_by_name = {}
    seen_source_indices = set()

    for collection_index, bone in enumerate(bones):
        name = str(bone.name)
        if name in bone_by_name:
            raise ValueError(f"Duplicate armature bone name '{name}'.")
        bone_by_name[name] = bone

        source_index = _bone_source_index(
            bone, source_index_by_name=source_index_by_name
        )
        if source_index is not None and source_index not in seen_source_indices:
            seen_source_indices.add(source_index)
            priority_by_name[name] = (0, source_index, collection_index, name)
            rank_by_name[name] = source_index

    counts = sorted(int(count) for count in lod_counts)
    source_ranks = dict(rank_by_name)
    for collection_index, bone in enumerate(bones):
        name = str(bone.name)
        if name in source_ranks:
            continue
        ancestor = bone.parent
        while ancestor is not None and ancestor.name not in source_ranks:
            ancestor = ancestor.parent
        lod = next(
            (
                count
                for count in counts
                if ancestor is not None and source_ranks[ancestor.name] < count
            ),
            None,
        )
        if lod is None:
            priority_by_name[name] = (1, collection_index, collection_index, name)
            rank_by_name[name] = None
        else:
            priority_by_name[name] = (0, lod - 0.5, collection_index, name)
            rank_by_name[name] = lod - 0.5

    children_by_name = {name: [] for name in bone_by_name}
    indegree = {name: 0 for name in bone_by_name}
    for bone in bones:
        parent = bone.parent
        if parent is None:
            continue
        parent_name = str(parent.name)
        child_name = str(bone.name)
        if parent_name not in bone_by_name:
            raise ValueError(
                f"Bone '{child_name}' references parent '{parent_name}', which is not in the armature."
            )
        children_by_name[parent_name].append(child_name)
        indegree[child_name] = 1

    ready = []
    for name, degree in indegree.items():
        if degree == 0:
            heapq.heappush(ready, (priority_by_name[name], name))

    ordered = []
    while ready:
        _, name = heapq.heappop(ready)
        ordered.append(bone_by_name[name])
        for child_name in children_by_name[name]:
            indegree[child_name] -= 1
            if indegree[child_name] == 0:
                heapq.heappush(ready, (priority_by_name[child_name], child_name))

    if len(ordered) != len(bones):
        cyclic = sorted(name for name, degree in indegree.items() if degree > 0)
        raise ValueError(f"Cycle detected in armature hierarchy: {', '.join(cyclic)}")
    return ordered, rank_by_name


def _parent_indices_for_ordered_bones(bones):
    export_index = {str(bone.name): index for index, bone in enumerate(bones)}
    if len(export_index) != len(bones):
        raise ValueError("Bone names must be unique for rig export.")

    parent_indices = []
    for child_index, bone in enumerate(bones):
        parent = bone.parent
        if parent is None:
            parent_indices.append(-1)
            continue
        parent_name = str(parent.name)
        if parent_name not in export_index:
            raise ValueError(
                f"Bone '{bone.name}' references parent '{parent_name}', which is not in the export order."
            )
        parent_index = export_index[parent_name]
        if parent_index >= child_index:
            raise ValueError(
                f"Invalid export order: parent '{parent_name}' ({parent_index}) must precede "
                f"child '{bone.name}' ({child_index})."
            )
        parent_indices.append(parent_index)
    return parent_indices


def _validate_export_topology(bone_names, parent_indices, *parallel_arrays):
    count = len(bone_names)
    if len(set(bone_names)) != count:
        raise ValueError("Rig export contains duplicate bone names.")
    if len(parent_indices) != count:
        raise ValueError("boneParentIndexes length does not match boneNames length.")
    for array_name, values in parallel_arrays:
        if values is not None and len(values) != count:
            raise ValueError(f"{array_name} length does not match boneNames length.")
    for child_index, parent_index in enumerate(parent_indices):
        if not isinstance(parent_index, int):
            raise ValueError(f"boneParentIndexes[{child_index}] is not an integer.")
        if parent_index == -1:
            continue
        if parent_index < 0 or parent_index >= count:
            raise ValueError(
                f"boneParentIndexes[{child_index}]={parent_index} is outside the boneNames array."
            )
        if parent_index >= child_index:
            raise ValueError(
                f"boneParentIndexes[{child_index}]={parent_index} does not precede its child."
            )


def _remap_bone_references(
    root: dict, source_names, export_names, source_indices, lod_ranks
) -> None:
    """Point the index-based bone references at the exported bone order"""
    export_index_by_source = {
        source_index: export_index
        for export_index, source_index in enumerate(source_indices)
        if source_index is not None
    }

    def exported_index(source_index: int, user: str) -> int:
        export_index = export_index_by_source.get(source_index)
        if export_index is None:
            name = (
                source_names[source_index]
                if 0 <= source_index < len(source_names)
                else source_index
            )
            raise ValueError(
                f"Bone '{name}' was deleted but {user} still uses it; restore the bone before exporting."
            )
        return export_index

    for setup in root.get("ikSetups") or ():
        data = setup.get("Data") if isinstance(setup, dict) else None
        if not isinstance(data, dict):
            continue
        user = f"IK setup '{(data.get('name') or {}).get('$value', '')}'"
        for key in ("firstBone", "secondBone", "endBone"):
            if isinstance(data.get(key + "Idx"), int):
                index = exported_index(data[key + "Idx"], user)
                data[key + "Idx"] = index
                if isinstance(data.get(key), dict):
                    data[key]["$value"] = export_names[index]

    ragdoll_names = root.get("ragdollNames") or []
    for body, description in enumerate(root.get("ragdollDesc") or ()):
        for side in ("Parent", "Child"):
            source_index = description.get(f"{side}AnimIndex")
            if not isinstance(source_index, int) or source_index < 0:
                continue
            index = exported_index(source_index, f"ragdoll body {body}")
            description[f"{side}AnimIndex"] = index
            names = ragdoll_names[body] if body < len(ragdoll_names) else None
            if isinstance(names, dict) and isinstance(
                names.get(f"{side}AnimName"), dict
            ):
                names[f"{side}AnimName"]["$value"] = export_names[index]

    # Each LOD evaluates the first N bones: it keeps the source bones it had and gains the new bones ranked inside it.
    counts = root.get("levelOfDetailStartIndices")
    if isinstance(counts, list) and counts:
        root["levelOfDetailStartIndices"] = [
            sum(1 for rank in lod_ranks if rank is not None and rank < int(count))
            for count in counts
        ]


def _transform_scale(transform: Any) -> Vector:
    if not isinstance(transform, dict):
        return Vector((1.0, 1.0, 1.0))
    scale = transform.get("Scale", {})
    return Vector(
        (
            float(scale.get("X", 1.0)),
            float(scale.get("Y", 1.0)),
            float(scale.get("Z", 1.0)),
        )
    )


def _quaternion_length_squared(quaternion: Quaternion) -> float:
    return sum(float(component) * float(component) for component in quaternion)


def _transform_quaternion(transform: Any) -> Quaternion | None:
    if not isinstance(transform, dict):
        return None
    rotation = transform.get("Rotation", {})
    try:
        quat = Quaternion(
            (
                float(rotation.get("r", 1.0)),
                float(rotation.get("i", 0.0)),
                float(rotation.get("j", 0.0)),
                float(rotation.get("k", 0.0)),
            )
        )
    except (TypeError, ValueError):
        return None
    if _quaternion_length_squared(quat) < 1e-12:
        return None
    quat.normalize()
    return quat


def _clean_export_float(value: float, eps: float = 1e-9) -> float:
    value = float(value)
    if abs(value) <= eps:
        return 0.0
    if abs(value - 1.0) <= eps:
        return 1.0
    if abs(value + 1.0) <= eps:
        return -1.0
    return value


def _matrix_to_qs_transform(
    matrix: Matrix,
    reference_transform: Any = None,
    scale_override: Vector | None = None,
    translation_w: float = 1.0,
) -> dict:
    translation, rotation, matrix_scale = matrix.decompose()
    if _quaternion_length_squared(rotation) < 1e-12:
        rotation = Quaternion((1.0, 0.0, 0.0, 0.0))
    else:
        rotation.normalize()

    reference_rotation = _transform_quaternion(reference_transform)
    if reference_rotation is not None and rotation.dot(reference_rotation) < 0.0:
        rotation.negate()

    scale = scale_override if scale_override is not None else matrix_scale
    result = (
        copy.deepcopy(reference_transform)
        if isinstance(reference_transform, dict)
        else {}
    )
    result.setdefault("$type", "QsTransform")

    rotation_value = result.get("Rotation")
    if not isinstance(rotation_value, dict):
        rotation_value = {}
        result["Rotation"] = rotation_value
    rotation_value.setdefault("$type", "Quaternion")
    rotation_value["i"] = _clean_export_float(rotation.x)
    rotation_value["j"] = _clean_export_float(rotation.y)
    rotation_value["k"] = _clean_export_float(rotation.z)
    rotation_value["r"] = _clean_export_float(rotation.w)

    translation_value = result.get("Translation")
    if not isinstance(translation_value, dict):
        translation_value = {}
        result["Translation"] = translation_value
    translation_value.setdefault("$type", "Vector4")
    translation_value.setdefault("W", float(translation_w))
    translation_value["X"] = _clean_export_float(translation.x)
    translation_value["Y"] = _clean_export_float(translation.y)
    translation_value["Z"] = _clean_export_float(translation.z)

    scale_value = result.get("Scale")
    if not isinstance(scale_value, dict):
        scale_value = {}
        result["Scale"] = scale_value
    scale_value.setdefault("$type", "Vector4")
    scale_value.setdefault("W", 1.0)
    scale_value["X"] = _clean_export_float(scale.x)
    scale_value["Y"] = _clean_export_float(scale.y)
    scale_value["Z"] = _clean_export_float(scale.z)
    return result


def _compose_qs_matrix(
    translation: Vector, rotation: Quaternion, scale: Vector
) -> Matrix:
    return Matrix(
        compose_matrix(
            tuple(translation),
            (rotation.x, rotation.y, rotation.z, rotation.w),
            tuple(scale),
        )
    )


def _qs_transform_to_matrix(transform: Any) -> Matrix:
    if not isinstance(transform, dict):
        return Matrix.Identity(4)
    translation_value = transform.get("Translation", {})
    translation = Vector(
        (
            float(translation_value.get("X", 0.0)),
            float(translation_value.get("Y", 0.0)),
            float(translation_value.get("Z", 0.0)),
        )
    )
    rotation = _transform_quaternion(transform) or Quaternion((1.0, 0.0, 0.0, 0.0))
    return _compose_qs_matrix(translation, rotation, _transform_scale(transform))


def _matrix_max_abs_difference(first: Matrix, second: Matrix) -> float:
    return max(
        abs(float(first[row][column]) - float(second[row][column]))
        for row in range(4)
        for column in range(4)
    )


def _source_pose_data(root: dict, local_array_name: str, model_array_name: str | None):
    names = _to_list_of_strings(root.get("boneNames", []))
    count = len(names)
    parents_raw = root.get("boneParentIndexes", [])
    parents = [
        int(parents_raw[index])
        if isinstance(parents_raw, list) and index < len(parents_raw)
        else -1
        for index in range(count)
    ]
    local_values = root.get(local_array_name, [])
    if not isinstance(local_values, list) or len(local_values) != count:
        local_values = []
    model_values = root.get(model_array_name, []) if model_array_name else []
    if not isinstance(model_values, list) or len(model_values) != count:
        model_values = []

    local_matrices = [None] * count
    accumulated_model_matrices = [None] * count
    if local_values:
        local_matrices = [_qs_transform_to_matrix(value) for value in local_values]

        def resolve_model(index: int):
            cached = accumulated_model_matrices[index]
            if cached is not None:
                return cached
            parent_index = parents[index]
            local_matrix = local_matrices[index]
            model_matrix = (
                resolve_model(parent_index) @ local_matrix
                if 0 <= parent_index < count
                else local_matrix
            )
            accumulated_model_matrices[index] = model_matrix
            return model_matrix

        for index in range(count):
            resolve_model(index)

    # The rig importer places bones from a complete model-space pose array directly. Prefer that
    # exact serialized array when present instead of re-accumulating local matrices;
    # this keeps export inverse to the actual import path.
    if model_values:
        model_matrices = [_qs_transform_to_matrix(value) for value in model_values]
    else:
        model_matrices = accumulated_model_matrices

    if not local_values and model_values:
        for index, model_matrix in enumerate(model_matrices):
            parent_index = parents[index]
            local_matrices[index] = (
                model_matrices[parent_index].inverted_safe() @ model_matrix
                if 0 <= parent_index < count
                else model_matrix.copy()
            )

    expected_blender_models = [
        Matrix(red_model_transform_to_current_bone(rigid_matrices(model_matrix)))
        if model_matrix is not None
        else None
        for model_matrix in model_matrices
    ]
    return {
        "names": names,
        "parents": parents,
        "local_values": local_values,
        "model_values": model_values,
        "local_matrices": local_matrices,
        "model_matrices": model_matrices,
        "expected_blender_models": expected_blender_models,
    }


def _is_identity_rigid_delta(matrix: Matrix, eps: float = RIGID_TOLERANCE) -> bool:
    return (
        _matrix_max_abs_difference(Matrix(rigid_matrices(matrix)), Matrix.Identity(4))
        <= eps
    )


def _build_topology_export_context(arm_obj, root: dict):
    arm_data = arm_obj.data
    bones, rank_by_name = _ordered_export_bones(
        arm_data, root.get("levelOfDetailStartIndices") or ()
    )
    parents = _parent_indices_for_ordered_bones(bones)
    source_names = _to_list_of_strings(root.get("boneNames", []))
    source_count = len(source_names)
    source_index_by_name = _source_name_index(source_names)

    current_blender_models = (
        [Matrix(matrix) for matrix in rest_model_matrices(bones)] if bones else []
    )

    imported_pose_name = _resolve_rig_export_pose_target(arm_data, "IMPORTED")
    imported_local_name = (
        "aPoseLS" if imported_pose_name == "A_POSE" else "boneTransforms"
    )
    imported_model_name = (
        "aPoseMS" if imported_pose_name == "A_POSE" else "referencePoseMS"
    )
    imported_source_pose = _source_pose_data(
        root, imported_local_name, imported_model_name
    )

    source_indices = []
    seen_source_indices = set()
    for bone in bones:
        source_index = _bone_source_index(
            bone, source_index_by_name=source_index_by_name
        )
        if (
            source_index is not None
            and 0 <= source_index < source_count
            and source_index not in seen_source_indices
        ):
            seen_source_indices.add(source_index)
            source_indices.append(source_index)
        else:
            source_indices.append(None)

    frame_deltas = [None] * len(bones)
    imported_desired_models = [None] * len(bones)
    new_local_matrices = [None] * len(bones)
    unchanged = [False] * len(bones)
    visiting = set()

    def resolve_imported(index: int):
        cached = imported_desired_models[index]
        if cached is not None:
            return cached
        if index in visiting:
            raise ValueError(
                f"Cycle detected in armature hierarchy at bone '{bones[index].name}'."
            )
        visiting.add(index)
        bone = bones[index]
        parent_index = parents[index]
        parent_model = resolve_imported(parent_index) if parent_index >= 0 else None
        source_index = source_indices[index]
        current_blender = current_blender_models[index]

        if source_index is not None:
            imported_blender = _imported_bone_matrix(bone)
            source_model = _imported_source_model_matrix(bone)
            if source_model is None and source_index < len(
                imported_source_pose["model_matrices"]
            ):
                source_model = imported_source_pose["model_matrices"][source_index]
            expected_blender = (
                imported_source_pose["expected_blender_models"][source_index]
                if source_index < len(imported_source_pose["expected_blender_models"])
                else None
            )
            if imported_blender is None:
                if (
                    expected_blender is None
                    or _matrix_max_abs_difference(current_blender, expected_blender)
                    > RIGID_TOLERANCE
                ):
                    raise ValueError(
                        f"Bone '{bone.name}' has no stored import rotation baseline and no longer "
                        "matches the source rig. Re-import the rig before exporting edited rotations."
                    )
                imported_blender = expected_blender
            if source_model is None:
                raise ValueError(
                    f"Bone '{bone.name}' has no REDengine source model transform for the "
                    f"imported {imported_pose_name.replace('_', '-').lower()}."
                )
            imported_blender = Matrix(rigid_matrices(imported_blender))
            edit_delta = Matrix(
                rigid_matrices(current_blender @ imported_blender.inverted_safe())
            )
            unchanged[index] = _is_identity_rigid_delta(edit_delta)
            desired_model = edit_delta @ source_model
            # The same edit in the bone's own frame, which carries it to the rig's other pose.
            frame_deltas[index] = source_model.inverted_safe() @ desired_model
        else:
            # A new Blender bone is itself the authored game-space frame. The declared
            # basis converts its local axes while leaving model-space translation intact.
            desired_model = Matrix(current_bone_model_transform_to_red(current_blender))
            if parent_model is not None:
                new_local_matrices[index] = parent_model.inverted_safe() @ desired_model
            else:
                new_local_matrices[index] = desired_model.copy()

        imported_desired_models[index] = desired_model
        visiting.remove(index)
        return desired_model

    for index in range(len(bones)):
        resolve_imported(index)

    # A source bone keeps its source name unless it was renamed in Blender, which shortens names over 63 bytes.
    export_names = [
        source_names[source_index]
        if source_index is not None
        and bone.name == blender_bone_name(source_names[source_index])
        else str(bone.name)
        for bone, source_index in zip(bones, source_indices)
    ]
    return {
        "bones": bones,
        "bone_names": export_names,
        "parent_indices": parents,
        "source_names": source_names,
        "source_indices": source_indices,
        "lod_ranks": [rank_by_name[str(bone.name)] for bone in bones],
        "frame_deltas": frame_deltas,
        "unchanged": unchanged,
        "imported_pose_name": imported_pose_name,
        "imported_desired_models": imported_desired_models,
        "new_local_matrices": new_local_matrices,
    }


def _export_pose_from_context(
    context: dict,
    root: dict,
    local_array_name: str,
    model_array_name: str | None,
):
    bones = context["bones"]
    parents = context["parent_indices"]
    source_indices = context["source_indices"]
    source_pose = _source_pose_data(root, local_array_name, model_array_name)

    local_matrices = [None] * len(bones)
    model_matrices = [None] * len(bones)
    local_transforms = [None] * len(bones)
    model_transforms = [None] * len(bones)
    preserved_count = 0
    reconstructed_count = 0
    nonuniform_scaled_edit_count = 0
    visiting = set()

    def has_nonuniform_scaled_ancestry(index: int) -> bool:
        current = index
        while current >= 0:
            source_index = source_indices[current]
            if source_index is not None and source_pose["local_values"]:
                scale = _transform_scale(source_pose["local_values"][source_index])
                if max(scale) - min(scale) > 1e-6:
                    return True
            current = parents[current]
        return False

    def resolve(index: int):
        nonlocal preserved_count, reconstructed_count, nonuniform_scaled_edit_count
        cached = model_matrices[index]
        if cached is not None:
            return cached
        if index in visiting:
            raise ValueError(
                f"Cycle detected in armature hierarchy at bone '{bones[index].name}'."
            )
        visiting.add(index)
        parent_index = parents[index]
        parent_model = resolve(parent_index) if parent_index >= 0 else None
        source_index = source_indices[index]

        source_local = None
        source_model = None
        source_parent = None
        model_reference = None
        if source_index is not None:
            if source_pose["local_values"] and source_index < len(
                source_pose["local_values"]
            ):
                source_local = source_pose["local_values"][source_index]
            if source_index < len(source_pose["model_matrices"]):
                source_model = source_pose["model_matrices"][source_index]
            if source_index < len(source_pose["parents"]):
                source_parent = source_pose["parents"][source_index]
            if source_pose["model_values"] and source_index < len(
                source_pose["model_values"]
            ):
                model_reference = source_pose["model_values"][source_index]

        current_parent_source = (
            source_indices[parent_index] if parent_index >= 0 else -1
        )
        # Edits are model-space, so a bone the user left alone keeps its model transform; its local transform
        # survives only while its parent's model transform does too.
        own_unchanged = context["unchanged"][index]
        can_preserve = (
            source_local is not None
            and source_model is not None
            and own_unchanged
            and (parent_index < 0 or context["unchanged"][parent_index])
            and source_parent == current_parent_source
        )

        if source_model is not None:
            desired_model = (
                source_model.copy()
                if own_unchanged
                else source_model @ context["frame_deltas"][index]
            )
        elif source_index is not None:
            # This pose is absent for the source bone. Reuse the imported edited model
            # rather than inventing another orientation.
            desired_model = context["imported_desired_models"][index].copy()
        else:
            new_local = context["new_local_matrices"][index]
            desired_model = (
                parent_model @ new_local
                if parent_model is not None
                else new_local.copy()
            )

        if can_preserve:
            local_matrix = source_pose["local_matrices"][source_index].copy()
            local_transform = copy.deepcopy(source_local)
            preserved_count += 1
        else:
            local_matrix = (
                parent_model.inverted_safe() @ desired_model
                if parent_model is not None
                else desired_model.copy()
            )
            reference = source_local
            local_transform = _matrix_to_qs_transform(
                local_matrix,
                reference,
                scale_override=None,
                translation_w=1.0 if parent_index < 0 else 0.0,
            )
            reconstructed_count += 1
            if has_nonuniform_scaled_ancestry(index):
                nonuniform_scaled_edit_count += 1

        if own_unchanged and source_model is not None and model_reference is not None:
            model_transform = copy.deepcopy(model_reference)
        else:
            model_transform = _matrix_to_qs_transform(
                desired_model,
                model_reference,
                scale_override=None,
                translation_w=1.0,
            )

        local_matrices[index] = local_matrix
        model_matrices[index] = desired_model
        local_transforms[index] = local_transform
        model_transforms[index] = model_transform
        visiting.remove(index)
        return desired_model

    for index in range(len(bones)):
        resolve(index)

    return {
        "local_transforms": local_transforms,
        "model_transforms": model_transforms,
        "preserved_transform_count": preserved_count,
        "reconstructed_transform_count": reconstructed_count,
        "nonuniform_scaled_edit_count": nonuniform_scaled_edit_count,
    }


def _resolve_rig_export_pose_target(arm_data, pose_target: str) -> str:
    normalized = str(pose_target or "IMPORTED").upper()
    if normalized == "IMPORTED":
        fallback = "T_POSE" if bool(arm_data.get("cp77_t_pose", True)) else "A_POSE"
        return str(arm_data.get("cp77_rig_imported_pose", fallback)).upper()
    if normalized in {"T_POSE", "A_POSE", "ALL"}:
        return normalized
    raise ValueError(f"Unsupported rig export pose target: {pose_target}")


def build_rig_json_from_armature(
    arm_obj, pose_target: str = "IMPORTED"
) -> tuple[dict, dict]:
    if arm_obj is None or getattr(arm_obj, "type", None) != "ARMATURE":
        raise TypeError("Rig export requires an armature object.")
    arm_data = arm_obj.data
    contract = str(arm_data.get("cp77_rig_space_contract", ""))
    if contract and contract != RIG_SPACE_CONTRACT_CURRENT:
        raise ValueError(f"Unsupported rig coordinate contract: {contract}")

    document = _rig_export_template_from_armature(arm_obj)
    root = document.setdefault("Data", {}).setdefault("RootChunk", {})
    root["$type"] = "animRig"
    source_root = copy.deepcopy(root)
    target = _resolve_rig_export_pose_target(arm_data, pose_target)
    topology = _build_topology_export_context(arm_obj, source_root)

    original_names = _to_list_of_strings(source_root.get("boneNames", []))
    original_parents = (
        list(source_root.get("boneParentIndexes", []))
        if isinstance(source_root.get("boneParentIndexes"), list)
        else []
    )
    topology_changed = (
        topology["bone_names"] != original_names
        or topology["parent_indices"] != original_parents
    )

    original_name_entries = (
        source_root.get("boneNames", [])
        if isinstance(source_root.get("boneNames"), list)
        else []
    )
    exported_name_entries = []
    for name, bone, source_index in zip(
        topology["bone_names"], topology["bones"], topology["source_indices"]
    ):
        template = (
            original_name_entries[source_index]
            if source_index is not None
            and 0 <= source_index < len(original_name_entries)
            else None
        )
        exported_name_entries.append(cname_entry(name, template))
    root["boneNames"] = exported_name_entries
    root["boneParentIndexes"] = list(topology["parent_indices"])
    if topology_changed:
        _remap_bone_references(
            root,
            original_names,
            topology["bone_names"],
            topology["source_indices"],
            topology["lod_ranks"],
        )

    t_pose = _export_pose_from_context(
        topology, source_root, "boneTransforms", "referencePoseMS"
    )
    has_a_pose = bool(source_root.get("aPoseLS")) or bool(source_root.get("aPoseMS"))
    a_pose = (
        _export_pose_from_context(topology, source_root, "aPoseLS", "aPoseMS")
        if has_a_pose or target in {"A_POSE", "ALL"}
        else None
    )

    # A rest edit reaches both poses; an untouched rig keeps its arrays as they were.
    rest_edited = topology_changed or not all(topology["unchanged"])
    if rest_edited or target in {"T_POSE", "ALL"}:
        root["boneTransforms"] = copy.deepcopy(t_pose["local_transforms"])
        if isinstance(root.get("referencePoseMS"), list) and root["referencePoseMS"]:
            root["referencePoseMS"] = copy.deepcopy(t_pose["model_transforms"])
    elif not isinstance(root.get("boneTransforms"), list) or len(
        root["boneTransforms"]
    ) != len(topology["bones"]):
        root["boneTransforms"] = copy.deepcopy(t_pose["local_transforms"])

    if a_pose is not None and (rest_edited or target in {"A_POSE", "ALL"}):
        root["aPoseLS"] = copy.deepcopy(a_pose["local_transforms"])
        root["aPoseMS"] = copy.deepcopy(a_pose["model_transforms"])

    populated_parallel_arrays = [("boneTransforms", root.get("boneTransforms"))]
    for array_name in ("referencePoseMS", "aPoseLS", "aPoseMS"):
        values = root.get(array_name)
        if isinstance(values, list) and values:
            populated_parallel_arrays.append((array_name, values))
    _validate_export_topology(
        topology["bone_names"],
        root["boneParentIndexes"],
        *populated_parallel_arrays,
    )

    track_names = _to_list_of_strings(root.get("trackNames", []))
    if not track_names:
        track_names = [str(value) for value in arm_data.get("trackNames", [])]
        root["trackNames"] = [cname_entry(name) for name in track_names]
    if track_names:
        existing_reference_tracks = root.get("referenceTracks", [])
        root["referenceTracks"] = [
            float(
                arm_obj.get(
                    name,
                    existing_reference_tracks[index]
                    if index < len(existing_reference_tracks)
                    else 0.0,
                )
            )
            for index, name in enumerate(track_names)
        ]

    header = document.setdefault("Header", {})
    header["ExportedDateTime"] = (
        datetime.now(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
    source = str(arm_data.get("cp77_source_rig_file", ""))
    if source and ";" not in source:
        header.setdefault("ArchiveFileName", strip_json_suffix(source))

    pose_summaries = [t_pose] + ([a_pose] if a_pose is not None else [])
    primary_pose = a_pose if target == "A_POSE" and a_pose is not None else t_pose
    summary = {
        "bone_count": len(topology["bones"]),
        "pose_target": target,
        "topology_changed": topology_changed,
        "source_template": bool(arm_data.get(RIG_EXPORT_TEMPLATE_KEY)),
        "preserved_transform_count": primary_pose["preserved_transform_count"],
        "reconstructed_transform_count": primary_pose["reconstructed_transform_count"],
        "nonuniform_scaled_edit_count": primary_pose["nonuniform_scaled_edit_count"],
        "total_preserved_transform_count": sum(
            p["preserved_transform_count"] for p in pose_summaries
        ),
        "total_reconstructed_transform_count": sum(
            p["reconstructed_transform_count"] for p in pose_summaries
        ),
        "new_bone_count": sum(index is None for index in topology["source_indices"]),
        "deleted_bone_count": max(
            0,
            len(original_names)
            - sum(index is not None for index in topology["source_indices"]),
        ),
    }
    return document, summary


def export_armature_to_rig_json(
    arm_obj, filepath: str, pose_target: str = "IMPORTED"
) -> dict:
    previous_mode = getattr(arm_obj, "mode", "OBJECT")
    mode_changed = False
    if arm_obj is getattr(bpy.context, "object", None) and previous_mode != "OBJECT":
        safe_mode_switch("OBJECT")
        mode_changed = True
    try:
        document, summary = build_rig_json_from_armature(arm_obj, pose_target)
    finally:
        if mode_changed and previous_mode in {"EDIT", "POSE"}:
            safe_mode_switch(previous_mode)
    filepath = os.path.abspath(filepath)
    if not filepath.lower().endswith(".rig.json"):
        filepath += ".rig.json"
    directory = os.path.dirname(filepath)
    if directory:
        os.makedirs(directory, exist_ok=True)
    atomic_write_text(
        filepath,
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
    )
    summary["filepath"] = filepath
    return summary


def export_active_rig(context, filepath: str) -> OperationResult:
    """Write the active armature's edits back to its .rig.json"""
    armature_object = context.view_layer.objects.active
    if armature_object is None or armature_object.type != "ARMATURE":
        return OperationResult.cancelled(
            "Select the armature to export as the active object."
        )
    summary = export_armature_to_rig_json(
        armature_object, filepath, pose_target="IMPORTED"
    )
    message = f"Exported {summary['bone_count']} bones to {os.path.basename(summary['filepath'])}."
    warnings = []
    if summary.get("topology_changed"):
        warnings.append(
            "The bone topology changed; retained non-pose metadata may need review."
        )
    if summary.get("nonuniform_scaled_edit_count"):
        warnings.append(
            "Edited bones under a nonuniform source scale were reconstructed approximately."
        )
    return OperationResult.finished(message, warnings=warnings)
