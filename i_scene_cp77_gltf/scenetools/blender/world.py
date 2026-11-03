import math
from pathlib import Path

import bpy
from mathutils import Vector

from ...blender import shader_nodes
from ...blender.identity import rna_identity
from ...blender.shader_nodes import assign_if_changed, new_node, set_default_if_changed
from ...blender.transactions import track_created_datablock, track_mutation
from ...importers.common.light_environment import apply_environment_to_registered_lights
from ...importers.common.reflection_probe_registry import (
    mark_registered_reflection_probes_dirty,
)
from ..model.sky_preview import (
    directional_light,
    exposure_scale,
    global_light_state,
    gray_color,
    rgb_color,
    specular_source,
    world_values,
)
from ..model.weather import solve_weather
from ..runtime.ownership import (
    cache_owned,
    find_owned,
    keep_scene_world,
    managed_name,
    retire_datablock,
    root_collection,
    tag_owned,
)
from .clouds import apply_cloud_preview
from .fog import apply_fog_preview
from .images import load_named_image
from .weather import apply_weather_preview

WORLD_NAME = "CP77_Environment"
GLOBAL_LIGHT_NAME = "CP77_GlobalLight"
GLOBAL_SPECULAR_LIGHT_NAME = "CP77_GlobalSpecularLight"
WORLD_SCHEMA_VERSION = 5

NODE_VISIBLE_SKY = "CP77 Visible Atmosphere"
NODE_LIGHTING_SKY = "CP77 Lighting Atmosphere"
NODE_VISIBLE_TINT = "CP77 Visible Sky Tint"
NODE_VISIBLE_MAG = "CP77 Visible Sky Magnitude"
NODE_LIGHTING_TINT = "CP77 Lighting Sky Tint"
NODE_LIGHTING_MAG = "CP77 Lighting Sky Magnitude"
NODE_STAR_TEX = "CP77 Starmap"
NODE_STAR_CORNER = "CP77 Star Corner Scale"
NODE_STAR_EXP_BASE = "CP77 Star Exponent Base"
NODE_STAR_CONST = "CP77 Star Constellation"
NODE_STAR_EXP_FINAL = "CP77 Star Exponent"
NODE_STAR_SCALE = "CP77 Star Scale"
NODE_GALACTIC_ROWS = tuple(f"CP77 Galactic Matrix Row {index}" for index in range(3))
NODE_GALAXY_TEX = "CP77 Galaxy"
NODE_GALAXY_SCALE = "CP77 Galaxy Scale"
NODE_MOON_TEX = "CP77 Moon"
NODE_MOON_TINT = "CP77 Moon Tint"
NODE_MOON_MASK = "CP77 Moon Front Mask"
NODE_MOON_GLOW_POWER = "CP77 Moon Glow Power"
NODE_MOON_GLOW_SCALE = "CP77 Moon Glow Scale"
NODE_MOON_GLOW_TINT = "CP77 Moon Glow Tint"
NODE_MOON_DOT = "CP77 Moon Dot"
NODE_MOON_TANGENT_DOT = "CP77 Moon Tangent Dot"
NODE_MOON_BITANGENT_DOT = "CP77 Moon Bitangent Dot"
NODE_MOON_U_DIV = "CP77 Moon U Divide"
NODE_MOON_V_DIV = "CP77 Moon V Divide"
NODE_VISIBLE_BG = "CP77 Visible Background"
NODE_LIGHTING_BG = "CP77 Lighting Background"
NODE_PREVIEW_EXPOSURE = "CP77 Preview Exposure"
NODE_AMBIENT_OVERRIDE_ENABLE = "CP77 Ambient Override Enable"
NODE_AMBIENT_OVERRIDE_MIX = "CP77 Ambient Override Mix"


def _resource_path(name):
    return Path(__file__).resolve().parents[2] / "resources" / "scenetools" / name


def _load_image(name, colorspace=None):
    return load_named_image(
        _resource_path(name),
        f"CP77 SceneTools {name}",
        colorspace=colorspace,
        check_existing=True,
        required=False,
    )


def _mix_multiply(tree, name, a_socket, b_default, location):
    node = new_node(
        tree, "ShaderNodeMixRGB", name, location, strip_label_prefix="CP77 "
    )
    node.blend_type = "MULTIPLY"
    node.inputs["Factor"].default_value = 1.0
    tree.links.new(a_socket, node.inputs["Color1"])
    node.inputs["Color2"].default_value = b_default
    return node


def _vector_scale(tree, name, vector_socket, scale, location):
    node = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "SCALE",
        name=name,
        label=name.removeprefix("CP77 "),
        location=location,
    ).node
    tree.links.new(vector_socket, node.inputs["Vector"])
    node.inputs["Scale"].default_value = float(scale)
    return node


def _mix_add(tree, name, a_socket, b_socket, location):
    node = new_node(
        tree, "ShaderNodeMixRGB", name, location, strip_label_prefix="CP77 "
    )
    node.blend_type = "ADD"
    node.inputs["Factor"].default_value = 1.0
    tree.links.new(a_socket, node.inputs["Color1"])
    tree.links.new(b_socket, node.inputs["Color2"])
    return node


def _map_range(tree, name, location, to_min=0.0, to_max=1.0):
    node = new_node(
        tree, "ShaderNodeMapRange", name, location, strip_label_prefix="CP77 "
    )
    node.inputs["From Min"].default_value = 0.0
    node.inputs["From Max"].default_value = 1.0
    node.inputs["To Min"].default_value = float(to_min)
    node.inputs["To Max"].default_value = float(to_max)
    node.clamp = True
    return node


