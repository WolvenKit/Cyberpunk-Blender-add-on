from __future__ import annotations

import math
import os

import bpy

from ..assetio.values import field_float
from ..entity.domain.light_representation import (
    SHADOWLESS_REPRESENTATIONS,
    linear_color,
    numeric_energy,
    softened_cosine_spot_blend,
)
from ..entity.domain.light_zones import (
    uses_light_zones,
    zone_color_property,
    zone_level_property,
    zone_light_type_property,
    zone_starts_on_property,
    zone_strength_property,
)
from ..entity.domain.lights import (
    LIGHT_ATTENUATION_CLAMP_DEFAULT,
    clamp_blender_exposure,
    effective_light_radius,
    flicker_multipliers,
    light_contributions,
    local_shadows_enabled,
)
from . import shader_nodes
from .keyframes import (
    assign_action_with_slot,
    bulk_set_keyframes,
    clear_fcurve_points,
    ensure_fcurve,
    get_action_fcurves,
)
from .shader_nodes import outputs_detached
from .transactions import track_created_datablock

# A light's energy at full brightness, which its preview scales.
BASE_ENERGY_KEY = "cp77_preview_base_energy"
# Set on an imported entity whose vehicle lights or light zones the vehicle switches drive.
PREVIEW_AVAILABLE_KEY = "cp77_vehicle_light_preview_available"
# The easing values Blender gives a key it inserts; keys added in bulk start without them.
_KEY_EASING = (("back", 1.70158), ("amplitude", 0.8), ("period", 4.1))


def capture_base_energy(obj):
    """Keep the light's current energy as its base energy"""
    obj[BASE_ENERGY_KEY] = float(obj.data.energy)


def configure_exposure(light, ev):
    if hasattr(light, "exposure"):
        light.exposure = clamp_blender_exposure(ev)


def configure_contributions(light, data, *, static_node=False):
    for name, factor in light_contributions(data, static_node=static_node).items():
        setattr(light, f"{name}_factor", factor)


def configure_shadow(light, data, representation):
    """Let the light cast shadows when its settings enable local shadows and its representation casts any"""
    if hasattr(light, "use_shadow"):
        light.use_shadow = (
            local_shadows_enabled(data)
            and representation not in SHADOWLESS_REPRESENTATIONS
        )


def configure_static_light(light, data, representation, sample_count):
    """Set one of the Blender lights of a sector light from its node data"""
    light.energy = numeric_energy(data) / max(1, int(sample_count))
    light.color = linear_color(data)
    configure_exposure(light, field_float(data, "EV", 0.0))
    if hasattr(light, "normalize"):
        light.normalize = True
    configure_contributions(light, data, static_node=True)
    if hasattr(light, "use_temperature"):
        light.use_temperature = False

    radius = effective_light_radius(
        field_float(data, "radius", 5.0),
        data.get("sceneDiffuse", True),
        data.get("sceneSpecular", not bool(data.get("noSpecular", 0))),
    )
    if hasattr(light, "use_custom_distance"):
        light.use_custom_distance = True
    if hasattr(light, "cutoff_distance"):
        light.cutoff_distance = radius

    source_radius = max(field_float(data, "sourceRadius", 0.0), 0.0)
    finite_source = representation in {
        "SPHERICAL_POINT",
        "CAPSULE_POINT_CHAIN",
        "CAPSULE_SPOT_CHAIN",
        "CAPSULE_WIDE_SPOT_POINT_CHAIN",
    }
    if hasattr(light, "shadow_soft_size"):
        light.shadow_soft_size = source_radius if finite_source else 0.0

    if light.type == "SPOT":
        outer = max(field_float(data, "outerAngle", 90.0), 0.001)
        inner = max(0.0, min(field_float(data, "innerAngle", 0.0), outer))
        light.spot_size = math.radians(min(outer, 179.999))
        light.spot_blend = softened_cosine_spot_blend(
            inner,
            outer,
            field_float(data, "softness", 2.0),
        )

    configure_shadow(light, data, representation)
    return radius, source_radius


def create_proxy_samples(
    primary, representation, offsets, radius, resolved_ies="", resolved_projection=""
):
    """The samples of the capsule light primary after its first"""
    samples = []
    for index, offset in enumerate(offsets[1:], start=1):
        light = track_created_datablock("lights", primary.data.copy())
        light.name = f"{primary.data.name}__proxy_{index:02d}"
        obj = track_created_datablock(
            "objects", bpy.data.objects.new(f"{primary.name}__proxy_{index:02d}", light)
        )
        obj.parent = primary
        obj.location = (float(offset - offsets[0]), 0.0, 0.0)
        obj["cp77_light_proxy"] = True
        obj["cp77_proxy_representation"] = representation
        obj["cp77_effective_radius"] = radius
        capture_base_energy(obj)
        if resolved_ies:
            obj["cp77_resolved_ies_profile"] = resolved_ies
        if resolved_projection:
            obj["cp77_resolved_projection_texture"] = resolved_projection
        samples.append(obj)
    return tuple(samples)


