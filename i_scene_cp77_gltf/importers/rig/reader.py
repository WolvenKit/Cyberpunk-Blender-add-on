from __future__ import annotations

import copy
import hashlib
import json
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

from ...animation.domain.rig.assembly import merge_rig_datas, plan_bones
from ...animation.domain.rig.masks import (
    rig_part_masks_by_bone_name,
    rig_part_rotation_ms_by_name,
)
from ...animation.domain.rig.metadata import (
    RIG_EXPORT_TEMPLATE_KEY,
    RIG_IMPORT_MATRIX_KEY,
    RIG_IMPORT_SOURCE_MODEL_KEY,
    encode_json_document,
)
from ...animation.domain.rig.naming import blender_bone_name, merged_bone_name
from ...animation.model.clip.bones import ANIMATION_BONE_SET
from ...animation.services.rig.repository import RigRepository, rig_source_document
from ...assetio.documents import DocumentSession
from ...assetio.paths import strip_json_suffix
from ...assetio.rig_documents import minimal_rig_document
from ...assetio.values import cname_entry
from ...bartmoss.matrix import flatten_matrix, transfer_matrix_delta
from ...blender.armature import (
    apply_bind_matrices,
    build_apose_matrices,
    model_space_matrices_cached,
    precision_safe_bone_length,
    set_edit_bone_model_matrices,
)
from ...blender.armature_edit import ArmatureEditSession, atomic_armature_update
from ...blender.context import safe_mode_switch
from ...blender.rig_metadata import (
    imported_bone_names,
    store_rig_part_masks,
    store_rig_part_rotation_ms,
)
from ...blender.tracks import ensure_track_property
from ...blender.transactions import track_created_datablock
from ...core.log import get_logger, operation
from ...core.notifications import import_message
from ...redSpace.contracts import RIG_SPACE_CONTRACT_CURRENT
from ...redSpace.transforms import red_model_transform_to_current_bone

_LOG = get_logger(__name__)

_SHAPE_SCALE_ROOT = (0.075, 0.075, 0.075)
_SHAPE_SCALE_WEAPON = (0.0125, 0.0125, 0.0125)
_SHAPE_SCALE_SMALL = (0.05, 0.05, 0.05)
_SHAPE_SCALE_LARGE = (0.1, 0.1, 0.1)
_ROOT_SHAPE_BONES = frozenset(("Root", "Hips", "Trajectory"))
_WEAPON_SHAPE_BONES = frozenset(("WeaponLeft", "WeaponRight"))
_SHAPE_BONE_SUFFIXES = ("JNT", "GRP", "IK")


def load_rig_data(filepath, repository=None):
    if repository is not None:
        return repository.load(filepath, required=True)
    with DocumentSession() as documents:
        return RigRepository(documents).load(filepath, required=True)


def merged_rig_document(
    filepaths, merged_rig_data, source_label: str = "", rig_datas=None
) -> dict:
    base_document = (
        copy.deepcopy(rig_datas[0].source_document)
        if rig_datas and rig_datas[0].source_document
        else None
    )
    if base_document is None and filepaths:
        base_document = rig_source_document(filepaths[0])
    document = base_document or minimal_rig_document(source_label)
    root = document.setdefault("Data", {}).setdefault("RootChunk", {})
    root.update(rig_data_to_root_chunk(merged_rig_data))
    root["$type"] = "animRig"
    root["boneNames"] = [cname_entry(str(name)) for name in merged_rig_data.bone_names]
    root["trackNames"] = [
        cname_entry(str(name)) for name in merged_rig_data.track_names
    ]
    root.setdefault("aPoseMS", [])
    root.setdefault("referencePoseMS", [])
    if source_label:
        document.setdefault("Header", {})["ArchiveFileName"] = strip_json_suffix(
            source_label
        )
    return document


