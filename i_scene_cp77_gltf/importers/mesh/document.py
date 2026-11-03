from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import numpy as np

from ...animation.rig_binding import merged_bone_name
from ...bartmoss.hierarchy import local_matrices_to_model
from ...redSpace.contracts import (
    GLTF_TO_BLENDER_BONE_RIGHT,
    GLTF_TO_RED,
    RED_TO_GLTF,
    SOURCE_REST_SPACE_CONTRACT,
)
from ...redSpace.transforms import gltf_matrix_to_red
from ...gltf.provenance import ORIGIN_PLUGIN, mark_origin
from ...blender.transactions import (
    DatablockImportTransaction,
    current_import_transaction,
    restore_id_properties as _restore_id_properties,
    snapshot_id_properties as _snapshot_id_properties,
    track_created_datablock,
    rollback_report_message,
)
from ..animation.document import (
    SamplingContext,
    SkeletonBinding,
    build_rest_armature_from_binding,
    build_sampling_context,
    read_glb,
)

try:
    import bmesh
    import bpy
    from mathutils import Matrix
except ImportError:
    bmesh = None
    bpy = None
    Matrix = None

_GLTF_TO_RED_4 = np.asarray(GLTF_TO_RED, dtype=np.float64)
_RED_TO_GLTF_4 = np.asarray(RED_TO_GLTF, dtype=np.float64)
_GLTF_TO_BONE_RIGHT_4 = np.asarray(GLTF_TO_BLENDER_BONE_RIGHT, dtype=np.float64)
_ROTATION_T = np.ascontiguousarray(_GLTF_TO_RED_4[:3, :3].astype(np.float32).T)
_BIND_MATRIX_TOLERANCE = 5.0e-5
_BIND_MATRIX_HARD_LIMIT = 1.0e-2
_WEIGHT_EPSILON = 1.0e-8
_SOURCE_NORMAL_ATTRIBUTE = ".cp77_source_normal"
_SOURCE_TANGENT_ATTRIBUTE = ".cp77_source_tangent"
_SOURCE_TANGENT_SIGN_ATTRIBUTE = ".cp77_source_tangent_sign"
_SOURCE_MESH_EXTRAS_KEY = "cp77_direct_mesh_extras"
_SOURCE_NODE_EXTRAS_KEY = "cp77_direct_node_extras"
_SOURCE_DOCUMENT_METADATA_KEY = "cp77_direct_document_metadata"
_SOURCE_SCENE_METADATA_KEY = "cp77_direct_scene_metadata"
_SOURCE_SKIN_EXTRAS_KEY = "cp77_direct_skin_extras"
_SOURCE_SKIN_BINDING_KEY = "cp77_direct_mesh_skin_binding"
_MESH_SOURCE_REST_SNAPSHOT_KEY = "cp77_direct_mesh_source_rest_json"
_SOURCE_MATERIAL_INDEX_KEY = "cp77_direct_material_index"

_COMPONENT_DTYPES = {
    5120: np.dtype("<i1"),
    5121: np.dtype("<u1"),
    5122: np.dtype("<i2"),
    5123: np.dtype("<u2"),
    5125: np.dtype("<u4"),
    5126: np.dtype("<f4"),
}
_TYPE_WIDTHS = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
    "MAT2": 4,
    "MAT3": 9,
    "MAT4": 16,
}

_UV_ATTRIBUTES = ("TEXCOORD_0", "TEXCOORD_1", "TEXCOORD_2", "TEXCOORD_3")
_COLOR_ATTRIBUTES = ("COLOR_0", "COLOR_1")
_JOINT_ATTRIBUTES = ("JOINTS_0", "JOINTS_1", "JOINTS_2", "JOINTS_3")
_WEIGHT_ATTRIBUTES = ("WEIGHTS_0", "WEIGHTS_1", "WEIGHTS_2", "WEIGHTS_3")


class DirectMeshImportError(RuntimeError):
    pass


class _MeshAccessorReader:

    __slots__ = ("document", "binary")

    def __init__(self, glb):
        self.document = glb.document
        self.binary = glb.binary

    def read(self, accessor_index: int, *, dtype=None, copy: bool = False) -> np.ndarray:
        accessors = self.document.get("accessors") or ()
        if not 0 <= accessor_index < len(accessors):
            raise DirectMeshImportError(f"Invalid glTF accessor index {accessor_index}.")
        accessor = accessors[accessor_index]
        if accessor.get("sparse"):
            raise DirectMeshImportError(
                f"Sparse accessor {accessor_index} is not supported by direct mesh import."
            )

        width = _TYPE_WIDTHS.get(accessor.get("type"))
        if width is None:
            raise DirectMeshImportError(
                f"Unsupported accessor type {accessor.get('type')!r}."
            )
        count = int(accessor.get("count", 0))
        target_dtype = np.dtype(dtype) if dtype is not None else None
        view_index = accessor.get("bufferView")
        if view_index is None:
            result = np.zeros((count, width), dtype=target_dtype or np.float32)
            return result[:, 0] if width == 1 else result

        views = self.document.get("bufferViews") or ()
        if not 0 <= view_index < len(views):
            raise DirectMeshImportError(f"Invalid glTF bufferView index {view_index}.")
        view = views[view_index]
        if int(view.get("buffer", 0)) != 0:
            raise DirectMeshImportError("Direct mesh import supports the embedded GLB buffer only.")

        component_type = int(accessor.get("componentType", 0))
        component_dtype = _COMPONENT_DTYPES.get(component_type)
        if component_dtype is None:
            raise DirectMeshImportError(
                f"Unsupported accessor component type {component_type}."
            )

        offset = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
        item_bytes = component_dtype.itemsize * width
        stride = int(view.get("byteStride", item_bytes))
        if stride < item_bytes:
            raise DirectMeshImportError(
                f"Accessor {accessor_index} has invalid byte stride {stride}."
            )
        end = offset + (count - 1) * stride + item_bytes if count else offset
        view_start = int(view.get("byteOffset", 0))
        view_end = view_start + int(view.get("byteLength", 0))
        if offset < view_start or end > view_end or end > len(self.binary):
            raise DirectMeshImportError(
                f"Accessor {accessor_index} exceeds its GLB bufferView."
            )

        if stride == item_bytes:
            raw = np.frombuffer(
                self.binary,
                dtype=component_dtype,
                count=count * width,
                offset=offset,
            ).reshape(count, width)
        else:
            raw = np.ndarray(
                shape=(count, width),
                dtype=component_dtype,
                buffer=self.binary,
                offset=offset,
                strides=(stride, component_dtype.itemsize),
            )

        if accessor.get("normalized") and component_type != 5126:
            result = raw.astype(np.float32, copy=True)
            if component_type in (5120, 5122):
                np.divide(result, float(np.iinfo(component_dtype).max), out=result)
                np.maximum(result, -1.0, out=result)
            else:
                np.divide(result, float(np.iinfo(component_dtype).max), out=result)
            if target_dtype is not None and target_dtype != result.dtype:
                result = result.astype(target_dtype, copy=False)
        else:
            result = np.asarray(raw, dtype=target_dtype or component_dtype)
            if copy:
                result = result.copy()

        return result[:, 0] if width == 1 else result


@dataclass(slots=True)
class SkinData:
    index: int
    joint_nodes: tuple[int, ...]
    bone_names: tuple[str, ...]
    parent_indices: tuple[int, ...]
    topological_joint_indices: tuple[int, ...]
    inverse_bind_matrices_gltf: np.ndarray
    inverse_bind_matrices_red: np.ndarray
    has_inverse_bind_matrices: bool
    extras: dict


@dataclass(slots=True)
class SkinningAudit:
    invalid_influence_count: int = 0
    unmapped_influence_count: int = 0
    duplicate_influence_count: int = 0
    zero_weight_vertex_count: int = 0
    valid_influence_count: int = 0
    unmapped_bones: tuple[str, ...] = ()


