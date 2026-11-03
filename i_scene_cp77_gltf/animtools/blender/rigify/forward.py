from __future__ import annotations

from dataclasses import dataclass

import bpy
from mathutils import Matrix

from ....animation.domain.rigify.mapping import (
    CP77_TO_METARIG,
    FOLLOW_BONE_PREFIX,
    FORWARD_CONSTRAINT,
    FORWARD_CONSTRAINT_NAMES,
    FORWARD_LIMIT_CONSTRAINT,
    FORWARD_LIMITED_LOCATION_BONES,
    FORWARD_LOCATION_BONES,
    FORWARD_LOCATION_CONSTRAINT,
    LEGACY_REVERSE_CONSTRAINT,
    LIMITED_LOCATION_OFFSETS,
    MAX_LIMITED_LOCATION_OFFSET,
    follow_bone_name,
    forward_neutral_key,
    resolve_forward_target,
)
from ....bartmoss.matrix import flatten_matrix
from ....blender.armature_edit import capture_constraint, recreate_constraint
from ....blender.context import preserved_context, safe_mode_switch
from ....blender.identity import rna_identity, rna_is_live
from ....blender.matrix import matrix_from_flat, safe_matrix_inverse
from ....blender.selection import select_objects
from ....blender.transactions import track_mutation
from ....core.log import get_logger, log_once

_LOG = get_logger(__name__)

_MIN_FOLLOW_BONE_LENGTH = 0.01
_REST_TOLERANCE = 1.0e-4


def current_depsgraph():
    try:
        return bpy.context.evaluated_depsgraph_get()
    except (AttributeError, RuntimeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("current_depsgraph", type(error).__name__),
            "current depsgraph: fell back after %s",
            error,
            exc_info=True,
        )
        return None


def evaluated_object(obj, depsgraph):
    if depsgraph is None:
        return obj
    try:
        return obj.evaluated_get(depsgraph)
    except (ReferenceError, RuntimeError, TypeError):
        return obj


def clear_legacy_reverse_constraints(rig) -> int:
    """Remove the constraints an earlier scheme used to drive the Rigify controls from the source rig"""
    if rig is None or rig.type != "ARMATURE":
        return 0
    removed = 0
    for pose_bone in rig.pose.bones:
        constraint = pose_bone.constraints.get(LEGACY_REVERSE_CONSTRAINT)
        if constraint is not None:
            pose_bone.constraints.remove(constraint)
            removed += 1
    return removed


def track_legacy_reverse_constraints(rig) -> None:
    """On rollback, put back the legacy reverse constraints clear_legacy_reverse_constraints() removes"""
    if rig is None or rig.type != "ARMATURE":
        return
    state = tuple(
        (pose_bone.name, index, capture_constraint(constraint))
        for pose_bone in rig.pose.bones
        for index, constraint in enumerate(pose_bone.constraints)
        if constraint.name == LEGACY_REVERSE_CONSTRAINT
    )

    def restore():
        if not rna_is_live(rig):
            return
        for bone_name, index, captured in state:
            pose_bone = rig.pose.bones.get(bone_name)
            if (
                pose_bone is None
                or pose_bone.constraints.get(LEGACY_REVERSE_CONSTRAINT) is not None
            ):
                continue
            recreate_constraint(rig, pose_bone.constraints, captured)
            pose_bone.constraints.move(
                len(pose_bone.constraints) - 1,
                min(index, len(pose_bone.constraints) - 1),
            )

    track_mutation(
        ("rigify-legacy-reverse-constraints", rna_identity(rig)),
        restore,
        label="Rigify legacy constraints",
    )


def track_forward_constraints(source) -> None:
    """On rollback, put back the follow constraints the source had"""
    if source is None or source.type != "ARMATURE":
        return
    state = tuple(
        (pose_bone.name, index, capture_constraint(constraint))
        for pose_bone in source.pose.bones
        for index, constraint in enumerate(pose_bone.constraints)
        if constraint.name in FORWARD_CONSTRAINT_NAMES
    )

    def restore():
        if not rna_is_live(source):
            return
        clear_forward_constraints(source)
        for bone_name, index, captured in state:
            pose_bone = source.pose.bones.get(bone_name)
            if pose_bone is None:
                continue
            recreate_constraint(source, pose_bone.constraints, captured)
            pose_bone.constraints.move(
                len(pose_bone.constraints) - 1,
                min(index, len(pose_bone.constraints) - 1),
            )

    track_mutation(
        ("rigify-forward-constraints", rna_identity(source)),
        restore,
        label="Rigify forward constraints",
    )


