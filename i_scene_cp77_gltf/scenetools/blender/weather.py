from __future__ import annotations

from pathlib import Path

import bpy

from ...blender import shader_nodes
from ...blender.shader_nodes import (
    assign_if_changed,
    new_node,
    set_default_if_changed,
)
from ...blender.transactions import track_created_datablock
from ..model import weather_preview
from ..model.sky_preview import exposure_scale
from ..model.weather_preview import (
    rain_effect_active,
    rain_flow,
    rain_intensity,
    rain_tint,
    weather_light,
)
from ..runtime.ownership import (
    cache_owned,
    find_owned,
    managed_name,
    retire_datablock,
    retire_object,
    root_collection,
    tag_owned,
)
from .images import load_named_image
from .rain_streaks import (
    PHASE_ATTRIBUTE,
    SEED_ATTRIBUTE,
    rain_streak_group,
    set_streak_material,
)

COLLECTION_NAME = "CP77 Weather Preview"
CIRRUS_OBJECT = "CP77_HighCloud_Cirrus"
ALTO_OBJECT = "CP77_HighCloud_Altocumulus"
WEATHER_ANCHOR_NAME = "CP77_WeatherAnchor"
RAIN_NEAR_OBJECT = "CP77_RainNearField"
RAIN_FAR_OBJECT = "CP77_RainFarField"
CLOUD_CIRRUS_MATERIAL = "CP77_Weather_Cirrus"
CLOUD_ALTO_MATERIAL = "CP77_Weather_Altocumulus"
RAIN_NEAR_MATERIAL = "CP77_Weather_RainNear"
RAIN_FAR_MATERIAL = "CP77_Weather_RainFar"
# Schema 4 cloud materials and schema 5 rain materials glow with each sample's light; schema 6 rain materials clamp
# with use_clamp; schema 4 rain fields are falling strands. Older ones are rebuilt by the next setup or refresh.
CLOUD_MATERIAL_SCHEMA = 4
RAIN_MATERIAL_SCHEMA = 6
RAIN_OBJECT_SCHEMA = 4
# The high-cloud cards fade out between these distances from their centre, in half-widths of the card.
CLOUD_EDGE_FADE = (0.55, 1.0)
RAIN_MASK = "rain_system_drop.png"
RAIN_MODIFIER = "CP77 Rain Streaks"

RESOURCE_ROOT = (
    Path(__file__).resolve().parents[2] / "resources" / "scenetools" / "weather"
)

CLOUD_SPECS = {
    "CIRRUS": {
        "object": CIRRUS_OBJECT,
        "material": CLOUD_CIRRUS_MATERIAL,
        "altitude": 500.0,
        "size": 6000.0,
        "diffuse": "cirrus_cover.png",
        "day_mask": "perlin_noise_tileable2.png",
        "night_mask": "perlin_noise_tileable2.png",
        "uv_scale": (4.0, 4.0),
        "uv_speed": (0.00200000009, 0.0),
        "color_power": 0.5,
        "day_multiplier": 5.0,
        "night_multiplier": 1.0,
        "rotation": 0.0,
    },
    "ALTOCUMULUS": {
        "object": ALTO_OBJECT,
        "material": CLOUD_ALTO_MATERIAL,
        "altitude": 400.0,
        "size": 6000.0,
        "diffuse": "altocumulus_1.png",
        "day_mask": "perlin_noise_tileable3.png",
        "night_mask": "perlin_noise_tileable2.png",
        "uv_scale": (12.0, 12.0),
        "uv_speed": (0.00999999978, 0.00100000005),
        "color_power": 1.5,
        "day_multiplier": 1.5,
        "night_multiplier": 1.0,
        "rotation": 0.100000001,
    },
}

# Near drops fade in and out over each fall; the far streaks thin out in patches and where they are seen end-on.
RAIN_SPECS = {
    "RAIN_NEAR": {
        "object": RAIN_NEAR_OBJECT,
        "material": RAIN_NEAR_MATERIAL,
        "count": 1600,
        "radius": 3.0,
        "z_min": -3.0,
        "z_max": 2.0,
        "length_range": (0.10, 0.42),
        "width_range": (0.004, 0.014),
        "fall_speed": 7.0,
        "brightness": 9.5,
        "opacity": 0.8,
        "wind_skew": 0.200000003,
        "distance_fade": (0.01, 2.5),
        "fade_over_fall": True,
        "patches": False,
        "seed": 0xC077A11,
    },
    "RAIN_FAR": {
        "object": RAIN_FAR_OBJECT,
        "material": RAIN_FAR_MATERIAL,
        "count": 24000,
        "radius": 45.0,
        "z_min": -20.0,
        "z_max": 20.0,
        "length_range": (0.45, 1.9),
        "width_range": (0.008, 0.028),
        "fall_speed": 9.0,
        "brightness": 1.64383602,
        "opacity": 0.6,
        "wind_skew": 0.119999997,
        "distance_fade": (2.5, 35.0),
        "fade_over_fall": False,
        "patches": True,
        "seed": 0xC077FA2,
    },
}