@dataclass(slots=True)
class Submesh:
    name: str
    lod: int
    material_index: int | None
    material_names: list[str]
    positions: np.ndarray
    triangles: np.ndarray
    normals: np.ndarray | None
    tangents: np.ndarray | None
    mesh_index: int = -1
    node_index: int = -1
    skin_index: int | None = None
    node_matrix_gltf: np.ndarray = field(
        default_factory=lambda: np.eye(4, dtype=np.float64)
    )
    node_matrix_red: np.ndarray = field(
        default_factory=lambda: np.eye(4, dtype=np.float64)
    )
    uv_layers: list[np.ndarray] = field(default_factory=list)
    color_layers: list[np.ndarray] = field(default_factory=list)
    joint_indices: np.ndarray | None = None
    joint_weights: np.ndarray | None = None
    morph_targets: list[tuple[str, np.ndarray]] = field(default_factory=list)
    mesh_extras: dict = field(default_factory=dict)
    node_extras: dict = field(default_factory=dict)

    @property
    def vertex_count(self) -> int:
        return int(self.positions.shape[0])


@dataclass(slots=True)
class DirectMeshData:
    source_path: str
    submeshes: list[Submesh]
    skin_bone_names: list[str] | None
    skins: dict[int, SkinData]
    binding: SkeletonBinding | None
    sampling_context: SamplingContext | None
    appearance_count: int
    authoritative_skin_index: int | None = None
    authoritative_mesh_bind_gltf: np.ndarray | None = None
    authoritative_joint_bind_gltf: np.ndarray | None = None
    max_inverse_bind_error: float = 0.0
    document_metadata: dict = field(default_factory=dict)
    scene_metadata: dict = field(default_factory=dict)
    source_generator: str = ""

    @property
    def is_skinned(self) -> bool:
        return self.authoritative_skin_index is not None


def _lod_from_name(name: str) -> int:
    marker_position = name.rfind("_LOD_")
    if marker_position < 0:
        return 1
    try:
        return int(name[marker_position + 5:])
    except ValueError:
        return 1


def _rotate_vectors(values) -> np.ndarray:
    source = np.asarray(values)
    if source.ndim != 2 or source.shape[1] < 3:
        raise DirectMeshImportError(f"Expected an Nx3 vector accessor, got {source.shape}.")
    return np.asarray(source[:, :3] @ _ROTATION_T, dtype=np.float32)


def _node_local_matrix(node: dict) -> np.ndarray:
    if "matrix" in node:
        values = np.asarray(node["matrix"], dtype=np.float64)
        if values.size != 16:
            raise DirectMeshImportError("glTF node matrix must contain 16 values.")
        return values.reshape(4, 4).T.copy()

    translation = np.asarray(
        node.get("translation", (0.0, 0.0, 0.0)),
        dtype=np.float64,
    )
    rotation = np.asarray(
        node.get("rotation", (0.0, 0.0, 0.0, 1.0)),
        dtype=np.float64,
    )
    scale = np.asarray(
        node.get("scale", (1.0, 1.0, 1.0)),
        dtype=np.float64,
    )
    if translation.shape != (3,) or rotation.shape != (4,) or scale.shape != (3,):
        raise DirectMeshImportError("Invalid glTF node TRS dimensions.")

    length = float(np.linalg.norm(rotation))
    if length <= 1.0e-15:
        rotation = np.asarray((0.0, 0.0, 0.0, 1.0), dtype=np.float64)
    else:
        rotation = rotation / length
    x, y, z, w = rotation
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z

    result = np.eye(4, dtype=np.float64)
    result[:3, :3] = np.asarray(
        (
            (1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)),
            (2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)),
            (2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)),
        ),
        dtype=np.float64,
    ) * scale[np.newaxis, :]
    result[:3, 3] = translation
    return result


def _node_hierarchy(document: dict):
    nodes = document.get("nodes") or ()
    parents = np.full(len(nodes), -1, dtype=np.int32)
    for parent_index, node in enumerate(nodes):
        for child_value in node.get("children", ()):
            child_index = int(child_value)
            if not 0 <= child_index < len(nodes):
                raise DirectMeshImportError(
                    f"Node {parent_index} references invalid child {child_index}."
                )
            if parents[child_index] >= 0:
                raise DirectMeshImportError(
                    f"Node {child_index} has multiple parents."
                )
            parents[child_index] = parent_index

    children = [[] for _ in nodes]
    roots = []
    for index, parent_index in enumerate(parents):
        if parent_index < 0:
            roots.append(index)
        else:
            children[int(parent_index)].append(index)

    topology = []
    stack = list(reversed(roots))
    while stack:
        index = stack.pop()
        topology.append(index)
        stack.extend(reversed(children[index]))
    if len(topology) != len(nodes):
        raise DirectMeshImportError("The glTF node hierarchy contains a cycle.")

    local = np.asarray([_node_local_matrix(node) for node in nodes], dtype=np.float64)
    global_matrices = local_matrices_to_model(local, parents, topology)
    return tuple(int(value) for value in parents), tuple(topology), global_matrices


def _skin_parent_indices(joint_nodes, node_parents):
    lookup = {node_index: joint_index for joint_index, node_index in enumerate(joint_nodes)}
    result = []
    for node_index in joint_nodes:
        parent_node = int(node_parents[node_index])
        while parent_node >= 0 and parent_node not in lookup:
            parent_node = int(node_parents[parent_node])
        result.append(lookup.get(parent_node, -1))
    return tuple(result)


def _joint_topology(parent_indices):
    children = [[] for _ in parent_indices]
    roots = []
    for index, parent_index in enumerate(parent_indices):
        if parent_index < 0:
            roots.append(index)
        elif parent_index < len(parent_indices):
            children[parent_index].append(index)
        else:
            raise DirectMeshImportError(
                f"Skin joint {index} has invalid parent index {parent_index}."
            )
    ordered = []
    stack = list(reversed(roots))
    while stack:
        index = stack.pop()
        ordered.append(index)
        stack.extend(reversed(children[index]))
    if len(ordered) != len(parent_indices):
        raise DirectMeshImportError("The skin joint hierarchy contains a cycle.")
    return tuple(ordered)


def _decode_inverse_bind_matrices(reader, skin, joint_count):
    accessor = skin.get("inverseBindMatrices")
    if accessor is None:
        return np.repeat(
            np.eye(4, dtype=np.float64)[np.newaxis, :, :],
            joint_count,
            axis=0,
        ), False

    raw = np.asarray(reader.read(int(accessor), dtype=np.float64), dtype=np.float64)
    if raw.size != joint_count * 16:
        raise DirectMeshImportError(
            "Skin inverseBindMatrices count does not match the joint table."
        )
    matrices = raw.reshape(joint_count, 4, 4).transpose(0, 2, 1).copy()
    return matrices, True