def clear_forward_constraints(source) -> int:
    if source is None or source.type != "ARMATURE":
        return 0
    removed = 0
    for pose_bone in source.pose.bones:
        for name in FORWARD_CONSTRAINT_NAMES:
            constraint = pose_bone.constraints.get(name)
            if constraint is not None:
                pose_bone.constraints.remove(constraint)
                removed += 1
    return removed


def _forward_targets(source, rig_names):
    for source_name, metarig_name in CP77_TO_METARIG.items():
        if source.pose.bones.get(source_name) is None:
            continue
        target_name = resolve_forward_target(source_name, metarig_name, rig_names)
        if target_name is not None:
            yield source_name, target_name


def forward_neutral(source, source_name: str):
    return matrix_from_flat(source.data.get(forward_neutral_key(source_name), ()))


def has_forward_neutral_pose(source, rig) -> bool:
    rig_names = set(rig.pose.bones.keys())
    return all(
        source.data.get(forward_neutral_key(source_name)) is not None
        for source_name, _target in _forward_targets(source, rig_names)
    )


def capture_forward_neutral_pose(source, rig, depsgraph=None) -> int:
    """Store the evaluated Rigify pose of every forward target as the source's neutral reference"""
    if (
        source is None
        or rig is None
        or source.type != "ARMATURE"
        or rig.type != "ARMATURE"
    ):
        return 0
    if depsgraph is None:
        depsgraph = current_depsgraph()
    rig_pose = evaluated_object(rig, depsgraph).pose.bones
    captured = 0
    for source_name, target_name in _forward_targets(source, set(rig_pose.keys())):
        target_pose_bone = rig_pose.get(target_name)
        if target_pose_bone is None:
            continue
        source.data[forward_neutral_key(source_name)] = flatten_matrix(
            target_pose_bone.matrix.copy()
        ).tolist()
        captured += 1
    return captured


def forward_sync_enabled(source) -> bool:
    """Whether the source follows its Rigify rig"""
    if source is None or source.type != "ARMATURE":
        return False
    bones = source.pose.bones
    return any(
        pose_bone.constraints.get(FORWARD_CONSTRAINT) is not None
        for pose_bone in (bones.get(name) for name in CP77_TO_METARIG)
        if pose_bone is not None
    )


@dataclass(frozen=True, slots=True)
class FollowBone:
    """A source bone's follow bone"""

    source: str
    target: str
    name: str
    rest: Matrix
    length: float
    location: bool = False
    limit: float = 0.0


def follow_plan(source, rig) -> tuple[FollowBone, ...]:
    """The follow bone of every mapped source bone"""
    rig_bones = rig.data.bones
    plan = []
    for source_name, target_name in _forward_targets(source, set(rig_bones.keys())):
        source_bone = source.data.bones[source_name]
        target_rest = rig_bones[target_name].matrix_local
        neutral = forward_neutral(source, source_name)
        limited = source_name in FORWARD_LIMITED_LOCATION_BONES
        plan.append(
            FollowBone(
                source_name,
                target_name,
                follow_bone_name(source_name),
                target_rest
                @ safe_matrix_inverse(neutral if neutral is not None else target_rest)
                @ source_bone.matrix_local,
                max(source_bone.length, _MIN_FOLLOW_BONE_LENGTH),
                limited or source_name in FORWARD_LOCATION_BONES,
                LIMITED_LOCATION_OFFSETS.get(source_name, MAX_LIMITED_LOCATION_OFFSET)
                if limited
                else 0.0,
            )
        )
    return tuple(plan)


def _close(first, second) -> bool:
    return all(
        abs(a - b) <= _REST_TOLERANCE
        for row, other in zip(first, second)
        for a, b in zip(row, other)
    )


def follow_bones_current(rig, plan) -> bool:
    """Whether the rig holds exactly the plan's follow bones, each a child of its target at its rest"""
    bones = rig.data.bones
    if {bone.name for bone in bones if bone.name.startswith(FOLLOW_BONE_PREFIX)} != {
        entry.name for entry in plan
    }:
        return False
    for entry in plan:
        bone = bones[entry.name]
        if (
            bone.parent is None
            or bone.parent.name != entry.target
            or not _close(bone.matrix_local, entry.rest.normalized())
        ):
            return False
    return True


