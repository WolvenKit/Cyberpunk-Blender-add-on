from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from dataclasses import dataclass

from ....bartmoss.qs_transform import QsTransform, compose, lerp_qs, relative_to
from ....bartmoss.scalar import lerp

_IDENTITY = QsTransform.identity()

ADDITIVE_ACTIVATION_THRESHOLD = 0.01
ADDITIVE_LOCAL = "AGAT_Local"
ADDITIVE_REF = "AGAT_Ref"
TRACK_BASE = "AGBT_BasePose"
TRACK_INTERPOLATE = "AGBT_Interpolate"
TRACK_ADD = "AGBT_Add"

ADDITIVE_STORAGE_DELTA = "DELTA"
ADDITIVE_STORAGE_REFERENCE_APPLIED = "REFERENCE_APPLIED"

ADDITIVE_ANIMATION_TYPES = frozenset(
    {
        "AdditiveFromRefPose",
        "AdditiveFromFirstFrame",
        "Additive",
        "AdditiveWithoutFirstFrame",
    }
)
EDITABLE_ADDITIVE_ANIMATION_TYPES = (
    "AdditiveFromRefPose",
    "Additive",
    "AdditiveWithoutFirstFrame",
)


@dataclass(frozen=True)
class AdditiveEvaluation:
    transforms_written: tuple[str, ...]
    tracks_written: tuple[str, ...] = ()


def _enum_value(value):
    while isinstance(value, Mapping):
        for key in ("$value", "value", "Value", "name"):
            if key in value:
                value = value[key]
                break
        else:
            break
    return value


def is_additive_animation_type(value) -> bool:
    value = _enum_value(value)
    return str(value or "Normal").split("::")[-1] in ADDITIVE_ANIMATION_TYPES


def next_editable_additive_type(value) -> str:
    current = str(value or "AdditiveFromRefPose")
    if current == "AdditiveFromFirstFrame":
        return "Additive"
    try:
        index = EDITABLE_ADDITIVE_ANIMATION_TYPES.index(current)
    except ValueError:
        index = -1
    return EDITABLE_ADDITIVE_ANIMATION_TYPES[
        (index + 1) % len(EDITABLE_ADDITIVE_ANIMATION_TYPES)
    ]


def normalize_additive_storage(value) -> str:
    text = str(_enum_value(value) or ADDITIVE_STORAGE_REFERENCE_APPLIED).split("::")[-1]
    aliases = {
        "Delta": ADDITIVE_STORAGE_DELTA,
        ADDITIVE_STORAGE_DELTA: ADDITIVE_STORAGE_DELTA,
        "ReferenceApplied": ADDITIVE_STORAGE_REFERENCE_APPLIED,
        "WolvenKit": ADDITIVE_STORAGE_REFERENCE_APPLIED,
        ADDITIVE_STORAGE_REFERENCE_APPLIED: ADDITIVE_STORAGE_REFERENCE_APPLIED,
    }
    if text not in aliases:
        raise ValueError(f"unsupported additive storage mode {value!r}")
    return aliases[text]


def recover_reference_applied_transform(
    reference: QsTransform,
    bind: QsTransform,
    sampled_basis: QsTransform,
) -> QsTransform:
    return relative_to(reference, compose(bind, sampled_basis))


def sampled_animation_transform(
    reference: QsTransform,
    sampled_basis: QsTransform,
    animation_type,
) -> QsTransform:
    if is_additive_animation_type(animation_type):
        return sampled_basis
    return compose(reference, sampled_basis)


def sampled_animation_track_seed(
    reference_tracks: Mapping[str, float],
    animation_type,
) -> dict[str, float]:
    if is_additive_animation_type(animation_type):
        return {name: 0.0 for name in reference_tracks}
    return {name: float(value) for name, value in reference_tracks.items()}


def normalize_additive_type(value) -> str:
    value = _enum_value(value)
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, int):
        if value == 0:
            return ADDITIVE_LOCAL
        if value == 1:
            return ADDITIVE_REF
    text = str(value or ADDITIVE_LOCAL).split("::")[-1]
    aliases = {
        "0": ADDITIVE_LOCAL,
        "Local": ADDITIVE_LOCAL,
        ADDITIVE_LOCAL: ADDITIVE_LOCAL,
        "1": ADDITIVE_REF,
        "Ref": ADDITIVE_REF,
        ADDITIVE_REF: ADDITIVE_REF,
    }
    if text not in aliases:
        raise ValueError(f"unsupported additive type {value!r}")
    return aliases[text]