def energy_fcurves(light):
    """The F-curves that animate a Blender light's energy (a flicker)"""
    animation_data = light.animation_data
    fcurves = (
        get_action_fcurves(animation_data.action, light)
        if animation_data is not None
        else None
    )
    return (
        tuple(fcurve for fcurve in fcurves if fcurve.data_path == "energy")
        if fcurves is not None
        else ()
    )


def light_zone_objects(collection):
    """The mesh objects under collection that have a light-zone material"""
    return [
        obj
        for obj in collection.all_objects
        if obj.type == "MESH"
        and any(
            slot.material is not None
            and uses_light_zones(slot.material.get("MaterialTemplate"))
            for slot in obj.material_slots
        )
    ]


def write_zone_light(objects, light):
    """Give each object the light zone values its lights set"""
    color_name, level_name = (
        zone_color_property(light.zone),
        zone_level_property(light.zone),
    )
    strength_name, starts_on_name = (
        zone_strength_property(light.zone),
        zone_starts_on_property(light.zone),
    )
    types_name = zone_light_type_property(light.zone)
    for obj in objects:
        obj[color_name] = list(light.color)
        obj[strength_name] = light.strength
        obj[level_name] = light.level
        if light.device:
            obj[starts_on_name] = light.starts_on
            obj.pop(types_name, None)
        else:
            obj[types_name] = int(obj.get(types_name, 0)) | light.light_types
            obj.pop(starts_on_name, None)
        obj.update_tag()


def set_zone_on(objects, zone, on, level=None):
    """Switch a light zone on or off for each object that drives it"""
    strength_name, level_name = zone_strength_property(zone), zone_level_property(zone)
    for obj in objects:
        if strength_name in obj:
            obj[level_name] = (
                (obj[strength_name] if level is None else level) if on else 0.0
            )
            obj.update_tag()


def _emission_node(node_tree):
    node = next((item for item in node_tree.nodes if item.type == "EMISSION"), None)
    if node is None:
        node = node_tree.nodes.new("ShaderNodeEmission")
        node.label = "CP77 Light Emission"
    return node


def _light_output_node(node_tree):
    node = next((item for item in node_tree.nodes if item.type == "OUTPUT_LIGHT"), None)
    if node is None:
        node = node_tree.nodes.new("ShaderNodeOutputLight")
    return node


def _find_labelled(node_tree, label):
    return next((item for item in node_tree.nodes if item.label == label), None)


def _labelled_node(node_tree, node_type, label):
    """The node labelled label, made as a node_type node when the tree has none"""
    node = _find_labelled(node_tree, label)
    if node is None:
        node = node_tree.nodes.new(node_type)
        node.label = label
    return node


def _clear_inputs(node_tree, *sockets):
    for socket in sockets:
        for link in tuple(socket.links):
            node_tree.links.remove(link)


def _math_node(node_tree, label, operation, first, second):
    """The output of the Math node labelled label, set to operation with new inputs"""
    node = _find_labelled(node_tree, label)
    if node is None:
        node = shader_nodes.math(
            node_tree.nodes, node_tree.links, operation, label=label
        ).node
    node.operation = operation
    for operand, identifier in zip((first, second), ("Value", "Value_001")):
        target = shader_nodes.socket_by_identifier(node.inputs, identifier)
        _clear_inputs(node_tree, target)
        shader_nodes.assign_socket(node_tree.links, operand, target)
    return node.outputs["Value"]


def _value_node(node_tree, label, value):
    node = _labelled_node(node_tree, "ShaderNodeValue", label)
    node.outputs["Value"].default_value = float(value)
    return node.outputs["Value"]


