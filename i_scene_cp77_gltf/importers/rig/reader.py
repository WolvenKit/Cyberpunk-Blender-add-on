from __future__ import annotations

from contextlib import contextmanager

import copy
import json
import os
import time
from typing import Any

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from ...assetio.documents import DocumentSession
from ...animation.rig import RigData, RigRepository
from ...animation.rig.metadata import (
    RIG_EXPORT_TEMPLATE_KEY,
    RIG_EXPORT_TEMPLATE_VERSION,
    RIG_IMPORT_MATRIX_KEY,
    RIG_IMPORT_MATRIX_VERSION,
    RIG_IMPORT_SOURCE_MODEL_KEY,
    encode_rig_export_template,
)
from ...animation.bones import ANIMATION_BONE_SET
from ...blender.context import get_safe_mode, safe_mode_switch
from ...blender.armature import (
    apply_bone_from_matrix,
    build_apose_matrices,
    children_by_parent,
    clear_parent_cache,
    model_space_matrices_cached,
)
from ...notifications import show_message
from ...animation.rig_binding import merged_bone_name
from ...animation.tracks import ensure_track_property
from ...redSpace.contracts import RIG_SPACE_CONTRACT_CURRENT
from ...redSpace.qs_transform import parse_wkit_trs
from ...blender.transactions import track_created_datablock

_MERGED_RIG_DATA_CACHE = {}
_SHAPE_SCALE_ROOT = (0.075, 0.075, 0.075)
_SHAPE_SCALE_WEAPON = (0.0125, 0.0125, 0.0125)
_SHAPE_SCALE_SMALL = (0.05, 0.05, 0.05)
_SHAPE_SCALE_LARGE = (0.1, 0.1, 0.1)
_ROOT_SHAPE_BONES = frozenset(("Root", "Hips", "Trajectory"))
_WEAPON_SHAPE_BONES = frozenset(("WeaponLeft", "WeaponRight"))
_SHAPE_BONE_SUFFIXES = ("JNT", "GRP", "IK")

_RIG_SPACE_CONTRACT = RIG_SPACE_CONTRACT_CURRENT
_RIG_BUILD_SERIAL = 0


def _emit_rig_build_phase(
        phase: str, seconds: float, rig_name: str = '', assign_shapes: bool = True,
        ):
    """No-op hook patched by the detachable entity importer audit."""
    return None


def _matrix_to_flat_list(matrix: Matrix) -> list[float]:
    return [component for row in matrix for component in row]


def _load_rig_data(filepath, repository=None):
    if repository is not None:
        return repository.load(filepath, required=True)
    with DocumentSession() as documents:
        return RigRepository(documents).load(filepath, required=True)


def _source_document_for_filepath(filepath):
    if not filepath or not str(filepath).casefold().endswith(".rig.json"):
        return None
    try:
        rig_data = _load_rig_data(filepath)
    except Exception:
        return None
    return copy.deepcopy(rig_data.source_document)


def _minimal_rig_document(source_rig_file: str = '') -> dict:
    archive_path = source_rig_file[:-5] if source_rig_file.lower().endswith('.json') else source_rig_file
    return {
        'Header': {
            'WKitJsonVersion': '0.0.9',
            'DataType': 'CR2W',
            'ArchiveFileName': archive_path,
            },
        'Data': {
            'RootChunk': {
                '$type': 'animRig',
                'aPoseLS': [],
                'aPoseMS': [],
                'boneNames': [],
                'boneParentIndexes': [],
                'boneTransforms': [],
                'referencePoseMS': [],
                'referenceTracks': [],
                'rigExtraTracks': [],
                'trackNames': [],
                }
            },
        }


def _cname_entry(name: str) -> dict:
    return {'$type': 'CName', '$storage': 'string', '$value': str(name)}


def merged_rig_document(filepaths, merged_rig_data, source_label: str = '', rig_datas=None) -> dict:
    base_document = copy.deepcopy(rig_datas[0].source_document) if rig_datas and rig_datas[0].source_document else None
    if base_document is None and filepaths:
        base_document = _source_document_for_filepath(filepaths[0])
    document = base_document or _minimal_rig_document(source_label)
    root = document.setdefault('Data', {}).setdefault('RootChunk', {})
    root.update(rig_data_to_root_chunk(merged_rig_data))
    root['$type'] = 'animRig'
    root['boneNames'] = [_cname_entry(name) for name in merged_rig_data.bone_names]
    root['trackNames'] = [_cname_entry(name) for name in merged_rig_data.track_names]
    root.setdefault('aPoseMS', [])
    root.setdefault('referencePoseMS', [])
    if source_label:
        archive_path = source_label[:-5] if source_label.lower().endswith('.json') else source_label
        document.setdefault('Header', {})['ArchiveFileName'] = archive_path
    return document


