from __future__ import annotations

import math
from dataclasses import dataclass

import bpy
from mathutils import Matrix

from ....animation.domain.rigify.mapping import (
    CP77_TO_METARIG,
    LIMB_SWITCH_FK,
    LIMB_SWITCH_PROPERTY,
    control_candidates,
    resolve_forward_target,
)
from ....blender.matrix import safe_matrix_inverse
from .forward import current_depsgraph, evaluated_object

_TORSO = "torso"
_HIPS = "Hips"


@dataclass(slots=True)
class _Binding:
    control: str
    source: str
    org: str
    depth: int  # Of the control in the rig hierarchy.
    org_neutral: Matrix


def _depth(armature, bone_name):
    bone = armature.data.bones.get(bone_name)
    depth = 0
    while bone is not None and bone.parent is not None:
        depth += 1
        bone = bone.parent
    return depth


def _world_pose(obj, pose_bone):
    return obj.matrix_world @ pose_bone.matrix


def _rigid(matrix):
    """The matrix without its scale"""
    return Matrix.LocRotScale(matrix.translation, matrix.to_quaternion(), None)


class ControlSolver:
    def __init__(self, source, rig, bindings, switches):
        self.source = source
        self.rig = rig
        self.bindings = bindings
        self.switches = switches
        self.levels = sorted({binding.depth for binding in bindings})
        self.control_names = tuple(
            dict.fromkeys(
                ([_TORSO] if rig.pose.bones.get(_TORSO) is not None else [])
                + [binding.control for binding in bindings]
            )
        )

    @classmethod
    def compile(cls, source, rig):
        """Bind each mapped source bone to the control that drives its ORG bone"""
        switches = []
        for pose_bone in rig.pose.bones:
            pose_bone.matrix_basis.identity()
            if LIMB_SWITCH_PROPERTY in pose_bone:
                pose_bone[LIMB_SWITCH_PROPERTY] = LIMB_SWITCH_FK
                switches.append(pose_bone.name)
        bpy.context.view_layer.update()
        rig_eval = evaluated_object(rig, current_depsgraph())
        names = set(rig.pose.bones.keys())
        bindings = []
        for source_name, metarig_name in CP77_TO_METARIG.items():
            if source.pose.bones.get(source_name) is None:
                continue
            org = resolve_forward_target(source_name, metarig_name, names)
            control = next(
                (
                    name
                    for name in control_candidates(source_name, metarig_name)
                    if name in names
                ),
                None,
            )
            if org is None or control is None:
                continue
            bindings.append(
                _Binding(
                    control,
                    source_name,
                    org,
                    _depth(rig, control),
                    _world_pose(rig, rig_eval.pose.bones[org]).copy(),
                )
            )
        return cls(source, rig, tuple(bindings), tuple(switches))

    def _source_delta(self, source_eval, source_name):
        pose_bone = source_eval.pose.bones[source_name]
        rest = self.source.matrix_world @ pose_bone.bone.matrix_local
        return _world_pose(self.source, pose_bone) @ safe_matrix_inverse(rest)

    def _place_torso(self, source_eval, rig_eval):
        torso = self.rig.pose.bones.get(_TORSO)
        hips = next(
            (binding for binding in self.bindings if binding.source == _HIPS), None
        )
        if torso is None or hips is None:
            return
        target = (self._source_delta(source_eval, _HIPS) @ hips.org_neutral).translation
        current = _world_pose(self.rig, rig_eval.pose.bones[hips.org]).translation
        offset = safe_matrix_inverse(self.rig.matrix_world).to_3x3() @ (
            target - current
        )
        torso.matrix = Matrix.Translation(offset) @ torso.matrix

    def solve(self, *, tolerance=1.0e-3, max_passes=12):
        """Pose the bound controls from the source's current pose"""
        view_layer = bpy.context.view_layer
        source_eval = evaluated_object(self.source, current_depsgraph())
        rig_inverse = safe_matrix_inverse(self.rig.matrix_world)
        targets = {
            binding.control: _rigid(
                self._source_delta(source_eval, binding.source) @ binding.org_neutral
            )
            for binding in self.bindings
        }
        for pose_bone in self.rig.pose.bones:
            pose_bone.matrix_basis.identity()
        view_layer.update()
        self._place_torso(source_eval, evaluated_object(self.rig, current_depsgraph()))
        view_layer.update()
        for _pass in range(max_passes):
            for level in self.levels:
                rig_eval = evaluated_object(self.rig, current_depsgraph())
                for binding in self.bindings:
                    if binding.depth != level:
                        continue
                    org_world = _rigid(
                        _world_pose(self.rig, rig_eval.pose.bones[binding.org])
                    )
                    correction = targets[binding.control] @ safe_matrix_inverse(
                        org_world
                    )
                    control_world = _rigid(
                        _world_pose(self.rig, rig_eval.pose.bones[binding.control])
                    )
                    pose_bone = self.rig.pose.bones[binding.control]
                    pose_bone.matrix = rig_inverse @ correction @ control_world
                    # The bake keys location and rotation only, so the controls keep unit scale.
                    pose_bone.scale = (1.0, 1.0, 1.0)
                    if all(pose_bone.lock_location):
                        pose_bone.location = (0.0, 0.0, 0.0)
                view_layer.update()
            if self.residual_degrees() <= tolerance:
                break

    def residuals(self, threshold=0.0) -> dict[str, float]:
        """Rotation difference in degrees between each source bone's delta and its ORG bone's delta"""
        depsgraph = current_depsgraph()
        source_eval = evaluated_object(self.source, depsgraph)
        rig_eval = evaluated_object(self.rig, depsgraph)
        result = {}
        for binding in self.bindings:
            source_delta = self._source_delta(
                source_eval, binding.source
            ).to_quaternion()
            org_world = _world_pose(self.rig, rig_eval.pose.bones[binding.org])
            org_delta = (
                org_world @ safe_matrix_inverse(binding.org_neutral)
            ).to_quaternion()
            angle = math.degrees(source_delta.rotation_difference(org_delta).angle)
            if angle > threshold:
                result[binding.source] = angle
        return result

    def residual_degrees(self) -> float:
        return max(self.residuals().values(), default=0.0)

    def key_switches(self, action, frame) -> None:
        """Key the limb switches in FK mode, so the baked FK controls keep driving the limbs"""
        for name in self.switches:
            pose_bone = self.rig.pose.bones[name]
            pose_bone[LIMB_SWITCH_PROPERTY] = LIMB_SWITCH_FK
            pose_bone.keyframe_insert(
                f'["{LIMB_SWITCH_PROPERTY}"]', frame=frame, group=name
            )
