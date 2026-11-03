from bpy.types import Panel

from ...blender.workspace import is_animation_workspace
from ...core.addon_identity import get_addon_preferences
from ...core.log import get_logger
from .tabs import (
    draw_characters_tab,
    draw_modelling_tab,
    draw_utilities_tab,
)

_LOG = get_logger(__name__)


class CP77_PT_MeshTools(Panel):
    bl_label = "Mesh Tools"
    bl_idname = "CP77_PT_MeshTools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CP77 Modding"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        if is_animation_workspace(context):
            return False
        preferences = get_addon_preferences(context)
        if preferences.context_only:
            return bool(
                context.active_object
                and context.active_object.type in {"MESH", "ARMATURE"}
            )
        return True

    def draw(self, context):
        layout = self.layout
        try:
            preferences = get_addon_preferences(context)
            if not preferences.show_modtools or not preferences.show_meshtools:
                return

            props = context.scene.cp77_panel_props
            row = layout.row(align=True)
            row.prop(props, "meshtab", expand=True)
            layout.separator()

            selected_meshes = tuple(
                obj for obj in context.selected_objects if obj.type == "MESH"
            )
            active = context.active_object
            has_mesh = active is not None and active.type == "MESH"
            has_meshes = len(selected_meshes) > 1
            has_armature = active is not None and active.type == "ARMATURE"

            if props.meshtab == "UTILITIES":
                draw_utilities_tab(context, layout, has_mesh, has_meshes, has_armature)
            elif props.meshtab == "MODELLING":
                draw_modelling_tab(context, layout, has_mesh, has_meshes)
            elif props.meshtab == "CHARACTERS":
                draw_characters_tab(context, layout)
            elif props.meshtab == "CLOTH":
                layout.label(text="Install the Garment extension")
        except Exception as error:
            _LOG.error("Mesh Tools panel draw failed: %s", error, exc_info=True)
            layout.label(text=f"Mesh Tools UI error: {error}", icon="ERROR")
