from __future__ import annotations

import copy
from dataclasses import dataclass

import numpy as np

from ..bartmoss.hierarchy import local_matrices_to_model, parent_first_order
from ..bartmoss.trs import compose_matrices
from .nodes import node_trs


class GLTFSkeletonError(ValueError):
    """A glTF skeleton cannot satisfy the shared node or skin contract"""


@dataclass(frozen=True)
class SkeletonBinding:
    skin_index: int
    joint_nodes: tuple[int, ...]
    bone_names: tuple[str, ...]
    source_parent_indices: tuple[int, ...]
    topological_joint_indices: tuple[int, ...]
    skin_extras: dict


@dataclass(frozen=True, slots=True)
class NodeHierarchy:
    parents: tuple[int, ...]
    topology: tuple[int, ...]
    translations: np.ndarray
    rotations: np.ndarray
    scales: np.ndarray
    local_matrices: np.ndarray
    global_matrices: np.ndarray


def build_node_hierarchy(document):
    """Decode and validate the node hierarchy once for mesh, rig and animation consumers"""
    nodes = document.get("nodes") or ()
    parents = tuple(node_parents(nodes))
    topology = parent_first_order(parents)
    defaults = [node_trs(node) for node in nodes]
    translations = np.asarray(
        [value[0] for value in defaults], dtype=np.float64
    ).reshape(-1, 3)
    rotations = np.asarray([value[1] for value in defaults], dtype=np.float64).reshape(
        -1, 4
    )
    scales = np.asarray([value[2] for value in defaults], dtype=np.float64).reshape(
        -1, 3
    )
    local = compose_matrices(translations, rotations, scales)
    for index, node in enumerate(nodes):
        if "matrix" in node:
            local[index] = np.asarray(node["matrix"], dtype=np.float64).reshape(4, 4).T
    return NodeHierarchy(
        parents,
        topology,
        translations,
        rotations,
        scales,
        local,
        local_matrices_to_model(local, parents, topology),
    )


@dataclass(frozen=True)
class SamplingContext:
    node_parents: tuple[int, ...]
    node_topology: tuple[int, ...]
    default_translations: np.ndarray
    default_rotations: np.ndarray
    default_scales: np.ndarray
    default_local_matrices: np.ndarray
    default_global_matrices: np.ndarray
    joint_default_prefixes: np.ndarray
    node_to_joint: dict[int, int]
    joint_node_set: frozenset[int]


def build_sampling_context(
    hierarchy: NodeHierarchy, binding: SkeletonBinding
) -> SamplingContext:
    parents = hierarchy.parents
    node_topology = hierarchy.topology
    default_translations = hierarchy.translations
    default_rotations = hierarchy.rotations
    default_scales = hierarchy.scales
    default_local = hierarchy.local_matrices
    default_global = hierarchy.global_matrices
    node_count = len(parents)
    default_segment = np.empty((node_count, 4, 4), dtype=np.float64)
    node_to_joint = {
        node_index: joint_index
        for joint_index, node_index in enumerate(binding.joint_nodes)
    }
    joint_default_prefixes = np.empty(
        (len(binding.joint_nodes), 4, 4), dtype=np.float64
    )
    nearest_joint_ancestor = np.full(node_count, -1, dtype=np.int32)
    identity = np.eye(4, dtype=np.float64)

    for node_index in node_topology:
        parent_index = parents[node_index]
        if parent_index < 0:
            default_segment[node_index] = default_local[node_index]
            prefix = identity
            nearest_joint = -1
        else:
            parent_joint = node_to_joint.get(parent_index)
            if parent_joint is not None:
                default_segment[node_index] = default_local[node_index]
                prefix = identity
                nearest_joint = parent_joint
            else:
                default_segment[node_index] = (
                    default_segment[parent_index] @ default_local[node_index]
                )
                prefix = default_segment[parent_index]
                nearest_joint = int(nearest_joint_ancestor[parent_index])

        nearest_joint_ancestor[node_index] = nearest_joint
        joint_index = node_to_joint.get(node_index)
        if joint_index is not None:
            expected_parent = binding.source_parent_indices[joint_index]
            if nearest_joint != expected_parent:
                raise GLTFSkeletonError(
                    f"Could not resolve joint hierarchy for {binding.bone_names[joint_index]!r}."
                )
            joint_default_prefixes[joint_index] = prefix

    return SamplingContext(
        node_parents=parents,
        node_topology=node_topology,
        default_translations=default_translations,
        default_rotations=default_rotations,
        default_scales=default_scales,
        default_local_matrices=default_local,
        default_global_matrices=default_global,
        joint_default_prefixes=joint_default_prefixes,
        node_to_joint=node_to_joint,
        joint_node_set=frozenset(node_to_joint),
    )