def _resource_path(group, filename):
    return RESOURCE_ROOT / group / filename


def weather_collection(scene, create=False):
    root = root_collection(scene, create=create)
    collection = find_owned("collections", scene, "WEATHER_COLLECTION")
    if collection is None and create:
        collection = track_created_datablock(
            "collections",
            bpy.data.collections.new(managed_name(scene, COLLECTION_NAME)),
        )
        tag_owned(collection, scene, "WEATHER_COLLECTION", base_name=COLLECTION_NAME)
        cache_owned("collections", scene, "WEATHER_COLLECTION", collection)
    if collection is not None and root is not None:
        if root.children.get(collection.name) is None:
            root.children.link(collection)
        if scene.collection.children.get(collection.name) is collection:
            scene.collection.children.unlink(collection)
    return collection


def _weather_material(scene, role):
    return find_owned("materials", scene, f"{role}_MATERIAL")


def _load_image(group, filename, non_color=True):
    return load_named_image(
        _resource_path(group, filename),
        f"CP77 Weather {filename}",
        colorspace="Non-Color" if non_color else None,
    )


def _set_transparent_surface(material):
    material.surface_render_method = "DITHERED"
    if hasattr(material, "use_transparency_overlap"):
        material.use_transparency_overlap = False


def _time_driver(socket, axis, scene, speed):
    driver = socket.driver_add("default_value", axis).driver
    driver.type = "SCRIPTED"
    fps = driver.variables.new()
    fps.name = "fps"
    fps.type = "SINGLE_PROP"
    fps.targets[0].id_type = "SCENE"
    fps.targets[0].id = scene
    fps.targets[0].data_path = "render.fps"
    fps_base = driver.variables.new()
    fps_base.name = "fps_base"
    fps_base.type = "SINGLE_PROP"
    fps_base.targets[0].id_type = "SCENE"
    fps_base.targets[0].id = scene
    fps_base.targets[0].data_path = "render.fps_base"
    driver.expression = f"frame * fps_base / fps * {float(speed):.12g}"


def _glow_surface(tree, color, alpha, strength, prefix, location):
    """Transparent where alpha is 0, else glowing in color at strength"""
    x, y = location
    emission = new_node(tree, "ShaderNodeEmission", f"{prefix} Emission", (x, y + 120))
    emission.inputs["Strength"].default_value = float(strength)
    tree.links.new(color, emission.inputs["Color"])
    transparent = new_node(
        tree, "ShaderNodeBsdfTransparent", f"{prefix} Transparent", (x, y - 140)
    )
    surface = new_node(tree, "ShaderNodeMixShader", f"{prefix} Surface", (x + 220, y))
    tree.links.new(alpha, surface.inputs["Fac"])
    tree.links.new(transparent.outputs["BSDF"], surface.inputs["Shader"])
    tree.links.new(
        emission.outputs["Emission"],
        shader_nodes.socket_by_identifier(surface.inputs, "Shader_001"),
    )
    output = new_node(
        tree, "ShaderNodeOutputMaterial", f"{prefix} Output", (x + 440, y)
    )
    tree.links.new(surface.outputs["Shader"], output.inputs["Surface"])
    return emission


def _cloud_edge_fade(tree, uv, location):
    """1 out to the inner edge-fade distance from the card's centre, falling to 0 at the outer one"""
    x, y = location
    offset = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        name="CP77 Cloud Edge Offset",
        location=(x, y),
    ).node
    shader_nodes.socket_by_identifier(offset.inputs, "Vector_001").default_value = (
        0.5,
        0.5,
        0.0,
    )
    tree.links.new(uv, offset.inputs["Vector"])
    length = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "LENGTH",
        name="CP77 Cloud Edge Length",
        location=(x + 180, y),
    ).node
    tree.links.new(offset.outputs["Vector"], length.inputs["Vector"])
    distance = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        None,
        2.0,
        name="CP77 Cloud Edge Distance",
        location=(x + 360, y),
    ).node
    tree.links.new(length.outputs["Value"], distance.inputs["Value"])
    inner, outer = CLOUD_EDGE_FADE
    fade = new_node(tree, "ShaderNodeMapRange", "CP77 Cloud Edge Fade", (x + 540, y))
    fade.clamp = True
    fade.inputs["From Min"].default_value = outer
    fade.inputs["From Max"].default_value = inner
    tree.links.new(distance.outputs["Value"], fade.inputs["Value"])
    return fade.outputs["Result"]