def _follow_collection(armature):
    """Rigify's hidden mechanism bone collection, made when the rig has none"""
    collection = armature.collections_all.get("MCH")
    if collection is None:
        collection = armature.collections.new("MCH")
        collection.is_visible = False
    return collection


def build_follow_bones(rig, plan) -> None:
    """Replace the rig's follow bones with the plan's"""
    select_objects(rig)
    safe_mode_switch("EDIT")
    edit_bones = rig.data.edit_bones
    for edit_bone in [
        edit_bone
        for edit_bone in edit_bones
        if edit_bone.name.startswith(FOLLOW_BONE_PREFIX)
    ]:
        edit_bones.remove(edit_bone)
    collection = _follow_collection(rig.data)
    for entry in plan:
        parent = edit_bones.get(entry.target)
        if parent is None:
            continue
        edit_bone = edit_bones.new(entry.name)
        edit_bone.tail = (0.0, entry.length, 0.0)
        edit_bone.matrix = entry.rest.normalized()
        edit_bone.parent = parent
        edit_bone.use_connect = False
        edit_bone.use_deform = False
        for owner in tuple(edit_bone.collections):
            owner.unassign(edit_bone)
        collection.assign(edit_bone)
    safe_mode_switch("OBJECT")


def track_follow_bones(rig) -> None:
    """On rollback, put back the follow bones the rig had"""
    if rig is None or rig.type != "ARMATURE":
        return
    state = tuple(
        FollowBone(
            "", bone.parent.name, bone.name, bone.matrix_local.copy(), bone.length
        )
        for bone in rig.data.bones
        if bone.name.startswith(FOLLOW_BONE_PREFIX) and bone.parent is not None
    )

    def restore():
        if not rna_is_live(rig) or follow_bones_current(rig, state):
            return
        with preserved_context():
            build_follow_bones(rig, state)

    track_mutation(
        ("rigify-follow-bones", rna_identity(rig)), restore, label="Rigify follow bones"
    )


def _follow_constraint(
    pose_bone, kind: str, name: str, target, subtarget: str, space: str = "POSE"
):
    constraint = pose_bone.constraints.new(kind)
    constraint.name = name
    constraint.target = target
    constraint.subtarget = subtarget
    constraint.target_space = space
    constraint.owner_space = space
    return constraint


def bind_follow_constraints(source, rig, plan) -> int:
    """Make every planned source bone follow its follow bone and return the number bound"""
    clear_forward_constraints(source)
    follow_names = set(rig.data.bones.keys())
    bound = 0
    for entry in plan:
        pose_bone = source.pose.bones.get(entry.source)
        if pose_bone is None or entry.name not in follow_names:
            continue
        pose_bone.matrix_basis = Matrix.Identity(4)
        _follow_constraint(
            pose_bone, "COPY_ROTATION", FORWARD_CONSTRAINT, rig, entry.name
        )
        if entry.location:
            _follow_constraint(
                pose_bone, "COPY_LOCATION", FORWARD_LOCATION_CONSTRAINT, rig, entry.name
            )
        if entry.limit > 0.0 and pose_bone.parent is not None:
            # Local space measures each bone from where its parent puts it, and the parent's own offset there is zero,
            # so this keeps the bone's offset within the limit.
            limit = _follow_constraint(
                pose_bone,
                "LIMIT_DISTANCE",
                FORWARD_LIMIT_CONSTRAINT,
                source,
                pose_bone.parent.name,
                "LOCAL",
            )
            limit.distance = entry.limit
            limit.limit_mode = "LIMITDIST_INSIDE"
        bound += 1
    return bound


def apply_follow_pose(source) -> None:
    """Write each following bone's evaluated pose into its basis"""
    for pose_bone in source.pose.bones:
        if pose_bone.constraints.get(FORWARD_CONSTRAINT) is not None:
            pose_bone.matrix_basis = source.convert_space(
                pose_bone=pose_bone,
                matrix=pose_bone.matrix,
                from_space="POSE",
                to_space="LOCAL",
            )
