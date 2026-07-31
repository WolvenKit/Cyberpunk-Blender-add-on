import bpy

from ....animation.animgraph_constants import ANIMGRAPH_TREE_ID

class REDENGINE_PT_subgraph_nav(bpy.types.Panel):
    bl_idname = "REDENGINE_PT_subgraph_nav"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "AnimGraph"
    bl_label = "Subgraph"

    @classmethod
    def poll(cls, context):
        space = context.space_data
        if space is None or space.type != 'NODE_EDITOR':
            return False
        tree = space.node_tree
        return tree is not None and tree.bl_idname == ANIMGRAPH_TREE_ID

    def draw(self, context):
        layout = self.layout
        space = context.space_data
        depth = len(space.path) if space.path else 0

        active = context.active_node
        if active is not None and getattr(active, "node_tree", None) is not None:
            enter = layout.operator(
                "redengine.enter_group",
                text=f"Enter {active.label or active.name}",
                icon='NODETREE',
            )
            enter.node_name = active.name

        if depth > 1:
            layout.operator("redengine.exit_group", text="Exit Subgraph", icon='LOOP_BACK')

        layout.label(text=f"Path depth: {depth}")
