import bpy

from ..bartmoss.scalar import clamp01, lerp_three
from ..blender import shader_nodes
from ..blender.shader_nodes import set_default_if_changed
from ..blender.transactions import new_tracked_datablock
from ..materials.blender.nodes import create_node
from ..materials.cache_identity import filtered_material_data_identity
from .graph import combine_bundle_node, separate_bundle_node
from .mat_common import find_input, param_color, param_float
from .multilayer_coat import (
    COAT_SURFACE_ITEMS,
    apply_principled_multilayer_coat_values,
    build_coat_normal,
    build_selected_layer_coverage,
    coat_layer_mask_items,
    coat_layer_range_key,
    configure_principled_multilayer_coat,
    f0_to_ior,
    selected_layer_indices,
)
from .multilayered import Multilayered

_VEHICLE_DESTR_COAT_VERSION = 3
_VEHICLE_DESTR_COAT_CONTROLS = (
    ("FLOAT", "Weight"),
    ("FLOAT", "Roughness"),
    ("FLOAT", "IOR"),
    ("RGBA", "Tint Fwd"),
    ("RGBA", "Tint Side"),
    ("FLOAT", "Tint Exponent"),
    ("FLOAT", "Opacity"),
)


def _vehicle_coat_group_name(layer_count, selected):
    range_key = coat_layer_range_key(layer_count, selected)
    return f"CP77 Vehicle Destruction Coat L{layer_count} R{range_key} {_VEHICLE_DESTR_COAT_VERSION}.0"


def _vehicle_destruction_coat_group(layer_count, selected):
    name = _vehicle_coat_group_name(layer_count, selected)
    existing = bpy.data.node_groups.get(name)
    if existing is not None:
        return existing

    group = new_tracked_datablock("node_groups", name, "ShaderNodeTree")
    needs_masks = bool(selected) and len(selected) != layer_count and layer_count > 1
    if needs_masks:
        group.interface.new_socket(
            name="Layer Masks", socket_type="NodeSocketBundle", in_out="INPUT"
        )
    baked_normal = group.interface.new_socket(
        name="Baked Normal", socket_type="NodeSocketVector", in_out="INPUT"
    )
    baked_normal.default_value = (0.0, 0.0, 1.0)
    group.interface.new_socket(
        name="Controls", socket_type="NodeSocketBundle", in_out="INPUT"
    )
    group.interface.new_socket(
        name="Coat Surface", socket_type="NodeSocketBundle", in_out="OUTPUT"
    )

    group_input = create_node(group.nodes, "NodeGroupInput", (-1400, 0))
    group_output = create_node(group.nodes, "NodeGroupOutput", (980, 0))

    mask_sockets = {}
    if needs_masks:
        mask_unpack = separate_bundle_node(
            group,
            coat_layer_mask_items(layer_count),
            (-1160, -440),
            name="CP77 Vehicle Layer Masks Unpack",
            label="Layer Masks",
        )
        group.links.new(
            group_input.outputs["Layer Masks"], mask_unpack.inputs["Bundle"]
        )
        for index in range(1, layer_count):
            mask_sockets[index] = mask_unpack.outputs[f"Layer {index + 1} Mask"]

    controls = separate_bundle_node(
        group,
        _VEHICLE_DESTR_COAT_CONTROLS,
        (-1160, 340),
        name="CP77 Vehicle Coat Controls Unpack",
        label="Coat Controls",
    )
    group.links.new(group_input.outputs["Controls"], controls.inputs["Bundle"])

    coverage = build_selected_layer_coverage(
        group, selected, layer_count, mask_sockets, (-900, -520)
    )
    coat_normal = build_coat_normal(
        group, {"decoded": group_input.outputs["Baked Normal"]}, 1.0, (-820, 100)
    )

    layer_weight = create_node(group.nodes, "ShaderNodeLayerWeight", (-300, 80))
    layer_weight.label = "Vehicle Coat View Angle"
    normal_input = find_input(layer_weight, "Normal")
    if normal_input is not None and coat_normal is not None:
        group.links.new(coat_normal, normal_input)

    one_minus = shader_nodes.math(
        group.nodes,
        group.links,
        "SUBTRACT",
        label="Vehicle Coat 1-NdotV",
        location=(-100, 80),
        hide=True,
    ).node
    one_minus.inputs["Value"].default_value = 1.0
    group.links.new(
        layer_weight.outputs["Facing"],
        shader_nodes.socket_by_identifier(one_minus.inputs, "Value_001"),
    )

    power = shader_nodes.math(
        group.nodes,
        group.links,
        "POWER",
        label="Vehicle Coat Tint Fresnel",
        location=(80, 80),
        hide=True,
    ).node
    group.links.new(one_minus.outputs["Value"], power.inputs["Value"])
    group.links.new(
        controls.outputs["Tint Exponent"],
        shader_nodes.socket_by_identifier(power.inputs, "Value_001"),
    )

    tint_mix = create_node(group.nodes, "ShaderNodeMix", (260, 80), blend_type="MIX")
    tint_mix.label = "Vehicle Coat Refraction Tint"
    tint_mix.data_type = "RGBA"
    tint_mix.clamp_factor = True
    group.links.new(
        power.outputs["Value"],
        shader_nodes.socket_by_identifier(tint_mix.inputs, "Factor_Float"),
    )
    group.links.new(
        controls.outputs["Tint Fwd"],
        shader_nodes.socket_by_identifier(tint_mix.inputs, "A_Color"),
    )
    group.links.new(
        controls.outputs["Tint Side"],
        shader_nodes.socket_by_identifier(tint_mix.inputs, "B_Color"),
    )

    tint_factor = shader_nodes.math(
        group.nodes,
        group.links,
        "MULTIPLY",
        label="Vehicle Coat Tint Coverage",
        location=(260, -160),
        hide=True,
    ).node
    group.links.new(coverage, tint_factor.inputs["Value"])
    group.links.new(
        controls.outputs["Opacity"],
        shader_nodes.socket_by_identifier(tint_factor.inputs, "Value_001"),
    )

    final_tint = create_node(group.nodes, "ShaderNodeMix", (470, 40), blend_type="MIX")
    final_tint.label = "Vehicle Coat Multiplicative Tint"
    final_tint.data_type = "RGBA"
    final_tint.clamp_factor = True
    shader_nodes.socket_by_identifier(final_tint.inputs, "A_Color").default_value = (
        1.0,
        1.0,
        1.0,
        1.0,
    )
    group.links.new(
        tint_factor.outputs["Value"],
        shader_nodes.socket_by_identifier(final_tint.inputs, "Factor_Float"),
    )
    group.links.new(
        shader_nodes.socket_by_identifier(tint_mix.outputs, "Result_Color"),
        shader_nodes.socket_by_identifier(final_tint.inputs, "B_Color"),
    )

    coat_surface = combine_bundle_node(
        group,
        COAT_SURFACE_ITEMS,
        (710, 80),
        name="CP77 Vehicle Coat Surface Pack",
        label="Coat Surface",
    )
    group.links.new(controls.outputs["Weight"], coat_surface.inputs["Weight"])
    group.links.new(controls.outputs["Roughness"], coat_surface.inputs["Roughness"])
    group.links.new(controls.outputs["IOR"], coat_surface.inputs["IOR"])
    if coat_normal is not None:
        group.links.new(coat_normal, coat_surface.inputs["Normal"])
    group.links.new(
        shader_nodes.socket_by_identifier(final_tint.outputs, "Result_Color"),
        coat_surface.inputs["Tint"],
    )
    group.links.new(coat_surface.outputs["Bundle"], group_output.inputs["Coat Surface"])
    return group


