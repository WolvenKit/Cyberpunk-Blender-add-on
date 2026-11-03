import hashlib
import math
import os
from pathlib import Path

import bpy
import numpy as np

from ..assetio.documents import file_identity
from ..assetio.resolver import resolve_asset_path
from ..bartmoss.scalar import clamp01
from ..blender import shader_nodes
from ..blender.transactions import new_tracked_datablock
from ..core.log import get_logger
from ..materials.blender.helper_caches import register_helper_cache
from ..materials.resources import load_material_document
from .mat_common import (
    MaterialTypeBase,
    find_input,
    find_output,
    link_sockets,
    new_labeled_node,
    param_color,
    param_float,
    param_texture_path,
    param_vector,
    set_input_value,
    set_scene_fps_driver,
)

_LOG = get_logger(__name__)

_WATER_PATCH_WORLD_SIZE = 10.0
_WATER_PATCH_EDGES = 27.0
_FFT_RESOLUTION = 512.0
# The world XY of the water map's top-left and bottom-right corners, and the UV scale and offset they give.
_WATER_MAP_BOUNDS = ((-5825.0, 4275.0), (2285.0, -3925.0))
_WATER_MAP_SCALE = (
    1.0 / (_WATER_MAP_BOUNDS[1][0] - _WATER_MAP_BOUNDS[0][0]),
    1.0 / (_WATER_MAP_BOUNDS[0][1] - _WATER_MAP_BOUNDS[1][1]),
)
_WATER_MAP_OFFSET = (
    -_WATER_MAP_BOUNDS[0][0] * _WATER_MAP_SCALE[0],
    -_WATER_MAP_BOUNDS[1][1] * _WATER_MAP_SCALE[1],
)
_WATER_ROUGHNESS = 0.1
_FOAM_ROUGHNESS_RANGE = (0.25, 0.5)
_FOAM_FADE_DISTANCE = 150.0
_WAVE_CUTOFF_RANGE = (25.0, 35.0)
_PATCH_REFERENCE_WATER_SIZE = 0.75
_PATCH_REFERENCE_CHOPPINESS_Z = 5.0
_WATER_PATCH_IMAGE_CACHE = {}
_WATER_PATCH_DATA_CACHE = {}


def clear_water_patch_image_cache():
    _WATER_PATCH_IMAGE_CACHE.clear()
    _WATER_PATCH_DATA_CACHE.clear()


def water_patch_image_cache_stats():
    return {
        "entries": len(_WATER_PATCH_IMAGE_CACHE),
        "decoded_entries": len(_WATER_PATCH_DATA_CACHE),
    }


register_helper_cache(
    "water_patch_images",
    clear=clear_water_patch_image_cache,
    stats=water_patch_image_cache_stats,
)


def _set_displacement_method(material, method="BOTH"):
    for holder in (material, getattr(material, "cycles", None)):
        if holder is None or not hasattr(holder, "displacement_method"):
            continue
        try:
            holder.displacement_method = method
            return True
        except (TypeError, ValueError):
            continue
    return False


def _set_material_transparency(material):
    material.use_nodes = True
    material.surface_render_method = "DITHERED"
    material.use_raytrace_refraction = True
    if hasattr(material, "use_transparency_overlap"):
        material.use_transparency_overlap = True
    if hasattr(material, "use_backface_culling"):
        material.use_backface_culling = False


def _expanded_resource_roots(roots):
    expanded = []
    for root in roots:
        if not root:
            continue
        candidate = os.path.normpath(os.path.abspath(os.path.expanduser(str(root))))
        if candidate not in expanded:
            expanded.append(candidate)
    return tuple(expanded)


def _json_extension(reference, fallback=".json"):
    filename = str(reference or "").replace("\\", "/").rsplit("/", 1)[-1]
    suffixes = Path(filename).suffixes
    return "".join(suffixes) if suffixes else fallback


def _resolve_json_sidecar(references, roots):
    expanded_roots = _expanded_resource_roots(roots)
    for reference in references:
        if not reference:
            continue
        resolved = resolve_asset_path(
            reference,
            roots=expanded_roots,
            extensions=(_json_extension(reference),),
            warn=False,
        )
        if resolved:
            return resolved
    return ""


def _mesh_json_references(mesh_path):
    references = []

    def add(candidate):
        if not candidate:
            return
        candidate = os.path.normpath(
            os.path.abspath(os.path.expanduser(str(candidate)))
        )
        if candidate not in references:
            references.append(candidate)

    if not mesh_path:
        return ()

    mesh_path = os.path.normpath(os.path.abspath(os.path.expanduser(str(mesh_path))))
    lower = mesh_path.lower()
    if lower.endswith(".mesh.json"):
        add(mesh_path)
    elif lower.endswith(".mesh.glb"):
        add(mesh_path[:-4] + ".json")
        add(mesh_path[:-9] + ".mesh.json")
    elif lower.endswith(".glb"):
        add(mesh_path[:-4] + ".mesh.json")
        add(mesh_path[:-4] + ".json")
    elif lower.endswith(".mesh"):
        add(mesh_path + ".json")
    else:
        add(mesh_path + ".mesh.json")

    basename = os.path.basename(mesh_path)
    if basename.lower().endswith(".mesh.glb"):
        basename = basename[:-4] + ".json"
    elif basename.lower().endswith(".glb"):
        basename = basename[:-4] + ".mesh.json"
    elif basename.lower().endswith(".mesh"):
        basename += ".json"
    elif not basename.lower().endswith(".mesh.json"):
        basename += ".mesh.json"
    if basename not in references:
        references.append(basename)
    return tuple(references)


