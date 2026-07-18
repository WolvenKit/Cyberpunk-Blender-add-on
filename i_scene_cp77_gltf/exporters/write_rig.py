from __future__ import annotations

import base64
import copy
import heapq
import json
import os
import zlib
from datetime import datetime, timezone
from typing import Any

import bpy
from mathutils import Matrix, Quaternion, Vector

from ..jsontool import JSONTool
from ..main.bartmoss_functions import safe_mode_switch

RIG_SPACE_CONTRACT = "CP77_RE_MODEL_BL_BONE_X_NEGZ_Y_Y_Z_X_V1"
RIG_EXPORT_TEMPLATE_KEY = "cp77_rig_export_template_zlib_b64"
RIG_EXPORT_TEMPLATE_VERSION = 1
RIG_IMPORT_MATRIX_KEY = 'cp77_rig_import_matrix'
RIG_IMPORT_SOURCE_MODEL_KEY = 'cp77_rig_import_source_model_matrix'
RIG_IMPORT_MATRIX_VERSION = 2
_SOURCE_DOCUMENT_CACHE = {}


def _matrix_to_flat_list(matrix: Matrix) -> list[float]:
    return [float(matrix[row][column]) for row in range(4) for column in range(4)]


def _matrix_from_flat_value(value: Any) -> Matrix | None:
    try:
        values = [float(component) for component in value]
    except (TypeError, ValueError):
        return None
    if len(values) != 16:
        return None
    return Matrix(tuple(tuple(values[row * 4 + column] for column in range(4)) for row in range(4)))


def attach_imported_bone_matrices(arm_obj, source_document: dict | None = None) -> None:
    """Persist exact import-side Blender and REDengine model baselines per bone.

    The Blender matrix captures the actual EditBone roll produced by Blender. The
    REDengine matrix captures the corresponding source model transform. Together they
    define an exact model-space edit delta for existing bones while allowing new bones
    to use the declared basis directly.
    """
    arm_data = arm_obj.data
    document = copy.deepcopy(source_document) if isinstance(source_document, dict) else None
    if document is None:
        document = _rig_export_template_from_armature(arm_obj)
    root = document.get('Data', {}).get('RootChunk', {}) if isinstance(document, dict) else {}
    imported_pose = 'T_POSE' if bool(arm_data.get('T-Pose', True)) else 'A_POSE'
    local_name = 'aPoseLS' if imported_pose == 'A_POSE' else 'boneTransforms'
    model_name = 'aPoseMS' if imported_pose == 'A_POSE' else 'referencePoseMS'
    source_pose = _source_pose_data(root, local_name, model_name)
    source_names = source_pose['names']

    for bone in arm_data.bones:
        bone[RIG_IMPORT_MATRIX_KEY] = _matrix_to_flat_list(bone.matrix_local)
        bone['cp77_rig_import_matrix_version'] = RIG_IMPORT_MATRIX_VERSION
        source_index = _bone_source_index(bone, source_names)
        if (
                source_index is not None
                and 0 <= source_index < len(source_pose['model_matrices'])
                and source_pose['model_matrices'][source_index] is not None
        ):
            bone[RIG_IMPORT_SOURCE_MODEL_KEY] = _matrix_to_flat_list(
                    source_pose['model_matrices'][source_index]
                    )
        elif RIG_IMPORT_SOURCE_MODEL_KEY in bone:
            del bone[RIG_IMPORT_SOURCE_MODEL_KEY]


def _imported_bone_matrix(bone) -> Matrix | None:
    return _matrix_from_flat_value(bone.get(RIG_IMPORT_MATRIX_KEY))


def _imported_source_model_matrix(bone) -> Matrix | None:
    return _matrix_from_flat_value(bone.get(RIG_IMPORT_SOURCE_MODEL_KEY))


def _rig_file_signature(filepath):
    normalized = os.path.normcase(os.path.abspath(filepath))
    try:
        stat = os.stat(filepath)
    except OSError:
        return normalized, None
    return normalized, (stat.st_mtime_ns, stat.st_size)


def cache_source_document(filepath: str, signature, document: dict) -> None:
    normalized = os.path.normcase(os.path.abspath(filepath))
    _SOURCE_DOCUMENT_CACHE[normalized] = (signature, document)


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


