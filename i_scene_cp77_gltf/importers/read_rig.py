from __future__ import annotations

import base64
import copy
import json
import os
import time
import zlib
from typing import Any

import numpy as np
from mathutils import Matrix, Quaternion, Vector

from ..jsontool import JSONTool
from ..main.animation_api import ensure_float_idproperty
from ..main.animation_bones import ANIMATION_BONE_SET
from ..main.bartmoss_functions import *
from ..main.common import show_message
from ..main.datashards import RigData
from ..main.rig_utils import merged_rig_bone_name
from ..main.transform_math import parse_wkit_trs

_PARENT_CHILDREN_CACHE = {}
_RIG_DATA_FILE_CACHE = {}
_MERGED_RIG_DATA_CACHE = {}
_MODEL_SPACE_MATRIX_CACHE = {}
_SHAPE_SCALE_ROOT = (0.075, 0.075, 0.075)
_SHAPE_SCALE_WEAPON = (0.0125, 0.0125, 0.0125)
_SHAPE_SCALE_SMALL = (0.05, 0.05, 0.05)
_SHAPE_SCALE_LARGE = (0.1, 0.1, 0.1)

_RIG_SPACE_CONTRACT = "CP77_RE_MODEL_BL_BONE_X_NEGZ_Y_Y_Z_X_V1"
_RIG_EXPORT_TEMPLATE_KEY = "cp77_rig_export_template_zlib_b64"
_RIG_EXPORT_TEMPLATE_VERSION = 1
_RIG_IMPORT_MATRIX_KEY = "cp77_rig_import_matrix"
_RIG_IMPORT_SOURCE_MODEL_KEY = "cp77_rig_import_source_model_matrix"
_RIG_IMPORT_MATRIX_VERSION = 2
_SOURCE_DOCUMENT_CACHE = {}


def _matrix_to_flat_list(matrix: Matrix) -> list[float]:
    return [float(matrix[row][column]) for row in range(4) for column in range(4)]


def _cache_source_document(filepath: str, signature, document: dict) -> None:
    normalized = os.path.normcase(os.path.abspath(filepath))
    _SOURCE_DOCUMENT_CACHE[normalized] = (signature, document)


def _source_document_for_filepath(filepath: str) -> dict | None:
    normalized, signature = _rig_file_signature(filepath)
    cached = _SOURCE_DOCUMENT_CACHE.get(normalized)
    if cached is not None and cached[0] == signature:
        return copy.deepcopy(cached[1])
    try:
        data = JSONTool.jsonload(filepath)
    except Exception:
        return None
    _SOURCE_DOCUMENT_CACHE[normalized] = (signature, data)
    return copy.deepcopy(data)


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


def _merged_rig_document(filepaths, merged_rig_data, source_label: str = '') -> dict:
    base_document = _source_document_for_filepath(filepaths[0]) if filepaths else None
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