def _attach_rig_export_metadata(arm_obj, source_document: dict | None) -> None:
    arm_data = arm_obj.data
    source_path = str(arm_data.get('source_rig_file', ''))
    if source_document is None and source_path and ';' not in source_path and os.path.isfile(source_path):
        source_document = _source_document_for_filepath(source_path)
    document = source_document if source_document else _minimal_rig_document(source_path)
    try:
        arm_data[RIG_EXPORT_TEMPLATE_KEY] = encode_rig_export_template(document)
        arm_data['cp77_rig_export_template_version'] = RIG_EXPORT_TEMPLATE_VERSION
    except (TypeError, ValueError, OverflowError):
        if RIG_EXPORT_TEMPLATE_KEY in arm_data:
            del arm_data[RIG_EXPORT_TEMPLATE_KEY]
    arm_data['cp77_rig_imported_pose'] = 'T_POSE' if bool(arm_data.get('T-Pose', True)) else 'A_POSE'


def _attach_imported_bone_matrices(arm_obj, source_model_matrices) -> None:
    arm_data = arm_obj.data
    bones = arm_data.bones
    matrix_count = len(source_model_matrices)
    for source_index, source_name in enumerate(arm_data.get('boneNames', [])):
        bone = bones.get(str(source_name))
        if bone is None:
            continue
        bone[RIG_IMPORT_MATRIX_KEY] = _matrix_to_flat_list(bone.matrix_local)
        bone['cp77_rig_import_matrix_version'] = RIG_IMPORT_MATRIX_VERSION
        if source_index < matrix_count:
            source_matrix = source_model_matrices[source_index]
            if source_matrix is not None:
                bone[RIG_IMPORT_SOURCE_MODEL_KEY] = _matrix_to_flat_list(source_matrix)
                continue
        if RIG_IMPORT_SOURCE_MODEL_KEY in bone:
            del bone[RIG_IMPORT_SOURCE_MODEL_KEY]


def _bounded_cache_store(cache, key, value, limit=64):
    cache[key] = value
    if len(cache) > limit:
        cache.pop(next(iter(cache)))


def _to_list_of_strings(seq) -> list[str]:
    if not isinstance(seq, (list, tuple)):
        return []
    out = []
    append = out.append
    for value in seq:
        if isinstance(value, dict) and "$value" in value:
            append(str(value.get("$value", "")))
        elif isinstance(value, str):
            append(value)
    return out


