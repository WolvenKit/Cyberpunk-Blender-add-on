from __future__ import annotations

from functools import partial

import bpy

from ...blender import shader_nodes
from ...blender.shader_nodes import (
    assign_if_changed,
    new_node,
    rgb_node,
    set_color_output,
    set_value_output,
    value_node,
)
from ...blender.transactions import track_created_datablock
from ..model.volume_preview import (
    DISTANT_TRANSMISSION_DENSITY_SCALE,
    capped_box,
    cloud_ceiling,
    distant_fog_ceiling,
    distant_fog_preview,
    global_fog_ceiling,
    global_fog_preview,
)
from ..runtime.ownership import (
    cache_owned,
    find_owned,
    managed_name,
    retire_datablock,
    retire_object,
    tag_owned,
)
from .meshes import cube_mesh
from .weather import ensure_weather_anchor, weather_collection

GLOBAL_FOG_OBJECT = "CP77_GlobalFogPreview"
DISTANT_FOG_OBJECT = "CP77_DistantFogPreview"
GLOBAL_FOG_MATERIAL = "CP77_Weather_GlobalFog"
DISTANT_FOG_MATERIAL = "CP77_Weather_DistantFog"
# Schema 3 cubes face outward, as Cycles needs to render a volume inside its mesh; older objects are
# rebuilt by the next setup or refresh.
FOG_OBJECT_SCHEMA_VERSION = 3
# Schema 3 is the compact graph (same density model); older materials are rebuilt by the next
# setup or refresh.
FOG_MATERIAL_SCHEMA_VERSION = 3

_set_value = partial(set_value_output, epsilon=1.0e-12)
_set_color = partial(
    set_color_output,
    minimum=0.0,
    maximum=None,
    epsilon=1.0e-12,
)


def _fog_material(scene, role):
    return find_owned("materials", scene, f"{role}_MATERIAL")


def _ensure_volume_object(scene, name, role, material):
    collection = weather_collection(scene, create=True)
    anchor = ensure_weather_anchor(scene, collection)
    obj = find_owned("objects", scene, role)
    if obj is None or obj.get("cp77_fog_schema") != FOG_OBJECT_SCHEMA_VERSION:
        stale_obj = obj
        target_name = managed_name(scene, name)
        mesh = cube_mesh(managed_name(scene, f"{name}_Mesh"))
        obj = track_created_datablock(
            "objects",
            bpy.data.objects.new(target_name, mesh),
        )
        tag_owned(obj, scene, role, base_name=name)
        cache_owned("objects", scene, role, obj)
        collection.objects.link(obj)
        obj.parent = anchor
        obj.location = (0.0, 0.0, 0.0)
        obj.display_type = "WIRE"
        obj["cp77_fog_schema"] = FOG_OBJECT_SCHEMA_VERSION
        if hasattr(obj, "visible_shadow"):
            obj.visible_shadow = False
        if stale_obj is not None:
            retire_object(
                stale_obj,
                scene=scene,
                role=role,
                replacement=obj,
                replacement_name=target_name,
            )
    if not obj.data.materials:
        obj.data.materials.append(material)
    elif obj.data.materials[0] is not material:
        obj.data.materials[0] = material
    return obj


