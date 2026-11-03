from __future__ import annotations

import math
import os
import time
from contextlib import nullcontext
from dataclasses import dataclass

import bpy
import numpy as np

from ...animation.domain.rig.naming import merged_bone_name
from ...animation.model.clip.metadata import (
    ANIMATION_SCHEMA,
    FPS,
    SKIN_EXTRAS_SNAPSHOT_KEY,
    SOURCE_REST_SNAPSHOT_KEY,
    TRACKS_IMPORTED_KEY,
    AnimationMetadataError,
    normalize_animation_extras,
    track_payload_duration,
)
from ...assetio.values import plain_value
from ...bartmoss.arrays import all_close
from ...bartmoss.curve import (
    sample_frame_grid,
    sample_linear,
    sample_quaternions_xyzw,
    sample_step,
)
from ...bartmoss.hierarchy import bone_basis_corrections, local_matrices_to_model
from ...bartmoss.matrix import RIGID_TOLERANCE
from ...bartmoss.quaternion import (
    product_matrix_wxyz,
    rotate_vector_xyzw,
    wxyz_from_matrices,
    wxyz_from_xyzw,
)
from ...bartmoss.trs import (
    compose_matrices,
    decompose_matrices,
)
from ...blender.action_metadata import (
    apply_action_extras,
    apply_skin_extras,
    clip_action_name,
    new_clip_action,
    store_action_source,
    store_json_snapshot,
)
from ...blender.animation_context import track_animation_import_state
from ...blender.armature import inheritance_issue, rest_model_matrices
from ...blender.context import BlenderContextSnapshot
from ...blender.event_markers import sync_markers_from_events
from ...blender.keyframes import (
    action_curve_map,
    assign_action_with_slot,
    bulk_set_keyframes,
    get_action_fcurves,
    property_curve_fingerprint,
    transform_curve_fingerprint,
    write_pose_curves,
)
from ...blender.tracks import import_anim_tracks, prepare_anim_track_properties
from ...blender.transactions import (
    DatablockImportTransaction,
    child_import_savepoint,
    current_import_transaction,
    raise_if_rollback_incomplete,
    rollback_import_child,
    track_created_datablock,
)
from ...core.log import get_logger
from ...gltf.accessors import GLTFAccessorReader
from ...gltf.container import GLBContainer, GLBContainerError, read_gltf_container
from ...gltf.mesh_contract import validate_direct_extensions
from ...gltf.provenance import (
    ORIGIN_PLUGIN,
    mark_origin,
)
from ...gltf.skeleton import (
    GLTFSkeletonError,
    SamplingContext,
    SkeletonBinding,
    build_node_hierarchy,
    build_sampling_context,
    build_skeleton_binding,
)
from ...materials.blender.skin_runtime import bind_skin_materials_for_armature
from ...redSpace.contracts import (
    RIG_SPACE_CONTRACT_CURRENT,
    SOURCE_REST_SPACE_CONTRACT,
)
from ...redSpace.transforms import (
    gltf_relative_to_blender,
    gltf_relative_to_blender_factors,
    gltf_rest_relative_to_blender,
)
from ..rig.gltf import build_rest_armature_from_binding

_LOG = get_logger(__name__)

_SUPPORTED_GLTF_INTERPOLATIONS = frozenset({"LINEAR", "STEP"})

# Below the near-frame key offsets WolvenKit writes on purpose, so key times survive import and export.
_FRAME_SNAP_TOLERANCE = 1e-5
# glTF stores rotations x, y, z, w; Blender pose channels hold w, x, y, z.
_XYZW_TO_WXYZ = np.eye(4)[[3, 0, 1, 2]]


class DirectAnimationImportError(RuntimeError):
    pass


class UnsupportedDirectAnimation(DirectAnimationImportError):
    pass


class DenseBasisRequired(UnsupportedDirectAnimation):
    """The clip is directly importable but requires dense basis conversion"""



_CLIP_DATA_ERRORS = (DirectAnimationImportError, AnimationMetadataError, ValueError)


@dataclass(frozen=True)
class SampledAnimation:
    name: str
    frames: np.ndarray
    model_matrices: np.ndarray | None
    relative_matrices: np.ndarray
    extras: dict
    duration_seconds: float = 0.0
    has_scale_channels: bool = False
    source_channels: tuple[ParsedGLTFChannel, ...] = ()


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
    scale_channels: tuple[SparsePropertyChannel | None, ...]
    extras: dict
    frame_count: int
    source_keypoints: int
    duration_seconds: float = 0.0
    source_channels: tuple[ParsedGLTFChannel, ...] = ()


@dataclass(frozen=True)
class SparseConversionContext:
    node_to_joint: dict[int, int]
    translation_rotations: np.ndarray
    translation_offsets: np.ndarray
    # Per joint: the source rotation (x, y, z, w) to the pose rotation (w, x, y, z), as one matrix product.
    rotation_matrices: np.ndarray
    default_locations: np.ndarray
    default_rotations_wxyz: np.ndarray
    pivot_offsets: np.ndarray


@dataclass(frozen=True)
class SparsePoseBase:
    location_values: np.ndarray
    rotation_values_wxyz: np.ndarray
    location_mask: np.ndarray
    rotation_mask: np.ndarray


@dataclass(frozen=True)
class TargetBinding:
    bone_names: tuple[str, ...]
    pose_bones: tuple
    rest_matrices: np.ndarray
    inverse_rest_matrices: np.ndarray
    inverse_rest_relative: np.ndarray
    basis_corrections: np.ndarray
    location_paths: tuple[str, ...]
    rotation_paths: tuple[str, ...]
    scale_paths: tuple[str, ...]
    fast_numpy_basis: bool
    merged_target: bool