def _decode_skins(reader, document, node_parents):
    nodes = document.get("nodes") or ()
    decoded = {}
    for skin_index, skin in enumerate(document.get("skins") or ()):
        joint_nodes = tuple(int(value) for value in (skin.get("joints") or ()))
        if not joint_nodes:
            raise DirectMeshImportError(f"Skin {skin_index} has no joints.")
        if len(set(joint_nodes)) != len(joint_nodes):
            raise DirectMeshImportError(f"Skin {skin_index} contains duplicate joints.")
        if any(index < 0 or index >= len(nodes) for index in joint_nodes):
            raise DirectMeshImportError(f"Skin {skin_index} references an invalid joint node.")

        extras = skin.get("extras") or {}
        extra_names = tuple(str(value) for value in (extras.get("boneNames") or ()))
        node_names = tuple(
            str(nodes[node_index].get("name", f"bone_{node_index}"))
            for node_index in joint_nodes
        )
        if extra_names and len(extra_names) != len(joint_nodes):
            raise DirectMeshImportError(
                f"Skin {skin_index} extras boneNames count does not match its joints."
            )
        if extra_names and extra_names != node_names:
            raise DirectMeshImportError(
                f"Skin {skin_index} extras boneNames do not match joint node names."
            )
        bone_names = extra_names or node_names
        if not all(bone_names) or len(set(bone_names)) != len(bone_names):
            raise DirectMeshImportError(
                f"Skin {skin_index} does not provide unique names for every joint."
            )

        inverse_bind_matrices, has_inverse_bind_matrices = (
            _decode_inverse_bind_matrices(reader, skin, len(joint_nodes))
        )
        parent_indices = _skin_parent_indices(joint_nodes, node_parents)
        extra_parents = extras.get("boneParentIndexes")
        if extra_parents is not None:
            try:
                normalized_extra_parents = tuple(int(value) for value in extra_parents)
            except (TypeError, ValueError) as error:
                raise DirectMeshImportError(
                    f"Skin {skin_index} extras boneParentIndexes is invalid."
                ) from error
            if normalized_extra_parents != parent_indices:
                raise DirectMeshImportError(
                    f"Skin {skin_index} extras boneParentIndexes does not match "
                    "the glTF joint hierarchy."
                )
        decoded[skin_index] = SkinData(
            index=skin_index,
            joint_nodes=joint_nodes,
            bone_names=bone_names,
            parent_indices=parent_indices,
            topological_joint_indices=_joint_topology(parent_indices),
            inverse_bind_matrices_gltf=inverse_bind_matrices,
            inverse_bind_matrices_red=np.matmul(
                np.matmul(
                    _GLTF_TO_RED_4[np.newaxis, :, :],
                    inverse_bind_matrices,
                ),
                _RED_TO_GLTF_4[np.newaxis, :, :],
            ),
            has_inverse_bind_matrices=has_inverse_bind_matrices,
            extras=dict(extras),
        )
    return decoded


def _mesh_instances(document, node_globals):
    meshes = document.get("meshes") or ()
    instances = [[] for _ in meshes]
    for node_index, node in enumerate(document.get("nodes") or ()):
        mesh_value = node.get("mesh")
        if mesh_value is None:
            continue
        mesh_index = int(mesh_value)
        if not 0 <= mesh_index < len(meshes):
            raise DirectMeshImportError(
                f"Node {node_index} references invalid mesh {mesh_index}."
            )
        skin_value = node.get("skin")
        skin_index = None if skin_value is None else int(skin_value)
        instances[mesh_index].append(
            (node_index, skin_index, node_globals[node_index].copy())
        )

    identity = np.eye(4, dtype=np.float64)
    for mesh_index, values in enumerate(instances):
        if not values:
            values.append((-1, None, identity.copy()))
    return instances


def _red_model_matrix(gltf_matrix):
    return gltf_matrix_to_red(gltf_matrix)


def _authoritative_bind_data(submeshes, skins, node_globals):
    skinned = [submesh for submesh in submeshes if submesh.skin_index is not None]
    if not skinned:
        return None, None, None, 0.0

    used_skin_indices = {int(submesh.skin_index) for submesh in skinned}
    if len(used_skin_indices) != 1:
        raise DirectMeshImportError(
            "Direct mesh import currently requires all skinned mesh nodes to use one skin."
        )
    skin_index = next(iter(used_skin_indices))
    skin = skins.get(skin_index)
    if skin is None:
        raise DirectMeshImportError(f"Mesh node references missing skin {skin_index}.")

    node_joint_bind = node_globals[np.asarray(skin.joint_nodes, dtype=np.int32)]
    authoritative_mesh_bind = None
    authoritative_joint_bind = None
    maximum_error = 0.0
    try:
        bind_matrices = np.linalg.inv(skin.inverse_bind_matrices_gltf)
    except np.linalg.LinAlgError as error:
        raise DirectMeshImportError(
            f"Skin {skin_index} contains a singular inverse bind matrix."
        ) from error

    for submesh in skinned:
        mesh_bind = submesh.node_matrix_gltf
        joint_bind = np.matmul(
            mesh_bind[np.newaxis, :, :],
            bind_matrices,
        )
        error = float(np.max(np.abs(joint_bind - node_joint_bind)))
        maximum_error = max(maximum_error, error)

        if authoritative_joint_bind is None:
            authoritative_mesh_bind = mesh_bind.copy()
            authoritative_joint_bind = joint_bind
        elif not np.allclose(
            joint_bind,
            authoritative_joint_bind,
            atol=_BIND_MATRIX_TOLERANCE,
            rtol=0.0,
        ):
            raise DirectMeshImportError(
                "Mesh nodes sharing a skin resolve to different bind poses."
            )

    return (
        skin_index,
        authoritative_mesh_bind,
        authoritative_joint_bind,
        maximum_error,
    )


def _read_blocks(reader, attributes, names, dtype):
    arrays = [
        reader.read(attributes[name], dtype=dtype)
        for name in names
        if name in attributes
    ]
    if not arrays:
        return None
    if len(arrays) == 1:
        return np.ascontiguousarray(arrays[0])
    vertex_count = arrays[0].shape[0]
    if any(array.shape[0] != vertex_count for array in arrays[1:]):
        raise DirectMeshImportError("Skinning accessor blocks have inconsistent vertex counts.")
    return np.ascontiguousarray(np.concatenate(arrays, axis=1))


def _decode_skinning(reader, attributes):
    joint_blocks = tuple(
        index for index, name in enumerate(_JOINT_ATTRIBUTES)
        if name in attributes
    )
    weight_blocks = tuple(
        index for index, name in enumerate(_WEIGHT_ATTRIBUTES)
        if name in attributes
    )
    if not joint_blocks and not weight_blocks:
        return None, None
    if joint_blocks != weight_blocks:
        raise DirectMeshImportError(
            f"Skinning JOINTS/WEIGHTS blocks differ: "
            f"{joint_blocks} vs {weight_blocks}."
        )

    joints = _read_blocks(reader, attributes, _JOINT_ATTRIBUTES, np.int32)
    weights = _read_blocks(reader, attributes, _WEIGHT_ATTRIBUTES, np.float32)
    weights = np.array(weights, dtype=np.float32, order="C", copy=True)
    if joints.shape != weights.shape:
        raise DirectMeshImportError(
            f"Skinning joint/weight shapes differ: {joints.shape} vs {weights.shape}."
        )
    return joints, weights



def _decode_morph_targets(reader, primitive, mesh_extras, import_garment_support):
    targets = primitive.get("targets") or ()
    if not targets:
        return []
    names = mesh_extras.get("targetNames") or ()
    decoded = []
    append = decoded.append
    for index, target in enumerate(targets):
        accessor = target.get("POSITION")
        if accessor is None:
            continue
        name = str(names[index]) if index < len(names) else f"morph_{index}"
        if not import_garment_support and name.casefold() == "garmentsupport":
            continue
        append((name, _rotate_vectors(reader.read(accessor, dtype=np.float32))))
    return decoded


def _decode_uv_layers(reader, attributes, flip_v):
    layers = []
    append = layers.append
    for name in _UV_ATTRIBUTES:
        accessor = attributes.get(name)
        if accessor is None:
            continue
        raw = reader.read(accessor, dtype=np.float32, copy=True)
        uv = np.asarray(raw[:, :2], dtype=np.float32)
        if not uv.flags.c_contiguous:
            uv = np.ascontiguousarray(uv)
        if flip_v:
            uv[:, 1] = 1.0 - uv[:, 1]
        append(uv)
    return layers


def _decode_color_layers(reader, attributes):
    layers = []
    append = layers.append
    for name in _COLOR_ATTRIBUTES:
        accessor = attributes.get(name)
        if accessor is None:
            continue
        raw = reader.read(accessor, dtype=np.float32)
        if raw.shape[1] == 4:
            color = np.array(raw, dtype=np.float32, order="C", copy=True)
        elif raw.shape[1] == 3:
            color = np.ones((raw.shape[0], 4), dtype=np.float32)
            color[:, :3] = raw
        else:
            raise DirectMeshImportError(f"Unsupported color accessor width {raw.shape[1]}.")
        append(color)
    return layers


