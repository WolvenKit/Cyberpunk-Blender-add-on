from bpy.types import Panel

from ...addon_identity import get_addon_preferences
from .tabs import (
    draw_characters_tab,
    draw_cloth_tab,
    draw_modelling_tab,
    draw_utilities_tab,
)


class CP77_PT_MeshTools(Panel):
    bl_label = "Mesh Tools"
    bl_idname = "CP77_PT_MeshTools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CP77 Modding"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        preferences = get_addon_preferences(context)
        if preferences.context_only:
            return context.active_object and context.active_object.type == "MESH"
        return True

    def draw(self, context):
        preferences = get_addon_preferences(context)
        if not preferences.show_modtools or not preferences.show_meshtools:
            return

        layout = self.layout
        props = context.scene.cp77_panel_props
        row = layout.row(align=True)
        row.prop(props, "meshtab", expand=True)
        layout.separator()

        selected_meshes = tuple(obj for obj in context.selected_objects if obj.type == "MESH")
        active = context.active_object
        has_mesh = active is not None and active.type == "MESH"
        has_meshes = len(selected_meshes) > 1
        has_armature = active is not None and active.type == "ARMATURE"

        if props.meshtab == "UTILITIES":
            draw_utilities_tab(context, layout, has_mesh, has_meshes, has_armature)
        elif props.meshtab == "MODELLING":
            draw_modelling_tab(context, layout, has_mesh, has_meshes)
        elif props.meshtab == "CHARACTERS":
            draw_characters_tab(context, layout, has_mesh)
        elif props.meshtab == "CLOTH":
            draw_cloth_tab(context, layout, has_mesh)