def _ensure_cloud_material(scene, role, spec):
    material_role = f"{role}_MATERIAL"
    material = _weather_material(scene, role)
    if (
        material is not None
        and material.get("cp77_weather_schema") == CLOUD_MATERIAL_SCHEMA
    ):
        return material
    stale_material = material
    target_name = managed_name(scene, spec["material"])
    material = track_created_datablock(
        "materials",
        bpy.data.materials.new(target_name),
    )
    tag_owned(material, scene, material_role, base_name=spec["material"])
    cache_owned("materials", scene, material_role, material)
    material.use_nodes = True
    material["cp77_weather_schema"] = CLOUD_MATERIAL_SCHEMA
    _set_transparent_surface(material)
    tree = material.node_tree
    tree.nodes.clear()

    texcoord = new_node(tree, "ShaderNodeTexCoord", "CP77 Cloud UV", (-1280, 120))
    scale = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        name="CP77 Cloud UV Scale",
        location=(-1080, 120),
    ).node
    shader_nodes.socket_by_identifier(scale.inputs, "Vector_001").default_value = (
        *spec["uv_scale"],
        1.0,
    )
    tree.links.new(texcoord.outputs["UV"], scale.inputs["Vector"])
    scroll = shader_nodes.vector_math(
        tree.nodes, tree.links, "ADD", name="CP77 Cloud UV Scroll", location=(-880, 120)
    ).node
    shader_nodes.socket_by_identifier(scroll.inputs, "Vector_001").default_value = (
        0.0,
        0.0,
        0.0,
    )
    tree.links.new(scale.outputs["Vector"], scroll.inputs["Vector"])
    _time_driver(
        shader_nodes.socket_by_identifier(scroll.inputs, "Vector_001"),
        0,
        scene,
        spec["uv_speed"][0],
    )
    _time_driver(
        shader_nodes.socket_by_identifier(scroll.inputs, "Vector_001"),
        1,
        scene,
        spec["uv_speed"][1],
    )

    diffuse = new_node(tree, "ShaderNodeTexImage", "CP77 Cloud Diffuse", (-660, 160))
    diffuse.image = _load_image("clouds", spec["diffuse"])
    diffuse.extension = "REPEAT"
    diffuse.interpolation = "Linear"
    tree.links.new(scroll.outputs["Vector"], diffuse.inputs["Vector"])
    channels = new_node(
        tree, "ShaderNodeSeparateColor", "CP77 Cloud Diffuse Channels", (-440, 180)
    )
    tree.links.new(diffuse.outputs["Color"], channels.inputs["Color"])

    # The layer's colour curve, red * (red ^ power * multiplier) ^ 2.2, the multiplier blending from night to day.
    branch_power = shader_nodes.math(
        tree.nodes,
        tree.links,
        "POWER",
        None,
        float(spec["color_power"]),
        name="CP77 Cloud Color Power",
        location=(-230, 210),
    ).node
    tree.links.new(channels.outputs["Red"], branch_power.inputs["Value"])
    day_factor = new_node(
        tree, "ShaderNodeValue", "CP77 Cloud Day Factor", (-450, -260)
    )
    day_factor.outputs["Value"].default_value = 1.0
    multiplier = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        None,
        float(spec["day_multiplier"]) - float(spec["night_multiplier"]),
        name="CP77 Cloud Color Multiplier",
        location=(-230, 60),
    ).node
    shader_nodes.socket_by_identifier(
        multiplier.inputs, "Value_002"
    ).default_value = float(spec["night_multiplier"])
    tree.links.new(day_factor.outputs["Value"], multiplier.inputs["Value"])
    branch = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        name="CP77 Cloud Branch Multiplier",
        location=(-30, 210),
    ).node
    tree.links.new(branch_power.outputs["Value"], branch.inputs["Value"])
    tree.links.new(
        multiplier.outputs["Value"],
        shader_nodes.socket_by_identifier(branch.inputs, "Value_001"),
    )
    gamma = shader_nodes.math(
        tree.nodes,
        tree.links,
        "POWER",
        None,
        2.2,
        name="CP77 Cloud Explicit Gamma",
        location=(170, 210),
    ).node
    tree.links.new(branch.outputs["Value"], gamma.inputs["Value"])
    final_value = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        name="CP77 Cloud Final Color",
        location=(370, 210),
    ).node
    tree.links.new(channels.outputs["Red"], final_value.inputs["Value"])
    tree.links.new(
        gamma.outputs["Value"],
        shader_nodes.socket_by_identifier(final_value.inputs, "Value_001"),
    )
    gray = new_node(tree, "ShaderNodeCombineXYZ", "CP77 Cloud Gray", (560, 210))
    for socket in gray.inputs:
        tree.links.new(final_value.outputs["Value"], socket)
    light = new_node(tree, "ShaderNodeRGB", "CP77 Cloud Light", (560, 380))
    light.outputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    lit_color = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        name="CP77 Cloud Lit Color",
        location=(760, 260),
    ).node
    tree.links.new(gray.outputs["Vector"], lit_color.inputs["Vector"])
    tree.links.new(
        light.outputs["Color"],
        shader_nodes.socket_by_identifier(lit_color.inputs, "Vector_001"),
    )

    mask_day = new_node(
        tree, "ShaderNodeTexImage", "CP77 Cloud Day Alpha Mask", (-620, -170)
    )
    mask_day.image = _load_image("clouds", spec["day_mask"])
    mask_day.extension = "REPEAT"
    mask_day.interpolation = "Linear"
    tree.links.new(texcoord.outputs["UV"], mask_day.inputs["Vector"])
    mask_night = new_node(
        tree, "ShaderNodeTexImage", "CP77 Cloud Night Alpha Mask", (-620, -360)
    )
    mask_night.image = _load_image("clouds", spec["night_mask"])
    mask_night.extension = "REPEAT"
    mask_night.interpolation = "Linear"
    tree.links.new(texcoord.outputs["UV"], mask_night.inputs["Vector"])
    day_mask_channels = new_node(
        tree, "ShaderNodeSeparateColor", "CP77 Cloud Day Mask Channels", (-400, -130)
    )
    night_mask_channels = new_node(
        tree, "ShaderNodeSeparateColor", "CP77 Cloud Night Mask Channels", (-400, -360)
    )
    tree.links.new(mask_day.outputs["Color"], day_mask_channels.inputs["Color"])
    tree.links.new(mask_night.outputs["Color"], night_mask_channels.inputs["Color"])
    mask_mix = new_node(
        tree, "ShaderNodeMix", "CP77 Cloud Alpha Mask Variant", (-170, -90)
    )
    mask_mix.data_type = "FLOAT"
    tree.links.new(
        day_factor.outputs["Value"],
        shader_nodes.socket_by_identifier(mask_mix.inputs, "Factor_Float"),
    )
    tree.links.new(
        night_mask_channels.outputs["Red"],
        shader_nodes.socket_by_identifier(mask_mix.inputs, "A_Float"),
    )
    tree.links.new(
        day_mask_channels.outputs["Red"],
        shader_nodes.socket_by_identifier(mask_mix.inputs, "B_Float"),
    )
    mask_output = shader_nodes.socket_by_identifier(mask_mix.outputs, "Result_Float")

    alpha = shader_nodes.math(
        tree.nodes, tree.links, "MULTIPLY", name="CP77 Cloud Alpha", location=(80, -40)
    ).node
    tree.links.new(diffuse.outputs["Alpha"], alpha.inputs["Value"])
    tree.links.new(
        mask_output, shader_nodes.socket_by_identifier(alpha.inputs, "Value_001")
    )
    preview_alpha = new_node(
        tree, "ShaderNodeValue", "CP77 Cloud Preview Alpha", (80, -180)
    )
    preview_alpha.outputs["Value"].default_value = 1.0
    final_alpha = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        name="CP77 Cloud Final Alpha",
        location=(300, -40),
    ).node
    tree.links.new(alpha.outputs["Value"], final_alpha.inputs["Value"])
    tree.links.new(
        preview_alpha.outputs["Value"],
        shader_nodes.socket_by_identifier(final_alpha.inputs, "Value_001"),
    )
    edged_alpha = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        name="CP77 Cloud Edged Alpha",
        location=(500, -40),
    ).node
    tree.links.new(final_alpha.outputs["Value"], edged_alpha.inputs["Value"])
    tree.links.new(
        _cloud_edge_fade(tree, texcoord.outputs["UV"], (-200, -560)),
        shader_nodes.socket_by_identifier(edged_alpha.inputs, "Value_001"),
    )
    _glow_surface(
        tree,
        lit_color.outputs["Vector"],
        edged_alpha.outputs["Value"],
        1.0,
        "CP77 Cloud",
        (960, 40),
    )
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