class AccessorReader(GLTFAccessorReader):
    """Cache shared animation inputs without retaining every decoded clip"""

    def __init__(self, glb):
        super().__init__(glb, error_type=DirectAnimationImportError)
        usage = {}
        for animation in self.document.get("animations", ()):
            for sampler in animation.get("samplers", ()):
                for key in ("input", "output"):
                    index = sampler.get(key)
                    if index is not None:
                        usage[index] = usage.get(index, 0) + 1
        self.cacheable = {index for index, count in usage.items() if count > 1}
        self.cache = {}

    def read(self, accessor_index):
        cached = self.cache.get(accessor_index)
        if cached is not None:
            return cached
        result = super().read(accessor_index, dtype=np.float64)
        if accessor_index in self.cacheable:
            self.cache[accessor_index] = result
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

    for channel_index, channel in enumerate(animation.get("channels", ())):
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

        input_layout, output_layout = (
            reader.accessors[input_accessor],
            reader.accessors[output_accessor],
        )
        if (
            input_layout.get("type") != "SCALAR"
            or input_layout.get("componentType") != 5126
        ):
            raise DirectAnimationImportError(
                "Animation input keys must use FLOAT SCALAR seconds."
            )
        expected_type = "VEC4" if path == "rotation" else "VEC3"
        if (
            output_layout.get("type") != expected_type
            or output_layout.get("componentType") != 5126
        ):
            raise DirectAnimationImportError(
                f"Animation {path} output must use FLOAT {expected_type} values."
            )

        times = np.asarray(reader.read(input_accessor), dtype=np.float64).reshape(-1)
        if not len(times):
            seen_targets.discard(key)
            continue
        if times[0] < 0.0 or (times[1:] <= times[:-1]).any():
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
        if (
            path == "rotation"
            and not (
                np.abs(np.sqrt((values * values).sum(axis=1)) - 1.0) <= 1.0e-3
            ).all()
        ):
            raise DirectAnimationImportError(
                "Animation rotations must contain unit quaternions."
            )
        if not np.isfinite(times).all() or not np.isfinite(values).all():
            raise DirectAnimationImportError(
                f"Animation sampler {sampler_index} contains non-finite data."
            )
        yield ParsedGLTFChannel(
            node_index=node_index,
            joint_index=joint_index,
            path=path,
            interpolation=interpolation,
            times=times,
            values=values,
            sampler_index=sampler_index,
        )


def _normalized_animation_extras(animation: dict, animation_index: int) -> dict:
    return normalize_animation_extras(
        animation.get("extras"),
        label=f"Animation {animation.get('name') or animation_index!r} extras",
        error_type=DirectAnimationImportError,
        compatible_schema=True,
    )


def _declared_schema_version(animation: dict):
    extras = animation.get("extras")
    schema = extras.get("schema") if isinstance(extras, dict) else None
    return schema.get("version") if isinstance(schema, dict) else None


def _schema_warnings(file_name, versions) -> list[str]:
    warnings = []
    current = ANIMATION_SCHEMA["version"]
    for version, count in sorted(
        versions.items(), key=lambda item: (item[0] is not None, item[0] or 0)
    ):
        if version is None:
            warnings.append(
                f"{file_name}: {count} clip(s) declare no animation schema; "
                f"metadata was read as schema version {current} with defaults"
            )
        else:
            relation = "newer" if version > current else "older"
            warnings.append(
                f"{file_name}: {count} clip(s) use {relation} animation schema "
                f"version {version} (this add-on reads version {current}); "
                "missing metadata was filled with defaults"
            )
    return warnings


def _validate_track_binding_counts(
    binding: SkeletonBinding, extras: dict, animation_name
) -> None:
    track_names = binding.skin_extras.get("trackNames") or ()
    has_track_payload = any(
        extras.get(label, ()) for label in ("trackKeys", "constTrackKeys")
    )
    if has_track_payload and not track_names:
        raise DirectAnimationImportError(
            f"Animation {animation_name!r} contains track keys, but the skin exposes no trackNames."
        )
    for label in ("trackKeys", "constTrackKeys"):
        for entry in extras.get(label, ()) or ():
            track_index = int(entry.get("trackIndex", -1))
            if track_index >= len(track_names):
                raise DirectAnimationImportError(
                    f"Animation {animation_name!r} {label} references track {track_index}, "
                    f"but the rig exposes only {len(track_names)} tracks."
                )


def _snap_frames_to_grid(frames):
    """Snap float32 time-quantization noise onto the integer frame grid"""
    frames = np.asarray(frames, dtype=np.float64)
    nearest = np.round(frames)
    snap = np.abs(frames - nearest) <= _FRAME_SNAP_TOLERANCE
    if snap.any():
        frames = frames.copy()
        frames[snap] = nearest[snap]
    return frames


def _clip_end_frame(maximum_time, fps: float = FPS) -> int:
    """Resolve the last frame index for a clip, absorbing float32 time error"""
    scaled = float(maximum_time) * fps
    nearest = round(scaled)
    if abs(scaled - nearest) <= _FRAME_SNAP_TOLERANCE:
        return max(0, int(nearest))
    return max(0, int(math.ceil(scaled)))


