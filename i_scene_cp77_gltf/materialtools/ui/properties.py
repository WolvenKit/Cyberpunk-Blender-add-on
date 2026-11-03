import bpy

from ..depot.state import (
    get_depot_template_index,
    get_material_depot_path,
    set_depot_template_index,
    set_material_depot_path,
)
from ..runtime.callbacks import (
    apply_metalin_ovrd,
    apply_metalout_ovrd,
    apply_microblend_mlsetup,
    apply_normalstr_ovrd,
    apply_roughin_ovrd,
    apply_roughout_ovrd,
    apply_template_preview,
    apply_view_mask,
    apply_view_mask_mode,
    get_layer_opacity,
    get_metalin_ovrd,
    get_metalout_ovrd,
    get_normalstr_ovrd,
    get_roughin_ovrd,
    get_roughout_ovrd,
    load_panel_data,
    microblend_filter,
    set_layer_opacity,
)


class CP77MlPropertyGroup(bpy.types.PropertyGroup):
    materialtools_mask_resolution_enum: bpy.props.EnumProperty(
        name="Mask Resolution",
        items=(
            ("256", "256", "256 × 256"),
            ("512", "512", "512 × 512"),
            ("1024", "1K", "1024 × 1024"),
            ("2048", "2K", "2048 × 2048"),
            ("4096", "4K", "4096 × 4096"),
        ),
        default="1024",
    )
    material_depot_path: bpy.props.StringProperty(
        name="Material Depot",
        subtype="DIR_PATH",
        get=get_material_depot_path,
        set=set_material_depot_path,
    )
    # The Multilayer Depot list's selection, held as the palette so palettes added by imports do not move it.
    depot_template: bpy.props.PointerProperty(type=bpy.types.Palette)
    depot_template_index: bpy.props.IntProperty(
        name="Multilayer Template",
        get=get_depot_template_index,
        set=set_depot_template_index,
    )
    depot_template_filter: bpy.props.StringProperty(name="Filter")
    multilayer_index_int: bpy.props.IntProperty(
        name="Layer", default=1, min=1, max=20, update=load_panel_data
    )
    multilayer_object_bool: bpy.props.BoolProperty(name="", default=False)
    multilayer_mask_preview_mode_enum: bpy.props.EnumProperty(
        name="Mask Preview",
        description="Choose the multilayer mask diagnostic shown in the viewport",
        items=(
            (
                "MASK",
                "Mask",
                "Show the raw mask image being painted, without layer opacity or microblend",
            ),
            (
                "CONTRIBUTING",
                "Layers",
                "Show the number of multilayer layers contributing at each texel",
            ),
            (
                "COMPLEXITY",
                "Complexity",
                "Show relative stored mask complexity weighted by mask resolution",
            ),
        ),
        default="MASK",
        update=apply_view_mask_mode,
    )
    multilayer_view_mask_bool: bpy.props.BoolProperty(
        name="View Mask",
        description="Preview matching masks on all meshes using the selected MLTemplate",
        default=False,
        update=apply_view_mask,
    )
    multilayer_template_preview_bool: bpy.props.BoolProperty(
        name="Preview MLTemplate",
        description="Solo the selected MLTemplate on all meshes using it, without other layers or microblend",
        default=False,
        update=apply_template_preview,
    )
    multilayer_paint_mask_bool: bpy.props.BoolProperty(name="Paint Mask", default=False)
    multilayer_paint_mask_enable_bool: bpy.props.BoolProperty(name="", default=False)
    multilayer_has_linked_layer: bpy.props.BoolProperty(name="", default=True)
    multilayer_has_generated_overrides: bpy.props.BoolProperty(name="", default=False)
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
    multilayer_opacity_float: bpy.props.FloatProperty(
        name="Opacity",
        description="Opacity of the selected layer",
        min=0.0,
        max=1.0,
        get=get_layer_opacity,
        set=set_layer_opacity,
    )
    multilayer_microblend_pointer: bpy.props.PointerProperty(
        type=bpy.types.Image,
        name="Microblend",
        update=apply_microblend_mlsetup,
        poll=microblend_filter,
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