def _ensure_cloud_object(scene, collection, role, spec):
    obj = find_owned("objects", scene, role)
    if obj is None:
        half = spec["size"] * 0.5
        mesh = track_created_datablock(
            "meshes", bpy.data.meshes.new(managed_name(scene, f"{spec['object']}_Mesh"))
        )
        mesh.from_pydata(
            [
                (-half, -half, 0.0),
                (half, -half, 0.0),
                (half, half, 0.0),
                (-half, half, 0.0),
            ],
            [],
            [(0, 1, 2, 3)],
        )
        uv = mesh.uv_layers.new(name="UVMap")
        uv_by_vertex = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
        loop_uv = []
        for loop in mesh.loops:
            loop_uv.extend(uv_by_vertex[loop.vertex_index])
        uv.uv.foreach_set("vector", loop_uv)
        mesh.update()
        obj = track_created_datablock(
            "objects", bpy.data.objects.new(managed_name(scene, spec["object"]), mesh)
        )
        tag_owned(obj, scene, role, base_name=spec["object"])
        cache_owned("objects", scene, role, obj)
        collection.objects.link(obj)
        obj.location.z = spec["altitude"]
        obj.rotation_euler[2] = float(spec.get("rotation", 0.0))
    if hasattr(obj, "visible_shadow"):
        assign_if_changed(obj, "visible_shadow", False)
    material = _ensure_cloud_material(scene, role, spec)
    if not obj.data.materials:
        obj.data.materials.append(material)
    elif obj.data.materials[0] is not material:
        obj.data.materials[0] = material
    return obj


def _camera_follow(obj, scene, *, vertical):
    constraint = obj.constraints.get("CP77 Weather Camera Follow")
    if constraint is None:
        constraint = obj.constraints.new("COPY_LOCATION")
        constraint.name = "CP77 Weather Camera Follow"
    if constraint.target is not scene.camera:
        constraint.target = scene.camera
    if not constraint.use_x:
        constraint.use_x = True
    if not constraint.use_y:
        constraint.use_y = True
    vertical = bool(vertical)
    if constraint.use_z != vertical:
        constraint.use_z = vertical


