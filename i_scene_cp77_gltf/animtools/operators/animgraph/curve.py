import bpy

from ....blender.operator_results import finish_operator
from ....core.log import get_logger
from ....core.notifications import report
from ...services.animgraph import editing
from .context import active_curve_property

_LOG = get_logger(__name__)


class _CurvePropertyOperator:
    bl_options = {"REGISTER", "UNDO"}

    property_index: bpy.props.IntProperty()


class REDENGINE_OT_curve_point_add(_CurvePropertyOperator, bpy.types.Operator):
    bl_idname = "redengine.curve_point_add"
    bl_label = "Add Curve Point"

    def execute(self, context):
        item = active_curve_property(context, self.property_index)
        if item is None:
            report(self, "WARNING", "No active REDengine curve property", logger=_LOG)
            return {"CANCELLED"}
        return finish_operator(self, editing.add_curve_point(item))


class REDENGINE_OT_curve_point_remove(_CurvePropertyOperator, bpy.types.Operator):
    bl_idname = "redengine.curve_point_remove"
    bl_label = "Remove Curve Point"

    def execute(self, context):
        item = active_curve_property(context, self.property_index)
        if item is None:
            return {"CANCELLED"}
        return finish_operator(self, editing.remove_curve_point(item))


class REDENGINE_OT_curve_points_sort(_CurvePropertyOperator, bpy.types.Operator):
    bl_idname = "redengine.curve_points_sort"
    bl_label = "Sort Curve Points"

    def execute(self, context):
        item = active_curve_property(context, self.property_index)
        if item is None:
            return {"CANCELLED"}
        return finish_operator(self, editing.sort_curve(item))


class REDENGINE_OT_curve_points_reset(_CurvePropertyOperator, bpy.types.Operator):
    bl_idname = "redengine.curve_points_reset"
    bl_label = "Reset Curve From Import"

    def execute(self, context):
        item = active_curve_property(context, self.property_index)
        if item is None:
            return {"CANCELLED"}
        return finish_operator(self, editing.reset_curve(item))


class REDENGINE_OT_curve_widget_init(_CurvePropertyOperator, bpy.types.Operator):
    bl_idname = "redengine.curve_widget_init"
    bl_label = "Initialize Native Curve Widget"

    def execute(self, context):
        node = getattr(context, "active_node", None)
        item = active_curve_property(context, self.property_index)
        if node is None or item is None:
            return {"CANCELLED"}
        return finish_operator(
            self,
            editing.push_curve_widget(
                node, item, failure="Could not create the native Blender curve widget"
            ),
        )


class REDENGINE_OT_curve_widget_push(_CurvePropertyOperator, bpy.types.Operator):
    bl_idname = "redengine.curve_widget_push"
    bl_label = "Push Points To Native Curve"

    def execute(self, context):
        node = getattr(context, "active_node", None)
        item = active_curve_property(context, self.property_index)
        if node is None or item is None:
            return {"CANCELLED"}
        return finish_operator(
            self,
            editing.push_curve_widget(
                node, item, failure="Could not update the native Blender curve widget"
            ),
        )


class REDENGINE_OT_curve_widget_apply(_CurvePropertyOperator, bpy.types.Operator):
    bl_idname = "redengine.curve_widget_apply"
    bl_label = "Apply Native Curve To REDengine Data"

    def execute(self, context):
        node = getattr(context, "active_node", None)
        item = active_curve_property(context, self.property_index)
        if node is None or item is None:
            return {"CANCELLED"}
        return finish_operator(self, editing.apply_curve_widget(node, item))


class REDENGINE_OT_curve_point_move(_CurvePropertyOperator, bpy.types.Operator):
    bl_idname = "redengine.curve_point_move"
    bl_label = "Move Curve Point"

    direction: bpy.props.EnumProperty(
        items=(("UP", "Up", ""), ("DOWN", "Down", "")),
        default="UP",
    )

    def execute(self, context):
        item = active_curve_property(context, self.property_index)
        if item is None:
            return {"CANCELLED"}
        return finish_operator(self, editing.move_curve_point(item, self.direction))


CURVE_OPERATOR_CLASSES = (
    REDENGINE_OT_curve_point_add,
    REDENGINE_OT_curve_point_remove,
    REDENGINE_OT_curve_points_sort,
    REDENGINE_OT_curve_points_reset,
    REDENGINE_OT_curve_widget_init,
    REDENGINE_OT_curve_widget_push,
    REDENGINE_OT_curve_widget_apply,
    REDENGINE_OT_curve_point_move,
)
