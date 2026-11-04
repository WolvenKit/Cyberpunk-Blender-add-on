import bpy

from ....animation.model.animgraph.constants import ANIMGRAPH_TREE_ID
from ....animation.model.animgraph.handles import normalized_source_handle
from ....blender.animgraph.results_overlay import POSE_SOCKET_ID
from ....blender.animgraph.rig_binding import binding_tree
from ....blender.context import node_editor_tree
from ....collisiontools.runtime.dangle.preview import (
    graph_runtime,
    graph_tree_previewing,
    set_view_handle,
)
from ....core.log import get_logger
from ....core.notifications import report

_LOG = get_logger(__name__)


class REDENGINE_OT_view_node_pose(bpy.types.Operator):
    bl_idname = "redengine.view_node_pose"
    bl_label = "Show Node Pose"
    bl_description = "Show this node's pose on the rig instead of the graph's final pose; again to return"
    bl_options = {"REGISTER"}

    node_name: bpy.props.StringProperty(options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        tree = node_editor_tree(context, ANIMGRAPH_TREE_ID, edit=True)
        return tree is not None and graph_tree_previewing(binding_tree(tree))

    def invoke(self, context, event):
        bpy.ops.node.select(
            location=(event.mouse_region_x, event.mouse_region_y), deselect_all=True
        )
        node = context.space_data.edit_tree.nodes.active
        if node is None or not node.select:
            return {"PASS_THROUGH"}
        self.node_name = node.name
        return self.execute(context)

    def execute(self, context):
        tree = context.space_data.edit_tree
        node = tree.nodes.get(self.node_name)
        handle = (
            normalized_source_handle(getattr(node, "red_handle_id", ""))
            if node is not None
            else ""
        )
        if not handle or not any(
            socket.bl_idname == POSE_SOCKET_ID for socket in node.outputs
        ):
            report(
                self,
                "WARNING",
                "Only a node that outputs a pose can be shown",
                logger=_LOG,
            )
            return {"CANCELLED"}
        root = binding_tree(tree)
        if root.red_preview.view_handle == handle:
            set_view_handle(root, None)
            return {"FINISHED"}
        runtime = graph_runtime(root)
        if (
            runtime is not None
            and handle in runtime.results().ran
            and not runtime.has_pose(handle)
        ):
            report(
                self,
                "WARNING",
                f"{node.name} outputs an additive difference, not a pose: show the blend that adds it",
                logger=_LOG,
            )
            return {"CANCELLED"}
        set_view_handle(root, handle)
        return {"FINISHED"}


class REDENGINE_OT_show_final_pose(bpy.types.Operator):
    bl_idname = "redengine.show_final_pose"
    bl_label = "Back to Final Pose"
    bl_description = "Show the graph's final pose on the rig again"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        tree = node_editor_tree(context, ANIMGRAPH_TREE_ID, edit=True)
        return tree is not None and bool(binding_tree(tree).red_preview.view_handle)

    def execute(self, context):
        set_view_handle(binding_tree(context.space_data.edit_tree), None)
        return {"FINISHED"}


NODE_POSE_OPERATOR_CLASSES = (
    REDENGINE_OT_view_node_pose,
    REDENGINE_OT_show_final_pose,
)
