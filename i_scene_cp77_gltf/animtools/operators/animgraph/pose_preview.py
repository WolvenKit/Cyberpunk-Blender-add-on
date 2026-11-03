import bpy

from ....animation.model.animgraph import (
    aim_constraint,
    direct_conn,
    point_constraint,
    simple_bounce,
)
from ....blender.operator_results import execute_operation
from ...services.animgraph import preview
from .context import active_node, active_tree


class PosePreviewOperator:
    """Evaluates the pose chain ending at the active node of one of red_types"""

    bl_options = {"REGISTER", "UNDO"}
    red_types = frozenset()

    @classmethod
    def poll(cls, context):
        tree, node = active_node(context, cls.red_types)
        return node is not None and preview.can_preview(tree)

    def execute(self, context):
        tree, node = active_node(context, self.red_types)
        return execute_operation(
            self, "AnimGraph pose preview", preview.evaluate_preview, tree, node
        )


class ClearPosePreviewOperator:
    """Restores the pose captured by the last preview while a node of red_types is active"""

    bl_options = {"REGISTER", "UNDO"}
    red_types = frozenset()

    @classmethod
    def poll(cls, context):
        tree, _node = active_node(context, cls.red_types)
        return tree is not None and preview.has_preview(tree)

    def execute(self, context):
        tree, _node = active_node(context, self.red_types)
        return execute_operation(
            self, "AnimGraph preview restore", preview.clear_preview, tree
        )


class REDENGINE_OT_aim_constraint_preview(PosePreviewOperator, bpy.types.Operator):
    bl_idname = "redengine.aim_constraint_preview"
    bl_label = "Preview Aim Constraint Chain"
    red_types = frozenset(aim_constraint.AIM_TYPES)


class REDENGINE_OT_aim_constraint_clear_preview(
    ClearPosePreviewOperator, bpy.types.Operator
):
    bl_idname = "redengine.aim_constraint_clear_preview"
    bl_label = "Clear Aim Constraint Preview"
    red_types = frozenset(aim_constraint.AIM_TYPES)


class REDENGINE_OT_direct_conn_preview(PosePreviewOperator, bpy.types.Operator):
    bl_idname = "redengine.direct_conn_preview"
    bl_label = "Preview Direct Connection Chain"
    red_types = frozenset({direct_conn.RED_TYPE})


class REDENGINE_OT_direct_conn_clear_preview(
    ClearPosePreviewOperator, bpy.types.Operator
):
    bl_idname = "redengine.direct_conn_clear_preview"
    bl_label = "Clear Direct Connection Preview"
    red_types = frozenset({direct_conn.RED_TYPE})


class REDENGINE_OT_point_constraint_preview(PosePreviewOperator, bpy.types.Operator):
    bl_idname = "redengine.point_constraint_preview"
    bl_label = "Preview Point Constraint Chain"
    red_types = frozenset({point_constraint.RED_TYPE})


class REDENGINE_OT_point_constraint_clear_preview(
    ClearPosePreviewOperator, bpy.types.Operator
):
    bl_idname = "redengine.point_constraint_clear_preview"
    bl_label = "Clear Point Constraint Preview"
    red_types = frozenset({point_constraint.RED_TYPE})


class REDENGINE_OT_simple_bounce_preview(PosePreviewOperator, bpy.types.Operator):
    bl_idname = "redengine.simple_bounce_preview"
    bl_label = "Preview Simple Bounce Chain"
    red_types = frozenset({simple_bounce.RED_TYPE})


class REDENGINE_OT_simple_bounce_clear_preview(
    ClearPosePreviewOperator, bpy.types.Operator
):
    bl_idname = "redengine.simple_bounce_clear_preview"
    bl_label = "Clear Simple Bounce Preview"
    red_types = frozenset({simple_bounce.RED_TYPE})


class REDENGINE_OT_animgraph_bind_active_armature(bpy.types.Operator):
    bl_idname = "redengine.animgraph_bind_active_armature"
    bl_label = "Bind Active Armature"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        tree = active_tree(context)
        active = getattr(context, "active_object", None)
        return (
            tree is not None
            and active is not None
            and getattr(active, "type", "") == "ARMATURE"
        )

    def execute(self, context):
        return execute_operation(
            self,
            "AnimGraph armature binding",
            preview.bind_armature,
            active_tree(context),
            context.active_object,
        )


class REDENGINE_OT_animgraph_clear_armature_binding(bpy.types.Operator):
    bl_idname = "redengine.animgraph_clear_armature_binding"
    bl_label = "Clear Armature Binding"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return preview.can_preview(active_tree(context))

    def execute(self, context):
        return execute_operation(
            self,
            "AnimGraph armature binding",
            preview.bind_armature,
            active_tree(context),
            None,
        )


POSE_PREVIEW_OPERATOR_CLASSES = (
    REDENGINE_OT_animgraph_bind_active_armature,
    REDENGINE_OT_animgraph_clear_armature_binding,
    REDENGINE_OT_direct_conn_preview,
    REDENGINE_OT_direct_conn_clear_preview,
    REDENGINE_OT_simple_bounce_preview,
    REDENGINE_OT_simple_bounce_clear_preview,
    REDENGINE_OT_point_constraint_preview,
    REDENGINE_OT_point_constraint_clear_preview,
    REDENGINE_OT_aim_constraint_preview,
    REDENGINE_OT_aim_constraint_clear_preview,
)