def _water_patch_parameter(payload):
    root = payload.get("Data", {}).get("RootChunk", {})
    for parameter in root.get("parameters", []):
        data = parameter.get("Data", {}) if isinstance(parameter, dict) else {}
        if data.get("$type") == "meshMeshParamWaterPatchData":
            return root, data
    return root, None


def _read_water_patch_mesh(mesh_path, roots):
    candidate = _resolve_json_sidecar(_mesh_json_references(mesh_path), roots)
    if not candidate:
        return None
    try:
        identity = file_identity(candidate).key
        cached = _WATER_PATCH_DATA_CACHE.get(identity)
        if cached is not None:
            return dict(cached)
        resource = load_material_document(candidate)
        payload = resource.payload if resource is not None else {}
        root, parameter = _water_patch_parameter(payload)
        if not parameter:
            return None

        rows = parameter.get("nodes", {}).get("Elements", [])
        if not rows:
            return None
        frame_count = len(rows[0].get("Elements", []))
        point_count = len(rows)
        grid_size = int(round(math.sqrt(point_count)))
        if (
            grid_size * grid_size != point_count
            or frame_count <= 0
            or any(len(row.get("Elements", [])) != frame_count for row in rows)
        ):
            _LOG.warning(
                "Ignoring unsupported water patch data layout %sx%s in %s",
                point_count,
                frame_count,
                candidate,
            )
            return None

        samples = np.asarray(
            [row["Elements"] for row in rows],
            dtype=np.float32,
        ).reshape(grid_size, grid_size, frame_count)

        bounds = root.get("boundingBox", {})
        minimum = bounds.get("Min", {})
        maximum = bounds.get("Max", {})
        patch_size_x = abs(float(maximum.get("X", 5.0)) - float(minimum.get("X", -5.0)))
        patch_size_y = abs(float(maximum.get("Y", 5.0)) - float(minimum.get("Y", -5.0)))
        patch_size_x = (
            patch_size_x if patch_size_x > 1.0e-6 else _WATER_PATCH_WORLD_SIZE
        )
        patch_size_y = (
            patch_size_y if patch_size_y > 1.0e-6 else _WATER_PATCH_WORLD_SIZE
        )

        edge_error = max(
            float(np.max(np.abs(samples[:, 0, :] - samples[:, -1, :]))),
            float(np.max(np.abs(samples[0, :, :] - samples[-1, :, :]))),
        )
        samples = np.frombuffer(samples.tobytes(), dtype=np.float32).reshape(
            samples.shape
        )
        decoded = {
            "sidecarPath": candidate,
            "samples": samples,
            "gridSize": grid_size,
            "frameCount": frame_count,
            "animLength": max(1.0e-6, float(parameter.get("animLength", 1.0))),
            "animLoop": int(parameter.get("animLoop", 0)),
            "patchSizeX": patch_size_x,
            "patchSizeY": patch_size_y,
            "heightMin": float(np.min(samples)),
            "heightMax": float(np.max(samples)),
            "edgeError": edge_error,
        }
        for previous_key, previous in tuple(_WATER_PATCH_DATA_CACHE.items()):
            if previous["sidecarPath"] == candidate:
                del _WATER_PATCH_DATA_CACHE[previous_key]
        _WATER_PATCH_DATA_CACHE[identity] = decoded
        return dict(decoded)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        _LOG.warning(
            "Failed to read water patch mesh data %s: %s", candidate, exc, exc_info=True
        )
        return None


def _water_patch_image(patch_data):
    if not patch_data:
        return None

    sidecar_path = patch_data["sidecarPath"]
    cache_key = file_identity(sidecar_path).key
    cached_name = _WATER_PATCH_IMAGE_CACHE.get(cache_key)
    if cached_name:
        cached = bpy.data.images.get(cached_name)
        if cached is not None:
            return cached

    samples = patch_data["samples"]
    grid_size = patch_data["gridSize"]
    frame_count = patch_data["frameCount"]
    columns = int(math.ceil(math.sqrt(frame_count)))
    rows = int(math.ceil(frame_count / columns))
    width = grid_size * columns
    height = grid_size * rows
    height_min = patch_data["heightMin"]
    height_max = patch_data["heightMax"]
    height_range = max(height_max - height_min, 1.0e-8)

    atlas = np.zeros((height, width, 4), dtype=np.float32)
    atlas[:, :, 3] = 1.0
    for frame in range(frame_count):
        tile_x = frame % columns
        tile_y = frame // columns
        frame_data = ((samples[:, :, frame] - height_min) / height_range).T
        y0 = tile_y * grid_size
        x0 = tile_x * grid_size
        atlas[y0 : y0 + grid_size, x0 : x0 + grid_size, :3] = frame_data[:, :, None]

    digest = hashlib.sha1(sidecar_path.encode("utf-8")).hexdigest()[:12]
    image_name = "CP77 Water Patch " + digest
    image = bpy.data.images.get(image_name)
    if image is None or tuple(image.size) != (width, height):
        if image is not None:
            bpy.data.images.remove(image)
        image = new_tracked_datablock(
            "images",
            image_name,
            width=width,
            height=height,
            alpha=True,
            float_buffer=True,
        )
    image.colorspace_settings.name = "Non-Color"
    image.alpha_mode = "CHANNEL_PACKED"
    image.pixels.foreach_set(np.ascontiguousarray(atlas).reshape(-1))
    image.update()
    try:
        image.pack()
    except RuntimeError:
        pass

    patch_data["imageName"] = image.name
    _WATER_PATCH_IMAGE_CACHE[cache_key] = image.name
    return image