def _extract_trs(trs: list[dict], n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return parse_wkit_trs(trs, n, quaternion_order="xyzw")






def create_debug_empties(obj, bone_names, bone_parents, bone_transforms, apose_ls, apose_ms, bind_pose):
    """
    Creates empties on an imported rig's joints for local and model space,
    and groups them under a parent collection
    """
    debug_collection_name = f"{obj.name}_transform_debugging"
    debug_collection = bpy.data.collections.get(debug_collection_name)
    if debug_collection is None:
        debug_collection = track_created_datablock(
            "collections", bpy.data.collections.new(debug_collection_name)
        )
        bpy.context.scene.collection.children.link(debug_collection)
    debug_collection['owner'] = obj

    # Helper to create a child collection and link it to Debugging
    def ensure_debug_subcollection(sub_name, create_fn):
        if sub_name in bpy.data.collections:
            sub_col = bpy.data.collections[sub_name]
        else:
            sub_col = track_created_datablock(
                "collections", bpy.data.collections.new(sub_name)
            )
            debug_collection.children.link(sub_col)
        create_fn(sub_col)

    if bind_pose == 'A-Pose':
        if apose_ls is not None:
            ensure_debug_subcollection(
                "aPoseLS", lambda col: create_aposels_empties(
                        obj, bone_names, bone_parents, apose_ls, collection_name=col.name
                        )
                )

        if apose_ms is not None:
            ensure_debug_subcollection(
                "aPoseMS", lambda col: create_aposems_empties(
                        obj, bone_names, bone_parents, apose_ms, collection_name=col.name
                        )
                )
    else:
        if bone_transforms is not None:
            ensure_debug_subcollection(
                "tPoseLS", lambda col: create_aposels_empties(
                        obj, bone_names, bone_parents, bone_transforms, collection_name=col.name
                        )
                )


def _create_pose_debug_empties(
        obj,
        bone_names,
        parent_indices,
        bone_transforms,
        collection_name,
        *,
        parent_hierarchy,
        ):
    collection = bpy.data.collections.get(collection_name)
    if collection is None:
        collection = track_created_datablock(
            "collections", bpy.data.collections.new(collection_name)
        )
    if collection.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(collection)

    empties = {}
    for index, name in enumerate(bone_names):
        empty = track_created_datablock(
            "objects", bpy.data.objects.new(f"{collection_name}_{name}", None)
        )
        empty.empty_display_size = 0.05
        empty.empty_display_type = 'ARROWS'
        empty.rotation_mode = 'QUATERNION'
        collection.objects.link(empty)
        empties[index] = empty

    if parent_hierarchy:
        for index, parent_index in enumerate(np.asarray(parent_indices, dtype=np.int32)):
            if parent_index >= 0 and parent_index in empties:
                child = empties[index]
                parent = empties[parent_index]
                child.parent = parent
                child.matrix_parent_inverse = parent.matrix_world.inverted()

    for index, transform in enumerate(bone_transforms):
        translation = transform["Translation"]
        rotation = transform["Rotation"]
        scale = transform["Scale"]
        empty = empties[index]
        bone_name = bone_names[index]
        empty.location = (translation["X"], translation["Y"], translation["Z"])
        empty.rotation_quaternion = Quaternion((rotation["r"], rotation["i"], rotation["j"], rotation["k"]))
        empty.scale = (scale["X"], scale["Y"], scale["Z"])
        constraint = empty.constraints.new(type='COPY_TRANSFORMS')
        constraint.name = f"CopyTransforms_{bone_name}"
        constraint.target = obj
        constraint.subtarget = bone_name
        constraint.owner_space = 'WORLD'
        constraint.target_space = 'WORLD'
        empty['Owner'] = f"{obj.name} {bone_name}"
        empty['Space: '] = collection_name
        empty["raw_translation"] = [translation["X"], translation["Y"], translation["Z"]]
        empty["raw_rotation"] = [rotation["r"], rotation["i"], rotation["j"], rotation["k"]]
        empty["raw_scale"] = [scale["X"], scale["Y"], scale["Z"]]


def create_aposels_empties(obj, bone_names, parent_indices, bone_transforms, collection_name="aPoseLS_Debug"):
    _create_pose_debug_empties(
            obj, bone_names, parent_indices, bone_transforms, collection_name, parent_hierarchy=True
            )


def create_aposems_empties(obj, bone_names, parent_indices, bone_transforms, collection_name="aPoseMS_Debug"):
    _create_pose_debug_empties(
            obj, bone_names, parent_indices, bone_transforms, collection_name, parent_hierarchy=False
            )










def is_identity_transform(transform: dict) -> bool:
    t = transform["Translation"];
    r = transform["Rotation"];
    s = transform["Scale"]
    return (
            abs(t["X"]) < 1e-6 and abs(t["Y"]) < 1e-6 and abs(t["Z"]) < 1e-6 and
            abs(r["r"] - 1) < 1e-6 and abs(r["i"]) < 1e-6 and abs(r["j"]) < 1e-6 and abs(r["k"]) < 1e-6 and
            abs(s["X"] - 1) < 1e-6 and abs(s["Y"] - 1) < 1e-6 and abs(s["Z"] - 1) < 1e-6
    )






def create_armature_from_data(
        filepath: str, bind_pose: str, create_debug: bool = False, assign_shapes: bool = True,
        rig_repository=None,
        ):
    rig_data = _load_rig_data(filepath, rig_repository)
    if not rig_data:
        show_message(f"Failed to load rig data from {filepath} ERROR")
        return None
    return create_armature_from_rig_data(
            rig_data,
            bind_pose,
            create_debug,
            source_rig_file=filepath,
            source_document=copy.deepcopy(rig_data.source_document),
            assign_shapes=assign_shapes,
            )


def create_armature_from_rig_files(
        filepaths, merged_name: str = '', source_label: str = '', create_debug: bool = False,
        assign_shapes: bool = True, rig_repository=None,
        ):
    """Build one JSON-derived armature by merging each later rig into the first.

    ``filepaths[0]`` is the base rig. Input order is authoritative and duplicate bones
    retain the base/earlier rig definition."""
    rig_datas = []
    for filepath in filepaths:
        rig_data = _load_rig_data(filepath, rig_repository)
        if rig_data:
            rig_datas.append(rig_data)
        else:
            show_message(f"Failed to load rig data from {filepath} ERROR")
    if not rig_datas:
        return None
    # A single rig uses the same remapping, pose fallback, parent, and track rules.
    merged = merge_rig_datas(rig_datas, merged_name or rig_datas[0].rig_name + '_metarig')
    merged_source = source_label or ';'.join(filepaths)
    return create_armature_from_rig_data(
            merged,
            'A-Pose',
            create_debug,
            source_rig_file=merged_source,
            source_document=merged_rig_document(filepaths, merged, source_label, rig_datas),
            assign_shapes=assign_shapes,
            )


def _identity_trs() -> dict:
    return {
        'Translation': {'X': 0.0, 'Y': 0.0, 'Z': 0.0},
        'Rotation': {'i': 0.0, 'j': 0.0, 'k': 0.0, 'r': 1.0},
        'Scale': {'X': 1.0, 'Y': 1.0, 'Z': 1.0},
        }


def _rig_apose_ls(rig_data) -> list[dict]:
    # Use the A-pose only when it covers the complete bone set.
    if len(rig_data.apose_ls) == len(rig_data.bone_names):
        return rig_data.apose_ls
    return rig_data.bone_transforms


def _precise_meta_pose_ls(rig_datas, meta_bone_names: list[str]):
    """Resolve the local A-pose transform for every merged-rig bone.

    Rigs are searched in order, and the first rig containing a bone supplies its local
    transform. Model space is accumulated later through the merged parent hierarchy.
    """
    first_transform_by_name = {}
    for rig_data in rig_datas:
        source_ls = _rig_apose_ls(rig_data)
        source_count = len(source_ls)
        seen_in_rig = set()
        for source_index, raw_name in enumerate(rig_data.bone_names):
            if source_index >= source_count:
                break
            name = merged_bone_name(raw_name)
            if not name or name in seen_in_rig:
                continue
            seen_in_rig.add(name)
            transform = source_ls[source_index]
            if transform is not None and name not in first_transform_by_name:
                first_transform_by_name[name] = transform
    return [transform if (transform := first_transform_by_name.get(name)) is not None else _identity_trs() for name in
            meta_bone_names]


def _merge_rig_data_into_state(
        rig_data,
        rig_order,
        names,
        index_by_meta_name,
        transforms,
        parents,
        track_names,
        track_index_by_name,
        reference_tracks,
        parts,
        bone_sources,
        rig_bone_mappings,
        rig_track_mappings,
        ):
    """Merge one rig's bones and tracks into the shared state."""
    source_ls = _rig_apose_ls(rig_data)
    source_names = rig_data.bone_names
    source_meta_names = [merged_bone_name(name) for name in source_names]
    parent_indices = rig_data.parent_indices.tolist() if hasattr(rig_data.parent_indices, 'tolist') else list(
        rig_data.parent_indices
        )

    bone_mapping = [-1] * len(source_names)
    for bone_index, raw_bone_name in enumerate(source_names):
        bone_name = source_meta_names[bone_index]
        existing_index = index_by_meta_name.get(bone_name)
        if existing_index is not None:
            bone_mapping[bone_index] = existing_index
            continue

        source_parent = int(parent_indices[bone_index]) if bone_index < len(parent_indices) else -1
        if 0 <= source_parent < len(source_names):
            parent_name = source_meta_names[source_parent]
            merged_parent = index_by_meta_name.get(parent_name, -1)
        else:
            parent_name = ''
            merged_parent = -1

        merged_index = len(names)
        index_by_meta_name[bone_name] = merged_index
        names.append(bone_name)
        transforms.append(
                source_ls[bone_index]
                if bone_index < len(source_ls) and source_ls[bone_index]
                else _identity_trs()
                )
        parents.append(merged_parent)
        bone_mapping[bone_index] = merged_index
        bone_sources[bone_name] = {
            'rig_order': rig_order,
            'rig_name': rig_data.rig_name,
            'source_index': bone_index,
            'source_name': raw_bone_name,
            'meta_name': bone_name,
            'parent_meta_name': parent_name,
            }

    # The engine omits source bone zero from AnimPartMetaMapping, but it still inserts
    # that bone into the MetaRig. Preserve the full source->meta map here and expose the
    # exact runtime mapping separately.
    rig_bone_mappings.append(
            {
                'rig_name': rig_data.rig_name,
                'all': bone_mapping,
                'runtime': [
                    (source_index, target_index)
                    for source_index, target_index in enumerate(bone_mapping)
                    if source_index != 0 and target_index >= 0
                    ],
                }
            )

    track_mapping = []
    for track_index, track_name in enumerate(rig_data.track_names):
        existing_index = track_index_by_name.get(track_name)
        if existing_index is None:
            existing_index = len(track_names)
            track_index_by_name[track_name] = existing_index
            track_names.append(track_name)
            reference_tracks.append(
                    rig_data.reference_tracks[track_index]
                    if track_index < len(rig_data.reference_tracks)
                    else 0.0
                    )
        track_mapping.append((track_index, existing_index))
    rig_track_mappings.append({'rig_name': rig_data.rig_name, 'runtime': track_mapping})

    if rig_data.parts:
        parts.extend(rig_data.parts)


def merge_rig_datas(rig_datas, merged_name: str, return_metadata: bool = False):
    """Build the merged rig topology and its local A-pose.

    Rigs are consumed in caller order. Bone names, parents, tracks, and mappings use
    first-wins resolution. Local transforms are then resolved in the same order before
    model space is accumulated through the merged hierarchy.
    """
    if not rig_datas:
        return (None, {}) if return_metadata else None
    rig_datas = list(rig_datas)
    source_ids = tuple(id(rig_data) for rig_data in rig_datas)
    cache_key = (merged_name, source_ids)
    cached = _MERGED_RIG_DATA_CACHE.get(cache_key)
    if cached is not None:
        cached_sources, cached_merged, cached_metadata = cached
        if len(cached_sources) == len(rig_datas) and all(a is b for a, b in zip(cached_sources, rig_datas)):
            return (cached_merged, cached_metadata) if return_metadata else cached_merged

    names: list[str] = []
    index_by_meta_name: dict[str, int] = {}
    transforms: list[dict] = []
    parents: list[int] = []
    track_names: list[str] = []
    track_index_by_name: dict[str, int] = {}
    reference_tracks: list[Any] = []
    parts: list[Any] = []
    bone_sources: dict[str, dict] = {}
    rig_bone_mappings: list[dict] = []
    rig_track_mappings: list[dict] = []

    base_rig = rig_datas[0]
    for rig_order, rig_data in enumerate(rig_datas):
        _merge_rig_data_into_state(
                rig_data,
                rig_order,
                names,
                index_by_meta_name,
                transforms,
                parents,
                track_names,
                track_index_by_name,
                reference_tracks,
                parts,
                bone_sources,
                rig_bone_mappings,
                rig_track_mappings,
                )

    # Resolve local transforms after the first-wins topology and mappings are complete.
    transforms = _precise_meta_pose_ls(rig_datas, names)

    q, t, s = _extract_trs(transforms, len(names))
    merged = RigData(
            num_bones=len(names),
            parent_indices=np.asarray(parents, dtype=np.int16),
            bone_names=names,
            track_names=track_names,
            ls_q=q,
            ls_t=t,
            ls_s=s,
            rig_name=merged_name,
            disable_connect=True,
            apose_ls=list(transforms),
            bone_transforms=list(transforms),
            parts=parts,
            rig_extra_tracks=list(base_rig.rig_extra_tracks),
            reference_tracks=reference_tracks,
            cooking_platform=base_rig.cooking_platform,
            distance_category_to_lod_map=list(base_rig.distance_category_to_lod_map),
            ik_setups=list(base_rig.ik_setups),
            level_of_detail_start_indices=list(base_rig.level_of_detail_start_indices),
            ragdoll_desc=list(base_rig.ragdoll_desc),
            ragdoll_names=list(base_rig.ragdoll_names),
            )
    metadata = {
        'bone_sources': bone_sources,
        'bone_index_by_name': dict(index_by_meta_name),
        'rig_bone_mappings': rig_bone_mappings,
        'rig_track_mappings': rig_track_mappings,
        'rig_order': [rig_data.rig_name for rig_data in rig_datas],
        }
    _bounded_cache_store(
            _MERGED_RIG_DATA_CACHE,
            cache_key,
            (tuple(rig_datas), merged, metadata),
            limit=32,
            )
    return (merged, metadata) if return_metadata else merged


def rig_data_to_root_chunk(rig_data) -> dict:
    """Represent a merged RigData as the RootChunk shape used by entity import."""
    if rig_data is None:
        return {}
    return {
        'boneNames': [{'$value': name} for name in rig_data.bone_names],
        'boneParentIndexes': rig_data.parent_indices.tolist(),
        'boneTransforms': list(rig_data.bone_transforms),
        'aPoseLS': list(rig_data.apose_ls),
        'aPoseMS': [],
        'trackNames': [{'$value': name} for name in rig_data.track_names],
        'referenceTracks': list(rig_data.reference_tracks),
        'levelOfDetailStartIndices': list(rig_data.level_of_detail_start_indices),
        'distanceCategoryToLodMap': list(rig_data.distance_category_to_lod_map),
        }


def _matrix_is_identity(mat: Matrix, eps: float = 1e-6) -> bool:
    return (
            abs(mat[0][0] - 1.0) <= eps and abs(mat[0][1]) <= eps and abs(mat[0][2]) <= eps and abs(mat[0][3]) <= eps
            and abs(mat[1][0]) <= eps and abs(mat[1][1] - 1.0) <= eps and abs(mat[1][2]) <= eps and abs(
            mat[1][3]
            ) <= eps
            and abs(mat[2][0]) <= eps and abs(mat[2][1]) <= eps and abs(mat[2][2] - 1.0) <= eps and abs(
            mat[2][3]
            ) <= eps
            and abs(mat[3][0]) <= eps and abs(mat[3][1]) <= eps and abs(mat[3][2]) <= eps and abs(
        mat[3][3] - 1.0
        ) <= eps
    )



def _coerce_model_space_matrices(values, bone_count: int):
    if values is None:
        return None
    try:
        sequence = list(values)
    except TypeError as error:
        raise ValueError("model_space_matrices must be an iterable of 4x4 matrices") from error
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
            matrix = Matrix(tuple(tuple(float(component) for component in row) for row in array))
        matrices.append(matrix)
    return tuple(matrices)


# Blender edit bones store head, tail and roll in float32. matrix_local's Y axis is
# recovered as (tail - head) / length, so the perpendicular component of the endpoint
# rounding error scales as ulp(|head|) / length: a short bone far from the origin cannot
# represent its own rest orientation. The direct mesh importer compares matrix_local against
# the authoritative inverse-bind rest within _BIND_MATRIX_TOLERANCE, and a bone below the
# length this implies makes that comparison unsatisfiable no matter how it is assigned.
_BIND_PRECISION_TARGET = 1.0e-5


def _precision_safe_bone_length(head, requested, target: float = _BIND_PRECISION_TARGET) -> float:
    """Raise a bone length until float32 head/tail can carry its orientation."""
    magnitude = max(
        abs(float(head[0])), abs(float(head[1])), abs(float(head[2])), 1.0e-6
    )
    ulp = float(np.spacing(np.float32(magnitude)))
    return max(float(requested), 2.0 * ulp / target)


def _set_edit_bone_model_matrices(
        edit_bones_by_index,
        model_matrices,
        parent_indices,
        *,
        default_length: float = 0.01,
        ) -> None:
    children = children_by_parent(parent_indices)
    heads = tuple(matrix.to_translation() for matrix in model_matrices)
    for bone_index, matrix in enumerate(model_matrices):
        distances = []
        for child_index in children[bone_index]:
            if child_index >= len(heads):
                continue
            distance = (heads[child_index] - heads[bone_index]).length
            if distance > 1e-6:
                distances.append(distance)
        length = max(
            sum(distances) / len(distances) if distances else default_length,
            default_length,
        )
        length = _precision_safe_bone_length(heads[bone_index], length)
        edit_bone = edit_bones_by_index[bone_index]
        edit_bone.matrix = matrix
        edit_bone.length = length


@contextmanager
def _isolated_armature_edit_session(arm_obj):
    """Edit one armature in a temporary one-object scene.

    Blender mode transitions evaluate the active view layer. Keeping the build object in
    an isolated scene prevents edit-mode entry and exit from traversing a populated import
    scene while leaving the resulting armature datablock and object fully reusable there.
    """
    global _RIG_BUILD_SERIAL

    context = bpy.context
    _RIG_BUILD_SERIAL += 1
    build_scene = track_created_datablock("scenes", bpy.data.scenes.new(
        f"__CP77_RIG_BUILD_{_RIG_BUILD_SERIAL:06d}__"
    ))
    build_view_layer = build_scene.view_layers[0]
    build_scene.collection.objects.link(arm_obj)
    arm_obj.hide_viewport = False
    arm_obj.hide_select = False
    arm_obj.select_set(True, view_layer=build_view_layer)
    build_view_layer.objects.active = arm_obj

    timings = {"enter": 0.0, "exit": 0.0}
    override = {
        "scene": build_scene,
        "view_layer": build_view_layer,
        "collection": build_scene.collection,
        "object": arm_obj,
        "active_object": arm_obj,
        "selected_objects": [arm_obj],
        "selected_editable_objects": [arm_obj],
    }

    try:
        with context.temp_override(**override):
            phase_started = time.perf_counter()
            if bpy.context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            if not bpy.ops.object.mode_set.poll():
                raise RuntimeError(
                    f"Unable to enter isolated Armature Edit Mode for {arm_obj.name!r}."
                )
            bpy.ops.object.mode_set(mode='EDIT')
            timings["enter"] = time.perf_counter() - phase_started
            try:
                yield timings
            finally:
                phase_started = time.perf_counter()
                if bpy.context.mode != 'OBJECT':
                    bpy.ops.object.mode_set(mode='OBJECT')
                timings["exit"] = time.perf_counter() - phase_started
    finally:
        if getattr(arm_obj, 'mode', 'OBJECT') != 'OBJECT':
            try:
                with context.temp_override(**override):
                    bpy.ops.object.mode_set(mode='OBJECT')
            except Exception:
                pass
        try:
            arm_obj.select_set(False, view_layer=build_view_layer)
        except (ReferenceError, RuntimeError):
            pass
        try:
            if build_scene.collection.objects.get(arm_obj.name) is arm_obj:
                build_scene.collection.objects.unlink(arm_obj)
        except (ReferenceError, RuntimeError):
            pass
        if bpy.data.scenes.get(build_scene.name) is build_scene:
            bpy.data.scenes.remove(build_scene)


def _activate_armature_in_current_view_layer(arm_obj) -> None:
    context = bpy.context
    for selected in tuple(context.selected_objects):
        try:
            selected.select_set(False)
        except (ReferenceError, RuntimeError):
            pass
    arm_obj.hide_viewport = False
    arm_obj.hide_select = False
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
    """Apply authoritative armature-space rest matrices in an isolated edit scene."""
    if arm_obj is None or getattr(arm_obj, 'type', None) != 'ARMATURE':
        raise ValueError("set_armature_model_space_matrices requires an armature object")
    names = tuple(str(name) for name in bone_names)
    matrices = _coerce_model_space_matrices(model_space_matrices, len(names))
    original_lengths = {
        bone.name: max(float(bone.length), 1.0e-5)
        for bone in arm_obj.data.bones
    }

    with _isolated_armature_edit_session(arm_obj) as timings:
        edit_bones = arm_obj.data.edit_bones
        for name, matrix in zip(names, matrices):
            edit_bone = edit_bones.get(name)
            if edit_bone is None:
                raise ValueError(f"Armature {arm_obj.name!r} is missing edit bone {name!r}")
            edit_bone.matrix = matrix
            edit_bone.length = _precision_safe_bone_length(
                matrix.translation, original_lengths.get(name, 0.01)
            )

    _attach_imported_bone_matrices(arm_obj, matrices)
    return timings

def create_armature_from_rig_data(
        rig_data,
        bind_pose: str,
        create_debug: bool = False,
        source_rig_file: str = '',
        source_document: dict | None = None,
        assign_shapes: bool = True,
        model_space_matrices=None,
        ):
    start_time = time.perf_counter()
    rig_name = str(rig_data.rig_name)
    mode_seconds = 0.0

    print(f'Beginning Import of: {rig_name} from: {source_rig_file} Bind Pose: {bind_pose}')
    context = bpy.context

    phase_started = time.perf_counter()
    safe_mode_switch('OBJECT')
    mode_seconds += time.perf_counter() - phase_started

    phase_started = time.perf_counter()
    coll_scene = context.scene.collection
    rig_col = bpy.data.collections.get(rig_name)
    if rig_col is None:
        rig_col = track_created_datablock(
            "collections", bpy.data.collections.new(rig_name)
        )
        coll_scene.children.link(rig_col)

    arm_data = track_created_datablock(
        "armatures", bpy.data.armatures.new(f"{rig_name}_Data")
    )
    arm_obj = track_created_datablock(
        "objects", bpy.data.objects.new(rig_name, arm_data)
    )
    rig_col.objects.link(arm_obj)

    parent_indices_list = rig_data.parent_indices.tolist()
    arm_data['source_rig_file'] = source_rig_file
    arm_data['cp77_rig_space_contract'] = _RIG_SPACE_CONTRACT
    arm_data['cp77_model_space_axes'] = 'REDengine XYZ; Blender armature space is numerically identical'
    arm_data['cp77_bone_local_basis'] = 'Blender X=-RE Z, Y=RE Y, Z=RE X'
    arm_data['boneNames'] = list(rig_data.bone_names)
    arm_data['boneParentIndexes'] = parent_indices_list
    arm_data['rig_extra_tracks'] = rig_data.rig_extra_tracks
    arm_data['trackNames'] = list(rig_data.track_names)
    arm_data['referenceTracks'] = list(rig_data.reference_tracks)
    _emit_rig_build_phase(
        'object_creation', time.perf_counter() - phase_started, rig_name, assign_shapes
    )

    override_matrices = _coerce_model_space_matrices(
        model_space_matrices,
        len(rig_data.bone_names),
    )

    try:
        with _isolated_armature_edit_session(arm_obj) as isolated_timings:
            phase_started = time.perf_counter()
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
            _emit_rig_build_phase(
                'edit_bones', time.perf_counter() - phase_started, rig_name, assign_shapes
            )

            phase_started = time.perf_counter()
            mats = build_apose_matrices(
                rig_data.apose_ms,
                rig_data.apose_ls,
                rig_data.bone_names,
                rig_data.parent_indices,
            ) if bind_pose == 'A-Pose' and override_matrices is None else None
            if override_matrices is not None:
                imported_model_matrices = override_matrices
                _set_edit_bone_model_matrices(
                    bone_index_map,
                    override_matrices,
                    rig_data.parent_indices,
                )
            else:
                global_transforms = model_space_matrices_cached(
                    rig_data.bone_transforms,
                    rig_data.parent_indices,
                )
                imported_model_matrices = mats if mats is not None else global_transforms
                if mats is None:
                    for i in range(len(rig_data.bone_names)):
                        mat = global_transforms[i] if i < len(global_transforms) else None
                        if mat is None or _matrix_is_identity(mat):
                            continue
                        apply_bone_from_matrix(
                            i,
                            mat,
                            bone_index_map,
                            rig_data.parent_indices,
                            global_transforms,
                        )

            arm_data['T-Pose'] = True
            if bind_pose == 'A-Pose' and override_matrices is None:
                if not rig_data.apose_ls and not rig_data.apose_ms:
                    print(
                        f"No A-Pose found in {rig_name}.json at {source_rig_file}, "
                        "falling back to T-Pose"
                    )
                if mats is not None:
                    for i, matrix in enumerate(mats):
                        apply_bone_from_matrix(
                            i,
                            matrix,
                            bone_index_map,
                            rig_data.parent_indices,
                            mats,
                        )
                    arm_data['T-Pose'] = False
                else:
                    print(
                        f"No A-Pose found in {rig_name}.json at {source_rig_file}, "
                        "falling back to T-Pose"
                    )
            _emit_rig_build_phase(
                'rest_matrices', time.perf_counter() - phase_started, rig_name, assign_shapes
            )

        mode_seconds += isolated_timings['enter'] + isolated_timings['exit']

        phase_started = time.perf_counter()
        if rig_data.parts:
            with _isolated_armature_edit_session(arm_obj) as part_timings:
                assign_part_groups(arm_obj, rig_data.parts)
            mode_seconds += part_timings['enter'] + part_timings['exit']
        _emit_rig_build_phase(
            'part_collections', time.perf_counter() - phase_started, rig_name, assign_shapes
        )
    except Exception:
        if bpy.data.objects.get(arm_obj.name) is arm_obj:
            bpy.data.objects.remove(arm_obj, do_unlink=True)
        if bpy.data.armatures.get(arm_data.name) is arm_data and arm_data.users == 0:
            bpy.data.armatures.remove(arm_data)
        raise

    _emit_rig_build_phase(
        'mode_selection_operations', mode_seconds, rig_name, assign_shapes
    )

    _activate_armature_in_current_view_layer(arm_obj)

    phase_started = time.perf_counter()
    if assign_shapes:
        assign_bone_shapes(arm_obj, rig_data.disable_connect)
    _emit_rig_build_phase(
        'custom_shapes', time.perf_counter() - phase_started, rig_name, assign_shapes
    )

    phase_started = time.perf_counter()
    assign_reference_tracks(arm_obj, rig_data.track_names, rig_data.reference_tracks)
    _emit_rig_build_phase(
        'reference_tracks', time.perf_counter() - phase_started, rig_name, assign_shapes
    )

    if create_debug:
        phase_started = time.perf_counter()
        create_debug_empties(
            arm_obj,
            rig_data.bone_names,
            rig_data.parent_indices,
            rig_data.bone_transforms,
            rig_data.apose_ls,
            rig_data.apose_ms,
            bind_pose,
        )
        _emit_rig_build_phase(
            'debug_empties', time.perf_counter() - phase_started, rig_name, assign_shapes
        )

    phase_started = time.perf_counter()
    for source_index, source_name in enumerate(rig_data.bone_names):
        bone = arm_data.bones.get(source_name)
        if bone is not None:
            bone['cp77_rig_index'] = source_index
            bone['cp77_rig_source_name'] = source_name
    _attach_rig_export_metadata(arm_obj, source_document)
    _attach_imported_bone_matrices(arm_obj, imported_model_matrices)
    clear_parent_cache(rig_data.parent_indices)
    _emit_rig_build_phase(
        'export_metadata', time.perf_counter() - phase_started, rig_name, assign_shapes
    )

    print(f"Successfully imported {rig_name} in {time.perf_counter() - start_time:.2f} seconds.")
    return arm_obj


def create_bone_shape():
    shape = bpy.data.objects.get("BoneCustomShape")
    if shape is None:
        current_mode = get_safe_mode()
        if current_mode != 'OBJECT':
            safe_mode_switch("OBJECT")
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.mesh.primitive_ico_sphere_add(radius=1.0, enter_editmode=False)
        shape = bpy.context.active_object
        shape.name = "BoneCustomShape"
        bpy.ops.object.shade_smooth()

    if shape.name not in bpy.context.view_layer.objects:
        bpy.context.collection.objects.link(shape)

    shape.hide_viewport = True
    shape.hide_render = True
    try:
        shape.hide_set(True)
    except RuntimeError as e:
        print(f"[create_bone_shape] Warning: Could not hide object: {e}")

    shape.select_set(False)
    return shape


def assign_bone_shapes(arm, disable_connect, shape=None):
    anim_bones = ANIMATION_BONE_SET
    if shape is None or not isinstance(shape, bpy.types.Object):
        shape = create_bone_shape()

    bpy.context.view_layer.objects.active = arm

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
    arm_obj.hide_set(False)
    arm_obj.hide_viewport = False
    arm_obj.hide_render = False
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    safe_mode_switch("EDIT")

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
    final_mask_entries = {}
    final_mask_rot_ms = []
    has_part_metadata = False
    for part in parts:
        if not isinstance(part, dict):
            continue
        part_name = part.get("name", {}).get("$value")
        if not isinstance(part_name, str):
            continue

        collection = arm_data.collections.get(part_name) or arm_data.collections.new(name=part_name)
        for bone_entry in part.get("singleBones", []):
            bone_name = bone_entry.get("$value") if isinstance(bone_entry, dict) else None
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
                resolved_root_name = root_name if bones.get(root_name) else merged_bone_name(root_name)
                root_bone = bones.get(resolved_root_name)
                if root_bone:
                    collection.assign(root_bone)
                for child_name in get_descendants(resolved_root_name):
                    child_bone = bones.get(child_name)
                    if child_bone:
                        collection.assign(child_bone)

        bones_with_rot_ms = [entry.get("$value") for entry in part.get("bonesWithRotationInModelSpace", []) if
                             isinstance(entry, dict) and "$value" in entry]
        mask_entries = {str(entry["index"]): entry["weight"] for entry in part.get("mask", []) if
                        isinstance(entry, dict) and "index" in entry and "weight" in entry}
        mask_rot_ms = part.get("maskRotMS", [])
        has_part_metadata = True
        for bone_name in bones_with_rot_ms:
            if bone_name not in final_bones_with_rot_ms:
                final_bones_with_rot_ms.append(bone_name)
        final_mask_entries.update(mask_entries)
        final_mask_rot_ms.extend(mask_rot_ms)
        for name in bones_with_rot_ms:
            if isinstance(name, str) and name not in pose_rotation_seen:
                pose_rotation_seen.add(name)
                pose_rotation_bones.append(name)

    if has_part_metadata:
        arm_obj["bonesWithRotationInModelSpace"] = final_bones_with_rot_ms
        arm_obj["mask"] = json.dumps(final_mask_entries)
        arm_obj["maskRotMS"] = final_mask_rot_ms

    if pose_rotation_bones:
        safe_mode_switch("POSE")
        pose_bones = arm_obj.pose.bones
        for bone_name in pose_rotation_bones:
            pose_bone = pose_bones.get(bone_name) or pose_bones.get(merged_bone_name(bone_name))
            if pose_bone:
                pose_bone["maskRotMS"] = True
    safe_mode_switch('OBJECT')


def assign_reference_tracks(arm_obj, track_names, reference_tracks):
    if not track_names:
        return
    names: list[str] = []
    for t in track_names:
        if isinstance(t, str):
            names.append(t)
        elif isinstance(t, dict) and "$value" in t:
            names.append(str(t["$value"]))
    for i, name in enumerate(names):
        if i < len(reference_tracks):
            ensure_track_property(
                arm_obj,
                name,
                float(reference_tracks[i]),
                default=float(reference_tracks[i]),
                overwrite_ui=False,
            )