def _multiply_sockets(tree, sockets, prefix, x=0, y=0):
    if not sockets:
        return None
    result = sockets[0]
    for index, socket in enumerate(sockets[1:], start=1):
        node = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            name=f"{prefix} {index}",
            location=(x + index * 150, y),
        ).node
        tree.links.new(result, node.inputs["Value"])
        tree.links.new(
            socket, shader_nodes.socket_by_identifier(node.inputs, "Value_001")
        )
        result = node.outputs["Value"]
    return result


def _rain_attribute(tree, name, label, location):
    node = new_node(tree, "ShaderNodeAttribute", label, location)
    node.attribute_name = name
    return node.outputs["Fac"]


def _map_range(tree, name, value, low, high, location):
    node = new_node(tree, "ShaderNodeMapRange", name, location)
    node.clamp = True
    node.inputs["From Min"].default_value = float(low)
    node.inputs["From Max"].default_value = float(high)
    tree.links.new(value, node.inputs["Value"])
    return node.outputs["Result"]


def _rain_distance_fade(tree, spec):
    camera = new_node(
        tree, "ShaderNodeCameraData", "CP77 Rain Camera Distance", (-1160, -500)
    )
    distance = camera.outputs.get("View Distance") or camera.outputs["View Z Depth"]
    low, high = spec["distance_fade"]
    subtract = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        name="CP77 Rain Distance Start",
        location=(-930, -500),
    ).node
    tree.links.new(distance, subtract.inputs["Value"])
    shader_nodes.socket_by_identifier(
        subtract.inputs, "Value_001"
    ).default_value = float(low)
    divide = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        name="CP77 Rain Distance Range",
        location=(-750, -500),
    ).node
    tree.links.new(subtract.outputs["Value"], divide.inputs["Value"])
    shader_nodes.socket_by_identifier(divide.inputs, "Value_001").default_value = max(
        float(high) - float(low), 1.0e-6
    )
    return shader_nodes.clamp(
        tree.nodes,
        tree.links,
        divide.outputs["Value"],
        name=f"{'CP77 Rain Distance Fade'} Clamp",
        location=(-570, -500),
    )


def _rain_profile(tree, seed):
    """The drop mask along each strand"""
    strand = new_node(tree, "ShaderNodeHairInfo", "CP77 Rain Strand", (-1400, 200))
    uv = new_node(tree, "ShaderNodeCombineXYZ", "CP77 Rain Profile UV", (-1200, 200))
    uv.inputs["X"].default_value = 0.5
    tree.links.new(strand.outputs["Intercept"], uv.inputs["Y"])
    texture = new_node(tree, "ShaderNodeTexImage", "CP77 Rain Mask", (-1000, 200))
    texture.image = _load_image("rain", RAIN_MASK)
    texture.extension = "EXTEND"
    texture.interpolation = "Linear"
    tree.links.new(uv.outputs["Vector"], texture.inputs["Vector"])
    channels = new_node(
        tree, "ShaderNodeSeparateColor", "CP77 Rain Mask Channels", (-800, 200)
    )
    tree.links.new(texture.outputs["Color"], channels.inputs["Color"])
    pick = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        None,
        3.0,
        name="CP77 Rain Shape Pick",
        location=(-1200, -40),
    ).node
    tree.links.new(seed, pick.inputs["Value"])
    index = shader_nodes.math(
        tree.nodes,
        tree.links,
        "FLOOR",
        name="CP77 Rain Shape Index",
        location=(-1040, -40),
    ).node
    tree.links.new(pick.outputs["Value"], index.inputs["Value"])
    profile = None
    for offset, channel in enumerate(("Red", "Green", "Blue")):
        chosen = shader_nodes.math(
            tree.nodes,
            tree.links,
            "COMPARE",
            None,
            float(offset),
            name=f"CP77 Rain Shape {channel}",
            location=(-880, -40 - offset * 90),
        ).node
        shader_nodes.socket_by_identifier(
            chosen.inputs, "Value_002"
        ).default_value = 0.5
        tree.links.new(index.outputs["Value"], chosen.inputs["Value"])
        part = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            name=f"CP77 Rain Shape {channel} Part",
            location=(-700, 200 - offset * 90),
        ).node
        tree.links.new(channels.outputs[channel], part.inputs["Value"])
        tree.links.new(
            chosen.outputs["Value"],
            shader_nodes.socket_by_identifier(part.inputs, "Value_001"),
        )
        if profile is None:
            profile = part.outputs["Value"]
            continue
        total = shader_nodes.math(
            tree.nodes,
            tree.links,
            "ADD",
            name=f"CP77 Rain Shape Sum {offset}",
            location=(-540, 200 - offset * 90),
        ).node
        tree.links.new(profile, total.inputs["Value"])
        tree.links.new(
            part.outputs["Value"],
            shader_nodes.socket_by_identifier(total.inputs, "Value_001"),
        )
        profile = total.outputs["Value"]
    return profile