def _build_patch_frame_offsets(nodes, links, time_output, patch_data, location):
    x, y = location
    frame_count = float(patch_data["frameCount"])
    columns = float(int(math.ceil(math.sqrt(patch_data["frameCount"]))))
    rows = float(int(math.ceil(patch_data["frameCount"] / columns)))

    cycle = shader_nodes.math(
        nodes, links, "DIVIDE", name="Water Patch Cycle", location=(x, y)
    ).node
    shader_nodes.socket_by_identifier(cycle.inputs, "Value_001").default_value = float(
        patch_data["animLength"]
    )
    link_sockets(links, time_output, cycle.inputs["Value"])

    cycle_wrap = shader_nodes.math(
        nodes, links, "FRACT", name="Water Patch Cycle Wrap", location=(x + 190, y)
    ).node
    link_sockets(links, find_output(cycle, "Value"), cycle_wrap.inputs["Value"])

    frame_position = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        name="Water Patch Frame Position",
        location=(x + 380, y),
    ).node
    shader_nodes.socket_by_identifier(
        frame_position.inputs, "Value_001"
    ).default_value = frame_count
    link_sockets(
        links, find_output(cycle_wrap, "Value"), frame_position.inputs["Value"]
    )

    frame = shader_nodes.math(
        nodes, links, "FLOOR", name="Water Patch Frame", location=(x + 570, y)
    ).node
    link_sockets(links, find_output(frame_position, "Value"), frame.inputs["Value"])

    blend = shader_nodes.math(
        nodes,
        links,
        "FRACT",
        name="Water Patch Frame Blend",
        location=(x + 570, y - 120),
    ).node
    link_sockets(links, find_output(frame_position, "Value"), blend.inputs["Value"])

    next_add = shader_nodes.math(
        nodes, links, "ADD", name="Water Patch Next Frame", location=(x + 760, y - 120)
    ).node
    shader_nodes.socket_by_identifier(next_add.inputs, "Value_001").default_value = 1.0
    link_sockets(links, find_output(frame, "Value"), next_add.inputs["Value"])

    next_frame = shader_nodes.math(
        nodes,
        links,
        "MODULO",
        name="Water Patch Next Frame Wrap",
        location=(x + 950, y - 120),
    ).node
    shader_nodes.socket_by_identifier(
        next_frame.inputs, "Value_001"
    ).default_value = frame_count
    link_sockets(links, find_output(next_add, "Value"), next_frame.inputs["Value"])

    def atlas_offset(frame_output, name, node_y):
        column = shader_nodes.math(
            nodes,
            links,
            "MODULO",
            name=f"{name} Column",
            location=(x + 760, node_y + 60),
        ).node
        shader_nodes.socket_by_identifier(
            column.inputs, "Value_001"
        ).default_value = columns
        link_sockets(links, frame_output, column.inputs["Value"])

        column_scale = shader_nodes.math(
            nodes, links, "DIVIDE", name=f"{name} U", location=(x + 950, node_y + 60)
        ).node
        shader_nodes.socket_by_identifier(
            column_scale.inputs, "Value_001"
        ).default_value = columns
        link_sockets(links, find_output(column, "Value"), column_scale.inputs["Value"])

        row_divide = shader_nodes.math(
            nodes,
            links,
            "DIVIDE",
            name=f"{name} Row Divide",
            location=(x + 760, node_y - 60),
        ).node
        shader_nodes.socket_by_identifier(
            row_divide.inputs, "Value_001"
        ).default_value = columns
        link_sockets(links, frame_output, row_divide.inputs["Value"])

        row = shader_nodes.math(
            nodes, links, "FLOOR", name=f"{name} Row", location=(x + 950, node_y - 60)
        ).node
        link_sockets(links, find_output(row_divide, "Value"), row.inputs["Value"])

        row_scale = shader_nodes.math(
            nodes, links, "DIVIDE", name=f"{name} V", location=(x + 1140, node_y - 60)
        ).node
        shader_nodes.socket_by_identifier(
            row_scale.inputs, "Value_001"
        ).default_value = rows
        link_sockets(links, find_output(row, "Value"), row_scale.inputs["Value"])

        offset = new_labeled_node(
            nodes, "ShaderNodeCombineXYZ", f"{name} Offset", (x + 1330, node_y)
        )
        link_sockets(links, find_output(column_scale, "Value"), offset.inputs["X"])
        link_sockets(links, find_output(row_scale, "Value"), offset.inputs["Y"])
        return find_output(offset, "Vector")

    current_offset = atlas_offset(
        find_output(frame, "Value"), "Current Water Patch Frame", y
    )
    next_offset = atlas_offset(
        find_output(next_frame, "Value"), "Next Water Patch Frame", y - 300
    )
    return current_offset, next_offset, find_output(blend, "Value")