def _decode_tangents(reader, accessor):
    raw = reader.read(accessor, dtype=np.float32)
    result = np.empty((raw.shape[0], 4), dtype=np.float32)
    result[:, :3] = raw[:, :3] @ _ROTATION_T
    result[:, 3] = raw[:, 3]
    return result


def _decode_submesh(
    reader,
    mesh,
    *,
    mesh_index: int,
    node_index: int,
    skin_index: int | None,
    node_matrix_gltf: np.ndarray,
    flip_v: bool,
    import_garment_support: bool,
    node_extras: dict | None = None,
) -> Submesh:
    primitives = mesh.get("primitives") or ()
    if not primitives:
        raise DirectMeshImportError(f"Mesh {mesh.get('name', 'submesh')!r} has no primitives.")
    if len(primitives) != 1:
        raise DirectMeshImportError(
            f"Mesh {mesh.get('name', 'submesh')!r} has {len(primitives)} primitives; "
            "the direct CP77 mesh path expects one primitive per submesh."
        )
    primitive = primitives[0]
    attributes = primitive.get("attributes") or {}
    position_accessor = attributes.get("POSITION")
    if position_accessor is None:
        raise DirectMeshImportError(f"Mesh {mesh.get('name', 'submesh')!r} has no POSITION accessor.")

    mesh_extras = mesh.get("extras") or {}
    name = str(mesh.get("name", "submesh"))
    positions = _rotate_vectors(reader.read(position_accessor, dtype=np.float32))

    indices_accessor = primitive.get("indices")
    if indices_accessor is None:
        if positions.shape[0] % 3:
            raise DirectMeshImportError(f"Unindexed mesh {name!r} is not a triangle list.")
        triangles = np.arange(positions.shape[0], dtype=np.int32).reshape(-1, 3)
    else:
        flat_indices = reader.read(indices_accessor, dtype=np.int32).reshape(-1)
        if flat_indices.size % 3:
            raise DirectMeshImportError(f"Mesh {name!r} index count is not divisible by three.")
        triangles = np.ascontiguousarray(flat_indices.reshape(-1, 3))

    normal_accessor = attributes.get("NORMAL")
    tangent_accessor = attributes.get("TANGENT")
    normals = (
        _rotate_vectors(reader.read(normal_accessor, dtype=np.float32))
        if normal_accessor is not None
        else None
    )
    tangents = _decode_tangents(reader, tangent_accessor) if tangent_accessor is not None else None
    joint_indices, joint_weights = _decode_skinning(reader, attributes)
    if joint_indices is not None and skin_index is None:
        raise DirectMeshImportError(
            f"Mesh {name!r} contains JOINTS/WEIGHTS attributes but its node has no skin."
        )

    return Submesh(
        name=name,
        lod=_lod_from_name(name),
        material_index=(
            int(primitive["material"])
            if primitive.get("material") is not None
            else None
        ),
        material_names=[str(value) for value in (mesh_extras.get("materialNames") or ())],
        positions=positions,
        triangles=triangles,
        normals=normals,
        tangents=tangents,
        mesh_index=mesh_index,
        node_index=node_index,
        skin_index=skin_index,
        node_matrix_gltf=np.asarray(node_matrix_gltf, dtype=np.float64),
        node_matrix_red=_red_model_matrix(node_matrix_gltf),
        uv_layers=_decode_uv_layers(reader, attributes, flip_v),
        color_layers=_decode_color_layers(reader, attributes),
        joint_indices=joint_indices,
        joint_weights=joint_weights,
        morph_targets=_decode_morph_targets(
            reader,
            primitive,
            mesh_extras,
            import_garment_support,
        ),
        mesh_extras=dict(mesh_extras),
        node_extras=dict(node_extras or {}),
    )


def decode_mesh_glb(
    filepath: str,
    *,
    flip_v: bool = True,
    build_binding: bool = True,
    import_garment_support: bool = True,
) -> DirectMeshData:
    glb = read_glb(filepath)
    document = glb.document
    reader = _MeshAccessorReader(glb)

    meshes = document.get("meshes") or ()
    if not meshes:
        raise DirectMeshImportError(f"{os.path.basename(filepath)} contains no meshes.")

    node_parents, _, node_globals = _node_hierarchy(document)
    skins = _decode_skins(reader, document, node_parents)
    instances = _mesh_instances(document, node_globals)
    nodes = document.get("nodes") or ()

    submeshes = []
    append = submeshes.append
    for mesh_index, mesh in enumerate(meshes):
        for node_index, skin_index, node_matrix_gltf in instances[mesh_index]:
            if skin_index is not None and skin_index not in skins:
                raise DirectMeshImportError(
                    f"Node {node_index} references missing skin {skin_index}."
                )
            append(
                _decode_submesh(
                    reader,
                    mesh,
                    mesh_index=mesh_index,
                    node_index=node_index,
                    skin_index=skin_index,
                    node_matrix_gltf=node_matrix_gltf,
                    flip_v=flip_v,
                    import_garment_support=import_garment_support,
                    node_extras=nodes[node_index].get("extras") or {},
                )
            )

    (
        authoritative_skin_index,
        authoritative_mesh_bind_gltf,
        authoritative_joint_bind_gltf,
        max_inverse_bind_error,
    ) = _authoritative_bind_data(submeshes, skins, node_globals)

    binding = None
    sampling_context = None
    skin_bone_names = None
    if authoritative_skin_index is not None:
        skin_bone_names = list(skins[authoritative_skin_index].bone_names)
        if build_binding:
            skin = skins[authoritative_skin_index]
            binding = SkeletonBinding(
                skin_index=skin.index,
                joint_nodes=skin.joint_nodes,
                bone_names=skin.bone_names,
                source_parent_indices=skin.parent_indices,
                topological_joint_indices=skin.topological_joint_indices,
                skin_extras=skin.extras,
            )
            sampling_context = build_sampling_context(document, binding)

    return DirectMeshData(
        source_path=os.path.abspath(filepath),
        submeshes=submeshes,
        skin_bone_names=skin_bone_names,
        skins=skins,
        binding=binding,
        sampling_context=sampling_context,
        appearance_count=max((len(item.material_names) for item in submeshes), default=0),
        authoritative_skin_index=authoritative_skin_index,
        authoritative_mesh_bind_gltf=authoritative_mesh_bind_gltf,
        authoritative_joint_bind_gltf=authoritative_joint_bind_gltf,
        max_inverse_bind_error=max_inverse_bind_error,
        document_metadata={
            key: document[key]
            for key in (
                "extras",
                "extensions",
                "extensionsUsed",
                "extensionsRequired",
                "materials",
            )
            if key in document
        },
        scene_metadata={
            key: value
            for key, value in ((document.get("scenes") or [{}])[0]).items()
            if key != "nodes"
        },
        source_generator=str((document.get("asset") or {}).get("generator", "") or ""),
    )


def _require_bpy():
    if bpy is None:
        raise RuntimeError("Blender is required to build mesh objects.")


def _loop_vertex_indices(mesh) -> np.ndarray:
    indices = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", indices)
    return indices


def _build_mesh_geometry(submesh: Submesh):
    mesh = track_created_datablock("meshes", bpy.data.meshes.new(submesh.name))
    positions = np.ascontiguousarray(submesh.positions, dtype=np.float32)
    triangles = np.ascontiguousarray(submesh.triangles, dtype=np.int32)
    vertex_count = positions.shape[0]
    triangle_count = triangles.shape[0]
    loop_count = triangle_count * 3

    mesh.vertices.add(vertex_count)
    mesh.vertices.foreach_set("co", positions.reshape(-1))
    mesh.loops.add(loop_count)
    mesh.loops.foreach_set("vertex_index", triangles.reshape(-1))
    mesh.polygons.add(triangle_count)
    mesh.polygons.foreach_set(
        "loop_start",
        np.arange(0, loop_count, 3, dtype=np.int32),
    )
    mesh.polygons.foreach_set(
        "loop_total",
        np.full(triangle_count, 3, dtype=np.int32),
    )

    mesh.update(calc_edges=True)
    geometry_changed = bool(mesh.validate(verbose=False))
    if geometry_changed:
        mesh.update(calc_edges=True)
    if len(mesh.vertices) != vertex_count:
        bpy.data.meshes.remove(mesh)
        raise DirectMeshImportError(
            f"Mesh {submesh.name!r} validation changed its vertex count; "
            "decoded vertex attributes can no longer be mapped safely."
        )

    loop_vertices = (
        _loop_vertex_indices(mesh)
        if geometry_changed or len(mesh.loops) != loop_count
        else triangles.reshape(-1)
    )
    return mesh, loop_vertices