def _attach_rig_export_metadata(arm_obj, source_document: dict | None) -> None:
    arm_data = arm_obj.data
    source_path = str(arm_data.get("cp77_source_rig_file", ""))
    if (
        source_document is None
        and source_path
        and ";" not in source_path
        and os.path.isfile(source_path)
    ):
        source_document = rig_source_document(source_path)
    document = source_document if source_document else minimal_rig_document(source_path)
    try:
        arm_data[RIG_EXPORT_TEMPLATE_KEY] = encode_json_document(document)
    except (TypeError, ValueError, OverflowError):
        # The source path remains available as a fallback if Blender rejects a large ID string.
        if RIG_EXPORT_TEMPLATE_KEY in arm_data:
            del arm_data[RIG_EXPORT_TEMPLATE_KEY]
    arm_data["cp77_rig_imported_pose"] = (
        "T_POSE" if bool(arm_data.get("cp77_t_pose", True)) else "A_POSE"
    )


def _attach_imported_bone_matrices(arm_obj, source_model_matrices) -> None:
    arm_data = arm_obj.data
    bones = arm_data.bones
    matrix_count = len(source_model_matrices)
    for source_index, source_name in enumerate(arm_data.get("boneNames", [])):
        bone = bones.get(blender_bone_name(str(source_name)))
        if bone is None:
            continue
        bone[RIG_IMPORT_MATRIX_KEY] = flatten_matrix(bone.matrix_local).tolist()
        if source_index < matrix_count:
            source_matrix = source_model_matrices[source_index]
            if source_matrix is not None:
                bone[RIG_IMPORT_SOURCE_MODEL_KEY] = flatten_matrix(
                    source_matrix
                ).tolist()
                continue
        if RIG_IMPORT_SOURCE_MODEL_KEY in bone:
            del bone[RIG_IMPORT_SOURCE_MODEL_KEY]


def create_armature_from_data(
    filepath: str,
    bind_pose: str,
    assign_shapes: bool = True,
    rig_repository=None,
):
    rig_data = load_rig_data(filepath, rig_repository)
    if not rig_data:
        import_message(
            f"Failed to load rig data from {filepath}", severity="ERROR", logger=_LOG
        )
        return None
    return create_armature_from_rig_data(
        rig_data,
        bind_pose,
        source_rig_file=filepath,
        source_document=copy.deepcopy(rig_data.source_document),
        assign_shapes=assign_shapes,
    )


def create_armature_from_rig_files(
    filepaths,
    merged_name: str = "",
    source_label: str = "",
    assign_shapes: bool = True,
    rig_repository=None,
):
    """Build one JSON-derived armature by merging each later rig into the first"""
    rig_datas = []
    for filepath in filepaths:
        rig_data = load_rig_data(filepath, rig_repository)
        if rig_data:
            rig_datas.append(rig_data)
        else:
            import_message(
                f"Failed to load rig data from {filepath}",
                severity="ERROR",
                logger=_LOG,
            )
    if not rig_datas:
        return None
    # A single rig uses the same remapping, pose fallback, parent, and track rules.
    merged = merge_rig_datas(
        rig_datas, merged_name or rig_datas[0].rig_name + "_metarig"
    )
    merged_source = source_label or ";".join(filepaths)
    return create_armature_from_rig_data(
        merged,
        "A-Pose",
        source_rig_file=merged_source,
        source_document=merged_rig_document(filepaths, merged, source_label, rig_datas),
        assign_shapes=assign_shapes,
    )


def rig_data_to_root_chunk(rig_data) -> dict:
    """Represent a merged RigData as the RootChunk shape used by entity import"""
    if rig_data is None:
        return {}
    return {
        "boneNames": [{"$value": name} for name in rig_data.bone_names],
        "boneParentIndexes": rig_data.parent_indices.tolist(),
        "boneTransforms": list(rig_data.bone_transforms),
        "aPoseLS": list(rig_data.apose_ls),
        "aPoseMS": [],
        "trackNames": [{"$value": name} for name in rig_data.track_names],
        "referenceTracks": list(rig_data.reference_tracks),
        "levelOfDetailStartIndices": list(rig_data.level_of_detail_start_indices),
        "distanceCategoryToLodMap": list(rig_data.distance_category_to_lod_map),
        "tags": {
            "$type": "redTagList",
            "tags": [
                {"$type": "CName", "$storage": "string", "$value": tag}
                for tag in rig_data.tags
            ],
        },
    }


