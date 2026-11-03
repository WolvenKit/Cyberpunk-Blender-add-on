from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np

from ...assetio.values import coerce_int
from ...bartmoss.geometry import isolate_repeated_triangle_faces
from ...gltf.accessors import GLTFAccessorReader
from ...gltf.container import GLBContainerError, read_gltf_container
from ...gltf.garment_support import (
    GARMENT_SUPPORT_MORPH,
    canonical_garment_attribute,
    is_garment_attribute,
)
from ...gltf.mesh_contract import (
    COLOR_ATTRIBUTES,
    JOINT_ATTRIBUTES,
    UV_ATTRIBUTES,
    WEIGHT_ATTRIBUTES,
    validate_direct_extensions,
    validate_mesh_arrays,
    validate_primitive_accessors,
)
from ...gltf.nodes import node_reference
from ...gltf.skeleton import (
    SamplingContext,
    SkeletonBinding,
    build_node_hierarchy,
    build_sampling_context,
    build_skeleton_binding,
)
from ...redSpace.tangent import convert_wolvenkit_tangent_sign
from ...redSpace.transforms import gltf_matrix_to_red, gltf_vectors_to_red
from ...redSpace.uv import convert_wolvenkit_uv_channel

BIND_MATRIX_TOLERANCE = 5.0e-5

_FRAME_EPSILON = 1.0e-12
_WEIGHT_TOLERANCE = 1.0e-5
_REPAIR_LABELS = {
    "normals": "degenerate normal(s) rebuilt from adjacent faces",
    "tangents": "degenerate tangent(s) rebuilt perpendicular to the normal",
    "tangent_signs": "tangent handedness value(s) snapped to +/-1",
    "invalid_joints": "influence(s) on joints outside the skin cleared",
    "negative_weights": "negative weight(s) cleared",
    "renormalized_weights": "vertex weight set(s) renormalized",
    "unweighted": "skinned vertex(es) without weights left unassigned",
    "uvs": "non-finite UV(s) set to 0",
}


class DirectMeshImportError(RuntimeError):
    pass


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
    uv_layers: list[tuple[int, np.ndarray]] = field(default_factory=list)
    color_layers: list[tuple[int, np.ndarray]] = field(default_factory=list)
    custom_colors: list[tuple[str, np.ndarray]] = field(default_factory=list)
    joint_indices: np.ndarray | None = None
    joint_weights: np.ndarray | None = None
    skinning_warning: str = ""
    morph_targets: list[tuple[str, np.ndarray]] = field(default_factory=list)
    morph_normals: list[tuple[str, np.ndarray]] = field(default_factory=list)
    morph_tangents: list[tuple[str, np.ndarray]] = field(default_factory=list)
    mesh_extras: dict = field(default_factory=dict)
    node_extras: dict = field(default_factory=dict)
    source_vertex_indices: np.ndarray | None = None
    repairs: dict[str, int] = field(default_factory=dict)

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

    @property
    def is_skinned(self) -> bool:
        return self.authoritative_skin_index is not None

    @property
    def repair_warning(self) -> str:
        totals = {}
        for submesh in self.submeshes:
            for key, count in submesh.repairs.items():
                totals[key] = totals.get(key, 0) + count
        details = [
            f"{totals[key]} {label}"
            for key, label in _REPAIR_LABELS.items()
            if totals.get(key)
        ]
        if not details:
            return ""
        return (
            f"{os.path.basename(self.source_path)}: imported with repaired "
            f"vertex data ({', '.join(details)})"
        )


def _lod_from_name(name: str) -> int:
    marker_position = name.rfind("_LOD_")
    if marker_position < 0:
        return 1
    return coerce_int(name[marker_position + 5 :], 1, unwrap=False)


def _rotate_vectors(values) -> np.ndarray:
    source = np.asarray(values)
    if source.ndim != 2 or source.shape[1] < 3:
        raise DirectMeshImportError(
            f"Expected an Nx3 vector accessor, got {source.shape}."
        )
    return np.asarray(gltf_vectors_to_red(source), dtype=np.float32)