def _write_vehicle_coat_controls(controls_pack, data):
    opacity = clamp01(param_float(data, "Opacity", 1.0))
    source_f0 = lerp_three((0.25, 0.04, 0.0), param_float(data, "CoatFresnelBias", 1.0))
    tint_fwd = param_color(data, "CoatTintFwd", (1.0, 1.0, 1.0, 1.0))
    inputs = controls_pack.inputs
    for socket_name, value in (
        ("Weight", 0.6 if opacity >= 0.001 else 0.0),
        ("Roughness", 0.05),
        ("IOR", max(1.0, f0_to_ior(source_f0))),
        ("Tint Fwd", tint_fwd),
        ("Tint Side", param_color(data, "CoatTintSide", tint_fwd)),
        (
            "Tint Exponent",
            lerp_three((0.25, 1.0, 6.0), param_float(data, "CoatTintFresnelBias", 1.0)),
        ),
        ("Opacity", opacity),
    ):
        set_default_if_changed(inputs[socket_name], value)


_PRINCIPLED_COAT_OPTIONS = dict(
    normal_strength=1.0,
    roughness=0.05,
    reflection_power=0.6,
)


def configure_vehicle_destruction_coat(data, context):
    tree = context["tree"]
    principled = context["principled"]
    layer_count = int(context["layer_count"])
    global_normal = context.get("global_normal")
    normal_source = None
    if global_normal:
        normal_source = global_normal.get("decoded")
        if normal_source is None:
            normal_source = global_normal.get("normal")
    if normal_source is None:
        return configure_principled_multilayer_coat(
            data, context, **_PRINCIPLED_COAT_OPTIONS
        )

    selected, range_mode = selected_layer_indices(data, layer_count)
    needs_masks = bool(selected) and len(selected) != layer_count and layer_count > 1
    mask_items = coat_layer_mask_items(layer_count) if needs_masks else ()
    mask_pack = None
    if mask_items:
        mask_pack = combine_bundle_node(
            tree,
            mask_items,
            (-420, -720),
            name="CP77 Vehicle Layer Masks Pack",
            label="Vehicle Layer Masks",
        )
        mask_pack["cp77_vehicle_destruction_role"] = "layer_masks"
        for index in range(1, layer_count):
            layer = (
                context["layer_nodes"][index]
                if index < len(context["layer_nodes"])
                else None
            )
            mask_socket = layer.outputs.get("Layer Mask") if layer is not None else None
            if mask_socket is not None:
                tree.links.new(mask_socket, mask_pack.inputs[f"Layer {index + 1} Mask"])

    controls_pack = combine_bundle_node(
        tree,
        _VEHICLE_DESTR_COAT_CONTROLS,
        (-420, -420),
        name="CP77 Vehicle Coat Controls Pack",
        label="Vehicle Coat Controls",
    )
    controls_pack["cp77_vehicle_destruction_role"] = "coat_controls"
    _write_vehicle_coat_controls(controls_pack, data)
    slots = context.get("slots")
    if slots is not None:
        slots["vehicle_coat_controls"] = controls_pack.name

    coat_node = create_node(tree.nodes, "ShaderNodeGroup", (-80, -520))
    coat_node.name = "CP77 Vehicle Destruction Coat"
    coat_node.label = "Vehicle Destruction Coat"
    coat_node["cp77_vehicle_destruction_role"] = "coat_stage"
    coat_node.node_tree = _vehicle_destruction_coat_group(layer_count, selected)
    if mask_pack is not None:
        tree.links.new(mask_pack.outputs["Bundle"], coat_node.inputs["Layer Masks"])
    tree.links.new(normal_source, coat_node.inputs["Baked Normal"])
    tree.links.new(controls_pack.outputs["Bundle"], coat_node.inputs["Controls"])

    coat_surface = separate_bundle_node(
        tree,
        COAT_SURFACE_ITEMS,
        (210, -420),
        name="CP77 Vehicle Coat Surface Unpack",
        label="Vehicle Coat Surface",
    )
    coat_surface["cp77_vehicle_destruction_role"] = "coat_surface"
    tree.links.new(coat_node.outputs["Coat Surface"], coat_surface.inputs["Bundle"])
    for source_name, target_name in (
        ("Weight", "Coat Weight"),
        ("Roughness", "Coat Roughness"),
        ("IOR", "Coat IOR"),
        ("Normal", "Coat Normal"),
        ("Tint", "Coat Tint"),
    ):
        target = find_input(principled, target_name)
        if target is not None:
            tree.links.new(coat_surface.outputs[source_name], target)

    return range_mode