def _apply_uv_layers(mesh, submesh, loop_vertices):
    if not submesh.uv_layers:
        return
    loop_uv = np.empty((len(loop_vertices), 2), dtype=np.float32)
    for layer_index, uv in enumerate(submesh.uv_layers):
        np.take(uv, loop_vertices, axis=0, out=loop_uv)
        layer = mesh.uv_layers.new(name=f"UVMap_{layer_index}" if layer_index else "UVMap")
        layer.uv.foreach_set("vector", loop_uv.reshape(-1))


def _apply_color_layers(mesh, submesh):
    for layer_index, color in enumerate(submesh.color_layers):
        attribute = mesh.color_attributes.new(
            name="Color" if layer_index == 0 else f"Color_{layer_index}",
            type="FLOAT_COLOR",
            domain="POINT",
        )
        attribute.data.foreach_set("color", np.ascontiguousarray(color).reshape(-1))


def _apply_custom_normals(mesh, submesh):
    if submesh.normals is None or not hasattr(mesh, "normals_split_custom_set_from_vertices"):
        return
    polygon_count = len(mesh.polygons)
    if polygon_count:
        mesh.polygons.foreach_set(
            "use_smooth",
            np.ones(polygon_count, dtype=np.bool_),
        )
    mesh.normals_split_custom_set_from_vertices(
        np.ascontiguousarray(submesh.normals, dtype=np.float32)
    )


def _apply_source_frame_attributes(mesh, submesh):
    if submesh.normals is not None:
        attribute = mesh.attributes.new(
            name=_SOURCE_NORMAL_ATTRIBUTE,
            type="FLOAT_VECTOR",
            domain="POINT",
        )
        attribute.data.foreach_set(
            "vector",
            np.ascontiguousarray(submesh.normals, dtype=np.float32).reshape(-1),
        )
    if submesh.tangents is not None:
        tangent = mesh.attributes.new(
            name=_SOURCE_TANGENT_ATTRIBUTE,
            type="FLOAT_VECTOR",
            domain="POINT",
        )
        tangent.data.foreach_set(
            "vector",
            np.ascontiguousarray(submesh.tangents[:, :3], dtype=np.float32).reshape(-1),
        )
        sign = mesh.attributes.new(
            name=_SOURCE_TANGENT_SIGN_ATTRIBUTE,
            type="FLOAT",
            domain="POINT",
        )
        sign.data.foreach_set(
            "value",
            np.ascontiguousarray(submesh.tangents[:, 3], dtype=np.float32),
        )


def _resolve_target_bone_name(armature, source_name):
    if armature is None:
        return None
    pose_bones = armature.pose.bones
    if pose_bones.get(source_name) is not None:
        return source_name
    mapped = merged_bone_name(source_name)
    return mapped if pose_bones.get(mapped) is not None else None