def rig_data_definition_hash(rig_data) -> str:
    """Return a stable digest for the rig topology, rest pose, and tracks"""
    payload = rig_data_to_root_chunk(rig_data)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _coerce_model_space_matrices(values, bone_count: int):
    if values is None:
        return None
    try:
        sequence = list(values)
    except TypeError as error:
        raise ValueError(
            "model_space_matrices must be an iterable of 4x4 matrices"
        ) from error
    if len(sequence) != bone_count:
        raise ValueError(
            f"model_space_matrices contains {len(sequence)} entries for {bone_count} bones"
        )
    matrices = []
    for index, value in enumerate(sequence):
        if isinstance(value, Matrix):
            matrix = value.copy()
        else:
            array = np.asarray(value, dtype=np.float64)
            if array.shape != (4, 4):
                raise ValueError(
                    f"model_space_matrices[{index}] has shape {array.shape}, expected (4, 4)"
                )
            matrix = Matrix(
                tuple(tuple(float(component) for component in row) for row in array)
            )
        matrices.append(matrix)
    return tuple(matrices)


_RIG_COLLECTION_KEY = "cp77_rig_collection"


def _collection_visible_in_view_layer(collection, view_layer) -> bool:
    stack = [view_layer.layer_collection]
    while stack:
        layer = stack.pop()
        if layer.exclude:
            continue
        if layer.collection is collection:
            return True
        stack.extend(layer.children)
    return False


def rig_collection_for(rig_name: str):
    """Return a rig collection that is reachable from the active view layer"""
    context = bpy.context
    existing = bpy.data.collections.get(rig_name)
    if (
        existing is not None
        and existing.get(_RIG_COLLECTION_KEY)
        and _collection_visible_in_view_layer(existing, context.view_layer)
    ):
        return existing
    collection = track_created_datablock(
        "collections", bpy.data.collections.new(rig_name)
    )
    collection[_RIG_COLLECTION_KEY] = True
    context.scene.collection.children.link(collection)
    return collection


def _activate_armature_in_current_view_layer(arm_obj) -> None:
    context = bpy.context
    for selected in tuple(context.selected_objects):
        try:
            selected.select_set(False)
        except (ReferenceError, RuntimeError):
            pass
    arm_obj.hide_viewport = False
    arm_obj.hide_select = False
    if context.view_layer.objects.get(arm_obj.name) is not arm_obj:
        return
    try:
        arm_obj.hide_set(False)
    except RuntimeError:
        pass
    arm_obj.select_set(True)
    context.view_layer.objects.active = arm_obj


def set_armature_model_space_matrices(
    arm_obj,
    bone_names,
    model_space_matrices,
):
    """Apply authoritative armature-space rest matrices in an isolated edit scene"""
    if arm_obj is None or getattr(arm_obj, "type", None) != "ARMATURE":
        raise ValueError(
            "set_armature_model_space_matrices requires an armature object"
        )
    names = tuple(str(name) for name in bone_names)
    matrices = _coerce_model_space_matrices(model_space_matrices, len(names))
    original_lengths = {
        bone.name: max(float(bone.length), 1.0e-5) for bone in arm_obj.data.bones
    }

    with ArmatureEditSession(arm_obj) as timings:
        edit_bones = arm_obj.data.edit_bones
        for name, matrix in zip(names, matrices):
            edit_bone = edit_bones.get(name)
            if edit_bone is None:
                raise ValueError(
                    f"Armature {arm_obj.name!r} is missing edit bone {name!r}"
                )
            edit_bone.matrix = matrix
            edit_bone.length = precision_safe_bone_length(
                matrix.translation, original_lengths.get(name, 0.01)
            )

    _attach_imported_bone_matrices(arm_obj, matrices)
    return timings