def _rain_fall_fade(tree):
    """Drops fade in over the first 30 % of their fall and out between 50 % and 70 % of it"""
    progress = _rain_attribute(
        tree, PHASE_ATTRIBUTE, "CP77 Rain Fall Progress", (-1400, -700)
    )
    fade_in = _map_range(
        tree, "CP77 Rain Fall Fade In", progress, 0.01, 0.3, (-1200, -700)
    )
    fade_out = _map_range(
        tree, "CP77 Rain Fall Fade Out", progress, 0.7, 0.5, (-1200, -860)
    )
    fade = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        name="CP77 Rain Fall Fade",
        location=(-1000, -760),
    ).node
    tree.links.new(fade_in, fade.inputs["Value"])
    tree.links.new(
        fade_out, shader_nodes.socket_by_identifier(fade.inputs, "Value_001")
    )
    return fade.outputs["Value"]


def _rain_patches(tree):
    """The far streaks thinned out in patches and where seen end-on"""
    geometry = new_node(
        tree, "ShaderNodeNewGeometry", "CP77 Rain Geometry", (-1600, -1000)
    )
    noise = new_node(tree, "ShaderNodeTexNoise", "CP77 Rain Patches", (-1400, -1000))
    noise.inputs["Scale"].default_value = 1.0 / 24.0
    tree.links.new(geometry.outputs["Position"], noise.inputs["Vector"])
    offset = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        None,
        0.3,
        name="CP77 Rain Patch Offset",
        location=(-1200, -1000),
    ).node
    tree.links.new(noise.outputs["Fac"], offset.inputs["Value"])
    density = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        None,
        2.4,
        name="CP77 Rain Patch Density",
        location=(-1040, -1000),
        use_clamp=True,
    ).node
    tree.links.new(offset.outputs["Value"], density.inputs["Value"])
    incoming = new_node(
        tree, "ShaderNodeSeparateXYZ", "CP77 Rain View Direction", (-1400, -1200)
    )
    tree.links.new(geometry.outputs["Incoming"], incoming.inputs["Vector"])
    steepness = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ABSOLUTE",
        name="CP77 Rain View Steepness",
        location=(-1200, -1200),
    ).node
    tree.links.new(incoming.outputs["Z"], steepness.inputs["Value"])
    root = shader_nodes.math(
        tree.nodes,
        tree.links,
        "POWER",
        None,
        1.0 / 3.0,
        name="CP77 Rain View Steepness Root",
        location=(-1040, -1200),
    ).node
    tree.links.new(steepness.outputs["Value"], root.inputs["Value"])
    side_on = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        1.0,
        name="CP77 Rain Side On",
        location=(-880, -1200),
    ).node
    tree.links.new(
        root.outputs["Value"],
        shader_nodes.socket_by_identifier(side_on.inputs, "Value_001"),
    )
    patches = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        name="CP77 Rain Patch Fade",
        location=(-720, -1100),
    ).node
    tree.links.new(density.outputs["Value"], patches.inputs["Value"])
    tree.links.new(
        side_on.outputs["Value"],
        shader_nodes.socket_by_identifier(patches.inputs, "Value_001"),
    )
    return patches.outputs["Value"]


def _ensure_rain_material(scene, role, spec):
    material_role = f"{role}_MATERIAL"
    material = _weather_material(scene, role)
    if (
        material is not None
        and material.get("cp77_weather_schema") == RAIN_MATERIAL_SCHEMA
    ):
        return material
    stale_material = material
    target_name = managed_name(scene, spec["material"])
    material = track_created_datablock(
        "materials",
        bpy.data.materials.new(target_name),
    )
    tag_owned(material, scene, material_role, base_name=spec["material"])
    cache_owned("materials", scene, material_role, material)
    material.use_nodes = True
    material["cp77_weather_schema"] = RAIN_MATERIAL_SCHEMA
    _set_transparent_surface(material)
    tree = material.node_tree
    tree.nodes.clear()

    seed = _rain_attribute(tree, SEED_ATTRIBUTE, "CP77 Rain Seed", (-1400, -200))
    seed_opacity = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        None,
        0.4,
        name="CP77 Rain Seed Opacity",
        location=(-1200, -300),
    ).node
    shader_nodes.socket_by_identifier(
        seed_opacity.inputs, "Value_002"
    ).default_value = 0.6
    tree.links.new(seed, seed_opacity.inputs["Value"])
    factors = [
        _rain_profile(tree, seed),
        _rain_distance_fade(tree, spec),
        seed_opacity.outputs["Value"],
    ]
    if spec["fade_over_fall"]:
        factors.append(_rain_fall_fade(tree))
    if spec["patches"]:
        factors.append(_rain_patches(tree))
    intensity = new_node(tree, "ShaderNodeValue", "CP77 Rain Intensity", (-600, -900))
    intensity.outputs["Value"].default_value = 0.0
    preview_scale = new_node(
        tree, "ShaderNodeValue", "CP77 Rain Preview Opacity", (-600, -1000)
    )
    preview_scale.outputs["Value"].default_value = float(spec["opacity"])
    factors.extend((intensity.outputs["Value"], preview_scale.outputs["Value"]))
    alpha = _multiply_sockets(tree, factors, "CP77 Rain Alpha", -400, -400)
    alpha = shader_nodes.clamp(
        tree.nodes,
        tree.links,
        alpha,
        name=f"{'CP77 Rain Alpha Clamp'} Clamp",
        location=(800, -400),
    )

    color = new_node(tree, "ShaderNodeRGB", "CP77 Rain Color", (400, 200))
    color.outputs["Color"].default_value = (0.72, 0.80, 1.0, 1.0)
    light = new_node(tree, "ShaderNodeRGB", "CP77 Rain Light", (400, 380))
    light.outputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    lit_color = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        name="CP77 Rain Lit Color",
        location=(600, 260),
    ).node
    tree.links.new(color.outputs["Color"], lit_color.inputs["Vector"])
    tree.links.new(
        light.outputs["Color"],
        shader_nodes.socket_by_identifier(lit_color.inputs, "Vector_001"),
    )
    _glow_surface(
        tree,
        lit_color.outputs["Vector"],
        alpha,
        float(spec["brightness"]),
        "CP77 Rain",
        (1100, 0),
    )
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