def _decode_inverse_bind_matrices(reader, skin, joint_count):
    accessor = skin.get("inverseBindMatrices")
    if accessor is None:
        return np.repeat(
            np.eye(4, dtype=np.float64)[np.newaxis, :, :],
            joint_count,
            axis=0,
        ), False

    raw = reader.read(accessor, dtype=np.float64)
    layout = reader.accessors[accessor]
    if (
        layout.get("type") != "MAT4"
        or layout.get("componentType") != 5126
        or layout.get("normalized", False)
        or raw.shape != (joint_count, 16)
    ):
        raise DirectMeshImportError(
            "Skin inverseBindMatrices count does not match the joint table."
        )
    matrices = raw.reshape(joint_count, 4, 4).transpose(0, 2, 1).copy()
    return matrices, True


def _decode_skins(reader, document, hierarchy):
    decoded = {}
    for skin_index, skin in enumerate(document.get("skins") or ()):
        binding = build_skeleton_binding(document, hierarchy, skin_index)
        inverse_bind_matrices, has_inverse_bind_matrices = (
            _decode_inverse_bind_matrices(reader, skin, len(binding.joint_nodes))
        )
        decoded[skin_index] = SkinData(
            index=skin_index,
            joint_nodes=binding.joint_nodes,
            bone_names=binding.bone_names,
            parent_indices=binding.source_parent_indices,
            topological_joint_indices=binding.topological_joint_indices,
            inverse_bind_matrices_gltf=inverse_bind_matrices,
            inverse_bind_matrices_red=gltf_matrix_to_red(inverse_bind_matrices),
            has_inverse_bind_matrices=has_inverse_bind_matrices,
            extras=binding.skin_extras,
        )
    return decoded


def _mesh_instances(document, node_globals):
    meshes = document.get("meshes") or ()
    instances = [[] for _ in meshes]
    for node_index, node in enumerate(document.get("nodes") or ()):
        mesh_value = node.get("mesh")
        if mesh_value is None:
            continue
        mesh_index = node_reference(mesh_value, len(meshes), f"Node {node_index} mesh")
        skin_value = node.get("skin")
        skin_index = (
            None
            if skin_value is None
            else node_reference(
                skin_value, len(document.get("skins") or ()), f"Node {node_index} skin"
            )
        )
        instances[mesh_index].append(
            (node_index, skin_index, node_globals[node_index].copy())
        )

    identity = np.eye(4, dtype=np.float64)
    for mesh_index, values in enumerate(instances):
        if not values:
            values.append((-1, None, identity.copy()))
    return instances


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
            atol=BIND_MATRIX_TOLERANCE,
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
        raise DirectMeshImportError(
            "Skinning accessor blocks have inconsistent vertex counts."
        )
    return np.ascontiguousarray(np.concatenate(arrays, axis=1))


def _decode_skinning(reader, attributes):
    joint_blocks = tuple(
        index for index, name in enumerate(JOINT_ATTRIBUTES) if name in attributes
    )
    weight_blocks = tuple(
        index for index, name in enumerate(WEIGHT_ATTRIBUTES) if name in attributes
    )
    if not joint_blocks and not weight_blocks:
        return None, None
    if joint_blocks != weight_blocks:
        raise DirectMeshImportError(
            f"Skinning JOINTS/WEIGHTS blocks differ: {joint_blocks} vs {weight_blocks}."
        )

    joints = _read_blocks(reader, attributes, JOINT_ATTRIBUTES, np.int32)
    weights = _read_blocks(reader, attributes, WEIGHT_ATTRIBUTES, np.float32)
    weights = np.ascontiguousarray(weights, dtype=np.float32)
    if joints.shape != weights.shape:
        raise DirectMeshImportError(
            f"Skinning joint/weight shapes differ: {joints.shape} vs {weights.shape}."
        )
    return joints, weights


def _decode_morph_targets(
    reader, primitive, mesh_extras, import_garment_support, vertex_count
):
    targets = primitive.get("targets") or ()
    names = mesh_extras.get("targetNames")
    if names is not None and (
        not isinstance(names, list)
        or len(names) != len(targets)
        or not all(isinstance(name, str) and name for name in names)
        or len(set(names)) != len(names)
    ):
        raise DirectMeshImportError(
            "Morph targetNames must uniquely name every target in order."
        )
    positions, normals, tangents = [], [], []
    for index, target in enumerate(targets):
        name = names[index] if names is not None else f"morph_{index}"
        if (
            not import_garment_support
            and name.casefold() == GARMENT_SUPPORT_MORPH.casefold()
        ):
            continue
        channels = {}
        for semantic in ("POSITION", "NORMAL", "TANGENT"):
            accessor_index = target.get(semantic)
            if accessor_index is None:
                continue
            values = reader.read(accessor_index, dtype=np.float32)
            accessor = reader.accessors[accessor_index]
            if (
                values.shape != (vertex_count, 3)
                or accessor.get("componentType") != 5126
                or accessor.get("normalized", False)
                or not np.all(np.isfinite(values))
            ):
                raise DirectMeshImportError(
                    f"Morph {name!r} {semantic} must contain finite FLOAT VEC3 deltas for every vertex."
                )
            channels[semantic] = _rotate_vectors(values)
        positions.append(
            (
                name,
                channels.get("POSITION", np.zeros((vertex_count, 3), dtype=np.float32)),
            )
        )
        if "NORMAL" in channels:
            normals.append((name, channels["NORMAL"]))
        if "TANGENT" in channels:
            tangents.append((name, channels["TANGENT"]))
    return positions, normals, tangents