def _blender_rest_matrix(red_model: Matrix) -> Matrix:
    """The edit-bone matrix for a REDengine model-space rest transform"""
    translation, rotation, _scale = red_model.decompose()
    rigid = Matrix.Translation(translation) @ rotation.normalized().to_matrix().to_4x4()
    return Matrix(red_model_transform_to_current_bone(rigid).tolist())


@atomic_armature_update
def reconcile_armature_from_rig_data(
    arm_obj,
    rig_data,
    *,
    source_rig_file: str = "",
    source_document: dict | None = None,
    assign_shapes: bool = False,
):
    """Reconcile an existing armature object to an ordered merged-rig definition"""
    if arm_obj is None or getattr(arm_obj, "type", None) != "ARMATURE":
        raise ValueError("reconcile_armature_from_rig_data requires an armature object")
    if rig_data is None:
        raise ValueError("rig_data is required")

    names = tuple(str(name) for name in rig_data.bone_names)
    parent_indices = tuple(int(value) for value in rig_data.parent_indices)
    if len(names) != len(parent_indices):
        raise ValueError("Merged rig bone names and parent indices differ in length")

    matrices = build_apose_matrices(
        rig_data.apose_ms,
        rig_data.apose_ls,
        rig_data.bone_names,
        rig_data.parent_indices,
    )
    if matrices is None:
        matrices = model_space_matrices_cached(
            rig_data.bone_transforms,
            rig_data.parent_indices,
        )
    if matrices is None or any(not isinstance(matrix, Matrix) for matrix in matrices):
        raise ValueError("Rig source does not provide a complete rest pose")
    matrices = tuple(matrix.copy() for matrix in matrices)
    if any(
        not np.isfinite(np.asarray(matrix)).all() or abs(matrix.determinant()) < 1e-12
        for matrix in matrices
    ):
        raise ValueError("Rig rest matrices must be finite and invertible")
    if len(matrices) != len(names):
        raise ValueError("Merged rig rest pose does not match its bone count")
    # The rest pose is REDengine model space; edit bones take Blender bone axes, as a freshly built rig has them.
    blender_matrices = tuple(_blender_rest_matrix(matrix) for matrix in matrices)

    arm_data = arm_obj.data
    plan = plan_bones(
        names, parent_indices, arm_data.bones.keys(), imported_bone_names(arm_obj)
    )
    old_names = tuple(str(name) for name in arm_data.get("boneNames", ()))
    old_parents = tuple(arm_data.get("boneParentIndexes", ()))
    old_parent_names = {
        name: old_names[int(parent)] if 0 <= int(parent) < len(old_names) else ""
        for name, parent in zip(old_names, old_parents)
    }
    rest_updates = {}
    for index, name in enumerate(names):
        bone = arm_data.bones.get(name)
        if bone is None:
            continue
        previous = bone.get(RIG_IMPORT_SOURCE_MODEL_KEY)
        baseline = bone.get(RIG_IMPORT_MATRIX_KEY)
        if previous is None or baseline is None:
            continue
        previous = np.asarray(previous, dtype=np.float64).reshape(4, 4)
        baseline = np.asarray(baseline, dtype=np.float64).reshape(4, 4)
        if not np.array_equal(previous, np.asarray(matrices[index])):
            # Carry the user's model-space edit (current against the import baseline) onto the new rest.
            current = transfer_matrix_delta(
                bone.matrix_local, baseline, blender_matrices[index]
            )
            imported = np.asarray(blender_matrices[index])
            if not np.isfinite(current).all() or not np.isfinite(imported).all():
                raise ValueError(f"Invalid rest metadata on bone {name!r}")
            rest_updates[name] = (Matrix(current.tolist()), imported)
    with ArmatureEditSession(arm_obj):
        edit_bones = arm_data.edit_bones
        # Preserve authored children, including their model-space rest transforms.
        for bone in tuple(edit_bones):
            if (
                bone.name not in plan.removed
                and bone.parent
                and bone.parent.name in plan.removed
            ):
                parent = bone.parent
                while parent and parent.name in plan.removed:
                    parent = parent.parent
                matrix = bone.matrix.copy()
                bone.use_connect = False
                bone.parent = parent
                bone.matrix = matrix
        for name in plan.removed:
            edit_bones.remove(edit_bones[name])
        for index in plan.order:
            name = names[index]
            parent_index = parent_indices[index]
            parent_name = names[parent_index] if parent_index >= 0 else ""
            parent = edit_bones.get(parent_name)
            bone = edit_bones.get(name)
            if name in plan.added:
                bone = edit_bones.new(name)
                bone.head = Vector((0.0, 0.0, 0.0))
                bone.tail = Vector((0.0, 0.05, 0.0))
                bone.parent = parent
                matrix = blender_matrices[index].copy()
                if parent is not None:
                    matrix = (
                        parent.matrix
                        @ blender_matrices[parent_index].inverted()
                        @ matrix
                    )
                bone.matrix = matrix
                bone.length = precision_safe_bone_length(matrix.translation, 0.05)
            elif old_parent_names.get(name, parent_name) != parent_name:
                current_parent = bone.parent.name if bone.parent else ""
                if current_parent == old_parent_names.get(name) or current_parent == "":
                    matrix = bone.matrix.copy()
                    bone.use_connect = False
                    bone.parent = parent
                    bone.matrix = matrix
            if name in rest_updates:
                bone.matrix = rest_updates[name][0]
        # Existing pose channels and authored rest deltas survive replacements.

    arm_data["cp77_source_rig_file"] = source_rig_file
    arm_data["cp77_rig_space_contract"] = RIG_SPACE_CONTRACT_CURRENT
    arm_data["boneNames"] = list(names)
    arm_data["boneParentIndexes"] = list(parent_indices)
    arm_data["trackNames"] = list(rig_data.track_names)
    arm_data["referenceTracks"] = list(rig_data.reference_tracks)
    arm_data["cp77_rig_tags"] = list(getattr(rig_data, "tags", ()) or ())

    for source_index, source_name in enumerate(names):
        bone = arm_data.bones.get(source_name)
        if bone is None:
            continue
        bone["cp77_rig_index"] = source_index
        bone["cp77_rig_source_name"] = source_name

    if rig_data.parts:
        assign_part_groups(arm_obj, rig_data.parts)
    else:
        store_rig_part_masks(arm_obj, {})
    if assign_shapes:
        assign_bone_shapes(arm_obj, rig_data.disable_connect)
    assign_reference_tracks(arm_obj, rig_data.track_names, rig_data.reference_tracks)
    _attach_rig_export_metadata(arm_obj, source_document)
    for index, name in enumerate(names):
        bone = arm_data.bones.get(name)
        if bone is None:
            raise ValueError(
                f"Blender could not retain the requested bone name {name!r}"
            )
        if name in rest_updates:
            bone[RIG_IMPORT_MATRIX_KEY] = flatten_matrix(rest_updates[name][1]).tolist()
            bone[RIG_IMPORT_SOURCE_MODEL_KEY] = flatten_matrix(matrices[index]).tolist()
        elif name in plan.added:
            bone[RIG_IMPORT_MATRIX_KEY] = flatten_matrix(bone.matrix_local).tolist()
            bone[RIG_IMPORT_SOURCE_MODEL_KEY] = flatten_matrix(matrices[index]).tolist()
    return arm_obj