def sample_animation(
    glb: GLBContainer,
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
    context = context or build_sampling_context(build_node_hierarchy(document), binding)
    extras = _normalized_animation_extras(animation, animation_index)
    animation_name = animation.get("name") or animation_index
    _validate_track_binding_counts(binding, extras, animation_name)
    channel_records = tuple(
        _parse_gltf_channel(
            animation,
            animation_index,
            reader,
            context.node_to_joint,
        )
    )

    maximum_time = max(
        (float(channel.times[-1]) for channel in channel_records),
        default=0.0,
    )
    has_scale_channels = any(channel.path == "scale" for channel in channel_records)
    source_frames = (
        np.concatenate(
            [_snap_frames_to_grid(channel.times * fps) for channel in channel_records]
        )
        if channel_records
        else np.empty(0, dtype=np.float64)
    )
    final_frame = float(_snap_frames_to_grid(np.asarray([maximum_time * fps]))[0])
    frames = sample_frame_grid(0.0, final_frame, source_frames)
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
        channel_times = _snap_frames_to_grid(channel.times * fps) / fps
        if channel.path == "rotation":
            rotations[:, channel.node_index] = sample_quaternions_xyzw(
                channel_times,
                channel.values,
                sample_times,
                channel.interpolation,
            )
        else:
            sampled_values = (
                sample_step(channel_times, channel.values, sample_times)
                if channel.interpolation == "STEP"
                else sample_linear(channel_times, channel.values, sample_times)
            )
            if channel.path == "translation":
                translations[:, channel.node_index] = sampled_values
            else:
                scales[:, channel.node_index] = sampled_values

    local = compose_matrices(
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
        relative_blender[:, joint_index] = gltf_relative_to_blender(
            relative_gltf[:, joint_index],
            parent_index < 0,
        )

    model_blender = None
    if include_model_matrices:
        model_blender = local_matrices_to_model(
            relative_blender,
            binding.source_parent_indices,
            binding.topological_joint_indices,
        )

    return SampledAnimation(
        name=str(animation.get("name") or f"Animation_{animation_index:03d}"),
        frames=frames,
        model_matrices=model_blender,
        relative_matrices=relative_blender,
        extras=extras,
        duration_seconds=max(float(maximum_time), track_payload_duration(extras)),
        has_scale_channels=has_scale_channels,
        source_channels=channel_records,
    )


def _constant_property_channel(frames, values, interpolation):
    frames = np.asarray(frames, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    if len(frames) > 1 and np.all(np.abs(values - values[0]) <= 1e-10):
        frames = frames[:1].copy()
        values = values[:1].copy()
    return SparsePropertyChannel(frames, values, interpolation)


def _rigid_inverse(matrix):
    inverse = np.eye(4, dtype=np.float64)
    rotation = matrix[:3, :3].T
    inverse[:3, :3] = rotation
    inverse[:3, 3] = -rotation @ matrix[:3, 3]
    return inverse


def build_sparse_conversion_context(
    binding: SkeletonBinding,
    context: SamplingContext,
    target: TargetBinding,
) -> SparseConversionContext:
    """Factor each joint's pose basis into left/right constants around the source TRS"""
    joint_count = len(binding.bone_names)
    translation_rotations = np.empty((joint_count, 3, 3), dtype=np.float64)
    translation_offsets = np.empty((joint_count, 3), dtype=np.float64)
    rotation_matrices = np.empty((joint_count, 4, 4), dtype=np.float64)
    default_locations = np.empty((joint_count, 3), dtype=np.float64)
    default_rotations = np.empty((joint_count, 4), dtype=np.float64)
    pivot_offsets = np.empty((joint_count, 3), dtype=np.float64)

    for joint_index, node_index in enumerate(binding.joint_nodes):
        correction = target.basis_corrections[joint_index]
        conversion_left, conversion_right = gltf_relative_to_blender_factors(
            binding.source_parent_indices[joint_index] < 0
        )
        right_matrix = conversion_right @ correction
        right_rotation = wxyz_from_matrices(right_matrix[:3, :3].reshape(1, 3, 3))[0]
        prefix = context.joint_default_prefixes[joint_index]
        left_matrix = (
            _rigid_inverse(correction)
            @ target.inverse_rest_relative[joint_index]
            @ conversion_left
            @ prefix
        )
        left_axes = left_matrix[:3, :3]
        scales = np.linalg.norm(left_axes, axis=0)
        normalized_left = left_axes / np.maximum(scales[None, :], 1e-15)
        if not np.allclose(scales, scales[:1], atol=RIGID_TOLERANCE) or not np.allclose(
            normalized_left.T @ normalized_left, np.eye(3), atol=RIGID_TOLERANCE
        ):
            raise UnsupportedDirectAnimation(
                "Sparse animation conversion requires rigid source and target bases."
            )
        left_rotation = wxyz_from_matrices(normalized_left.reshape(1, 3, 3))[0]
        translation_rotations[joint_index] = left_axes
        translation_offsets[joint_index] = left_matrix[:3, 3]
        rotation_matrices[joint_index] = (
            product_matrix_wxyz(left_rotation, right_rotation) @ _XYZW_TO_WXYZ
        )
        pivot_offsets[joint_index] = right_matrix[:3, 3]

        source_default = context.default_rotations[node_index]
        default_locations[joint_index] = (
            left_axes
            @ (
                context.default_translations[node_index]
                + rotate_vector_xyzw(source_default, right_matrix[:3, 3])
            )
            + left_matrix[:3, 3]
        )
        default_rotation = rotation_matrices[joint_index] @ source_default
        default_rotations[joint_index] = default_rotation / max(
            np.linalg.norm(default_rotation), 1e-15
        )

    return SparseConversionContext(
        node_to_joint=context.node_to_joint,
        translation_rotations=translation_rotations,
        translation_offsets=translation_offsets,
        rotation_matrices=rotation_matrices,
        default_locations=default_locations,
        default_rotations_wxyz=default_rotations,
        pivot_offsets=pivot_offsets,
    )


def _pivot_location_channel(
    conversion, context, node_index, joint_index, translation, rotation, fps
):
    """Sample a pivot joint's location from its translation and rotation channels"""
    interpolations = {
        channel[2] for channel in (translation, rotation) if channel is not None
    }
    if len(interpolations) != 1 or not interpolations <= {"LINEAR", "STEP"}:
        raise DenseBasisRequired(
            "A rest pivot offset with mixed or cubic interpolation requires dense basis conversion."
        )
    interpolation = interpolations.pop()
    frames = np.unique(
        np.concatenate(
            [channel[3] for channel in (translation, rotation) if channel is not None]
        )
    )
    seconds = frames / fps
    if translation is None:
        translations = np.repeat(
            np.asarray(context.default_translations[node_index], dtype=np.float64)[
                None
            ],
            len(frames),
            axis=0,
        )
    elif interpolation == "STEP":
        translations = sample_step(translation[0], translation[1], seconds)
    else:
        translations = sample_linear(translation[0], translation[1], seconds)
    if rotation is None:
        rotations = np.repeat(
            np.asarray(context.default_rotations[node_index], dtype=np.float64)[None],
            len(frames),
            axis=0,
        )
    else:
        rotations = sample_quaternions_xyzw(
            rotation[0], rotation[1], seconds, interpolation
        )
    source = translations + rotate_vector_xyzw(
        rotations, conversion.pivot_offsets[joint_index]
    )
    return _constant_property_channel(
        frames,
        _transform_sparse_translation(conversion, joint_index, source),
        interpolation,
    )


def _transform_sparse_translation(conversion, joint_index, values):
    values = np.asarray(values, dtype=np.float64).reshape(-1, 3)
    rotation = conversion.translation_rotations[joint_index]
    return values @ rotation.T + conversion.translation_offsets[joint_index]


def _transform_sparse_rotation(conversion, joint_index, values):
    values = np.asarray(values, dtype=np.float64).reshape(-1, 4)
    result = values @ conversion.rotation_matrices[joint_index].T
    result /= np.maximum(np.linalg.norm(result, axis=1)[:, None], 1e-15)
    if len(result) > 1:
        dots = np.sum(result[:-1] * result[1:], axis=1)
        flips = np.cumprod(np.where(dots < 0.0, -1.0, 1.0))
        result[1:] *= flips[:, None]
    return result


def sparse_animation(
    glb: GLBContainer,
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
    context = context or build_sampling_context(build_node_hierarchy(document), binding)
    extras = _normalized_animation_extras(animation, animation_index)
    animation_name = animation.get("name") or animation_index
    _validate_track_binding_counts(binding, extras, animation_name)
    conversion = conversion or build_sparse_conversion_context(binding, context, target)
    location_channels = [None] * len(binding.bone_names)
    rotation_channels = [None] * len(binding.bone_names)
    scale_channels = [None] * len(binding.bone_names)
    seen_targets = set()
    maximum_time = track_payload_duration(extras)
    source_keypoints = 0
    pivot_joints = np.linalg.norm(conversion.pivot_offsets, axis=1) > 1e-8
    pivot_translations = {}
    pivot_rotations = {}

    source_channels = tuple(
        _parse_gltf_channel(
            animation,
            animation_index,
            reader,
            conversion.node_to_joint,
        )
    )
    for channel in source_channels:
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
            if all_close(values, default_scale.reshape(1, 3), 2e-6):
                continue
            if pivot_joints[joint_index]:
                raise DenseBasisRequired(
                    "Animated scale on a bone with a rest pivot offset requires dense basis conversion."
                )
            if np.any(values <= 1e-8) or not all_close(
                default_scale, default_scale[0], 2e-6
            ):
                raise DenseBasisRequired(
                    "Mirrored, singular or non-uniform rest scale requires dense basis conversion."
                )
            _, conversion_right = gltf_relative_to_blender_factors(
                binding.source_parent_indices[joint_index] < 0
            )
            scale_axes = (conversion_right @ target.basis_corrections[joint_index])[
                :3, :3
            ]
            if not np.allclose(
                np.abs(scale_axes).max(axis=0), 1.0, atol=1e-6
            ) and not np.allclose(values, values[:, :1], atol=1e-6):
                raise UnsupportedDirectAnimation(
                    "Non-uniform scale would introduce shear in the target bone basis."
                )
            rest_inverse_scale = np.linalg.norm(
                conversion.translation_rotations[joint_index][:, 0]
            )
            transformed = (values * rest_inverse_scale) @ np.square(scale_axes)
            scale_channels[joint_index] = _constant_property_channel(
                _snap_frames_to_grid(times * fps), transformed, interpolation
            )
            source_keypoints += len(times) * 3
            continue

        source_keypoints += len(times) * (3 if path == "translation" else 4)
        channel_frames = _snap_frames_to_grid(times * fps)
        source_values = values
        if (
            path == "rotation"
            and interpolation == "LINEAR"
            and len(times) > 1
            and np.any(np.diff(channel_frames) > 1.0 + 1e-5)
        ):
            sampled_frames = sample_frame_grid(
                0.0, float(channel_frames[-1]), channel_frames
            )
            values = sample_quaternions_xyzw(
                times, values, sampled_frames / fps, "LINEAR"
            )
            channel_frames = sampled_frames
        if pivot_joints[joint_index]:
            stash = pivot_translations if path == "translation" else pivot_rotations
            stash[joint_index] = (times, source_values, interpolation, channel_frames)
            if path == "translation":
                continue
        transformed = (
            _transform_sparse_translation(conversion, joint_index, values)
            if path == "translation"
            else _transform_sparse_rotation(conversion, joint_index, values)
        )
        if path == "translation":
            if pose_base is not None and pose_base.location_mask[joint_index]:
                base_value = pose_base.location_values[joint_index]
                if all_close(transformed, base_value.reshape(1, 3), 1e-9):
                    continue
            location_channels[joint_index] = _constant_property_channel(
                channel_frames, transformed, interpolation
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
                if all_close(transformed, alignment_value.reshape(1, 4), 1e-9):
                    continue
            rotation_channels[joint_index] = _constant_property_channel(
                channel_frames, transformed, interpolation
            )

    for joint_index in np.flatnonzero(pivot_joints):
        translation = pivot_translations.get(int(joint_index))
        rotation = pivot_rotations.get(int(joint_index))
        if translation is None and rotation is None:
            continue
        location = _pivot_location_channel(
            conversion,
            context,
            binding.joint_nodes[joint_index],
            int(joint_index),
            translation,
            rotation,
            fps,
        )
        seen_targets.add((int(joint_index), "translation"))
        if (
            pose_base is not None
            and pose_base.location_mask[joint_index]
            and all_close(
                location.values,
                pose_base.location_values[joint_index].reshape(1, 3),
                1e-9,
            )
        ):
            continue
        location_channels[joint_index] = location

    if pose_base is not None or include_defaults:
        for joint_index in range(len(binding.bone_names)):
            if (
                location_channels[joint_index] is None
                and (joint_index, "translation") not in seen_targets
                and (
                    include_defaults
                    or not (
                        pose_base.location_mask[joint_index]
                        and all_close(
                            conversion.default_locations[joint_index],
                            pose_base.location_values[joint_index],
                            1e-9,
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
                        )
                        >= 1.0 - 1e-9
                    )
                )
            ):
                default_rotation = conversion.default_rotations_wxyz[joint_index].copy()
                if (
                    pose_base is not None
                    and np.dot(
                        default_rotation,
                        pose_base.rotation_values_wxyz[joint_index],
                    )
                    < 0.0
                ):
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
        scale_channels=tuple(scale_channels),
        extras=extras,
        frame_count=max(1, _clip_end_frame(maximum_time, fps) + 1),
        source_keypoints=source_keypoints,
        duration_seconds=float(maximum_time),
        source_channels=source_channels,
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


def _resolve_target_bone_names(armature, binding: SkeletonBinding) -> tuple[str, ...]:
    pose_bones = armature.pose.bones
    resolved = []
    used = set()
    for source_name in binding.bone_names:
        target_name = (
            source_name
            if pose_bones.get(source_name) is not None
            else merged_bone_name(source_name)
        )
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
            "Select a supported rig-import armature or a mesh bound to one "
            "before importing animations."
        )
    contract = str(armature.data.get("cp77_rig_space_contract", ""))
    if contract != RIG_SPACE_CONTRACT_CURRENT:
        raise UnsupportedDirectAnimation(
            "The selected armature was not imported with the supported JSON rig-space contract."
        )

    target_names = _resolve_target_bone_names(armature, binding)
    for source_name, target_name in zip(binding.bone_names, target_names):
        pose_bone = armature.pose.bones[target_name]
        issue = inheritance_issue(pose_bone.bone)
        if issue:
            raise UnsupportedDirectAnimation(
                f"Target bone {target_name!r} for source joint {source_name!r} {issue}."
            )
        if getattr(pose_bone, "rotation_mode", "QUATERNION") != "QUATERNION":
            pose_bone.rotation_mode = "QUATERNION"
    return target_names


def _source_rest_snapshot(binding, target_binding, document, context) -> dict:
    matrices = np.linalg.inv(target_binding.inverse_rest_relative)
    authored_transforms = []
    for index, node_index in enumerate(binding.joint_nodes):
        node = document["nodes"][node_index]
        if "matrix" in node or not np.allclose(
            context.joint_default_prefixes[index], np.eye(4), atol=1e-12, rtol=0
        ):
            authored_transforms.append(None)
        else:
            authored_transforms.append(
                {
                    key: node[key]
                    for key in ("translation", "rotation", "scale")
                    if key in node
                }
            )
    return {
        "version": 1,
        "space": SOURCE_REST_SPACE_CONTRACT,
        "boneNames": list(binding.bone_names),
        "matrices": matrices.reshape(len(matrices), 16).tolist(),
        "gltfTransforms": authored_transforms,
    }


def _source_channels_snapshot(action, armature, target_binding, channels) -> dict:
    """Preserve authored channels and their absence while imported curves remain unchanged"""
    curve_map = action_curve_map(action, armature)
    authored = {
        (int(channel.joint_index), str(channel.path)): channel for channel in channels
    }
    payload = []
    for joint_index in range(len(target_binding.bone_names)):
        paths = {
            "location": target_binding.location_paths[joint_index],
            "rotation_quaternion": target_binding.rotation_paths[joint_index],
            "scale": target_binding.scale_paths[joint_index],
        }
        transform_fingerprint = None
        if np.any(np.abs(target_binding.basis_corrections[joint_index, :3, 3]) > 1e-8):
            transform_fingerprint = transform_curve_fingerprint(curve_map, paths)
        for path, property_name, width in (
            ("translation", "location", 3),
            ("rotation", "rotation_quaternion", 4),
            ("scale", "scale", 3),
        ):
            entry = {
                "jointIndex": joint_index,
                "path": path,
                "curveFingerprint": transform_fingerprint
                or property_curve_fingerprint(curve_map, paths[property_name], width),
            }
            channel = authored.get((joint_index, path))
            if channel is None:
                entry["omitted"] = True
            else:
                entry.update(
                    interpolation=str(channel.interpolation),
                    times=[float(value) for value in channel.times],
                    values=[
                        [float(component) for component in row]
                        for row in channel.values
                    ],
                )
            payload.append(entry)
    return {"version": 1, "channels": payload}


def build_target_binding(
    armature,
    binding: SkeletonBinding,
    context: SamplingContext,
    target_names: tuple[str, ...] | None = None,
) -> TargetBinding:
    target_names = target_names or _resolve_target_bone_names(armature, binding)
    pose_bones = tuple(armature.pose.bones[name] for name in target_names)
    # Edit bones carry no scale or shear: anything beyond a rotation in matrix_local is float32 noise, which Blender's
    # roll math amplifies for a bone pointing nearly opposite its parent's Y axis.
    rest_matrices = rest_model_matrices(pose_bone.bone for pose_bone in pose_bones)
    inverse_rest = np.linalg.inv(rest_matrices)

    source_rest_relative = gltf_rest_relative_to_blender(
        context.default_local_matrices,
        context.joint_default_prefixes,
        binding.joint_nodes,
        binding.source_parent_indices,
    )
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
    rest_orthogonality = np.matmul(np.swapaxes(normalized_rest, 1, 2), normalized_rest)
    # A uniform rest scale commutes with every rotation, so pose bases relative to it stay free of shear.
    fast_numpy_basis = bool(
        np.all(source_scales > RIGID_TOLERANCE)
        and np.allclose(source_scales, source_scales[:, :1], atol=RIGID_TOLERANCE)
        and np.allclose(source_orthogonality, np.eye(3), atol=RIGID_TOLERANCE)
        and np.allclose(rest_scales, 1.0, atol=RIGID_TOLERANCE)
        and np.allclose(rest_orthogonality, np.eye(3), atol=RIGID_TOLERANCE)
        and not any(inheritance_issue(pose_bone.bone) for pose_bone in pose_bones)
    )
    if not fast_numpy_basis:
        raise UnsupportedDirectAnimation(
            "The selected rig-import target contains non-rigid bone bases or "
            "unsupported inheritance settings."
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
        basis_corrections=bone_basis_corrections(
            source_rest_relative, binding.source_parent_indices, rest_matrices
        ),
        location_paths=tuple(pb.path_from_id("location") for pb in pose_bones),
        rotation_paths=tuple(
            pb.path_from_id("rotation_quaternion") for pb in pose_bones
        ),
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
            np.matmul(
                np.linalg.inv(target.basis_corrections[joint_index]),
                target.inverse_rest_relative[joint_index],
            ),
            np.matmul(
                sampled.relative_matrices[:, joint_index],
                target.basis_corrections[joint_index],
            ),
        )

    axes = basis[..., :3, :3]
    rotations = axes / np.maximum(np.linalg.norm(axes, axis=-2)[..., None, :], 1e-15)
    if not np.allclose(
        np.swapaxes(rotations, -1, -2) @ rotations, np.eye(3), atol=RIGID_TOLERANCE
    ):
        raise UnsupportedDirectAnimation(
            "Animation transforms introduce shear that Blender pose channels cannot represent."
        )
    locations, rotations_xyzw, scales = decompose_matrices(basis)
    return locations, wxyz_from_xyzw(rotations_xyzw), scales


def _basis_channels(
    binding: SkeletonBinding,
    sampled: SampledAnimation,
    target: TargetBinding,
):
    locations, rotations, scales = _basis_channels_numpy(binding, sampled, target)

    for joint_index in range(len(binding.bone_names)):
        dots = np.sum(rotations[:-1, joint_index] * rotations[1:, joint_index], axis=1)
        flips = np.cumprod(np.where(dots < 0.0, -1.0, 1.0))
        rotations[1:, joint_index] *= flips[:, None]
    return locations, rotations, scales


def _replace_curve_keys(
    fcurves,
    data_path,
    index,
    group_name,
    frames,
    values,
    interpolation="LINEAR",
):
    curve = fcurves.ensure(data_path, index=index, group_name=group_name)
    previous_count = len(curve.keyframe_points)
    if previous_count:
        curve.keyframe_points.clear()
    new_count = bulk_set_keyframes(
        curve, frames, values, interpolation=interpolation, collapse_constant=True
    )
    return curve, previous_count, new_count


def _build_sparse_pose_template(
    armature,
    pose_base,
    target_binding,
):
    """Seed complete bone transforms so switching Actions cannot retain a prior pose"""
    action = track_created_datablock(
        "actions",
        bpy.data.actions.new("__CP77_DIRECT_ANIM_POSE_TEMPLATE__"),
    )
    action.use_fake_user = False
    fcurves = get_action_fcurves(action, armature, create=True)
    curve_count = 0
    keypoint_count = 0
    try:
        for joint_index, bone_name in enumerate(target_binding.bone_names):
            location = pose_base.location_values[joint_index]
            rotation = pose_base.rotation_values_wxyz[joint_index]
            if pose_base.location_mask[joint_index]:
                path = target_binding.location_paths[joint_index]
                for component in range(3):
                    curve = fcurves.ensure(path, index=component, group_name=bone_name)
                    keypoint_count += bulk_set_keyframes(
                        curve,
                        (0.0,),
                        (location[component],),
                        interpolation="LINEAR",
                        collapse_constant=True,
                    )
                    curve_count += 1
            if pose_base.rotation_mask[joint_index]:
                path = target_binding.rotation_paths[joint_index]
                for component in range(4):
                    curve = fcurves.ensure(path, index=component, group_name=bone_name)
                    keypoint_count += bulk_set_keyframes(
                        curve,
                        (0.0,),
                        (rotation[component],),
                        interpolation="LINEAR",
                        collapse_constant=True,
                    )
                    curve_count += 1
            for component in range(3):
                curve = fcurves.ensure(
                    target_binding.scale_paths[joint_index],
                    index=component,
                    group_name=bone_name,
                )
                keypoint_count += bulk_set_keyframes(
                    curve,
                    (0.0,),
                    (1.0,),
                    interpolation="LINEAR",
                    collapse_constant=True,
                )
                curve_count += 1
        return action, curve_count, keypoint_count
    except Exception:
        if bpy.data.actions.get(action.name) is action:
            bpy.data.actions.remove(action)
        raise


def _write_sparse_pose_action(
    armature,
    sparse,
    import_tracks,
    target_binding,
    template_action=None,
    template_curve_count=0,
    template_keypoint_count=0,
    timing_totals=None,
):
    timing_totals = timing_totals if timing_totals is not None else {}
    shell_started = time.perf_counter()
    if template_action is not None:
        action = track_created_datablock("actions", template_action.copy())
        action.name = clip_action_name(sparse.name, armature)
        action.use_fake_user = True
    else:
        action = new_clip_action(sparse.name, armature)
    try:
        fcurves = get_action_fcurves(action, armature, create=True)
        timing_totals["action_shell"] = timing_totals.get("action_shell", 0.0) + (
            time.perf_counter() - shell_started
        )

        pose_started = time.perf_counter()
        pose_curve_count = int(template_curve_count)
        pose_keypoint_count = int(template_keypoint_count)
        pose_override_curve_count = 0
        pose_override_keypoint_count = 0
        for joint_index, bone_name in enumerate(target_binding.bone_names):
            properties = (
                (
                    sparse.location_channels[joint_index],
                    target_binding.location_paths[joint_index],
                    3,
                ),
                (
                    sparse.rotation_channels[joint_index],
                    target_binding.rotation_paths[joint_index],
                    4,
                ),
                (
                    sparse.scale_channels[joint_index],
                    target_binding.scale_paths[joint_index],
                    3,
                ),
            )
            for channel, path, width in properties:
                if channel is None:
                    continue
                for component in range(width):
                    was_existing = (
                        fcurves.find(data_path=path, index=component) is not None
                    )
                    _, previous_count, new_count = _replace_curve_keys(
                        fcurves,
                        path,
                        component,
                        bone_name,
                        channel.frames,
                        channel.values[:, component],
                        interpolation=channel.interpolation,
                    )
                    pose_keypoint_count += new_count - previous_count
                    pose_override_curve_count += 1
                    pose_override_keypoint_count += new_count
                    if not was_existing:
                        pose_curve_count += 1
        timing_totals["pose_curves"] = timing_totals.get("pose_curves", 0.0) + (
            time.perf_counter() - pose_started
        )

        metadata_started = time.perf_counter()
        if apply_action_extras(action, sparse.extras):
            sync_markers_from_events(action)
        timing_totals["metadata"] = timing_totals.get("metadata", 0.0) + (
            time.perf_counter() - metadata_started
        )

        track_stats = {
            "curve_count": 0,
            "keypoint_count": 0,
            "omitted_zero_count": 0,
        }
        if import_tracks:
            tracks_started = time.perf_counter()
            track_stats = (
                import_anim_tracks(
                    action,
                    armature=armature,
                    ensure_properties=False,
                    extras=sparse.extras,
                    replace_existing=False,
                )
                or track_stats
            )
            timing_totals["track_curves"] = timing_totals.get("track_curves", 0.0) + (
                time.perf_counter() - tracks_started
            )

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
    timing_totals = timing_totals if timing_totals is not None else {}
    shell_started = time.perf_counter()
    action = new_clip_action(sampled.name, armature)
    try:
        fcurves = get_action_fcurves(action, armature, create=True)
        timing_totals["action_shell"] = timing_totals.get("action_shell", 0.0) + (
            time.perf_counter() - shell_started
        )

        pose_started = time.perf_counter()
        locations, rotations, scales = _basis_channels(binding, sampled, target_binding)
        pose_curve_count, pose_keypoint_count = write_pose_curves(
            fcurves,
            target_binding.pose_bones,
            sampled.frames,
            locations,
            rotations,
            scales,
        )
        timing_totals["pose_curves"] = timing_totals.get("pose_curves", 0.0) + (
            time.perf_counter() - pose_started
        )

        metadata_started = time.perf_counter()
        if apply_action_extras(action, sampled.extras):
            sync_markers_from_events(action)
        timing_totals["metadata"] = timing_totals.get("metadata", 0.0) + (
            time.perf_counter() - metadata_started
        )

        track_stats = {
            "curve_count": 0,
            "keypoint_count": 0,
            "omitted_zero_count": 0,
        }
        if import_tracks:
            tracks_started = time.perf_counter()
            track_stats = (
                import_anim_tracks(
                    action,
                    armature=armature,
                    ensure_properties=False,
                    extras=sampled.extras,
                    replace_existing=False,
                )
                or track_stats
            )
            timing_totals["track_curves"] = timing_totals.get("track_curves", 0.0) + (
                time.perf_counter() - tracks_started
            )

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


def _import_anims_glb_to_armature_impl(
    filepath: str,
    armature=None,
    *,
    import_tracks: bool = True,
    verbose: bool = False,
    assign_action: bool = True,
):
    started_at = time.perf_counter()
    glb = read_gltf_container(filepath)
    try:
        validate_direct_extensions(glb.document)
    except ValueError as error:
        raise DirectAnimationImportError(str(error)) from error
    parse_seconds = time.perf_counter() - started_at
    setup_started = time.perf_counter()
    if len(glb.document.get("skins") or ()) != 1:
        raise ValueError(
            "Direct CP77 animation and rig import requires exactly one skin."
        )
    hierarchy = build_node_hierarchy(glb.document)
    binding = build_skeleton_binding(glb.document, hierarchy)
    reader = AccessorReader(glb)
    sampling_context = build_sampling_context(hierarchy, binding)
    if armature is None:
        armature = build_rest_armature_from_binding(
            binding,
            sampling_context,
            source_label=os.path.abspath(filepath),
        )
    target_names = validate_target_armature(armature, binding)
    animations = glb.document.get("animations", ())
    if not animations:
        raise UnsupportedDirectAnimation("The GLB contains no animations.")
    file_name = os.path.basename(filepath)
    importable = []
    skipped_clips = []
    schema_versions = {}
    for animation_index, animation in enumerate(animations):
        try:
            _normalized_animation_extras(animation, animation_index)
        except DirectAnimationImportError as error:
            skipped_clips.append(f"{animation.get('name') or animation_index}: {error}")
            continue
        version = _declared_schema_version(animation)
        if version != ANIMATION_SCHEMA["version"]:
            schema_versions[version] = schema_versions.get(version, 0) + 1
        importable.append(animation_index)
    if not importable:
        raise DirectAnimationImportError(
            f"No animation clip in {file_name} has valid metadata; first error: {skipped_clips[0]}"
        )

    target_binding = build_target_binding(
        armature, binding, sampling_context, target_names
    )
    if not target_binding.fast_numpy_basis:
        _LOG.warning(
            "Target rig requires the Blender basis fallback; dense clips may be substantially slower"
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
        for base_animation_index in importable:
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
            except _CLIP_DATA_ERRORS:
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
                sparse_pose_base,
                target_binding,
            )
    setup_seconds = time.perf_counter() - setup_started

    animation_data = armature.animation_data_create()
    previous_action = animation_data.action
    previous_slot = getattr(animation_data, "action_slot", None)
    created_actions = []
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
        mark_origin(
            armature,
            ORIGIN_PLUGIN,
            source_path=filepath,
        )
        source_rest_snapshot = _source_rest_snapshot(
            binding, target_binding, glb.document, sampling_context
        )
        store_json_snapshot(armature, SKIN_EXTRAS_SNAPSHOT_KEY, skin_extras)
        store_json_snapshot(
            armature,
            SOURCE_REST_SNAPSHOT_KEY,
            source_rest_snapshot,
        )
        if not target_binding.merged_target:
            apply_skin_extras(armature, skin_extras)
        else:
            rig_path = skin_extras.get("rigPath")
            if rig_path is not None:
                armature["rigPath"] = plain_value(rig_path)
            track_names = skin_extras.get("trackNames") or ()
            armature["trackNames"] = {
                str(index): str(name) for index, name in enumerate(track_names)
            }

        if import_tracks and prepare_anim_track_properties(
            (animations[index].get("extras") or {} for index in importable),
            armature,
        ):
            bind_skin_materials_for_armature(armature)

        total_frames = 0
        sparse_clip_count = 0
        dense_clip_count = 0
        for clip_number, animation_index in enumerate(importable, start=1):
            clip_state = child_import_savepoint()
            conversion_started = time.perf_counter()
            try:
                sparse = None
                sampled = None
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
                if sparse is None:
                    sampled = sample_animation(
                        glb,
                        binding,
                        animation_index,
                        reader=reader,
                        context=sampling_context,
                        include_model_matrices=False,
                    )
                clip_conversion_seconds = time.perf_counter() - conversion_started
                clip_frame_count = (
                    sparse.frame_count if sparse is not None else len(sampled.frames)
                )
                action_started = time.perf_counter()
                if sparse is not None:
                    action, action_stats = _write_sparse_pose_action(
                        armature,
                        sparse,
                        import_tracks=import_tracks,
                        target_binding=target_binding,
                        template_action=sparse_template_action,
                        template_curve_count=sparse_template_curve_count,
                        template_keypoint_count=sparse_template_keypoint_count,
                        timing_totals=blender_timing,
                    )
                else:
                    action, action_stats = _write_pose_action(
                        armature,
                        binding,
                        sampled,
                        import_tracks=import_tracks,
                        target_binding=target_binding,
                        timing_totals=blender_timing,
                    )
                clip_action_seconds = time.perf_counter() - action_started
                # Persist the authoritative clip length so re-export preserves a static
                # tail even when the trailing keyframes hold a constant pose.
                mark_origin(
                    action,
                    ORIGIN_PLUGIN,
                    source_path=filepath,
                )
                action["cp77_direct_anim_frame_count"] = int(clip_frame_count)
                action[TRACKS_IMPORTED_KEY] = bool(import_tracks)
                action["cp77_direct_anim_duration_seconds"] = float(
                    sparse.duration_seconds
                    if sparse is not None
                    else sampled.duration_seconds
                )
                # Each action keeps the skin and rest it was imported with, for its own export.
                store_action_source(
                    action,
                    source_name=sparse.name if sparse is not None else sampled.name,
                    skin=skin_extras,
                    source_rest=source_rest_snapshot,
                    source_channels=_source_channels_snapshot(
                        action,
                        armature,
                        target_binding,
                        sparse.source_channels
                        if sparse is not None
                        else sampled.source_channels,
                    ),
                )
            except _CLIP_DATA_ERRORS as error:
                rollback_import_child(
                    clip_state,
                    f"animation clip {animations[animation_index].get('name') or animation_index}",
                )
                skipped_clips.append(
                    f"{animations[animation_index].get('name') or animation_index}: {error}"
                )
                continue
            if sparse is not None:
                sparse_clip_count += 1
            else:
                dense_clip_count += 1
            conversion_seconds += clip_conversion_seconds
            action_seconds += clip_action_seconds
            total_frames += clip_frame_count
            total_pose_curves += action_stats["pose_curves"]
            total_pose_keypoints += action_stats["pose_keypoints"]
            total_pose_override_curves += action_stats["pose_override_curves"]
            total_pose_override_keypoints += action_stats["pose_override_keypoints"]
            total_track_curves += action_stats["track_curves"]
            total_track_keypoints += action_stats["track_keypoints"]
            total_omitted_zero_tracks += action_stats["omitted_zero_tracks"]
            created_actions.append(action)
            if verbose and (
                clip_number == 1
                or clip_number % 10 == 0
                or clip_number == len(importable)
            ):
                _LOG.debug(
                    "Created %d/%d actions; latest=%s",
                    clip_number,
                    len(importable),
                    action.name,
                )

        if not created_actions:
            raise DirectAnimationImportError(
                f"No animation clip in {file_name} could be imported; first error: {skipped_clips[0]}"
            )

        if previous_action is not None:
            assign_action_with_slot(armature, previous_action)
            if previous_slot is not None and hasattr(animation_data, "action_slot"):
                try:
                    animation_data.action_slot = previous_slot
                except (TypeError, RuntimeError):
                    pass
        elif created_actions and assign_action:
            assign_action_with_slot(armature, created_actions[0])

    finally:
        # The template only seeds the clips; a failed import's actions, assignment and rig properties are restored by
        # the transaction that tracks them (see import_anims_glb_to_armature).
        if (
            sparse_template_action is not None
            and bpy.data.actions.get(sparse_template_action.name)
            is sparse_template_action
        ):
            bpy.data.actions.remove(sparse_template_action)

    elapsed_seconds = time.perf_counter() - started_at
    if verbose:
        _LOG.debug(
            "Timing: parse=%.3fs, setup=%.3fs, convert=%.3fs, Blender data=%.3fs, total=%.3fs",
            parse_seconds,
            setup_seconds,
            conversion_seconds,
            action_seconds,
            elapsed_seconds,
        )
        _LOG.debug(
            "Blender data split: actions=%.3fs, pose=%.3fs, metadata=%.3fs, tracks=%.3fs",
            blender_timing["action_shell"],
            blender_timing["pose_curves"],
            blender_timing["metadata"],
            blender_timing["track_curves"],
        )
        _LOG.debug(
            "Payload: pose=%d curves/%d keys, tracks=%d curves/%d keys, "
            "omitted_zero_tracks=%d, sparse_clips=%d, dense_clips=%d, "
            "pose_template=%d curves/%d keys, python_pose_writes=%d curves/%d keys",
            total_pose_curves,
            total_pose_keypoints,
            total_track_curves,
            total_track_keypoints,
            total_omitted_zero_tracks,
            sparse_clip_count,
            dense_clip_count,
            sparse_template_curve_count,
            sparse_template_keypoint_count,
            total_pose_override_curves,
            total_pose_override_keypoints,
        )
        animation_type_counts = {}
        additive_action_names = []
        for action in created_actions:
            animation_type = str(action.get("animationType", "Normal") or "Normal")
            animation_type_counts[animation_type] = (
                animation_type_counts.get(animation_type, 0) + 1
            )
            if animation_type != "Normal":
                additive_action_names.append(action.name)
        _LOG.debug(
            "Animation types: %s; additive actions=%s",
            ", ".join(
                f"{name}={count}"
                for name, count in sorted(animation_type_counts.items())
            )
            or "none",
            tuple(additive_action_names),
        )

    warnings = _schema_warnings(file_name, schema_versions)
    if skipped_clips:
        warnings.append(
            f"{file_name}: skipped {len(skipped_clips)} of {len(animations)} "
            f"animation clip(s) with invalid data; first: {skipped_clips[0]}"
        )
    return {
        "direct_imported": True,
        "filepath": os.path.abspath(filepath),
        "armature": armature,
        "actions": created_actions,
        "warnings": tuple(warnings),
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


def import_anims_glb_to_armature(
    filepath, armature=None, *, import_tracks=True, verbose=False, assign_action=True
):
    """Import actions and an optional reconstructed rig as one reversible transaction"""
    active = current_import_transaction()
    owner = active or DatablockImportTransaction()
    savepoint = owner.savepoint()
    snapshot = BlenderContextSnapshot().store() if active is None else None
    try:
        with owner.scope() if active is None else nullcontext():
            track_animation_import_state(armature)
            result = _import_anims_glb_to_armature_impl(
                filepath,
                armature,
                import_tracks=import_tracks,
                verbose=verbose,
                assign_action=assign_action,
            )
    except Exception as error:
        report = owner.rollback() if active is None else owner.rollback_to(savepoint)
        if snapshot is not None:
            snapshot.restore()
        raise_if_rollback_incomplete(
            report, error, error_type=DirectAnimationImportError
        )
        if isinstance(error, (GLBContainerError, GLTFSkeletonError)):
            raise DirectAnimationImportError(str(error)) from error
        raise
    if active is None:
        owner.commit()
    result["all_objects"] = [result["armature"]]
    return result