def _decode_uv_layers(reader, attributes, restore_red_uvs):
    layers = []
    append = layers.append
    for channel_index, name in enumerate(UV_ATTRIBUTES):
        accessor = attributes.get(name)
        if accessor is None:
            continue
        raw = reader.read(
            accessor,
            dtype=np.float32,
            copy=restore_red_uvs,
        )
        uv = np.asarray(raw[:, :2], dtype=np.float32)
        if not uv.flags.c_contiguous:
            uv = np.ascontiguousarray(uv)
        if restore_red_uvs:
            uv = convert_wolvenkit_uv_channel(uv, channel_index, copy=False)
        append((channel_index, uv))
    return layers


def _decode_color_layers(reader, attributes):
    layers = []
    append = layers.append
    for channel_index, name in enumerate(COLOR_ATTRIBUTES):
        accessor = attributes.get(name)
        if accessor is None:
            continue
        raw = reader.read(accessor, dtype=np.float32)
        if raw.shape[1] == 4:
            color = np.ascontiguousarray(raw, dtype=np.float32)
        elif raw.shape[1] == 3:
            color = np.ones((raw.shape[0], 4), dtype=np.float32)
            color[:, :3] = raw
        else:
            raise DirectMeshImportError(
                f"Unsupported color accessor width {raw.shape[1]}."
            )
        append((channel_index, color))
    return layers


def _decode_custom_colors(reader, attributes, import_garment_support):
    decoded = []
    decoded_names = set()
    for raw_name, accessor in attributes.items():
        if not str(raw_name).startswith("_"):
            continue
        name = canonical_garment_attribute(str(raw_name))
        if not import_garment_support and is_garment_attribute(name):
            continue
        if name in decoded_names:
            raise DirectMeshImportError(
                f"Duplicate custom color attribute after canonicalization: {name!r}."
            )
        raw = reader.read(accessor, dtype=np.float32)
        if raw.ndim != 2 or raw.shape[1] not in (3, 4):
            raise DirectMeshImportError(
                f"Unsupported custom color accessor {raw_name!r} shape {raw.shape}."
            )
        if raw.shape[1] == 4:
            color = np.ascontiguousarray(raw, dtype=np.float32)
        else:
            color = np.ones((raw.shape[0], 4), dtype=np.float32)
            color[:, :3] = raw
        decoded.append((name, color))
        decoded_names.add(name)
    return decoded


def _decode_tangents(reader, accessor, *, restore_red_space: bool):
    raw = reader.read(accessor, dtype=np.float32)
    result = np.empty((raw.shape[0], 4), dtype=np.float32)
    result[:, :3] = gltf_vectors_to_red(raw)
    result[:, 3] = (
        convert_wolvenkit_tangent_sign(raw[:, 3]) if restore_red_space else raw[:, 3]
    )
    return result


def _degenerate_rows(values):
    finite = np.all(np.isfinite(values), axis=1)
    lengths_squared = np.einsum(
        "ij,ij->i",
        np.where(finite[:, None], values, 0.0),
        np.where(finite[:, None], values, 0.0),
    )
    return ~finite | (lengths_squared <= _FRAME_EPSILON)


def _unit_rows(values, fallback):
    values = np.asarray(values, dtype=np.float64)
    lengths = np.sqrt(np.einsum("ij,ij->i", values, values))
    result = np.empty_like(values)
    valid = lengths > np.sqrt(_FRAME_EPSILON)
    result[valid] = values[valid] / lengths[valid, None]
    result[~valid] = fallback
    return result