def _scale_matrix(scale: Vector | tuple | list) -> Matrix:
    matrix = Matrix.Identity(4)
    matrix[0][0], matrix[1][1], matrix[2][2] = scale
    return matrix


def _rig_data_to_root_chunk(rig_data) -> dict:
    return {
        'boneNames': [_cname_entry(name) for name in rig_data.bone_names],
        'boneParentIndexes': rig_data.parent_indices.tolist(),
        'boneTransforms': list(rig_data.bone_transforms),
        'aPoseLS': list(rig_data.apose_ls),
        'aPoseMS': [],
        'trackNames': [_cname_entry(name) for name in rig_data.track_names],
        'referenceTracks': list(rig_data.reference_tracks),
        'levelOfDetailStartIndices': list(rig_data.level_of_detail_start_indices),
        'distanceCategoryToLodMap': list(rig_data.distance_category_to_lod_map),
        }


def source_document_for_filepath(filepath: str) -> dict | None:
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
    archive_path = source_rig_file
    if archive_path.lower().endswith('.json'):
        archive_path = archive_path[:-5]
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


def merged_rig_document(filepaths, merged_rig_data, source_label: str = '') -> dict:
    base_document = source_document_for_filepath(filepaths[0]) if filepaths else None
    document = base_document or _minimal_rig_document(source_label)
    root = document.setdefault('Data', {}).setdefault('RootChunk', {})
    root.update(_rig_data_to_root_chunk(merged_rig_data))
    root['$type'] = 'animRig'
    root['boneNames'] = [_cname_entry(name) for name in merged_rig_data.bone_names]
    root['trackNames'] = [_cname_entry(name) for name in merged_rig_data.track_names]
    root.setdefault('aPoseMS', [])
    root.setdefault('referencePoseMS', [])
    header = document.setdefault('Header', {})
    if source_label:
        archive_path = source_label[:-5] if source_label.lower().endswith('.json') else source_label
        header['ArchiveFileName'] = archive_path
    return document


