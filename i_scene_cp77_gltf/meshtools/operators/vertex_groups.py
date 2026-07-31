from bpy.props import BoolProperty
from bpy.types import Operator

from ...blender.collections import get_active_collection, get_selected_collection
from ..services.vertex_group_service import delete_empty_vertex_groups, group_ungrouped_vertices
from ..services.weight_transfer_service import transfer_weights
from .result import finish_operator


class CP77WeightTransfer(Operator):
    bl_idname = 'cp77.trans_weights'
    bl_label = "Cyberpunk 2077 Weight Transfer Tool"
    bl_description = "Transfer weights from source mesh to target mesh"
    vertInterop: BoolProperty(
            name="Use Nearest Vert Interpolated",
            description="Sometimes gives better results when the default mode fails",
            default=False
            )
    bySubmesh: BoolProperty(
            name="Transfer by Submesh Order",
            description="Because Mana Gets what Mana Wants :D",
            default=False
            )

    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        selected_collection = get_selected_collection()
        active_collection = get_active_collection()

        if active_collection and selected_collection and active_collection.name == selected_collection.name:
            active_collection = None

        props = context.scene.cp77_panel_props

        if selected_collection and active_collection:
            props.mesh_source = selected_collection.name
            props.mesh_target = active_collection.name
        elif selected_collection:
            props.mesh_target = selected_collection.name

        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        return finish_operator(
            self,
            transfer_weights(context, self.vertInterop, self.bySubmesh),
        )

    def draw(self, context):
        props = context.scene.cp77_panel_props

        layout = self.layout
        row = layout.row(align=True)
        split = row.split(factor=0.3, align=True)
        split.label(text="Source Mesh:")
        split.prop(props, "mesh_source", text="")
        row = layout.row(align=True)
        split = row.split(factor=0.3, align=True)
        split.label(text="Target Mesh:")
        split.prop(props, "mesh_target", text="")
        row = layout.row(align=True)
        row.prop(self, 'vertInterop', text="Use Nearest Vert Interpolation")
        row = layout.row(align=True)
        row.prop(self, 'bySubmesh')


class CP77GroupVerts(Operator):
    bl_idname = "cp77.group_verts"
    bl_parent_id = "CP77_PT_MeshTools"
    bl_label = "Assign to Nearest Group"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Assign ungrouped vertices to their nearest group"

    def execute(self, context):
        return finish_operator(self, group_ungrouped_vertices(context))


class CP77DeleteVertGroups(Operator):
    bl_idname = "cp77.del_empty_vgroup"
    bl_parent_id = "CP77_PT_MeshTools"
    bl_label = "Delete Unused Vertex Groups"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Delete empty vertex groups"

    def execute(self, context):
        return finish_operator(self, delete_empty_vertex_groups(context))
