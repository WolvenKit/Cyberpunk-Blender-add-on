from __future__ import annotations

from pathlib import Path

import bpy

from ...blender import shader_nodes
from ...blender.shader_nodes import (
    new_node,
    rgb_node,
    set_color_output,
    set_value_output,
    value_node,
)
from ...blender.transactions import track_created_datablock
from ..model.volume_preview import (
    CLOUD_BASE_NOISE_WORLD_SCALE,
    CLOUD_COVERAGE_WORLD_SCALE,
    CLOUD_DETAIL_NOISE_WORLD_SCALE,
    CLOUD_PREVIEW_SIZE,
    CLOUD_WORLD_SIZE,
    cloud_preview,
)
from ..runtime.ownership import (
    cache_owned,
    find_owned,
    managed_name,
    retire_datablock,
    retire_object,
    tag_owned,
)
from .images import load_named_image
from .meshes import cube_mesh
from .weather import ensure_weather_anchor, weather_collection

CLOUD_VOLUME_OBJECT = "CP77_VolumetricCloudPreview"
CLOUD_VOLUME_MATERIAL = "CP77_Weather_VolumetricClouds"
CLOUD_TEXTURE_SPACE = "CP77_CloudTextureSpace"
_CLOUD_ROLE = "VOLUMETRIC_CLOUDS"
_MATERIAL_ROLE = "VOLUMETRIC_CLOUD_MATERIAL"
# Schema 3 cubes face outward, as Cycles needs to render a volume inside its mesh; schema 2 and
# older objects are rebuilt by the next setup or refresh.
CLOUD_OBJECT_SCHEMA_VERSION = 3
# Schema 3 is the compact graph (same density model, about half the nodes); schema 2 and
# older materials are rebuilt by the next setup or refresh.
CLOUD_MATERIAL_SCHEMA_VERSION = 3
CLOUD_NOISE_TILES = 8.0
CLOUD_NOISE_FRAMES = 64.0
CLOUD_NOISE_TILE_PIXELS = 128.0
CLOUD_NOISE_TILE_EDGE_SCALE = (CLOUD_NOISE_TILE_PIXELS - 2.0) / CLOUD_NOISE_TILE_PIXELS
CLOUD_NOISE_TILE_CENTER = 1.0 / CLOUD_NOISE_TILE_PIXELS
RESOURCE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "resources"
    / "scenetools"
    / "weather"
    / "clouds"
)


def _safe_ratio(tree, numerator, denominator, name, location, minimum=1.0e-4):
    safe = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MAXIMUM",
        denominator,
        minimum,
        name=f"{name} Denominator",
        location=location,
    )
    return shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        numerator,
        safe,
        name=name,
        location=(location[0] + 160, location[1]),
        use_clamp=True,
    )


def _load_image(filename):
    return load_named_image(
        RESOURCE_ROOT / filename,
        f"CP77 Weather {filename}",
        colorspace="Non-Color",
    )


def _ensure_texture_space(scene, collection):
    role = "CLOUD_TEXTURE_SPACE"
    obj = find_owned("objects", scene, role)
    if obj is None:
        obj = track_created_datablock(
            "objects",
            bpy.data.objects.new(managed_name(scene, CLOUD_TEXTURE_SPACE), None),
        )
        tag_owned(obj, scene, role, base_name=CLOUD_TEXTURE_SPACE)
        cache_owned("objects", scene, role, obj)
        collection.objects.link(obj)
        obj.location = (0.0, 0.0, 0.0)
        obj.rotation_euler = (0.0, 0.0, 0.0)
        obj.scale = (1.0, 1.0, 1.0)
    elif collection.objects.get(obj.name) is None:
        collection.objects.link(obj)
    return obj


