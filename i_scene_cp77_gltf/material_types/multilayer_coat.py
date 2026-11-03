import math

import bpy

from ..bartmoss.scalar import clamp01, lerp_three
from ..blender import shader_nodes
from ..blender.shader_nodes import set_default_if_changed
from ..blender.transactions import new_tracked_datablock
from ..materials.blender.nodes import CreateShaderNodeValue, create_node
from .graph import combine_bundle_node, separate_bundle_node
from .mat_common import find_input, param_color, param_float
from .normal_math import directx_tangent_to_normal_map


def f0_to_ior(f0):
    f0 = max(0.0, min(0.99, float(f0)))
    root = math.sqrt(f0)
    return (1.0 + root) / max(1.0 - root, 1.0e-6)


def selected_layer_indices(data, layer_count):
    if layer_count <= 0:
        return (), "empty"

    raw_min = param_float(data, "CoatLayerMin", -1.0)
    raw_max = param_float(data, "CoatLayerMax", -1.0)
    if raw_min < 0.0 and raw_max < 0.0:
        return tuple(range(layer_count)), "negative-bounds-all-layers"

    lower = 0 if raw_min < 0.0 else min(max(int(raw_min), 0), layer_count - 1)
    upper = (
        layer_count - 1 if raw_max < 0.0 else min(max(int(raw_max), 0), layer_count - 1)
    )
    if upper < lower:
        return (), "empty-range"
    return tuple(range(lower, upper + 1)), "indexed-range"


def build_selected_layer_coverage(
    tree,
    selected,
    layer_count,
    mask_sockets,
    location=(-620, -980),
):
    selected_set = set(selected)
    if not selected:
        return CreateShaderNodeValue(
            tree, 0.0, *location, "Clear Coat Layer Coverage"
        ).outputs["Value"]
    if len(selected) == layer_count:
        return CreateShaderNodeValue(
            tree, 1.0, *location, "Clear Coat Layer Coverage"
        ).outputs["Value"]

    remaining = CreateShaderNodeValue(
        tree, 1.0, *location, "Clear Coat Remaining Coverage"
    ).outputs["Value"]
    coverage = CreateShaderNodeValue(
        tree,
        0.0,
        location[0],
        location[1] - 80,
        "Clear Coat Selected Coverage",
    ).outputs["Value"]
    x = location[0] + 180

    last_needed = min(selected_set)
    for index in range(layer_count - 1, max(0, last_needed - 1), -1):
        mask_socket = mask_sockets.get(index)
        if mask_socket is None:
            continue
        mask = shader_nodes.clamp(
            tree.nodes,
            tree.links,
            mask_socket,
            label=f"Layer {index + 1} Mask",
            location=(x, location[1] - index * 55),
        )

        if index in selected_set:
            visible = shader_nodes.math(
                tree.nodes,
                tree.links,
                "MULTIPLY",
                label=f"Layer {index + 1} Visible",
                location=(x + 320, location[1] - index * 55),
                hide=True,
            ).node
            tree.links.new(mask, visible.inputs["Value"])
            tree.links.new(
                remaining,
                shader_nodes.socket_by_identifier(visible.inputs, "Value_001"),
            )
            add = shader_nodes.math(
                tree.nodes,
                tree.links,
                "ADD",
                label=f"Add Coat Layer {index + 1}",
                location=(x + 500, location[1] - index * 55),
                hide=True,
            ).node
            tree.links.new(coverage, add.inputs["Value"])
            tree.links.new(
                visible.outputs["Value"],
                shader_nodes.socket_by_identifier(add.inputs, "Value_001"),
            )
            coverage = add.outputs["Value"]

        if index == last_needed:
            break

        invert = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            label=f"Layer {index + 1} Reveal Below",
            location=(x + 320, location[1] - index * 55 - 28),
            hide=True,
        ).node
        invert.inputs["Value"].default_value = 1.0
        tree.links.new(
            mask, shader_nodes.socket_by_identifier(invert.inputs, "Value_001")
        )
        next_remaining = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label=f"Remaining Below Layer {index + 1}",
            location=(x + 500, location[1] - index * 55 - 28),
            hide=True,
        ).node
        tree.links.new(remaining, next_remaining.inputs["Value"])
        tree.links.new(
            invert.outputs["Value"],
            shader_nodes.socket_by_identifier(next_remaining.inputs, "Value_001"),
        )
        remaining = next_remaining.outputs["Value"]

    if 0 in selected_set:
        add_base = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            label="Add Base Coat Layer",
            location=(x + 680, location[1]),
            hide=True,
        ).node
        tree.links.new(coverage, add_base.inputs["Value"])
        tree.links.new(
            remaining, shader_nodes.socket_by_identifier(add_base.inputs, "Value_001")
        )
        coverage = add_base.outputs["Value"]

    return shader_nodes.clamp(
        tree.nodes,
        tree.links,
        coverage,
        label="Clear Coat Coverage",
        location=(x + 850, location[1]),
    )