def normalize_track_mode(value) -> str:
    value = _enum_value(value)
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, int):
        modes = (TRACK_BASE, TRACK_INTERPOLATE, TRACK_ADD)
        if 0 <= value < len(modes):
            return modes[value]
    text = str(value or TRACK_ADD).split("::")[-1]
    aliases = {
        "0": TRACK_BASE,
        "BasePose": TRACK_BASE,
        TRACK_BASE: TRACK_BASE,
        "1": TRACK_INTERPOLATE,
        "Interpolate": TRACK_INTERPOLATE,
        TRACK_INTERPOLATE: TRACK_INTERPOLATE,
        "2": TRACK_ADD,
        "Add": TRACK_ADD,
        TRACK_ADD: TRACK_ADD,
    }
    if text not in aliases:
        raise ValueError(f"unsupported additive track mode {value!r}")
    return aliases[text]


def final_additive_weight(
    control: float, bias: float = 0.0, scale: float = 1.0
) -> float:
    return (float(control) - float(bias)) * float(scale)


def additive_branch_active(weight: float) -> bool:
    return abs(float(weight)) > ADDITIVE_ACTIVATION_THRESHOLD


def additive_activation_transition(previous_active: bool, weight: float):
    active = additive_branch_active(weight)
    return active, active and not previous_active, previous_active and not active


def convert_pose_to_additive_local(
    first_frame: Mapping[str, QsTransform],
    sampled_frame: Mapping[str, QsTransform],
) -> dict[str, QsTransform]:
    result: dict[str, QsTransform] = {}
    for name, sampled in sampled_frame.items():
        reference = first_frame.get(name)
        result[name] = (
            relative_to(reference, sampled) if reference is not None else sampled
        )
    return result


def reference_or_identity_pose(
    reference_pose: Mapping[str, QsTransform], *, additive: bool
) -> dict[str, QsTransform]:
    """A copy of the reference pose, or identity for each of its bones when the pose is additive"""
    if additive:
        return {name: QsTransform.identity() for name in reference_pose}
    return dict(reference_pose)


def blend_additive_transform(
    base: QsTransform,
    additive: QsTransform,
    weight: float,
    additive_type=ADDITIVE_LOCAL,
    *,
    clamp_weight: bool,
) -> QsTransform:
    weight = float(weight)
    if clamp_weight:
        weight = max(0.0, min(1.0, weight))
    if weight == 0.0:
        return base
    mode = normalize_additive_type(additive_type)
    if mode == ADDITIVE_LOCAL:
        weighted_delta = lerp_qs(QsTransform.identity(), additive, weight)
        return compose(base, weighted_delta)
    target = compose(additive, base)
    return lerp_qs(base, target, weight)


def layer_additive_bone(
    pose: MutableMapping[str, QsTransform],
    name: str,
    additive: QsTransform,
    *,
    weight: float,
    storage_mode: str,
    reference_basis: Mapping[str, QsTransform],
    mask_weights: Mapping[str, float] | None,
    replace_with_reference_applied: bool = False,
) -> None:
    """Layer one sampled additive bone transform onto pose in place"""
    if (
        replace_with_reference_applied
        and storage_mode == ADDITIVE_STORAGE_REFERENCE_APPLIED
        and mask_weights is None
    ):
        pose[name] = additive
        return
    if storage_mode == ADDITIVE_STORAGE_REFERENCE_APPLIED:
        reference = reference_basis.get(name)
        if reference is None:
            raise KeyError(f"Action reference basis is missing additive bone {name!r}")
        additive = relative_to(reference, additive)
    mask_weight = 1.0 if mask_weights is None else float(mask_weights.get(name, 0.0))
    effective_weight = weight * mask_weight
    if effective_weight == 0.0:
        return
    pose[name] = blend_additive_transform(
        pose.get(name, _IDENTITY),
        additive,
        effective_weight,
        ADDITIVE_LOCAL,
        clamp_weight=False,
    )