def reconcile_armature_overlay_from_rig_data(
    arm_obj, base_rig_data, merged_rig_data, *, source_rig_file="", source_document=None
):
    """Appearance changes use the same source-owned delta as manual part edits"""
    reconcile_armature_from_rig_data(
        arm_obj,
        merged_rig_data,
        source_rig_file=source_rig_file,
        source_document=source_document,
        assign_shapes=False,
    )
    base_names = set(getattr(base_rig_data, "bone_names", ()))
    return tuple(name for name in merged_rig_data.bone_names if name not in base_names)


def create_armature_from_rig_data(
    rig_data,
    bind_pose: str,
    source_rig_file: str = "",
    source_document: dict | None = None,
    assign_shapes: bool = True,
    model_space_matrices=None,
    collection=None,
):
    rig_name = str(rig_data.rig_name)
    with operation(
        _LOG, f"rig import {rig_name}", source=source_rig_file, bind_pose=bind_pose
    ):
        safe_mode_switch("OBJECT")

        rig_col = collection if collection is not None else rig_collection_for(rig_name)

        arm_data = track_created_datablock(
            "armatures", bpy.data.armatures.new(f"{rig_name}_Data")
        )
        # Relationship lines join each bone head to its parent's head, the joint hierarchy the rig defines.
        arm_data.relation_line_position = "HEAD"
        arm_obj = track_created_datablock(
            "objects", bpy.data.objects.new(rig_name, arm_data)
        )
        rig_col.objects.link(arm_obj)

        parent_indices_list = rig_data.parent_indices.tolist()
        arm_data["cp77_source_rig_file"] = source_rig_file
        arm_data["cp77_rig_space_contract"] = RIG_SPACE_CONTRACT_CURRENT
        arm_data["boneNames"] = list(rig_data.bone_names)
        arm_data["boneParentIndexes"] = parent_indices_list
        arm_data["trackNames"] = list(rig_data.track_names)
        arm_data["referenceTracks"] = list(rig_data.reference_tracks)
        arm_data["cp77_rig_tags"] = list(getattr(rig_data, "tags", ()) or ())

        override_matrices = _coerce_model_space_matrices(
            model_space_matrices,
            len(rig_data.bone_names),
        )

        try:
            with ArmatureEditSession(arm_obj):
                edit_bones = arm_data.edit_bones
                bone_index_map: dict[int, bpy.types.EditBone] = {}
                for i, name in enumerate(rig_data.bone_names):
                    bone = edit_bones.new(name)
                    bone.head = Vector((0, 0, 0))
                    bone.tail = Vector((0, 0.05, 0))
                    bone_index_map[i] = bone
                for i, parent_idx in enumerate(parent_indices_list):
                    child_bone = bone_index_map[i]
                    if parent_idx != -1:
                        child_bone.parent = bone_index_map[parent_idx]

                mats = (
                    build_apose_matrices(
                        rig_data.apose_ms,
                        rig_data.apose_ls,
                        rig_data.bone_names,
                        rig_data.parent_indices,
                    )
                    if bind_pose == "A-Pose" and override_matrices is None
                    else None
                )
                if override_matrices is not None:
                    imported_model_matrices = override_matrices
                    set_edit_bone_model_matrices(
                        bone_index_map,
                        override_matrices,
                        rig_data.parent_indices,
                    )
                else:
                    global_transforms = model_space_matrices_cached(
                        rig_data.bone_transforms,
                        rig_data.parent_indices,
                    )
                    imported_model_matrices = (
                        mats if mats is not None else global_transforms
                    )
                    if mats is None:
                        apply_bind_matrices(
                            bone_index_map,
                            global_transforms[: len(rig_data.bone_names)],
                            rig_data.parent_indices,
                            skip_identity=True,
                        )

                arm_data["cp77_t_pose"] = True
                if bind_pose == "A-Pose" and override_matrices is None:
                    if mats is not None:
                        apply_bind_matrices(
                            bone_index_map, mats, rig_data.parent_indices
                        )
                        arm_data["cp77_t_pose"] = False
                    else:
                        _LOG.warning(
                            "A-Pose unavailable for %s; using T-Pose fallback from %s",
                            rig_name,
                            source_rig_file,
                        )

            if rig_data.parts:
                assign_part_groups(arm_obj, rig_data.parts)
        except Exception:
            if bpy.data.objects.get(arm_obj.name) is arm_obj:
                bpy.data.objects.remove(arm_obj, do_unlink=True)
            if (
                bpy.data.armatures.get(arm_data.name) is arm_data
                and arm_data.users == 0
            ):
                bpy.data.armatures.remove(arm_data)
            raise

        _activate_armature_in_current_view_layer(arm_obj)

        if assign_shapes:
            assign_bone_shapes(arm_obj, rig_data.disable_connect)

        assign_reference_tracks(
            arm_obj, rig_data.track_names, rig_data.reference_tracks
        )

        for source_index, source_name in enumerate(rig_data.bone_names):
            bone = arm_data.bones.get(blender_bone_name(source_name))
            if bone is not None:
                bone["cp77_rig_index"] = source_index
                bone["cp77_rig_source_name"] = source_name
        _attach_rig_export_metadata(arm_obj, source_document)
        _attach_imported_bone_matrices(arm_obj, imported_model_matrices)
    return arm_obj