def build_coat_normal(tree, global_normal, strength, location=(120, -560)):
    if not global_normal:
        return None
    source = global_normal.get("decoded")
    if source is None:
        source = global_normal.get("normal")
    if source is None:
        return None
    return directx_tangent_to_normal_map(
        tree,
        source,
        strength=strength,
        location=location,
        label="Clear Coat Normal",
    )


def _build_coat_tint(tree, coat_normal, location=(-520, -560)):
    """The view-angle tint stage and its Fresnel power and tint mix nodes"""
    layer_weight = create_node(tree.nodes, "ShaderNodeLayerWeight", location)
    layer_weight.label = "Clear Coat View Angle"
    normal_input = find_input(layer_weight, "Normal")
    if normal_input is not None and coat_normal is not None:
        tree.links.new(coat_normal, normal_input)

    one_minus = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        label="Clear Coat 1-NdotV",
        location=(location[0] + 180, location[1]),
        hide=True,
    ).node
    one_minus.inputs["Value"].default_value = 1.0
    tree.links.new(
        layer_weight.outputs["Facing"],
        shader_nodes.socket_by_identifier(one_minus.inputs, "Value_001"),
    )

    power = shader_nodes.math(
        tree.nodes,
        tree.links,
        "POWER",
        label="Clear Coat Tint Fresnel",
        location=(location[0] + 350, location[1]),
        hide=True,
    ).node
    tree.links.new(one_minus.outputs["Value"], power.inputs["Value"])

    mix = create_node(
        tree.nodes, "ShaderNodeMix", (location[0] + 530, location[1]), blend_type="MIX"
    )
    mix.label = "Clear Coat Refraction Tint"
    mix.data_type = "RGBA"
    mix.clamp_factor = True
    tree.links.new(
        power.outputs["Value"],
        shader_nodes.socket_by_identifier(mix.inputs, "Factor_Float"),
    )
    return power, mix


_CLEAR_COAT_GRAPH_VERSION = 5
_CLEAR_COAT_CONTROLS = (
    ("FLOAT", "Weight"),
    ("FLOAT", "Roughness"),
    ("FLOAT", "IOR"),
    ("FLOAT", "Normal Strength"),
    ("RGBA", "Tint Fwd"),
    ("RGBA", "Tint Side"),
    ("FLOAT", "Tint Exponent"),
    ("FLOAT", "Opacity"),
)
COAT_SURFACE_ITEMS = (
    ("FLOAT", "Weight"),
    ("FLOAT", "Roughness"),
    ("FLOAT", "IOR"),
    ("VECTOR", "Normal"),
    ("RGBA", "Tint"),
)


def coat_layer_mask_items(layer_count):
    """The mask interface items of layers 2..layer_count"""
    return tuple(
        ("FLOAT", f"Layer {index + 1} Mask") for index in range(1, layer_count)
    )


def coat_layer_range_key(layer_count, selected):
    """The group-name key of the selected layer range"""
    if not selected:
        return "none"
    if len(selected) == layer_count:
        return "all"
    return f"{selected[0] + 1}-{selected[-1] + 1}"


def _clear_coat_group_name(layer_count, selected):
    range_key = coat_layer_range_key(layer_count, selected)
    return f"CP77 Multilayer Clear Coat L{layer_count} R{range_key} {_CLEAR_COAT_GRAPH_VERSION}.0"