def _build_global_fog_material(material):
    material.use_nodes = True
    material["cp77_fog_schema"] = FOG_MATERIAL_SCHEMA_VERSION
    tree = material.node_tree
    tree.nodes.clear()

    geometry = new_node(
        tree, "ShaderNodeNewGeometry", "CP77 Fog Position", (-1500, 200)
    )
    position = geometry.outputs["Position"]
    separate = new_node(
        tree, "ShaderNodeSeparateXYZ", "CP77 Fog Position XYZ", (-1310, 200)
    )
    tree.links.new(position, separate.inputs["Vector"])
    world_z = separate.outputs["Z"]

    density = value_node(tree, "CP77 Fog Density", 0.0, (-1480, 530)).outputs["Value"]
    fog_height = value_node(tree, "CP77 Fog Height", 0.0, (-1480, 460)).outputs["Value"]
    height_falloff = value_node(
        tree, "CP77 Fog Height Falloff", 0.0, (-1480, 390)
    ).outputs["Value"]
    max_cut = value_node(tree, "CP77 Fog Height Max Cut", 1.0, (-1480, 320)).outputs[
        "Value"
    ]
    anisotropy = value_node(tree, "CP77 Fog Anisotropy", 0.0, (-1480, 250)).outputs[
        "Value"
    ]
    absorption = value_node(tree, "CP77 Fog Absorption", 0.0, (-1480, 180)).outputs[
        "Value"
    ]
    enabled = value_node(tree, "CP77 Fog Preview Enabled", 1.0, (-1480, 110)).outputs[
        "Value"
    ]

    # Density thins linearly to zero over the first kilometre of altitude ...
    world_height = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        world_z,
        -0.001,
        1.0,
        name="CP77 Fog World Height Saturate",
        location=(-1120, 420),
        use_clamp=True,
    )
    # ... and decays as exp(-max(z - height, 0) * falloff) above the fog height, capped.
    height_below = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        fog_height,
        world_z,
        name="CP77 Fog Height Delta",
        location=(-1120, 260),
    )
    height_depth = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MINIMUM",
        height_below,
        0.0,
        name="CP77 Fog Height Depth",
        location=(-930, 260),
    )
    exponent = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        height_depth,
        height_falloff,
        name="CP77 Fog Falloff Exponent",
        location=(-740, 260),
    )
    decay = shader_nodes.math(
        tree.nodes,
        tree.links,
        "EXPONENT",
        exponent,
        name="CP77 Fog Height Exp",
        location=(-560, 260),
    )
    decay = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MINIMUM",
        decay,
        max_cut,
        name="CP77 Fog Falloff Max Cut",
        location=(-380, 260),
    )

    base_density = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        density,
        world_height,
        name="CP77 Fog Base Density",
        location=(-160, 430),
    )
    height_density = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        base_density,
        decay,
        name="CP77 Fog Height Density",
        location=(30, 410),
    )

    noise = new_node(tree, "ShaderNodeTexNoise", "CP77 Fog Noise", (-880, -100))
    noise.noise_dimensions = "3D"
    tree.links.new(position, noise.inputs["Vector"])
    noise_scale = value_node(tree, "CP77 Fog Noise Scale", 1.0, (-1110, -100)).outputs[
        "Value"
    ]
    preview_scale = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        noise_scale,
        0.01,
        name="CP77 Fog Noise Preview Scale",
        location=(-920, -230),
    )
    tree.links.new(preview_scale, noise.inputs["Scale"])
    noise.inputs["Detail"].default_value = 2.0
    noise.inputs["Roughness"].default_value = 0.5
    threshold = value_node(tree, "CP77 Fog Noise Threshold", 0.0, (-720, -220)).outputs[
        "Value"
    ]
    excess = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        noise.outputs["Fac"],
        threshold,
        name="CP77 Fog Noise Threshold Subtract",
        location=(-500, -100),
    )
    excess = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MAXIMUM",
        excess,
        0.0,
        name="CP77 Fog Noise Threshold Max",
        location=(-310, -100),
    )
    modulation = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        excess,
        0.5,
        0.5,
        name="CP77 Fog Noise Bias",
        location=(-120, -100),
    )

    noisy_density = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        height_density,
        modulation,
        name="CP77 Fog Noisy Density",
        location=(230, 320),
    )
    final_density = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        noisy_density,
        enabled,
        name="CP77 Fog Final Density",
        location=(410, 320),
    )

    color = rgb_node(tree, "CP77 Fog Albedo", (1.0, 1.0, 1.0), (340, 110))
    scatter = new_node(tree, "ShaderNodeVolumeScatter", "CP77 Fog Scatter", (650, 250))
    tree.links.new(color.outputs["Color"], scatter.inputs["Color"])
    tree.links.new(final_density, scatter.inputs["Density"])
    tree.links.new(anisotropy, scatter.inputs["Anisotropy"])

    absorption_density = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        final_density,
        absorption,
        name="CP77 Fog Absorption Density",
        location=(430, 10),
    )
    absorb = new_node(
        tree, "ShaderNodeVolumeAbsorption", "CP77 Fog Absorption", (650, 20)
    )
    absorb.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    tree.links.new(absorption_density, absorb.inputs["Density"])

    add = new_node(tree, "ShaderNodeAddShader", "CP77 Fog Volume", (890, 160))
    tree.links.new(scatter.outputs["Volume"], add.inputs["Shader"])
    tree.links.new(
        absorb.outputs["Volume"],
        shader_nodes.socket_by_identifier(add.inputs, "Shader_001"),
    )
    output = new_node(tree, "ShaderNodeOutputMaterial", "CP77 Fog Output", (1100, 160))
    tree.links.new(add.outputs["Shader"], output.inputs["Volume"])
    return material


