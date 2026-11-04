import bpy

from ....animation.domain.animgraph.shared_meta_pose import resource_stem
from ....blender.animgraph.rig_binding import binding_tree
from ...operators.animgraph.context import animgraph_editor_poll


class REDENGINE_PT_graph_source(bpy.types.Panel):
    bl_idname = "REDENGINE_PT_graph_source"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Graph"
    bl_label = "Graph"
    bl_order = 0

    @classmethod
    def poll(cls, context):
        return animgraph_editor_poll(context)

    def draw(self, context):
        layout = self.layout
        root = binding_tree(context.space_data.node_tree)
        row = layout.row(align=True)
        row.operator("import_scene.cp77_animgraph", text="Open", icon="FILE_FOLDER")
        row.operator("redengine.export_animgraph", text="Export", icon="EXPORT")
        row.operator("redengine.validate_graph", text="Check", icon="CHECKMARK")
        col = layout.column(align=True)
        col.prop(root, "red_bound_armature", text="Armature")
        if root.red_bound_armature is not None:
            part = (
                resource_stem(root.red_rig_part, ".rig.json")
                if root.red_rig_part
                else "Automatic"
            )
            col.operator_menu_enum(
                "redengine.bind_rig_part", "part", text=part, icon="ARMATURE_DATA"
            )