def _multilayer_clear_coat_group(layer_count, selected):
    name = _clear_coat_group_name(layer_count, selected)
    existing = bpy.data.node_groups.get(name)
    if existing is not None:
        return existing

    group = new_tracked_datablock("node_groups", name, "ShaderNodeTree")
    needs_masks = bool(selected) and len(selected) != layer_count and layer_count > 1
    if needs_masks:
        group.interface.new_socket(
            name="Layer Masks", socket_type="NodeSocketBundle", in_out="INPUT"
        )
    normal_socket = group.interface.new_socket(
        name="Global Normal", socket_type="NodeSocketVector", in_out="INPUT"
    )
    normal_socket.default_value = (0.0, 0.0, 1.0)
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
            (-1160, -500),
            name="CP77 Clear Coat Layer Masks Unpack",
            label="Layer Masks",
        )
        group.links.new(
            group_input.outputs["Layer Masks"], mask_unpack.inputs["Bundle"]
        )
        for index in range(1, layer_count):
            mask_sockets[index] = mask_unpack.outputs[f"Layer {index + 1} Mask"]

    controls = separate_bundle_node(
        group,
        _CLEAR_COAT_CONTROLS,
        (-1160, 300),
        name="CP77 Clear Coat Controls Unpack",
        label="Clear Coat Controls",
    )
    group.links.new(group_input.outputs["Controls"], controls.inputs["Bundle"])

    coverage = build_selected_layer_coverage(
        group, selected, layer_count, mask_sockets, (-940, -520)
    )

    coat_normal = directx_tangent_to_normal_map(
        group,
        group_input.outputs["Global Normal"],
        strength=controls.outputs["Normal Strength"],
        location=(-900, 140),
        label="Clear Coat Normal",
    )

    layer_weight = create_node(group.nodes, "ShaderNodeLayerWeight", (-340, -100))
    layer_weight.label = "Clear Coat View Angle"
    normal_input = find_input(layer_weight, "Normal")
    if normal_input is not None:
        group.links.new(coat_normal, normal_input)
    one_minus = shader_nodes.math(
        group.nodes,
        group.links,
        "SUBTRACT",
        label="Clear Coat 1-NdotV",
        location=(-150, -100),
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
        label="Clear Coat Tint Fresnel",
        location=(30, -100),
        hide=True,
    ).node
    group.links.new(one_minus.outputs["Value"], power.inputs["Value"])
    group.links.new(
        controls.outputs["Tint Exponent"],
        shader_nodes.socket_by_identifier(power.inputs, "Value_001"),
    )

    tint_mix = create_node(group.nodes, "ShaderNodeMix", (220, -100), blend_type="MIX")
    tint_mix.label = "Clear Coat Refraction Tint"
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
        label="Clear Coat Tint Coverage",
        location=(220, -300),
        hide=True,
    ).node
    group.links.new(coverage, tint_factor.inputs["Value"])
    group.links.new(
        controls.outputs["Opacity"],
        shader_nodes.socket_by_identifier(tint_factor.inputs, "Value_001"),
    )
    final_tint = create_node(
        group.nodes, "ShaderNodeMix", (450, -100), blend_type="MIX"
    )
    final_tint.label = "Clear Coat Multiplicative Tint"
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
        name="CP77 Clear Coat Surface Pack",
        label="Coat Surface",
    )
    group.links.new(controls.outputs["Weight"], coat_surface.inputs["Weight"])
    group.links.new(controls.outputs["Roughness"], coat_surface.inputs["Roughness"])
    group.links.new(controls.outputs["IOR"], coat_surface.inputs["IOR"])
    group.links.new(coat_normal, coat_surface.inputs["Normal"])
    group.links.new(
        shader_nodes.socket_by_identifier(final_tint.outputs, "Result_Color"),
        coat_surface.inputs["Tint"],
    )
    group.links.new(coat_surface.outputs["Bundle"], group_output.inputs["Coat Surface"])
    return group