def _area_weighted_vertex_normals(positions, triangles, vertices):
    accumulated = np.zeros((len(positions), 3), dtype=np.float64)
    if triangles.size:
        corners = np.asarray(positions, dtype=np.float64)[triangles]
        faces = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
        for corner in range(3):
            np.add.at(accumulated, triangles[:, corner], faces)
    return _unit_rows(accumulated[vertices], (0.0, 0.0, 1.0))


def _repair_vertex_frames(submesh, repairs):
    normals = submesh.normals
    if normals is not None:
        degenerate = _degenerate_rows(normals)
        if np.any(degenerate):
            normals = normals.copy()
            normals[degenerate] = _area_weighted_vertex_normals(
                submesh.positions,
                submesh.triangles,
                degenerate,
            )
            submesh.normals = normals
            repairs["normals"] = int(np.count_nonzero(degenerate))

    tangents = submesh.tangents
    if tangents is None:
        return
    degenerate = _degenerate_rows(tangents[:, :3])
    signs = tangents[:, 3]
    invalid_signs = ~(
        np.isfinite(signs)
        & np.isclose(np.abs(signs), 1.0, rtol=0, atol=_WEIGHT_TOLERANCE)
    )
    if not np.any(degenerate) and not np.any(invalid_signs):
        return
    tangents = tangents.copy()
    if np.any(degenerate):
        reference = (
            np.asarray(normals[degenerate], dtype=np.float64)
            if normals is not None
            else np.tile((0.0, 0.0, 1.0), (int(np.count_nonzero(degenerate)), 1))
        )
        axis = np.zeros_like(reference)
        axis[:, 0] = 1.0
        axis[np.abs(reference[:, 0]) > 0.9] = (0.0, 1.0, 0.0)
        projected = axis - reference * np.einsum("ij,ij->i", axis, reference)[:, None]
        tangents[degenerate, :3] = _unit_rows(projected, (1.0, 0.0, 0.0))
        repairs["tangents"] = int(np.count_nonzero(degenerate))
    if np.any(invalid_signs):
        tangents[invalid_signs, 3] = np.where(signs[invalid_signs] < 0.0, -1.0, 1.0)
        repairs["tangent_signs"] = int(np.count_nonzero(invalid_signs))
    submesh.tangents = tangents


def _repair_skin_weights(submesh, joint_count, repairs):
    joints = submesh.joint_indices
    weights = submesh.joint_weights
    if joints is None or weights is None:
        return
    joints = joints.copy()
    weights = np.where(np.isfinite(weights), weights, 0.0).astype(np.float32)
    invalid_joints = (joints < 0) | (joints >= joint_count)
    if np.any(invalid_joints):
        cleared = int(np.count_nonzero(invalid_joints & (weights > 0.0)))
        if cleared:
            repairs["invalid_joints"] = cleared
        weights[invalid_joints] = 0.0
        joints[invalid_joints] = 0
    negative = weights < 0.0
    if np.any(negative):
        repairs["negative_weights"] = int(np.count_nonzero(negative))
        weights[negative] = 0.0
    totals = weights.sum(axis=1, dtype=np.float64)
    weighted = totals > _WEIGHT_TOLERANCE
    unnormalized = weighted & ~np.isclose(totals, 1.0, rtol=0, atol=_WEIGHT_TOLERANCE)
    if np.any(unnormalized):
        weights[unnormalized] = (
            weights[unnormalized] / totals[unnormalized, None]
        ).astype(np.float32)
        repairs["renormalized_weights"] = int(np.count_nonzero(unnormalized))
    if not np.all(weighted):
        weights[~weighted] = 0.0
        repairs["unweighted"] = int(np.count_nonzero(~weighted))
    submesh.joint_indices = joints
    submesh.joint_weights = np.ascontiguousarray(weights, dtype=np.float32)


def _repair_uv_layers(submesh, repairs):
    layers = []
    cleared = 0
    for channel_index, uv in submesh.uv_layers:
        invalid = ~np.isfinite(uv).all(axis=1)
        if np.any(invalid):
            uv = uv.copy()
            uv[invalid] = 0.0
            cleared += int(np.count_nonzero(invalid))
        layers.append((channel_index, uv))
    if cleared:
        submesh.uv_layers = layers
        repairs["uvs"] = cleared


def _repair_vertex_data(submesh, joint_count):
    """Repair per-vertex defects in place and return the repair counts"""
    repairs = {}
    _repair_vertex_frames(submesh, repairs)
    _repair_uv_layers(submesh, repairs)
    _repair_skin_weights(submesh, joint_count, repairs)
    return repairs