def create_bone_shape():
    """Return the shared bone display shape"""
    shape = bpy.data.objects.get("BoneCustomShape")
    if shape is None:
        mesh = track_created_datablock("meshes", bpy.data.meshes.new("BoneCustomShape"))
        geometry = bmesh.new()
        try:
            bmesh.ops.create_icosphere(geometry, subdivisions=2, radius=1.0)
            geometry.to_mesh(mesh)
        finally:
            geometry.free()
        mesh.shade_smooth()
        shape = track_created_datablock(
            "objects",
            bpy.data.objects.new("BoneCustomShape", mesh),
        )
    shape.hide_viewport = True
    shape.hide_render = True
    return shape


def assign_bone_shapes(arm, disable_connect, shape=None):
    anim_bones = ANIMATION_BONE_SET
    if shape is None or not isinstance(shape, bpy.types.Object):
        shape = create_bone_shape()

    for pb in arm.pose.bones:
        name = pb.name

        if name in _ROOT_SHAPE_BONES:
            desired_shape = shape
            scale = _SHAPE_SCALE_ROOT
            bone_size = False
        elif name in _WEAPON_SHAPE_BONES:
            desired_shape = shape
            scale = _SHAPE_SCALE_WEAPON
            bone_size = False
        elif disable_connect:
            desired_shape = shape
            scale = _SHAPE_SCALE_SMALL
            bone_size = True
        elif name.endswith(_SHAPE_BONE_SUFFIXES):
            desired_shape = shape
            scale = _SHAPE_SCALE_LARGE if name not in anim_bones else _SHAPE_SCALE_SMALL
            bone_size = None
        else:
            desired_shape = None
            scale = None
            bone_size = None

        if pb.custom_shape != desired_shape:
            pb.custom_shape = desired_shape
        if desired_shape is not None:
            pb.custom_shape_scale_xyz = scale
            # The non-connected suffix path historically left bone-size sizing at its
            # default; None preserves that instead of forcing a value.
            if bone_size is not None:
                pb.use_custom_shape_bone_size = bone_size