def _principled_coat_values(
    data, *, normal_strength=None, roughness=None, reflection_power=None
):
    """The clear coat's per-material values"""
    opacity = clamp01(param_float(data, "Opacity", 1.0))
    reflection = (
        max(0.0, param_float(data, "CoatReflectionPower", 1.0))
        if reflection_power is None
        else max(0.0, float(reflection_power))
    )
    roughness_value = (
        clamp01(param_float(data, "CoatRoughnessBase", 0.05))
        if roughness is None
        else clamp01(roughness)
    )
    source_f0 = lerp_three(
        (0.25, 0.04, 0.0),
        param_float(data, "CoatFresnelBias", 1.0),
    )
    tint_fwd = param_color(data, "CoatTintFwd", (1.0, 1.0, 1.0, 1.0))
    return {
        "opacity": opacity,
        "reflection": reflection,
        "weight": reflection if opacity >= 0.001 else 0.0,
        "roughness": roughness_value,
        "ior": max(1.0, f0_to_ior(source_f0)),
        "normal_strength": (
            max(0.0, param_float(data, "CoatNormalStrength", 1.0))
            if normal_strength is None
            else max(0.0, float(normal_strength))
        ),
        "tint_fwd": tint_fwd,
        "tint_side": param_color(data, "CoatTintSide", tint_fwd),
        "tint_exponent": lerp_three(
            (0.25, 1.0, 6.0), param_float(data, "CoatTintFresnelBias", 1.0)
        ),
    }


def _write_principled_coat(principled, power, mix, tint_factor, values):
    for socket_name, key in (
        ("Coat Weight", "weight"),
        ("Coat Roughness", "roughness"),
        ("Coat IOR", "ior"),
    ):
        set_default_if_changed(find_input(principled, socket_name), values[key])
    set_default_if_changed(
        shader_nodes.socket_by_identifier(power.inputs, "Value_001"),
        values["tint_exponent"],
    )
    set_default_if_changed(
        shader_nodes.socket_by_identifier(mix.inputs, "A_Color"), values["tint_fwd"]
    )
    set_default_if_changed(
        shader_nodes.socket_by_identifier(mix.inputs, "B_Color"), values["tint_side"]
    )
    set_default_if_changed(
        shader_nodes.socket_by_identifier(tint_factor.inputs, "Value_001"),
        values["opacity"],
    )


def _write_clear_coat_controls(controls_pack, values):
    inputs = controls_pack.inputs
    for socket_name, key in (
        ("Weight", "weight"),
        ("Roughness", "roughness"),
        ("IOR", "ior"),
        ("Normal Strength", "normal_strength"),
        ("Tint Fwd", "tint_fwd"),
        ("Tint Side", "tint_side"),
        ("Tint Exponent", "tint_exponent"),
        ("Opacity", "opacity"),
    ):
        set_default_if_changed(inputs[socket_name], values[key])


def apply_principled_multilayer_coat_values(
    Mat,
    data,
    slots,
    *,
    normal_strength=None,
    roughness=None,
    reflection_power=None,
):
    """Write a clear coat's values into a copy of a material with the same coat"""
    values = _principled_coat_values(
        data,
        normal_strength=normal_strength,
        roughness=roughness,
        reflection_power=reflection_power,
    )
    nodes = Mat.node_tree.nodes
    if "clear_coat_controls" in slots:
        _write_clear_coat_controls(nodes[slots["clear_coat_controls"]], values)
    else:
        _write_principled_coat(
            nodes[slots["clear_coat_principled"]],
            nodes[slots["clear_coat_tint_power"]],
            nodes[slots["clear_coat_tint_mix"]],
            nodes[slots["clear_coat_tint_factor"]],
            values,
        )


