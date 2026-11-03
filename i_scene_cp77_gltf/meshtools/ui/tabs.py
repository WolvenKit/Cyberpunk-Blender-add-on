from ...icons.cp77_icons import get_icon
from ..runtime.characters import character_sections
from ..services.submesh_service import is_safe_join_result
from ..services.uv_service import has_uv_checker, has_uv_density
from .validation import draw_glb_mesh_validation


def draw_utilities_tab(
    context, layout, has_mesh_selected, has_meshes_selected, has_armature_selected
):
    draw_glb_mesh_validation(context, layout)

    if has_armature_selected:
        box = layout.box()
        col = box.column()
        col.label(text="Clean up Armature", icon_value=get_icon("ARMATURE"))
        col.operator("delete_unused_bones.cp77", text="Delete unused bones")

    box = layout.box()
    box.label(text="Mesh Cleanup", icon_value=get_icon("TRAUMA"))
    col = box.column()
    col.operator("cp77.submesh_prep")
    col.operator("cp77.delete_orphan_bones", text="Delete Orphan Bones")

    if has_mesh_selected or has_meshes_selected:
        box = layout.box()
        box.label(text="Armature", icon_value=get_icon("ARMATURE"))
        col = box.column()
        col.operator("cp77.set_armature", text="Change Armature Target")

    if has_mesh_selected or has_meshes_selected:
        box = layout.box()
        box.label(text="Mirror Tools", icon_value=get_icon("MIRROR"))
        col = box.column()
        col.operator("cp77.mirror_x_axis", text="Safely mirror")
        col.operator("cp77.mirror_vertex_groups", text="Mirror Vertex Groups")
        box.operator("cp77.rotate_obj", text="Rotate Selected Objects")


def draw_modelling_tab(context, layout, has_mesh_selected, has_meshes_selected):

    box = layout.box()
    box.label(text="Vertex Groups", icon_value=get_icon("TRAUMA"))
    col = box.column()
    col.operator("cp77.group_verts", text="Group Ungrouped Verts")
    col.operator("cp77.del_empty_vgroup", text="Delete Unused Vert Groups")

    if not (has_mesh_selected or has_meshes_selected):
        box = layout.box()
        box.label(icon_value=get_icon("SCULPT"), text="Select a mesh")
        return

    box = layout.box()
    box.label(icon_value=get_icon("SCULPT"), text="Modelling:")
    col = box.column()
    col.operator("cp77.shrinkwrap", text="GarmentSupport/Decal")
    col.operator("cp77.trans_weights", text="Weight Transfer Tool")

    uv_box = layout.box()
    uv_box.label(text="UV Analysis")
    uv_col = uv_box.column(align=True)
    selected_meshes = tuple(
        obj for obj in context.selected_objects if obj.type == "MESH"
    )
    has_checker = any(has_uv_checker(obj) for obj in selected_meshes)
    has_density = any(has_uv_density(obj) for obj in selected_meshes)
    checker_row = uv_col.row(align=True)
    checker_row.operator("cp77.uv_checker", text="Apply UV Checker")
    if has_checker:
        checker_row.operator("cp77.uv_unchecker", text="Remove", icon="X")
    row = uv_col.row(align=True)
    if has_density:
        row.operator("cp77.uv_density", text="Refresh UV Density", icon="FILE_REFRESH")
        row.operator("cp77.uv_density_remove", text="Remove", icon="X")
    else:
        row.operator("cp77.uv_density", text="UV Density", icon="SHADING_RENDERED")
    uv_col.prop(
        context.scene.cp77_mesh_analysis, "uv_density_reference", text="Reference"
    )
    if has_uv_density(context.active_object):
        median = context.active_object.get("cp77_uv_density_median")
        low = context.active_object.get("cp77_uv_density_min")
        high = context.active_object.get("cp77_uv_density_max")
        if median is not None and low is not None and high is not None:
            uv_col.label(text=f"{low:.0f}–{high:.0f} px/m · median {median:.0f}")

    if has_mesh_selected and is_safe_join_result(context.active_object):
        col.operator("cp77.safe_split", text="Split into submeshes")
    elif has_meshes_selected:
        col.operator("cp77.safe_join", text="Join Meshes")

    box = layout.box()
    box.label(text="AKL Autofitter", icon_value=get_icon("REFIT"))
    col = box.column()
    col.operator("cp77.auto_fitter", text="Refit Selected Meshes")

    box = layout.box()
    box.label(text="Vertex Colours", icon="BRUSH_DATA")
    col = box.column()
    col.operator("cp77.apply_vertex_color_preset")
    col.operator("cp77.add_vertex_color_preset")
    col.operator("cp77.delete_vertex_color_preset")


def draw_characters_tab(context, layout):
    box = layout.box()
    box.label(text="Characters", icon="MESH_DATA")
    col = box.column()
    col.operator("cp77.load_base_character", icon="IMPORT")

    char_props = context.scene.cp77_character_shape
    has_head_shapes, has_breast_shapes = character_sections(char_props)

    if has_head_shapes:
        box = layout.box()
        box.label(text="Head Shape", icon="SHAPEKEY_DATA")
        col = box.column(align=True)
        col.prop(char_props, "eyes")
        col.prop(char_props, "nose")
        col.prop(char_props, "mouth")
        col.prop(char_props, "jaw")
        col.prop(char_props, "ears")

    if has_breast_shapes:
        box = layout.box()
        box.label(text="Body Shape", icon="SHAPEKEY_DATA")
        col = box.column(align=True)
        col.prop(char_props, "breasts")