def _separate_color(tree, name, socket, location):
    node = new_node(
        tree, "ShaderNodeSeparateColor", name, location, strip_label_prefix="CP77 "
    )
    node.mode = "RGB"
    tree.links.new(socket, node.inputs["Color"])
    return node


def _separate_xyz(tree, name, socket, location):
    node = new_node(
        tree, "ShaderNodeSeparateXYZ", name, location, strip_label_prefix="CP77 "
    )
    tree.links.new(socket, node.inputs["Vector"])
    return node


def _build_sky_direction(tree, incoming_socket):
    outward = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "SCALE",
        name="CP77 Sky Outward Direction",
        label="Sky Outward Direction",
        location=(-1370, -260),
    ).node
    tree.links.new(incoming_socket, outward.inputs["Vector"])
    outward.inputs["Scale"].default_value = -1.0

    normalized = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "NORMALIZE",
        name="CP77 Sky Direction Normalized",
        label="Sky Direction Normalized",
        location=(-1170, -260),
    ).node
    tree.links.new(outward.outputs["Vector"], normalized.inputs["Vector"])
    return normalized.outputs["Vector"]


def _build_galactic_direction(tree, sky_direction):
    # Rows of the sky-to-galactic rotation; each sample sets them for its hour, latitude and sun rotation offset.
    rows = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    outputs = []
    y = -350
    for index, (name, row) in enumerate(zip(NODE_GALACTIC_ROWS, rows)):
        dot = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "DOT_PRODUCT",
            name=name,
            label=name.removeprefix("CP77 "),
            location=(-960, y - index * 100),
        ).node
        tree.links.new(sky_direction, dot.inputs["Vector"])
        shader_nodes.socket_by_identifier(dot.inputs, "Vector_001").default_value = row
        outputs.append(dot.outputs["Value"])

    combined = new_node(
        tree,
        "ShaderNodeCombineXYZ",
        "CP77 Galactic Direction",
        (-700, -450),
        strip_label_prefix="CP77 ",
    )
    for axis, output in zip("XYZ", outputs):
        tree.links.new(output, combined.inputs[axis])

    normalized = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "NORMALIZE",
        name="CP77 Galactic Direction Normalized",
        label="Galactic Direction Normalized",
        location=(-500, -450),
    ).node
    tree.links.new(combined.outputs["Vector"], normalized.inputs["Vector"])
    return normalized.outputs["Vector"]


def _build_star_nodes(tree, normal_socket):
    flip = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        name="CP77 Starmap Direction",
        label="Starmap Direction",
        location=(-1180, -500),
    ).node
    shader_nodes.socket_by_identifier(flip.inputs, "Vector_001").default_value = (
        1.0,
        1.0,
        -1.0,
    )
    tree.links.new(normal_socket, flip.inputs["Vector"])

    texture = new_node(
        tree,
        "ShaderNodeTexEnvironment",
        NODE_STAR_TEX,
        (-960, -500),
        strip_label_prefix="CP77 ",
    )
    texture.projection = "EQUIRECTANGULAR"
    texture.interpolation = "Linear"
    texture.image = _load_image("starmap_equirect_raw.png", "Non-Color")
    tree.links.new(flip.outputs["Vector"], texture.inputs["Vector"])

    channels = _separate_color(
        tree, "CP77 Starmap Channels", texture.outputs["Color"], (-740, -500)
    )

    absolute = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "ABSOLUTE",
        name="CP77 Direction Abs",
        label="Direction Abs",
        location=(-1160, -720),
    ).node
    tree.links.new(normal_socket, absolute.inputs["Vector"])
    xyz = _separate_xyz(
        tree, "CP77 Direction Components", absolute.outputs["Vector"], (-960, -720)
    )
    max_xy = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MAXIMUM",
        name="CP77 Corner Max XY",
        location=(-750, -750),
    ).node
    tree.links.new(xyz.outputs["X"], max_xy.inputs["Value"])
    tree.links.new(
        xyz.outputs["Y"], shader_nodes.socket_by_identifier(max_xy.inputs, "Value_001")
    )
    max_xyz = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MAXIMUM",
        name="CP77 Corner Max XYZ",
        location=(-570, -750),
    ).node
    tree.links.new(max_xy.outputs["Value"], max_xyz.inputs["Value"])
    tree.links.new(
        xyz.outputs["Z"], shader_nodes.socket_by_identifier(max_xyz.inputs, "Value_001")
    )

    corner = _map_range(tree, NODE_STAR_CORNER, (-390, -730), 1.25, 0.75)
    tree.links.new(max_xyz.outputs["Value"], corner.inputs["Value"])
    mask = shader_nodes.math(
        tree.nodes, tree.links, "MULTIPLY", name="CP77 Star Mask", location=(-180, -650)
    ).node
    tree.links.new(channels.outputs["Red"], mask.inputs["Value"])
    tree.links.new(
        corner.outputs["Result"],
        shader_nodes.socket_by_identifier(mask.inputs, "Value_001"),
    )

    base_exp = _map_range(tree, NODE_STAR_EXP_BASE, (-370, -500), 25.0, 10.5)
    tree.links.new(channels.outputs["Green"], base_exp.inputs["Value"])
    constellation = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        None,
        100.0,
        name=NODE_STAR_CONST,
        location=(-370, -380),
        use_clamp=True,
    ).node
    tree.links.new(channels.outputs["Blue"], constellation.inputs["Value"])
    final_exp = _map_range(tree, NODE_STAR_EXP_FINAL, (-150, -450), 25.0, 10.0)
    tree.links.new(constellation.outputs["Value"], final_exp.inputs["Value"])
    tree.links.new(base_exp.outputs["Result"], final_exp.inputs["To Min"])

    opacity = shader_nodes.math(
        tree.nodes, tree.links, "POWER", name="CP77 Star Opacity", location=(40, -560)
    ).node
    tree.links.new(mask.outputs["Value"], opacity.inputs["Value"])
    tree.links.new(
        final_exp.outputs["Result"],
        shader_nodes.socket_by_identifier(opacity.inputs, "Value_001"),
    )
    intensity = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        name="CP77 Star Intensity",
        location=(220, -520),
    ).node
    tree.links.new(channels.outputs["Green"], intensity.inputs["Value"])
    tree.links.new(
        opacity.outputs["Value"],
        shader_nodes.socket_by_identifier(intensity.inputs, "Value_001"),
    )
    scaled = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        None,
        5.0 * 10.0,
        name=NODE_STAR_SCALE,
        location=(400, -520),
    ).node
    tree.links.new(intensity.outputs["Value"], scaled.inputs["Value"])

    gray = new_node(
        tree,
        "ShaderNodeCombineXYZ",
        "CP77 Star Color",
        (570, -520),
        strip_label_prefix="CP77 ",
    )
    for axis in "XYZ":
        tree.links.new(scaled.outputs["Value"], gray.inputs[axis])
    return gray.outputs["Vector"]