def _sample_atlas(tree, coords, image, prefix, x, y, *, with_alpha=True):
    """Trilinear lookup in the 8x8 slice atlas"""
    uvw = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "FRACTION",
        coords,
        name=f"{prefix} UVW",
        location=(x, y),
    )
    tile_uv = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        uvw,
        (CLOUD_NOISE_TILE_EDGE_SCALE / CLOUD_NOISE_TILES,) * 2 + (0.0,),
        (CLOUD_NOISE_TILE_CENTER / CLOUD_NOISE_TILES,) * 2 + (0.0,),
        name=f"{prefix} Slice UV",
        location=(x + 180, y + 60),
    )
    w = new_node(tree, "ShaderNodeSeparateXYZ", f"{prefix} W", (x + 180, y - 80))
    tree.links.new(uvw, w.inputs["Vector"])
    frames = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        w.outputs["Z"],
        CLOUD_NOISE_FRAMES,
        name=f"{prefix} Z Frames",
        location=(x + 360, y - 80),
    )
    frame = shader_nodes.math(
        tree.nodes,
        tree.links,
        "CEIL",
        frames,
        name=f"{prefix} Frame",
        location=(x + 540, y - 40),
    )
    phase = shader_nodes.math(
        tree.nodes,
        tree.links,
        "FRACT",
        frames,
        name=f"{prefix} Z Phase",
        location=(x + 540, y - 140),
    )
    next_frame = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        frame,
        1.0,
        name=f"{prefix} Next Frame",
        location=(x + 540, y - 240),
    )

    def slice_texture(frame_socket, suffix, yy):
        column = shader_nodes.math(
            tree.nodes,
            tree.links,
            "MODULO",
            frame_socket,
            CLOUD_NOISE_TILES,
            name=f"{prefix} Tile X {suffix}",
            location=(x + 720, yy + 60),
        )
        row = shader_nodes.math(
            tree.nodes,
            tree.links,
            "DIVIDE",
            frame_socket,
            CLOUD_NOISE_TILES,
            name=f"{prefix} Tile Row {suffix}",
            location=(x + 720, yy - 20),
        )
        row_floor = shader_nodes.math(
            tree.nodes,
            tree.links,
            "FLOOR",
            row,
            name=f"{prefix} Tile Row Floor {suffix}",
            location=(x + 880, yy - 20),
        )
        tile_y = shader_nodes.math(
            tree.nodes,
            tree.links,
            "SUBTRACT",
            CLOUD_NOISE_TILES,
            row_floor,
            name=f"{prefix} Tile Y {suffix}",
            location=(x + 1040, yy - 20),
        )
        offset = new_node(
            tree, "ShaderNodeCombineXYZ", f"{prefix} Tile {suffix}", (x + 1200, yy + 20)
        )
        tree.links.new(column, offset.inputs["X"])
        tree.links.new(tile_y, offset.inputs["Y"])
        uv = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "MULTIPLY_ADD",
            offset.outputs["Vector"],
            (1.0 / CLOUD_NOISE_TILES,) * 3,
            tile_uv,
            name=f"{prefix} Atlas UV {suffix}",
            location=(x + 1360, yy + 20),
        )
        wrapped = shader_nodes.vector_math(
            tree.nodes,
            tree.links,
            "FRACTION",
            uv,
            name=f"{prefix} Atlas UV Wrap {suffix}",
            location=(x + 1520, yy + 20),
        )
        texture = new_node(
            tree,
            "ShaderNodeTexImage",
            f"{prefix} Texture {suffix}",
            (x + 1680, yy + 20),
        )
        texture.image = image
        texture.extension = "EXTEND"
        texture.interpolation = "Linear"
        tree.links.new(wrapped, texture.inputs["Vector"])
        return texture

    current = slice_texture(frame, "A", y + 180)
    following = slice_texture(next_frame, "B", y - 260)
    color_delta = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        following.outputs["Color"],
        current.outputs["Color"],
        name=f"{prefix} Slice Color Delta",
        location=(x + 1900, y + 60),
    )
    color = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        color_delta,
        phase,
        current.outputs["Color"],
        name=f"{prefix} Slice Interpolation",
        location=(x + 2060, y + 60),
    )
    if not with_alpha:
        return color, None
    alpha_delta = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        following.outputs["Alpha"],
        current.outputs["Alpha"],
        name=f"{prefix} Slice Alpha Delta",
        location=(x + 1900, y - 100),
    )
    alpha = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        alpha_delta,
        phase,
        current.outputs["Alpha"],
        name=f"{prefix} Alpha Interpolation",
        location=(x + 2060, y - 100),
    )
    return color, alpha


