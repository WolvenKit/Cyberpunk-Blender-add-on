import bpy
from bpy.types import (
    Panel,
    UIList,
)

from ...blender.workspace import is_animation_workspace
from ...core.addon_identity import get_addon_preferences
from ...core.log import get_logger, log_once
from ...materials.blender.multilayer import linked_source
from ..common.access import node_input
from ..depot.state import (
    is_multilayer_template_palette,
    selected_template_palette,
)
from ..depot.thumbnails import microblend_icon
from ..multilayer.editor import editable_layer_sockets
from ..multilayer.palette import mltemplate_name_from_path
from ..multilayer.state import (
    id_property,
    resolve_material_state,
    resolve_template_state,
)

_LOG = get_logger(__name__)


class CP77_UL_MultilayerPalettes(UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        row = layout.row(align=True)
        row.label(text=item.name, icon="MATERIAL")

    def filter_items(self, context, data, property_name):
        items = getattr(data, property_name)
        props = context.scene.cp77_ml_props
        query = (
            str(getattr(props, "depot_template_filter", "") or "").casefold().strip()
        )
        flags = []
        for item in items:
            template_path = str(item.get("MLTemplatePath", "") or "")
            matched = is_multilayer_template_palette(item) and (
                not query
                or query in item.name.casefold()
                or query in template_path.casefold()
            )
            flags.append(self.bitflag_filter_item if matched else 0)
        return flags, []


def _mask_source(layer_node):
    return linked_source(node_input(layer_node, "Mask"))


def _mask_image(layer_node):
    source = _mask_source(layer_node)
    try:
        return (
            source.image if source is not None and source.type == "TEX_IMAGE" else None
        )
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_mask_image", type(error).__name__),
            "mask image: fell back after %s",
            error,
            exc_info=True,
        )
        return None


def _template_name(layer_node):
    template = resolve_template_state(layer_node)
    if template.template_path:
        return mltemplate_name_from_path(template.template_path)
    return "Unresolved"


def _draw_onboarding(layout, state):
    box = layout.box()
    if state.obj is None:
        box.label(text="Select a mesh", icon="MATERIAL")
        box.operator(
            "create_multilayer_object.mlsetup",
            text="Create Multilayer Object",
            icon="ADD",
        )
        return
    if state.material is None:
        box.label(text="The active mesh has no material.", icon="INFO")
    else:
        box.label(
            text=f"{state.material.name} is not a multilayer material.", icon="INFO"
        )
    row = box.row(align=True)
    row.operator(
        "create_multilayer_material.mlsetup", text="Create Multilayer", icon="ADD"
    )
    row.operator("cp77.load_material_template", text="Load .mt", icon="FILE_FOLDER")


def _draw_template_library(layout, props, state):
    header, panel = layout.panel(
        "cp77_materialtools_template_library", default_closed=True
    )
    header.label(text="Multilayer Depot", icon="ASSET_MANAGER")
    if panel is None:
        return

    panel.prop(props, "material_depot_path", text="")
    row = panel.row(align=True)
    row.operator("cp77.scan_material_depot", text="Scan", icon="FILE_REFRESH")
    row.operator("cp77.load_multilayer_template", text="Load One", icon="FILE_FOLDER")
    panel.prop(props, "depot_template_filter", text="", icon="VIEWZOOM")
    panel.template_list(
        "CP77_UL_MultilayerPalettes",
        "",
        bpy.data,
        "palettes",
        props,
        "depot_template_index",
        rows=4,
    )

    selected = selected_template_palette(props)
    if selected is not None:
        row = panel.row(align=True)
        row.label(text=selected.name, icon="MATERIAL")
        apply_col = row.column()
        apply_col.enabled = state.valid_layer
        apply_col.operator(
            "cp77.apply_multilayer_template", text="Apply", icon="CHECKMARK"
        )


def _draw_palette(layout, context, state):
    header, panel = layout.panel("cp77_materialtools_palette", default_closed=False)
    header.label(text="Palette", icon="COLOR")
    if panel is None:
        return
    layout = panel
    palette = state.palette
    row = layout.row(align=True)
    row.label(text="Palette", icon="COLOR")
    if palette is None:
        row.label(text="Unavailable", icon="ERROR")
    else:
        row.label(text=palette.name)

    color = node_input(state.layer_node, "ColorScale")
    if color is not None:
        swatch = row.row()
        swatch.enabled = False
        swatch.prop(color, "default_value", text="")

    if palette is None:
        return
    paint = getattr(getattr(context, "tool_settings", None), "gpencil_paint", None)
    if context.mode != "PAINT_TEXTURE" and paint is not None:
        try:
            layout.template_palette(paint, "palette")
        except (AttributeError, ReferenceError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_draw_palette", type(error).__name__),
                "draw palette: fell back after %s",
                error,
                exc_info=True,
            )