def _build_galaxy_nodes(tree, normal_socket):
    xyz = _separate_xyz(tree, "CP77 Galaxy Direction", normal_socket, (-1160, -950))
    atan = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ARCTAN2",
        name="CP77 Galaxy Longitude",
        location=(-960, -980),
    ).node
    tree.links.new(xyz.outputs["X"], atan.inputs["Value"])
    tree.links.new(
        xyz.outputs["Y"], shader_nodes.socket_by_identifier(atan.inputs, "Value_001")
    )
    lon_div = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        None,
        math.tau,
        name="CP77 Galaxy Longitude Scale",
        location=(-780, -980),
    ).node
    tree.links.new(atan.outputs["Value"], lon_div.inputs["Value"])
    lon_frac = shader_nodes.math(
        tree.nodes,
        tree.links,
        "FRACT",
        name="CP77 Galaxy Longitude Frac",
        location=(-600, -980),
    ).node
    tree.links.new(lon_div.outputs["Value"], lon_frac.inputs["Value"])

    acos = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ARCCOSINE",
        name="CP77 Galaxy Inclination",
        location=(-960, -1080),
    ).node
    tree.links.new(xyz.outputs["Z"], acos.inputs["Value"])
    lat_div = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        None,
        1.5,
        name="CP77 Galaxy Latitude Scale",
        location=(-780, -1080),
    ).node
    tree.links.new(acos.outputs["Value"], lat_div.inputs["Value"])
    lat_sub = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        1.55,
        name="CP77 Galaxy Latitude",
        location=(-600, -1080),
        use_clamp=True,
    ).node
    tree.links.new(
        lat_div.outputs["Value"],
        shader_nodes.socket_by_identifier(lat_sub.inputs, "Value_001"),
    )
    lat_frac = shader_nodes.math(
        tree.nodes,
        tree.links,
        "FRACT",
        name="CP77 Galaxy Latitude Frac",
        location=(-430, -1080),
    ).node
    tree.links.new(lat_sub.outputs["Value"], lat_frac.inputs["Value"])

    uv = new_node(
        tree,
        "ShaderNodeCombineXYZ",
        "CP77 Galaxy UV",
        (-260, -1030),
        strip_label_prefix="CP77 ",
    )
    tree.links.new(lon_frac.outputs["Value"], uv.inputs["X"])
    tree.links.new(lat_frac.outputs["Value"], uv.inputs["Y"])

    texture = new_node(
        tree,
        "ShaderNodeTexImage",
        NODE_GALAXY_TEX,
        (-70, -1010),
        strip_label_prefix="CP77 ",
    )
    texture.extension = "REPEAT"
    texture.interpolation = "Linear"
    texture.image = _load_image("galaxy_equirect.png")
    tree.links.new(uv.outputs["Vector"], texture.inputs["Vector"])

    scale = _vector_scale(
        tree, NODE_GALAXY_SCALE, texture.outputs["Color"], 0.3, (150, -1010)
    )
    return scale.outputs["Vector"]


