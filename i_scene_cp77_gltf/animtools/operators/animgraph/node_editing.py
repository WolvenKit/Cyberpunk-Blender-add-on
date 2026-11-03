import bpy

from ....animation.model.animgraph import direct_conn, point_constraint, simple_bounce
from ....blender.operator_results import finish_operator
from ...services.animgraph import editing
from .context import active_node

_POINT_CONSTRAINT = frozenset({point_constraint.RED_TYPE})
_SIMPLE_BOUNCE = frozenset({simple_bounce.RED_TYPE})
_DIRECT_CONN = frozenset({direct_conn.RED_TYPE})


class REDENGINE_OT_direct_conn_channels(bpy.types.Operator):
    bl_idname = "redengine.direct_conn_channels"
    bl_label = "Set Direct Connection Channels"
    bl_options = {"REGISTER", "UNDO"}

    channel_group: bpy.props.EnumProperty(
        name="Channel Group",
        items=(
            ("POSITION", "Position", "Position channels"),
            ("ROTATION", "Rotation", "Rotation channels"),
            ("SCALE", "Scale", "Scale channels"),
            ("ALL", "All", "All transform channels"),
            ("CLEAR", "Clear", "Disable all transform channels"),
        ),
        default="ALL",
    )

    @classmethod
    def poll(cls, context):
        return active_node(context, _DIRECT_CONN)[1] is not None

    def execute(self, context):
        _tree, node = active_node(context, _DIRECT_CONN)
        return finish_operator(
            self, editing.set_direct_conn_channels(node, self.channel_group)
        )


class REDENGINE_OT_point_constraint_input(bpy.types.Operator):
    bl_idname = "redengine.point_constraint_input"
    bl_label = "Edit Point Constraint Input"
    bl_options = {"REGISTER", "UNDO"}

    item_index: bpy.props.IntProperty(default=-1)
    action: bpy.props.EnumProperty(
        items=(
            ("ADD", "Add", "Add a weighted transform input"),
            ("REMOVE", "Remove", "Remove the active weighted transform input"),
            ("UP", "Up", "Move the input earlier"),
            ("DOWN", "Down", "Move the input later"),
        )
    )

    @classmethod
    def poll(cls, context):
        return active_node(context, _POINT_CONSTRAINT)[0] is not None

    def execute(self, context):
        _tree, node = active_node(context, _POINT_CONSTRAINT)
        return finish_operator(
            self,
            editing.edit_node_list(
                node, "red_point_constraint_inputs", self.action, self.item_index
            ),
        )


class REDENGINE_OT_simple_bounce_transform_output(bpy.types.Operator):
    bl_idname = "redengine.simple_bounce_transform_output"
    bl_label = "Edit Simple Bounce Transform Output"
    bl_options = {"REGISTER", "UNDO"}

    item_index: bpy.props.IntProperty(default=-1)
    action: bpy.props.EnumProperty(
        items=(
            ("ADD", "Add", "Add a transform output"),
            ("REMOVE", "Remove", "Remove the active transform output"),
            ("UP", "Up", "Move the active transform output earlier"),
            ("DOWN", "Down", "Move the active transform output later"),
        )
    )

    @classmethod
    def poll(cls, context):
        return active_node(context, _SIMPLE_BOUNCE)[0] is not None

    def execute(self, context):
        _tree, node = active_node(context, _SIMPLE_BOUNCE)
        return finish_operator(
            self,
            editing.edit_node_list(
                node,
                "red_simple_bounce_transform_outputs",
                self.action,
                self.item_index,
            ),
        )


class REDENGINE_OT_simple_bounce_channel_entry(bpy.types.Operator):
    bl_idname = "redengine.simple_bounce_channel_entry"
    bl_label = "Edit Simple Bounce Channel Entry"
    bl_options = {"REGISTER", "UNDO"}

    transform_output_index: bpy.props.IntProperty(default=-1)
    item_index: bpy.props.IntProperty(default=-1)
    action: bpy.props.EnumProperty(
        items=(
            ("ADD", "Add", "Add a channel entry"),
            ("REMOVE", "Remove", "Remove the active channel entry"),
            ("UP", "Up", "Move the active channel entry earlier"),
            ("DOWN", "Down", "Move the active channel entry later"),
        )
    )

    @classmethod
    def poll(cls, context):
        return active_node(context, _SIMPLE_BOUNCE)[0] is not None

    def execute(self, context):
        _tree, node = active_node(context, _SIMPLE_BOUNCE)
        return finish_operator(
            self,
            editing.edit_bounce_channel_entries(
                node, self.transform_output_index, self.action, self.item_index
            ),
        )


class REDENGINE_OT_simple_bounce_track_output(bpy.types.Operator):
    bl_idname = "redengine.simple_bounce_track_output"
    bl_label = "Edit Simple Bounce Track Output"
    bl_options = {"REGISTER", "UNDO"}

    item_index: bpy.props.IntProperty(default=-1)
    action: bpy.props.EnumProperty(
        items=(
            ("ADD", "Add", "Add a track output"),
            ("REMOVE", "Remove", "Remove the active track output"),
            ("UP", "Up", "Move the active track output earlier"),
            ("DOWN", "Down", "Move the active track output later"),
        )
    )

    @classmethod
    def poll(cls, context):
        return active_node(context, _SIMPLE_BOUNCE)[0] is not None

    def execute(self, context):
        _tree, node = active_node(context, _SIMPLE_BOUNCE)
        return finish_operator(
            self,
            editing.edit_node_list(
                node, "red_simple_bounce_track_outputs", self.action, self.item_index
            ),
        )


NODE_EDITING_OPERATOR_CLASSES = (
    REDENGINE_OT_direct_conn_channels,
    REDENGINE_OT_point_constraint_input,
    REDENGINE_OT_simple_bounce_transform_output,
    REDENGINE_OT_simple_bounce_channel_entry,
    REDENGINE_OT_simple_bounce_track_output,
)