def _encode_rig_export_template(document: dict) -> str:
    raw = json.dumps(document, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return base64.b64encode(zlib.compress(raw, 9)).decode('ascii')


def _attach_rig_export_metadata(arm_obj, source_document: dict | None) -> None:
    arm_data = arm_obj.data
    source_path = str(arm_data.get('source_rig_file', ''))
    if source_document is None and source_path and ';' not in source_path and os.path.isfile(source_path):
        source_document = _source_document_for_filepath(source_path)
    document = copy.deepcopy(source_document) if source_document else _minimal_rig_document(source_path)
    try:
        arm_data[_RIG_EXPORT_TEMPLATE_KEY] = _encode_rig_export_template(document)
        arm_data['cp77_rig_export_template_version'] = _RIG_EXPORT_TEMPLATE_VERSION
    except (TypeError, ValueError, OverflowError):
        if _RIG_EXPORT_TEMPLATE_KEY in arm_data:
            del arm_data[_RIG_EXPORT_TEMPLATE_KEY]
    arm_data['cp77_rig_imported_pose'] = 'T_POSE' if bool(arm_data.get('T-Pose', True)) else 'A_POSE'


def _attach_imported_bone_matrices(arm_obj, source_model_matrices) -> None:
    for source_index, source_name in enumerate(arm_obj.data.get('boneNames', [])):
        bone = arm_obj.data.bones.get(str(source_name))
        if bone is None:
            continue
        bone[_RIG_IMPORT_MATRIX_KEY] = _matrix_to_flat_list(bone.matrix_local)
        bone['cp77_rig_import_matrix_version'] = _RIG_IMPORT_MATRIX_VERSION
        if source_index < len(source_model_matrices):
            source_matrix = source_model_matrices[source_index]
            if source_matrix is not None:
                bone[_RIG_IMPORT_SOURCE_MODEL_KEY] = _matrix_to_flat_list(source_matrix)
                continue
        if _RIG_IMPORT_SOURCE_MODEL_KEY in bone:
            del bone[_RIG_IMPORT_SOURCE_MODEL_KEY]


def _bounded_cache_store(cache, key, value, limit=64):
    cache[key] = value
    if len(cache) > limit:
        cache.pop(next(iter(cache)))


def _rig_file_signature(filepath):
    normalized = os.path.normcase(os.path.abspath(filepath))
    try:
        stat = os.stat(filepath)
    except OSError:
        return normalized, None
    return normalized, (stat.st_mtime_ns, stat.st_size)


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


def trs_dicts_to_arrays(trs_list: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return parse_wkit_trs(trs_list, quaternion_order="wxyz")


def trs_to_matrices_np(q_wxyz: np.ndarray, t: np.ndarray, s: np.ndarray) -> np.ndarray:
    """Batch convert TRS numpy arrays to homogenous 4x4 matrices.
    q_wxyz: [N,4] with (w,x,y,z)
    t: [N,3]
    s: [N,3]
    Returns: mats [N,4,4] row-major
    """
    w, x, y, z = q_wxyz[:, 0], q_wxyz[:, 1], q_wxyz[:, 2], q_wxyz[:, 3]
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z

    r00 = 1 - 2 * (yy + zz)
    r01 = 2 * (xy - wz)
    r02 = 2 * (xz + wy)
    r10 = 2 * (xy + wz)
    r11 = 1 - 2 * (xx + zz)
    r12 = 2 * (yz - wx)
    r20 = 2 * (xz - wy)
    r21 = 2 * (yz + wx)
    r22 = 1 - 2 * (xx + yy)

    # scale axes
    r00 *= s[:, 0];
    r10 *= s[:, 0];
    r20 *= s[:, 0]
    r01 *= s[:, 1];
    r11 *= s[:, 1];
    r21 *= s[:, 1]
    r02 *= s[:, 2];
    r12 *= s[:, 2];
    r22 *= s[:, 2]

    n = q_wxyz.shape[0]
    mats = np.zeros((n, 4, 4), dtype=np.float32)
    mats[:, 0, 0] = r00;
    mats[:, 0, 1] = r01;
    mats[:, 0, 2] = r02;
    mats[:, 0, 3] = t[:, 0]
    mats[:, 1, 0] = r10;
    mats[:, 1, 1] = r11;
    mats[:, 1, 2] = r12;
    mats[:, 1, 3] = t[:, 1]
    mats[:, 2, 0] = r20;
    mats[:, 2, 1] = r21;
    mats[:, 2, 2] = r22;
    mats[:, 2, 3] = t[:, 2]
    mats[:, 3, 3] = 1.0
    return mats


def read_rig(filepath: str) -> RigData:
    """Read .rig.json and return RigData (numpy-backed)."""
    normalized, signature = _rig_file_signature(filepath)
    cached = _RIG_DATA_FILE_CACHE.get(normalized)
    if cached is not None and cached[0] == signature:
        return cached[1]

    data = JSONTool.jsonload(filepath)
    _cache_source_document(filepath, signature, data)
    base_name = os.path.basename(filepath)
    rig_name = base_name.replace(".rig.json", "")

    root = data.get("Data", {}).get("RootChunk", {})
    bone_names = _to_list_of_strings(root.get("boneNames", []))
    parent_indices = np.asarray(root.get("boneParentIndexes", []), dtype=np.int16).reshape(-1)
    track_names = _to_list_of_strings(root.get("trackNames", []))

    trs = root.get("boneTransforms", [])
    q, t, s = _extract_trs(trs, len(bone_names))

    rig_data = RigData(
            num_bones=len(bone_names),
            parent_indices=parent_indices,
            bone_names=bone_names,
            track_names=track_names,
            ls_q=q,
            ls_t=t,
            ls_s=s,
            rig_name=rig_name,
            disable_connect=True,
            apose_ms=root.get("aPoseMS", []),
            apose_ls=root.get("aPoseLS", []),
            bone_transforms=trs,
            parts=root.get("parts", []),
            rig_extra_tracks=root.get("rigExtraTracks", []),
            reference_tracks=root.get("referenceTracks", []),
            cooking_platform=root.get("cookingPlatform", ""),
            distance_category_to_lod_map=root.get("distanceCategoryToLodMap", []),
            ik_setups=root.get("ikSetups", []),
            level_of_detail_start_indices=root.get("levelOfDetailStartIndices", []),
            ragdoll_desc=root.get("ragdollDesc", []),
            ragdoll_names=root.get("ragdollNames", []),
            )
    _RIG_DATA_FILE_CACHE[normalized] = (signature, rig_data)
    return rig_data


def create_debug_empties(obj, bone_names, bone_parents, bone_transforms, apose_ls, apose_ms, bind_pose):
    """
    Creates empties on an imported rig's joints for local and model space,
    and groups them under a parent collection
    """
    debug_collection_name = f"{obj.name}_transform_debugging"
    debug_collection = bpy.data.collections.get(debug_collection_name)
    if debug_collection is None:
        debug_collection = bpy.data.collections.new(debug_collection_name)
        bpy.context.scene.collection.children.link(debug_collection)
    debug_collection['owner'] = obj

    # Helper to create a child collection and link it to Debugging
    def ensure_debug_subcollection(sub_name, create_fn):
        if sub_name in bpy.data.collections:
            sub_col = bpy.data.collections[sub_name]
        else:
            sub_col = bpy.data.collections.new(sub_name)
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
    collection = bpy.data.collections.get(collection_name) or bpy.data.collections.new(collection_name)
    if collection.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(collection)

    empties = {}
    for index, name in enumerate(bone_names):
        empty = bpy.data.objects.new(f"{collection_name}_{name}", None)
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


def scale_matrix(s: Vector | tuple | list) -> Matrix:
    m = Matrix.Identity(4)
    m[0][0], m[1][1], m[2][2] = s
    return m


def meta_bone_name(name: str) -> str:
    return merged_rig_bone_name(name)


def compute_global_transform(
        index: int, transforms: list[dict], parents: np.ndarray, cache: dict[int, Matrix],
        ) -> Matrix:
    cached = cache.get(index)
    if cached is not None:
        return cached

    transform = transforms[index]
    translation = transform["Translation"]
    rotation = transform["Rotation"]
    scale = transform.get("Scale", {"X": 1.0, "Y": 1.0, "Z": 1.0})
    translation_vector = Vector((translation["X"], translation["Y"], translation["Z"]))
    rotation_quaternion = Quaternion((rotation["r"], rotation["i"], rotation["j"], rotation["k"]))
    scale_vector = Vector((scale["X"], scale["Y"], scale["Z"]))
    local_matrix = Matrix.Translation(translation_vector) @ rotation_quaternion.to_matrix().to_4x4() @ scale_matrix(
        scale_vector
        )
    parent_index = int(parents[index]) if index < len(parents) else -1
    matrix = local_matrix if parent_index == -1 else compute_global_transform(
        parent_index, transforms, parents, cache
        ) @ local_matrix
    cache[index] = matrix
    return matrix


def _model_space_matrices_cached(transforms, parent_indices):
    cache_key = (id(transforms), id(parent_indices), len(transforms), len(parent_indices))
    cached = _MODEL_SPACE_MATRIX_CACHE.get(cache_key)
    if cached is not None and cached[0] is transforms and cached[1] is parent_indices:
        return cached[2]
    resolved = {}
    matrices = tuple(
            compute_global_transform(index, transforms, parent_indices, resolved)
            for index in range(len(transforms))
            )
    _bounded_cache_store(
            _MODEL_SPACE_MATRIX_CACHE,
            cache_key,
            (transforms, parent_indices, matrices),
            )
    return matrices


def build_apose_matrices(apose_ms, apose_ls, bone_names: list[str], parent_indices: np.ndarray):
    bone_count = len(bone_names)
    # Partial A-pose arrays fall back to the reference pose.
    if not isinstance(apose_ls, list) or len(apose_ls) != bone_count:
        return None
    if isinstance(apose_ms, list) and len(apose_ms) == bone_count:
        q_wxyz, t, s = trs_dicts_to_arrays(apose_ms)
        mats_np = trs_to_matrices_np(q_wxyz, t, s)
        return [Matrix(m) for m in mats_np]

    return list(_model_space_matrices_cached(apose_ls, parent_indices))


def is_identity_transform(transform: dict) -> bool:
    t = transform["Translation"];
    r = transform["Rotation"];
    s = transform["Scale"]
    return (
            abs(t["X"]) < 1e-6 and abs(t["Y"]) < 1e-6 and abs(t["Z"]) < 1e-6 and
            abs(r["r"] - 1) < 1e-6 and abs(r["i"]) < 1e-6 and abs(r["j"]) < 1e-6 and abs(r["k"]) < 1e-6 and
            abs(s["X"] - 1) < 1e-6 and abs(s["Y"] - 1) < 1e-6 and abs(s["Z"] - 1) < 1e-6
    )


def _children_by_parent(parent_indices):
    cache_key = id(parent_indices)
    cached = _PARENT_CHILDREN_CACHE.get(cache_key)
    if cached is not None and cached[0] is parent_indices and cached[1] == len(parent_indices):
        return cached[2]
    children = [[] for _ in range(len(parent_indices))]
    for child_index, parent_index in enumerate(parent_indices):
        parent_index = int(parent_index)
        if 0 <= parent_index < len(children):
            children[parent_index].append(child_index)
    _PARENT_CHILDREN_CACHE[cache_key] = (parent_indices, len(parent_indices), children)
    return children


def apply_bone_from_matrix(
        bone_index: int, mat: Matrix, edit_bones: dict[int, bpy.types.EditBone], parent_indices: np.ndarray,
        global_transforms: dict[int, Matrix], default_length: float = 0.01,
        ):
    """Apply a REDengine model-space transform to an edit bone.

    Blender uses local Y as the bone length axis and ``align_roll`` aligns local Z.
    With the serialized Y direction used for the tail and serialized X supplied to
    ``align_roll``, the generated local basis is X=-RE Z, Y=RE Y, Z=RE X. The
    armature is tagged with this contract for consumers of bone-local data.
    """
    active_object = bpy.context.object
    if active_object is None or getattr(active_object, 'mode', None) != 'EDIT':
        safe_mode_switch('EDIT')
    head = mat.to_translation()

    distance_sum = 0.0
    distance_count = 0
    for child_index in _children_by_parent(parent_indices)[bone_index]:
        child_matrix = (
            global_transforms.get(child_index)
            if hasattr(global_transforms, 'get')
            else global_transforms[child_index] if child_index < len(global_transforms) else None
        )
        if child_matrix is None:
            continue
        distance = (child_matrix.to_translation() - head).length
        if distance > 1e-6:
            distance_sum += distance
            distance_count += 1
    length = max(distance_sum / distance_count if distance_count else default_length, default_length)

    rotation = mat.to_quaternion()
    rotation_norm_squared = sum(component * component for component in rotation)
    if rotation_norm_squared < 1e-12:
        rotation = Quaternion((1.0, 0.0, 0.0, 0.0))
    else:
        rotation.normalize()
    basis = rotation.to_matrix()
    y_axis = basis @ Vector((0.0, 1.0, 0.0))
    x_axis = basis @ Vector((1.0, 0.0, 0.0))
    if y_axis.length_squared < 1e-12:
        y_axis = Vector((0.0, 1.0, 0.0))
    else:
        y_axis.normalize()

    edit_bone = edit_bones[bone_index]
    edit_bone.head = head
    edit_bone.tail = head + y_axis * length
    edit_bone.align_roll(x_axis)


def create_armature_from_data(
        filepath: str, bind_pose: str, create_debug: bool = False, assign_shapes: bool = True,
        ):
    rig_data = read_rig(filepath)
    if not rig_data:
        show_message(f"Failed to load rig data from {filepath} ERROR")
        return None
    return create_armature_from_rig_data(
            rig_data,
            bind_pose,
            create_debug,
            source_rig_file=filepath,
            source_document=_source_document_for_filepath(filepath),
            assign_shapes=assign_shapes,
            )


def create_armature_from_rig_files(
        filepaths, merged_name: str = '', source_label: str = '', create_debug: bool = False,
        assign_shapes: bool = True,
        ):
    """Build one JSON-derived armature by merging each later rig into the first.

    ``filepaths[0]`` is the base rig. Input order is authoritative and duplicate bones
    retain the base/earlier rig definition."""
    rig_datas = []
    for filepath in filepaths:
        rig_data = read_rig(filepath)
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
            source_document=_merged_rig_document(filepaths, merged, source_label),
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
            name = meta_bone_name(raw_name)
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
    source_meta_names = [meta_bone_name(name) for name in source_names]
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
    """Represent a merged RigData as the RootChunk shape used by entity_import."""
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


def create_armature_from_rig_data(
        rig_data,
        bind_pose: str,
        create_debug: bool = False,
        source_rig_file: str = '',
        source_document: dict | None = None,
        assign_shapes: bool = True,
        ):
    start_time = time.time()
    rig_col = None

    print(f'Beginning Import of: {rig_data.rig_name} from: {source_rig_file} Bind Pose: {bind_pose}')
    context = bpy.context
    safe_mode_switch('OBJECT')
    coll_scene = context.scene.collection
    rig_col = bpy.data.collections.get(rig_data.rig_name)
    if rig_col is None:
        rig_col = bpy.data.collections.new(rig_data.rig_name)
        coll_scene.children.link(rig_col)
    bpy.ops.object.add(type='ARMATURE', enter_editmode=True, location=(0, 0, 0))
    arm_obj = context.object
    if rig_col not in arm_obj.users_collection:
        rig_col.objects.link(arm_obj)
    for collection in tuple(arm_obj.users_collection):
        if collection is not rig_col:
            collection.objects.unlink(arm_obj)

    arm_data = arm_obj.data
    arm_obj.name = rig_data.rig_name
    arm_data.name = f"{rig_data.rig_name}_Data"
    parent_indices_list = rig_data.parent_indices.tolist()
    arm_data['source_rig_file'] = source_rig_file
    arm_data['cp77_rig_space_contract'] = _RIG_SPACE_CONTRACT
    arm_data['cp77_model_space_axes'] = 'REDengine XYZ; Blender armature space is numerically identical'
    arm_data['cp77_bone_local_basis'] = 'Blender X=-RE Z, Y=RE Y, Z=RE X'
    arm_data['boneNames'] = rig_data.bone_names
    arm_data['boneParentIndexes'] = parent_indices_list
    arm_data['rig_extra_tracks'] = rig_data.rig_extra_tracks
    arm_data['trackNames'] = list(rig_data.track_names)
    arm_data['referenceTracks'] = list(rig_data.reference_tracks)

    edit_bones = arm_data.edit_bones
    bone_index_map: dict[int, bpy.types.EditBone] = {}

    for i, name in enumerate(rig_data.bone_names):
        b = edit_bones.new(name)
        b.head = Vector((0, 0, 0))
        b.tail = Vector((0, 0.05, 0))
        bone_index_map[i] = b

    for i, parent_idx in enumerate(parent_indices_list):
        child_bone = bone_index_map[i]
        if parent_idx != -1:
            parent_bone = bone_index_map[parent_idx]
            child_bone.parent = parent_bone

    mats = build_apose_matrices(
        rig_data.apose_ms, rig_data.apose_ls, rig_data.bone_names, rig_data.parent_indices
        ) if bind_pose == 'A-Pose' else None
    global_transforms = _model_space_matrices_cached(rig_data.bone_transforms, rig_data.parent_indices)
    imported_model_matrices = mats if mats is not None else global_transforms
    if mats is None:

        for i in range(len(rig_data.bone_names)):
            mat = global_transforms[i] if i < len(global_transforms) else None
            # Skip on the accumulated transform: a bone whose local transform is identity but
            # whose parent is transformed still needs placing at that parent.
            if mat is None or _matrix_is_identity(mat):
                continue
            apply_bone_from_matrix(i, mat, bone_index_map, rig_data.parent_indices, global_transforms)

    arm_data['T-Pose'] = True

    if bind_pose == 'A-Pose':
        if not rig_data.apose_ls and not rig_data.apose_ms:
            print(f"No A-Pose found in {rig_data.rig_name}.json at {source_rig_file}, falling back to T-Pose")
        if mats is not None:
            # Tail directions must be derived from the same pose as the heads and rolls.
            # Using reference-pose child positions here creates a hybrid A/T-pose rest rig.
            apose_global_transforms = mats
            for i, m in enumerate(mats):
                apply_bone_from_matrix(i, m, bone_index_map, rig_data.parent_indices, apose_global_transforms)
            arm_data['T-Pose'] = False
        else:
            print(f"No A-Pose found in {rig_data.rig_name}.json at {source_rig_file}, falling back to T-Pose")

    assign_part_groups(arm_obj, rig_data.parts)
    if assign_shapes:
        assign_bone_shapes(arm_obj, rig_data.disable_connect)
    assign_reference_tracks(arm_obj, rig_data.track_names, rig_data.reference_tracks)

    if create_debug:
        create_debug_empties(
            arm_obj, rig_data.bone_names, rig_data.parent_indices, rig_data.bone_transforms, rig_data.apose_ls,
            rig_data.apose_ms, bind_pose
            )

    safe_mode_switch('OBJECT')
    for source_index, source_name in enumerate(rig_data.bone_names):
        bone = arm_data.bones.get(source_name)
        if bone is not None:
            bone['cp77_rig_index'] = source_index
            bone['cp77_rig_source_name'] = source_name
    _attach_rig_export_metadata(arm_obj, source_document)
    _attach_imported_bone_matrices(arm_obj, imported_model_matrices)
    _PARENT_CHILDREN_CACHE.pop(id(rig_data.parent_indices), None)
    print(f"Successfully imported {rig_data.rig_name} in {time.time() - start_time:.2f} seconds.")
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
    bpy.ops.object.mode_set(mode='POSE')

    for pb in arm.pose.bones:
        name = pb.name
        pb.custom_shape = None

        if name in {"Root", "Hips", "Trajectory"}:
            pb.custom_shape = shape
            pb.custom_shape_scale_xyz = _SHAPE_SCALE_ROOT
            pb.use_custom_shape_bone_size = False
        elif name in {"WeaponLeft", "WeaponRight"}:
            pb.custom_shape = shape
            pb.custom_shape_scale_xyz = _SHAPE_SCALE_WEAPON
            pb.use_custom_shape_bone_size = False
        else:
            use_shape = (disable_connect or name.endswith("JNT") or name.endswith("GRP") or name.endswith("IK"))
            if use_shape:
                pb.custom_shape = shape
                if disable_connect:
                    pb.custom_shape_scale_xyz = _SHAPE_SCALE_SMALL
                    pb.use_custom_shape_bone_size = True
                elif name not in anim_bones:
                    pb.custom_shape_scale_xyz = _SHAPE_SCALE_LARGE
                else:
                    pb.custom_shape_scale_xyz = _SHAPE_SCALE_SMALL


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
                bone = bones.get(bone_name) or bones.get(meta_bone_name(bone_name))
                if bone:
                    collection.assign(bone)

        for tree in part.get("treeBones", []):
            if not isinstance(tree, dict):
                continue
            for root_name in collect_root_bones(tree):
                if not isinstance(root_name, str):
                    continue
                resolved_root_name = root_name if bones.get(root_name) else meta_bone_name(root_name)
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
            pose_bone = pose_bones.get(bone_name) or pose_bones.get(meta_bone_name(bone_name))
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
            ensure_float_idproperty(arm_obj, name, float(reference_tracks[i]))