def _build_moon_nodes(tree, normal_socket):
    dot = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "DOT_PRODUCT",
        name=NODE_MOON_DOT,
        label=NODE_MOON_DOT.removeprefix("CP77 "),
        location=(-1120, -1260),
    ).node
    shader_nodes.socket_by_identifier(dot.inputs, "Vector_001").default_value = (
        0.0,
        0.0,
        1.0,
    )
    tree.links.new(normal_socket, dot.inputs["Vector"])

    tangent_dot = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "DOT_PRODUCT",
        name=NODE_MOON_TANGENT_DOT,
        label=NODE_MOON_TANGENT_DOT.removeprefix("CP77 "),
        location=(-1120, -1370),
    ).node
    shader_nodes.socket_by_identifier(
        tangent_dot.inputs, "Vector_001"
    ).default_value = (1.0, 0.0, 0.0)
    tree.links.new(normal_socket, tangent_dot.inputs["Vector"])
    bitangent_dot = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "DOT_PRODUCT",
        name=NODE_MOON_BITANGENT_DOT,
        label=NODE_MOON_BITANGENT_DOT.removeprefix("CP77 "),
        location=(-1120, -1470),
    ).node
    shader_nodes.socket_by_identifier(
        bitangent_dot.inputs, "Vector_001"
    ).default_value = (0.0, 1.0, 0.0)
    tree.links.new(normal_socket, bitangent_dot.inputs["Vector"])

    u_div = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        None,
        0.02,
        name=NODE_MOON_U_DIV,
        location=(-900, -1370),
    ).node
    tree.links.new(tangent_dot.outputs["Value"], u_div.inputs["Value"])
    u_add = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        None,
        0.5,
        name="CP77 Moon U",
        location=(-720, -1370),
    ).node
    tree.links.new(u_div.outputs["Value"], u_add.inputs["Value"])
    v_div = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        None,
        0.02,
        name=NODE_MOON_V_DIV,
        location=(-900, -1470),
    ).node
    tree.links.new(bitangent_dot.outputs["Value"], v_div.inputs["Value"])
    v_add = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        None,
        0.5,
        name="CP77 Moon V",
        location=(-720, -1470),
    ).node
    tree.links.new(v_div.outputs["Value"], v_add.inputs["Value"])
    uv = new_node(
        tree,
        "ShaderNodeCombineXYZ",
        "CP77 Moon UV",
        (-530, -1410),
        strip_label_prefix="CP77 ",
    )
    tree.links.new(u_add.outputs["Value"], uv.inputs["X"])
    tree.links.new(v_add.outputs["Value"], uv.inputs["Y"])

    texture = new_node(
        tree,
        "ShaderNodeTexImage",
        NODE_MOON_TEX,
        (-340, -1390),
        strip_label_prefix="CP77 ",
    )
    texture.extension = "CLIP"
    texture.interpolation = "Linear"
    texture.image = _load_image("moon_disc.png")
    tree.links.new(uv.outputs["Vector"], texture.inputs["Vector"])

    tint = _mix_multiply(
        tree,
        NODE_MOON_TINT,
        texture.outputs["Color"],
        rgb_color((0.0, 0.0, 0.0)),
        (-100, -1390),
    )
    front = shader_nodes.math(
        tree.nodes,
        tree.links,
        "GREATER_THAN",
        None,
        0.0,
        name=NODE_MOON_MASK,
        location=(-870, -1260),
    ).node
    tree.links.new(dot.outputs["Value"], front.inputs["Value"])
    masked = _mix_multiply(
        tree, "CP77 Moon Masked", tint.outputs["Color"], gray_color(1.0), (100, -1390)
    )
    gray = masked.inputs["Color2"]
    tree.links.new(front.outputs["Value"], gray)

    positive = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MAXIMUM",
        None,
        0.0,
        name="CP77 Moon Glow Dot",
        location=(-680, -1240),
    ).node
    tree.links.new(dot.outputs["Value"], positive.inputs["Value"])
    glow_power = shader_nodes.math(
        tree.nodes,
        tree.links,
        "POWER",
        None,
        10.0,
        name=NODE_MOON_GLOW_POWER,
        location=(-500, -1240),
    ).node
    tree.links.new(positive.outputs["Value"], glow_power.inputs["Value"])
    glow_scale = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        None,
        0.05,
        name=NODE_MOON_GLOW_SCALE,
        location=(-320, -1240),
    ).node
    tree.links.new(glow_power.outputs["Value"], glow_scale.inputs["Value"])
    glow_gray = new_node(
        tree,
        "ShaderNodeCombineXYZ",
        "CP77 Moon Glow Gray",
        (-140, -1240),
        strip_label_prefix="CP77 ",
    )
    for axis in "XYZ":
        tree.links.new(glow_scale.outputs["Value"], glow_gray.inputs[axis])
    glow_tint = _mix_multiply(
        tree,
        NODE_MOON_GLOW_TINT,
        glow_gray.outputs["Vector"],
        rgb_color((1.0, 1.0, 1.0)),
        (60, -1240),
    )

    moon = _mix_add(
        tree,
        "CP77 Moon Composite",
        masked.outputs["Color"],
        glow_tint.outputs["Color"],
        (300, -1320),
    )
    return moon.outputs["Color"]