def ensure_weather_anchor(scene, collection):
    role = "WEATHER_ANCHOR"
    anchor = find_owned("objects", scene, role)
    if anchor is None:
        anchor = track_created_datablock(
            "objects",
            bpy.data.objects.new(managed_name(scene, WEATHER_ANCHOR_NAME), None),
        )
        tag_owned(anchor, scene, role, base_name=WEATHER_ANCHOR_NAME)
        cache_owned("objects", scene, role, anchor)
        collection.objects.link(anchor)
        if scene.camera is not None:
            anchor.location = scene.camera.matrix_world.translation
        else:
            anchor.location = scene.cursor.location
    elif collection.objects.get(anchor.name) is None:
        collection.objects.link(anchor)
    return anchor


def _ensure_rain_field(scene, collection, anchor, role, spec):
    material = _ensure_rain_material(scene, role, spec)
    obj = find_owned("objects", scene, role)
    if obj is None or obj.get("cp77_weather_rain_schema") != RAIN_OBJECT_SCHEMA:
        stale_obj = obj
        target_name = managed_name(scene, spec["object"])
        curves = track_created_datablock(
            "hair_curves",
            bpy.data.hair_curves.new(managed_name(scene, f"{spec['object']}_Curves")),
        )
        obj = track_created_datablock(
            "objects",
            bpy.data.objects.new(target_name, curves),
        )
        tag_owned(obj, scene, role, base_name=spec["object"])
        cache_owned("objects", scene, role, obj)
        collection.objects.link(obj)
        obj.parent = anchor
        obj.location = (0.0, 0.0, 0.0)
        obj.rotation_mode = "QUATERNION"
        obj["cp77_weather_rain_schema"] = RAIN_OBJECT_SCHEMA
        if hasattr(obj, "visible_shadow"):
            obj.visible_shadow = False
        modifier = obj.modifiers.new(RAIN_MODIFIER, "NODES")
        modifier.node_group = rain_streak_group(
            managed_name(scene, f"{spec['object']}_Streaks"), spec, material
        )
        if stale_obj is not None:
            retire_object(
                stale_obj,
                scene=scene,
                role=role,
                replacement=obj,
                replacement_name=target_name,
            )
    else:
        modifier = obj.modifiers.get(RAIN_MODIFIER)
        set_streak_material(getattr(modifier, "node_group", None), material)
    return obj


def center_weather_on_view(context):
    scene = context.scene
    collection = weather_collection(scene, create=True)
    anchor = ensure_weather_anchor(scene, collection)
    region_data = getattr(context, "region_data", None)
    area = getattr(context, "area", None)
    if area is not None and area.type == "VIEW_3D" and region_data is not None:
        anchor.location = region_data.view_matrix.inverted().translation
        return "VIEW_3D"
    if scene.camera is not None:
        anchor.location = scene.camera.matrix_world.translation
        return "SCENE_CAMERA"
    anchor.location = scene.cursor.location
    return "CURSOR"


def _rain_field_objects(scene):
    return tuple(
        obj
        for role, spec in RAIN_SPECS.items()
        for obj in (find_owned("objects", scene, role),)
        if obj is not None
    )


def ensure_weather_preview(scene, settings):
    collection = weather_collection(scene, create=True)
    created = {"clouds": 0, "rain": 0}
    if settings.preview_high_clouds:
        for role, spec in CLOUD_SPECS.items():
            if find_owned("objects", scene, role) is None:
                created["clouds"] += 1
            obj = _ensure_cloud_object(scene, collection, role, spec)
            _camera_follow(obj, scene, vertical=False)
    if settings.preview_rain:
        anchor = ensure_weather_anchor(scene, collection)
        for role, spec in RAIN_SPECS.items():
            existed = find_owned("objects", scene, role) is not None
            _ensure_rain_field(scene, collection, anchor, role, spec)
            if not existed:
                created["rain"] += 1
    return created