def _build_distant_fog_material(material, anchor):
    material.use_nodes = True
    material["cp77_fog_schema"] = FOG_MATERIAL_SCHEMA_VERSION
    tree = material.node_tree
    tree.nodes.clear()

    geometry = new_node(
        tree, "ShaderNodeNewGeometry", "CP77 Distant Fog Position", (-1550, 170)
    )
    position = geometry.outputs["Position"]
    separate = new_node(
        tree, "ShaderNodeSeparateXYZ", "CP77 Distant Fog Position XYZ", (-1360, 300)
    )
    tree.links.new(position, separate.inputs["Vector"])
    world_z = separate.outputs["Z"]
    # Distances are measured from the weather anchor, so the fog box itself can be resized and
    # lowered under the cloud deck without moving the fog.
    origin = new_node(
        tree, "ShaderNodeTexCoord", "CP77 Distant Fog Origin", (-1360, 80)
    )
    origin.object = anchor
    offset = origin.outputs["Object"]
    distance = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "LENGTH",
        offset,
        name="CP77 Distant Fog Distance",
        location=(-950, 80),
    )
    horizontal = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        offset,
        (1.0, 1.0, 0.0),
        name="CP77 Distant Fog Horizontal",
        location=(-950, -80),
    )
    horizontal_distance = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "LENGTH",
        horizontal,
        name="CP77 Distant Fog Horizontal Distance",
        location=(-760, -80),
    )

    enabled = value_node(
        tree, "CP77 Distant Fog Preview Enabled", 1.0, (-1510, 540)
    ).outputs["Value"]
    start = value_node(tree, "CP77 Distant Fog Start Range", 0.0, (-1510, 470)).outputs[
        "Value"
    ]
    density1 = value_node(
        tree, "CP77 Distant Fog Density 1", 0.0, (-1510, 400)
    ).outputs["Value"]
    height1 = value_node(tree, "CP77 Distant Fog Height 1", 0.0, (-1510, 330)).outputs[
        "Value"
    ]
    falloff1 = value_node(
        tree, "CP77 Distant Fog Falloff 1", 0.0, (-1510, 260)
    ).outputs["Value"]
    density2 = value_node(
        tree, "CP77 Distant Fog Density 2", 0.0, (-1510, 190)
    ).outputs["Value"]
    height2 = value_node(tree, "CP77 Distant Fog Height 2", 0.0, (-1510, 120)).outputs[
        "Value"
    ]
    falloff2 = value_node(tree, "CP77 Distant Fog Falloff 2", 0.0, (-1510, 50)).outputs[
        "Value"
    ]
    near_distance = value_node(
        tree, "CP77 Distant Fog Near Color Distance", 0.0, (-1510, -20)
    ).outputs["Value"]
    far_distance = value_node(
        tree, "CP77 Distant Fog Far Color Distance", 1.0, (-1510, -90)
    ).outputs["Value"]

    def layer(prefix, density_value, height_value, falloff_value, y):
        delta = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            world_z,
            height_value,
            name=f"{prefix} Height Delta",
            location=(-1150, y),
        )
        exponent = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            delta,
            falloff_value,
            name=f"{prefix} Exponent",
            location=(-960, y),
        )
        exponent = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            exponent,
            -0.01,
            name=f"{prefix} Falloff Scale",
            location=(-770, y),
        )
        exponent = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MINIMUM",
            exponent,
            127.0,
            name=f"{prefix} Exponent Clamp",
            location=(-580, y),
        )
        transmission = shader_nodes.math(
            tree.nodes,
            tree.links,
            "POWER",
            2.0,
            exponent,
            name=f"{prefix} Exp2",
            location=(-390, y),
        )
        scaled_density = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            density_value,
            0.001 * DISTANT_TRANSMISSION_DENSITY_SCALE,
            name=f"{prefix} Density Scale",
            location=(-200, y),
        )
        return shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            scaled_density,
            transmission,
            name=f"{prefix} Density",
            location=(-10, y),
        )

    layer1 = layer("CP77 Distant Fog Layer 1", density1, height1, falloff1, 420)
    layer2 = layer("CP77 Distant Fog Layer 2", density2, height2, falloff2, 250)
    layers = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        layer1,
        layer2,
        name="CP77 Distant Fog Layer Sum",
        location=(390, 340),
    )
    range_mask = shader_nodes.math(
        tree.nodes,
        tree.links,
        "GREATER_THAN",
        distance,
        start,
        name="CP77 Distant Fog Start Mask",
        location=(190, 100),
    )
    ranged = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        layers,
        range_mask,
        name="CP77 Distant Fog Ranged Density",
        location=(580, 300),
    )
    final_density = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        ranged,
        enabled,
        name="CP77 Distant Fog Final Density",
        location=(770, 300),
    )

    color_range = new_node(
        tree, "ShaderNodeMapRange", "CP77 Distant Fog Color Range", (-300, -130)
    )
    color_range.clamp = True
    tree.links.new(horizontal_distance, color_range.inputs["Value"])
    tree.links.new(near_distance, color_range.inputs["From Min"])
    tree.links.new(far_distance, color_range.inputs["From Max"])
    color_range.inputs["To Min"].default_value = 0.0
    color_range.inputs["To Max"].default_value = 1.0
    color_weight = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        color_range.outputs["Result"],
        color_range.outputs["Result"],
        name="CP77 Distant Fog Color Range Squared",
        location=(-80, -130),
    )
    near_color = rgb_node(
        tree, "CP77 Distant Fog Near Color", (1.0, 1.0, 1.0), (130, -120)
    ).outputs["Color"]
    far_color = rgb_node(
        tree, "CP77 Distant Fog Far Color", (1.0, 1.0, 1.0), (130, -220)
    ).outputs["Color"]
    color = shader_nodes.vector_lerp(
        tree.nodes,
        tree.links,
        near_color,
        far_color,
        color_weight,
        name="CP77 Distant Fog Color",
        location=(370, -150),
    )

    scatter = new_node(
        tree, "ShaderNodeVolumeScatter", "CP77 Distant Fog Scatter", (900, 180)
    )
    tree.links.new(color, scatter.inputs["Color"])
    tree.links.new(final_density, scatter.inputs["Density"])
    scatter.inputs["Anisotropy"].default_value = 0.0
    output = new_node(
        tree, "ShaderNodeOutputMaterial", "CP77 Distant Fog Output", (1110, 180)
    )
    tree.links.new(scatter.outputs["Volume"], output.inputs["Volume"])
    return material