def _aggregate_deform_weights(joints, weights, source_to_group):
    joints = np.asarray(joints, dtype=np.int32)
    weights = np.asarray(weights, dtype=np.float32)
    source_to_group = np.asarray(source_to_group, dtype=np.int32)
    if joints.shape != weights.shape:
        raise DirectMeshImportError(
            f"Joint and weight arrays have different shapes: {joints.shape} != {weights.shape}."
        )

    finite = np.isfinite(weights)
    positive = finite & (weights > _WEIGHT_EPSILON)
    invalid_weight_count = int(np.count_nonzero((~finite) | (weights < -_WEIGHT_EPSILON)))
    in_range = (joints >= 0) & (joints < len(source_to_group))
    valid_source = positive & in_range
    invalid_influence_count = invalid_weight_count + int(
        np.count_nonzero(positive & ~in_range)
    )

    mapped = np.full(joints.shape, -1, dtype=np.int32)
    mapped[valid_source] = source_to_group[joints[valid_source]]
    unmapped = valid_source & (mapped < 0)
    usable = valid_source & (mapped >= 0)
    if not np.any(usable):
        audit = SkinningAudit(
            invalid_influence_count=invalid_influence_count,
            unmapped_influence_count=int(np.count_nonzero(unmapped)),
            zero_weight_vertex_count=int(joints.shape[0]),
        )
        empty_i = np.empty(0, dtype=np.int32)
        empty_w = np.empty(0, dtype=np.float32)
        return empty_i, empty_i, empty_w, audit

    vertex_grid = np.broadcast_to(
        np.arange(joints.shape[0], dtype=np.int64)[:, np.newaxis],
        joints.shape,
    )
    vertex_indices = vertex_grid[usable]
    group_indices = mapped[usable].astype(np.int64, copy=False)
    usable_weights = weights[usable].astype(np.float64, copy=False)

    stride = int(np.max(group_indices)) + 1
    keys = vertex_indices * stride + group_indices
    order = np.argsort(keys, kind="stable")
    sorted_keys = keys[order]
    sorted_weights = usable_weights[order]
    unique_keys, reduce_starts = np.unique(sorted_keys, return_index=True)
    summed_weights = np.add.reduceat(sorted_weights, reduce_starts)

    aggregate_vertices = (unique_keys // stride).astype(np.int32)
    aggregate_groups = (unique_keys % stride).astype(np.int32)
    duplicate_count = int(len(keys) - len(unique_keys))

    positive_sums = summed_weights > _WEIGHT_EPSILON
    aggregate_vertices = aggregate_vertices[positive_sums]
    aggregate_groups = aggregate_groups[positive_sums]
    summed_weights = summed_weights[positive_sums]

    totals = np.bincount(
        aggregate_vertices,
        weights=summed_weights,
        minlength=joints.shape[0],
    )
    surviving = totals[aggregate_vertices] > _WEIGHT_EPSILON
    aggregate_vertices = aggregate_vertices[surviving]
    aggregate_groups = aggregate_groups[surviving]
    summed_weights = summed_weights[surviving]
    normalized_weights = (
        summed_weights / totals[aggregate_vertices]
    ).astype(np.float32)

    zero_weight_vertices = int(
        np.count_nonzero(totals <= _WEIGHT_EPSILON)
    )
    audit = SkinningAudit(
        invalid_influence_count=invalid_influence_count,
        unmapped_influence_count=int(np.count_nonzero(unmapped)),
        duplicate_influence_count=duplicate_count,
        zero_weight_vertex_count=zero_weight_vertices,
        valid_influence_count=len(normalized_weights),
    )
    return aggregate_vertices, aggregate_groups, normalized_weights, audit


def _prepare_vertex_groups(obj, submesh, skin, armature):
    joints = submesh.joint_indices
    weights = submesh.joint_weights
    if joints is None or weights is None:
        return None

    positive = np.isfinite(weights) & (weights > _WEIGHT_EPSILON)
    in_range = (joints >= 0) & (joints < len(skin.bone_names))
    invalid_positive_count = int(np.count_nonzero(positive & ~in_range))
    if invalid_positive_count:
        raise DirectMeshImportError(
            f"Skinned mesh {submesh.name!r} contains "
            f"{invalid_positive_count} positive influences with invalid joint indices."
        )
    used_source_indices = np.unique(joints[positive & in_range])

    source_to_group = np.full(len(skin.bone_names), -1, dtype=np.int32)
    unmapped_bones = []
    resolved_groups = []
    for source_index_value in used_source_indices:
        source_index = int(source_index_value)
        source_name = skin.bone_names[source_index]
        target_name = _resolve_target_bone_name(armature, source_name)
        if target_name is None:
            unmapped_bones.append(source_name)
            continue
        resolved_groups.append((source_index, target_name))

    if unmapped_bones:
        raise DirectMeshImportError(
            f"Skinned mesh {submesh.name!r} references weighted bones that "
            "do not exist on the destination armature: "
            + ", ".join(unmapped_bones[:16])
        )

    for source_index, target_name in resolved_groups:
        group = obj.vertex_groups.get(target_name) or obj.vertex_groups.new(
            name=target_name
        )
        source_to_group[source_index] = group.index

    vertices, groups, normalized, audit = _aggregate_deform_weights(
        joints,
        weights,
        source_to_group,
    )
    audit.unmapped_bones = tuple(unmapped_bones)
    return vertices, groups, normalized, audit


def _write_deform_weights(obj, vertices, groups, weights):
    if not len(weights):
        return False

    if bmesh is None:
        for vertex_index, group_index, weight in zip(vertices, groups, weights):
            obj.vertex_groups[int(group_index)].add(
                (int(vertex_index),),
                float(weight),
                "REPLACE",
            )
        return False

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        deform_layer = bm.verts.layers.deform.verify()
        current_vertex = -1
        deform = None
        for vertex_index, group_index, weight in zip(vertices, groups, weights):
            vertex_index = int(vertex_index)
            if vertex_index != current_vertex:
                current_vertex = vertex_index
                deform = bm.verts[vertex_index][deform_layer]
            deform[int(group_index)] = float(weight)
        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()
    return True


def _apply_vertex_groups(obj, submesh, skin, armature):
    prepared = _prepare_vertex_groups(obj, submesh, skin, armature)
    if prepared is None:
        return False, SkinningAudit()
    vertices, groups, weights, audit = prepared
    topology_rebuilt = _write_deform_weights(obj, vertices, groups, weights)
    return topology_rebuilt, audit


def _apply_shape_keys(obj, submesh):
    if not submesh.morph_targets:
        return
    basis = obj.shape_key_add(name="Basis", from_mix=False)
    basis.value = 0.0
    work = np.empty_like(submesh.positions, dtype=np.float32)
    for name, delta in submesh.morph_targets:
        np.add(submesh.positions, delta, out=work)
        key = obj.shape_key_add(name=name, from_mix=False)
        key.data.foreach_set("co", work.reshape(-1))
        key.value = 0.0


def reset_shape_key_values(objects):
    for obj in objects:
        mesh = getattr(obj, "data", None)
        shape_keys = getattr(mesh, "shape_keys", None)
        if shape_keys is None:
            continue
        for key in shape_keys.key_blocks:
            key.value = 0.0


def _finish_submesh_object(obj, submesh, loop_vertices):
    mesh = obj.data
    _apply_uv_layers(mesh, submesh, loop_vertices)
    _apply_color_layers(mesh, submesh)
    _apply_shape_keys(obj, submesh)
    _apply_custom_normals(mesh, submesh)
    _apply_source_frame_attributes(mesh, submesh)
    mesh.update()


def _new_submesh_object(submesh: Submesh):
    mesh, loop_vertices = _build_mesh_geometry(submesh)
    return (
        track_created_datablock(
            "objects", bpy.data.objects.new(submesh.name, mesh)
        ),
        loop_vertices,
    )


def build_submesh_object(submesh: Submesh, *, collection=None):
    """Construct and link one Blender mesh object from decoded NumPy buffers."""
    _require_bpy()
    obj, loop_vertices = _new_submesh_object(submesh)
    _set_object_bind_transform(obj, submesh, None)
    _finish_submesh_object(obj, submesh, loop_vertices)
    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def _expected_bind_bone_matrices(mesh_data: DirectMeshData):
    joint_bind = mesh_data.authoritative_joint_bind_gltf
    skin_index = mesh_data.authoritative_skin_index
    if joint_bind is None or skin_index is None:
        return None, None
    skin = mesh_data.skins[skin_index]
    matrices = np.matmul(
        np.matmul(_GLTF_TO_RED_4[np.newaxis, :, :], joint_bind),
        _GLTF_TO_BONE_RIGHT_4[np.newaxis, :, :],
    )
    return skin, matrices


def _armature_bind_error(armature, skin, expected_matrices):
    maximum = 0.0
    missing = []
    for source_name, expected in zip(skin.bone_names, expected_matrices):
        target_name = _resolve_target_bone_name(armature, source_name)
        if target_name is None:
            missing.append(source_name)
            continue
        actual = np.asarray(
            armature.data.bones[target_name].matrix_local,
            dtype=np.float64,
        )
        maximum = max(maximum, float(np.max(np.abs(actual - expected))))
    return maximum, tuple(missing)


def _bind_failure_detail(armature, skin, expected_matrices):
    """Explain why an inverse-bind rest pose could not be satisfied.

    Edit bones store head, tail and roll in float32 and cannot store scale or shear, so
    an unreachable target is one of two things: a non-rigid expected matrix, whose scale
    is discarded by the assignment, or a bone too short to carry its own orientation
    because matrix_local's Y axis is recovered as (tail - head) / length and the
    endpoint rounding error therefore scales as ulp(|head|) / length.
    """
    basis = expected_matrices[:, :3, :3]
    u, singular, vt = np.linalg.svd(basis)
    residual = np.max(np.abs(basis - np.matmul(u, vt)), axis=(1, 2))
    scale_deviation = np.max(np.abs(singular - 1.0), axis=1)

    heads = expected_matrices[:, :3, 3]
    magnitude = np.maximum(np.max(np.abs(heads), axis=1), 1.0e-6)
    ulp = np.spacing(magnitude.astype(np.float32)).astype(np.float64)
    required_length = 2.0 * ulp / _BIND_MATRIX_TOLERANCE

    lines = []
    short = []
    for index, source_name in enumerate(skin.bone_names):
        target_name = _resolve_target_bone_name(armature, source_name)
        if target_name is None:
            continue
        bone = armature.data.bones[target_name]
        length = float(bone.length)
        error = float(
            np.max(
                np.abs(
                    np.asarray(bone.matrix_local, dtype=np.float64)
                    - expected_matrices[index]
                )
            )
        )
        if error <= _BIND_MATRIX_TOLERANCE:
            continue
        lines.append((error, source_name, length, float(required_length[index]),
                      float(residual[index]), float(scale_deviation[index])))
        if length < required_length[index]:
            short.append(source_name)

    lines.sort(reverse=True)
    non_rigid = [name for _, name, _, _, res, _ in lines if res > _BIND_MATRIX_TOLERANCE]

    report = []
    if short:
        report.append(
            f"{len(short)} joint(s) are shorter than float32 head/tail can carry at "
            "this tolerance; lengthen them using the rig reader's "
            "_precision_safe_bone_length contract."
        )
    if non_rigid:
        report.append(
            f"{len(non_rigid)} joint(s) have non-rigid bind matrices (scale or shear) "
            f"that an edit bone cannot represent."
        )
    if not report:
        report.append(
            "No joint is short or non-rigid; the residual is likely roll quantization."
        )
    for error, name, length, needed, _, scale in lines[:8]:
        report.append(
            f"  {name}: error {error:.6g}, length {length:.6g} "
            f"(needs {needed:.6g}), scale dev {scale:.6g}"
        )
    return "\n".join(report)


def _set_created_armature_bind_pose(armature, skin, expected_matrices):
    maximum, missing = _armature_bind_error(armature, skin, expected_matrices)
    if missing:
        raise DirectMeshImportError(
            "Created armature is missing skin joints: " + ", ".join(missing[:8])
        )
    if maximum <= _BIND_MATRIX_TOLERANCE:
        return maximum, False

    from ..rig import set_armature_model_space_matrices

    target_names = []
    for source_name in skin.bone_names:
        target_name = _resolve_target_bone_name(armature, source_name)
        if target_name is None:
            raise DirectMeshImportError(
                f"Created armature is missing edit bone for {source_name!r}."
            )
        target_names.append(target_name)

    set_armature_model_space_matrices(
        armature,
        target_names,
        expected_matrices,
    )

    corrected_error, missing = _armature_bind_error(
        armature,
        skin,
        expected_matrices,
    )
    if missing:
        raise DirectMeshImportError(
            "Created armature is missing skin joints after correction: "
            + ", ".join(missing[:8])
        )
    if corrected_error > _BIND_MATRIX_HARD_LIMIT:
        detail = _bind_failure_detail(armature, skin, expected_matrices)
        raise DirectMeshImportError(
            f"Authoritative inverse-bind rest pose is unusable "
            f"(max error {corrected_error:.6g}, limit {_BIND_MATRIX_HARD_LIMIT:.6g}).\n"
            + detail
        )
    if corrected_error > _BIND_MATRIX_TOLERANCE:
        print(
            f"[CP77 Direct Mesh] Rest pose applied within {corrected_error:.6g} "
            f"(clean tolerance {_BIND_MATRIX_TOLERANCE:.6g}); continuing.\n"
            + _bind_failure_detail(armature, skin, expected_matrices)
        )
    return corrected_error, True


def _authoritative_source_rest_snapshot(armature, skin, global_matrices):
    relative = np.empty_like(global_matrices)
    for joint_index in skin.topological_joint_indices:
        parent_index = skin.parent_indices[joint_index]
        relative[joint_index] = (
            global_matrices[joint_index]
            if parent_index < 0
            else np.linalg.inv(global_matrices[parent_index])
            @ global_matrices[joint_index]
        )

    snapshot = {
        "version": 2,
        "space": SOURCE_REST_SPACE_CONTRACT,
        "boneNames": list(skin.bone_names),
        "matrices": relative.reshape(len(relative), 16).tolist(),
    }
    target_matrices = []
    for source_name in skin.bone_names:
        target_name = _resolve_target_bone_name(armature, source_name)
        if target_name is None:
            target_matrices = []
            break
        target_matrices.append(
            np.asarray(
                armature.data.bones[target_name].matrix_local,
                dtype=np.float64,
            )
        )
    if target_matrices:
        snapshot["targetMatrices"] = np.asarray(
            target_matrices, dtype=np.float64
        ).reshape(len(target_matrices), 16).tolist()
    return snapshot


def _store_authoritative_source_rest(armature, skin, global_matrices):
    snapshot = _authoritative_source_rest_snapshot(
        armature, skin, global_matrices
    )
    armature[_MESH_SOURCE_REST_SNAPSHOT_KEY] = json.dumps(
        snapshot,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return snapshot


def _configure_armature_bind_pose(mesh_data, armature, created_armature):
    skin, expected = _expected_bind_bone_matrices(mesh_data)
    if skin is None:
        return 0.0, False, ()

    if created_armature:
        error, corrected = _set_created_armature_bind_pose(
            armature,
            skin,
            expected,
        )
        _store_authoritative_source_rest(
            armature,
            skin,
            expected,
        )
        missing = ()
    else:
        error, missing = _armature_bind_error(armature, skin, expected)
        corrected = False

    armature["cp77_inverse_bind_source_error"] = float(
        mesh_data.max_inverse_bind_error
    )
    armature["cp77_target_bind_error"] = float(error)
    armature["cp77_bind_pose_corrected"] = bool(corrected)
    return error, corrected, missing


def _set_object_bind_transform(obj, submesh, armature):
    matrix = Matrix(
        tuple(
            tuple(float(value) for value in row)
            for row in submesh.node_matrix_red
        )
    )
    if armature is None:
        obj.matrix_world = matrix
        return
    obj.parent = armature
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_basis = matrix


def _resolve_armature(mesh_data: DirectMeshData, armature):
    if armature is not None:
        return armature
    if not mesh_data.is_skinned:
        return None
    if mesh_data.binding is None or mesh_data.sampling_context is None:
        raise DirectMeshImportError("A skinned mesh requires a decoded skeleton binding.")
    skin, expected_matrices = _expected_bind_bone_matrices(mesh_data)
    if skin is None or expected_matrices is None:
        raise DirectMeshImportError(
            "A skinned mesh has no authoritative inverse-bind rest pose."
        )
    return build_rest_armature_from_binding(
        mesh_data.binding,
        mesh_data.sampling_context,
        source_label=mesh_data.source_path,
        assign_shapes=False,
        model_space_matrices=expected_matrices,
    )


def _collection_name_from_filepath(filepath: str) -> str:
    name = os.path.splitext(os.path.basename(filepath))[0]
    return name or "CP77_Mesh"


def _new_import_collection(filepath: str):
    collection = track_created_datablock(
        "collections",
        bpy.data.collections.new(_collection_name_from_filepath(filepath)),
    )
    bpy.context.scene.collection.children.link(collection)
    return collection


def _move_object_to_collection(obj, collection):
    if collection.objects.get(obj.name) is None:
        collection.objects.link(obj)
    for current in tuple(obj.users_collection):
        if current is not collection:
            current.objects.unlink(obj)


def _select_imported_objects(objects, active=None):
    for selected in tuple(bpy.context.selected_objects):
        selected.select_set(False)
    for obj in objects:
        obj.select_set(True)
    if active is not None:
        bpy.context.view_layer.objects.active = active


def _store_json_property(idblock, key, value):
    idblock[key] = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _source_skin_binding_snapshot(skin):
    return {
        "version": 1,
        "boneNames": list(skin.bone_names),
        "boneParentIndexes": [int(value) for value in skin.parent_indices],
    }


def _finalize_import_collection(
    collection,
    filepath,
    mesh_objects,
    armature,
    audits,
    mesh_data,
):
    collection["orig_filepath"] = os.path.abspath(filepath)
    mark_origin(
        collection,
        ORIGIN_PLUGIN,
        generator=mesh_data.source_generator,
        source_path=filepath,
    )
    collection["numMeshChildren"] = len(mesh_objects)
    collection["numArmatureChildren"] = int(armature is not None)
    collection["cp77_invalid_skin_influences"] = sum(
        audit.invalid_influence_count for audit in audits
    )
    collection["cp77_unmapped_skin_influences"] = sum(
        audit.unmapped_influence_count for audit in audits
    )
    collection["cp77_duplicate_skin_influences"] = sum(
        audit.duplicate_influence_count for audit in audits
    )
    collection["cp77_zero_weight_vertices"] = sum(
        audit.zero_weight_vertex_count for audit in audits
    )
    collection["cp77_inverse_bind_max_error"] = float(
        mesh_data.max_inverse_bind_error
    )
    _store_json_property(
        collection,
        _SOURCE_DOCUMENT_METADATA_KEY,
        mesh_data.document_metadata,
    )
    _store_json_property(
        collection,
        _SOURCE_SCENE_METADATA_KEY,
        mesh_data.scene_metadata,
    )
    if mesh_data.authoritative_skin_index is not None:
        _store_json_property(
            collection,
            _SOURCE_SKIN_BINDING_KEY,
            _source_skin_binding_snapshot(
                mesh_data.skins[mesh_data.authoritative_skin_index]
            ),
        )


def _import_mesh_glb_impl(
    filepath: str,
    armature=None,
    *,
    appearance_index: int = 0,
    flip_v: bool = True,
    collection=None,
    import_garment_support: bool = True,
    hide_armature: bool = False,
):
    """Import a WolvenKit mesh GLB with authoritative glTF skin binding."""
    _require_bpy()

    mesh_data = decode_mesh_glb(
        filepath,
        flip_v=flip_v,
        build_binding=armature is None,
        import_garment_support=import_garment_support,
    )
    resolved_armature = _resolve_armature(mesh_data, armature)
    target_collection = collection or _new_import_collection(filepath)
    created_armature = armature is None and resolved_armature is not None

    bind_error = 0.0
    bind_corrected = False
    missing_bind_bones = ()
    source_rest_snapshot = None
    if resolved_armature is not None:
        bind_error, bind_corrected, missing_bind_bones = (
            _configure_armature_bind_pose(
                mesh_data,
                resolved_armature,
                created_armature,
            )
        )
        source_skin, source_bind_matrices = _expected_bind_bone_matrices(mesh_data)
        if source_skin is not None and source_bind_matrices is not None:
            source_rest_snapshot = _authoritative_source_rest_snapshot(
                resolved_armature,
                source_skin,
                source_bind_matrices,
            )
            _store_json_property(
                target_collection,
                _MESH_SOURCE_REST_SNAPSHOT_KEY,
                source_rest_snapshot,
            )

    if created_armature:
        mark_origin(
            resolved_armature,
            ORIGIN_PLUGIN,
            generator=mesh_data.source_generator,
            source_path=filepath,
        )
        resolved_armature.name = f"Armature__{target_collection.name}"
        _move_object_to_collection(resolved_armature, target_collection)
        resolved_armature.hide_set(bool(hide_armature))

    created = []
    audits = []
    for submesh in mesh_data.submeshes:
        obj, loop_vertices = _new_submesh_object(submesh)
        _set_object_bind_transform(obj, submesh, resolved_armature)

        audit = SkinningAudit()
        if submesh.joint_indices is not None:
            if resolved_armature is None or submesh.skin_index is None:
                bpy.data.objects.remove(obj, do_unlink=True)
                raise DirectMeshImportError(
                    f"Skinned mesh {submesh.name!r} has no destination armature."
                )
            skin = mesh_data.skins[submesh.skin_index]
            topology_rebuilt, audit = _apply_vertex_groups(
                obj,
                submesh,
                skin,
                resolved_armature,
            )
            if topology_rebuilt:
                loop_vertices = _loop_vertex_indices(obj.data)
            modifier = obj.modifiers.new(name="Armature", type="ARMATURE")
            modifier.object = resolved_armature

        _finish_submesh_object(obj, submesh, loop_vertices)
        mark_origin(
            obj,
            ORIGIN_PLUGIN,
            generator=mesh_data.source_generator,
            source_path=filepath,
        )
        _store_json_property(obj, _SOURCE_MESH_EXTRAS_KEY, submesh.mesh_extras)
        _store_json_property(obj, _SOURCE_NODE_EXTRAS_KEY, submesh.node_extras)
        _store_json_property(
            obj,
            _SOURCE_DOCUMENT_METADATA_KEY,
            mesh_data.document_metadata,
        )
        _store_json_property(
            obj,
            _SOURCE_SCENE_METADATA_KEY,
            mesh_data.scene_metadata,
        )
        if submesh.material_index is not None:
            obj[_SOURCE_MATERIAL_INDEX_KEY] = int(submesh.material_index)
        if submesh.skin_index is not None:
            skin = mesh_data.skins[submesh.skin_index]
            _store_json_property(
                obj,
                _SOURCE_SKIN_EXTRAS_KEY,
                skin.extras,
            )
            _store_json_property(
                obj,
                _SOURCE_SKIN_BINDING_KEY,
                _source_skin_binding_snapshot(skin),
            )
            if source_rest_snapshot is not None:
                _store_json_property(
                    obj,
                    _MESH_SOURCE_REST_SNAPSHOT_KEY,
                    source_rest_snapshot,
                )
        if 0 <= appearance_index < len(submesh.material_names):
            obj["cp77_material_name"] = submesh.material_names[appearance_index]
        obj["cp77_lod"] = submesh.lod
        obj["cp77_skin_invalid_influences"] = audit.invalid_influence_count
        obj["cp77_skin_unmapped_influences"] = audit.unmapped_influence_count
        obj["cp77_skin_duplicate_influences"] = audit.duplicate_influence_count
        obj["cp77_skin_zero_weight_vertices"] = audit.zero_weight_vertex_count
        target_collection.objects.link(obj)
        created.append(obj)
        audits.append(audit)

        if (
            audit.invalid_influence_count
            or audit.unmapped_influence_count
            or audit.duplicate_influence_count
            or audit.zero_weight_vertex_count
        ):
            details = []
            if audit.invalid_influence_count:
                details.append(f"{audit.invalid_influence_count} invalid")
            if audit.unmapped_influence_count:
                details.append(f"{audit.unmapped_influence_count} unmapped")
            if audit.duplicate_influence_count:
                details.append(f"{audit.duplicate_influence_count} duplicates consolidated")
            if audit.zero_weight_vertex_count:
                details.append(f"{audit.zero_weight_vertex_count} zero-weight vertices")
            print(f"[CP77 Direct Mesh] {obj.name}: " + ", ".join(details))
            if audit.unmapped_bones:
                print(
                    "[CP77 Direct Mesh] Unmapped bones: "
                    + ", ".join(audit.unmapped_bones[:16])
                )

    _finalize_import_collection(
        target_collection,
        filepath,
        created,
        resolved_armature if created_armature else None,
        audits,
        mesh_data,
    )
    reset_shape_key_values(created)

    if mesh_data.max_inverse_bind_error > _BIND_MATRIX_TOLERANCE:
        print(
            f"[CP77 Direct Mesh] Inverse-bind/node-rest disagreement: "
            f"{mesh_data.max_inverse_bind_error:.6g}; "
            + ("created armature rest corrected." if bind_corrected else "target armature retained.")
        )
    if missing_bind_bones:
        print(
            "[CP77 Direct Mesh] Target armature is missing bind bones: "
            + ", ".join(missing_bind_bones[:16])
        )

    all_objects = ([resolved_armature] if created_armature else []) + created
    selectable = [obj for obj in all_objects if not obj.hide_get()]
    active = (
        resolved_armature
        if created_armature and not resolved_armature.hide_get()
        else (created[0] if created else None)
    )
    _select_imported_objects(selectable, active=active)

    return {
        "objects": created,
        "all_objects": all_objects,
        "armature": resolved_armature,
        "collection": target_collection,
        "mesh_data": mesh_data,
        "skin_audits": audits,
        "target_bind_error": bind_error,
        "bind_pose_corrected": bind_corrected,
        "missing_bind_bones": missing_bind_bones,
    }


def import_mesh_glb(
    filepath: str,
    armature=None,
    *,
    appearance_index: int = 0,
    flip_v: bool = True,
    collection=None,
    import_garment_support: bool = True,
    hide_armature: bool = False,
    transaction=None,
):
    _require_bpy()
    active = current_import_transaction()
    if transaction is not None and active not in (None, transaction):
        raise RuntimeError("Mesh import transaction conflicts with active transaction")
    owner = transaction or active
    owns_transaction = owner is None
    if owner is None:
        owner = DatablockImportTransaction()
    armature_properties = _snapshot_id_properties(armature)
    collection_properties = _snapshot_id_properties(collection)
    scope = owner.scope() if active is not owner else None
    try:
        if scope is None:
            result = _import_mesh_glb_impl(
                filepath,
                armature,
                appearance_index=appearance_index,
                flip_v=flip_v,
                collection=collection,
                import_garment_support=import_garment_support,
                hide_armature=hide_armature,
            )
        else:
            with scope:
                result = _import_mesh_glb_impl(
                    filepath,
                    armature,
                    appearance_index=appearance_index,
                    flip_v=flip_v,
                    collection=collection,
                    import_garment_support=import_garment_support,
                    hide_armature=hide_armature,
                )
    except Exception as error:
        report = owner.rollback() if owns_transaction else None
        _restore_id_properties(armature, armature_properties)
        _restore_id_properties(collection, collection_properties)
        rollback_error = rollback_report_message(report)
        if rollback_error:
            raise RuntimeError(
                f"{error}; rollback incomplete: {rollback_error}"
            ) from error
        raise
    if owns_transaction:
        owner.commit()
    return result
