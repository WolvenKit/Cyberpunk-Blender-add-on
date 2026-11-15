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
    check_unweighted_vertices: bpy.props.BoolProperty(
        name="Ungrouped Vertices",
        description="Find vertices without weights; Fix gives them their nearest weighted vertex's weights",
        default=True,
    )
    check_unused_bones: bpy.props.BoolProperty(
        name="Orphan Bones",
        description="Find armature bones no mesh carries weight on; Fix removes them",
        default=True,
    )
    check_unused_vertex_groups: bpy.props.BoolProperty(
        name="Unused Vertex Groups",
        description="Find vertex groups without weights; Fix removes them",
        default=True,
    )
    check_missing_uv: bpy.props.BoolProperty(
        name="Missing UV Layer",
        description="Find meshes without an active UV layer; Fix adds one",
        default=True,
    )
    check_degenerate_faces: bpy.props.BoolProperty(
        name="Degenerate Faces",
        description="Find faces without area; Fix dissolves them",
        default=True,
    )
    check_degenerate_uvs: bpy.props.BoolProperty(
        name="UV-Degenerate Faces",
        description="Find faces without UV area; Fix dissolves them",
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