def _build_patch_sample(
    nodes, links, image, coordinate, frame_offsets, patch_data, location, label
):
    x, y = location
    current_offset, next_offset, frame_blend = frame_offsets
    grid_size = float(patch_data["gridSize"])
    columns = float(int(math.ceil(math.sqrt(patch_data["frameCount"]))))
    rows = float(int(math.ceil(patch_data["frameCount"] / columns)))

    scale = shader_nodes.vector_math(
        nodes, links, "MULTIPLY", name=f"{label} Scale", location=(x, y)
    ).node
    shader_nodes.socket_by_identifier(scale.inputs, "Vector_001").default_value = (
        1.0 / patch_data["patchSizeX"],
        1.0 / patch_data["patchSizeY"],
        1.0,
    )
    link_sockets(links, coordinate, scale.inputs["Vector"])

    wrap = shader_nodes.vector_math(
        nodes, links, "FRACTION", name=f"{label} Wrap", location=(x + 190, y)
    ).node
    link_sockets(links, find_output(scale, "Vector"), wrap.inputs["Vector"])

    texel_scale = shader_nodes.vector_math(
        nodes, links, "MULTIPLY", name=f"{label} Texel Scale", location=(x + 380, y)
    ).node
    edge_scale = (grid_size - 1.0) / grid_size
    shader_nodes.socket_by_identifier(
        texel_scale.inputs, "Vector_001"
    ).default_value = (edge_scale, edge_scale, 1.0)
    link_sockets(links, find_output(wrap, "Vector"), texel_scale.inputs["Vector"])

    texel_center = shader_nodes.vector_math(
        nodes, links, "ADD", name=f"{label} Texel Center", location=(x + 570, y)
    ).node
    shader_nodes.socket_by_identifier(
        texel_center.inputs, "Vector_001"
    ).default_value = (0.5 / grid_size, 0.5 / grid_size, 0.0)
    link_sockets(
        links, find_output(texel_scale, "Vector"), texel_center.inputs["Vector"]
    )

    tile_scale = shader_nodes.vector_math(
        nodes, links, "MULTIPLY", name=f"{label} Atlas Scale", location=(x + 760, y)
    ).node
    shader_nodes.socket_by_identifier(tile_scale.inputs, "Vector_001").default_value = (
        1.0 / columns,
        1.0 / rows,
        1.0,
    )
    link_sockets(
        links, find_output(texel_center, "Vector"), tile_scale.inputs["Vector"]
    )

    def sample(offset, name, node_y):
        atlas_vector = shader_nodes.vector_math(
            nodes, links, "ADD", name=f"{name} UV", location=(x + 950, node_y)
        ).node
        link_sockets(
            links, find_output(tile_scale, "Vector"), atlas_vector.inputs["Vector"]
        )
        link_sockets(
            links,
            offset,
            shader_nodes.socket_by_identifier(atlas_vector.inputs, "Vector_001"),
        )

        texture = new_labeled_node(
            nodes, "ShaderNodeTexImage", name, (x + 1140, node_y)
        )
        texture.image = image
        texture.interpolation = "Linear"
        texture.extension = "EXTEND"
        link_sockets(
            links, find_output(atlas_vector, "Vector"), find_input(texture, "Vector")
        )
        return find_output(texture, "Color")

    current = sample(current_offset, f"Current {label}", y + 90)
    following = sample(next_offset, f"Next {label}", y - 90)

    blend = new_labeled_node(
        nodes, "ShaderNodeMixRGB", f"Interpolated {label}", (x + 1360, y)
    )
    blend.blend_type = "MIX"
    link_sockets(links, frame_blend, blend.inputs["Factor"])
    link_sockets(links, current, blend.inputs["Color1"])
    link_sockets(links, following, blend.inputs["Color2"])

    channel = new_labeled_node(
        nodes, "ShaderNodeSeparateColor", f"{label} Channel", (x + 1560, y)
    )
    channel.mode = "RGB"
    link_sockets(links, find_output(blend, "Color"), find_input(channel, "Color"))
    normalized = find_output(channel, "Red", "R")

    decode_scale = shader_nodes.math(
        nodes, links, "MULTIPLY", name=f"{label} Range", location=(x + 1760, y)
    ).node
    shader_nodes.socket_by_identifier(
        decode_scale.inputs, "Value_001"
    ).default_value = patch_data["heightMax"] - patch_data["heightMin"]
    link_sockets(links, normalized, decode_scale.inputs["Value"])

    decode_bias = shader_nodes.math(
        nodes, links, "ADD", name=f"{label} Height", location=(x + 1950, y)
    ).node
    shader_nodes.socket_by_identifier(
        decode_bias.inputs, "Value_001"
    ).default_value = patch_data["heightMin"]
    link_sockets(links, find_output(decode_scale, "Value"), decode_bias.inputs["Value"])
    return find_output(decode_bias, "Value"), normalized