def _build_ambient_override(tree, direction_socket, base_lighting_socket):
    components = _separate_xyz(
        tree, "CP77 Ambient Direction", direction_socket, (250, -210)
    )
    face_weights = []
    for axis, output in enumerate(components.outputs[name] for name in "XYZ"):
        positive = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MAXIMUM",
            None,
            0.0,
            name=f"CP77 Ambient +{axis}",
            location=(450, -160 - axis * 150),
        ).node
        tree.links.new(output, positive.inputs["Value"])
        positive_square = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            name=f"CP77 Ambient +{axis} Squared",
            location=(640, -160 - axis * 150),
        ).node
        tree.links.new(positive.outputs["Value"], positive_square.inputs["Value"])
        tree.links.new(
            positive.outputs["Value"],
            shader_nodes.socket_by_identifier(positive_square.inputs, "Value_001"),
        )
        negative_value = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            None,
            -1.0,
            name=f"CP77 Ambient -{axis} Negate",
            location=(450, -235 - axis * 150),
        ).node
        tree.links.new(output, negative_value.inputs["Value"])
        negative = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MAXIMUM",
            None,
            0.0,
            name=f"CP77 Ambient -{axis}",
            location=(640, -235 - axis * 150),
        ).node
        tree.links.new(negative_value.outputs["Value"], negative.inputs["Value"])
        negative_square = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MULTIPLY",
            name=f"CP77 Ambient -{axis} Squared",
            location=(830, -235 - axis * 150),
        ).node
        tree.links.new(negative.outputs["Value"], negative_square.inputs["Value"])
        tree.links.new(
            negative.outputs["Value"],
            shader_nodes.socket_by_identifier(negative_square.inputs, "Value_001"),
        )
        face_weights.extend(
            (positive_square.outputs["Value"], negative_square.outputs["Value"])
        )

    weighted = []
    for index, weight in enumerate(face_weights):
        color = new_node(
            tree,
            "ShaderNodeRGB",
            f"CP77 Ambient Face {index}",
            (850, -700 - index * 85),
            strip_label_prefix="CP77 ",
        )
        color.outputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
        scale = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "SCALE",
            name=f"CP77 Ambient Face {index} Weight",
            label=f"Ambient Face {index} Weight",
            location=(1070, -700 - index * 85),
        ).node
        tree.links.new(color.outputs["Color"], scale.inputs["Vector"])
        tree.links.new(weight, scale.inputs["Scale"])
        weighted.append(scale.outputs["Vector"])

    ambient = weighted[0]
    for index, value in enumerate(weighted[1:], start=1):
        add = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "ADD",
            name=f"CP77 Ambient Sum {index}",
            label=f"Ambient Sum {index}",
            location=(1280 + index * 120, -650),
        ).node
        tree.links.new(ambient, add.inputs["Vector"])
        tree.links.new(
            value, shader_nodes.socket_by_identifier(add.inputs, "Vector_001")
        )
        ambient = add.outputs["Vector"]

    enabled = new_node(
        tree,
        "ShaderNodeValue",
        NODE_AMBIENT_OVERRIDE_ENABLE,
        (1250, -250),
        strip_label_prefix="CP77 ",
    )
    enabled.outputs["Value"].default_value = 0.0
    mix = new_node(
        tree,
        "ShaderNodeMixRGB",
        NODE_AMBIENT_OVERRIDE_MIX,
        (1500, -40),
        strip_label_prefix="CP77 ",
    )
    mix.blend_type = "MIX"
    tree.links.new(enabled.outputs["Value"], mix.inputs["Factor"])
    tree.links.new(base_lighting_socket, mix.inputs["Color1"])
    tree.links.new(ambient, mix.inputs["Color2"])
    return mix.outputs["Color"]


def build_world(world):
    world.use_nodes = True
    tree = world.node_tree
    tree.nodes.clear()

    geometry = new_node(
        tree,
        "ShaderNodeNewGeometry",
        "CP77 Sky Geometry",
        (-1580, -120),
        strip_label_prefix="CP77 ",
    )
    incoming = geometry.outputs.get("Incoming") or geometry.outputs["Position"]
    sky_direction = _build_sky_direction(tree, incoming)
    galactic_direction = _build_galactic_direction(tree, sky_direction)

    visible_sky = new_node(
        tree,
        "ShaderNodeTexSky",
        NODE_VISIBLE_SKY,
        (-1160, 240),
        strip_label_prefix="CP77 ",
    )
    visible_sky.sky_type = "HOSEK_WILKIE"
    visible_sky.sun_disc = False
    lighting_sky = new_node(
        tree,
        "ShaderNodeTexSky",
        NODE_LIGHTING_SKY,
        (-1160, 40),
        strip_label_prefix="CP77 ",
    )
    lighting_sky.sky_type = "HOSEK_WILKIE"
    lighting_sky.sun_disc = False

    visible_tint = _mix_multiply(
        tree,
        NODE_VISIBLE_TINT,
        visible_sky.outputs["Color"],
        rgb_color((1.0, 1.0, 1.0)),
        (-900, 240),
    )
    visible_mag = _mix_multiply(
        tree,
        NODE_VISIBLE_MAG,
        visible_tint.outputs["Color"],
        gray_color(1.0),
        (-680, 240),
    )
    lighting_tint = _mix_multiply(
        tree,
        NODE_LIGHTING_TINT,
        lighting_sky.outputs["Color"],
        rgb_color((1.0, 1.0, 1.0)),
        (-900, 40),
    )
    lighting_mag = _mix_multiply(
        tree,
        NODE_LIGHTING_MAG,
        lighting_tint.outputs["Color"],
        gray_color(1.0),
        (-680, 40),
    )

    stars = _build_star_nodes(tree, galactic_direction)
    galaxy = _build_galaxy_nodes(tree, galactic_direction)
    moon = _build_moon_nodes(tree, sky_direction)
    night_a = _mix_add(tree, "CP77 Stars + Galaxy", stars, galaxy, (650, -680))
    night_b = _mix_add(
        tree, "CP77 Night Sky", night_a.outputs["Color"], moon, (850, -520)
    )
    visible = _mix_add(
        tree,
        "CP77 Visible Composite",
        visible_mag.outputs["Color"],
        night_b.outputs["Color"],
        (1030, 170),
    )

    exposure = new_node(
        tree,
        "ShaderNodeValue",
        NODE_PREVIEW_EXPOSURE,
        (820, 400),
        strip_label_prefix="CP77 ",
    )
    exposure.outputs["Value"].default_value = 1.0

    visible_bg = new_node(
        tree,
        "ShaderNodeBackground",
        NODE_VISIBLE_BG,
        (1250, 160),
        strip_label_prefix="CP77 ",
    )
    tree.links.new(visible.outputs["Color"], visible_bg.inputs["Color"])
    tree.links.new(exposure.outputs["Value"], visible_bg.inputs["Strength"])
    ambient_or_lighting = _build_ambient_override(
        tree, sky_direction, lighting_mag.outputs["Color"]
    )
    lighting_bg = new_node(
        tree,
        "ShaderNodeBackground",
        NODE_LIGHTING_BG,
        (1780, -40),
        strip_label_prefix="CP77 ",
    )
    tree.links.new(ambient_or_lighting, lighting_bg.inputs["Color"])
    tree.links.new(exposure.outputs["Value"], lighting_bg.inputs["Strength"])

    light_path = new_node(
        tree,
        "ShaderNodeLightPath",
        "CP77 Camera Ray",
        (1260, -100),
        strip_label_prefix="CP77 ",
    )
    mix = new_node(
        tree,
        "ShaderNodeMixShader",
        "CP77 Visible / Lighting",
        (2000, 80),
        strip_label_prefix="CP77 ",
    )
    tree.links.new(light_path.outputs["Is Camera Ray"], mix.inputs["Factor"])
    tree.links.new(lighting_bg.outputs["Background"], mix.inputs["Shader"])
    tree.links.new(
        visible_bg.outputs["Background"],
        shader_nodes.socket_by_identifier(mix.inputs, "Shader_001"),
    )
    output = new_node(
        tree,
        "ShaderNodeOutputWorld",
        "CP77 World Output",
        (2200, 80),
        strip_label_prefix="CP77 ",
    )
    tree.links.new(mix.outputs["Shader"], output.inputs["Surface"])
    world["cp77_world_schema_version"] = WORLD_SCHEMA_VERSION
    return world