def _noise_coords(tree, world_coords, scale, offset_x, offset_y, prefix, x, y):
    """World position over the noise tile size, centred and shifted by the wind offsets"""
    offset = new_node(tree, "ShaderNodeCombineXYZ", f"{prefix} Offset", (x, y - 120))
    tree.links.new(offset_x, offset.inputs["X"])
    tree.links.new(offset_y, offset.inputs["Y"])
    centred = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "ADD",
        offset.outputs["Vector"],
        (0.5, 0.5, 0.0),
        name=f"{prefix} Centred Offset",
        location=(x + 180, y - 120),
    )
    return shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        world_coords,
        (1.0 / scale,) * 3,
        centred,
        name=f"{prefix} Coordinates",
        location=(x + 360, y),
    )


def _channel_weight(tree, color, name, location):
    """Weighted noise octaves"""
    return shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "DOT_PRODUCT",
        color,
        (0.625, 0.25, 0.125),
        name=name,
        location=location,
    )


def _remapped_noise(tree, color, alpha, prefix, x, y):
    weight = _channel_weight(tree, color, f"{prefix} Octaves", (x, y))
    lower = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        weight,
        1.0,
        name=f"{prefix} Lower",
        location=(x + 180, y),
    )
    numerator = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        alpha,
        lower,
        name=f"{prefix} Alpha Numerator",
        location=(x + 360, y + 40),
    )
    denominator = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        1.0,
        lower,
        name=f"{prefix} Alpha Denominator",
        location=(x + 360, y - 60),
    )
    return _safe_ratio(tree, numerator, denominator, f"{prefix} Noise", (x + 540, y))