def configure_principled_multilayer_coat(
    data,
    context,
    *,
    normal_strength=None,
    roughness=None,
    reflection_power=None,
):
    tree = context["tree"]
    principled = context["principled"]
    layer_count = int(context["layer_count"])
    slots = context.get("slots")
    slots = {} if slots is None else slots
    values = _principled_coat_values(
        data,
        normal_strength=normal_strength,
        roughness=roughness,
        reflection_power=reflection_power,
    )

    global_normal = context.get("global_normal")
    normal_source = None
    if global_normal:
        normal_source = global_normal.get("decoded")
        if normal_source is None:
            normal_source = global_normal.get("normal")

    selected, range_mode = selected_layer_indices(data, layer_count)
    if normal_source is None:
        mask_sockets = {}
        for index in range(1, layer_count):
            layer = (
                context["layer_nodes"][index]
                if index < len(context["layer_nodes"])
                else None
            )
            mask = layer.outputs.get("Layer Mask") if layer is not None else None
            if mask is not None:
                mask_sockets[index] = mask
        coverage = build_selected_layer_coverage(
            tree, selected, layer_count, mask_sockets
        )
        power, source_mix = _build_coat_tint(tree, None)
        tint_factor = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            label="Clear Coat Tint Coverage",
            location=(520, -390),
            hide=True,
        ).node
        tree.links.new(coverage, tint_factor.inputs["Value"])
        tint_mix = create_node(
            tree.nodes, "ShaderNodeMix", (700, -390), blend_type="MIX"
        )
        tint_mix.label = "Clear Coat Final Multiplicative Tint"
        tint_mix.data_type = "RGBA"
        tint_mix.clamp_factor = True
        shader_nodes.socket_by_identifier(tint_mix.inputs, "A_Color").default_value = (
            1.0,
            1.0,
            1.0,
            1.0,
        )
        tree.links.new(
            shader_nodes.socket_by_identifier(source_mix.outputs, "Result_Color"),
            shader_nodes.socket_by_identifier(tint_mix.inputs, "B_Color"),
        )
        tree.links.new(
            tint_factor.outputs["Value"],
            shader_nodes.socket_by_identifier(tint_mix.inputs, "Factor_Float"),
        )
        tint_input = find_input(principled, "Coat Tint")
        if tint_input is not None:
            tree.links.new(
                shader_nodes.socket_by_identifier(tint_mix.outputs, "Result_Color"),
                tint_input,
            )
        _write_principled_coat(principled, power, source_mix, tint_factor, values)
        slots.update(
            clear_coat_principled=principled.name,
            clear_coat_tint_power=power.name,
            clear_coat_tint_mix=source_mix.name,
            clear_coat_tint_factor=tint_factor.name,
        )
    else:
        needs_masks = (
            bool(selected) and len(selected) != layer_count and layer_count > 1
        )
        mask_pack = None
        if needs_masks:
            mask_items = coat_layer_mask_items(layer_count)
            mask_pack = combine_bundle_node(
                tree,
                mask_items,
                (-420, -720),
                name="CP77 Clear Coat Layer Masks Pack",
                label="Clear Coat Layer Masks",
            )
            mask_pack["cp77_multilayer_clear_coat_role"] = "layer_masks"
            for index in range(1, layer_count):
                layer = (
                    context["layer_nodes"][index]
                    if index < len(context["layer_nodes"])
                    else None
                )
                mask_socket = (
                    layer.outputs.get("Layer Mask") if layer is not None else None
                )
                if mask_socket is not None:
                    tree.links.new(
                        mask_socket, mask_pack.inputs[f"Layer {index + 1} Mask"]
                    )

        controls_pack = combine_bundle_node(
            tree,
            _CLEAR_COAT_CONTROLS,
            (-420, -420),
            name="CP77 Clear Coat Controls Pack",
            label="Clear Coat Controls",
        )
        controls_pack["cp77_multilayer_clear_coat_role"] = "coat_controls"
        _write_clear_coat_controls(controls_pack, values)
        slots["clear_coat_controls"] = controls_pack.name

        coat_node = create_node(tree.nodes, "ShaderNodeGroup", (-80, -520))
        coat_node.name = "CP77 Multilayer Clear Coat"
        coat_node.label = "Multilayer Clear Coat"
        coat_node["cp77_multilayer_clear_coat_role"] = "coat_stage"
        coat_node.node_tree = _multilayer_clear_coat_group(layer_count, selected)
        if mask_pack is not None:
            tree.links.new(mask_pack.outputs["Bundle"], coat_node.inputs["Layer Masks"])
        tree.links.new(normal_source, coat_node.inputs["Global Normal"])
        tree.links.new(controls_pack.outputs["Bundle"], coat_node.inputs["Controls"])

        coat_surface = separate_bundle_node(
            tree,
            COAT_SURFACE_ITEMS,
            (220, -420),
            name="CP77 Clear Coat Surface Unpack",
            label="Clear Coat Surface",
        )
        coat_surface["cp77_multilayer_clear_coat_role"] = "coat_surface"
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