def ensure_world(scene):
    world = find_owned("worlds", scene, "WORLD")
    stale_world = None
    rebuild = world is None
    if world is not None:
        rebuild = (
            not world.use_nodes
            or NODE_VISIBLE_SKY not in world.node_tree.nodes
            or int(world.get("cp77_world_schema_version", 0)) != WORLD_SCHEMA_VERSION
        )
        if rebuild:
            stale_world = world

    if rebuild:
        target_name = managed_name(scene, WORLD_NAME)
        world = track_created_datablock(
            "worlds",
            bpy.data.worlds.new(target_name),
        )
        tag_owned(world, scene, "WORLD", base_name=WORLD_NAME)
        cache_owned("worlds", scene, "WORLD", world)
        build_world(world)

    if scene.world is not world:
        previous_world = scene.world
        track_mutation(
            ("scenetools", str(rna_identity(scene)), "world"),
            lambda scene=scene, previous_world=previous_world: setattr(
                scene,
                "world",
                previous_world,
            ),
            verify=lambda scene=scene, previous_world=previous_world: (
                scene.world is previous_world
            ),
            label="SceneTools scene world assignment",
        )
        keep_scene_world(scene, previous_world)
        scene.world = world

    if stale_world is not None:
        retire_datablock(
            "worlds",
            stale_world,
            scene=scene,
            role="WORLD",
            replacement=world,
            replacement_name=target_name,
        )
    return world


def _ensure_sun(scene, name, role):
    obj = find_owned("objects", scene, role)
    target = root_collection(scene, create=True)
    if (
        obj is not None
        and obj.type == "LIGHT"
        and obj.data is not None
        and obj.data.type == "SUN"
    ):
        if target.objects.get(obj.name) is not obj:
            target.objects.link(obj)
        if scene.collection.objects.get(obj.name) is obj:
            scene.collection.objects.unlink(obj)
        return obj
    light_role = f"{role}_DATA"
    light = find_owned("lights", scene, light_role)
    if light is None or light.type != "SUN":
        light = track_created_datablock(
            "lights",
            bpy.data.lights.new(managed_name(scene, name), "SUN"),
        )
        tag_owned(light, scene, light_role, base_name=name)
        cache_owned("lights", scene, light_role, light)
    obj = track_created_datablock(
        "objects",
        bpy.data.objects.new(managed_name(scene, name), light),
    )
    tag_owned(obj, scene, role, base_name=name)
    cache_owned("objects", scene, role, obj)
    target.objects.link(obj)
    if scene.collection.objects.get(obj.name) is obj:
        scene.collection.objects.unlink(obj)
    return obj


def ensure_global_light(scene):
    obj = _ensure_sun(scene, GLOBAL_LIGHT_NAME, "GLOBAL_LIGHT")
    if hasattr(obj.data, "diffuse_factor"):
        obj.data.diffuse_factor = 1.0
    if hasattr(obj.data, "specular_factor"):
        obj.data.specular_factor = 0.0
    return obj


