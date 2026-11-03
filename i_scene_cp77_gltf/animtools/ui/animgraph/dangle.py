import bpy

from ....animation.model.animgraph.constants import ANIMGRAPH_TREE_ID
from ....blender.animgraph.variables import root_tree_for
from ....collisiontools.services.dangles.view import can_return_to_editor


class REDENGINE_PT_dangle_bridge(bpy.types.Panel):
    bl_idname = "REDENGINE_PT_dangle_bridge"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Graph"
    bl_label = "Dangle Editor"

    @classmethod
    def poll(cls, context):
        space = context.space_data
        if space is None or space.type != "NODE_EDITOR":
            return False
        tree = root_tree_for(space.node_tree)
        return bool(
            tree is not None
            and tree.bl_idname == ANIMGRAPH_TREE_ID
            and str(tree.get("cp77_dangle_rig", "") or "")
        )

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        if can_return_to_editor(context):
            row.operator("dangle.switch_to_editor", icon="VIEW3D", text="Editor View")

        sync_row = layout.row(align=True)
        sync_row.operator(
            "dangle.push_to_editor", icon="FILE_REFRESH", text="Resync Editor"
        )