def evaluate_blend_additive(
    base_pose: MutableMapping[str, QsTransform],
    additive_pose: Mapping[str, QsTransform],
    base_tracks: MutableMapping[str, float],
    additive_tracks: Mapping[str, float],
    *,
    weight: float,
    additive_type=ADDITIVE_LOCAL,
    blend_tracks=TRACK_ADD,
    mask_weights: Mapping[str, float] | None = None,
) -> AdditiveEvaluation:
    weight = max(0.0, min(1.0, float(weight)))
    additive_type = normalize_additive_type(additive_type)
    blend_tracks = normalize_track_mode(blend_tracks)
    written_bones: list[str] = []
    if weight != 0.0:
        candidates = base_pose if mask_weights is None else mask_weights
        for name in candidates:
            if name not in base_pose or name not in additive_pose:
                continue
            bone_weight = (
                weight
                if mask_weights is None
                else weight * float(mask_weights.get(name, 0.0))
            )
            if bone_weight == 0.0:
                continue
            base_pose[name] = blend_additive_transform(
                base_pose[name],
                additive_pose[name],
                bone_weight,
                additive_type,
                clamp_weight=False,
            )
            written_bones.append(name)

    written_tracks: list[str] = []
    if blend_tracks != TRACK_BASE and weight != 0.0:
        for name, base_raw in tuple(base_tracks.items()):
            base_value = float(base_raw)
            additive_value = float(additive_tracks.get(name, 0.0))
            if blend_tracks == TRACK_ADD:
                base_tracks[name] = base_value + additive_value * weight
            else:
                base_tracks[name] = float(lerp(base_value, additive_value, weight))
            written_tracks.append(name)
        for name, additive_raw in additive_tracks.items():
            if name in base_tracks:
                continue
            additive_value = float(additive_raw)
            base_tracks[name] = (
                additive_value * weight
                if blend_tracks == TRACK_ADD
                else float(lerp(0.0, additive_value, weight))
            )
            written_tracks.append(name)
    return AdditiveEvaluation(tuple(written_bones), tuple(written_tracks))


def evaluate_shared_meta_pose_additive(
    local_pose: MutableMapping[str, QsTransform],
    local_tracks: MutableMapping[str, float],
    parent_pose: Mapping[str, QsTransform],
    parent_tracks: Mapping[str, float],
    reference_pose: Mapping[str, QsTransform],
    reference_tracks: Mapping[str, float],
    transform_names: Sequence[str],
    track_names: Sequence[str],
    *,
    weight: float,
    additive_type=ADDITIVE_LOCAL,
    blend_tracks=TRACK_ADD,
    convert_parent_pose_to_additive: bool = True,
) -> AdditiveEvaluation:
    additive_type = normalize_additive_type(additive_type)
    blend_tracks = normalize_track_mode(blend_tracks)
    if blend_tracks == TRACK_BASE:
        raise ValueError(
            "SharedMetaPoseAdditive does not support AGBT_BasePose track blending"
        )
    weight = float(weight)
    written_bones: list[str] = []
    for name in transform_names:
        if name not in local_pose or name not in parent_pose:
            continue
        additive = parent_pose[name]
        if convert_parent_pose_to_additive:
            reference = reference_pose.get(name)
            if reference is None:
                continue
            additive = relative_to(reference, additive)
        local_pose[name] = blend_additive_transform(
            local_pose[name], additive, weight, additive_type, clamp_weight=False
        )
        written_bones.append(name)

    written_tracks: list[str] = []
    for name in track_names:
        if name not in parent_tracks:
            continue
        additive_value = float(parent_tracks[name])
        if convert_parent_pose_to_additive:
            additive_value -= float(reference_tracks.get(name, 0.0))
        base_value = float(local_tracks.get(name, 0.0))
        if blend_tracks == TRACK_ADD:
            local_tracks[name] = base_value + additive_value * weight
        else:
            local_tracks[name] = float(lerp(base_value, additive_value, weight))
        written_tracks.append(name)
    return AdditiveEvaluation(tuple(written_bones), tuple(written_tracks))