def ensure_global_specular_light(scene):
    obj = _ensure_sun(scene, GLOBAL_SPECULAR_LIGHT_NAME, "GLOBAL_SPECULAR_LIGHT")
    if hasattr(obj.data, "diffuse_factor"):
        obj.data.diffuse_factor = 0.0
    if hasattr(obj.data, "specular_factor"):
        obj.data.specular_factor = 1.0
    if hasattr(obj.data, "volume_factor"):
        obj.data.volume_factor = 0.0
    if hasattr(obj.data, "transmission_factor"):
        obj.data.transmission_factor = 0.0
    return obj


def _orientation(direction):
    return Vector(direction).normalized().to_track_quat("Z", "Y").to_matrix().to_4x4()


def _apply_directional(light_obj, orientation, angle, values):
    light_obj.matrix_world = orientation
    data = light_obj.data
    assign_if_changed(data, "angle", angle)
    assign_if_changed(data, "color", values.color)
    assign_if_changed(data, "energy", values.energy)


def _apply_world_values(world, values):
    nodes = world.node_tree.nodes
    visible_sky = nodes.get(NODE_VISIBLE_SKY)
    lighting_sky = nodes.get(NODE_LIGHTING_SKY)
    if visible_sky is None or lighting_sky is None:
        build_world(world)
        nodes = world.node_tree.nodes
        visible_sky = nodes[NODE_VISIBLE_SKY]
        lighting_sky = nodes[NODE_LIGHTING_SKY]

    for sky, turbidity in (
        (visible_sky, values.turbidity),
        (lighting_sky, values.lut_turbidity),
    ):
        assign_if_changed(sky, "turbidity", turbidity)
        assign_if_changed(sky, "ground_albedo", values.ground_albedo)
        assign_if_changed(sky, "sun_direction", values.sun_direction)

    set_default_if_changed(
        nodes[NODE_VISIBLE_TINT].inputs["Color2"], values.visible_tint
    )
    set_default_if_changed(
        nodes[NODE_VISIBLE_MAG].inputs["Color2"], values.visible_magnitude
    )
    set_default_if_changed(
        nodes[NODE_LIGHTING_TINT].inputs["Color2"], values.lighting_tint
    )
    set_default_if_changed(
        nodes[NODE_LIGHTING_MAG].inputs["Color2"], values.lighting_magnitude
    )

    corner = nodes[NODE_STAR_CORNER]
    set_default_if_changed(corner.inputs["To Min"], values.star_corner_near)
    set_default_if_changed(corner.inputs["To Max"], values.star_corner_far)
    base_exp = nodes[NODE_STAR_EXP_BASE]
    set_default_if_changed(base_exp.inputs["To Min"], values.star_dim_scale)
    set_default_if_changed(base_exp.inputs["To Max"], values.star_bright_scale)
    set_default_if_changed(
        nodes[NODE_STAR_EXP_FINAL].inputs["To Max"], values.star_constellation_scale
    )
    set_default_if_changed(
        shader_nodes.socket_by_identifier(nodes[NODE_STAR_SCALE].inputs, "Value_001"),
        values.star_scale,
    )
    for name, row in zip(NODE_GALACTIC_ROWS, values.galactic_rows):
        node = nodes.get(name)
        if node is not None:
            set_default_if_changed(
                shader_nodes.socket_by_identifier(node.inputs, "Vector_001"), row
            )
    galaxy = nodes[NODE_GALAXY_SCALE]
    set_default_if_changed(galaxy.inputs["Scale"], values.galaxy_scale)

    set_default_if_changed(nodes[NODE_MOON_TINT].inputs["Color2"], values.moon_tint)
    set_default_if_changed(
        shader_nodes.socket_by_identifier(nodes[NODE_MOON_DOT].inputs, "Vector_001"),
        values.moon_direction,
    )
    set_default_if_changed(
        shader_nodes.socket_by_identifier(
            nodes[NODE_MOON_TANGENT_DOT].inputs, "Vector_001"
        ),
        values.moon_tangent,
    )
    set_default_if_changed(
        shader_nodes.socket_by_identifier(
            nodes[NODE_MOON_BITANGENT_DOT].inputs, "Vector_001"
        ),
        values.moon_bitangent,
    )
    set_default_if_changed(
        shader_nodes.socket_by_identifier(nodes[NODE_MOON_U_DIV].inputs, "Value_001"),
        values.moon_diameter_scale,
    )
    set_default_if_changed(
        shader_nodes.socket_by_identifier(nodes[NODE_MOON_V_DIV].inputs, "Value_001"),
        values.moon_diameter_scale,
    )
    set_default_if_changed(
        shader_nodes.socket_by_identifier(
            nodes[NODE_MOON_GLOW_POWER].inputs, "Value_001"
        ),
        values.moon_glow_power,
    )
    set_default_if_changed(
        shader_nodes.socket_by_identifier(
            nodes[NODE_MOON_GLOW_SCALE].inputs, "Value_001"
        ),
        values.moon_glow_scale,
    )
    glow_tint = nodes.get(NODE_MOON_GLOW_TINT)
    if glow_tint is not None:
        set_default_if_changed(glow_tint.inputs["Color2"], values.moon_glow_tint)

    ambient_enable = nodes.get(NODE_AMBIENT_OVERRIDE_ENABLE)
    if ambient_enable is not None:
        set_default_if_changed(ambient_enable.outputs["Value"], values.ambient_enabled)
    for index, rgba in enumerate(values.ambient_faces):
        face = nodes.get(f"CP77 Ambient Face {index}")
        if face is not None:
            set_default_if_changed(face.outputs["Color"], rgba)

    set_default_if_changed(
        nodes[NODE_PREVIEW_EXPOSURE].outputs["Value"], values.exposure
    )


