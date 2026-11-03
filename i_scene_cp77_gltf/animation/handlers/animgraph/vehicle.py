from __future__ import annotations

from ....assetio.transform_values import vector3_from_data
from ...domain.animgraph.vehicle import (
    apply_translation,
    resolve_rotate_angle,
    resolve_translation,
    rotate_bone_local,
    rotate_bone_model,
)
from ...model.animgraph.evaluation import PoseOpEvaluation
from .base import PoseOpHandler


class RotateBoneHandler(PoseOpHandler):
    node_types = ("animAnimNode_RotateBone",)
    bone_fields = ("bone",)
    uses_tracks = False

    def evaluate(self, context, op):
        bone = str(op.data.get("bone", "") or "")
        linked = (
            context.values.linked("float", op.handle, "angleNode", 0.0)
            if op.data.get("hasAngleNode")
            else None
        )
        minimum = (
            context.values.linked(
                "float",
                op.handle,
                "minValueNode",
                float(op.data.get("minAngle", -90.0)),
            )
            if op.data.get("hasMinValueNode")
            else float(op.data.get("minAngle", -90.0))
        )
        maximum = (
            context.values.linked(
                "float", op.handle, "maxValueNode", float(op.data.get("maxAngle", 90.0))
            )
            if op.data.get("hasMaxValueNode")
            else float(op.data.get("maxAngle", 90.0))
        )
        previous = float(
            context._rotate_angles.get(op.handle, op.data.get("biasAngle", 0.0) or 0.0)
        )
        angle = resolve_rotate_angle(
            previous,
            linked_angle=linked,
            scale=float(op.data.get("scale", 1.0) or 0.0),
            bias_angle=float(op.data.get("biasAngle", 0.0) or 0.0),
            min_angle=minimum,
            max_angle=maximum,
            clamp_rotation=bool(op.data.get("clampRotation", False)),
            incremental=bool(op.data.get("useIncrementalMode", False)),
            dt=float(context._current_raw_dt),
        )
        context._rotate_angles[op.handle] = angle
        if bone not in op.pose:
            return op.child
        if bool(op.data.get("inModelSpace", False)):
            rotate_bone_model(
                op.pose,
                op.child.parent_map,
                bone,
                str(op.data.get("axis", "X_Axis") or "X_Axis"),
                angle,
            )
        else:
            op.pose[bone] = rotate_bone_local(
                op.pose[bone], str(op.data.get("axis", "X_Axis") or "X_Axis"), angle
            )
        evaluation = PoseOpEvaluation((bone,), ())
        return evaluation


class TranslateBoneHandler(PoseOpHandler):
    node_types = ("animAnimNode_TranslateBone",)
    bone_fields = ("bone",)
    uses_tracks = False

    def evaluate(self, context, op):
        bone = str(op.data.get("bone", "") or "")
        bias = vector3_from_data(op.data.get("biasValue"))
        scale = vector3_from_data(op.data.get("scale"), (1.0, 1.0, 1.0))
        linked = (
            context.values.linked(
                "vector", op.handle, "inputTranslation", (0.0, 0.0, 0.0)
            )
            if bool(op.data.get("hasInputTranslation", False))
            else None
        )
        previous = context._translation_values.get(op.handle, bias)
        translation = resolve_translation(
            previous,
            linked_translation=linked,
            scale=scale,
            bias=bias,
            incremental=bool(op.data.get("useIncrementalMode", False)),
            dt=float(context._current_raw_dt),
        )
        context._translation_values[op.handle] = translation
        if bone not in op.pose:
            return op.child
        op.pose[bone] = apply_translation(op.pose[bone], translation)
        evaluation = PoseOpEvaluation((bone,), ())
        return evaluation