def _set_hidden(obj, hidden):
    hidden = bool(hidden)
    if obj.hide_render != hidden:
        obj.hide_render = hidden
    if obj.hide_viewport != hidden:
        obj.hide_viewport = hidden


def apply_weather_preview(scene, settings, sample, weather_sample):
    exposure = exposure_scale(settings.preview_exposure)
    day_factor = weather_preview.day_factor(sample)
    preview_light = weather_light(sample)
    cloud_visible = bool(settings.preview_high_clouds)
    for role, spec in CLOUD_SPECS.items():
        obj = find_owned("objects", scene, role)
        if obj is None:
            continue
        _camera_follow(obj, scene, vertical=False)
        _set_hidden(obj, not cloud_visible)
        material = _weather_material(scene, role)
        if material is None or not material.use_nodes:
            continue
        nodes = material.node_tree.nodes
        node = nodes.get("CP77 Cloud Day Factor")
        if node is not None:
            set_default_if_changed(node.outputs["Value"], day_factor)
        alpha = nodes.get("CP77 Cloud Preview Alpha")
        if alpha is not None:
            set_default_if_changed(
                alpha.outputs["Value"], 1.0 if cloud_visible else 0.0
            )
        light = nodes.get("CP77 Cloud Light")
        if light is not None:
            set_default_if_changed(light.outputs["Color"], preview_light)
        emission = nodes.get("CP77 Cloud Emission")
        if emission is not None:
            set_default_if_changed(emission.inputs["Strength"], exposure)

    anchor = find_owned("objects", scene, "WEATHER_ANCHOR")
    if (
        anchor is not None
        and settings.weather_follow_scene_camera
        and scene.camera is not None
    ):
        anchor.location = scene.camera.matrix_world.translation
    active = bool(
        settings.preview_rain
        and rain_effect_active(weather_sample)
        and anchor is not None
    )
    tint = rain_tint(sample, weather_sample)
    intensity = rain_intensity(active, weather_sample)
    for role, spec in RAIN_SPECS.items():
        obj = find_owned("objects", scene, role)
        if obj is not None:
            _set_hidden(obj, not active)
            quaternion = rain_flow(weather_sample, spec["wind_skew"])
            if obj.rotation_mode != "QUATERNION":
                obj.rotation_mode = "QUATERNION"
            assign_if_changed(obj, "rotation_quaternion", quaternion)
        material = _weather_material(scene, role)
        if material is None or not material.use_nodes:
            continue
        nodes = material.node_tree.nodes
        intensity_node = nodes.get("CP77 Rain Intensity")
        if intensity_node is not None:
            set_default_if_changed(intensity_node.outputs["Value"], intensity)
        color_node = nodes.get("CP77 Rain Color")
        if color_node is not None:
            set_default_if_changed(color_node.outputs["Color"], tint)
        light = nodes.get("CP77 Rain Light")
        if light is not None:
            set_default_if_changed(light.outputs["Color"], preview_light)
        emission = nodes.get("CP77 Rain Emission")
        if emission is not None:
            set_default_if_changed(
                emission.inputs["Strength"], float(spec["brightness"]) * exposure
            )


def weather_keyframe_targets(scene):
    """(owner, data path) pairs a bake keys on the high-cloud and rain previews"""
    targets = []
    for role, spec in CLOUD_SPECS.items():
        material = _weather_material(scene, role)
        if material is None or not material.use_nodes:
            continue
        nodes = material.node_tree.nodes
        for name, output in (
            ("CP77 Cloud Day Factor", "Value"),
            ("CP77 Cloud Preview Alpha", "Value"),
            ("CP77 Cloud Light", "Color"),
        ):
            node = nodes.get(name)
            if node is not None:
                targets.append((node.outputs[output], "default_value"))
        emission = nodes.get("CP77 Cloud Emission")
        if emission is not None:
            targets.append((emission.inputs["Strength"], "default_value"))
    for role, spec in RAIN_SPECS.items():
        obj = find_owned("objects", scene, role)
        if obj is not None:
            targets.append((obj, "rotation_quaternion"))
        material = _weather_material(scene, role)
        if material is None or not material.use_nodes:
            continue
        nodes = material.node_tree.nodes
        for name, output in (
            ("CP77 Rain Intensity", "Value"),
            ("CP77 Rain Color", "Color"),
            ("CP77 Rain Light", "Color"),
        ):
            node = nodes.get(name)
            if node is not None:
                targets.append((node.outputs[output], "default_value"))
        emission = nodes.get("CP77 Rain Emission")
        if emission is not None:
            targets.append((emission.inputs["Strength"], "default_value"))
    return tuple(targets)


def clear_weather_preview_animation(scene):
    for role, spec in CLOUD_SPECS.items():
        material = _weather_material(scene, role)
        if material is not None and material.use_nodes:
            material.node_tree.animation_data_clear()
    for role, spec in RAIN_SPECS.items():
        material = _weather_material(scene, role)
        if material is not None and material.use_nodes:
            material.node_tree.animation_data_clear()
    for obj in _rain_field_objects(scene):
        obj.animation_data_clear()