def _build_cloud_material(material, texture_space):
    material.use_nodes = True
    material["cp77_cloud_schema"] = CLOUD_MATERIAL_SCHEMA_VERSION
    tree = material.node_tree
    tree.nodes.clear()

    texcoord = new_node(
        tree, "ShaderNodeTexCoord", "CP77 Cloud Coordinates", (-3000, 500)
    )
    texcoord.object = texture_space
    world_coords = texcoord.outputs["Object"]
    generated = texcoord.outputs["Generated"]
    generated_xyz = new_node(
        tree, "ShaderNodeSeparateXYZ", "CP77 Cloud Generated XYZ", (-2820, 900)
    )
    tree.links.new(generated, generated_xyz.inputs["Vector"])
    altitude = generated_xyz.outputs["Z"]

    coverage = value_node(tree, "CP77 Cloud Coverage", 0.0, (-3000, 1250)).outputs[
        "Value"
    ]
    horizon_coverage = value_node(
        tree, "CP77 Cloud Horizon Coverage", 1.0, (-3000, 1180)
    ).outputs["Value"]
    cloud_density = value_node(tree, "CP77 Cloud Density", 0.0, (-3000, 1110)).outputs[
        "Value"
    ]
    preview_enabled = value_node(
        tree, "CP77 Cloud Preview Enabled", 1.0, (-3000, 1040)
    ).outputs["Value"]
    ray_start = value_node(tree, "CP77 Cloud Ray Start", 25.0, (-3000, 970)).outputs[
        "Value"
    ]
    ray_falloff = value_node(
        tree, "CP77 Cloud Ray Falloff", 50.0, (-3000, 900)
    ).outputs["Value"]
    in_scatter = value_node(tree, "CP77 Cloud In Scatter", 0.2, (-3000, 830)).outputs[
        "Value"
    ]
    out_scatter = value_node(tree, "CP77 Cloud Out Scatter", 0.1, (-3000, 760)).outputs[
        "Value"
    ]
    in_vs_out = value_node(tree, "CP77 Cloud In Vs Out", 0.5, (-3000, 690)).outputs[
        "Value"
    ]
    silver = value_node(tree, "CP77 Cloud Silver Lining", 0.8, (-3000, 620)).outputs[
        "Value"
    ]
    coverage_offset_x = value_node(
        tree, "CP77 Cloud Coverage Offset X", 0.0, (-3000, 520)
    ).outputs["Value"]
    coverage_offset_y = value_node(
        tree, "CP77 Cloud Coverage Offset Y", 0.0, (-3000, 450)
    ).outputs["Value"]
    noise_offset_x = value_node(
        tree, "CP77 Cloud Noise Offset X", 0.0, (-3000, 380)
    ).outputs["Value"]
    noise_offset_y = value_node(
        tree, "CP77 Cloud Noise Offset Y", 0.0, (-3000, 310)
    ).outputs["Value"]
    detail_offset_x = value_node(
        tree, "CP77 Cloud Detail Offset X", 0.0, (-3000, 240)
    ).outputs["Value"]
    detail_offset_y = value_node(
        tree, "CP77 Cloud Detail Offset Y", 0.0, (-3000, 170)
    ).outputs["Value"]
    tint = rgb_node(tree, "CP77 Cloud Tint", (1.0, 1.0, 1.0), (-3000, 80)).outputs[
        "Color"
    ]

    # Weather map: repeating coordinates from world position, preview scale and wind offset.
    weather_uv = _noise_coords(
        tree,
        world_coords,
        CLOUD_COVERAGE_WORLD_SCALE,
        coverage_offset_x,
        coverage_offset_y,
        "CP77 Cloud Weather",
        -2750,
        600,
    )
    weather_uv = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "FRACTION",
        weather_uv,
        name="CP77 Cloud Weather UV",
        location=(-2200, 600),
    )
    weather = new_node(
        tree, "ShaderNodeTexImage", "CP77 Cloud Weather Texture", (-2050, 570)
    )
    weather.image = _load_image("cloud_weather.png")
    weather.extension = "REPEAT"
    weather.interpolation = "Linear"
    tree.links.new(weather_uv, weather.inputs["Vector"])
    weather_channels = new_node(
        tree, "ShaderNodeSeparateColor", "CP77 Cloud Weather Channels", (-1840, 570)
    )
    tree.links.new(weather.outputs["Color"], weather_channels.inputs["Color"])

    coverage_gate = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        coverage,
        0.5,
        name="CP77 Cloud Coverage Gate",
        location=(-1670, 760),
        use_clamp=True,
    )
    secondary = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        coverage_gate,
        2.0,
        name="CP77 Cloud Weather Secondary",
        location=(-1500, 760),
    )
    secondary_g = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        secondary,
        weather_channels.outputs["Green"],
        name="CP77 Cloud Weather Secondary G",
        location=(-1330, 760),
    )
    weather_coverage = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MAXIMUM",
        weather_channels.outputs["Red"],
        secondary_g,
        name="CP77 Cloud Weather Coverage",
        location=(-1160, 720),
    )

    # Horizon coverage across the 4096 m cloud square: fract(max(4 r - 0.5, 0)), r = horizontal
    # distance from the preview centre in generated units (the preview spans four squares).
    horizon_vector = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        generated,
        (1.0, 1.0, 0.0),
        (-0.5, -0.5, 0.0),
        name="CP77 Cloud Horizon Vector",
        location=(-1660, 430),
    )
    horizon_distance = shader_nodes.vector_math(
        tree.nodes,
        tree.links,
        "LENGTH",
        horizon_vector,
        name="CP77 Cloud Horizon Distance",
        location=(-1480, 430),
    )
    horizon_start = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        horizon_distance,
        CLOUD_PREVIEW_SIZE / CLOUD_WORLD_SIZE,
        -0.5,
        name="CP77 Cloud Horizon Start",
        location=(-1300, 430),
    )
    horizon_positive = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MAXIMUM",
        horizon_start,
        0.0,
        name="CP77 Cloud Horizon Positive",
        location=(-1120, 430),
    )
    horizon_frac = shader_nodes.math(
        tree.nodes,
        tree.links,
        "FRACT",
        horizon_positive,
        name="CP77 Cloud Horizon Frac",
        location=(-940, 430),
    )
    horizon = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        horizon_frac,
        horizon_coverage,
        name="CP77 Cloud Horizon Influence",
        location=(-760, 430),
    )
    weather_coverage_final = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        weather_coverage,
        horizon,
        name="CP77 Cloud Weather Coverage Final",
        location=(-580, 680),
        use_clamp=True,
    )

    # Vertical cloud bounds from normalized altitude and the weather map's stop height.
    bottom_round = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        altitude,
        0.07,
        name="CP77 Cloud Bottom Round",
        location=(-1650, 230),
        use_clamp=True,
    )
    stop_height = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        weather_channels.outputs["Blue"],
        0.12,
        name="CP77 Cloud Stop Height",
        location=(-1650, 120),
        use_clamp=True,
    )
    stop_low = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        stop_height,
        0.2,
        name="CP77 Cloud Stop Height Low",
        location=(-1480, 100),
    )
    stop_numerator = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        stop_height,
        altitude,
        name="CP77 Cloud Top Round Numerator",
        location=(-1300, 170),
    )
    stop_denominator = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        stop_height,
        stop_low,
        name="CP77 Cloud Top Round Denominator",
        location=(-1300, 80),
    )
    top_round = _safe_ratio(
        tree, stop_numerator, stop_denominator, "CP77 Cloud Top Round", (-1120, 160)
    )
    height_scale = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        bottom_round,
        top_round,
        name="CP77 Cloud Height Alter",
        location=(-760, 200),
    )

    # Density by altitude and the weather map's density channel.
    base_density_ramp = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        altitude,
        0.2,
        name="CP77 Cloud Base Density Ramp",
        location=(-1650, -80),
        use_clamp=True,
    )
    density_altitude = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        altitude,
        base_density_ramp,
        name="CP77 Cloud Density Altitude",
        location=(-1480, -70),
    )
    weather_density = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        weather.outputs["Alpha"],
        2.0,
        name="CP77 Cloud Weather Density A",
        location=(-1480, -160),
    )
    density_weather = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        density_altitude,
        weather_density,
        name="CP77 Cloud Density Weather",
        location=(-1300, -70),
    )
    top_density_numerator = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        1.0,
        altitude,
        name="CP77 Cloud Density Top Numerator",
        location=(-1300, -170),
    )
    top_density = shader_nodes.math(
        tree.nodes,
        tree.links,
        "DIVIDE",
        top_density_numerator,
        0.1,
        name="CP77 Cloud Density Top Ramp",
        location=(-1120, -170),
        use_clamp=True,
    )
    density_scale = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        density_weather,
        top_density,
        name="CP77 Cloud Density Alter",
        location=(-940, -70),
    )

    # Base shape from the sliced volume noise, interpolated between Z slices.
    noise_image = _load_image("cloud_noise.png")
    base_coords = _noise_coords(
        tree,
        world_coords,
        CLOUD_BASE_NOISE_WORLD_SCALE,
        noise_offset_x,
        noise_offset_y,
        "CP77 Cloud Base Noise",
        -2750,
        -420,
    )
    base_color, base_alpha = _sample_atlas(
        tree, base_coords, noise_image, "CP77 Cloud Base Atlas", -2200, -450
    )
    base_noise = _remapped_noise(
        tree, base_color, base_alpha, "CP77 Cloud Base Noise", 0, -450
    )
    base_horizon = shader_nodes.math(
        tree.nodes,
        tree.links,
        "ADD",
        base_noise,
        horizon,
        name="CP77 Cloud Base Noise Horizon",
        location=(900, -390),
        use_clamp=True,
    )

    coverage_weather = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        coverage,
        weather_coverage_final,
        name="CP77 Cloud Coverage Weather Product",
        location=(900, -250),
    )
    coverage_height = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        weather_coverage_final,
        height_scale,
        name="CP77 Cloud Coverage Height",
        location=(900, -160),
    )
    coverage_shape_scale = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        coverage_height,
        coverage,
        name="CP77 Cloud Coverage Shape Scale",
        location=(1080, -160),
    )
    coverage_shape = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        coverage_shape_scale,
        0.2,
        name="CP77 Cloud Coverage Shape",
        location=(1260, -160),
        use_clamp=True,
    )
    coverage_shape_density = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        coverage_shape,
        density_scale,
        name="CP77 Cloud Coverage Shape Density",
        location=(1440, -160),
    )
    coverage_shape_gate = shader_nodes.math(
        tree.nodes,
        tree.links,
        "GREATER_THAN",
        coverage_shape_density,
        0.0001,
        name="CP77 Cloud Coverage Early Gate",
        location=(1620, -160),
    )
    threshold = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        1.0,
        coverage_weather,
        name="CP77 Cloud Coverage Threshold",
        location=(1080, -250),
    )
    base_height = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        base_horizon,
        height_scale,
        name="CP77 Cloud Base Noise Height",
        location=(1080, -360),
    )
    base_numerator = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        base_height,
        threshold,
        name="CP77 Cloud Base Shape Numerator",
        location=(1260, -360),
    )
    base_shape = _safe_ratio(
        tree, base_numerator, coverage_weather, "CP77 Cloud Base Shape", (1440, -360)
    )
    base_density = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        base_shape,
        density_scale,
        name="CP77 Cloud Base Density Result",
        location=(1800, -360),
    )
    base_detail_gate = shader_nodes.math(
        tree.nodes,
        tree.links,
        "GREATER_THAN",
        base_density,
        0.0001,
        name="CP77 Cloud Base Detail Gate",
        location=(1980, -360),
    )

    # Detail erosion from a second, finer lookup of the same atlas (colour only).
    detail_coords = _noise_coords(
        tree,
        world_coords,
        CLOUD_DETAIL_NOISE_WORLD_SCALE,
        detail_offset_x,
        detail_offset_y,
        "CP77 Cloud Detail Noise",
        -2750,
        -1200,
    )
    detail_color, _ = _sample_atlas(
        tree,
        detail_coords,
        noise_image,
        "CP77 Cloud Detail Atlas",
        -2200,
        -1230,
        with_alpha=False,
    )
    detail = _channel_weight(
        tree, detail_color, "CP77 Cloud Detail Octaves", (0, -1230)
    )
    detail_altitude = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        altitude,
        5.0,
        name="CP77 Cloud Detail Altitude",
        location=(0, -1340),
        use_clamp=True,
    )
    # mix(detail, 1 - detail, t) = detail + (1 - 2 detail) t
    detail_swing = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        detail,
        -2.0,
        1.0,
        name="CP77 Cloud Detail Swing",
        location=(180, -1230),
    )
    detail_result = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        detail_swing,
        detail_altitude,
        detail,
        name="CP77 Cloud Detail Modifier",
        location=(360, -1230),
    )
    coverage_negative = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        coverage,
        -1.0,
        name="CP77 Cloud Coverage Negative",
        location=(180, -1340),
    )
    coverage_decay = shader_nodes.math(
        tree.nodes,
        tree.links,
        "EXPONENT",
        coverage_negative,
        name="CP77 Cloud Coverage Exp",
        location=(360, -1340),
    )
    detail_modifier = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        detail_result,
        coverage_decay,
        name="CP77 Cloud Detail Coverage",
        location=(540, -1230),
    )
    detail_numerator = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        base_noise,
        detail_modifier,
        name="CP77 Cloud Detail Shape Numerator",
        location=(720, -1150),
    )
    detail_denominator = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        1.0,
        detail_modifier,
        name="CP77 Cloud Detail Shape Denominator",
        location=(720, -1240),
    )
    detail_shape = _safe_ratio(
        tree,
        detail_numerator,
        detail_denominator,
        "CP77 Cloud Detail Shape",
        (900, -1150),
    )
    detail_height = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        detail_shape,
        height_scale,
        name="CP77 Cloud Detail Height",
        location=(1260, -1080),
    )
    final_numerator = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        detail_height,
        threshold,
        name="CP77 Cloud Final Shape Numerator",
        location=(1440, -1080),
    )
    final_shape = _safe_ratio(
        tree, final_numerator, coverage_weather, "CP77 Cloud Final Shape", (1620, -1080)
    )
    detail_density = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        final_shape,
        density_scale,
        name="CP77 Cloud Detail Density Result",
        location=(1980, -1020),
    )
    # Detail erosion applies only where the base shape already has density.
    branch_delta = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        detail_density,
        base_density,
        name="CP77 Cloud Base Detail Delta",
        location=(2160, -1020),
    )
    branch = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY_ADD",
        branch_delta,
        base_detail_gate,
        base_density,
        name="CP77 Cloud Base Detail Branch",
        location=(2340, -1020),
    )
    gated = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        branch,
        coverage_shape_gate,
        name="CP77 Cloud Coverage Early Exit",
        location=(2520, -1020),
    )

    # Ramp density after the ray enters the slab. View Distance is the closest stable proxy
    # available from Blender volume nodes.
    camera = new_node(
        tree, "ShaderNodeCameraData", "CP77 Cloud Camera Distance", (1900, -760)
    )
    start_distance = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        camera.outputs.get("View Distance") or camera.outputs["View Z Depth"],
        ray_start,
        name="CP77 Cloud Ray Start Distance",
        location=(2080, -760),
    )
    near = _safe_ratio(
        tree, start_distance, ray_falloff, "CP77 Cloud Ray Start Falloff", (2260, -760)
    )

    density = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        gated,
        cloud_density,
        name="CP77 Cloud Vol Density",
        location=(2700, -940),
    )
    density = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        density,
        near,
        name="CP77 Cloud Near Density",
        location=(2880, -940),
    )
    density = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        density,
        preview_enabled,
        name="CP77 Cloud Final Density",
        location=(3060, -940),
    )

    # Blend a forward silver-lining lobe with an opposing lobe.
    forward_weight = shader_nodes.math(
        tree.nodes,
        tree.links,
        "SUBTRACT",
        1.0,
        in_vs_out,
        name="CP77 Cloud Forward Lobe Weight",
        location=(2700, -650),
    )
    forward_density = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        density,
        forward_weight,
        name="CP77 Cloud Forward Density",
        location=(2880, -620),
    )
    backward_density = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        density,
        in_vs_out,
        name="CP77 Cloud Backward Density",
        location=(2880, -720),
    )
    forward_g = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MAXIMUM",
        in_scatter,
        silver,
        name="CP77 Cloud Forward Anisotropy",
        location=(2700, -500),
    )
    backward_g = shader_nodes.math(
        tree.nodes,
        tree.links,
        "MULTIPLY",
        out_scatter,
        -1.0,
        name="CP77 Cloud Backward Anisotropy",
        location=(2700, -420),
    )

    forward = new_node(
        tree, "ShaderNodeVolumeScatter", "CP77 Cloud Forward Scatter", (3280, -620)
    )
    tree.links.new(tint, forward.inputs["Color"])
    tree.links.new(forward_density, forward.inputs["Density"])
    tree.links.new(forward_g, forward.inputs["Anisotropy"])
    backward = new_node(
        tree, "ShaderNodeVolumeScatter", "CP77 Cloud Backward Scatter", (3280, -800)
    )
    tree.links.new(tint, backward.inputs["Color"])
    tree.links.new(backward_density, backward.inputs["Density"])
    tree.links.new(backward_g, backward.inputs["Anisotropy"])
    add = new_node(tree, "ShaderNodeAddShader", "CP77 Cloud Dual Lobe", (3500, -700))
    tree.links.new(forward.outputs["Volume"], add.inputs["Shader"])
    tree.links.new(
        backward.outputs["Volume"],
        shader_nodes.socket_by_identifier(add.inputs, "Shader_001"),
    )
    output = new_node(
        tree, "ShaderNodeOutputMaterial", "CP77 Cloud Output", (3700, -700)
    )
    tree.links.new(add.outputs["Shader"], output.inputs["Volume"])
    return material


