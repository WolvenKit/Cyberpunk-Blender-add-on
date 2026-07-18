from __future__ import annotations

import copy
import json
import math
import os
import struct
import time
from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np

try:
    import bpy
    from mathutils import Matrix
except ImportError:
    bpy = None
    Matrix = None

from ..main.animation_glb import (
    BLENDER_BONE_RIGHT_TO_GLTF as _BLENDER_BONE_RIGHT_TO_GLTF,
    FPS,
    GLTF_TO_BLENDER_BONE_RIGHT as _GLTF_TO_BLENDER_BONE_RIGHT,
    GLTF_TO_RED as _GLTF_TO_RED,
    RIG_SPACE_CONTRACT,
    SKIN_EXTRAS_SNAPSHOT_KEY,
    SOURCE_REST_SNAPSHOT_KEY,
    SOURCE_REST_SPACE_CONTRACT,
    compose_trs_batch,
    quaternions_wxyz_from_matrices as _quaternions_wxyz_from_matrices,
)
from ..main.rig_utils import merged_rig_bone_name
from ..main.transform_math import quat_multiply_wxyz

if bpy is not None:
    from ..main.animation_api import (
        assign_action_with_slot,
        bulk_set_keyframes,
        get_action_fcurves,
    )
else:
    assign_action_with_slot = None
    bulk_set_keyframes = None
    get_action_fcurves = None


_COMPONENT_DTYPES = {
    5120: np.dtype("<i1"),
    5121: np.dtype("<u1"),
    5122: np.dtype("<i2"),
    5123: np.dtype("<u2"),
    5125: np.dtype("<u4"),
    5126: np.dtype("<f4"),
}
_SUPPORTED_GLTF_INTERPOLATIONS = frozenset({"LINEAR", "STEP"})

_TYPE_WIDTHS = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
    "MAT2": 4,
    "MAT3": 9,
    "MAT4": 16,
}


class DirectAnimationImportError(RuntimeError):
    pass


class UnsupportedDirectAnimation(DirectAnimationImportError):
    pass


class DenseBasisRequired(UnsupportedDirectAnimation):
    """The clip is directly importable but requires dense basis conversion."""

    pass


@dataclass(frozen=True)
class GLBData:
    document: dict
    binary: bytes


@dataclass(frozen=True)
class SkeletonBinding:
    skin_index: int
    joint_nodes: tuple[int, ...]
    bone_names: tuple[str, ...]
    source_parent_indices: tuple[int, ...]
    topological_joint_indices: tuple[int, ...]
    skin_extras: dict


@dataclass(frozen=True)
class SampledAnimation:
    name: str
    frames: np.ndarray
    model_matrices: np.ndarray | None
    relative_matrices: np.ndarray
    extras: dict
    has_scale_channels: bool = False


@dataclass(frozen=True)
class ParsedGLTFChannel:
    node_index: int
    joint_index: int
    path: str
    interpolation: str
    times: np.ndarray
    values: np.ndarray
    sampler_index: int


@dataclass(frozen=True)
class SparsePropertyChannel:
    frames: np.ndarray
    values: np.ndarray
    interpolation: str


@dataclass(frozen=True)
class SparseAnimation:
    name: str
    location_channels: tuple[SparsePropertyChannel | None, ...]
    rotation_channels: tuple[SparsePropertyChannel | None, ...]
    extras: dict
    frame_count: int
    source_keypoints: int


@dataclass(frozen=True)
class SparseConversionContext:
    node_to_joint: dict[int, int]
    translation_rotations: np.ndarray
    translation_offsets: np.ndarray
    rotation_left_wxyz: np.ndarray
    rotation_right_wxyz: np.ndarray
    default_locations: np.ndarray
    default_rotations_wxyz: np.ndarray


@dataclass(frozen=True)
class SparsePoseBase:
    location_values: np.ndarray
    rotation_values_wxyz: np.ndarray
    location_mask: np.ndarray
    rotation_mask: np.ndarray


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


@dataclass(frozen=True)
class TargetBinding:
    bone_names: tuple[str, ...]
    pose_bones: tuple
    rest_matrices: np.ndarray
    inverse_rest_matrices: np.ndarray
    inverse_rest_relative: np.ndarray
    location_paths: tuple[str, ...]
    rotation_paths: tuple[str, ...]
    scale_paths: tuple[str, ...]
    fast_numpy_basis: bool
    merged_target: bool


class AccessorReader:
    def __init__(self, glb: GLBData):
        self.document = glb.document
        self.binary = glb.binary
        usage = {}
        for animation in self.document.get("animations", ()):
            for sampler in animation.get("samplers", ()):
                for key in ("input", "output"):
                    accessor_index = sampler.get(key)
                    if accessor_index is not None:
                        accessor_index = int(accessor_index)
                        usage[accessor_index] = usage.get(accessor_index, 0) + 1
        self.cacheable = {
            accessor_index
            for accessor_index, count in usage.items()
            if count > 1
        }
        self.cache = {}

    def read(self, accessor_index: int) -> np.ndarray:
        if accessor_index in self.cacheable:
            cached = self.cache.get(accessor_index)
            if cached is not None:
                return cached

        accessors = self.document.get("accessors", ())
        if not 0 <= accessor_index < len(accessors):
            raise DirectAnimationImportError(
                f"Invalid glTF accessor index {accessor_index}."
            )
        accessor = accessors[accessor_index]
        if accessor.get("sparse"):
            raise UnsupportedDirectAnimation(
                f"Sparse accessor {accessor_index} is not supported by direct animation import."
            )
        view_index = accessor.get("bufferView")
        if view_index is None:
            count = int(accessor.get("count", 0))
            width = _TYPE_WIDTHS.get(accessor.get("type"))
            if width is None:
                raise UnsupportedDirectAnimation(
                    f"Unsupported accessor type {accessor.get('type')!r}."
                )
            result = np.zeros((count, width), dtype=np.float64)
            if width == 1:
                result = result[:, 0]
            if accessor_index in self.cacheable:
                self.cache[accessor_index] = result
            return result

        views = self.document.get("bufferViews", ())
        if not 0 <= view_index < len(views):
            raise DirectAnimationImportError(
                f"Invalid glTF bufferView index {view_index}."
            )
        view = views[view_index]
        if int(view.get("buffer", 0)) != 0:
            raise UnsupportedDirectAnimation(
                "Direct animation import supports the embedded GLB buffer only."
            )

        component_type = int(accessor.get("componentType", 0))
        dtype = _COMPONENT_DTYPES.get(component_type)
        if dtype is None:
            raise UnsupportedDirectAnimation(
                f"Unsupported accessor component type {component_type}."
            )
        width = _TYPE_WIDTHS.get(accessor.get("type"))
        if width is None:
            raise UnsupportedDirectAnimation(
                f"Unsupported accessor type {accessor.get('type')!r}."
            )

        count = int(accessor.get("count", 0))
        offset = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
        item_bytes = dtype.itemsize * width
        stride = int(view.get("byteStride", item_bytes))
        if stride < item_bytes:
            raise DirectAnimationImportError(
                f"Accessor {accessor_index} has invalid byte stride {stride}."
            )

        end = offset + (count - 1) * stride + item_bytes if count else offset
        view_start = int(view.get("byteOffset", 0))
        view_end = view_start + int(view.get("byteLength", 0))
        if offset < view_start or end > view_end or end > len(self.binary):
            raise DirectAnimationImportError(
                f"Accessor {accessor_index} exceeds its GLB bufferView."
            )

        if stride == item_bytes:
            raw = np.frombuffer(
                self.binary, dtype=dtype, count=count * width, offset=offset
            ).reshape(count, width)
        else:
            raw = np.ndarray(
                shape=(count, width),
                dtype=dtype,
                buffer=self.binary,
                offset=offset,
                strides=(stride, dtype.itemsize),
            )

        result = np.asarray(raw, dtype=np.float64).copy()
        if accessor.get("normalized") and component_type != 5126:
            if component_type in (5120, 5122):
                maximum = float(np.iinfo(dtype).max)
                result = np.maximum(result / maximum, -1.0)
            else:
                result /= float(np.iinfo(dtype).max)
        if width == 1:
            result = result[:, 0]
        if accessor_index in self.cacheable:
            self.cache[accessor_index] = result
        return result