def _projection_factor(node_tree, projection_path):
    if not projection_path or not os.path.isfile(projection_path):
        return None
    before = len(bpy.data.images)
    try:
        image = bpy.data.images.load(projection_path, check_existing=True)
    except (RuntimeError, OSError, ValueError):
        return None
    if len(bpy.data.images) > before:
        track_created_datablock("images", image)
    image.colorspace_settings.name = "Non-Color"

    coordinates = _labelled_node(
        node_tree, "ShaderNodeTexCoord", "CP77 Projection Coordinates"
    )
    mapping = _labelled_node(node_tree, "ShaderNodeMapping", "CP77 Projection Mapping")
    if "Location" in mapping.inputs:
        mapping.inputs["Location"].default_value = (0.5, 0.5, 0.0)
    if "Scale" in mapping.inputs:
        mapping.inputs["Scale"].default_value = (0.5, 0.5, 1.0)
    texture = _labelled_node(node_tree, "ShaderNodeTexImage", "CP77 Projection Texture")
    texture.image = image
    texture.extension = "CLIP"
    texture.projection = "FLAT"
    grayscale = _labelled_node(
        node_tree, "ShaderNodeRGBToBW", "CP77 Projection Strength"
    )

    vector_input = mapping.inputs["Vector"]
    image_vector = texture.inputs["Vector"]
    grayscale_color = grayscale.inputs["Color"]
    _clear_inputs(node_tree, vector_input, image_vector, grayscale_color)
    node_tree.links.new(coordinates.outputs["Normal"], vector_input)
    node_tree.links.new(mapping.outputs["Vector"], image_vector)
    node_tree.links.new(texture.outputs["Color"], grayscale_color)
    return grayscale.outputs["Val"]


def _multiply_factors(node_tree, factors):
    if not factors:
        return None
    result = factors[0]
    for index, factor in enumerate(factors[1:], start=1):
        result = _math_node(
            node_tree, f"CP77 Light Distribution {index}", "MULTIPLY", result, factor
        )
    return result


def _ray_distance_socket(node_tree):
    return _labelled_node(
        node_tree, "ShaderNodeLightPath", "CP77 Source Ray Distance"
    ).outputs["Ray Length"]


def _attenuation_factor(
    node_tree, attenuation, radius, clamp_attenuation, attenuation_clamp
):
    distance = _ray_distance_socket(node_tree)
    radius = _value_node(node_tree, "CP77 Attenuation Radius", max(float(radius), 0.01))

    if str(attenuation) == "LA_Linear":
        normalized = _math_node(
            node_tree, "CP77 Linear Normalized Distance", "DIVIDE", distance, radius
        )
        normalized.node.use_clamp = True
        result = _math_node(
            node_tree, "CP77 Linear Attenuation", "SUBTRACT", 1.0, normalized
        )
    else:
        distance_squared = _math_node(
            node_tree, "CP77 Distance Squared", "MULTIPLY", distance, distance
        )
        radius_squared = _math_node(
            node_tree, "CP77 Radius Squared", "MULTIPLY", radius, radius
        )
        factor = _math_node(
            node_tree, "CP77 Radius Factor", "DIVIDE", distance_squared, radius_squared
        )
        factor_squared = _math_node(
            node_tree, "CP77 Radius Factor Squared", "MULTIPLY", factor, factor
        )
        one_minus = _math_node(
            node_tree, "CP77 Smooth Radius", "SUBTRACT", 1.0, factor_squared
        )
        smooth = _math_node(
            node_tree, "CP77 Smooth Radius Max", "MAXIMUM", one_minus, 0.0
        )
        numerator = _math_node(
            node_tree, "CP77 Smooth Radius Squared", "MULTIPLY", smooth, smooth
        )
        denominator = _math_node(
            node_tree, "CP77 Distance Denominator", "MAXIMUM", distance_squared, 1.0e-4
        )
        result = _math_node(
            node_tree,
            "CP77 Inverse Square Attenuation",
            "DIVIDE",
            numerator,
            denominator,
        )

    if clamp_attenuation:
        result = _math_node(
            node_tree, "CP77 Attenuation Clamp", "MINIMUM", result, None
        )
        limit = _value_node(
            node_tree,
            "CP77 Attenuation Clamp Limit",
            max(1.0, min(float(attenuation_clamp), 128.0)),
        )
        node_tree.links.new(
            limit, shader_nodes.socket_by_identifier(result.node.inputs, "Value_001")
        )

    subtracted = _math_node(
        node_tree, "CP77 Attenuation Threshold Subtract", "SUBTRACT", result, 0.0002
    )
    low = _math_node(
        node_tree, "CP77 Attenuation Threshold Max", "MAXIMUM", subtracted, 0.0
    )
    scaled = _math_node(
        node_tree, "CP77 Attenuation Threshold Scale", "MULTIPLY", low, 2.0
    )
    test = _math_node(
        node_tree, "CP77 Attenuation Threshold Test", "LESS_THAN", result, 0.0004
    )
    low_weight = _math_node(
        node_tree, "CP77 Attenuation Low Weight", "MULTIPLY", scaled, test
    )
    high_condition = _math_node(
        node_tree, "CP77 Attenuation High Condition", "SUBTRACT", 1.0, test
    )
    high_weight = _math_node(
        node_tree, "CP77 Attenuation High Weight", "MULTIPLY", result, high_condition
    )
    return _math_node(
        node_tree, "CP77 Attenuation Threshold Result", "ADD", low_weight, high_weight
    )