def _draw_mask_preview(layout, props):
    row = layout.row(align=True)
    row.label(text="Mask Preview", icon="HIDE_OFF")
    row.prop(props, "multilayer_mask_preview_mode_enum", text="")
    row.prop(props, "multilayer_view_mask_bool", text="", icon="HIDE_OFF", toggle=True)


def _draw_mask(layout, context, props, state):
    row = layout.row(align=True)
    row.label(text="Mask", icon="IMAGE_DATA")
    if state.layer_index == 1:
        row.label(text="Base layer")
        _draw_mask_preview(layout, props)
        return

    source = _mask_source(state.layer_node)
    image = _mask_image(state.layer_node)
    if source is not None and getattr(source, "type", None) != "TEX_IMAGE":
        row.alert = True
        row.label(text="Procedural mask", icon="ERROR")
        _draw_mask_preview(layout, props)
        return

    if image is None:
        row.alert = True
        row.label(text="Missing", icon="ERROR")
        row.prop(props, "materialtools_mask_resolution_enum", text="")
        op = row.operator("generate_active_mask.mlsetup", text="Create", icon="ADD")
        op.dimensions = props.materialtools_mask_resolution_enum
        _draw_mask_preview(layout, props)
        return

    if (
        state.mask_node is not None
        and getattr(state.mask_node, "type", None) == "TEX_IMAGE"
    ):
        try:
            row.prop(state.mask_node, "image", text="")
        except (AttributeError, ReferenceError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_draw_mask", type(error).__name__),
                "draw mask: fell back after %s",
                error,
                exc_info=True,
            )
            row.label(text=image.name)
    else:
        row.label(text=image.name)

    paint = layout.row(align=True)
    paint.enabled = (
        props.multilayer_paint_mask_enable_bool and context.mode != "PAINT_TEXTURE"
    )
    paint.operator(
        "enter_texture_paint.mlsetup",
        text="Paint Mask",
        icon="BRUSH_DATA",
    )
    _draw_mask_preview(layout, props)


def _draw_override_presets(layout, props):
    row = layout.row(align=True)
    row.label(text="Normal")
    row.prop(props, "multilayer_normalstr_enum", text="")

    grid = layout.grid_flow(columns=2, even_columns=True, even_rows=True, align=True)
    col = grid.column(align=True)
    col.label(text="Metal In / Out")
    pair = col.row(align=True)
    pair.prop(props, "multilayer_metalin_enum", text="")
    pair.prop(props, "multilayer_metalout_enum", text="")
    col = grid.column(align=True)
    col.label(text="Rough In / Out")
    pair = col.row(align=True)
    pair.prop(props, "multilayer_roughin_enum", text="")
    pair.prop(props, "multilayer_roughout_enum", text="")


def _draw_projection(layout, props, socket_map):
    row = layout.row(align=True)
    mat_tile = socket_map.get("MatTile")
    if mat_tile is not None:
        row.prop(mat_tile, "default_value", text="Mat Tile")
    if socket_map.get("Opacity") is not None:
        row.prop(props, "multilayer_opacity_float", text="Opacity")

    row = layout.row(align=True)
    offset_u = socket_map.get("OffsetU")
    offset_v = socket_map.get("OffsetV")
    if offset_u is not None:
        row.prop(offset_u, "default_value", text="Offset U")
    if offset_v is not None:
        row.prop(offset_v, "default_value", text="V")


