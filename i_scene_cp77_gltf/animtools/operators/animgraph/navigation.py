import bpy

from ....animation.animgraph_constants import ANIMGRAPH_TREE_ID


class REDENGINE_OT_enter_group(bpy.types.Operator):
    bl_idname = "redengine.enter_group"
    bl_label = "Enter Subgraph"
    bl_options = {'REGISTER', 'UNDO'}

    node_name: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (
            space is not None
            and space.type == 'NODE_EDITOR'
            and space.edit_tree is not None
            and space.edit_tree.bl_idname == ANIMGRAPH_TREE_ID
        )

    def execute(self, context):
        space = context.space_data
        tree = space.edit_tree
        node = tree.nodes.get(self.node_name) if self.node_name else None
        if node is None:
            node = context.active_node
        if node is None or getattr(node, "node_tree", None) is None:
            self.report({'WARNING'}, "No subgraph to enter")
            return {'CANCELLED'}
        space.path.append(node.node_tree, node=node)
        return {'FINISHED'}


class REDENGINE_OT_exit_group(bpy.types.Operator):
    bl_idname = "redengine.exit_group"
    bl_label = "Exit Subgraph"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return (
            space is not None
            and space.type == 'NODE_EDITOR'
            and space.path is not None
            and len(space.path) > 1
        )

    def execute(self, context):
        context.space_data.path.pop()
        return {'FINISHED'}