def _build_shore_mask(
    nodes,
    links,
    world_position,
    water_map_image,
    map_weight,
    shore_offset,
    shore_threshold,
):
    if water_map_image is None or map_weight <= 0.0:
        value = new_labeled_node(nodes, "ShaderNodeValue", "Shore Mask", (-760, 650))
        value.outputs["Value"].default_value = 1.0
        return value.outputs["Value"]

    scale = shader_nodes.vector_math(
        nodes, links, "MULTIPLY", name="Water Map World Scale", location=(-1580, 680)
    ).node
    shader_nodes.socket_by_identifier(scale.inputs, "Vector_001").default_value = (
        *_WATER_MAP_SCALE,
        0.0,
    )
    link_sockets(links, world_position, scale.inputs["Vector"])

    offset = shader_nodes.vector_math(
        nodes, links, "ADD", name="Water Map World Offset", location=(-1370, 680)
    ).node
    shader_nodes.socket_by_identifier(offset.inputs, "Vector_001").default_value = (
        *_WATER_MAP_OFFSET,
        0.0,
    )
    link_sockets(links, find_output(scale, "Vector"), offset.inputs["Vector"])

    texture = new_labeled_node(nodes, "ShaderNodeTexImage", "Water Map", (-1160, 680))
    texture.image = water_map_image
    texture.interpolation = "Linear"
    texture.extension = "REPEAT"
    link_sockets(links, find_output(offset, "Vector"), find_input(texture, "Vector"))

    channels = new_labeled_node(
        nodes, "ShaderNodeSeparateColor", "Water Map Channels", (-940, 680)
    )
    channels.mode = "RGB"
    link_sockets(links, find_output(texture, "Color"), find_input(channels, "Color"))

    subtract = shader_nodes.math(
        nodes, links, "SUBTRACT", name="Shore Remap Offset", location=(-720, 680)
    ).node
    shader_nodes.socket_by_identifier(
        subtract.inputs, "Value_001"
    ).default_value = shore_offset
    link_sockets(links, find_output(channels, "Green", "G"), subtract.inputs["Value"])

    denominator = shore_threshold - shore_offset
    if abs(denominator) < 1.0e-6:
        denominator = 1.0e-6 if denominator >= 0.0 else -1.0e-6
    remap = shader_nodes.math(
        nodes, links, "DIVIDE", name="Shore Remap", location=(-510, 680)
    ).node
    shader_nodes.socket_by_identifier(
        remap.inputs, "Value_001"
    ).default_value = denominator
    remap.use_clamp = True
    link_sockets(links, find_output(subtract, "Value"), remap.inputs["Value"])

    weighted = shader_nodes.math(
        nodes, links, "MULTIPLY_ADD", name="Shore Mask", location=(-300, 680)
    ).node
    shader_nodes.socket_by_identifier(
        weighted.inputs, "Value_001"
    ).default_value = map_weight
    shader_nodes.socket_by_identifier(weighted.inputs, "Value_002").default_value = (
        1.0 - map_weight
    )
    weighted.use_clamp = True
    link_sockets(links, find_output(remap, "Value"), weighted.inputs["Value"])
    return find_output(weighted, "Value")


def _build_wave_cutoff(nodes, links):
    camera = new_labeled_node(
        nodes, "ShaderNodeCameraData", "Water Camera", (-760, -920)
    )

    start = shader_nodes.math(
        nodes, links, "SUBTRACT", name="Wave Cutoff Start", location=(-540, -920)
    ).node
    shader_nodes.socket_by_identifier(
        start.inputs, "Value_001"
    ).default_value = _WAVE_CUTOFF_RANGE[0]
    link_sockets(links, find_output(camera, "View Distance"), start.inputs["Value"])

    range_node = shader_nodes.math(
        nodes, links, "DIVIDE", name="Wave Cutoff Range", location=(-330, -920)
    ).node
    shader_nodes.socket_by_identifier(range_node.inputs, "Value_001").default_value = (
        _WAVE_CUTOFF_RANGE[1] - _WAVE_CUTOFF_RANGE[0]
    )
    range_node.use_clamp = True
    link_sockets(links, find_output(start, "Value"), range_node.inputs["Value"])

    inverse = shader_nodes.math(
        nodes, links, "SUBTRACT", name="Wave Cutoff", location=(-120, -920)
    ).node
    inverse.inputs["Value"].default_value = 1.0
    link_sockets(
        links,
        find_output(range_node, "Value"),
        shader_nodes.socket_by_identifier(inverse.inputs, "Value_001"),
    )
    return find_output(inverse, "Value"), find_output(camera, "View Distance")