def _ensure_material(scene):
    collection = weather_collection(scene, create=True)
    texture_space = _ensure_texture_space(scene, collection)
    material = find_owned("materials", scene, _MATERIAL_ROLE)
    stale_material = None
    rebuild = material is None
    if material is not None:
        rebuild = (
            material.get("cp77_cloud_schema") != CLOUD_MATERIAL_SCHEMA_VERSION
            or not material.use_nodes
        )
        if rebuild:
            stale_material = material

    if rebuild:
        target_name = managed_name(scene, CLOUD_VOLUME_MATERIAL)
        material = track_created_datablock(
            "materials",
            bpy.data.materials.new(target_name),
        )
        tag_owned(material, scene, _MATERIAL_ROLE, base_name=CLOUD_VOLUME_MATERIAL)
        cache_owned("materials", scene, _MATERIAL_ROLE, material)
        _build_cloud_material(material, texture_space)
        if stale_material is not None:
            retire_datablock(
                "materials",
                stale_material,
                scene=scene,
                role=_MATERIAL_ROLE,
                replacement=material,
                replacement_name=target_name,
            )
    else:
        texcoord = material.node_tree.nodes.get("CP77 Cloud Coordinates")
        if (
            texcoord is not None
            and getattr(texcoord, "object", None) is not texture_space
        ):
            texcoord.object = texture_space
    return material