def _ensure_material(scene, name, role, builder):
    material_role = f"{role}_MATERIAL"
    material = _fog_material(scene, role)
    stale_material = None
    rebuild = material is None
    if material is not None:
        rebuild = (
            material.get("cp77_fog_schema") != FOG_MATERIAL_SCHEMA_VERSION
            or not material.use_nodes
        )
        if rebuild:
            stale_material = material

    if rebuild:
        target_name = managed_name(scene, name)
        material = track_created_datablock(
            "materials",
            bpy.data.materials.new(target_name),
        )
        tag_owned(material, scene, material_role, base_name=name)
        cache_owned("materials", scene, material_role, material)
        builder(material)
        if stale_material is not None:
            retire_datablock(
                "materials",
                stale_material,
                scene=scene,
                role=material_role,
                replacement=material,
                replacement_name=target_name,
            )
    return material


def ensure_fog_preview(scene, settings):
    created = 0
    if settings.preview_volumetric_fog:
        material = _ensure_material(
            scene, GLOBAL_FOG_MATERIAL, "GLOBAL_FOG", _build_global_fog_material
        )
        if find_owned("objects", scene, "GLOBAL_FOG") is None:
            created += 1
        _ensure_volume_object(scene, GLOBAL_FOG_OBJECT, "GLOBAL_FOG", material)
    if settings.preview_distant_fog:
        anchor = ensure_weather_anchor(scene, weather_collection(scene, create=True))
        material = _ensure_material(
            scene,
            DISTANT_FOG_MATERIAL,
            "DISTANT_FOG",
            partial(_build_distant_fog_material, anchor=anchor),
        )
        origin = material.node_tree.nodes.get("CP77 Distant Fog Origin")
        if origin is not None and getattr(origin, "object", anchor) is not anchor:
            origin.object = anchor
        if find_owned("objects", scene, "DISTANT_FOG") is None:
            created += 1
        _ensure_volume_object(scene, DISTANT_FOG_OBJECT, "DISTANT_FOG", material)
    return created


def _anchor_height(obj):
    # The anchor is a top-level empty; its location is current even before the depsgraph updates.
    return (
        float(obj.parent.location.z)
        if obj is not None and obj.parent is not None
        else 0.0
    )