def node_parents(nodes) -> list[int]:
    parents = [-1] * len(nodes)
    for parent_index, node in enumerate(nodes):
        for child_index in node.get("children", ()):
            if isinstance(child_index, bool) or not isinstance(child_index, int):
                raise GLTFSkeletonError("Node child indices must be integers.")
            if not 0 <= child_index < len(nodes):
                raise GLTFSkeletonError(
                    f"Node {parent_index} references invalid child {child_index}."
                )
            if parents[child_index] != -1:
                raise GLTFSkeletonError(f"Node {child_index} has multiple parents.")
            parents[child_index] = parent_index
    return parents


def build_skeleton_binding(
    document: dict, hierarchy: NodeHierarchy, skin_index: int = 0
) -> SkeletonBinding:
    skins = document.get("skins", ())
    nodes = document.get("nodes", ())
    if (
        isinstance(skin_index, bool)
        or not isinstance(skin_index, int)
        or not 0 <= skin_index < len(skins)
    ):
        raise GLTFSkeletonError("The document references an invalid skin.")
    skin = skins[skin_index]
    raw_joints = skin.get("joints", ())
    if not isinstance(raw_joints, list) or any(
        isinstance(index, bool) or not isinstance(index, int) for index in raw_joints
    ):
        raise GLTFSkeletonError("Skin joints must be an array of integer node indices.")
    joints = tuple(raw_joints)
    if not joints:
        raise GLTFSkeletonError("The glTF skin has no joints.")
    if any(index < 0 or index >= len(nodes) for index in joints):
        raise GLTFSkeletonError("The skin contains an invalid joint node index.")
    if len(set(joints)) != len(joints):
        raise GLTFSkeletonError("The skin contains duplicate joint nodes.")

    extras = copy.deepcopy(skin.get("extras") or {})
    track_names = extras.get("trackNames", [])
    if not isinstance(track_names, list):
        raise GLTFSkeletonError("skin.extras.trackNames must be a list.")
    if len(track_names) > 0xFFFF:
        raise GLTFSkeletonError(
            "skin.extras.trackNames exceeds the supported track count."
        )
    normalized_track_names = tuple(str(name) for name in track_names)
    if len(set(normalized_track_names)) != len(normalized_track_names):
        raise GLTFSkeletonError("skin.extras.trackNames contains duplicate names.")

    extra_names = tuple(str(name) for name in extras.get("boneNames", ()))
    node_names = tuple(str(nodes[index].get("name", "")) for index in joints)
    bone_names = extra_names if len(extra_names) == len(joints) else node_names
    if not all(bone_names) or len(set(bone_names)) != len(bone_names):
        raise GLTFSkeletonError(
            "The skin does not provide unique names for every joint."
        )
    if extra_names and extra_names != node_names:
        raise GLTFSkeletonError(
            "Skin extras boneNames do not match the glTF joint node names."
        )

    parents = hierarchy.parents
    joint_lookup = {
        node_index: joint_index for joint_index, node_index in enumerate(joints)
    }
    source_parents = []
    for node_index in joints:
        parent_node = parents[node_index]
        while parent_node >= 0 and parent_node not in joint_lookup:
            parent_node = parents[parent_node]
        source_parents.append(joint_lookup.get(parent_node, -1))

    extra_parents = extras.get("boneParentIndexes")
    if extra_parents is not None:
        if not isinstance(extra_parents, list) or len(extra_parents) != len(joints):
            raise GLTFSkeletonError(
                "skin.extras.boneParentIndexes must match the joint count."
            )
        if any(
            isinstance(value, bool) or not isinstance(value, int)
            for value in extra_parents
        ):
            raise GLTFSkeletonError(
                "skin.extras.boneParentIndexes must contain integers."
            )
        normalized = tuple(extra_parents)
        if normalized != tuple(source_parents):
            raise GLTFSkeletonError(
                "Skin extras boneParentIndexes do not match the glTF joint hierarchy."
            )

    joint_topology = parent_first_order(source_parents)
    return SkeletonBinding(
        skin_index=skin_index,
        joint_nodes=joints,
        bone_names=bone_names,
        source_parent_indices=tuple(source_parents),
        topological_joint_indices=joint_topology,
        skin_extras=extras,
    )
