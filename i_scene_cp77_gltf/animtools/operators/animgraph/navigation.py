import bpy

from ....animation.model.animgraph.constants import ANIMGRAPH_TREE_ID
from ....blender.animgraph.navigation_path import go_to
from ....blender.context import node_editor_tree
from ....core.log import get_logger
from ....core.notifications import report

_LOG = get_logger(__name__)


class REDENGINE_OT_enter_group(bpy.types.Operator):
    bl_idname = "redengine.enter_group"
    bl_label = "Enter Subgraph"
    bl_options = {"REGISTER", "UNDO"}

    node_name: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        return node_editor_tree(context, ANIMGRAPH_TREE_ID, edit=True) is not None

    def execute(self, context):
        space = context.space_data
        tree = space.edit_tree
        node = tree.nodes.get(self.node_name) if self.node_name else None
        if node is None:
            node = context.active_node
        if node is None or getattr(node, "node_tree", None) is None:
            report(self, "ERROR_INVALID_CONTEXT", "No subgraph to enter", logger=_LOG)
            return {"CANCELLED"}
        space.path.append(node.node_tree, node=node)
        return {"FINISHED"}


class REDENGINE_OT_exit_group(bpy.types.Operator):
    bl_idname = "redengine.exit_group"
    bl_label = "Exit Subgraph"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (
            space is not None
            and space.type == "NODE_EDITOR"
            and space.path is not None
            and len(space.path) > 1
        )

    def execute(self, context):
        context.space_data.path.pop()
        return {"FINISHED"}


class REDENGINE_OT_enter_editor_subgraph(bpy.types.Operator):
    bl_idname = "redengine.enter_editor_subgraph"
    bl_label = "Enter Editor Subgraph"
    bl_options = {"REGISTER", "UNDO"}

    tree_name: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return space is not None and space.type == "NODE_EDITOR"

    def execute(self, context):
        tree = bpy.data.node_groups.get(self.tree_name) if self.tree_name else None
        if tree is None:
            report(self, "WARNING", "Editor subgraph not found", logger=_LOG)
            return {"CANCELLED"}
        try:
            context.space_data.path.append(tree)
        except TypeError:
            # Trees that cannot join the editor path are shown directly instead.
            context.space_data.node_tree = tree
        return {"FINISHED"}


class REDENGINE_OT_go_to_level(bpy.types.Operator):
    bl_idname = "redengine.go_to_level"
    bl_label = "Go to Level"
    bl_description = "Show this level of the graph"

    index: bpy.props.IntProperty(options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return node_editor_tree(context, ANIMGRAPH_TREE_ID) is not None

    def execute(self, context):
        area = context.area
        go_to(
            context.space_data,
            int(area.as_pointer()) if area is not None else 0,
            self.index,
        )
        return {"FINISHED"}


NAVIGATION_OPERATOR_CLASSES = (
    REDENGINE_OT_go_to_level,
    REDENGINE_OT_enter_group,
    REDENGINE_OT_exit_group,
    REDENGINE_OT_enter_editor_subgraph,
)
