import bpy

from ..blender.mesh_appearances import set_use_appearance

_VERTEX_GROUP_ITEMS = (("None", "None", "No vertex group"),)
_VERTEX_GROUP_SIGNATURE = None
_APPEARANCE_ITEMS = [("0", "", "", 0)]


def _selected_group_signature(context):
    selected = tuple(
        obj
        for obj in getattr(context, "selected_objects", ())
        if getattr(obj, "type", None) == "MESH"
    )
    return tuple(
        (obj.as_pointer(), tuple(group.name for group in obj.vertex_groups))
        for obj in selected
    )


def vertex_group_items(_owner, context):
    global _VERTEX_GROUP_ITEMS, _VERTEX_GROUP_SIGNATURE
    signature = _selected_group_signature(context)
    if signature == _VERTEX_GROUP_SIGNATURE:
        return _VERTEX_GROUP_ITEMS

    names = {name for _pointer, groups in signature for name in groups}
    preferred = sorted(name for name in names if name.casefold().startswith("group"))
    remaining = sorted(names.difference(preferred))
    _VERTEX_GROUP_ITEMS = tuple(
        [("None", "None", "No vertex group")]
        + [
            (name, name, f"Use '{name}' vertex group")
            for name in (*preferred, *remaining)
        ]
    )
    _VERTEX_GROUP_SIGNATURE = signature
    return _VERTEX_GROUP_ITEMS


def appearance_items(_owner, context):
    scene = getattr(context, "scene", None) or bpy.context.scene
    _APPEARANCE_ITEMS[:] = [
        (str(index), appearance.name, "", index)
        for index, appearance in enumerate(scene.cp77_mesh_appearances)
    ] or [("0", "", "", 0)]
    return _APPEARANCE_ITEMS


def clear_property_caches():
    global _VERTEX_GROUP_ITEMS, _VERTEX_GROUP_SIGNATURE
    _VERTEX_GROUP_ITEMS = (("None", "None", "No vertex group"),)
    _VERTEX_GROUP_SIGNATURE = None
    _APPEARANCE_ITEMS[:] = [("0", "", "", 0)]


class Vertex_Group_Properties(bpy.types.PropertyGroup):
    presets: bpy.props.EnumProperty(items=vertex_group_items, name="Vertex Group")


class MeshValidationProperties(bpy.types.PropertyGroup):
    is_skinned: bpy.props.BoolProperty(
        name="Skinned Mesh",
        description="Validate armature and vertex-group requirements used by skinned GLB export",
        default=True,
    )
    advanced_validation: bpy.props.BoolProperty(
        name="Additional Validation",
        description="Enable optional UV, degeneracy, weight, and unused-bone checks",
        default=False,
    )
    check_missing_uv: bpy.props.BoolProperty(
        name="Require Active UV Layer", default=True
    )
    check_degenerate_faces: bpy.props.BoolProperty(
        name="Check Degenerate Faces", default=True
    )
    check_degenerate_uvs: bpy.props.BoolProperty(
        name="Check Degenerate UVs", default=False
    )
    check_unweighted_vertices: bpy.props.BoolProperty(
        name="Check Unweighted Vertices", default=True
    )
    check_unused_bones: bpy.props.BoolProperty(name="Check Unused Bones", default=False)

    show_fixes: bpy.props.BoolProperty(name="Repair Options", default=False)
    fix_remove_unmatched_vertex_groups: bpy.props.BoolProperty(
        name="Remove Groups Without Bones",
        default=True,
    )
    fix_apply_autofitter_shape_keys: bpy.props.BoolProperty(
        name="Bake Autofitter Shape Keys",
        default=False,
    )
    fix_add_missing_uv: bpy.props.BoolProperty(
        name="Add Missing UV Layer", default=True
    )
    fix_dissolve_degenerate_faces: bpy.props.BoolProperty(
        name="Dissolve Degenerate Faces",
        default=True,
    )
    fix_dissolve_degenerate_uvs: bpy.props.BoolProperty(
        name="Dissolve UV-Degenerate Faces",
        default=False,
    )
    fix_assign_unweighted_vertices: bpy.props.BoolProperty(
        name="Assign Unweighted Vertices",
        description="Assign unweighted vertices to the armature's first bone with weight 0.01",
        default=False,
    )
    fix_remove_unused_bones: bpy.props.BoolProperty(
        name="Remove Unused Bones",
        description="Remove bones without matching vertex groups and preserve retained bone transforms",
        default=False,
    )
    fix_limit_influences: bpy.props.BoolProperty(
        name="Limit Bone Influences",
        description="Keep each vertex's 8 strongest bone influences and normalize them. This changes how those "
        "vertices deform",
        default=False,
    )

    last_status: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    last_report: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    last_mesh_count: bpy.props.IntProperty(default=0, min=0, options={"SKIP_SAVE"})
    last_issue_count: bpy.props.IntProperty(default=0, min=0, options={"SKIP_SAVE"})
    last_fix_count: bpy.props.IntProperty(default=0, min=0, options={"SKIP_SAVE"})
    last_remaining_count: bpy.props.IntProperty(default=0, min=0, options={"SKIP_SAVE"})


class MeshAnalysisProperties(bpy.types.PropertyGroup):
    uv_density_reference: bpy.props.FloatProperty(
        name="Reference Density",
        description="Texels per meter mapped to the center of the UV Density heat map",
        default=512.0,
        min=1.0,
        soft_max=4096.0,
        precision=0,
    )


class MeshAppearance(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name", default="appearance")


class MeshAppearanceUse(bpy.types.PropertyGroup):
    index: bpy.props.IntProperty(name="Appearance", min=0)
    appearance: bpy.props.EnumProperty(
        name="Appearance",
        description="The appearance that shows this material in the slot",
        items=appearance_items,
        get=lambda self: self.index,
        set=set_use_appearance,
    )


class MeshAppearanceMaterial(bpy.types.PropertyGroup):
    slot_index: bpy.props.IntProperty(name="Material Slot", min=0)
    material: bpy.props.PointerProperty(name="Material", type=bpy.types.Material)
    appearances: bpy.props.CollectionProperty(type=MeshAppearanceUse)


class MeshAppearanceOriginal(bpy.types.PropertyGroup):
    slot_index: bpy.props.IntProperty(name="Material Slot", min=0)
    material: bpy.props.PointerProperty(name="Material", type=bpy.types.Material)