def _draw_microblend(layout, props, socket_map):
    header, panel = layout.panel("cp77_materialtools_microblend", default_closed=True)
    header.label(text="Microblend", icon="TEXTURE")
    if panel is None:
        return
    layout = panel
    row = layout.row(align=True)
    row.prop(
        props, "multilayer_microblend_pointer", text="Microblend", icon="NODE_TEXTURE"
    )
    row.operator("cp77.load_depot_microblends", text="", icon="FILE_REFRESH")
    icon = microblend_icon(props.multilayer_microblend_pointer)
    if icon:
        layout.template_icon(icon_value=icon, scale=4.0)

    row = layout.row(align=True)
    strength = socket_map.get("MicroblendNormalStrength")
    contrast = socket_map.get("MicroblendContrast")
    if strength is not None:
        row.prop(strength, "default_value", text="Strength")
    if contrast is not None:
        row.prop(contrast, "default_value", text="Contrast")

    row = layout.row(align=True)
    tile = socket_map.get("MbTile")
    offset_u = socket_map.get("MicroblendOffsetU")
    offset_v = socket_map.get("MicroblendOffsetV")
    if tile is not None:
        row.prop(tile, "default_value", text="Tile")
    if offset_u is not None:
        row.prop(offset_u, "default_value", text="Offset U")
    if offset_v is not None:
        row.prop(offset_v, "default_value", text="V")


def _draw_multilayer_editor(layout, context, props, state):
    box = layout

    row = box.row(align=True)
    row.label(text="Multilayer", icon="NODE_MATERIAL")
    row.prop(props, "multilayer_index_int", text="Layer")
    row.operator("reload_material.cp77", text="", icon="FILE_REFRESH")

    row = box.row(align=True)
    current = resolve_template_state(state.layer_node) if state.valid_layer else None
    row.label(text="Template", icon="ASSET_MANAGER")
    row.label(
        text=_template_name(state.layer_node)
        if state.valid_layer
        else "No linked layer"
    )
    preview = row.column(align=True)
    preview.enabled = state.valid_layer
    preview.prop(
        props,
        "multilayer_template_preview_bool",
        text="Solo",
        icon="HIDE_OFF",
        toggle=True,
    )
    if current is not None and current.errors:
        row.alert = True
        row.label(text="", icon="ERROR")

    if not state.valid_layer:
        warning = box.row()
        warning.alert = True
        warning.label(
            text=state.error_message or "Selected layer is not linked", icon="ERROR"
        )
        return

    _draw_mask(box, context, props, state)
    _draw_palette(box, context, state)

    box.separator(factor=0.35)
    _draw_override_presets(box, props)

    sockets, missing = editable_layer_sockets(state)
    socket_map = {label: socket for socket, label in sockets}
    _draw_projection(box, props, socket_map)
    _draw_microblend(box, props, socket_map)

    if missing:
        warning = box.row()
        warning.alert = True
        warning.label(text="Missing controls: " + ", ".join(missing), icon="ERROR")

    tools = box.row(align=True)
    tools.operator("export_scene.mlsetup", text="Export MLSETUP", icon="EXPORT")
    tools.operator("export_scene.mlmask", text="Export MLMASK", icon="EXPORT")
    op = tools.operator("generate_masks.mlsetup", text="", icon="IMAGE_DATA")
    op.dimensions = props.materialtools_mask_resolution_enum


def _draw_material_utilities(layout, state):
    row = layout.row(align=True)
    row.label(
        text=getattr(state.material, "name", "No active material"), icon="MATERIAL"
    )
    row.operator("relocate_mesh.mlsetup", text="", icon="FILEBROWSER")
    row.operator("export_scene.mi", text="", icon="EXPORT")
    row.operator("export_scene.hp", text="", icon="STRANDS")


class CP77_PT_MaterialTools(Panel):
    bl_label = "Material Tools"
    bl_idname = "CP77_PT_MaterialTools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CP77 Modding"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        if is_animation_workspace(context):
            return False
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

        if context.mode == "PAINT_TEXTURE":
            layout.operator(
                "enter_texture_paint.mlsetup",
                text="Exit Mask Painting",
                icon="CHECKMARK",
            )

        _draw_material_utilities(layout, state)
        _draw_template_library(layout, props, state)

        if state.material is None or id_property(state.material, "MLSetup") is None:
            _draw_onboarding(layout, state)
            return
        if state.root_node is None:
            row = layout.row()
            row.alert = True
            row.label(text="Multilayer root node is missing", icon="ERROR")
            layout.operator(
                "reload_material.cp77", text="Reload Material", icon="FILE_REFRESH"
            )
            return

        _draw_multilayer_editor(layout, context, props, state)


MATERIAL_UI_CLASSES = (
    CP77_UL_MultilayerPalettes,
    CP77_PT_MaterialTools,
)
