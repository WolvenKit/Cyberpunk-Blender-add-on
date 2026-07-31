import bpy

from .callbacks import (
    apply_metalin_ovrd,
    apply_metalout_ovrd,
    apply_microblend_mlsetup,
    apply_mltemplate,
    apply_normalstr_ovrd,
    apply_paint_mask,
    apply_roughin_ovrd,
    apply_roughout_ovrd,
    apply_view_mask,
    get_metalin_ovrd,
    get_metalout_ovrd,
    get_normalstr_ovrd,
    get_roughin_ovrd,
    get_roughout_ovrd,
    load_panel_data,
    microblend_filter,
)


class CP77MlPropertyGroup(bpy.types.PropertyGroup):
    multilayer_index_int: bpy.props.IntProperty(
        name="Layer", default=1, min=1, max=20, update=load_panel_data
    )
    multilayer_object_bool: bpy.props.BoolProperty(name="", default=False)
    multilayer_overrides_disconnected_bool: bpy.props.BoolProperty(
        name="Toggle Override Method", default=False
    )
    multilayer_view_mask_bool: bpy.props.BoolProperty(
        name="View Mask", default=False, update=apply_view_mask
    )
    multilayer_paint_mask_bool: bpy.props.BoolProperty(
        name="Paint Mask", default=False, update=apply_paint_mask
    )
    multilayer_paint_mask_enable_bool: bpy.props.BoolProperty(name="", default=False)
    multilayer_has_linked_layer: bpy.props.BoolProperty(name="", default=True)
    multilayer_has_generated_overrides: bpy.props.BoolProperty(name="", default=False)
    multilayer_palette_string: bpy.props.StringProperty(
        name="MLTEMPLATE", update=apply_mltemplate
    )
    multilayer_normalstr_enum: bpy.props.EnumProperty(
        name="NormalStrength",
        description="NormalStrength",
        items=get_normalstr_ovrd,
        update=apply_normalstr_ovrd,
    )
    multilayer_metalin_enum: bpy.props.EnumProperty(
        name="MetalLevelsIn",
        description="MetalLevelsIn",
        items=get_metalin_ovrd,
        update=apply_metalin_ovrd,
    )
    multilayer_metalout_enum: bpy.props.EnumProperty(
        name="MetalLevelsOut",
        description="MetalLevelsOut",
        items=get_metalout_ovrd,
        update=apply_metalout_ovrd,
    )
    multilayer_roughin_enum: bpy.props.EnumProperty(
        name="RoughLevelsIn",
        description="RoughLevelsIn",
        items=get_roughin_ovrd,
        update=apply_roughin_ovrd,
    )
    multilayer_roughout_enum: bpy.props.EnumProperty(
        name="RoughLevelsOut",
        description="RoughLevelsOut",
        items=get_roughout_ovrd,
        update=apply_roughout_ovrd,
    )
    multilayer_microblend_pointer: bpy.props.PointerProperty(
        type=bpy.types.Image,
        name="Microblend",
        update=apply_microblend_mlsetup,
        poll=microblend_filter,
    )
    multilayer_microblend_filter_bool: bpy.props.BoolProperty(
        name="Microblend Filter",
        description="Filters available images for filepaths containing 'microblend'",
        default=True,
    )
    multilayer_layergroup_string: bpy.props.StringProperty(name="", default="")
    last_palette: bpy.props.PointerProperty(type=bpy.types.Palette)
    last_palette_color: bpy.props.FloatVectorProperty(
        name="r",
        subtype="COLOR",
        default=(1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
    )
    last_paint_brush: bpy.props.StringProperty(name="")
    last_active_object: bpy.props.PointerProperty(type=bpy.types.Object)
    last_active_material: bpy.props.PointerProperty(type=bpy.types.Material)
    last_multilayer_index: bpy.props.IntProperty(name="", default=0)