def _decode_submesh(
    reader,
    mesh,
    *,
    mesh_index: int,
    node_index: int,
    skin_index: int | None,
    node_matrix_gltf: np.ndarray,
    restore_red_uvs: bool,
    import_garment_support: bool,
    joint_count: int = 0,
    node_extras: dict | None = None,
) -> Submesh:
    primitives = mesh.get("primitives") or ()
    if not primitives:
        raise DirectMeshImportError(
            f"Mesh {mesh.get('name', 'submesh')!r} has no primitives."
        )
    if len(primitives) != 1:
        raise DirectMeshImportError(
            f"Mesh {mesh.get('name', 'submesh')!r} has {len(primitives)} primitives; "
            "the direct CP77 mesh path expects one primitive per submesh."
        )
    primitive = primitives[0]
    try:
        validate_primitive_accessors(reader.accessors, primitive)
    except ValueError as error:
        raise DirectMeshImportError(str(error)) from error
    attributes = primitive.get("attributes") or {}
    position_accessor = attributes.get("POSITION")
    if position_accessor is None:
        raise DirectMeshImportError(
            f"Mesh {mesh.get('name', 'submesh')!r} has no POSITION accessor."
        )

    mesh_extras = mesh.get("extras") or {}
    name = str(mesh.get("name", "submesh"))
    positions = _rotate_vectors(reader.read(position_accessor, dtype=np.float32))

    indices_accessor = primitive.get("indices")
    if indices_accessor is None:
        if positions.shape[0] % 3:
            raise DirectMeshImportError(
                f"Unindexed mesh {name!r} is not a triangle list."
            )
        triangles = np.arange(positions.shape[0], dtype=np.int32).reshape(-1, 3)
    else:
        flat_indices = reader.read(indices_accessor, dtype=np.int32).reshape(-1)
        if flat_indices.size % 3:
            raise DirectMeshImportError(
                f"Mesh {name!r} index count is not divisible by three."
            )
        triangles = np.ascontiguousarray(flat_indices.reshape(-1, 3))

    if triangles.size:
        minimum_index = int(triangles.min())
        maximum_index = int(triangles.max())
        if minimum_index < 0 or maximum_index >= positions.shape[0]:
            invalid_index = minimum_index if minimum_index < 0 else maximum_index
            raise DirectMeshImportError(
                f"Mesh {name!r} references vertex index {invalid_index} "
                f"outside the decoded vertex range 0..{positions.shape[0] - 1}."
            )

    normal_accessor = attributes.get("NORMAL")
    tangent_accessor = attributes.get("TANGENT")
    normals = (
        _rotate_vectors(reader.read(normal_accessor, dtype=np.float32))
        if normal_accessor is not None
        else None
    )
    tangents = (
        _decode_tangents(
            reader,
            tangent_accessor,
            restore_red_space=restore_red_uvs,
        )
        if tangent_accessor is not None
        else None
    )
    skinning_warning = ""
    joint_indices, joint_weights = _decode_skinning(reader, attributes)
    if joint_indices is not None and skin_index is None:
        # WolvenKit keeps a cloth mesh's weights on a node without a skin; nothing binds them, so the mesh is static.
        joint_indices = joint_weights = None
        skinning_warning = f"Mesh {name!r} has skin weights but its node has no skin; it imports without them."

    morph_targets, morph_normals, morph_tangents = _decode_morph_targets(
        reader,
        primitive,
        mesh_extras,
        import_garment_support,
        len(positions),
    )
    decoded = Submesh(
        name=name,
        lod=_lod_from_name(name),
        material_names=[
            str(value) for value in (mesh_extras.get("materialNames") or ())
        ],
        positions=positions,
        triangles=triangles,
        normals=normals,
        tangents=tangents,
        mesh_index=mesh_index,
        node_index=node_index,
        skin_index=skin_index,
        node_matrix_gltf=np.asarray(node_matrix_gltf, dtype=np.float64),
        node_matrix_red=gltf_matrix_to_red(node_matrix_gltf),
        uv_layers=_decode_uv_layers(reader, attributes, restore_red_uvs),
        color_layers=_decode_color_layers(reader, attributes),
        custom_colors=_decode_custom_colors(reader, attributes, import_garment_support),
        joint_indices=joint_indices,
        joint_weights=joint_weights,
        skinning_warning=skinning_warning,
        morph_targets=morph_targets,
        morph_normals=morph_normals,
        morph_tangents=morph_tangents,
        mesh_extras=dict(mesh_extras),
        node_extras=dict(node_extras or {}),
    )
    decoded.repairs = _repair_vertex_data(decoded, joint_count)
    arrays = {"POSITION": decoded.positions}
    if decoded.normals is not None:
        arrays["NORMAL"] = decoded.normals
    if decoded.tangents is not None:
        arrays["TANGENT"] = decoded.tangents
    arrays.update((f"TEXCOORD_{index}", values) for index, values in decoded.uv_layers)
    arrays.update((f"COLOR_{index}", values) for index, values in decoded.color_layers)
    if decoded.joint_indices is not None:
        arrays["JOINTS_0"] = decoded.joint_indices[:, :4]
        arrays["WEIGHTS_0"] = decoded.joint_weights[:, :4]
        if decoded.joint_indices.shape[1] > 4:
            arrays["JOINTS_1"] = decoded.joint_indices[:, 4:]
            arrays["WEIGHTS_1"] = decoded.joint_weights[:, 4:]
    try:
        validate_mesh_arrays(
            arrays,
            decoded.triangles,
            joint_count=joint_count,
            allow_unweighted=True,
        )
        for attribute_name, values in (
            *decoded.custom_colors,
            *decoded.morph_targets,
            *decoded.morph_normals,
            *decoded.morph_tangents,
        ):
            if (
                values.ndim != 2
                or len(values) != len(decoded.positions)
                or not np.all(np.isfinite(values))
            ):
                raise ValueError(
                    f"{attribute_name} has invalid shape or non-finite data."
                )
    except ValueError as error:
        raise DirectMeshImportError(f"Mesh {name!r}: {error}") from error
    source_indices, detached_triangles = isolate_repeated_triangle_faces(
        decoded.triangles, decoded.vertex_count
    )
    if source_indices is not None:
        decoded.triangles = detached_triangles
        decoded.source_vertex_indices = source_indices
        for attribute in (
            "positions",
            "normals",
            "tangents",
            "joint_indices",
            "joint_weights",
        ):
            values = getattr(decoded, attribute)
            if values is not None:
                setattr(
                    decoded, attribute, np.ascontiguousarray(values[source_indices])
                )
        for attribute in (
            "uv_layers",
            "color_layers",
            "custom_colors",
            "morph_targets",
            "morph_normals",
            "morph_tangents",
        ):
            setattr(
                decoded,
                attribute,
                [
                    (name, np.ascontiguousarray(values[source_indices]))
                    for name, values in getattr(decoded, attribute)
                ],
            )
    return decoded