class VehicleDestrBlendshape(Multilayered):
    def surface_source_data(self, Data):
        if not Data.get("BakedNormal"):
            return Data
        source_data = dict(Data)
        source_data["GlobalNormal"] = Data["BakedNormal"]
        return source_data

    def configure_multilayer_surface(self, Mat, Data, context):
        range_mode = configure_vehicle_destruction_coat(Data, context)
        return range_mode

    def surface_structure(self, Data, layer_count):
        return selected_layer_indices(Data, layer_count)

    def apply_surface_values(self, Mat, Data, slots, layer_count):
        if "vehicle_coat_controls" in slots:
            _write_vehicle_coat_controls(
                Mat.node_tree.nodes[slots["vehicle_coat_controls"]], Data
            )
        else:
            apply_principled_multilayer_coat_values(
                Mat, Data, slots, **_PRINCIPLED_COAT_OPTIONS
            )


used_params = [
    "GlobalNormal",
    "MultilayerMask",
    "MultilayerSetup",
    "GlobalNormalIntensity",
    "GlobalNormalUVScale",
    "GlobalNormalUVBias",
    "UseOldVertexFormat",
    "UVGenScaleOffset",
    "MaskAtlas",
    "MaskTiles",
    "Layers",
    "LayersStartIndex",
    "SurfaceTexAspectRatio",
    "MaskToTileScale",
    "MaskTileSize",
    "MaskAtlasDims",
    "MaskBaseResolution",
    "SetupLayerMask",
    "Opacity",
    "CoatTintFwd",
    "CoatTintSide",
    "CoatTintFresnelBias",
    "CoatFresnelBias",
    "CoatLayerMin",
    "CoatLayerMax",
    "BakedNormal",
]


_CACHE_PARAMETERS = frozenset(used_params)


def material_cache_identity(raw_material):
    return filtered_material_data_identity(raw_material, _CACHE_PARAMETERS)