def _native_quadratic_compensation(node_tree, attenuation):
    falloff = _labelled_node(
        node_tree, "ShaderNodeLightFalloff", "CP77 Native Falloff Compensation"
    )
    _clear_inputs(node_tree, falloff.inputs["Strength"])
    node_tree.links.new(attenuation, falloff.inputs["Strength"])
    falloff.inputs["Smooth"].default_value = 0.0
    return falloff.outputs["Constant"]


def update_cycles_attenuation_radius(light, radius):
    node_tree = getattr(light, "node_tree", None)
    if node_tree is None:
        return False
    node = _find_labelled(node_tree, "CP77 Attenuation Radius")
    if node is None:
        return False
    node.outputs["Value"].default_value = max(float(radius), 0.01)
    return True


def configure_cycles_distribution(
    light,
    attenuation,
    radius,
    clamp_attenuation=False,
    attenuation_clamp=LIGHT_ATTENUATION_CLAMP_DEFAULT,
    ies_path="",
    projection_path="",
):
    use_ies = (
        bool(ies_path)
        and os.path.isfile(ies_path)
        and str(ies_path).lower().endswith(".ies")
    )
    use_projection = bool(projection_path) and os.path.isfile(projection_path)

    node_tree = getattr(light, "node_tree", None)
    if node_tree is None and hasattr(light, "use_nodes"):
        light.use_nodes = True
        node_tree = getattr(light, "node_tree", None)
    if node_tree is None:
        return

    emission = _emission_node(node_tree)
    output = _light_output_node(node_tree)
    surface = output.inputs["Surface"]
    if not any(
        link.from_node is emission and link.to_socket == surface
        for link in node_tree.links
    ):
        _clear_inputs(node_tree, surface)
        node_tree.links.new(emission.outputs["Emission"], surface)

    # The strength graph is built with the emission unlinked from the output, so each edit updates only this light.
    with outputs_detached(node_tree):
        factors = [
            _native_quadratic_compensation(
                node_tree,
                _attenuation_factor(
                    node_tree, attenuation, radius, clamp_attenuation, attenuation_clamp
                ),
            )
        ]
        if use_ies:
            ies = _labelled_node(node_tree, "ShaderNodeTexIES", "CP77 IES Profile")
            ies.mode = "EXTERNAL"
            ies.filepath = ies_path
            ies.inputs["Strength"].default_value = 1.0
            factors.append(ies.outputs["Factor"])
        if use_projection:
            projection = _projection_factor(node_tree, projection_path)
            if projection is not None:
                factors.append(projection)
        combined = _multiply_factors(node_tree, factors)
        strength = emission.inputs["Strength"]
        _clear_inputs(node_tree, strength)
        if combined is not None:
            node_tree.links.new(combined, strength)


def animate_flicker(
    light, flicker, seed_value, period_count=16, base_energy=None, active=True
):
    if not isinstance(flicker, dict):
        return False
    strength = max(0.0, float(flicker.get("flickerStrength", 0.0) or 0.0))
    period = max(0.0, float(flicker.get("flickerPeriod", 0.0) or 0.0))
    if strength <= 0.0 or period <= 0.0:
        return False

    targets = flicker_multipliers(strength, period_count, seed_value)
    if not targets:
        return False
    scene = bpy.context.scene
    fps = float(scene.render.fps) / max(float(scene.render.fps_base), 1e-8)
    base_energy = float(light.energy if base_energy is None else base_energy)
    # A later key on the same frame replaces the earlier one.
    keys = {
        1 + max(0, round(index * period * fps)): base_energy * multiplier
        for index, multiplier in enumerate(targets)
    }
    animation_data = light.animation_data
    action = animation_data.action if animation_data is not None else None
    if action is None:
        action = track_created_datablock(
            "actions", bpy.data.actions.new(f"{light.name}Action")
        )
        assign_action_with_slot(light, action)
    fcurve = ensure_fcurve(action, light, "energy", 0)
    clear_fcurve_points(fcurve)
    frames = sorted(keys)
    count = bulk_set_keyframes(
        fcurve, frames, [keys[frame] for frame in frames], "LINEAR"
    )
    for name, value in _KEY_EASING:
        fcurve.keyframe_points.foreach_set(name, [value] * count)
    fcurve.update()
    light.energy = base_energy * targets[0]

    if not any(modifier.type == "CYCLES" for modifier in fcurve.modifiers):
        modifier = fcurve.modifiers.new(type="CYCLES")
        modifier.mode_before = "REPEAT"
        modifier.mode_after = "REPEAT"
    fcurve.mute = not bool(active)
    if not active:
        light.energy = 0.0
    return True