def _ensure_cloud_object(scene, material):
    collection = weather_collection(scene, create=True)
    anchor = ensure_weather_anchor(scene, collection)
    obj = find_owned("objects", scene, _CLOUD_ROLE)
    if obj is None or obj.get("cp77_cloud_schema") != CLOUD_OBJECT_SCHEMA_VERSION:
        stale_obj = obj
        target_name = managed_name(scene, CLOUD_VOLUME_OBJECT)
        mesh = cube_mesh(managed_name(scene, f"{CLOUD_VOLUME_OBJECT}_Mesh"))
        obj = track_created_datablock(
            "objects",
            bpy.data.objects.new(target_name, mesh),
        )
        tag_owned(obj, scene, _CLOUD_ROLE, base_name=CLOUD_VOLUME_OBJECT)
        cache_owned("objects", scene, _CLOUD_ROLE, obj)
        collection.objects.link(obj)
        obj.display_type = "WIRE"
        obj["cp77_cloud_schema"] = CLOUD_OBJECT_SCHEMA_VERSION
        if hasattr(obj, "visible_shadow"):
            obj.visible_shadow = True
        if stale_obj is not None:
            retire_object(
                stale_obj,
                scene=scene,
                role=_CLOUD_ROLE,
                replacement=obj,
                replacement_name=target_name,
            )
    constraint = obj.constraints.get("CP77 Cloud Camera XY")
    if constraint is None:
        constraint = obj.constraints.new("COPY_LOCATION")
        constraint.name = "CP77 Cloud Camera XY"
    constraint.target = anchor
    constraint.use_x = True
    constraint.use_y = True
    constraint.use_z = False
    if not obj.data.materials:
        obj.data.materials.append(material)
    elif obj.data.materials[0] is not material:
        obj.data.materials[0] = material
    return obj