def _encode_rig_export_template(document: dict) -> str:
    raw = json.dumps(document, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return base64.b64encode(zlib.compress(raw, 9)).decode('ascii')


def _decode_rig_export_template(payload: str) -> dict | None:
    if not payload:
        return None
    try:
        raw = zlib.decompress(base64.b64decode(payload.encode('ascii')))
        decoded = json.loads(raw.decode('utf-8'))
    except (ValueError, TypeError, zlib.error, json.JSONDecodeError):
        return None
    return decoded if isinstance(decoded, dict) else None


def attach_rig_export_metadata(arm_obj, source_document: dict | None) -> None:
    arm_data = arm_obj.data
    source_path = str(arm_data.get('source_rig_file', ''))
    if source_document is None and source_path and ';' not in source_path and os.path.isfile(source_path):
        source_document = source_document_for_filepath(source_path)
    document = copy.deepcopy(source_document) if source_document else _minimal_rig_document(source_path)
    try:
        arm_data[RIG_EXPORT_TEMPLATE_KEY] = _encode_rig_export_template(document)
        arm_data['cp77_rig_export_template_version'] = RIG_EXPORT_TEMPLATE_VERSION
    except (TypeError, ValueError, OverflowError):
        # The source path remains available as a fallback if Blender rejects a large ID string.
        if RIG_EXPORT_TEMPLATE_KEY in arm_data:
            del arm_data[RIG_EXPORT_TEMPLATE_KEY]
    arm_data['cp77_rig_imported_pose'] = 'T_POSE' if bool(arm_data.get('T-Pose', True)) else 'A_POSE'


def _rig_export_template_from_armature(arm_obj) -> dict:
    arm_data = arm_obj.data
    stored = _decode_rig_export_template(str(arm_data.get(RIG_EXPORT_TEMPLATE_KEY, '')))
    if stored is not None:
        return stored

    source = str(arm_data.get('source_rig_file', ''))
    if source and ';' not in source and os.path.isfile(source):
        loaded = source_document_for_filepath(source)
        if loaded is not None:
            return loaded
    return _minimal_rig_document(source)


def _bone_source_index(bone, source_names=None):
    source_index = bone.get('cp77_rig_index')
    if isinstance(source_index, int) and source_index >= 0:
        return source_index
    if source_names:
        source_name = str(bone.get('cp77_rig_source_name', bone.name))
        try:
            return source_names.index(source_name)
        except ValueError:
            try:
                return source_names.index(bone.name)
            except ValueError:
                return None
    return None


def _ordered_export_bones(arm_data):
    bones = list(arm_data.bones)
    if not bones:
        return []

    legacy_names = [str(value) for value in arm_data.get('boneNames', [])]
    bone_by_name = {}
    priority_by_name = {}
    seen_source_indices = set()

    for collection_index, bone in enumerate(bones):
        name = str(bone.name)
        if name in bone_by_name:
            raise ValueError(f"Duplicate armature bone name '{name}'.")
        bone_by_name[name] = bone

        source_index = _bone_source_index(bone, legacy_names)
        if source_index is not None and source_index not in seen_source_indices:
            seen_source_indices.add(source_index)
            priority_by_name[name] = (0, source_index, collection_index, name)
        else:
            priority_by_name[name] = (1, collection_index, collection_index, name)

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
    return ordered


def _parent_indices_for_ordered_bones(bones):
    export_index = {str(bone.name): index for index, bone in enumerate(bones)}
    if len(export_index) != len(bones):
        raise ValueError('Bone names must be unique for rig export.')

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
        raise ValueError('Rig export contains duplicate bone names.')
    if len(parent_indices) != count:
        raise ValueError('boneParentIndexes length does not match boneNames length.')
    for array_name, values in parallel_arrays:
        if values is not None and len(values) != count:
            raise ValueError(f"{array_name} length does not match boneNames length.")
    for child_index, parent_index in enumerate(parent_indices):
        if not isinstance(parent_index, int):
            raise ValueError(f'boneParentIndexes[{child_index}] is not an integer.')
        if parent_index == -1:
            continue
        if parent_index < 0 or parent_index >= count:
            raise ValueError(
                    f'boneParentIndexes[{child_index}]={parent_index} is outside the boneNames array.'
                    )
        if parent_index >= child_index:
            raise ValueError(
                    f'boneParentIndexes[{child_index}]={parent_index} does not precede its child.'
                    )


def _cname_entry(name: str, template: Any = None) -> dict:
    if isinstance(template, dict):
        entry = copy.deepcopy(template)
        entry['$value'] = name
        return entry
    return {'$type': 'CName', '$storage': 'string', '$value': name}


def _transform_scale(transform: Any) -> Vector:
    if not isinstance(transform, dict):
        return Vector((1.0, 1.0, 1.0))
    scale = transform.get('Scale', {})
    return Vector(
            (
                float(scale.get('X', 1.0)),
                float(scale.get('Y', 1.0)),
                float(scale.get('Z', 1.0)),
                )
            )


def _quaternion_length_squared(quaternion: Quaternion) -> float:
    return sum(float(component) * float(component) for component in quaternion)


def _transform_quaternion(transform: Any) -> Quaternion | None:
    if not isinstance(transform, dict):
        return None
    rotation = transform.get('Rotation', {})
    try:
        quat = Quaternion(
                (
                    float(rotation.get('r', 1.0)),
                    float(rotation.get('i', 0.0)),
                    float(rotation.get('j', 0.0)),
                    float(rotation.get('k', 0.0)),
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
        matrix: Matrix, reference_transform: Any = None, scale_override: Vector | None = None,
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
    result = copy.deepcopy(reference_transform) if isinstance(reference_transform, dict) else {}
    result.setdefault('$type', 'QsTransform')

    rotation_value = result.get('Rotation')
    if not isinstance(rotation_value, dict):
        rotation_value = {}
        result['Rotation'] = rotation_value
    rotation_value.setdefault('$type', 'Quaternion')
    rotation_value['i'] = _clean_export_float(rotation.x)
    rotation_value['j'] = _clean_export_float(rotation.y)
    rotation_value['k'] = _clean_export_float(rotation.z)
    rotation_value['r'] = _clean_export_float(rotation.w)

    translation_value = result.get('Translation')
    if not isinstance(translation_value, dict):
        translation_value = {}
        result['Translation'] = translation_value
    translation_value.setdefault('$type', 'Vector4')
    translation_value.setdefault('W', float(translation_w))
    translation_value['X'] = _clean_export_float(translation.x)
    translation_value['Y'] = _clean_export_float(translation.y)
    translation_value['Z'] = _clean_export_float(translation.z)

    scale_value = result.get('Scale')
    if not isinstance(scale_value, dict):
        scale_value = {}
        result['Scale'] = scale_value
    scale_value.setdefault('$type', 'Vector4')
    scale_value.setdefault('W', 1.0)
    scale_value['X'] = _clean_export_float(scale.x)
    scale_value['Y'] = _clean_export_float(scale.y)
    scale_value['Z'] = _clean_export_float(scale.z)
    return result


def _compose_qs_matrix(translation: Vector, rotation: Quaternion, scale: Vector) -> Matrix:
    return Matrix.Translation(translation) @ rotation.to_matrix().to_4x4() @ _scale_matrix(scale)


def _qs_transform_to_matrix(transform: Any) -> Matrix:
    if not isinstance(transform, dict):
        return Matrix.Identity(4)
    translation_value = transform.get('Translation', {})
    translation = Vector(
            (
                float(translation_value.get('X', 0.0)),
                float(translation_value.get('Y', 0.0)),
                float(translation_value.get('Z', 0.0)),
                )
            )
    rotation = _transform_quaternion(transform) or Quaternion((1.0, 0.0, 0.0, 0.0))
    return _compose_qs_matrix(translation, rotation, _transform_scale(transform))


def _rigid_matrix(matrix: Matrix) -> Matrix:
    translation, rotation, _ = matrix.decompose()
    if _quaternion_length_squared(rotation) < 1e-12:
        rotation = Quaternion((1.0, 0.0, 0.0, 0.0))
    else:
        rotation.normalize()
    return Matrix.Translation(translation) @ rotation.to_matrix().to_4x4()


def _matrix_max_abs_difference(first: Matrix, second: Matrix) -> float:
    return max(
            abs(float(first[row][column]) - float(second[row][column]))
            for row in range(4)
            for column in range(4)
            )


def _source_pose_data(root: dict, local_array_name: str, model_array_name: str | None):
    names = _to_list_of_strings(root.get('boneNames', []))
    count = len(names)
    parents_raw = root.get('boneParentIndexes', [])
    parents = [
        int(parents_raw[index]) if isinstance(parents_raw, list) and index < len(parents_raw) else -1
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

    # read_rig.py consumes a complete model-space pose array directly.  Prefer that
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

    basis = Matrix(
            (
                (0.0, 0.0, -1.0, 0.0),
                (0.0, 1.0, 0.0, 0.0),
                (1.0, 0.0, 0.0, 0.0),
                (0.0, 0.0, 0.0, 1.0),
                )
            )
    basis_inverse = basis.inverted()
    expected_blender_models = [
        _rigid_matrix(model_matrix) @ basis_inverse if model_matrix is not None else None
        for model_matrix in model_matrices
        ]
    return {
        'names': names,
        'parents': parents,
        'local_values': local_values,
        'model_values': model_values,
        'local_matrices': local_matrices,
        'model_matrices': model_matrices,
        'expected_blender_models': expected_blender_models,
        }


def _reference_transform_for_bone(root: dict, array_name: str, bone, fallback_array: str = 'boneTransforms'):
    source_index = _bone_source_index(bone, _to_list_of_strings(root.get('boneNames', [])))
    if source_index is None:
        return None
    values = root.get(array_name, [])
    if isinstance(values, list) and source_index < len(values):
        return values[source_index]
    values = root.get(fallback_array, [])
    if isinstance(values, list) and source_index < len(values):
        return values[source_index]
    return None


def _is_identity_rigid_delta(matrix: Matrix, eps: float = 2e-5) -> bool:
    return _matrix_max_abs_difference(_rigid_matrix(matrix), Matrix.Identity(4)) <= eps


def _build_topology_export_context(arm_obj, root: dict):
    arm_data = arm_obj.data
    bones = _ordered_export_bones(arm_data)
    parents = _parent_indices_for_ordered_bones(bones)
    source_names = _to_list_of_strings(root.get('boneNames', []))
    source_count = len(source_names)

    basis = Matrix(
            (
                (0.0, 0.0, -1.0, 0.0),
                (0.0, 1.0, 0.0, 0.0),
                (1.0, 0.0, 0.0, 0.0),
                (0.0, 0.0, 0.0, 1.0),
                )
            )
    current_blender_models = [_rigid_matrix(bone.matrix_local.copy()) for bone in bones]

    imported_pose_name = _resolve_rig_export_pose_target(arm_data, 'IMPORTED')
    imported_local_name = 'aPoseLS' if imported_pose_name == 'A_POSE' else 'boneTransforms'
    imported_model_name = 'aPoseMS' if imported_pose_name == 'A_POSE' else 'referencePoseMS'
    imported_source_pose = _source_pose_data(root, imported_local_name, imported_model_name)

    source_indices = []
    seen_source_indices = set()
    for bone in bones:
        source_index = _bone_source_index(bone, source_names)
        if (
                source_index is not None
                and 0 <= source_index < source_count
                and source_index not in seen_source_indices
        ):
            seen_source_indices.add(source_index)
            source_indices.append(source_index)
        else:
            source_indices.append(None)

    edit_deltas = [None] * len(bones)
    imported_desired_models = [None] * len(bones)
    new_local_matrices = [None] * len(bones)
    unchanged = [False] * len(bones)
    visiting = set()

    def resolve_imported(index: int):
        cached = imported_desired_models[index]
        if cached is not None:
            return cached
        if index in visiting:
            raise ValueError(f"Cycle detected in armature hierarchy at bone '{bones[index].name}'.")
        visiting.add(index)
        bone = bones[index]
        parent_index = parents[index]
        parent_model = resolve_imported(parent_index) if parent_index >= 0 else None
        source_index = source_indices[index]
        current_blender = current_blender_models[index]

        if source_index is not None:
            imported_blender = _imported_bone_matrix(bone)
            source_model = _imported_source_model_matrix(bone)
            if source_model is None and source_index < len(imported_source_pose['model_matrices']):
                source_model = imported_source_pose['model_matrices'][source_index]
            expected_blender = (
                imported_source_pose['expected_blender_models'][source_index]
                if source_index < len(imported_source_pose['expected_blender_models'])
                else None
            )
            if imported_blender is None:
                if (
                        expected_blender is None
                        or _matrix_max_abs_difference(current_blender, expected_blender) > 2e-5
                ):
                    raise ValueError(
                            f"Bone '{bone.name}' has no stored import rotation baseline and no longer "
                            "matches the source rig. Re-import it with the current read_rig.py "
                            "before exporting edited rotations."
                            )
                imported_blender = expected_blender
            if source_model is None:
                raise ValueError(
                        f"Bone '{bone.name}' has no REDengine source model transform for the "
                        f"imported {imported_pose_name.replace('_', '-').lower()}."
                        )
            imported_blender = _rigid_matrix(imported_blender)
            edit_delta = _rigid_matrix(current_blender @ imported_blender.inverted_safe())
            edit_deltas[index] = edit_delta
            unchanged[index] = _is_identity_rigid_delta(edit_delta)
            desired_model = edit_delta @ source_model
        else:
            # A new Blender bone is itself the authored REDengine frame. The declared
            # basis converts its local axes while leaving model-space translation intact.
            desired_model = current_blender @ basis
            if parent_model is not None:
                new_local_matrices[index] = parent_model.inverted_safe() @ desired_model
            else:
                new_local_matrices[index] = desired_model.copy()

        imported_desired_models[index] = desired_model
        visiting.remove(index)
        return desired_model

    for index in range(len(bones)):
        resolve_imported(index)

    return {
        'bones': bones,
        'bone_names': [str(bone.name) for bone in bones],
        'parent_indices': parents,
        'source_names': source_names,
        'source_indices': source_indices,
        'edit_deltas': edit_deltas,
        'unchanged': unchanged,
        'imported_pose_name': imported_pose_name,
        'imported_desired_models': imported_desired_models,
        'new_local_matrices': new_local_matrices,
        }


def _export_pose_from_context(
        context: dict,
        root: dict,
        local_array_name: str,
        model_array_name: str | None,
        ):
    bones = context['bones']
    parents = context['parent_indices']
    source_indices = context['source_indices']
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
            if source_index is not None and source_pose['local_values']:
                scale = _transform_scale(source_pose['local_values'][source_index])
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
            raise ValueError(f"Cycle detected in armature hierarchy at bone '{bones[index].name}'.")
        visiting.add(index)
        parent_index = parents[index]
        parent_model = resolve(parent_index) if parent_index >= 0 else None
        source_index = source_indices[index]

        source_local = None
        source_model = None
        source_parent = None
        model_reference = None
        if source_index is not None:
            if source_pose['local_values'] and source_index < len(source_pose['local_values']):
                source_local = source_pose['local_values'][source_index]
            if source_index < len(source_pose['model_matrices']):
                source_model = source_pose['model_matrices'][source_index]
            if source_index < len(source_pose['parents']):
                source_parent = source_pose['parents'][source_index]
            if source_pose['model_values'] and source_index < len(source_pose['model_values']):
                model_reference = source_pose['model_values'][source_index]

        current_parent_source = source_indices[parent_index] if parent_index >= 0 else -1
        can_preserve = (
                source_local is not None
                and source_model is not None
                and context['unchanged'][index]
                and source_parent == current_parent_source
        )

        if source_model is not None:
            desired_model = context['edit_deltas'][index] @ source_model
        elif source_index is not None:
            # This pose is absent for the source bone. Reuse the imported edited model
            # rather than inventing another orientation.
            desired_model = context['imported_desired_models'][index].copy()
        else:
            new_local = context['new_local_matrices'][index]
            desired_model = parent_model @ new_local if parent_model is not None else new_local.copy()

        if can_preserve:
            local_matrix = source_pose['local_matrices'][source_index].copy()
            local_transform = copy.deepcopy(source_local)
            preserved_count += 1
        else:
            local_matrix = parent_model.inverted_safe() @ desired_model if parent_model is not None else desired_model.copy()
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

        if can_preserve and model_reference is not None:
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
        'local_transforms': local_transforms,
        'model_transforms': model_transforms,
        'preserved_transform_count': preserved_count,
        'reconstructed_transform_count': reconstructed_count,
        'nonuniform_scaled_edit_count': nonuniform_scaled_edit_count,
        }


def _resolve_rig_export_pose_target(arm_data, pose_target: str) -> str:
    normalized = str(pose_target or 'IMPORTED').upper()
    if normalized == 'IMPORTED':
        fallback = 'T_POSE' if bool(arm_data.get('T-Pose', True)) else 'A_POSE'
        return str(arm_data.get('cp77_rig_imported_pose', fallback)).upper()
    if normalized in {'T_POSE', 'A_POSE', 'ALL'}:
        return normalized
    raise ValueError(f"Unsupported rig export pose target: {pose_target}")


def build_rig_json_from_armature(arm_obj, pose_target: str = 'IMPORTED') -> tuple[dict, dict]:
    if arm_obj is None or getattr(arm_obj, 'type', None) != 'ARMATURE':
        raise TypeError('Rig export requires an armature object.')
    arm_data = arm_obj.data
    contract = str(arm_data.get('cp77_rig_space_contract', ''))
    if contract and contract != RIG_SPACE_CONTRACT:
        raise ValueError(f"Unsupported rig coordinate contract: {contract}")

    document = _rig_export_template_from_armature(arm_obj)
    root = document.setdefault('Data', {}).setdefault('RootChunk', {})
    root['$type'] = 'animRig'
    source_root = copy.deepcopy(root)
    target = _resolve_rig_export_pose_target(arm_data, pose_target)
    topology = _build_topology_export_context(arm_obj, source_root)

    original_names = _to_list_of_strings(source_root.get('boneNames', []))
    original_parents = list(source_root.get('boneParentIndexes', [])) if isinstance(
        source_root.get('boneParentIndexes'), list
        ) else []
    topology_changed = (
            topology['bone_names'] != original_names
            or topology['parent_indices'] != original_parents
    )

    original_name_entries = source_root.get('boneNames', []) if isinstance(source_root.get('boneNames'), list) else []
    exported_name_entries = []
    for name, bone, source_index in zip(
            topology['bone_names'], topology['bones'], topology['source_indices']
            ):
        template = (
            original_name_entries[source_index]
            if source_index is not None and 0 <= source_index < len(original_name_entries)
            else None
        )
        exported_name_entries.append(_cname_entry(name, template))
    root['boneNames'] = exported_name_entries
    root['boneParentIndexes'] = list(topology['parent_indices'])

    t_pose = _export_pose_from_context(topology, source_root, 'boneTransforms', 'referencePoseMS')
    has_a_pose = bool(source_root.get('aPoseLS')) or bool(source_root.get('aPoseMS'))
    a_pose = (
        _export_pose_from_context(topology, source_root, 'aPoseLS', 'aPoseMS')
        if has_a_pose or target in {'A_POSE', 'ALL'}
        else None
    )

    if topology_changed or target in {'T_POSE', 'ALL'}:
        root['boneTransforms'] = copy.deepcopy(t_pose['local_transforms'])
        if isinstance(root.get('referencePoseMS'), list) and root['referencePoseMS']:
            root['referencePoseMS'] = copy.deepcopy(t_pose['model_transforms'])
    elif not isinstance(root.get('boneTransforms'), list) or len(root['boneTransforms']) != len(topology['bones']):
        root['boneTransforms'] = copy.deepcopy(t_pose['local_transforms'])

    if a_pose is not None and (topology_changed or target in {'A_POSE', 'ALL'}):
        root['aPoseLS'] = copy.deepcopy(a_pose['local_transforms'])
        root['aPoseMS'] = copy.deepcopy(a_pose['model_transforms'])

    populated_parallel_arrays = [('boneTransforms', root.get('boneTransforms'))]
    for array_name in ('referencePoseMS', 'aPoseLS', 'aPoseMS'):
        values = root.get(array_name)
        if isinstance(values, list) and values:
            populated_parallel_arrays.append((array_name, values))
    _validate_export_topology(
            topology['bone_names'],
            root['boneParentIndexes'],
            *populated_parallel_arrays,
            )

    track_names = _to_list_of_strings(root.get('trackNames', []))
    if not track_names:
        track_names = [str(value) for value in arm_data.get('trackNames', [])]
        root['trackNames'] = [_cname_entry(name) for name in track_names]
    if track_names:
        existing_reference_tracks = root.get('referenceTracks', [])
        root['referenceTracks'] = [
            float(
                arm_obj.get(name, existing_reference_tracks[index] if index < len(existing_reference_tracks) else 0.0)
                )
            for index, name in enumerate(track_names)
            ]

    header = document.setdefault('Header', {})
    header['ExportedDateTime'] = datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
    source = str(arm_data.get('source_rig_file', ''))
    if source and ';' not in source:
        header.setdefault('ArchiveFileName', source[:-5] if source.lower().endswith('.json') else source)

    pose_summaries = [t_pose] + ([a_pose] if a_pose is not None else [])
    primary_pose = a_pose if target == 'A_POSE' and a_pose is not None else t_pose
    summary = {
        'bone_count': len(topology['bones']),
        'pose_target': target,
        'topology_changed': topology_changed,
        'source_template': bool(arm_data.get(RIG_EXPORT_TEMPLATE_KEY)),
        'preserved_transform_count': primary_pose['preserved_transform_count'],
        'reconstructed_transform_count': primary_pose['reconstructed_transform_count'],
        'nonuniform_scaled_edit_count': primary_pose['nonuniform_scaled_edit_count'],
        'total_preserved_transform_count': sum(p['preserved_transform_count'] for p in pose_summaries),
        'total_reconstructed_transform_count': sum(p['reconstructed_transform_count'] for p in pose_summaries),
        'new_bone_count': sum(index is None for index in topology['source_indices']),
        'deleted_bone_count': max(
            0, len(original_names) - sum(index is not None for index in topology['source_indices'])
            ),
        }
    return document, summary


def export_armature_to_rig_json(arm_obj, filepath: str, pose_target: str = 'IMPORTED') -> dict:
    previous_mode = getattr(arm_obj, 'mode', 'OBJECT')
    mode_changed = False
    if arm_obj is getattr(bpy.context, 'object', None) and previous_mode != 'OBJECT':
        safe_mode_switch('OBJECT')
        mode_changed = True
    try:
        document, summary = build_rig_json_from_armature(arm_obj, pose_target)
    finally:
        if mode_changed and previous_mode in {'EDIT', 'POSE'}:
            safe_mode_switch(previous_mode)
    filepath = os.path.abspath(filepath)
    if not filepath.lower().endswith('.rig.json'):
        filepath += '.rig.json'
    directory = os.path.dirname(filepath)
    if directory:
        os.makedirs(directory, exist_ok=True)
    temporary = filepath + '.tmp'
    try:
        with open(temporary, 'w', encoding='utf-8', newline='\n') as handle:
            json.dump(document, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        os.replace(temporary, filepath)
    except Exception:
        try:
            if os.path.exists(temporary):
                os.remove(temporary)
        finally:
            raise
    summary['filepath'] = filepath
    return summary