def _build_foam(
    nodes,
    links,
    world_position,
    view_distance,
    shore_mask,
    water_uv_scale,
    foam_image,
    foam_size,
    foam_intensity,
):
    if foam_image is None or foam_intensity <= 0.0:
        value = new_labeled_node(nodes, "ShaderNodeValue", "Foam Opacity", (690, 880))
        value.outputs["Value"].default_value = 0.0
        roughness = new_labeled_node(
            nodes, "ShaderNodeValue", "Foam Roughness", (690, 760)
        )
        roughness.outputs["Value"].default_value = _FOAM_ROUGHNESS_RANGE[0]
        return value.outputs["Value"], roughness.outputs["Value"]

    mapping = new_labeled_node(
        nodes, "ShaderNodeMapping", "Foam Mapping", (-1160, 1120)
    )
    mapping.vector_type = "POINT"
    scale = water_uv_scale * foam_size
    set_input_value(mapping, (scale, scale, 1.0), "Scale")
    link_sockets(links, world_position, find_input(mapping, "Vector"))

    texture = new_labeled_node(
        nodes, "ShaderNodeTexImage", "Foam Texture", (-940, 1120)
    )
    texture.image = foam_image
    texture.interpolation = "Linear"
    texture.extension = "REPEAT"
    link_sockets(links, find_output(mapping, "Vector"), find_input(texture, "Vector"))

    channels = new_labeled_node(
        nodes, "ShaderNodeSeparateColor", "Foam Texture Channels", (-720, 1120)
    )
    channels.mode = "RGB"
    link_sockets(links, find_output(texture, "Color"), find_input(channels, "Color"))
    foam_red = find_output(channels, "Red", "R")

    difference = shader_nodes.math(
        nodes, links, "SUBTRACT", name="Foam Difference", location=(-490, 1030)
    ).node
    shader_nodes.socket_by_identifier(
        difference.inputs, "Value_001"
    ).default_value = 0.5
    link_sockets(links, foam_red, difference.inputs["Value"])

    intensity = shader_nodes.math(
        nodes, links, "MULTIPLY", name="Foam Intensity", location=(-270, 1030)
    ).node
    shader_nodes.socket_by_identifier(
        intensity.inputs, "Value_001"
    ).default_value = foam_intensity
    link_sockets(links, find_output(difference, "Value"), intensity.inputs["Value"])

    shore = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        name="Foam Shore Mask",
        location=(-50, 1030),
        use_clamp=True,
    ).node
    link_sockets(links, find_output(intensity, "Value"), shore.inputs["Value"])
    link_sockets(
        links, shore_mask, shader_nodes.socket_by_identifier(shore.inputs, "Value_001")
    )

    distance = shader_nodes.math(
        nodes, links, "DIVIDE", name="Foam Distance", location=(170, 1120)
    ).node
    shader_nodes.socket_by_identifier(
        distance.inputs, "Value_001"
    ).default_value = _FOAM_FADE_DISTANCE
    distance.use_clamp = True
    link_sockets(links, view_distance, distance.inputs["Value"])

    near = shader_nodes.math(
        nodes, links, "SUBTRACT", name="Foam Distance Fade", location=(390, 1120)
    ).node
    near.inputs["Value"].default_value = 1.0
    link_sockets(
        links,
        find_output(distance, "Value"),
        shader_nodes.socket_by_identifier(near.inputs, "Value_001"),
    )

    opacity = shader_nodes.math(
        nodes,
        links,
        "MULTIPLY",
        name="Foam Opacity",
        location=(610, 1030),
        use_clamp=True,
    ).node
    link_sockets(links, find_output(shore, "Value"), opacity.inputs["Value"])
    link_sockets(
        links,
        find_output(near, "Value"),
        shader_nodes.socket_by_identifier(opacity.inputs, "Value_001"),
    )

    roughness = shader_nodes.math(
        nodes, links, "MULTIPLY_ADD", name="Foam Roughness", location=(610, 850)
    ).node
    shader_nodes.socket_by_identifier(roughness.inputs, "Value_001").default_value = (
        _FOAM_ROUGHNESS_RANGE[1] - _FOAM_ROUGHNESS_RANGE[0]
    )
    shader_nodes.socket_by_identifier(
        roughness.inputs, "Value_002"
    ).default_value = _FOAM_ROUGHNESS_RANGE[0]
    roughness.use_clamp = True
    link_sockets(links, foam_red, roughness.inputs["Value"])
    return find_output(opacity, "Value"), find_output(roughness, "Value")


