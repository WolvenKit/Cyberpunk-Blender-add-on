from bpy.types import Panel, UIList

from ...blender.workspace import is_animation_workspace
from ...core.addon_identity import get_addon_preferences


def _meshtools_shown(context):
    if is_animation_workspace(context):
        return False
    preferences = get_addon_preferences(context)
    return bool(preferences.show_modtools and preferences.show_meshtools)


class CP77_UL_MeshAppearances(UIList):
    """Draws one row per mesh appearance"""

    bl_idname = "CP77_UL_mesh_appearances"

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_property, index
    ):
        layout.prop(item, "name", text="", emboss=False)


def draw_appearances_tab(context, layout):
    scene = context.scene
    if not len(scene.cp77_mesh_appearances):
        layout.operator("cp77.mesh_appearance_add", icon="ADD")
        return
    row = layout.row()
    row.template_list(
        "CP77_UL_mesh_appearances",
        "",
        scene,
        "cp77_mesh_appearances",
        scene,
        "cp77_mesh_appearance_index",
        rows=3,
    )
    column = row.column(align=True)
    column.operator("cp77.mesh_appearance_add", text="", icon="ADD")
    column.operator("cp77.mesh_appearance_remove", text="", icon="REMOVE")
    column = layout.column(align=True)
    column.operator("cp77.mesh_appearance_display")
    column.operator("cp77.mesh_appearance_assign")
    column.operator("cp77.mesh_appearance_reset")


class CP77_PT_MeshAppearanceMaterials(Panel):
    bl_label = "Mesh Appearances"
    bl_idname = "CP77_PT_MeshAppearanceMaterials"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return (
            obj is not None
            and obj.type == "MESH"
            and len(obj.material_slots) > 0
            and len(context.scene.cp77_mesh_appearances) > 0
            and _meshtools_shown(context)
        )

    def draw(self, context):
        layout = self.layout
        obj = context.object
        slot_index = obj.active_material_index
        for row_index, item in enumerate(obj.data.cp77_appearance_materials):
            if item.slot_index != slot_index:
                continue
            box = layout.box()
            header = box.row(align=True)
            header.prop(item, "material", text="")
            header.operator(
                "cp77.mesh_appearance_use_add", text="", icon="ADD"
            ).row = row_index
            header.operator(
                "cp77.mesh_appearance_material_remove", text="", icon="X"
            ).row = row_index
            for use_index, use in enumerate(item.appearances):
                line = box.row(align=True)
                line.prop(use, "appearance", text="")
                remove = line.operator(
                    "cp77.mesh_appearance_use_remove", text="", icon="REMOVE"
                )
                remove.row = row_index
                remove.use = use_index
        layout.operator("cp77.mesh_appearance_material_add", icon="ADD")