def read_glb(filepath: str) -> GLBData:
    with open(filepath, "rb") as stream:
        header = stream.read(12)
        if len(header) != 12:
            raise DirectAnimationImportError("The file is too short to be a GLB.")
        magic, version, declared_length = struct.unpack("<4sII", header)
        if magic != b"glTF" or version != 2:
            raise UnsupportedDirectAnimation("Direct import requires a glTF 2.0 GLB.")

        json_chunk = None
        binary_chunk = b""
        while stream.tell() < declared_length:
            chunk_header = stream.read(8)
            if len(chunk_header) != 8:
                raise DirectAnimationImportError("Truncated GLB chunk header.")
            chunk_length, chunk_type = struct.unpack("<II", chunk_header)
            payload = stream.read(chunk_length)
            if len(payload) != chunk_length:
                raise DirectAnimationImportError("Truncated GLB chunk payload.")
            if chunk_type == 0x4E4F534A:
                json_chunk = payload
            elif chunk_type == 0x004E4942:
                binary_chunk = payload

    if json_chunk is None:
        raise DirectAnimationImportError("GLB has no JSON chunk.")
    try:
        document = json.loads(json_chunk.decode("utf-8").rstrip("\x00 \t\r\n"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DirectAnimationImportError(f"Invalid GLB JSON chunk: {error}") from error
    return GLBData(document=document, binary=binary_chunk)


def build_sampling_context(document: dict, binding: SkeletonBinding) -> SamplingContext:
    nodes = document.get("nodes", ())
    node_parents = tuple(_node_parents(nodes))
    node_topology = _topological_indices(node_parents)
    defaults = [_node_default_trs(node) for node in nodes]
    if defaults:
        default_translations = np.asarray([value[0] for value in defaults], dtype=np.float64)
        default_rotations = np.asarray([value[1] for value in defaults], dtype=np.float64)
        default_scales = np.asarray([value[2] for value in defaults], dtype=np.float64)
    else:
        default_translations = np.empty((0, 3), dtype=np.float64)
        default_rotations = np.empty((0, 4), dtype=np.float64)
        default_scales = np.empty((0, 3), dtype=np.float64)

    node_count = len(nodes)
    default_local = compose_trs_batch(
        default_translations,
        default_rotations,
        default_scales,
    )
    default_global = np.empty((node_count, 4, 4), dtype=np.float64)
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
        parent_index = node_parents[node_index]
        if parent_index < 0:
            default_global[node_index] = default_local[node_index]
            default_segment[node_index] = default_local[node_index]
            prefix = identity
            nearest_joint = -1
        else:
            default_global[node_index] = (
                default_global[parent_index] @ default_local[node_index]
            )
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
                raise UnsupportedDirectAnimation(
                    f"Could not resolve joint hierarchy for {binding.bone_names[joint_index]!r}."
                )
            joint_default_prefixes[joint_index] = prefix

    return SamplingContext(
        node_parents=node_parents,
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


def _node_default_trs(node: dict):
    if "matrix" in node:
        matrix = np.asarray(node["matrix"], dtype=np.float64).reshape(4, 4).T
        translation = matrix[:3, 3].copy()
        columns = matrix[:3, :3]
        scale = np.linalg.norm(columns, axis=0)
        rotation_matrix = columns / np.maximum(scale[np.newaxis, :], 1e-15)
        rotation_wxyz = _quaternions_wxyz_from_matrices(rotation_matrix)[0]
        rotation_xyzw = rotation_wxyz[[1, 2, 3, 0]]
        return translation, rotation_xyzw, scale
    return (
        np.asarray(node.get("translation", (0.0, 0.0, 0.0)), dtype=np.float64),
        np.asarray(node.get("rotation", (0.0, 0.0, 0.0, 1.0)), dtype=np.float64),
        np.asarray(node.get("scale", (1.0, 1.0, 1.0)), dtype=np.float64),
    )


def _node_parents(nodes) -> list[int]:
    parents = [-1] * len(nodes)
    for parent_index, node in enumerate(nodes):
        for child_index in node.get("children", ()):
            child_index = int(child_index)
            if not 0 <= child_index < len(nodes):
                raise DirectAnimationImportError(
                    f"Node {parent_index} references invalid child {child_index}."
                )
            if parents[child_index] != -1:
                raise UnsupportedDirectAnimation(
                    f"Node {child_index} has multiple parents."
                )
            parents[child_index] = parent_index
    return parents


def _topological_indices(parents) -> tuple[int, ...]:
    children = [[] for _ in parents]
    roots = []
    for index, parent in enumerate(parents):
        if parent < 0:
            roots.append(index)
        elif parent < len(parents):
            children[parent].append(index)
        else:
            raise DirectAnimationImportError(f"Invalid parent index {parent}.")
    ordered = []
    stack = list(reversed(roots))
    while stack:
        index = stack.pop()
        ordered.append(index)
        stack.extend(reversed(children[index]))
    if len(ordered) != len(parents):
        raise UnsupportedDirectAnimation("The glTF node hierarchy contains a cycle.")
    return tuple(ordered)


def build_skeleton_binding(document: dict, skin_index: int = 0) -> SkeletonBinding:
    skins = document.get("skins", ())
    nodes = document.get("nodes", ())
    if len(skins) != 1 or skin_index != 0:
        raise UnsupportedDirectAnimation(
            "Direct CP77 animation import currently requires exactly one skin."
        )
    skin = skins[skin_index]
    joints = tuple(int(index) for index in skin.get("joints", ()))
    if not joints:
        raise UnsupportedDirectAnimation("The animation GLB skin has no joints.")
    if len(set(joints)) != len(joints):
        raise DirectAnimationImportError("The skin contains duplicate joint nodes.")

    extras = copy.deepcopy(skin.get("extras") or {})
    extra_names = tuple(str(name) for name in extras.get("boneNames", ()))
    node_names = tuple(str(nodes[index].get("name", "")) for index in joints)
    bone_names = extra_names if len(extra_names) == len(joints) else node_names
    if not all(bone_names) or len(set(bone_names)) != len(bone_names):
        raise UnsupportedDirectAnimation(
            "The skin does not provide unique names for every joint."
        )
    if extra_names and extra_names != node_names:
        raise UnsupportedDirectAnimation(
            "Skin extras boneNames do not match the glTF joint node names."
        )

    node_parents = _node_parents(nodes)
    joint_lookup = {node_index: joint_index for joint_index, node_index in enumerate(joints)}
    source_parents = []
    for node_index in joints:
        parent_node = node_parents[node_index]
        while parent_node >= 0 and parent_node not in joint_lookup:
            parent_node = node_parents[parent_node]
        source_parents.append(joint_lookup.get(parent_node, -1))

    extra_parents = extras.get("boneParentIndexes")
    if isinstance(extra_parents, list) and len(extra_parents) == len(joints):
        normalized = tuple(int(value) for value in extra_parents)
        if normalized != tuple(source_parents):
            raise UnsupportedDirectAnimation(
                "Skin extras boneParentIndexes do not match the glTF joint hierarchy."
            )

    joint_topology = _topological_indices(source_parents)
    return SkeletonBinding(
        skin_index=skin_index,
        joint_nodes=joints,
        bone_names=bone_names,
        source_parent_indices=tuple(source_parents),
        topological_joint_indices=joint_topology,
        skin_extras=extras,
    )


def _sample_linear(times, values, sample_times):
    if len(times) == 0:
        raise DirectAnimationImportError("Animation sampler has no input keys.")
    if len(times) != len(values):
        raise DirectAnimationImportError("Animation sampler input/output counts differ.")
    if len(times) == 1:
        return np.repeat(values[:1], len(sample_times), axis=0)
    right = np.searchsorted(times, sample_times, side="right")
    right = np.clip(right, 1, len(times) - 1)
    left = right - 1
    denominator = times[right] - times[left]
    factor = np.divide(
        sample_times - times[left],
        denominator,
        out=np.zeros_like(sample_times),
        where=np.abs(denominator) > 1e-15,
    )
    factor = np.clip(factor, 0.0, 1.0)
    before = sample_times <= times[0]
    after = sample_times >= times[-1]
    result = values[left] + (values[right] - values[left]) * factor[:, None]
    result[before] = values[0]
    result[after] = values[-1]
    return result


def _sample_step(times, values, sample_times):
    if len(times) == 0 or len(times) != len(values):
        raise DirectAnimationImportError("Invalid STEP animation sampler.")
    indices = np.searchsorted(times, sample_times, side="right") - 1
    indices = np.clip(indices, 0, len(times) - 1)
    return values[indices]


def _sample_quaternions(times, values, sample_times, interpolation):
    values = np.asarray(values, dtype=np.float64).copy()
    lengths = np.linalg.norm(values, axis=1)
    values[lengths <= 1e-15] = (0.0, 0.0, 0.0, 1.0)
    lengths = np.linalg.norm(values, axis=1)
    values /= lengths[:, None]
    if len(values) > 1:
        adjacent_dots = np.sum(values[:-1] * values[1:], axis=1)
        signs = np.ones(len(values), dtype=np.float64)
        signs[1:] = np.cumprod(
            np.where(adjacent_dots < 0.0, -1.0, 1.0)
        )
        values *= signs[:, None]
    if interpolation == "STEP" or len(times) == 1:
        return _sample_step(times, values, sample_times)

    right = np.searchsorted(times, sample_times, side="right")
    right = np.clip(right, 1, len(times) - 1)
    left = right - 1
    denominator = times[right] - times[left]
    factor = np.divide(
        sample_times - times[left], denominator,
        out=np.zeros_like(sample_times), where=np.abs(denominator) > 1e-15,
    )
    factor = np.clip(factor, 0.0, 1.0)
    q0 = values[left]
    q1 = values[right]
    dot = np.sum(q0 * q1, axis=1)
    q1 = np.where((dot < 0.0)[:, None], -q1, q1)
    dot = np.clip(np.abs(dot), 0.0, 1.0)
    theta = np.arccos(dot)
    sin_theta = np.sin(theta)
    linear = sin_theta < 1e-7
    w0 = np.empty_like(factor)
    w1 = np.empty_like(factor)
    w0[linear] = 1.0 - factor[linear]
    w1[linear] = factor[linear]
    nonlinear = ~linear
    w0[nonlinear] = np.sin((1.0 - factor[nonlinear]) * theta[nonlinear]) / sin_theta[nonlinear]
    w1[nonlinear] = np.sin(factor[nonlinear] * theta[nonlinear]) / sin_theta[nonlinear]
    result = q0 * w0[:, None] + q1 * w1[:, None]
    result /= np.maximum(np.linalg.norm(result, axis=1)[:, None], 1e-15)
    result[sample_times <= times[0]] = values[0]
    result[sample_times >= times[-1]] = values[-1]
    return result



def _parse_gltf_channel(
    animation: dict,
    animation_index: int,
    reader: AccessorReader,
    node_to_joint: dict[int, int],
):
    samplers = animation.get("samplers", ())
    seen_targets = set()
    animation_name = animation.get("name", animation_index)

    for channel in animation.get("channels", ()):
        target = channel.get("target") or {}
        node_value = target.get("node")
        path = target.get("path")
        if path == "weights":
            raise UnsupportedDirectAnimation(
                f"Animation {animation_name!r} contains morph-weight channels."
            )
        if path not in {"translation", "rotation", "scale"}:
            raise UnsupportedDirectAnimation(
                f"Unsupported animation target path {path!r}."
            )
        try:
            node_index = int(node_value)
        except (TypeError, ValueError) as error:
            raise DirectAnimationImportError(
                "Animation channel has an invalid target node."
            ) from error
        joint_index = node_to_joint.get(node_index)
        if joint_index is None:
            raise UnsupportedDirectAnimation(
                f"Animation targets non-joint node {node_index}."
            )

        key = (joint_index, path)
        if key in seen_targets:
            raise UnsupportedDirectAnimation(
                f"Animation contains duplicate {path} channels for node {node_index}."
            )
        seen_targets.add(key)

        try:
            sampler_index = int(channel.get("sampler", -1))
        except (TypeError, ValueError) as error:
            raise DirectAnimationImportError(
                "Animation channel has an invalid sampler."
            ) from error
        if not 0 <= sampler_index < len(samplers):
            raise DirectAnimationImportError(
                "Animation channel has an invalid sampler."
            )
        sampler = samplers[sampler_index]
        interpolation = str(sampler.get("interpolation", "LINEAR")).upper()
        if interpolation not in _SUPPORTED_GLTF_INTERPOLATIONS:
            raise UnsupportedDirectAnimation(
                f"Interpolation {interpolation!r} is not supported by direct import."
            )
        try:
            input_accessor = int(sampler["input"])
            output_accessor = int(sampler["output"])
        except (KeyError, TypeError, ValueError) as error:
            raise DirectAnimationImportError(
                f"Animation sampler {sampler_index} has invalid accessors."
            ) from error

        times = np.asarray(reader.read(input_accessor), dtype=np.float64).reshape(-1)
        if not len(times):
            seen_targets.discard(key)
            continue
        if times[0] < 0.0 or np.any(np.diff(times) <= 0.0):
            raise DirectAnimationImportError(
                f"Animation sampler {sampler_index} input times are not strictly increasing."
            )

        width = 4 if path == "rotation" else 3
        values = np.asarray(reader.read(output_accessor), dtype=np.float64)
        if values.size != len(times) * width:
            raise DirectAnimationImportError(
                f"Animation sampler {sampler_index} output size does not match its {path} input."
            )
        values = values.reshape(len(times), width)
        yield ParsedGLTFChannel(
            node_index=node_index,
            joint_index=joint_index,
            path=path,
            interpolation=interpolation,
            times=times,
            values=values,
            sampler_index=sampler_index,
        )

def sample_animation(
    glb: GLBData,
    binding: SkeletonBinding,
    animation_index: int,
    fps: float = FPS,
    reader: AccessorReader | None = None,
    context: SamplingContext | None = None,
    include_model_matrices: bool = True,
) -> SampledAnimation:
    document = glb.document
    animations = document.get("animations", ())
    if not 0 <= animation_index < len(animations):
        raise DirectAnimationImportError(f"Invalid animation index {animation_index}.")
    animation = animations[animation_index]
    reader = reader or AccessorReader(glb)
    context = context or build_sampling_context(document, binding)
    channel_records = tuple(
        _parse_gltf_channel(
            animation, animation_index, reader, context.node_to_joint
        )
    )

    maximum_time = max(
        (float(channel.times[-1]) for channel in channel_records),
        default=0.0,
    )
    has_scale_channels = any(
        channel.path == "scale" for channel in channel_records
    )
    end_frame = max(0, int(math.ceil(maximum_time * fps - 1e-7)))
    frames = np.arange(end_frame + 1, dtype=np.float64)
    sample_times = frames / fps
    frame_count = len(frames)
    node_count = len(document.get("nodes", ()))
    translations = np.broadcast_to(
        context.default_translations, (frame_count, node_count, 3)
    ).copy()
    rotations = np.broadcast_to(
        context.default_rotations, (frame_count, node_count, 4)
    ).copy()
    scales = np.broadcast_to(
        context.default_scales, (frame_count, node_count, 3)
    ).copy()

    for channel in channel_records:
        if channel.path == "rotation":
            rotations[:, channel.node_index] = _sample_quaternions(
                channel.times,
                channel.values,
                sample_times,
                channel.interpolation,
            )
        else:
            sampled_values = (
                _sample_step(channel.times, channel.values, sample_times)
                if channel.interpolation == "STEP"
                else _sample_linear(channel.times, channel.values, sample_times)
            )
            if channel.path == "translation":
                translations[:, channel.node_index] = sampled_values
            else:
                scales[:, channel.node_index] = sampled_values

    local = compose_trs_batch(
        translations,
        rotations,
        scales,
        normalize_rotations_in_place=True,
    )
    node_relative = np.empty_like(local)
    for node_index in context.node_topology:
        parent_index = context.node_parents[node_index]
        if parent_index < 0 or parent_index in context.joint_node_set:
            node_relative[:, node_index] = local[:, node_index]
        else:
            node_relative[:, node_index] = np.matmul(
                node_relative[:, parent_index], local[:, node_index]
            )
    relative_gltf = node_relative[:, binding.joint_nodes].copy()

    relative_blender = np.empty_like(relative_gltf)
    for joint_index in binding.topological_joint_indices:
        parent_index = binding.source_parent_indices[joint_index]
        if parent_index < 0:
            relative_blender[:, joint_index] = np.matmul(
                np.matmul(_GLTF_TO_RED, relative_gltf[:, joint_index]),
                _GLTF_TO_BLENDER_BONE_RIGHT,
            )
        else:
            relative_blender[:, joint_index] = np.matmul(
                np.matmul(
                    _BLENDER_BONE_RIGHT_TO_GLTF,
                    relative_gltf[:, joint_index],
                ),
                _GLTF_TO_BLENDER_BONE_RIGHT,
            )

    model_blender = None
    if include_model_matrices:
        model_blender = np.empty_like(relative_blender)
        for joint_index in binding.topological_joint_indices:
            parent_index = binding.source_parent_indices[joint_index]
            if parent_index < 0:
                model_blender[:, joint_index] = relative_blender[:, joint_index]
            else:
                model_blender[:, joint_index] = np.matmul(
                    model_blender[:, parent_index],
                    relative_blender[:, joint_index],
                )

    return SampledAnimation(
        name=str(animation.get("name") or f"Animation_{animation_index:03d}"),
        frames=frames,
        model_matrices=model_blender,
        relative_matrices=relative_blender,
        extras=animation.get("extras") or {},
        has_scale_channels=has_scale_channels,
    )


def _constant_property_channel(frames, values, interpolation):
    frames = np.asarray(frames, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    if len(frames) > 1 and np.all(np.abs(values - values[0]) <= 1e-10):
        frames = frames[:1].copy()
        values = values[:1].copy()
    return SparsePropertyChannel(frames, values, interpolation)


def _quat_multiply_wxyz(left, right):
    return quat_multiply_wxyz(
        np.asarray(left, dtype=np.float64),
        np.asarray(right, dtype=np.float64),
    )

def build_sparse_conversion_context(
    binding: SkeletonBinding,
    context: SamplingContext,
    target: TargetBinding,
) -> SparseConversionContext:
    joint_count = len(binding.bone_names)
    translation_rotations = np.empty((joint_count, 3, 3), dtype=np.float64)
    translation_offsets = np.empty((joint_count, 3), dtype=np.float64)
    rotation_left = np.empty((joint_count, 4), dtype=np.float64)
    rotation_right = np.empty((joint_count, 4), dtype=np.float64)
    default_locations = np.empty((joint_count, 3), dtype=np.float64)
    default_rotations = np.empty((joint_count, 4), dtype=np.float64)

    right_matrix = _GLTF_TO_BLENDER_BONE_RIGHT
    right_rotation = _quaternions_wxyz_from_matrices(
        right_matrix[:3, :3].reshape(1, 3, 3)
    )[0]
    for joint_index, node_index in enumerate(binding.joint_nodes):
        prefix = context.joint_default_prefixes[joint_index]
        conversion_left = (
            _GLTF_TO_RED
            if binding.source_parent_indices[joint_index] < 0
            else _BLENDER_BONE_RIGHT_TO_GLTF
        )
        left_matrix = (
            target.inverse_rest_relative[joint_index]
            @ conversion_left
            @ prefix
        )
        left_axes = left_matrix[:3, :3]
        scales = np.linalg.norm(left_axes, axis=0)
        normalized_left = left_axes / np.maximum(scales[None, :], 1e-15)
        if not np.allclose(scales, 1.0, atol=2e-5) or not np.allclose(
            normalized_left.T @ normalized_left, np.eye(3), atol=2e-5
        ):
            raise UnsupportedDirectAnimation(
                "Sparse animation conversion requires rigid source and target bases."
            )
        left_rotation = _quaternions_wxyz_from_matrices(
            normalized_left.reshape(1, 3, 3)
        )[0]
        translation_rotations[joint_index] = left_axes
        translation_offsets[joint_index] = left_matrix[:3, 3]
        rotation_left[joint_index] = left_rotation
        rotation_right[joint_index] = right_rotation

        default_locations[joint_index] = (
            left_axes @ context.default_translations[node_index]
            + left_matrix[:3, 3]
        )
        source_default = context.default_rotations[node_index]
        source_default_wxyz = source_default[[3, 0, 1, 2]]
        default_rotation = _quat_multiply_wxyz(
            _quat_multiply_wxyz(left_rotation, source_default_wxyz),
            right_rotation,
        )
        default_rotations[joint_index] = (
            default_rotation / max(np.linalg.norm(default_rotation), 1e-15)
        )

    return SparseConversionContext(
        node_to_joint=context.node_to_joint,
        translation_rotations=translation_rotations,
        translation_offsets=translation_offsets,
        rotation_left_wxyz=rotation_left,
        rotation_right_wxyz=rotation_right,
        default_locations=default_locations,
        default_rotations_wxyz=default_rotations,
    )


def _transform_sparse_translation(conversion, joint_index, values):
    values = np.asarray(values, dtype=np.float64).reshape(-1, 3)
    rotation = conversion.translation_rotations[joint_index]
    return values @ rotation.T + conversion.translation_offsets[joint_index]


def _transform_sparse_rotation(conversion, joint_index, values):
    values = np.asarray(values, dtype=np.float64).reshape(-1, 4)
    source_wxyz = values[:, (3, 0, 1, 2)]
    left = conversion.rotation_left_wxyz[joint_index]
    right = conversion.rotation_right_wxyz[joint_index]
    result = _quat_multiply_wxyz(
        _quat_multiply_wxyz(left, source_wxyz), right
    )
    result /= np.maximum(np.linalg.norm(result, axis=1)[:, None], 1e-15)
    if len(result) > 1:
        dots = np.sum(result[:-1] * result[1:], axis=1)
        flips = np.cumprod(np.where(dots < 0.0, -1.0, 1.0))
        result[1:] *= flips[:, None]
    return result


def sparse_animation(
    glb: GLBData,
    binding: SkeletonBinding,
    animation_index: int,
    target: TargetBinding,
    *,
    fps: float = FPS,
    reader: AccessorReader | None = None,
    context: SamplingContext | None = None,
    conversion: SparseConversionContext | None = None,
    pose_base: SparsePoseBase | None = None,
    include_defaults: bool = False,
) -> SparseAnimation:
    document = glb.document
    animations = document.get("animations", ())
    if not 0 <= animation_index < len(animations):
        raise DirectAnimationImportError(f"Invalid animation index {animation_index}.")
    animation = animations[animation_index]
    reader = reader or AccessorReader(glb)
    context = context or build_sampling_context(document, binding)
    conversion = conversion or build_sparse_conversion_context(
        binding, context, target
    )
    location_channels = [None] * len(binding.bone_names)
    rotation_channels = [None] * len(binding.bone_names)
    seen_targets = set()
    maximum_time = 0.0
    source_keypoints = 0

    for channel in _parse_gltf_channel(
        animation, animation_index, reader, conversion.node_to_joint
    ):
        joint_index = channel.joint_index
        node_index = channel.node_index
        path = channel.path
        interpolation = channel.interpolation
        times = channel.times
        values = channel.values
        seen_targets.add((joint_index, path))
        maximum_time = max(maximum_time, float(times[-1]))

        if path == "scale":
            default_scale = context.default_scales[node_index]
            if np.allclose(
                values,
                default_scale.reshape(1, 3),
                atol=2e-6,
                rtol=2e-6,
            ):
                continue
            raise DenseBasisRequired(
                "Non-default or animated scale requires dense basis conversion."
            )

        source_keypoints += len(times) * (3 if path == "translation" else 4)
        transformed = (
            _transform_sparse_translation(conversion, joint_index, values)
            if path == "translation"
            else _transform_sparse_rotation(conversion, joint_index, values)
        )
        if path == "translation":
            if pose_base is not None and pose_base.location_mask[joint_index]:
                base_value = pose_base.location_values[joint_index]
                if np.allclose(
                    transformed,
                    base_value.reshape(1, 3),
                    atol=1e-9,
                    rtol=1e-9,
                ):
                    continue
            location_channels[joint_index] = _constant_property_channel(
                times * fps, transformed, interpolation
            )
        else:
            alignment_value = (
                pose_base.rotation_values_wxyz[joint_index]
                if pose_base is not None and pose_base.rotation_mask[joint_index]
                else conversion.default_rotations_wxyz[joint_index]
            )
            if len(transformed) and np.dot(transformed[0], alignment_value) < 0.0:
                transformed = -transformed
            if pose_base is not None and pose_base.rotation_mask[joint_index]:
                if np.allclose(
                    transformed,
                    alignment_value.reshape(1, 4),
                    atol=1e-9,
                    rtol=1e-9,
                ):
                    continue
            rotation_channels[joint_index] = _constant_property_channel(
                times * fps, transformed, interpolation
            )

    if pose_base is not None or include_defaults:
        for joint_index in range(len(binding.bone_names)):
            if (
                location_channels[joint_index] is None
                and (joint_index, "translation") not in seen_targets
                and (
                    include_defaults
                    or not (
                        pose_base.location_mask[joint_index]
                        and np.allclose(
                            conversion.default_locations[joint_index],
                            pose_base.location_values[joint_index],
                            atol=1e-9,
                            rtol=1e-9,
                        )
                    )
                )
            ):
                location_channels[joint_index] = SparsePropertyChannel(
                    np.array((0.0,), dtype=np.float64),
                    conversion.default_locations[joint_index].reshape(1, 3).copy(),
                    "LINEAR",
                )
            if (
                rotation_channels[joint_index] is None
                and (joint_index, "rotation") not in seen_targets
                and (
                    include_defaults
                    or not (
                        pose_base.rotation_mask[joint_index]
                        and abs(
                            float(
                                np.dot(
                                    conversion.default_rotations_wxyz[joint_index],
                                    pose_base.rotation_values_wxyz[joint_index],
                                )
                            )
                        ) >= 1.0 - 1e-9
                    )
                )
            ):
                default_rotation = conversion.default_rotations_wxyz[joint_index].copy()
                if pose_base is not None and np.dot(
                    default_rotation,
                    pose_base.rotation_values_wxyz[joint_index],
                ) < 0.0:
                    default_rotation = -default_rotation
                rotation_channels[joint_index] = SparsePropertyChannel(
                    np.array((0.0,), dtype=np.float64),
                    default_rotation.reshape(1, 4),
                    "LINEAR",
                )

    return SparseAnimation(
        name=str(animation.get("name") or f"Animation_{animation_index:03d}"),
        location_channels=tuple(location_channels),
        rotation_channels=tuple(rotation_channels),
        extras=animation.get("extras") or {},
        frame_count=max(1, int(math.ceil(maximum_time * fps - 1e-7)) + 1),
        source_keypoints=source_keypoints,
    )

def build_sparse_pose_base(
    sparse: SparseAnimation,
    conversion: SparseConversionContext,
) -> SparsePoseBase:
    joint_count = len(sparse.location_channels)
    location_values = np.asarray(conversion.default_locations, dtype=np.float64).copy()
    rotation_values = np.asarray(
        conversion.default_rotations_wxyz, dtype=np.float64
    ).copy()
    location_mask = np.zeros(joint_count, dtype=bool)
    rotation_mask = np.zeros(joint_count, dtype=bool)

    for joint_index in range(joint_count):
        location = sparse.location_channels[joint_index]
        if location is None:
            location_mask[joint_index] = True
        elif len(location.values) == 1:
            location_values[joint_index] = location.values[0]
            location_mask[joint_index] = True

        rotation = sparse.rotation_channels[joint_index]
        if rotation is None:
            rotation_mask[joint_index] = True
        elif len(rotation.values) == 1:
            value = rotation.values[0].copy()
            if np.dot(value, rotation_values[joint_index]) < 0.0:
                value = -value
            rotation_values[joint_index] = value
            rotation_mask[joint_index] = True

    return SparsePoseBase(
        location_values=location_values,
        rotation_values_wxyz=rotation_values,
        location_mask=location_mask,
        rotation_mask=rotation_mask,
    )


def _meta_bone_name(name: str) -> str:
    return merged_rig_bone_name(name)


def _resolve_target_bone_names(armature, binding: SkeletonBinding) -> tuple[str, ...]:
    pose_bones = armature.pose.bones
    resolved = []
    used = set()
    for source_name in binding.bone_names:
        target_name = source_name if pose_bones.get(source_name) is not None else _meta_bone_name(source_name)
        if pose_bones.get(target_name) is None:
            raise UnsupportedDirectAnimation(
                f"Target armature is missing required bone {source_name!r} "
                f"(resolved target name {target_name!r})."
            )
        if target_name in used:
            raise UnsupportedDirectAnimation(
                f"Multiple source joints resolve to target bone {target_name!r}."
            )
        used.add(target_name)
        resolved.append(target_name)
    return tuple(resolved)


def validate_target_armature(armature, binding: SkeletonBinding) -> tuple[str, ...]:
    if armature is None or getattr(armature, "type", None) != "ARMATURE":
        raise UnsupportedDirectAnimation(
            "Select a read_rig armature or a mesh bound to one before importing animations."
        )
    contract = str(armature.data.get("cp77_rig_space_contract", ""))
    if contract != RIG_SPACE_CONTRACT:
        raise UnsupportedDirectAnimation(
            "The selected armature was not imported with the supported JSON rig-space contract."
        )

    target_names = _resolve_target_bone_names(armature, binding)
    for source_name, target_name in zip(binding.bone_names, target_names):
        pose_bone = armature.pose.bones[target_name]
        inherit_scale = getattr(pose_bone.bone, "inherit_scale", "FULL")
        if inherit_scale != "FULL":
            raise UnsupportedDirectAnimation(
                f"Target bone {target_name!r} for source joint {source_name!r} "
                f"uses unsupported inherit_scale={inherit_scale!r}."
            )
        if not getattr(pose_bone.bone, "use_inherit_rotation", True):
            raise UnsupportedDirectAnimation(
                f"Target bone {target_name!r} disables inherited rotation."
            )
        if not getattr(pose_bone.bone, "use_local_location", True):
            raise UnsupportedDirectAnimation(
                f"Target bone {target_name!r} disables local location."
            )
        if getattr(pose_bone, "rotation_mode", "QUATERNION") != "QUATERNION":
            pose_bone.rotation_mode = "QUATERNION"
    return target_names


def _store_json_snapshot(idblock, key: str, value) -> None:
    idblock[key] = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _source_rest_snapshot(binding, target_binding) -> dict:
    matrices = np.linalg.inv(target_binding.inverse_rest_relative)
    return {
        "version": 1,
        "space": SOURCE_REST_SPACE_CONTRACT,
        "boneNames": list(binding.bone_names),
        "matrices": matrices.reshape(len(matrices), 16).tolist(),
    }


def _idprop_plain(value):
    if isinstance(value, (str, bool, int, float)) or value is None:
        return value
    if hasattr(value, "keys"):
        return {str(key): _idprop_plain(value[key]) for key in value.keys()}
    if hasattr(value, "__iter__"):
        return [_idprop_plain(item) for item in value]
    return str(value)


def _assign_action(armature, action):
    return assign_action_with_slot(armature, action)


def _action_fcurves(action, armature):
    return get_action_fcurves(action, armature, create=True)


def _ensure_fcurve(fcurves, data_path, index, group_name):
    return fcurves.ensure(data_path, index=index, group_name=group_name)


def _bulk_keys(fcurve, frames, values, interpolation="LINEAR"):
    return bulk_set_keyframes(
        fcurve,
        frames,
        values,
        interpolation=interpolation,
        collapse_constant=True,
    )

def _matrix_from_numpy(value):
    return Matrix(tuple(tuple(float(component) for component in row) for row in value))


def _matrix_to_numpy(value):
    return np.asarray(value, dtype=np.float64)


def _source_rest_relative_matrices(
    binding: SkeletonBinding,
    context: SamplingContext,
) -> np.ndarray:
    source_rest = np.empty((len(binding.bone_names), 4, 4), dtype=np.float64)
    for joint_index, node_index in enumerate(binding.joint_nodes):
        relative_gltf = (
            context.joint_default_prefixes[joint_index]
            @ context.default_local_matrices[node_index]
        )
        if binding.source_parent_indices[joint_index] < 0:
            source_rest[joint_index] = (
                _GLTF_TO_RED @ relative_gltf @ _GLTF_TO_BLENDER_BONE_RIGHT
            )
        else:
            source_rest[joint_index] = (
                _BLENDER_BONE_RIGHT_TO_GLTF
                @ relative_gltf
                @ _GLTF_TO_BLENDER_BONE_RIGHT
            )
    return source_rest


def build_target_binding(
    armature,
    binding: SkeletonBinding,
    context: SamplingContext,
    target_names: tuple[str, ...] | None = None,
) -> TargetBinding:
    target_names = target_names or _resolve_target_bone_names(armature, binding)
    pose_bones = tuple(armature.pose.bones[name] for name in target_names)
    rest_matrices = np.asarray(
        [_matrix_to_numpy(pose_bone.bone.matrix_local) for pose_bone in pose_bones],
        dtype=np.float64,
    )
    inverse_rest = np.linalg.inv(rest_matrices)

    source_rest_relative = _source_rest_relative_matrices(binding, context)
    inverse_source_rest_relative = np.linalg.inv(source_rest_relative)
    source_axes = source_rest_relative[:, :3, :3]
    source_scales = np.linalg.norm(source_axes, axis=1)
    normalized_source = source_axes / np.maximum(source_scales[:, None, :], 1e-15)
    source_orthogonality = np.matmul(
        np.swapaxes(normalized_source, 1, 2), normalized_source
    )

    rest_axes = rest_matrices[:, :3, :3]
    rest_scales = np.linalg.norm(rest_axes, axis=1)
    normalized_rest = rest_axes / np.maximum(rest_scales[:, None, :], 1e-15)
    rest_orthogonality = np.matmul(
        np.swapaxes(normalized_rest, 1, 2), normalized_rest
    )
    fast_numpy_basis = bool(
        np.allclose(source_scales, 1.0, atol=2e-5)
        and np.allclose(source_orthogonality, np.eye(3), atol=2e-5)
        and np.allclose(rest_scales, 1.0, atol=2e-5)
        and np.allclose(rest_orthogonality, np.eye(3), atol=2e-5)
        and all(getattr(pb.bone, "inherit_scale", "FULL") == "FULL" for pb in pose_bones)
        and all(getattr(pb.bone, "use_inherit_rotation", True) for pb in pose_bones)
        and all(getattr(pb.bone, "use_local_location", True) for pb in pose_bones)
    )
    if not fast_numpy_basis:
        raise UnsupportedDirectAnimation(
            "The selected read_rig target contains non-rigid bone bases or unsupported inheritance settings."
        )

    target_bone_names = tuple(str(name) for name in armature.data.get("boneNames", ()))
    merged_target = (
        len(target_bone_names) != len(binding.bone_names)
        or target_names != binding.bone_names
    )
    return TargetBinding(
        bone_names=target_names,
        pose_bones=pose_bones,
        rest_matrices=rest_matrices,
        inverse_rest_matrices=inverse_rest,
        inverse_rest_relative=inverse_source_rest_relative,
        location_paths=tuple(pb.path_from_id("location") for pb in pose_bones),
        rotation_paths=tuple(pb.path_from_id("rotation_quaternion") for pb in pose_bones),
        scale_paths=tuple(pb.path_from_id("scale") for pb in pose_bones),
        fast_numpy_basis=True,
        merged_target=merged_target,
    )


def _basis_channels_numpy(
    binding: SkeletonBinding,
    sampled: SampledAnimation,
    target: TargetBinding,
):
    basis = np.empty_like(sampled.relative_matrices)
    for joint_index in binding.topological_joint_indices:
        basis[:, joint_index] = np.matmul(
            target.inverse_rest_relative[joint_index],
            sampled.relative_matrices[:, joint_index],
        )

    locations = basis[..., :3, 3].copy()
    axes = basis[..., :3, :3]
    scales = np.linalg.norm(axes, axis=-2)
    rotations = axes / np.maximum(scales[..., None, :], 1e-15)
    quaternions = _quaternions_wxyz_from_matrices(rotations)
    return locations, quaternions, scales


def _basis_channels_blender(
    armature,
    binding: SkeletonBinding,
    sampled: SampledAnimation,
    target: TargetBinding,
):
    """Safety fallback for rigs that cannot use the vectorized basis path.

    Keep this path correct but isolated; a complete NumPy equivalent of
    Bone.convert_local_to_pose remains required before it can be considered fast.
    """
    if sampled.model_matrices is None:
        raise DirectAnimationImportError(
            "Model matrices are required for Blender basis conversion fallback."
        )
    frame_count = len(sampled.frames)
    joint_count = len(binding.bone_names)
    locations = np.zeros((frame_count, joint_count, 3), dtype=np.float64)
    rotations = np.zeros((frame_count, joint_count, 4), dtype=np.float64)
    scales = np.ones((frame_count, joint_count, 3), dtype=np.float64)

    for frame_index in range(frame_count):
        desired = [
            _matrix_from_numpy(sampled.model_matrices[frame_index, joint_index])
            for joint_index in range(joint_count)
        ]
        for joint_index in binding.topological_joint_indices:
            pose_bone = target.pose_bones[joint_index]
            parent_index = binding.source_parent_indices[joint_index]
            if parent_index < 0:
                basis = pose_bone.bone.convert_local_to_pose(
                    desired[joint_index],
                    pose_bone.bone.matrix_local,
                    invert=True,
                )
            else:
                basis = pose_bone.bone.convert_local_to_pose(
                    desired[joint_index],
                    pose_bone.bone.matrix_local,
                    parent_matrix=desired[parent_index],
                    parent_matrix_local=target.pose_bones[parent_index].bone.matrix_local,
                    invert=True,
                )
            location, rotation, scale = basis.decompose()
            rotation.normalize()
            locations[frame_index, joint_index] = tuple(location)
            rotations[frame_index, joint_index] = (
                rotation.w, rotation.x, rotation.y, rotation.z
            )
            scales[frame_index, joint_index] = tuple(scale)
    return locations, rotations, scales


def _basis_channels(
    armature,
    binding: SkeletonBinding,
    sampled: SampledAnimation,
    target: TargetBinding,
):
    locations, rotations, scales = _basis_channels_numpy(
        binding, sampled, target
    )

    for joint_index in range(len(binding.bone_names)):
        dots = np.sum(
            rotations[:-1, joint_index] * rotations[1:, joint_index], axis=1
        )
        flips = np.cumprod(np.where(dots < 0.0, -1.0, 1.0))
        rotations[1:, joint_index] *= flips[:, None]
    return locations, rotations, scales


def _property_is_default(channel, default_value):
    return (
        channel is not None
        and len(channel.values) == 1
        and np.allclose(channel.values[0], default_value, atol=1e-7)
    )


def _replace_curve_keys(
    fcurves,
    data_path,
    index,
    group_name,
    frames,
    values,
    interpolation="LINEAR",
):
    curve = _ensure_fcurve(fcurves, data_path, index, group_name)
    previous_count = len(curve.keyframe_points)
    if previous_count:
        curve.keyframe_points.clear()
    new_count = _bulk_keys(
        curve,
        frames,
        values,
        interpolation=interpolation,
    )
    return curve, previous_count, new_count


def _build_sparse_pose_template(
    armature,
    binding,
    pose_base,
    target_binding,
):
    action = bpy.data.actions.new("__CP77_DIRECT_ANIM_POSE_TEMPLATE__")
    action.use_fake_user = False
    fcurves = _action_fcurves(action, armature)
    curve_count = 0
    keypoint_count = 0
    try:
        for joint_index, bone_name in enumerate(target_binding.bone_names):
            location = pose_base.location_values[joint_index]
            rotation = pose_base.rotation_values_wxyz[joint_index]
            if pose_base.location_mask[joint_index] and not np.allclose(
                location,
                (0.0, 0.0, 0.0),
                atol=1e-9,
                rtol=1e-9,
            ):
                path = target_binding.location_paths[joint_index]
                for component in range(3):
                    curve = _ensure_fcurve(
                        fcurves, path, component, bone_name
                    )
                    keypoint_count += _bulk_keys(
                        curve,
                        (0.0,),
                        (location[component],),
                    )
                    curve_count += 1
            if pose_base.rotation_mask[joint_index] and not np.allclose(
                rotation,
                (1.0, 0.0, 0.0, 0.0),
                atol=1e-9,
                rtol=1e-9,
            ):
                path = target_binding.rotation_paths[joint_index]
                for component in range(4):
                    curve = _ensure_fcurve(
                        fcurves, path, component, bone_name
                    )
                    keypoint_count += _bulk_keys(
                        curve,
                        (0.0,),
                        (rotation[component],),
                    )
                    curve_count += 1
        return action, curve_count, keypoint_count
    except Exception:
        if bpy.data.actions.get(action.name) is action:
            bpy.data.actions.remove(action)
        raise


def _write_sparse_pose_action(
    armature,
    binding,
    sparse,
    import_tracks,
    target_binding,
    template_action=None,
    template_curve_count=0,
    template_keypoint_count=0,
    timing_totals=None,
):
    from ..cyber_props import add_anim_props
    from ..animtools.tracks import import_anim_tracks

    timing_totals = timing_totals if timing_totals is not None else {}
    shell_started = time.perf_counter()
    if template_action is not None:
        action = template_action.copy()
        action.name = sparse.name
    else:
        action = bpy.data.actions.new(sparse.name)
    action.use_fake_user = True
    try:
        fcurves = _action_fcurves(action, armature)
        timing_totals["action_shell"] = timing_totals.get(
            "action_shell", 0.0
        ) + (time.perf_counter() - shell_started)

        pose_started = time.perf_counter()
        pose_curve_count = int(template_curve_count)
        pose_keypoint_count = int(template_keypoint_count)
        pose_override_curve_count = 0
        pose_override_keypoint_count = 0
        for joint_index, bone_name in enumerate(target_binding.bone_names):
            location = sparse.location_channels[joint_index]
            rotation = sparse.rotation_channels[joint_index]
            if location is not None:
                path = target_binding.location_paths[joint_index]
                for component in range(3):
                    existing = fcurves.find(data_path=path, index=component)
                    was_existing = existing is not None
                    _, previous_count, new_count = _replace_curve_keys(
                        fcurves,
                        path,
                        component,
                        bone_name,
                        location.frames,
                        location.values[:, component],
                        interpolation=location.interpolation,
                    )
                    pose_keypoint_count += new_count - previous_count
                    pose_override_curve_count += 1
                    pose_override_keypoint_count += new_count
                    if not was_existing:
                        pose_curve_count += 1
            if rotation is not None:
                path = target_binding.rotation_paths[joint_index]
                for component in range(4):
                    existing = fcurves.find(data_path=path, index=component)
                    was_existing = existing is not None
                    _, previous_count, new_count = _replace_curve_keys(
                        fcurves,
                        path,
                        component,
                        bone_name,
                        rotation.frames,
                        rotation.values[:, component],
                        interpolation=rotation.interpolation,
                    )
                    pose_keypoint_count += new_count - previous_count
                    pose_override_curve_count += 1
                    pose_override_keypoint_count += new_count
                    if not was_existing:
                        pose_curve_count += 1
        timing_totals["pose_curves"] = timing_totals.get(
            "pose_curves", 0.0
        ) + (time.perf_counter() - pose_started)

        metadata_started = time.perf_counter()
        add_anim_props(SimpleNamespace(extras=sparse.extras), action)
        timing_totals["metadata"] = timing_totals.get(
            "metadata", 0.0
        ) + (time.perf_counter() - metadata_started)

        track_stats = {
            "curve_count": 0,
            "keypoint_count": 0,
            "omitted_zero_count": 0,
        }
        if import_tracks:
            tracks_started = time.perf_counter()
            track_stats = import_anim_tracks(
                action,
                armature=armature,
                ensure_properties=False,
                extras=sparse.extras,
                replace_existing=False,
            ) or track_stats
            timing_totals["track_curves"] = timing_totals.get(
                "track_curves", 0.0
            ) + (time.perf_counter() - tracks_started)

        return action, {
            "pose_curves": pose_curve_count,
            "pose_keypoints": pose_keypoint_count,
            "pose_override_curves": pose_override_curve_count,
            "pose_override_keypoints": pose_override_keypoint_count,
            "track_curves": int(track_stats.get("curve_count", 0)),
            "track_keypoints": int(track_stats.get("keypoint_count", 0)),
            "omitted_zero_tracks": int(track_stats.get("omitted_zero_count", 0)),
        }
    except Exception:
        if bpy.data.actions.get(action.name) is action:
            bpy.data.actions.remove(action)
        raise


def _write_pose_action(
    armature,
    binding,
    sampled,
    import_tracks,
    target_binding,
    timing_totals=None,
):
    from ..cyber_props import add_anim_props
    from ..animtools.tracks import import_anim_tracks

    timing_totals = timing_totals if timing_totals is not None else {}
    shell_started = time.perf_counter()
    action = bpy.data.actions.new(sampled.name)
    action.use_fake_user = True
    try:
        fcurves = _action_fcurves(action, armature)
        timing_totals["action_shell"] = timing_totals.get(
            "action_shell", 0.0
        ) + (time.perf_counter() - shell_started)

        pose_started = time.perf_counter()
        locations, rotations, scales = _basis_channels(
            armature, binding, sampled, target_binding
        )
        frames = sampled.frames.astype(np.float64)
        pose_curve_count = 0
        pose_keypoint_count = 0

        for joint_index, bone_name in enumerate(target_binding.bone_names):
            location_path = target_binding.location_paths[joint_index]
            rotation_path = target_binding.rotation_paths[joint_index]
            scale_path = target_binding.scale_paths[joint_index]

            for component in range(3):
                curve = _ensure_fcurve(fcurves, location_path, component, bone_name)
                pose_keypoint_count += _bulk_keys(
                    curve, frames, locations[:, joint_index, component]
                )
                pose_curve_count += 1
            for component in range(4):
                curve = _ensure_fcurve(fcurves, rotation_path, component, bone_name)
                pose_keypoint_count += _bulk_keys(
                    curve, frames, rotations[:, joint_index, component]
                )
                pose_curve_count += 1
            if not np.allclose(scales[:, joint_index], 1.0, atol=1e-7):
                for component in range(3):
                    curve = _ensure_fcurve(fcurves, scale_path, component, bone_name)
                    pose_keypoint_count += _bulk_keys(
                        curve, frames, scales[:, joint_index, component]
                    )
                    pose_curve_count += 1
        timing_totals["pose_curves"] = timing_totals.get(
            "pose_curves", 0.0
        ) + (time.perf_counter() - pose_started)

        metadata_started = time.perf_counter()
        add_anim_props(SimpleNamespace(extras=sampled.extras), action)
        timing_totals["metadata"] = timing_totals.get(
            "metadata", 0.0
        ) + (time.perf_counter() - metadata_started)

        track_stats = {
            "curve_count": 0,
            "keypoint_count": 0,
            "omitted_zero_count": 0,
        }
        if import_tracks:
            tracks_started = time.perf_counter()
            track_stats = import_anim_tracks(
                action,
                armature=armature,
                ensure_properties=False,
                extras=sampled.extras,
                replace_existing=False,
            ) or track_stats
            timing_totals["track_curves"] = timing_totals.get(
                "track_curves", 0.0
            ) + (time.perf_counter() - tracks_started)

        return action, {
            "pose_curves": pose_curve_count,
            "pose_keypoints": pose_keypoint_count,
            "pose_override_curves": pose_curve_count,
            "pose_override_keypoints": pose_keypoint_count,
            "track_curves": int(track_stats.get("curve_count", 0)),
            "track_keypoints": int(track_stats.get("keypoint_count", 0)),
            "omitted_zero_tracks": int(track_stats.get("omitted_zero_count", 0)),
        }
    except Exception:
        if bpy.data.actions.get(action.name) is action:
            bpy.data.actions.remove(action)
        raise


def import_anims_glb_to_armature(
    filepath: str,
    armature,
    *,
    import_tracks: bool = True,
    verbose: bool = False,
):
    if bpy is None or Matrix is None:
        raise RuntimeError("Blender is required to create animation actions.")

    started_at = time.perf_counter()
    glb = read_glb(filepath)
    parse_seconds = time.perf_counter() - started_at
    setup_started = time.perf_counter()
    binding = build_skeleton_binding(glb.document)
    target_names = validate_target_armature(armature, binding)
    animations = glb.document.get("animations", ())
    if not animations:
        raise UnsupportedDirectAnimation("The GLB contains no animations.")

    reader = AccessorReader(glb)
    sampling_context = build_sampling_context(glb.document, binding)
    target_binding = build_target_binding(
        armature, binding, sampling_context, target_names
    )
    if verbose and not target_binding.fast_numpy_basis:
        print(
            "[CP77 Direct Anim] Target rig requires the Blender basis fallback; "
            "dense clips may be substantially slower."
        )
    sparse_conversion = (
        build_sparse_conversion_context(binding, sampling_context, target_binding)
        if target_binding.fast_numpy_basis
        else None
    )
    sparse_pose_base = None
    sparse_template_action = None
    sparse_template_curve_count = 0
    sparse_template_keypoint_count = 0
    if sparse_conversion is not None:
        for base_animation_index in range(len(animations)):
            try:
                base_sparse = sparse_animation(
                    glb,
                    binding,
                    base_animation_index,
                    target_binding,
                    reader=reader,
                    context=sampling_context,
                    conversion=sparse_conversion,
                    include_defaults=True,
                )
            except DenseBasisRequired:
                continue
            sparse_pose_base = build_sparse_pose_base(
                base_sparse,
                sparse_conversion,
            )
            break
        if sparse_pose_base is not None:
            (
                sparse_template_action,
                sparse_template_curve_count,
                sparse_template_keypoint_count,
            ) = _build_sparse_pose_template(
                armature,
                binding,
                sparse_pose_base,
                target_binding,
            )
    setup_seconds = time.perf_counter() - setup_started

    animation_data = armature.animation_data_create()
    previous_action = animation_data.action
    previous_slot = getattr(animation_data, "action_slot", None)
    created_actions = []
    skin_property_keys = {
        "rigPath", "boneNames", "boneParentIndexes", "trackNames",
        SKIN_EXTRAS_SNAPSHOT_KEY, SOURCE_REST_SNAPSHOT_KEY,
    }
    previous_skin_values = {
        key: _idprop_plain(armature.get(key))
        for key in skin_property_keys
        if key in armature
    }
    conversion_seconds = 0.0
    action_seconds = 0.0
    total_pose_curves = 0
    total_pose_keypoints = 0
    total_pose_override_curves = 0
    total_pose_override_keypoints = 0
    total_track_curves = 0
    total_track_keypoints = 0
    total_omitted_zero_tracks = 0
    blender_timing = {
        "action_shell": 0.0,
        "pose_curves": 0.0,
        "metadata": 0.0,
        "track_curves": 0.0,
    }

    try:
        skin_extras = binding.skin_extras
        _store_json_snapshot(armature, SKIN_EXTRAS_SNAPSHOT_KEY, skin_extras)
        _store_json_snapshot(
            armature,
            SOURCE_REST_SNAPSHOT_KEY,
            _source_rest_snapshot(binding, target_binding),
        )
        if not target_binding.merged_target:
            from ..cyber_props import add_skin_props
            add_skin_props(SimpleNamespace(extras=skin_extras), armature)
        else:
            rig_path = skin_extras.get("rigPath")
            if rig_path is not None:
                armature["rigPath"] = _idprop_plain(rig_path)
            track_names = skin_extras.get("trackNames") or ()
            armature["trackNames"] = {
                str(index): str(name)
                for index, name in enumerate(track_names)
            }

        if import_tracks:
            from ..animtools.tracks import prepare_anim_track_properties

            prepare_anim_track_properties(
                (animation.get("extras") or {} for animation in animations),
                armature,
            )

        total_frames = 0
        sparse_clip_count = 0
        dense_clip_count = 0
        for animation_index, animation in enumerate(animations):
            conversion_started = time.perf_counter()
            sparse = None
            if target_binding.fast_numpy_basis:
                try:
                    sparse = sparse_animation(
                        glb,
                        binding,
                        animation_index,
                        target_binding,
                        reader=reader,
                        context=sampling_context,
                        conversion=sparse_conversion,
                        pose_base=sparse_pose_base,
                    )
                except DenseBasisRequired:
                    sparse = None

            if sparse is not None:
                sparse_clip_count += 1
                conversion_seconds += time.perf_counter() - conversion_started
                clip_frame_count = sparse.frame_count
                total_frames += clip_frame_count
                action_started = time.perf_counter()
                action, action_stats = _write_sparse_pose_action(
                    armature,
                    binding,
                    sparse,
                    import_tracks=import_tracks,
                    target_binding=target_binding,
                    template_action=sparse_template_action,
                    template_curve_count=sparse_template_curve_count,
                    template_keypoint_count=sparse_template_keypoint_count,
                    timing_totals=blender_timing,
                )
            else:
                dense_clip_count += 1
                sampled = sample_animation(
                    glb,
                    binding,
                    animation_index,
                    reader=reader,
                    context=sampling_context,
                    include_model_matrices=True,
                )
                conversion_seconds += time.perf_counter() - conversion_started
                clip_frame_count = len(sampled.frames)
                total_frames += clip_frame_count
                action_started = time.perf_counter()
                action, action_stats = _write_pose_action(
                    armature,
                    binding,
                    sampled,
                    import_tracks=import_tracks,
                    target_binding=target_binding,
                    timing_totals=blender_timing,
                )
            action_seconds += time.perf_counter() - action_started
            total_pose_curves += action_stats["pose_curves"]
            total_pose_keypoints += action_stats["pose_keypoints"]
            total_pose_override_curves += action_stats["pose_override_curves"]
            total_pose_override_keypoints += action_stats["pose_override_keypoints"]
            total_track_curves += action_stats["track_curves"]
            total_track_keypoints += action_stats["track_keypoints"]
            total_omitted_zero_tracks += action_stats["omitted_zero_tracks"]
            created_actions.append(action)
            if verbose and (
                animation_index == 0
                or (animation_index + 1) % 10 == 0
                or animation_index + 1 == len(animations)
            ):
                print(
                    f"[CP77 Direct Anim] Created {animation_index + 1}/"
                    f"{len(animations)} actions; latest={action.name}"
                )

        if previous_action is not None:
            _assign_action(armature, previous_action)
            if previous_slot is not None and hasattr(animation_data, "action_slot"):
                try:
                    animation_data.action_slot = previous_slot
                except (TypeError, RuntimeError):
                    pass
        elif created_actions:
            _assign_action(armature, created_actions[0])

    except Exception:
        if sparse_template_action is not None and bpy.data.actions.get(
            sparse_template_action.name
        ) is sparse_template_action:
            bpy.data.actions.remove(sparse_template_action)
        if previous_action is not None:
            _assign_action(armature, previous_action)
        else:
            animation_data.action = None
        for action in created_actions:
            if bpy.data.actions.get(action.name) is action:
                bpy.data.actions.remove(action)
        for key in skin_property_keys:
            if key in previous_skin_values:
                armature[key] = previous_skin_values[key]
            elif key in armature:
                del armature[key]
        raise

    if sparse_template_action is not None and bpy.data.actions.get(
        sparse_template_action.name
    ) is sparse_template_action:
        bpy.data.actions.remove(sparse_template_action)

    elapsed_seconds = time.perf_counter() - started_at
    if verbose:
        print(
            "[CP77 Direct Anim] Timing: "
            f"parse={parse_seconds:.3f}s, setup={setup_seconds:.3f}s, "
            f"convert={conversion_seconds:.3f}s, "
            f"Blender data={action_seconds:.3f}s, total={elapsed_seconds:.3f}s"
        )
        print(
            "[CP77 Direct Anim] Blender data split: "
            f"actions={blender_timing['action_shell']:.3f}s, "
            f"pose={blender_timing['pose_curves']:.3f}s, "
            f"metadata={blender_timing['metadata']:.3f}s, "
            f"tracks={blender_timing['track_curves']:.3f}s"
        )
        print(
            "[CP77 Direct Anim] Payload: "
            f"pose={total_pose_curves} curves/{total_pose_keypoints} keys, "
            f"tracks={total_track_curves} curves/{total_track_keypoints} keys, "
            f"omitted_zero_tracks={total_omitted_zero_tracks}, "
            f"sparse_clips={sparse_clip_count}, dense_clips={dense_clip_count}, "
            f"pose_template={sparse_template_curve_count} curves/"
            f"{sparse_template_keypoint_count} keys, "
            f"python_pose_writes={total_pose_override_curves} curves/"
            f"{total_pose_override_keypoints} keys"
        )

    return {
        "direct_imported": True,
        "filepath": os.path.abspath(filepath),
        "armature": armature,
        "actions": created_actions,
        "animation_count": len(created_actions),
        "bone_count": len(binding.bone_names),
        "frame_count": total_frames,
        "fast_numpy_basis": target_binding.fast_numpy_basis,
        "elapsed_seconds": elapsed_seconds,
        "parse_seconds": parse_seconds,
        "setup_seconds": setup_seconds,
        "conversion_seconds": conversion_seconds,
        "action_seconds": action_seconds,
        "pose_curve_count": total_pose_curves,
        "pose_keypoint_count": total_pose_keypoints,
        "pose_override_curve_count": total_pose_override_curves,
        "pose_override_keypoint_count": total_pose_override_keypoints,
        "track_curve_count": total_track_curves,
        "track_keypoint_count": total_track_keypoints,
        "omitted_zero_track_count": total_omitted_zero_tracks,
        "blender_timing": dict(blender_timing),
        "skin_extras_keys": tuple(binding.skin_extras.keys()),
        "sparse_clip_count": sparse_clip_count,
        "dense_clip_count": dense_clip_count,
        "pose_template_curve_count": sparse_template_curve_count,
        "pose_template_keypoint_count": sparse_template_keypoint_count,
    }