class GlobalWaterPatch(MaterialTypeBase):
    def __init__(self, BasePath, image_format, ProjPath, MeshPath=""):
        super().__init__(BasePath, image_format, ProjPath)
        self.MeshPath = MeshPath

    def _load_image(self, path, *, non_color=False):
        return self._load_relative_image(
            path,
            non_color=non_color,
            reject_suffixes=(".dtex",),
            error_label="water",
        )

    def create(self, Data, Mat):
        data = Data if isinstance(Data, dict) else {}
        scalar_defaults = {
            "WaterMapWeight": 0.0,
            "WaterSize": 0.25,
            "ShoreThreshold": 0.0,
            "ShoreOffset": 0.0,
            "Hack_SkipSimulatedNormals": 0.0,
            "ScatteringDepth": 2.0,
            "NormalDetailScale": 5.0,
            "NormalDetailIntensity": 1.0,
            "ScatteringSunRadius": 1.5,
            "ScatteringSunIntensity": 1.5,
            "BlurRadius": 1.0,
            "ScatteringSlopeThreshold": 0.025,
            "ScatteringSlopeIntensity": 5.0,
            "WaterOpacity": 1.0,
            "IndexOfRefraction": 1.33,
            "RefractionNormalIntensity": 2.0,
            "BlurStrength": 0.0,
            "FoamSize": 50.0,
            "FoamThreshold": 0.25,
            "FoamIntensity": 0.1,
            "EdgeBlend": 0.1,
        }

        water_size = max(
            0.001, param_float(data, "WaterSize", scalar_defaults["WaterSize"])
        )
        map_weight = clamp01(
            param_float(data, "WaterMapWeight", scalar_defaults["WaterMapWeight"])
        )
        shore_threshold = param_float(
            data, "ShoreThreshold", scalar_defaults["ShoreThreshold"]
        )
        shore_offset = param_float(data, "ShoreOffset", scalar_defaults["ShoreOffset"])
        scattering_depth = max(
            0.0,
            param_float(data, "ScatteringDepth", scalar_defaults["ScatteringDepth"]),
        )
        normal_detail_scale = max(
            0.001,
            param_float(
                data, "NormalDetailScale", scalar_defaults["NormalDetailScale"]
            ),
        )
        normal_detail_intensity = max(
            0.0,
            param_float(
                data, "NormalDetailIntensity", scalar_defaults["NormalDetailIntensity"]
            ),
        )
        ior = max(
            1.0,
            param_float(
                data, "IndexOfRefraction", scalar_defaults["IndexOfRefraction"]
            ),
        )
        foam_size = max(
            0.001, param_float(data, "FoamSize", scalar_defaults["FoamSize"])
        )
        foam_intensity = max(
            0.0, param_float(data, "FoamIntensity", scalar_defaults["FoamIntensity"])
        )
        scattering_color = param_color(
            data,
            "ScatteringColor",
            (59.0 / 255.0, 153.0 / 255.0, 153.0 / 255.0, 51.0 / 255.0),
        )
        foam_color = param_color(
            data,
            "FoamColor",
            (202.0 / 255.0, 202.0 / 255.0, 202.0 / 255.0, 1.0),
        )
        choppiness = param_vector(data, "Choppiness", (-40.0, -40.0, 40.0, 1.0))

        water_uv_scale = (
            _WATER_PATCH_EDGES / (_WATER_PATCH_WORLD_SIZE * _FFT_RESOLUTION)
        ) * water_size
        height_scale = (float(choppiness[2]) / _PATCH_REFERENCE_CHOPPINESS_Z) * (
            _PATCH_REFERENCE_WATER_SIZE / water_size
        )

        scattering_alpha = clamp01(scattering_color[3])
        scattering_rgb = [
            clamp01(channel * scattering_alpha) for channel in scattering_color[:3]
        ]
        attenuation = tuple(
            clamp01(math.exp(-scattering_depth * clamp01(1.0 - channel)))
            for channel in scattering_rgb
        ) + (1.0,)

        roots = (self.ProjPath, self.BasePath)
        patch_data = _read_water_patch_mesh(self.MeshPath, roots)
        patch_image = _water_patch_image(patch_data)
        water_map_image = self._load_image(
            param_texture_path(data, "WaterMap"), non_color=True
        )
        foam_image = self._load_image(
            param_texture_path(data, "FoamTexture"), non_color=True
        )

        _set_material_transparency(Mat)
        _set_displacement_method(Mat, "BOTH")

        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

        output = new_labeled_node(
            nodes, "ShaderNodeOutputMaterial", "Material Output", (1600, 120)
        )
        water = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Water Surface", (1130, 180)
        )
        foam = new_labeled_node(
            nodes, "ShaderNodeBsdfPrincipled", "Foam Surface", (1130, 520)
        )
        mix = new_labeled_node(
            nodes, "ShaderNodeMixShader", "Water and Foam", (1390, 240)
        )
        link_sockets(links, find_output(water, "BSDF"), mix.inputs["Shader"])
        link_sockets(
            links,
            find_output(foam, "BSDF"),
            shader_nodes.socket_by_identifier(mix.inputs, "Shader_001"),
        )
        link_sockets(links, find_output(mix, "Shader"), find_input(output, "Surface"))

        set_input_value(water, attenuation, "Base Color")
        set_input_value(water, 0.0, "Metallic")
        set_input_value(water, _WATER_ROUGHNESS, "Roughness")
        set_input_value(water, ior, "IOR")
        set_input_value(water, 1.0, "Transmission Weight", "Transmission")
        set_input_value(water, 1.0, "Alpha")
        set_input_value(water, 0.0, "Coat Weight", "Clearcoat")
        set_input_value(water, 0.0, "Sheen Weight", "Sheen")

        set_input_value(foam, foam_color, "Base Color")
        set_input_value(foam, 0.0, "Metallic")
        set_input_value(foam, 0.0, "Transmission Weight", "Transmission")
        set_input_value(foam, 1.0, "Alpha")
        set_input_value(foam, 0.0, "Coat Weight", "Clearcoat")
        set_input_value(foam, 0.0, "Sheen Weight", "Sheen")

        Mat.diffuse_color = attenuation

        geometry = new_labeled_node(
            nodes, "ShaderNodeNewGeometry", "World Water Coordinates", (-1880, 100)
        )
        world_position = find_output(geometry, "Position")
        time_value = new_labeled_node(
            nodes, "ShaderNodeValue", "Water Time", (-1880, -660)
        )
        set_scene_fps_driver(
            time_value.outputs["Value"].driver_add("default_value").driver
        )

        shore_mask = _build_shore_mask(
            nodes,
            links,
            world_position,
            water_map_image,
            map_weight,
            shore_offset,
            shore_threshold,
        )
        wave_cutoff, view_distance = _build_wave_cutoff(nodes, links)

        base_height = None
        detail_height = None
        if patch_data is not None and patch_image is not None:
            frame_offsets = _build_patch_frame_offsets(
                nodes,
                links,
                find_output(time_value, "Value"),
                patch_data,
                (-2880, -760),
            )
            base_height, _ = _build_patch_sample(
                nodes,
                links,
                patch_image,
                world_position,
                frame_offsets,
                patch_data,
                (-2880, -120),
                "Water Patch Height",
            )

            detail_coordinate = shader_nodes.vector_math(
                nodes,
                links,
                "SCALE",
                name="Water Detail Coordinates",
                location=(-2880, 300),
            ).node
            detail_coordinate.inputs["Scale"].default_value = normal_detail_scale
            link_sockets(links, world_position, detail_coordinate.inputs["Vector"])
            detail_height, _ = _build_patch_sample(
                nodes,
                links,
                patch_image,
                find_output(detail_coordinate, "Vector"),
                frame_offsets,
                patch_data,
                (-2880, 520),
                "Water Detail Height",
            )

            height_amplitude = shader_nodes.math(
                nodes, links, "MULTIPLY", name="Water Height Scale", location=(80, -470)
            ).node
            shader_nodes.socket_by_identifier(
                height_amplitude.inputs, "Value_001"
            ).default_value = height_scale
            link_sockets(links, base_height, height_amplitude.inputs["Value"])

            displacement_shore = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                name="Water Displacement Shore Mask",
                location=(300, -470),
            ).node
            link_sockets(
                links,
                find_output(height_amplitude, "Value"),
                displacement_shore.inputs["Value"],
            )
            link_sockets(
                links,
                shore_mask,
                shader_nodes.socket_by_identifier(
                    displacement_shore.inputs, "Value_001"
                ),
            )

            displacement_cutoff = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                name="Water Displacement Cutoff",
                location=(520, -470),
            ).node
            link_sockets(
                links,
                find_output(displacement_shore, "Value"),
                displacement_cutoff.inputs["Value"],
            )
            link_sockets(
                links,
                wave_cutoff,
                shader_nodes.socket_by_identifier(
                    displacement_cutoff.inputs, "Value_001"
                ),
            )

            displacement = new_labeled_node(
                nodes,
                "ShaderNodeDisplacement",
                "Water Vertical Displacement",
                (1140, -340),
            )
            displacement.inputs["Midlevel"].default_value = 0.0
            displacement.inputs["Scale"].default_value = 1.0
            link_sockets(
                links,
                find_output(displacement_cutoff, "Value"),
                displacement.inputs["Height"],
            )
            link_sockets(
                links,
                find_output(displacement, "Displacement"),
                find_input(output, "Displacement"),
            )

            shore_normal = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY_ADD",
                name="Shore Normal Scale",
                location=(300, -90),
            ).node
            shader_nodes.socket_by_identifier(
                shore_normal.inputs, "Value_001"
            ).default_value = 0.9
            shader_nodes.socket_by_identifier(
                shore_normal.inputs, "Value_002"
            ).default_value = 0.1
            shore_normal.use_clamp = True
            link_sockets(links, shore_mask, shore_normal.inputs["Value"])

            base_bump = new_labeled_node(
                nodes, "ShaderNodeBump", "Water Patch Normal", (750, -30)
            )
            base_bump.inputs["Distance"].default_value = 1.0
            link_sockets(
                links, find_output(shore_normal, "Value"), base_bump.inputs["Strength"]
            )
            link_sockets(
                links,
                find_output(height_amplitude, "Value"),
                base_bump.inputs["Height"],
            )

            detail_normal_height = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                name="Water Detail Normal Height",
                location=(300, 150),
            ).node
            shader_nodes.socket_by_identifier(
                detail_normal_height.inputs, "Value_001"
            ).default_value = height_scale
            link_sockets(links, detail_height, detail_normal_height.inputs["Value"])

            detail_strength = shader_nodes.math(
                nodes,
                links,
                "MULTIPLY",
                name="Water Detail Normal Strength",
                location=(520, 90),
            ).node
            shader_nodes.socket_by_identifier(
                detail_strength.inputs, "Value_001"
            ).default_value = normal_detail_intensity
            link_sockets(
                links,
                find_output(shore_normal, "Value"),
                detail_strength.inputs["Value"],
            )

            detail_bump = new_labeled_node(
                nodes, "ShaderNodeBump", "Water Detail Normal", (920, 30)
            )
            detail_bump.inputs["Distance"].default_value = 1.0
            link_sockets(
                links,
                find_output(detail_strength, "Value"),
                detail_bump.inputs["Strength"],
            )
            link_sockets(
                links,
                find_output(detail_normal_height, "Value"),
                detail_bump.inputs["Height"],
            )
            link_sockets(
                links, find_output(base_bump, "Normal"), detail_bump.inputs["Normal"]
            )
            final_normal = find_output(detail_bump, "Normal")
            link_sockets(links, final_normal, find_input(water, "Normal"))
            link_sockets(links, final_normal, find_input(foam, "Normal"))

        foam_opacity, foam_roughness = _build_foam(
            nodes,
            links,
            world_position,
            view_distance,
            shore_mask,
            water_uv_scale,
            foam_image,
            foam_size,
            foam_intensity,
        )
        link_sockets(links, foam_opacity, mix.inputs["Factor"])
        link_sockets(links, foam_roughness, find_input(foam, "Roughness"))

        visible_parameters = (
            "WaterSize",
            "WaterMapWeight",
            "ShoreOffset",
            "ShoreThreshold",
            "NormalDetailScale",
            "NormalDetailIntensity",
            "ScatteringDepth",
            "ScatteringSunRadius",
            "ScatteringSunIntensity",
            "ScatteringSlopeThreshold",
            "ScatteringSlopeIntensity",
            "IndexOfRefraction",
            "RefractionNormalIntensity",
            "FoamSize",
            "FoamThreshold",
            "FoamIntensity",
            "EdgeBlend",
        )
        for index, name in enumerate(visible_parameters):
            value_node = new_labeled_node(
                nodes,
                "ShaderNodeValue",
                name,
                (-1840 + (index % 4) * 190, -1220 - (index // 4) * 95),
            )
            value_node.outputs["Value"].default_value = param_float(
                data, name, scalar_defaults[name]
            )
