from __future__ import annotations

from ...entity.domain.chunks import FULL_MASK, parse_mask, part_visible
from ...entity.model.component_types import SKINNED_TYPES
from ..operators.appearances import (
    CP77_OT_EntityDuplicateAppearance,
    CP77_OT_EntityMakeDefault,
    CP77_OT_EntityNewMeshAppearance,
    CP77_OT_EntityRemoveAppearance,
    CP77_OT_EntityRenameAppearance,
)
from ..operators.components import (
    CP77_OT_EntityAddComponent,
    CP77_OT_EntityPartVisibility,
    CP77_OT_EntityRemoveComponent,
    CP77_OT_EntityReplaceMesh,
    CP77_OT_EntityShowAllParts,
)
from ..operators.export import CP77_OT_EntityExport
from ..runtime.scene_cache import component_view, entity_index
from ..runtime.ui_refresh import choices_key, schedule_refresh
from ..services.selection import current_collection, selected_component
from .menus import (
    PART_CONTEXT_KEY,
    CP77_MT_EntityComponentMore,
    CP77_MT_EntityMeshAppearance,
    CP77_MT_EntityPartMaterial,
    CP77_MT_EntityRemoveMeshAppearance,
)


def _ready(tools, collection) -> bool:
    """Whether the selected appearance's state and pickers are prepared"""
    ready = collection is not None and collection.cp77_entity_state.initialized
    if not ready or tools.choices_key != choices_key(
        tools.entity, collection.name, tools.component_index
    ):
        schedule_refresh()
    return ready


def _draw_pickers(layout, tools, collection):
    layout.use_property_split = True
    layout.use_property_decorate = False
    layout.prop(tools, "entity")
    row = layout.row(align=True)
    row.prop(tools, "appearance")
    row.operator(CP77_OT_EntityDuplicateAppearance.bl_idname, text="", icon="DUPLICATE")
    row.operator(CP77_OT_EntityRenameAppearance.bl_idname, text="", icon="GREASEPENCIL")
    default = collection is not None and collection.cp77_entity_state.is_default
    row.operator(
        CP77_OT_EntityMakeDefault.bl_idname,
        text="",
        icon="SOLO_ON" if default else "SOLO_OFF",
    )
    row.operator(CP77_OT_EntityRemoveAppearance.bl_idname, text="", icon="TRASH")
    if tools.issues:
        layout.template_list(
            "CP77_UL_EntityIssues", "", tools, "issues", tools, "issue_index", rows=3
        )
    layout.operator(
        CP77_OT_EntityExport.bl_idname, text="Export Entity…", icon="EXPORT"
    )


def _draw_components(layout, tools, collection):
    row = layout.row()
    row.template_list(
        "CP77_UL_EntityComponents",
        "",
        collection.cp77_entity_state,
        "components",
        tools,
        "component_index",
        rows=8,
    )
    side = row.column(align=True)
    side.operator(CP77_OT_EntityAddComponent.bl_idname, text="", icon="ADD")
    side.operator(CP77_OT_EntityRemoveComponent.bl_idname, text="", icon="REMOVE")
    side.separator()
    side.menu(CP77_MT_EntityComponentMore.bl_idname, text="", icon="DOWNARROW_HLT")


def _draw_component(layout, tools, item, view):
    layout.use_property_split = True
    layout.use_property_decorate = False
    layout.prop(item, "name")
    layout.prop(item, "type_key")
    row = layout.row(align=True)
    if item.mesh_collection is not None:
        row.prop(item.mesh_collection, "name", text="Mesh")
    row.operator(CP77_OT_EntityReplaceMesh.bl_idname, text="", icon="FILE_REFRESH")
    if view.modelled:
        layout.prop(item, "base_mesh")
    layout.prop_search(item, "attach_target", tools, "attach_choices", text="Attach To")
    if tools.slot_choices:
        layout.prop_search(item, "attach_slot", tools, "slot_choices", text="Slot")
    if item.type_key in SKINNED_TYPES:
        layout.prop_search(
            item, "skin_target", tools, "rig_choices", text="Deform With"
        )


def _draw_mesh_appearance(layout, item, view):
    row = layout.row(align=True)
    row.menu(
        CP77_MT_EntityMeshAppearance.bl_idname, text=item.mesh_appearance or "default"
    )
    row.operator(CP77_OT_EntityNewMeshAppearance.bl_idname, text="", icon="DUPLICATE")
    row.menu(CP77_MT_EntityRemoveMeshAppearance.bl_idname, text="", icon="TRASH")
    names = view.mesh_appearances
    appearance_index = (
        names.index(item.mesh_appearance) if item.mesh_appearance in names else 0
    )
    mask = parse_mask(item.chunk_mask) if item.chunk_mask else FULL_MASK
    header = layout.row(align=True)
    header.alignment = "RIGHT"
    header.operator(CP77_OT_EntityShowAllParts.bl_idname, text="", icon="HIDE_OFF")
    column = layout.column(align=True)
    for part in view.parts:
        visible = part_visible(mask, part.index)
        row = column.row(align=True)
        operator = row.operator(
            CP77_OT_EntityPartVisibility.bl_idname,
            text="",
            emboss=False,
            icon="HIDE_OFF" if visible else "HIDE_ON",
        )
        operator.part, operator.visible = part.index, not visible
        row.label(
            text=part.material_names[0] if part.material_names else f"Part {part.index}"
        )
        material = (
            part.material_names[appearance_index]
            if appearance_index < len(part.material_names)
            else ""
        )
        row.context_pointer_set(PART_CONTEXT_KEY, part.objects[0])
        row.menu(CP77_MT_EntityPartMaterial.bl_idname, text=material or "None")


def draw_entity(layout, context):
    """The Entity section"""
    tools = getattr(context.scene, "cp77_entity_tools", None)
    if tools is None or not entity_index().entities:
        return
    header, body = layout.panel("cp77_scene_entity", default_closed=True)
    header.label(text="Entity")
    if not body:
        return
    collection = current_collection(context)
    ready = _ready(tools, collection)
    _draw_pickers(body.column(), tools, collection)
    if collection is None:
        return
    header, components = body.panel("cp77_entity_components", default_closed=False)
    header.label(text="Components")
    if components and ready:
        _draw_components(components, tools, collection)
    item = selected_component(collection, tools.component_index)
    if item is None:
        return
    view = component_view(collection, item.name)
    header, component = body.panel("cp77_entity_component", default_closed=False)
    header.label(text="Component")
    if component:
        _draw_component(component, tools, item, view)
    header, appearance = body.panel("cp77_entity_mesh_appearance", default_closed=False)
    header.label(text="Mesh Appearance")
    if appearance:
        _draw_mesh_appearance(appearance, item, view)
