import bpy
from bpy.types import Panel

from ..addon_identity import get_addon_preferences
from .editor import editable_layer_sockets
from .state import resolve_material_state, resolve_template_state


def _id_property(owner, name, default=None):
    try:
        return owner.get(name, default) if owner is not None else default
    except (AttributeError, ReferenceError, TypeError):
        return default


class CP77_PT_MaterialTools(Panel):
    bl_label = "Material Tools"
    bl_idname = "CP77_PT_MaterialTools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CP77 Modding"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        prefs = get_addon_preferences(context)
        if not getattr(prefs, "show_modtools", True):
            return False
        if getattr(prefs, "context_only", False):
            obj = getattr(context, "active_object", None)
            return obj is not None and getattr(obj, "type", None) == "MESH"
        return True

    def draw(self, context):
        layout = self.layout
        props = context.scene.cp77_ml_props
        state = resolve_material_state(context)
        palette = state.palette

        header = layout.box()
        header.label(
            text=getattr(state.material, "name", "No active material"),
            icon="MATERIAL",
        )
        row = header.row(align=True)
        row.operator("reload_material.cp77", icon="FILE_REFRESH")
        row.operator("relocate_mesh.mlsetup", icon="ZOOM_ALL")
        row = header.row(align=True)
        row.operator("export_scene.mi", icon="EXPORT")
        row.operator("export_scene.hp", icon="STRANDS")
        header.operator("create_multilayer_material.mlsetup", icon="NODE_COMPOSITING")

        tools = layout.box()
        title = tools.row(align=True)
        title.label(text="MULTILAYERED")
        title.operator(
            "generate_layer_overrides_disconnected.mlsetup",
            text="",
            icon="MESH_MONKEY",
        )
        row = tools.row(align=True)
        row.operator("export_scene.mlsetup")
        row.operator("export_scene.mlmask")
        tools.operator("generate_masks.mlsetup", icon="IMAGE_DATA")

        editor = layout.box()
        if state.material is None or _id_property(state.material, "MLSetup") is None:
            message = editor.row()
            message.alignment = "CENTER"
            message.scale_y = 2
            message.label(text="Select a multilayer material to edit", icon="INFO")
            return
        if state.root_node is None:
            box = editor.box()
            box.alert = True
            box.label(text="Multilayer root node is missing", icon="ERROR")
            box.label(text="Reload or rebuild this material")
            return

        row = editor.row(align=True)
        if props.multilayer_has_generated_overrides:
            row.alert = True
            row.label(text="Palette data is missing", icon="ERROR")
            row.operator("generate_layer_overrides.mlsetup", text="Generate")
        elif palette is None:
            row.alert = True
            row.label(text="No active multilayer palette", icon="ERROR")
            row.operator("generate_layer_overrides.mlsetup", text="Generate")
        else:
            row.prop_search(
                props,
                "multilayer_palette_string",
                bpy.data,
                "palettes",
                text="",
                icon="NODE_MATERIAL",
            )
        row.prop(props, "multilayer_index_int", text="")

        if not state.valid_layer:
            diagnostic = editor.box()
            diagnostic.alert = True
            diagnostic.label(text=state.error_message or "Selected layer is not linked", icon="ERROR")
            return
        template = resolve_template_state(state.layer_node)
        if template.errors:
            diagnostic = editor.box()
            diagnostic.alert = True
            for message in template.errors:
                diagnostic.label(text=message, icon="ERROR")

        row = editor.row(align=True)
        row.prop(props, "multilayer_microblend_pointer", text="", icon="NODE_TEXTURE")
        row.prop(
            props,
            "multilayer_microblend_filter_bool",
            text="",
            icon="VIEWZOOM",
            toggle=True,
        )

        row = editor.row(align=True)
        paint_text = "Exit Mask Paint" if context.mode == "PAINT_TEXTURE" else "Paint Mask"
        paint_column = row.column()
        paint_column.enabled = props.multilayer_paint_mask_enable_bool
        paint_column.operator("enter_texture_paint.mlsetup", text=paint_text, icon="BRUSH_DATA")
        row.prop(props, "multilayer_view_mask_bool", toggle=True)

        editor.separator()
        levels = editor.row()
        metal = levels.box()
        metal.label(text="Metal Levels")
        metal.prop(props, "multilayer_metalin_enum", text="")
        metal.prop(props, "multilayer_metalout_enum", text="")
        rough = levels.box()
        rough.label(text="Rough Levels")
        rough.prop(props, "multilayer_roughin_enum", text="")
        rough.prop(props, "multilayer_roughout_enum", text="")

        row = editor.row(align=True)
        row.label(text="NormalStrength")
        row.prop(props, "multilayer_normalstr_enum", text="")

        sockets, missing = editable_layer_sockets(state)
        for socket, label in sockets:
            editor.prop(socket, "default_value", text=label)
        if missing:
            warning = editor.box()
            warning.alert = True
            warning.label(text="Missing layer controls", icon="ERROR")
            warning.label(text=", ".join(missing))

        template_path = _id_property(palette, "MLTemplatePath", "")
        if template_path:
            path_row = editor.row()
            path_row.enabled = False
            path_row.label(text=str(template_path).split(".")[0])
        paint = getattr(getattr(context, "tool_settings", None), "gpencil_paint", None)
        if context.mode != "PAINT_TEXTURE" and palette is not None and paint is not None:
            editor.template_palette(paint, "palette")