def decode_mesh_glb(
    filepath: str,
    *,
    restore_red_uvs: bool = True,
    build_binding: bool = True,
    import_garment_support: bool = True,
) -> DirectMeshData:
    try:
        glb = read_gltf_container(filepath)
    except GLBContainerError as error:
        raise DirectMeshImportError(str(error)) from error
    document = glb.document
    try:
        validate_direct_extensions(document)
    except ValueError as error:
        raise DirectMeshImportError(str(error)) from error
    reader = GLTFAccessorReader(glb, error_type=DirectMeshImportError)

    meshes = document.get("meshes") or ()
    if not meshes:
        raise DirectMeshImportError(f"{os.path.basename(filepath)} contains no meshes.")

    try:
        hierarchy = build_node_hierarchy(document)
        skins = _decode_skins(reader, document, hierarchy)
        instances = _mesh_instances(document, hierarchy.global_matrices)
    except ValueError as error:
        raise DirectMeshImportError(str(error)) from error
    node_globals = hierarchy.global_matrices
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
                    restore_red_uvs=restore_red_uvs,
                    import_garment_support=import_garment_support,
                    joint_count=len(skins[skin_index].joint_nodes)
                    if skin_index is not None
                    else 0,
                    node_extras=(nodes[node_index].get("extras") or {})
                    if node_index >= 0
                    else {},
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
            sampling_context = build_sampling_context(hierarchy, binding)

    return DirectMeshData(
        source_path=os.path.abspath(filepath),
        submeshes=submeshes,
        skin_bone_names=skin_bone_names,
        skins=skins,
        binding=binding,
        sampling_context=sampling_context,
        appearance_count=max(
            (len(item.material_names) for item in submeshes), default=0
        ),
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
            )
            if key in document
        },
        scene_metadata={
            key: value
            for key, value in ((document.get("scenes") or [{}])[0]).items()
            if key != "nodes"
        },
    )
