import bpy

from ....animation.model.animgraph.constants import ANIMGRAPH_TREE_ID
from ....blender.context import node_editor_tree
from ....blender.operator_results import execute_operation
from ...services.animgraph import editing


class REDENGINE_OT_add_node(bpy.types.Operator):
    bl_idname = "redengine.add_node"
    bl_label = "Add AnimGraph Node"
    bl_options = {"REGISTER", "UNDO"}

    node_type: bpy.props.StringProperty(
        name="Node Type",
        description="REDengine node $type without the animAnimNode_ prefix",
    )

    @classmethod
    def poll(cls, context):
        return node_editor_tree(context, ANIMGRAPH_TREE_ID, edit=True) is not None

    def invoke(self, context, event):
        self._cursor = context.space_data.cursor_location.copy()
        return self.execute(context)

    def execute(self, context):
        location = getattr(self, "_cursor", None)
        if location is None:
            location = (0.0, 0.0)
        return execute_operation(
            self,
            "Add AnimGraph node",
            editing.add_node,
            context.space_data.edit_tree,
            self.node_type,
            location,
        )