def apply_sample(
    scene,
    settings,
    sample,
    *,
    update_world=True,
    update_global_lights=True,
    update_weather_preview=True,
    update_cloud_preview=True,
    update_fog_preview=True,
    sync_registered=True,
):
    exposure = exposure_scale(settings.preview_exposure)
    weather_sample = solve_weather(sample.hour, sample.weather)
    world = None
    global_light = None
    specular_light = None
    if update_world:
        world = (
            ensure_world(scene)
            if settings.create_world
            else find_owned("worlds", scene, "WORLD")
        )
    if update_global_lights:
        global_light = (
            ensure_global_light(scene)
            if settings.create_global_light
            else find_owned("objects", scene, "GLOBAL_LIGHT")
        )
        specular_light = (
            ensure_global_specular_light(scene)
            if settings.create_global_light
            else find_owned("objects", scene, "GLOBAL_SPECULAR_LIGHT")
        )
        light = global_light_state(sample, weather_sample)
        orientation = _orientation(light.direction)
        if global_light is not None and global_light.type == "LIGHT":
            _apply_directional(
                global_light,
                orientation,
                light.angle,
                directional_light(light.source_rgb, exposure),
            )
            fog_light_scale = max(0.0, float(weather_sample.fog.global_light_scale))
            if hasattr(global_light.data, "volume_factor"):
                assign_if_changed(global_light.data, "volume_factor", fog_light_scale)

        if specular_light is not None and specular_light.type == "LIGHT":
            _apply_directional(
                specular_light,
                orientation,
                light.angle,
                directional_light(specular_source(light, sample), exposure),
            )

    if sync_registered:
        apply_environment_to_registered_lights(scene, sample, weather_sample)
    if update_weather_preview:
        apply_weather_preview(scene, settings, sample, weather_sample)
    if update_cloud_preview:
        apply_cloud_preview(scene, settings, sample, weather_sample)
    if update_fog_preview:
        apply_fog_preview(scene, settings, sample, weather_sample)

    if update_world and world is not None and world.use_nodes:
        _apply_world_values(world, world_values(sample, weather_sample, exposure))
    if sync_registered:
        mark_registered_reflection_probes_dirty(scene)


def world_keyframe_targets(world):
    """(owner, data path) pairs a bake keys on the preview world, in a stable order"""
    if world is None or not world.use_nodes:
        return ()
    nodes = world.node_tree.nodes
    targets = []
    for name in (
        NODE_VISIBLE_TINT,
        NODE_VISIBLE_MAG,
        NODE_LIGHTING_TINT,
        NODE_LIGHTING_MAG,
        NODE_MOON_TINT,
        NODE_MOON_GLOW_TINT,
    ):
        node = nodes.get(name)
        if node is not None:
            targets.append((node.inputs["Color2"], "default_value"))
    galaxy = nodes.get(NODE_GALAXY_SCALE)
    if galaxy is not None:
        targets.append((galaxy.inputs["Scale"], "default_value"))
    # The second operand of each Math and Vector Math node.
    for names, identifier in (
        (
            (
                NODE_STAR_SCALE,
                NODE_MOON_GLOW_POWER,
                NODE_MOON_GLOW_SCALE,
                NODE_MOON_U_DIV,
                NODE_MOON_V_DIV,
            ),
            "Value_001",
        ),
        (
            (
                NODE_MOON_DOT,
                NODE_MOON_TANGENT_DOT,
                NODE_MOON_BITANGENT_DOT,
                *NODE_GALACTIC_ROWS,
            ),
            "Vector_001",
        ),
    ):
        for name in names:
            node = nodes.get(name)
            if node is not None:
                targets.append(
                    (
                        shader_nodes.socket_by_identifier(node.inputs, identifier),
                        "default_value",
                    )
                )
    for name, sockets in (
        (NODE_STAR_CORNER, ("To Min", "To Max")),
        (NODE_STAR_EXP_BASE, ("To Min", "To Max")),
        (NODE_STAR_EXP_FINAL, ("To Max",)),
    ):
        node = nodes.get(name)
        if node is not None:
            targets.extend((node.inputs[socket], "default_value") for socket in sockets)
    for names, output in (
        ((NODE_PREVIEW_EXPOSURE, NODE_AMBIENT_OVERRIDE_ENABLE), "Value"),
        (tuple(f"CP77 Ambient Face {index}" for index in range(6)), "Color"),
    ):
        for name in names:
            node = nodes.get(name)
            if node is not None:
                targets.append((node.outputs[output], "default_value"))
    for name in (NODE_VISIBLE_SKY, NODE_LIGHTING_SKY):
        node = nodes.get(name)
        if node is not None:
            targets.extend(
                (node, path) for path in ("turbidity", "ground_albedo", "sun_direction")
            )
    return tuple(targets)


def global_light_keyframe_targets(light_objects):
    targets = []
    for light_obj in light_objects:
        if light_obj is None or light_obj.type != "LIGHT":
            continue
        targets.append((light_obj, "rotation_euler"))
        targets.extend((light_obj.data, path) for path in ("color", "energy", "angle"))
    return tuple(targets)


def clear_world_animation(world):
    if world is None or not world.use_nodes:
        return
    world.node_tree.animation_data_clear()