def _apply_volume(obj, active, extent, properties, ceiling):
    if obj is None:
        return
    offset, half_height = capped_box(extent, _anchor_height(obj), ceiling)
    assign_if_changed(obj, "location", (0.0, 0.0, offset))
    assign_if_changed(obj, "scale", (extent, extent, half_height))
    obj.hide_viewport = not active
    obj.hide_render = not active
    for key, value in properties.items():
        obj[key] = value


def apply_fog_preview(scene, settings, sample, weather_sample):
    ceiling = cloud_ceiling(
        settings.preview_volumetric_clouds
        and find_owned("objects", scene, "VOLUMETRIC_CLOUDS") is not None,
        weather_sample,
    )
    global_obj = find_owned("objects", scene, "GLOBAL_FOG")
    global_mat = _fog_material(scene, "GLOBAL_FOG")
    fog = global_fog_preview(
        settings.preview_volumetric_fog, global_obj is not None, weather_sample
    )
    _apply_volume(
        global_obj,
        fog.active,
        fog.preview_range,
        fog.properties,
        global_fog_ceiling(weather_sample, _anchor_height(global_obj), ceiling),
    )
    for name, value in fog.values.items():
        _set_value(global_mat, name, value)
    _set_color(global_mat, "CP77 Fog Albedo", fog.albedo)

    distant_obj = find_owned("objects", scene, "DISTANT_FOG")
    distant_mat = _fog_material(scene, "DISTANT_FOG")
    distant = distant_fog_preview(
        settings.preview_distant_fog, distant_obj is not None, sample, weather_sample
    )
    _apply_volume(
        distant_obj,
        distant.active,
        distant.preview_far,
        distant.properties,
        distant_fog_ceiling(weather_sample, _anchor_height(distant_obj), ceiling),
    )
    for name, value in distant.values.items():
        _set_value(distant_mat, name, value)
    _set_color(distant_mat, "CP77 Distant Fog Near Color", distant.near_color)
    _set_color(distant_mat, "CP77 Distant Fog Far Color", distant.far_color)


_GLOBAL_FOG_KEYED_VALUES = (
    "CP77 Fog Preview Enabled",
    "CP77 Fog Density",
    "CP77 Fog Height",
    "CP77 Fog Height Falloff",
    "CP77 Fog Height Max Cut",
    "CP77 Fog Anisotropy",
    "CP77 Fog Absorption",
    "CP77 Fog Noise Scale",
    "CP77 Fog Noise Threshold",
)
_GLOBAL_FOG_KEYED_COLORS = ("CP77 Fog Albedo",)
_DISTANT_FOG_KEYED_VALUES = (
    "CP77 Distant Fog Preview Enabled",
    "CP77 Distant Fog Start Range",
    "CP77 Distant Fog Density 1",
    "CP77 Distant Fog Height 1",
    "CP77 Distant Fog Falloff 1",
    "CP77 Distant Fog Density 2",
    "CP77 Distant Fog Height 2",
    "CP77 Distant Fog Falloff 2",
    "CP77 Distant Fog Near Color Distance",
    "CP77 Distant Fog Far Color Distance",
)
_DISTANT_FOG_KEYED_COLORS = (
    "CP77 Distant Fog Near Color",
    "CP77 Distant Fog Far Color",
)


def fog_keyframe_targets(scene):
    """(owner, data path) pairs a bake keys on the global and distant fog previews"""
    targets = []
    for role, values, colors in (
        ("GLOBAL_FOG", _GLOBAL_FOG_KEYED_VALUES, _GLOBAL_FOG_KEYED_COLORS),
        ("DISTANT_FOG", _DISTANT_FOG_KEYED_VALUES, _DISTANT_FOG_KEYED_COLORS),
    ):
        obj = find_owned("objects", scene, role)
        if obj is not None:
            targets.extend(((obj, "location"), (obj, "scale")))
        material = _fog_material(scene, role)
        if material is None or not material.use_nodes:
            continue
        nodes = material.node_tree.nodes
        for names, output in ((values, "Value"), (colors, "Color")):
            for name in names:
                node = nodes.get(name)
                if node is not None:
                    targets.append((node.outputs[output], "default_value"))
    return tuple(targets)


def clear_fog_preview_animation(scene):
    for role in ("GLOBAL_FOG", "DISTANT_FOG"):
        obj = find_owned("objects", scene, role)
        if obj is not None:
            obj.animation_data_clear()
        material = _fog_material(scene, role)
        if material is not None and material.use_nodes:
            material.node_tree.animation_data_clear()