def ensure_cloud_preview(scene, settings):
    if not settings.preview_volumetric_clouds:
        return 0
    material = _ensure_material(scene)
    existed = find_owned("objects", scene, _CLOUD_ROLE) is not None
    _ensure_cloud_object(scene, material)
    return 0 if existed else 1


def apply_cloud_preview(scene, settings, sample, weather_sample):
    obj = find_owned("objects", scene, _CLOUD_ROLE)
    material = find_owned("materials", scene, _MATERIAL_ROLE)
    if obj is None or material is None:
        return
    preview = cloud_preview(settings.preview_volumetric_clouds, sample, weather_sample)
    if obj.hide_viewport == preview.active:
        obj.hide_viewport = not preview.active
    if obj.hide_render == preview.active:
        obj.hide_render = not preview.active

    obj.location.z = preview.center_z
    obj.scale = preview.scale
    for name, value in preview.values.items():
        set_value_output(material, name, value)
    set_color_output(material, "CP77 Cloud Tint", preview.tint)


_CLOUD_KEYED_VALUES = (
    "CP77 Cloud Preview Enabled",
    "CP77 Cloud Coverage",
    "CP77 Cloud Horizon Coverage",
    "CP77 Cloud Density",
    "CP77 Cloud Ray Start",
    "CP77 Cloud Ray Falloff",
    "CP77 Cloud In Scatter",
    "CP77 Cloud Out Scatter",
    "CP77 Cloud In Vs Out",
    "CP77 Cloud Silver Lining",
    "CP77 Cloud Coverage Offset X",
    "CP77 Cloud Coverage Offset Y",
    "CP77 Cloud Noise Offset X",
    "CP77 Cloud Noise Offset Y",
    "CP77 Cloud Detail Offset X",
    "CP77 Cloud Detail Offset Y",
)
_CLOUD_KEYED_COLORS = ("CP77 Cloud Tint",)


def cloud_keyframe_targets(scene):
    """(owner, data path) pairs a bake keys on the volumetric cloud preview"""
    targets = []
    obj = find_owned("objects", scene, _CLOUD_ROLE)
    if obj is not None:
        targets.extend(((obj, "location"), (obj, "scale")))
    material = find_owned("materials", scene, _MATERIAL_ROLE)
    if material is not None and material.use_nodes:
        nodes = material.node_tree.nodes
        for names, output in (
            (_CLOUD_KEYED_VALUES, "Value"),
            (_CLOUD_KEYED_COLORS, "Color"),
        ):
            for name in names:
                node = nodes.get(name)
                if node is not None:
                    targets.append((node.outputs[output], "default_value"))
    return tuple(targets)


def clear_cloud_preview_animation(scene):
    obj = find_owned("objects", scene, _CLOUD_ROLE)
    if obj is not None:
        obj.animation_data_clear()
    material = find_owned("materials", scene, _MATERIAL_ROLE)
    if material is not None and material.use_nodes:
        animation = material.node_tree.animation_data
        if animation is not None and animation.action is not None:
            animation.action = None