def assign_part_groups(arm_obj, parts):
    if not parts or not isinstance(parts, list):
        return

    arm_data = arm_obj.data
    bones = arm_data.bones
    children_by_name = {}
    for bone in bones:
        if bone.parent:
            children_by_name.setdefault(bone.parent.name, []).append(bone.name)

    def collect_root_bones(tree):
        roots = []
        stack = [tree]
        while stack:
            current = stack.pop()
            if not isinstance(current, dict):
                continue
            root_entry = current.get("rootBone", {})
            root = root_entry.get("$value") if isinstance(root_entry, dict) else None
            if root:
                roots.append(root)
            subtrees = current.get("subtreesToChange", [])
            if subtrees:
                stack.extend(reversed(subtrees))
        return roots

    descendants_cache = {}

    def get_descendants(bone_name):
        cached = descendants_cache.get(bone_name)
        if cached is not None:
            return cached
        descendants = []
        stack = list(reversed(children_by_name.get(bone_name, ())))
        while stack:
            child_name = stack.pop()
            descendants.append(child_name)
            children = children_by_name.get(child_name)
            if children:
                stack.extend(reversed(children))
        descendants_cache[bone_name] = descendants
        return descendants

    pose_rotation_bones = []
    pose_rotation_seen = set()
    final_bones_with_rot_ms = []
    final_mask_rot_ms = []
    source_bone_names = tuple(str(name) for name in arm_data.get("boneNames", ()))
    source_parents = tuple(arm_data.get("boneParentIndexes", ()) or ())
    part_masks = rig_part_masks_by_bone_name(
        parts,
        source_bone_names,
        source_parents if len(source_parents) == len(source_bone_names) else None,
    )
    part_rotation_ms = rig_part_rotation_ms_by_name(parts, source_bone_names)
    has_part_metadata = False
    for part in parts:
        if not isinstance(part, dict):
            continue
        part_name = part.get("name", {}).get("$value")
        if not isinstance(part_name, str):
            continue

        collection = arm_data.collections.get(part_name) or arm_data.collections.new(
            name=part_name
        )
        for bone_entry in part.get("singleBones", []):
            bone_name = (
                bone_entry.get("$value") if isinstance(bone_entry, dict) else None
            )
            if isinstance(bone_name, str):
                bone = bones.get(bone_name) or bones.get(merged_bone_name(bone_name))
                if bone:
                    collection.assign(bone)

        for tree in part.get("treeBones", []):
            if not isinstance(tree, dict):
                continue
            for root_name in collect_root_bones(tree):
                if not isinstance(root_name, str):
                    continue
                resolved_root_name = (
                    root_name if bones.get(root_name) else merged_bone_name(root_name)
                )
                root_bone = bones.get(resolved_root_name)
                if root_bone:
                    collection.assign(root_bone)
                for child_name in get_descendants(resolved_root_name):
                    child_bone = bones.get(child_name)
                    if child_bone:
                        collection.assign(child_bone)

        bones_with_rot_ms = [
            entry.get("$value")
            for entry in part.get("bonesWithRotationInModelSpace", [])
            if isinstance(entry, dict) and "$value" in entry
        ]
        mask_rot_ms = part.get("maskRotMS", [])
        has_part_metadata = True
        for bone_name in bones_with_rot_ms:
            if bone_name not in final_bones_with_rot_ms:
                final_bones_with_rot_ms.append(bone_name)
        final_mask_rot_ms.extend(mask_rot_ms)
        for name in bones_with_rot_ms:
            if isinstance(name, str) and name not in pose_rotation_seen:
                pose_rotation_seen.add(name)
                pose_rotation_bones.append(name)

    if has_part_metadata:
        arm_obj["bonesWithRotationInModelSpace"] = final_bones_with_rot_ms
        arm_obj["maskRotMS"] = final_mask_rot_ms
        store_rig_part_masks(arm_obj, part_masks)
        store_rig_part_rotation_ms(arm_obj, part_rotation_ms)

    if pose_rotation_bones:
        pose_bones = arm_obj.pose.bones
        for bone_name in pose_rotation_bones:
            pose_bone = pose_bones.get(bone_name) or pose_bones.get(
                merged_bone_name(bone_name)
            )
            if pose_bone:
                pose_bone["maskRotMS"] = True


def assign_reference_tracks(arm_obj, track_names, reference_tracks):
    if not track_names:
        return
    reference_tracks = reference_tracks or ()
    names: list[str] = []
    for t in track_names:
        if isinstance(t, str):
            names.append(t)
        elif isinstance(t, dict) and "$value" in t:
            names.append(str(t["$value"]))
    for i, name in enumerate(names):
        default = float(reference_tracks[i]) if i < len(reference_tracks) else 0.0
        ensure_track_property(
            arm_obj,
            name,
            default,
            default=default,
            overwrite_ui=False,
        )
