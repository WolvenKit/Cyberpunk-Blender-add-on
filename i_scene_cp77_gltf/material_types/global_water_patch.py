import hashlib
import math
import os
<<<<<<< Updated upstream
import re
from pathlib import Path

import bpy
from ..blender.transactions import new_tracked_datablock
import numpy as np

from ..assetio.documents import file_identity
from ..materials.resources import load_material_document
from ..assetio.resolver import resolve_asset_path

from .mat_common import (
    MaterialTypeBase,
    clamp01,
=======
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
>>>>>>> Stashed changes
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

<<<<<<< Updated upstream

_TEMPLATE_PATH = "engine\\materials\\global_water_patch.mt"
_PREVIEW_TAG = "AUTHORED_HEIGHT_FFT_FRESNEL_FOAM_V3_EEVEE_NEXT"

_FFT_DEFAULTS = {
    "generator": "CRenderSimWaterFFT",
    "amplitude": 20.0,
    "lambda": 0.5,
    "windDir": 0.0,
    "windScale": 1.0,
    "windSpeed": 10.0,
    "width": 512,
    "height": 512,
    "effectiveFormat": "R16G16B16A16_Float",
}

_SIM_DEFAULTS = {
    "generator": "CRenderSimWaterImpulse",
    "resolution": 1024,
    "simulationSpeed": 24.0,
    "width": 256,
    "height": 256,
}

_WATER_PATCH_IMAGE_CACHE = {}


def _scale_color(color, factor):
    return tuple(clamp01(component * factor) for component in color[:3]) + (color[3],)


def _mix_color_value(first, second, factor):
    factor = clamp01(factor)
    return tuple(
        clamp01(first[index] * (1.0 - factor) + second[index] * factor)
        for index in range(3)
    ) + (first[3] * (1.0 - factor) + second[3] * factor,)


def _lift_color(color, target_peak):
    # ScatteringColor is a dark subsurface tint; used directly as a surface base colour it reads as
    # dark paint under EEVEE. Lift its value toward target_peak while preserving hue.
    peak = max(color[0], color[1], color[2], 1e-4)
    if peak >= target_peak:
        return color
    factor = target_peak / peak
    return tuple(clamp01(component * factor) for component in color[:3]) + (color[3],)


def _surface_response(scattering_depth, blur_radius, blur_strength, normal_intensity, opacity):
    depth_roughness = min(max(scattering_depth, 0.0) * 0.008, 0.08)
    # Kept below the EEVEE Next raytrace roughness cutoff (~0.2) so refraction survives; see
    # EEVEE Next ray-tracing overpower report blender/blender#124643.
    roughness = clamp01(
        0.08
        + max(blur_radius, 0.0) * 0.02
        + max(blur_strength, 0.0) * 0.04
        + max(normal_intensity, 0.0) * 0.012
        + depth_roughness,
        0.06,
        0.28,
    )
    # Kept modest: depth colour is carried by the surface scattering tint (no Volume output), so the
    # water must read as its own colour, not as a see-through pane onto a dark box or dark world.
    transmission = clamp01(
        0.20
        + 0.30 / (1.0 + max(scattering_depth, 0.0) * 0.35)
        - max(blur_strength, 0.0) * 0.03,
        0.15,
        0.42,
    ) * clamp01(opacity)
    specular_level = clamp01(
        0.5 - max(blur_radius, 0.0) * 0.015 - max(blur_strength, 0.0) * 0.025,
        0.35,
        0.5,
    )
    micro_roughness = clamp01(
        0.03 + max(normal_intensity, 0.0) * 0.03 + max(blur_strength, 0.0) * 0.02,
        0.02,
        0.12,
    )
    return roughness, transmission, specular_level, micro_roughness


def _needs_raytracing_hint(material):
    # Refraction requires the scene ray-tracing pipeline (Properties > Render > Raytracing). That is
    # a scene-level toggle, so it is left to the user rather than mutated from a material builder.
    material["cp77_water_needs_scene_raytracing"] = True


def _set_displacement_method(material, method="BOTH"):
    # The displacement enum moved between material and material.cycles across 4.x/5.x; EEVEE Next
    # collapses DISPLACEMENT to BOTH internally, so BOTH is the safe request on either holder.
    for holder in (material, getattr(material, "cycles", None)):
        if holder is not None and hasattr(holder, "displacement_method"):
            try:
                holder.displacement_method = method
                return True
            except (TypeError, ValueError):
                continue
=======
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
>>>>>>> Stashed changes
    return False


def _set_material_transparency(material):
    material.use_nodes = True
<<<<<<< Updated upstream
    if hasattr(material, "surface_render_method"):
        try:
            material.surface_render_method = "DITHERED"
        except (TypeError, ValueError):
            pass
    if hasattr(material, "blend_method"):
        try:
            material.blend_method = "HASHED"
        except (TypeError, ValueError):
            pass
    for attr in ("use_screen_refraction", "use_raytrace_refraction"):
        if hasattr(material, attr):
            try:
                setattr(material, attr, True)
            except (TypeError, ValueError):
                pass
    if hasattr(material, "use_transparency_overlap"):
        material.use_transparency_overlap = False
=======
    material.surface_render_method = "DITHERED"
    material.use_raytrace_refraction = True
    if hasattr(material, "use_transparency_overlap"):
        material.use_transparency_overlap = True
>>>>>>> Stashed changes
    if hasattr(material, "use_backface_culling"):
        material.use_backface_culling = False


<<<<<<< Updated upstream
def _safe_resource_parts(resource_path):
    return [
        part
        for part in re.split(r"[\\/]+", resource_path or "")
        if part and part not in (".", "..")
    ]


def _expanded_resource_roots(roots):
    # MaterialBuilder supplies the exact project raw root and material depot root.
=======
def _expanded_resource_roots(roots):
>>>>>>> Stashed changes
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


<<<<<<< Updated upstream
def _resolve_json_sidecar(references, roots, extension=None):
=======
def _resolve_json_sidecar(references, roots):
>>>>>>> Stashed changes
    expanded_roots = _expanded_resource_roots(roots)
    for reference in references:
        if not reference:
            continue
<<<<<<< Updated upstream
        target_extension = extension or _json_extension(reference)
        resolved = resolve_asset_path(
            reference,
            roots=expanded_roots,
            extensions=(target_extension,),
=======
        resolved = resolve_asset_path(
            reference,
            roots=expanded_roots,
            extensions=(_json_extension(reference),),
>>>>>>> Stashed changes
            warn=False,
        )
        if resolved:
            return resolved
    return ""


<<<<<<< Updated upstream
def _resource_json_references(resource_path):
    parts = _safe_resource_parts(resource_path)
    if not parts:
        return ()
    relative = os.path.join(*parts)
    if not relative.lower().endswith(".json"):
        relative += ".json"
    return relative, os.path.basename(relative)


def _read_dynamic_texture(resource_path, roots, defaults):
    result = dict(defaults)
    result["resourcePath"] = resource_path
    result["sidecarPath"] = ""

    references = _resource_json_references(resource_path)
    candidate = _resolve_json_sidecar(
        references,
        roots,
        extension=_json_extension(references[0]) if references else ".json",
    )
    if candidate:
        try:
            resource = load_material_document(candidate)
            root = resource.root if resource is not None else {}
            generator = root.get("generator", {})
            generator_data = generator.get("Data", {}) if isinstance(generator, dict) else {}
            for key, value in generator_data.items():
                if key == "$type":
                    result["generator"] = value
                elif isinstance(value, (int, float, str, bool)):
                    result[key] = value
            for key in ("width", "height", "dataFormat", "mipChain", "samplesCount"):
                if key in root:
                    result[key] = root[key]
            result["sidecarPath"] = candidate
        except (ValueError, TypeError, KeyError) as exc:
            print(f"Failed to read dynamic water texture metadata {candidate}: {exc}")

    if result.get("generator") == "CRenderSimWaterFFT":
        result.setdefault("effectiveFormat", "R16G16B16A16_Float")
    return result


=======
>>>>>>> Stashed changes
def _mesh_json_references(mesh_path):
    references = []

    def add(candidate):
        if not candidate:
            return
<<<<<<< Updated upstream
        candidate = os.path.normpath(os.path.abspath(os.path.expanduser(str(candidate))))
        if candidate not in references:
            references.append(candidate)

    if mesh_path:
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

=======
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
>>>>>>> Stashed changes
    return tuple(references)


def _water_patch_parameter(payload):
    root = payload.get("Data", {}).get("RootChunk", {})
    for parameter in root.get("parameters", []):
        data = parameter.get("Data", {}) if isinstance(parameter, dict) else {}
        if data.get("$type") == "meshMeshParamWaterPatchData":
            return root, data
    return root, None


def _read_water_patch_mesh(mesh_path, roots):
<<<<<<< Updated upstream
    references = _mesh_json_references(mesh_path)
    candidate = _resolve_json_sidecar(
        references,
        roots,
    )
    if not candidate:
        return None
    try:
=======
    candidate = _resolve_json_sidecar(_mesh_json_references(mesh_path), roots)
    if not candidate:
        return None
    try:
        identity = file_identity(candidate).key
        cached = _WATER_PATCH_DATA_CACHE.get(identity)
        if cached is not None:
            return dict(cached)
>>>>>>> Stashed changes
        resource = load_material_document(candidate)
        payload = resource.payload if resource is not None else {}
        root, parameter = _water_patch_parameter(payload)
        if not parameter:
            return None

        rows = parameter.get("nodes", {}).get("Elements", [])
        if not rows:
            return None
<<<<<<< Updated upstream
        samples_per_point = len(rows[0].get("Elements", []))
=======
        frame_count = len(rows[0].get("Elements", []))
>>>>>>> Stashed changes
        point_count = len(rows)
        grid_size = int(round(math.sqrt(point_count)))
        if (
            grid_size * grid_size != point_count
<<<<<<< Updated upstream
            or samples_per_point <= 0
            or any(len(row.get("Elements", [])) != samples_per_point for row in rows)
        ):
            print(
                "Ignoring unsupported water patch data layout "
                f"{point_count}x{samples_per_point} in {candidate}"
=======
            or frame_count <= 0
            or any(len(row.get("Elements", [])) != frame_count for row in rows)
        ):
            _LOG.warning(
                "Ignoring unsupported water patch data layout %sx%s in %s",
                point_count,
                frame_count,
                candidate,
>>>>>>> Stashed changes
            )
            return None

        samples = np.asarray(
            [row["Elements"] for row in rows],
            dtype=np.float32,
<<<<<<< Updated upstream
        ).reshape(grid_size, grid_size, samples_per_point)
=======
        ).reshape(grid_size, grid_size, frame_count)
>>>>>>> Stashed changes

        bounds = root.get("boundingBox", {})
        minimum = bounds.get("Min", {})
        maximum = bounds.get("Max", {})
        patch_size_x = abs(float(maximum.get("X", 5.0)) - float(minimum.get("X", -5.0)))
        patch_size_y = abs(float(maximum.get("Y", 5.0)) - float(minimum.get("Y", -5.0)))
<<<<<<< Updated upstream
        patch_size_x = patch_size_x if patch_size_x > 1e-6 else 10.0
        patch_size_y = patch_size_y if patch_size_y > 1e-6 else 10.0
=======
        patch_size_x = (
            patch_size_x if patch_size_x > 1.0e-6 else _WATER_PATCH_WORLD_SIZE
        )
        patch_size_y = (
            patch_size_y if patch_size_y > 1.0e-6 else _WATER_PATCH_WORLD_SIZE
        )
>>>>>>> Stashed changes

        edge_error = max(
            float(np.max(np.abs(samples[:, 0, :] - samples[:, -1, :]))),
            float(np.max(np.abs(samples[0, :, :] - samples[-1, :, :]))),
        )
<<<<<<< Updated upstream

        return {
            "sidecarPath": candidate,
            "samples": samples,
            "gridSize": grid_size,
            "frameCount": samples_per_point,
            "animLength": max(1e-6, float(parameter.get("animLength", 1.0))),
=======
        samples = np.frombuffer(samples.tobytes(), dtype=np.float32).reshape(
            samples.shape
        )
        decoded = {
            "sidecarPath": candidate,
            "samples": samples,
            "gridSize": grid_size,
            "frameCount": frame_count,
            "animLength": max(1.0e-6, float(parameter.get("animLength", 1.0))),
>>>>>>> Stashed changes
            "animLoop": int(parameter.get("animLoop", 0)),
            "patchSizeX": patch_size_x,
            "patchSizeY": patch_size_y,
            "heightMin": float(np.min(samples)),
            "heightMax": float(np.max(samples)),
            "edgeError": edge_error,
        }
<<<<<<< Updated upstream
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Failed to read water patch mesh data {candidate}: {exc}")
        return None



def _atlas_geometry(frame_count):
    columns = int(math.ceil(math.sqrt(frame_count)))
    rows = int(math.ceil(frame_count / columns))
    return columns, rows


=======
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


>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
    columns, rows = _atlas_geometry(frame_count)
    width = grid_size * columns
    height = grid_size * rows

    height_min = patch_data["heightMin"]
    height_max = patch_data["heightMax"]
    height_range = max(height_max - height_min, 1e-8)
=======
    columns = int(math.ceil(math.sqrt(frame_count)))
    rows = int(math.ceil(frame_count / columns))
    width = grid_size * columns
    height = grid_size * rows
    height_min = patch_data["heightMin"]
    height_max = patch_data["heightMax"]
    height_range = max(height_max - height_min, 1.0e-8)
>>>>>>> Stashed changes

    atlas = np.zeros((height, width, 4), dtype=np.float32)
    atlas[:, :, 3] = 1.0
    for frame in range(frame_count):
        tile_x = frame % columns
        tile_y = frame // columns
<<<<<<< Updated upstream
        # samples[:, :, frame] is [tileX, tileY]; the sampler feeds world X into U (column) and
        # world Y into V (row), so the tile is stored transposed to keep X<->tileX, Y<->tileY.
        frame_data = ((samples[:, :, frame] - height_min) / height_range).T
        y0 = tile_y * grid_size
        x0 = tile_x * grid_size
        atlas[y0:y0 + grid_size, x0:x0 + grid_size, 0] = frame_data
        atlas[y0:y0 + grid_size, x0:x0 + grid_size, 1] = frame_data
        atlas[y0:y0 + grid_size, x0:x0 + grid_size, 2] = frame_data
=======
        frame_data = ((samples[:, :, frame] - height_min) / height_range).T
        y0 = tile_y * grid_size
        x0 = tile_x * grid_size
        atlas[y0 : y0 + grid_size, x0 : x0 + grid_size, :3] = frame_data[:, :, None]
>>>>>>> Stashed changes

    digest = hashlib.sha1(sidecar_path.encode("utf-8")).hexdigest()[:12]
    image_name = "CP77 Water Patch " + digest
    image = bpy.data.images.get(image_name)
    if image is None or tuple(image.size) != (width, height):
        if image is not None:
            bpy.data.images.remove(image)
<<<<<<< Updated upstream
        image = new_tracked_datablock("images", image_name, width=width, height=height, alpha=True, float_buffer=True)
=======
        image = new_tracked_datablock(
            "images",
            image_name,
            width=width,
            height=height,
            alpha=True,
            float_buffer=True,
        )
>>>>>>> Stashed changes
    image.colorspace_settings.name = "Non-Color"
    image.alpha_mode = "CHANNEL_PACKED"
    image.pixels.foreach_set(np.ascontiguousarray(atlas).reshape(-1))
    image.update()
    try:
        image.pack()
    except RuntimeError:
        pass

<<<<<<< Updated upstream
    patch_data["atlasColumns"] = columns
    patch_data["atlasRows"] = rows
    patch_data["atlasWidth"] = width
    patch_data["atlasHeight"] = height
=======
>>>>>>> Stashed changes
    patch_data["imageName"] = image.name
    _WATER_PATCH_IMAGE_CACHE[cache_key] = image.name
    return image


<<<<<<< Updated upstream
def _build_water_patch_atlas_sample(nodes, links, image, world_position, time_output, patch_data, location):
    x, y = location
    grid_size = float(patch_data["gridSize"])
    frame_count = float(patch_data["frameCount"])
    # Derive the atlas layout locally so a warm image cache (which skips the writer) cannot leave
    # atlasColumns/atlasRows unset on a freshly read patch_data.
    columns, rows = _atlas_geometry(patch_data["frameCount"])
    columns = float(columns)
    rows = float(rows)
    anim_length = float(patch_data["animLength"])

    patch_mapping = new_labeled_node(nodes, "ShaderNodeMapping", "Authored Water Patch Mapping", (x, y))
    patch_mapping.vector_type = "POINT"
    set_input_value(patch_mapping, (1.0 / patch_data["patchSizeX"], 1.0 / patch_data["patchSizeY"], 1.0), "Scale")
    link_sockets(links, world_position, find_input(patch_mapping, "Vector"))

    patch_fraction = new_labeled_node(nodes, "ShaderNodeVectorMath", "Authored Water Patch Wrap", (x + 210, y))
    patch_fraction.operation = "FRACTION"
    link_sockets(links, find_output(patch_mapping, "Vector"), patch_fraction.inputs[0])

    texel_scale = new_labeled_node(nodes, "ShaderNodeVectorMath", "Authored Water Patch Texel Scale", (x + 420, y))
    texel_scale.operation = "MULTIPLY"
    edge_scale = (grid_size - 1.0) / grid_size
    texel_scale.inputs[1].default_value = (edge_scale, edge_scale, 1.0)
    link_sockets(links, find_output(patch_fraction, "Vector"), texel_scale.inputs[0])

    texel_center = new_labeled_node(nodes, "ShaderNodeVectorMath", "Authored Water Patch Texel Center", (x + 630, y))
    texel_center.operation = "ADD"
    texel_center.inputs[1].default_value = (0.5 / grid_size, 0.5 / grid_size, 0.0)
    link_sockets(links, find_output(texel_scale, "Vector"), texel_center.inputs[0])
    local_uv = find_output(texel_center, "Vector")

    cycle = new_labeled_node(nodes, "ShaderNodeMath", "Water Patch Animation Cycle", (x, y - 250))
    cycle.operation = "DIVIDE"
    cycle.inputs[1].default_value = anim_length
    link_sockets(links, time_output, cycle.inputs[0])

    cycle_fraction = new_labeled_node(nodes, "ShaderNodeMath", "Water Patch Animation Wrap", (x + 190, y - 250))
    cycle_fraction.operation = "FRACT"
    link_sockets(links, find_output(cycle, "Value"), cycle_fraction.inputs[0])

    frame_position = new_labeled_node(nodes, "ShaderNodeMath", "Water Patch Frame Position", (x + 380, y - 250))
    frame_position.operation = "MULTIPLY"
    frame_position.inputs[1].default_value = frame_count
    link_sockets(links, find_output(cycle_fraction, "Value"), frame_position.inputs[0])

    frame_floor = new_labeled_node(nodes, "ShaderNodeMath", "Water Patch Frame", (x + 570, y - 250))
    frame_floor.operation = "FLOOR"
    link_sockets(links, find_output(frame_position, "Value"), frame_floor.inputs[0])

    frame_blend = new_labeled_node(nodes, "ShaderNodeMath", "Water Patch Frame Blend", (x + 570, y - 360))
    frame_blend.operation = "FRACT"
    link_sockets(links, find_output(frame_position, "Value"), frame_blend.inputs[0])

    frame_next_add = new_labeled_node(nodes, "ShaderNodeMath", "Water Patch Next Frame", (x + 760, y - 250))
    frame_next_add.operation = "ADD"
    frame_next_add.inputs[1].default_value = 1.0
    link_sockets(links, find_output(frame_floor, "Value"), frame_next_add.inputs[0])

    frame_next = new_labeled_node(nodes, "ShaderNodeMath", "Water Patch Next Frame Wrap", (x + 950, y - 250))
    frame_next.operation = "MODULO"
    frame_next.inputs[1].default_value = frame_count
    link_sockets(links, find_output(frame_next_add, "Value"), frame_next.inputs[0])

    def atlas_vector(frame_output, name, node_y):
        column = new_labeled_node(nodes, "ShaderNodeMath", f"{name} Column", (x + 760, node_y))
        column.operation = "MODULO"
        column.inputs[1].default_value = columns
        link_sockets(links, frame_output, column.inputs[0])

        row_divide = new_labeled_node(nodes, "ShaderNodeMath", f"{name} Row Divide", (x + 760, node_y - 90))
        row_divide.operation = "DIVIDE"
        row_divide.inputs[1].default_value = columns
        link_sockets(links, frame_output, row_divide.inputs[0])

        row = new_labeled_node(nodes, "ShaderNodeMath", f"{name} Row", (x + 950, node_y - 90))
        row.operation = "FLOOR"
        link_sockets(links, find_output(row_divide, "Value"), row.inputs[0])

        offset = new_labeled_node(nodes, "ShaderNodeCombineXYZ", f"{name} Offset", (x + 1140, node_y))
        link_sockets(links, find_output(column, "Value"), offset.inputs["X"])
        link_sockets(links, find_output(row, "Value"), offset.inputs["Y"])

        add = new_labeled_node(nodes, "ShaderNodeVectorMath", f"{name} Atlas Tile", (x + 1330, node_y))
        add.operation = "ADD"
        link_sockets(links, local_uv, add.inputs[0])
        link_sockets(links, find_output(offset, "Vector"), add.inputs[1])

        scale = new_labeled_node(nodes, "ShaderNodeVectorMath", f"{name} Atlas Scale", (x + 1520, node_y))
        scale.operation = "MULTIPLY"
        scale.inputs[1].default_value = (1.0 / columns, 1.0 / rows, 1.0)
        link_sockets(links, find_output(add, "Vector"), scale.inputs[0])
        return find_output(scale, "Vector")

    current_vector = atlas_vector(find_output(frame_floor, "Value"), "Current Water Patch Frame", y - 500)
    next_vector = atlas_vector(find_output(frame_next, "Value"), "Next Water Patch Frame", y - 780)

    current_texture = new_labeled_node(nodes, "ShaderNodeTexImage", "Current Authored Water Height", (x + 1740, y - 500))
    current_texture.image = image
    current_texture.interpolation = "Linear"
    current_texture.extension = "EXTEND"
    link_sockets(links, current_vector, find_input(current_texture, "Vector"))

    next_texture = new_labeled_node(nodes, "ShaderNodeTexImage", "Next Authored Water Height", (x + 1740, y - 780))
    next_texture.image = image
    next_texture.interpolation = "Linear"
    next_texture.extension = "EXTEND"
    link_sockets(links, next_vector, find_input(next_texture, "Vector"))

    blend = new_labeled_node(nodes, "ShaderNodeMixRGB", "Interpolated Authored Water Height", (x + 1960, y - 620))
    blend.blend_type = "MIX"
    link_sockets(links, find_output(frame_blend, "Value"), blend.inputs[0])
    link_sockets(links, find_output(current_texture, "Color"), blend.inputs[1])
    link_sockets(links, find_output(next_texture, "Color"), blend.inputs[2])

    decode_scale = new_labeled_node(nodes, "ShaderNodeMath", "Authored Water Height Range", (x + 2180, y - 620))
    decode_scale.operation = "MULTIPLY"
    decode_scale.inputs[1].default_value = patch_data["heightMax"] - patch_data["heightMin"]
    link_sockets(links, find_output(blend, "Color"), decode_scale.inputs[0])

    decode_bias = new_labeled_node(nodes, "ShaderNodeMath", "Authored Water Height Bias", (x + 2370, y - 620))
    decode_bias.operation = "ADD"
    decode_bias.inputs[1].default_value = patch_data["heightMin"]
    link_sockets(links, find_output(decode_scale, "Value"), decode_bias.inputs[0])

    return find_output(decode_bias, "Value"), find_output(blend, "Color")


def _store_metadata(material, data, scalar_names, color_names, texture_names, fft_data, sim_data):
    material["cp77_water_template"] = _TEMPLATE_PATH
    for name, default in scalar_names.items():
        material[f"cp77_{name}"] = param_float(data, name, default)
    for name, default in color_names.items():
        material[f"cp77_{name}"] = list(param_color(data, name, default))
    for name in texture_names:
        material[f"cp77_{name}"] = param_texture_path(data, name)
    material["cp77_Choppiness"] = list(param_vector(data, "Choppiness", (-40.0, -40.0, 40.0, 1.0)))
    for prefix, values in (("WaterFFT", fft_data), ("WaterSim", sim_data)):
        for key, value in values.items():
            if isinstance(value, (str, int, float, bool)):
                material[f"cp77_{prefix}_{key}"] = value
=======
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
>>>>>>> Stashed changes


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
<<<<<<< Updated upstream
        color_defaults = {
            "ScatteringColor": (59.0 / 255.0, 153.0 / 255.0, 153.0 / 255.0, 51.0 / 255.0),
            "FoamColor": (202.0 / 255.0, 202.0 / 255.0, 202.0 / 255.0, 1.0),
        }
        texture_names = ("WaterFFT", "WaterSim", "WaterMap", "FoamTexture")

        water_size = max(0.001, param_float(data, "WaterSize", scalar_defaults["WaterSize"]))
        map_weight = clamp01(param_float(data, "WaterMapWeight", scalar_defaults["WaterMapWeight"]))
        shore_threshold = param_float(data, "ShoreThreshold", scalar_defaults["ShoreThreshold"])
        shore_offset = param_float(data, "ShoreOffset", scalar_defaults["ShoreOffset"])
        skip_simulated_normals = clamp01(param_float(data, "Hack_SkipSimulatedNormals", 0.0))
        scattering_depth = max(0.0, param_float(data, "ScatteringDepth", scalar_defaults["ScatteringDepth"]))
        normal_scale = max(0.001, param_float(data, "NormalDetailScale", scalar_defaults["NormalDetailScale"]))
        normal_intensity = max(0.0, param_float(data, "NormalDetailIntensity", scalar_defaults["NormalDetailIntensity"]))
        sun_radius = max(0.001, param_float(data, "ScatteringSunRadius", scalar_defaults["ScatteringSunRadius"]))
        sun_intensity = max(0.0, param_float(data, "ScatteringSunIntensity", scalar_defaults["ScatteringSunIntensity"]))
        slope_threshold = max(0.0, param_float(data, "ScatteringSlopeThreshold", scalar_defaults["ScatteringSlopeThreshold"]))
        slope_intensity = max(0.0, param_float(data, "ScatteringSlopeIntensity", scalar_defaults["ScatteringSlopeIntensity"]))
        opacity = clamp01(param_float(data, "WaterOpacity", scalar_defaults["WaterOpacity"]))
        ior = max(1.0, param_float(data, "IndexOfRefraction", scalar_defaults["IndexOfRefraction"]))
        refraction_normal = max(0.0, param_float(data, "RefractionNormalIntensity", scalar_defaults["RefractionNormalIntensity"]))
        blur_radius = max(0.0, param_float(data, "BlurRadius", scalar_defaults["BlurRadius"]))
        blur_strength = max(0.0, param_float(data, "BlurStrength", scalar_defaults["BlurStrength"]))
        foam_size = max(0.001, param_float(data, "FoamSize", scalar_defaults["FoamSize"]))
        foam_threshold = max(0.0, param_float(data, "FoamThreshold", scalar_defaults["FoamThreshold"]))
        foam_intensity = max(0.0, param_float(data, "FoamIntensity", scalar_defaults["FoamIntensity"]))
        edge_blend = max(0.001, param_float(data, "EdgeBlend", scalar_defaults["EdgeBlend"]))
        scattering_color = param_color(data, "ScatteringColor", color_defaults["ScatteringColor"])
        foam_color = param_color(data, "FoamColor", color_defaults["FoamColor"])
        surface_tint = _lift_color(scattering_color, 0.55)
        choppiness = param_vector(data, "Choppiness", (-40.0, -40.0, 40.0, 1.0))

        water_fft_path = param_texture_path(data, "WaterFFT")
        water_sim_path = param_texture_path(data, "WaterSim")
        roots = (self.ProjPath, self.BasePath)
        fft_data = _read_dynamic_texture(water_fft_path, roots, _FFT_DEFAULTS)
        sim_data = _read_dynamic_texture(water_sim_path, roots, _SIM_DEFAULTS)
        patch_data = _read_water_patch_mesh(self.MeshPath, roots)
        patch_image = _water_patch_image(patch_data)

        _needs_raytracing_hint(Mat)
        _set_material_transparency(Mat)
        _set_displacement_method(Mat, "BOTH")
        _store_metadata(Mat, data, scalar_defaults, color_defaults, texture_names, fft_data, sim_data)

        water_map_path = param_texture_path(data, "WaterMap")
        foam_path = param_texture_path(data, "FoamTexture")
        water_map_image = self._load_image(water_map_path, non_color=True)
        foam_image = self._load_image(foam_path, non_color=True)
=======

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
>>>>>>> Stashed changes

        tree = Mat.node_tree
        nodes = tree.nodes
        links = tree.links
        nodes.clear()

<<<<<<< Updated upstream
        output = new_labeled_node(nodes, "ShaderNodeOutputMaterial", "Material Output", (1700, 80))
        principled = new_labeled_node(nodes, "ShaderNodeBsdfPrincipled", "Global Water Patch", (1380, 80))
        link_sockets(links, find_output(principled, "BSDF"), find_input(output, "Surface"))

        roughness, transmission, specular_level, micro_roughness_strength = _surface_response(
            scattering_depth, blur_radius, blur_strength, normal_intensity, opacity
        )

        set_input_value(principled, 0.0, "Metallic")
        set_input_value(principled, roughness, "Roughness")
        set_input_value(principled, ior, "IOR")
        set_input_value(principled, specular_level, "Specular IOR Level", "Specular")
        set_input_value(principled, transmission, "Transmission Weight", "Transmission")
        set_input_value(principled, 0.0, "Coat Weight", "Clearcoat")
        set_input_value(principled, 0.0, "Sheen Weight", "Sheen")
        set_input_value(principled, clamp01(scattering_depth / (scattering_depth + 4.0), 0.0, 0.75), "Diffuse Roughness")

        # Thickness replaced Refraction Depth in EEVEE Next; it scales how far raytraced transmission
        # bends. Present only on 4.2+, so set it defensively.
        thickness_socket = principled.inputs.get("Thickness")
        if thickness_socket is not None:
            thickness_socket.default_value = clamp01(0.15 + scattering_depth * 0.12, 0.1, 2.5)

        Mat.diffuse_color = (*surface_tint[:3], opacity)

        geometry = new_labeled_node(nodes, "ShaderNodeNewGeometry", "World Water Coordinates", (-1780, 180))
        world_position = find_output(geometry, "Position")

        water_map_world_size = 4096.0
        map_scale = new_labeled_node(nodes, "ShaderNodeVectorMath", "Water Map World Scale", (-1540, 500))
        map_scale.operation = "SCALE"
        map_scale.inputs[3].default_value = 1.0 / water_map_world_size
        link_sockets(links, world_position, map_scale.inputs[0])

        map_offset = new_labeled_node(nodes, "ShaderNodeVectorMath", "Water Map World Offset", (-1320, 500))
        map_offset.operation = "ADD"
        map_offset.inputs[1].default_value = (0.5, 0.5, 0.0)
        link_sockets(links, find_output(map_scale, "Vector"), map_offset.inputs[0])
        water_map_vector = find_output(map_offset, "Vector")

        time_value = new_labeled_node(nodes, "ShaderNodeValue", "Water Time", (-1700, -560))
        set_scene_fps_driver(time_value.outputs[0].driver_add("default_value").driver)
        sim_activity = new_labeled_node(nodes, "ShaderNodeValue", "WaterSim Activity", (-1700, -680))
        sim_activity.outputs[0].default_value = 0.0
        sim_activity.label = "Runtime impulse activity; animate manually for Blender preview"

        authored_height = None
        authored_height_normalized = None
        if patch_data is not None and patch_image is not None:
            authored_height, authored_height_normalized = _build_water_patch_atlas_sample(
                nodes, links, patch_image, world_position, find_output(time_value, "Value"), patch_data, (-2850, -120)
            )

        chop_xy = math.hypot(choppiness[0], choppiness[1])
        material_direction = math.atan2(choppiness[1], choppiness[0]) if chop_xy > 1e-6 else 0.0
        wave_direction = float(fft_data.get("windDir", 0.0)) + material_direction
        wind_speed = max(0.01, float(fft_data.get("windSpeed", 10.0)))
        wind_scale = max(0.01, float(fft_data.get("windScale", 1.0)))
        fft_amplitude = max(0.0, float(fft_data.get("amplitude", 20.0)))
        fft_lambda = max(0.001, float(fft_data.get("lambda", 0.5)))
        simulation_speed = max(0.0, float(sim_data.get("simulationSpeed", 24.0)))
        simulation_resolution = max(1.0, float(sim_data.get("resolution", 1024.0)))

        primary_phase = new_labeled_node(nodes, "ShaderNodeMath", "FFT Primary Phase", (-1450, -560))
        primary_phase.operation = "MULTIPLY"
        primary_phase.inputs[1].default_value = wind_speed * 0.35
        link_sockets(links, find_output(time_value, "Value"), primary_phase.inputs[0])

        secondary_phase = new_labeled_node(nodes, "ShaderNodeMath", "FFT Secondary Phase", (-1450, -680))
        secondary_phase.operation = "MULTIPLY"
        secondary_phase.inputs[1].default_value = -wind_speed * (0.16 + 0.12 * fft_lambda)
        link_sockets(links, find_output(time_value, "Value"), secondary_phase.inputs[0])

        detail_time = new_labeled_node(nodes, "ShaderNodeMath", "Water Detail Time", (-1450, -800))
        detail_time.operation = "MULTIPLY"
        detail_time.inputs[1].default_value = 0.18 + simulation_speed / 120.0
        link_sockets(links, find_output(time_value, "Value"), detail_time.inputs[0])

        primary_mapping = new_labeled_node(nodes, "ShaderNodeMapping", "Primary FFT Mapping", (-1450, 220))
        primary_mapping.vector_type = "POINT"
        set_input_value(primary_mapping, (0.0, 0.0, wave_direction), "Rotation")
        set_input_value(primary_mapping, (0.09 / water_size, 0.09 / water_size, 1.0), "Scale")
        link_sockets(links, world_position, find_input(primary_mapping, "Vector"))

        secondary_mapping = new_labeled_node(nodes, "ShaderNodeMapping", "Secondary FFT Mapping", (-1450, 20))
        secondary_mapping.vector_type = "POINT"
        set_input_value(secondary_mapping, (0.0, 0.0, wave_direction + 1.0471975512), "Rotation")
        set_input_value(secondary_mapping, (0.19 / water_size, 0.19 / water_size, 1.0), "Scale")
        link_sockets(links, world_position, find_input(secondary_mapping, "Vector"))

        # The engine's CRenderSimWaterFFT is a Tessendorf-style directional spectrum (Tessendorf,
        # "Simulating Ocean Water", 2001). It is approximated here with a pair of crossed animated
        # 4D noise fields instead of banded waves, which avoids the corduroy look on open water.
        primary_wave = new_labeled_node(nodes, "ShaderNodeTexNoise", "FFT Primary Swell", (-1180, 240))
        primary_wave.noise_dimensions = "4D"
        set_input_value(primary_wave, max(0.4, 1.1 * wind_scale), "Scale")
        set_input_value(primary_wave, 4.0, "Detail")
        set_input_value(primary_wave, 0.55, "Roughness")
        set_input_value(primary_wave, fft_lambda * 1.5, "Distortion")
        link_sockets(links, find_output(primary_mapping, "Vector"), find_input(primary_wave, "Vector"))
        link_sockets(links, find_output(primary_phase, "Value"), find_input(primary_wave, "W"))

        primary_signed = new_labeled_node(nodes, "ShaderNodeMath", "Primary Swell Signed", (-940, 300))
        primary_signed.operation = "SUBTRACT"
        primary_signed.inputs[1].default_value = 0.5
        link_sockets(links, find_output(primary_wave, "Fac"), primary_signed.inputs[0])

        secondary_wave = new_labeled_node(nodes, "ShaderNodeTexNoise", "FFT Secondary Swell", (-1180, 20))
        secondary_wave.noise_dimensions = "4D"
        set_input_value(secondary_wave, max(0.4, 1.7 * wind_scale * (0.8 + fft_lambda)), "Scale")
        set_input_value(secondary_wave, 3.0, "Detail")
        set_input_value(secondary_wave, 0.5, "Roughness")
        set_input_value(secondary_wave, fft_lambda, "Distortion")
        link_sockets(links, find_output(secondary_mapping, "Vector"), find_input(secondary_wave, "Vector"))
        link_sockets(links, find_output(secondary_phase, "Value"), find_input(secondary_wave, "W"))

        secondary_signed = new_labeled_node(nodes, "ShaderNodeMath", "Secondary Swell Signed", (-940, 80))
        secondary_signed.operation = "SUBTRACT"
        secondary_signed.inputs[1].default_value = 0.5
        link_sockets(links, find_output(secondary_wave, "Fac"), secondary_signed.inputs[0])

        detail_noise = new_labeled_node(nodes, "ShaderNodeTexNoise", "Normal Detail", (-1180, -250))
        detail_noise.noise_dimensions = "4D"
        set_input_value(detail_noise, normal_scale * 0.35 / water_size, "Scale")
        set_input_value(detail_noise, 5.0, "Detail")
        set_input_value(detail_noise, 0.65, "Roughness")
        set_input_value(detail_noise, 0.15 * fft_lambda, "Distortion")
        link_sockets(links, find_output(primary_mapping, "Vector"), find_input(detail_noise, "Vector"))
        link_sockets(links, find_output(detail_time, "Value"), find_input(detail_noise, "W"))

        impulse_noise = new_labeled_node(nodes, "ShaderNodeTexNoise", "WaterSim Impulses", (-1180, -430))
        impulse_noise.noise_dimensions = "4D"
        impulse_scale = normal_scale * 0.45 * max(1.0, math.sqrt(simulation_resolution / 256.0)) / water_size
        set_input_value(impulse_noise, impulse_scale, "Scale")
        set_input_value(impulse_noise, 2.0, "Detail")
        set_input_value(impulse_noise, 0.5, "Roughness")
        link_sockets(links, find_output(primary_mapping, "Vector"), find_input(impulse_noise, "Vector"))
        link_sockets(links, find_output(detail_time, "Value"), find_input(impulse_noise, "W"))

        impulse_weight = new_labeled_node(nodes, "ShaderNodeMath", "WaterSim Activity Weight", (-930, -430))
        impulse_weight.operation = "MULTIPLY"
        link_sockets(links, find_output(impulse_noise, "Fac"), impulse_weight.inputs[0])
        link_sockets(links, find_output(sim_activity, "Value"), impulse_weight.inputs[1])

        detail_height = new_labeled_node(nodes, "ShaderNodeMath", "Combined Detail Height", (-700, -300))
        detail_height.operation = "ADD"
        detail_height.use_clamp = True
        link_sockets(links, find_output(detail_noise, "Fac"), detail_height.inputs[0])
        link_sockets(links, find_output(impulse_weight, "Value"), detail_height.inputs[1])

        micro_roughness = new_labeled_node(nodes, "ShaderNodeMath", "Animated Water Micro Roughness", (-470, -430))
        micro_roughness.operation = "MULTIPLY_ADD"
        micro_roughness.inputs[1].default_value = micro_roughness_strength
        micro_roughness.inputs[2].default_value = max(0.04, roughness - micro_roughness_strength * 0.5)
        micro_roughness.use_clamp = True
        link_sockets(links, find_output(detail_height, "Value"), micro_roughness.inputs[0])

        primary_weight = new_labeled_node(nodes, "ShaderNodeMath", "Primary Wave Weight", (-720, 300))
        primary_weight.operation = "MULTIPLY"
        primary_weight.inputs[1].default_value = 0.62
        link_sockets(links, find_output(primary_signed, "Value"), primary_weight.inputs[0])

        secondary_weight = new_labeled_node(nodes, "ShaderNodeMath", "Secondary Wave Weight", (-720, 80))
        secondary_weight.operation = "MULTIPLY"
        secondary_weight.inputs[1].default_value = 0.34
        link_sockets(links, find_output(secondary_signed, "Value"), secondary_weight.inputs[0])

        detail_signed = new_labeled_node(nodes, "ShaderNodeMath", "Detail Wave Signed", (-720, -180))
        detail_signed.operation = "MULTIPLY_ADD"
        detail_signed.inputs[1].default_value = 0.10
        detail_signed.inputs[2].default_value = -0.05
        link_sockets(links, find_output(detail_height, "Value"), detail_signed.inputs[0])

        wave_add = new_labeled_node(nodes, "ShaderNodeMath", "Combined FFT", (-500, 200))
        wave_add.operation = "ADD"
        link_sockets(links, find_output(primary_weight, "Value"), wave_add.inputs[0])
        link_sockets(links, find_output(secondary_weight, "Value"), wave_add.inputs[1])

        # Signed procedural swell in the same metric register as the authored height so the two can
        # be blended without one scale swamping the other.
        procedural_height = new_labeled_node(nodes, "ShaderNodeMath", "Procedural Swell Height", (-280, 160))
        procedural_height.operation = "ADD"
        link_sockets(links, find_output(wave_add, "Value"), procedural_height.inputs[0])
        link_sockets(links, find_output(detail_signed, "Value"), procedural_height.inputs[1])

        choppiness_strength = (chop_xy + abs(choppiness[2])) / 40.0
        broad_strength = 0.0 if skip_simulated_normals >= 0.5 else clamp01(
            0.10 + (fft_amplitude / 40.0) * 0.20 + choppiness_strength * 0.14, 0.0, 0.75
        )
        detail_strength = clamp01(normal_intensity * refraction_normal * 0.18, 0.0, 1.2)

        procedural_amplitude = clamp01(0.04 + (fft_amplitude / 40.0) * 0.22 + choppiness_strength * 0.10, 0.01, 0.35)
        procedural_metric = new_labeled_node(nodes, "ShaderNodeMath", "Procedural Swell Metric", (-60, 160))
        procedural_metric.operation = "MULTIPLY"
        procedural_metric.inputs[1].default_value = procedural_amplitude
        link_sockets(links, find_output(procedural_height, "Value"), procedural_metric.inputs[0])

        # Broad displacement height in metres. When authored data is present it dominates, with the
        # procedural swell added as a small residual (both metric, so the mix is meaningful).
        if authored_height is not None:
            displace_height = new_labeled_node(nodes, "ShaderNodeMath", "Broad Water Height", (180, 60))
            displace_height.operation = "MULTIPLY_ADD"
            displace_height.inputs[1].default_value = 0.85
            link_sockets(links, authored_height, displace_height.inputs[0])

            procedural_residual = new_labeled_node(nodes, "ShaderNodeMath", "Procedural Water Residual", (-60, -40))
            procedural_residual.operation = "MULTIPLY"
            procedural_residual.inputs[1].default_value = 0.35
            link_sockets(links, find_output(procedural_metric, "Value"), procedural_residual.inputs[0])
            link_sockets(links, find_output(procedural_residual, "Value"), displace_height.inputs[2])
            broad_metric_output = find_output(displace_height, "Value")
        else:
            broad_metric_output = find_output(procedural_metric, "Value")

        # Normalized 0..1 broad height for threshold-style consumers (foam, slope scattering). Uses
        # the authored normalized channel when present so weighting stays in the fixed 0.82/0.18 mix.
        broad_normalized = new_labeled_node(nodes, "ShaderNodeMath", "Broad Water Height Normalized", (180, -160))
        broad_normalized.operation = "MULTIPLY_ADD"
        broad_normalized.inputs[1].default_value = 0.82
        broad_normalized.use_clamp = True
        if authored_height_normalized is not None:
            link_sockets(links, authored_height_normalized, broad_normalized.inputs[0])
        else:
            link_sockets(links, find_output(procedural_height, "Value"), broad_normalized.inputs[0])

        procedural_normalized = new_labeled_node(nodes, "ShaderNodeMath", "Procedural Height Normalized", (-60, -260))
        procedural_normalized.operation = "MULTIPLY"
        procedural_normalized.inputs[1].default_value = 0.18
        link_sockets(links, find_output(procedural_height, "Value"), procedural_normalized.inputs[0])
        link_sockets(links, find_output(procedural_normalized, "Value"), broad_normalized.inputs[2])
        broad_normalized_output = find_output(broad_normalized, "Value")

        # True geometry displacement (EEVEE Next / Cycles). Midlevel 0 because the height is signed;
        # geometry resolution caps detail, so a Subdivision modifier is expected for the ocean patch.
        displacement = new_labeled_node(nodes, "ShaderNodeDisplacement", "Water Displacement", (1380, -260))
        displacement.inputs["Midlevel"].default_value = 0.0
        displacement.inputs["Scale"].default_value = 1.0
        link_sockets(links, broad_metric_output, displacement.inputs["Height"])
        link_sockets(links, find_output(displacement, "Displacement"), find_input(output, "Displacement"))

        # EEVEE recovers faceted normals from displacement, so drive the shading normal from bump:
        # a light broad term to smooth the facets plus the fine detail octave.
        broad_bump = new_labeled_node(nodes, "ShaderNodeBump", "Water Patch Normal", (700, -160))
        broad_bump.inputs["Strength"].default_value = broad_strength
        broad_bump.inputs["Distance"].default_value = (
            clamp01((patch_data["heightMax"] - patch_data["heightMin"]) * 0.45, 0.02, 0.22)
            if patch_data is not None
            else clamp01(procedural_amplitude * 0.6, 0.01, 0.12)
        )
        link_sockets(links, broad_normalized_output, broad_bump.inputs["Height"])

        detail_bump = new_labeled_node(nodes, "ShaderNodeBump", "Detail Water Normal", (930, -120))
        detail_bump.inputs["Strength"].default_value = detail_strength
        detail_bump.inputs["Distance"].default_value = clamp01(0.08 / normal_scale, 0.002, 0.05)
        link_sockets(links, find_output(detail_height, "Value"), detail_bump.inputs["Height"])
        link_sockets(links, find_output(broad_bump, "Normal"), detail_bump.inputs["Normal"])
        link_sockets(links, find_output(detail_bump, "Normal"), find_input(principled, "Normal"))

        coverage_output = None
        depth_output = None
        if water_map_image is not None:
            water_map = new_labeled_node(nodes, "ShaderNodeTexImage", "Water Map", (-1180, 680))
            water_map.image = water_map_image
            water_map.interpolation = "Linear"
            water_map.extension = "EXTEND"
            link_sockets(links, water_map_vector, find_input(water_map, "Vector"))

            map_channels = new_labeled_node(nodes, "ShaderNodeSeparateColor", "Water Map Channels", (-930, 680))
            map_channels.mode = "RGB"
            link_sockets(links, find_output(water_map, "Color"), find_input(map_channels, "Color"))

            threshold = clamp01(shore_threshold + shore_offset)
            half_width = clamp01(edge_blend * 0.5, 0.002, 0.49)
            coverage_ramp = new_labeled_node(nodes, "ShaderNodeValToRGB", "Water Coverage", (-690, 650))
            coverage_ramp.color_ramp.interpolation = "EASE"
            coverage_ramp.color_ramp.elements[0].position = clamp01(threshold - half_width)
            coverage_ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
            coverage_ramp.color_ramp.elements[1].position = clamp01(threshold + half_width)
            coverage_ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
            link_sockets(links, find_output(map_channels, "Green", "G"), coverage_ramp.inputs["Fac"])

            map_weight_mix = new_labeled_node(nodes, "ShaderNodeMixRGB", "Water Map Weight", (-440, 660))
            map_weight_mix.blend_type = "MIX"
            map_weight_mix.inputs[0].default_value = map_weight
            map_weight_mix.inputs[1].default_value = (1.0, 1.0, 1.0, 1.0)
            link_sockets(links, find_output(coverage_ramp, "Color"), map_weight_mix.inputs[2])
            coverage_output = find_output(map_weight_mix, "Color")

            depth_weight = new_labeled_node(nodes, "ShaderNodeMath", "Water Depth Map Weight", (-440, 560))
            depth_weight.operation = "MULTIPLY_ADD"
            depth_weight.inputs[1].default_value = map_weight
            depth_weight.inputs[2].default_value = (1.0 - map_weight) * 0.5
            link_sockets(links, find_output(map_channels, "Red", "R"), depth_weight.inputs[0])
            depth_output = find_output(depth_weight, "Value")

        if coverage_output is None:
            coverage_value = new_labeled_node(nodes, "ShaderNodeValue", "Water Coverage", (-440, 660))
            coverage_value.outputs[0].default_value = 1.0
            coverage_output = coverage_value.outputs[0]
        if depth_output is None:
            depth_value = new_labeled_node(nodes, "ShaderNodeValue", "Water Depth Map", (-440, 560))
            depth_value.outputs[0].default_value = 0.5
            depth_output = depth_value.outputs[0]

        alpha = new_labeled_node(nodes, "ShaderNodeValue", "Water Alpha", (1140, -430))
        alpha.outputs[0].default_value = opacity
        alpha.label = "Authored opacity only; WaterMap never clips tile geometry"
        link_sockets(links, find_output(alpha, "Value"), find_input(principled, "Alpha"))

        inverse_coverage = new_labeled_node(nodes, "ShaderNodeMath", "Inverse Coverage", (-170, 650))
        inverse_coverage.operation = "SUBTRACT"
        inverse_coverage.inputs[0].default_value = 1.0
        link_sockets(links, coverage_output, inverse_coverage.inputs[1])

        shore_band = new_labeled_node(nodes, "ShaderNodeMath", "Shore Band", (40, 650))
        shore_band.operation = "MULTIPLY"
        link_sockets(links, coverage_output, shore_band.inputs[0])
        link_sockets(links, find_output(inverse_coverage, "Value"), shore_band.inputs[1])

        shore_band_scale = new_labeled_node(nodes, "ShaderNodeMath", "Shore Band Scale", (250, 650))
        shore_band_scale.operation = "MULTIPLY"
        shore_band_scale.inputs[1].default_value = 4.0
        shore_band_scale.use_clamp = True
        link_sockets(links, find_output(shore_band, "Value"), shore_band_scale.inputs[0])

        deep_color = _scale_color(surface_tint, clamp01(0.62 + 0.20 / (1.0 + scattering_depth * 0.18), 0.55, 0.9))
        shallow_color = _scale_color(surface_tint, clamp01(1.0 + sun_intensity * 0.03, 1.0, 1.3))
        sun_color = _mix_color_value(
            _scale_color(surface_tint, clamp01(1.05 + sun_intensity * 0.04, 1.05, 1.4)),
            (0.55, 0.68, 0.78, 1.0),
            clamp01(sun_intensity / (sun_intensity + 8.0) * 0.5),
        )
        crest_color = _mix_color_value(
            _scale_color(surface_tint, clamp01(1.1 + slope_intensity * 0.04, 1.1, 1.4)),
            foam_color,
            clamp01(slope_intensity / (slope_intensity + 6.0) * 0.4),
        )

        deep_rgb = new_labeled_node(nodes, "ShaderNodeRGB", "Deep Scattering Color", (-170, 980))
        deep_rgb.outputs[0].default_value = deep_color
        shallow_rgb = new_labeled_node(nodes, "ShaderNodeRGB", "Shallow Scattering Color", (-170, 900))
        shallow_rgb.outputs[0].default_value = shallow_color

        depth_mix = new_labeled_node(nodes, "ShaderNodeMixRGB", "Scattering Depth", (80, 940))
        depth_mix.blend_type = "MIX"
        link_sockets(links, depth_output, depth_mix.inputs[0])
        link_sockets(links, find_output(deep_rgb, "Color"), depth_mix.inputs[1])
        link_sockets(links, find_output(shallow_rgb, "Color"), depth_mix.inputs[2])

        layer_weight = new_labeled_node(nodes, "ShaderNodeLayerWeight", "View Scattering", (-170, 810))
        set_input_value(layer_weight, clamp01((ior - 1.0) / 0.5, 0.0, 1.0), "Blend")

        sun_power = new_labeled_node(nodes, "ShaderNodeMath", "Sun Scattering Radius", (80, 800))
        sun_power.operation = "POWER"
        sun_power.inputs[1].default_value = clamp01(1.0 / sun_radius, 0.15, 8.0)
        link_sockets(links, find_output(layer_weight, "Facing"), sun_power.inputs[0])

        sun_amount = new_labeled_node(nodes, "ShaderNodeMath", "Sun Scattering Intensity", (300, 800))
        sun_amount.operation = "MULTIPLY"
        sun_amount.inputs[1].default_value = clamp01(sun_intensity / (sun_intensity + 8.0) * 0.35, 0.0, 0.35)
        link_sockets(links, find_output(sun_power, "Value"), sun_amount.inputs[0])

        sun_rgb = new_labeled_node(nodes, "ShaderNodeRGB", "Sun Scattering Color", (300, 920))
        sun_rgb.outputs[0].default_value = sun_color

        sun_mix = new_labeled_node(nodes, "ShaderNodeMixRGB", "Sun Scattering", (530, 920))
        sun_mix.blend_type = "MIX"
        link_sockets(links, find_output(sun_amount, "Value"), sun_mix.inputs[0])
        link_sockets(links, find_output(depth_mix, "Color"), sun_mix.inputs[1])
        link_sockets(links, find_output(sun_rgb, "Color"), sun_mix.inputs[2])

        normalized_slope_threshold = slope_threshold / (slope_threshold + 1.0) if slope_threshold > 1.0 else slope_threshold
        slope_ramp = new_labeled_node(nodes, "ShaderNodeValToRGB", "Slope Scattering Threshold", (40, 430))
        slope_ramp.color_ramp.interpolation = "EASE"
        slope_ramp.color_ramp.elements[0].position = clamp01(normalized_slope_threshold)
        slope_ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
        slope_ramp.color_ramp.elements[1].position = clamp01(normalized_slope_threshold + 0.08)
        slope_ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
        link_sockets(links, broad_normalized_output, slope_ramp.inputs["Fac"])

        slope_amount = new_labeled_node(nodes, "ShaderNodeMath", "Slope Scattering Intensity", (270, 430))
        slope_amount.operation = "MULTIPLY"
        slope_amount.inputs[1].default_value = clamp01(slope_intensity / (slope_intensity + 4.0), 0.0, 0.75)
        link_sockets(links, find_output(slope_ramp, "Color"), slope_amount.inputs[0])

        crest_rgb = new_labeled_node(nodes, "ShaderNodeRGB", "Crest Scattering Color", (530, 760))
        crest_rgb.outputs[0].default_value = crest_color

        crest_mix = new_labeled_node(nodes, "ShaderNodeMixRGB", "Wave Crest Scattering", (760, 900))
        crest_mix.blend_type = "MIX"
        link_sockets(links, find_output(slope_amount, "Value"), crest_mix.inputs[0])
        link_sockets(links, find_output(sun_mix, "Color"), crest_mix.inputs[1])
        link_sockets(links, find_output(crest_rgb, "Color"), crest_mix.inputs[2])

        grazing_color = _mix_color_value(
            _scale_color(surface_tint, clamp01(1.05 + sun_intensity * 0.02, 1.05, 1.3)),
            (0.50, 0.66, 0.78, 1.0),
            0.30,
        )
        grazing_rgb = new_labeled_node(nodes, "ShaderNodeRGB", "Grazing Water Tint", (760, 720))
        grazing_rgb.outputs[0].default_value = grazing_color

        grazing_amount = new_labeled_node(nodes, "ShaderNodeMath", "Grazing Water Response", (530, 700))
        grazing_amount.operation = "MULTIPLY"
        grazing_amount.inputs[1].default_value = clamp01(0.14 + sun_intensity / (sun_intensity + 6.0) * 0.16, 0.14, 0.30)
        link_sockets(links, find_output(layer_weight, "Fresnel"), grazing_amount.inputs[0])

        grazing_mix = new_labeled_node(nodes, "ShaderNodeMixRGB", "Water Grazing Color", (960, 790))
        grazing_mix.blend_type = "MIX"
        link_sockets(links, find_output(grazing_amount, "Value"), grazing_mix.inputs[0])
        link_sockets(links, find_output(crest_mix, "Color"), grazing_mix.inputs[1])
        link_sockets(links, find_output(grazing_rgb, "Color"), grazing_mix.inputs[2])

        foam_source = find_output(detail_height, "Value")
        if foam_image is not None:
            foam_mapping = new_labeled_node(nodes, "ShaderNodeMapping", "Foam Mapping", (-930, 1160))
            foam_mapping.vector_type = "POINT"
            set_input_value(foam_mapping, (0.0, 0.0, wave_direction + 0.35), "Rotation")
            set_input_value(foam_mapping, (1.0 / foam_size, 1.0 / foam_size, 1.0), "Scale")
            link_sockets(links, world_position, find_input(foam_mapping, "Vector"))

            foam_drift_x = new_labeled_node(nodes, "ShaderNodeMath", "Foam Drift X", (-1160, 1250))
            foam_drift_x.operation = "MULTIPLY"
            foam_drift_x.inputs[1].default_value = math.cos(wave_direction) * clamp01(wind_speed / 10.0, 0.15, 2.5) * 0.018
            link_sockets(links, find_output(time_value, "Value"), foam_drift_x.inputs[0])

            foam_drift_y = new_labeled_node(nodes, "ShaderNodeMath", "Foam Drift Y", (-1160, 1160))
            foam_drift_y.operation = "MULTIPLY"
            foam_drift_y.inputs[1].default_value = math.sin(wave_direction) * clamp01(wind_speed / 10.0, 0.15, 2.5) * 0.018
            link_sockets(links, find_output(time_value, "Value"), foam_drift_y.inputs[0])

            foam_drift = new_labeled_node(nodes, "ShaderNodeCombineXYZ", "Foam Drift", (-980, 1270))
            link_sockets(links, find_output(foam_drift_x, "Value"), foam_drift.inputs["X"])
            link_sockets(links, find_output(foam_drift_y, "Value"), foam_drift.inputs["Y"])
            link_sockets(links, find_output(foam_drift, "Vector"), find_input(foam_mapping, "Location"))

            foam_texture = new_labeled_node(nodes, "ShaderNodeTexImage", "Foam Texture", (-690, 1160))
            foam_texture.image = foam_image
            foam_texture.interpolation = "Linear"
            foam_texture.extension = "REPEAT"
            link_sockets(links, find_output(foam_mapping, "Vector"), find_input(foam_texture, "Vector"))

            foam_bw = new_labeled_node(nodes, "ShaderNodeRGBToBW", "Foam Luminance", (-440, 1160))
            link_sockets(links, find_output(foam_texture, "Color"), find_input(foam_bw, "Color"))
            foam_source = find_output(foam_bw, "Val")

        normalized_foam_threshold = foam_threshold / (foam_threshold + 1.0) if foam_threshold > 1.0 else foam_threshold
        foam_width = clamp01(0.06 + edge_blend * 0.12, 0.04, 0.20)

        foam_texture_threshold = new_labeled_node(nodes, "ShaderNodeValToRGB", "Foam Texture Threshold", (-170, 1160))
        foam_texture_threshold.color_ramp.interpolation = "EASE"
        foam_texture_threshold.color_ramp.elements[0].position = clamp01(normalized_foam_threshold - foam_width)
        foam_texture_threshold.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
        foam_texture_threshold.color_ramp.elements[1].position = clamp01(normalized_foam_threshold + foam_width)
        foam_texture_threshold.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
        link_sockets(links, foam_source, foam_texture_threshold.inputs["Fac"])

        # Restrict wave foam to crests via the broad height field rather than the raw value.
        wave_foam_threshold = new_labeled_node(nodes, "ShaderNodeValToRGB", "Wave Foam Threshold", (-170, 1060))
        wave_foam_threshold.color_ramp.interpolation = "EASE"
        wave_foam_threshold.color_ramp.elements[0].position = clamp01(normalized_foam_threshold - foam_width)
        wave_foam_threshold.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
        wave_foam_threshold.color_ramp.elements[1].position = clamp01(normalized_foam_threshold + foam_width)
        wave_foam_threshold.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
        link_sockets(links, broad_normalized_output, wave_foam_threshold.inputs["Fac"])

        simulated_foam = new_labeled_node(nodes, "ShaderNodeMath", "Simulated Foam", (50, 1060))
        simulated_foam.operation = "MULTIPLY"
        simulated_foam.inputs[1].default_value = 1.0 - skip_simulated_normals
        link_sockets(links, find_output(wave_foam_threshold, "Color"), simulated_foam.inputs[0])

        foam_driver = new_labeled_node(nodes, "ShaderNodeMath", "Foam Driver", (270, 1080))
        foam_driver.operation = "MAXIMUM"
        link_sockets(links, find_output(shore_band_scale, "Value"), foam_driver.inputs[0])
        link_sockets(links, find_output(simulated_foam, "Value"), foam_driver.inputs[1])

        foam_pattern = new_labeled_node(nodes, "ShaderNodeMath", "Foam Pattern", (490, 1100))
        foam_pattern.operation = "MULTIPLY"
        link_sockets(links, find_output(foam_texture_threshold, "Color"), foam_pattern.inputs[0])
        link_sockets(links, find_output(foam_driver, "Value"), foam_pattern.inputs[1])

        foam_amount = new_labeled_node(nodes, "ShaderNodeMath", "Foam Intensity", (710, 1100))
        foam_amount.operation = "MULTIPLY"
        foam_amount.inputs[1].default_value = foam_intensity
        foam_amount.use_clamp = True
        link_sockets(links, find_output(foam_pattern, "Value"), foam_amount.inputs[0])

        foam_rgb = new_labeled_node(nodes, "ShaderNodeRGB", "Foam Color", (710, 1210))
        foam_rgb.outputs[0].default_value = foam_color

        foam_mix = new_labeled_node(nodes, "ShaderNodeMixRGB", "Water and Foam", (1140, 900))
        foam_mix.blend_type = "MIX"
        link_sockets(links, find_output(foam_amount, "Value"), foam_mix.inputs[0])
        link_sockets(links, find_output(grazing_mix, "Color"), foam_mix.inputs[1])
        link_sockets(links, find_output(foam_rgb, "Color"), foam_mix.inputs[2])
        link_sockets(links, find_output(foam_mix, "Color"), find_input(principled, "Base Color"))

        foam_roughness = new_labeled_node(nodes, "ShaderNodeMath", "Foam Roughness", (1140, 620))
        foam_roughness.operation = "MULTIPLY_ADD"
        foam_roughness.inputs[1].default_value = max(0.0, 0.58 - roughness)
        foam_roughness.use_clamp = True
        link_sockets(links, find_output(foam_amount, "Value"), foam_roughness.inputs[0])
        link_sockets(links, find_output(micro_roughness, "Value"), foam_roughness.inputs[2])
        link_sockets(links, find_output(foam_roughness, "Value"), find_input(principled, "Roughness"))

        inverse_foam = new_labeled_node(nodes, "ShaderNodeMath", "Inverse Foam", (1140, 520))
        inverse_foam.operation = "SUBTRACT"
        inverse_foam.inputs[0].default_value = 1.0
        link_sockets(links, find_output(foam_amount, "Value"), inverse_foam.inputs[1])

        foam_transmission = new_labeled_node(nodes, "ShaderNodeMath", "Foam Transmission", (1340, 500))
        foam_transmission.operation = "MULTIPLY"
        foam_transmission.inputs[1].default_value = transmission
        link_sockets(links, find_output(inverse_foam, "Value"), foam_transmission.inputs[0])
        link_sockets(links, find_output(foam_transmission, "Value"), find_input(principled, "Transmission Weight", "Transmission"))

        # No Volume output. Absorption has no in-scattering, so the depth-extruded box renders black
        # from above at any density; depth colour is carried on the surface by the deep/shallow
        # scattering tint under bounded transmission. This diverges from a literal water volume but
        # reads as water regardless of box depth or camera side.

        parameter_frame = new_labeled_node(nodes, "NodeFrame", "REDengine Water Parameters", (-1700, -980))
        parameter_frame.label = "Material, FFT and impulse parameters"
        parameter_values = list(scalar_defaults.items())
        for index, (name, default) in enumerate(parameter_values):
            value_node = new_labeled_node(
                nodes, "ShaderNodeValue", name, (-1660 + (index % 4) * 180, -1020 - (index // 4) * 95)
            )
            value_node.outputs[0].default_value = param_float(data, name, default)
            value_node.parent = parameter_frame

        for index, name in enumerate(("amplitude", "lambda", "windDir", "windScale", "windSpeed")):
            value_node = new_labeled_node(nodes, "ShaderNodeValue", f"WaterFFT {name}", (-1660 + index * 180, -1590))
            value_node.outputs[0].default_value = float(fft_data.get(name, _FFT_DEFAULTS[name]))
            value_node.parent = parameter_frame

        Mat["cp77_water_loaded_WaterMap"] = bool(water_map_image)
        Mat["cp77_water_loaded_FoamTexture"] = bool(foam_image)
        Mat["cp77_water_roughness"] = roughness
        Mat["cp77_water_transmission"] = transmission
        Mat["cp77_water_specular_ior_level"] = specular_level
        Mat["cp77_water_micro_roughness_strength"] = micro_roughness_strength
        Mat["cp77_water_preview"] = _PREVIEW_TAG
        Mat["cp77_water_fft_broad_strength"] = broad_strength
        Mat["cp77_water_detail_strength"] = detail_strength
        Mat["cp77_water_sim_resolution"] = simulation_resolution
        Mat["cp77_water_procedural_amplitude"] = procedural_amplitude
        Mat["cp77_water_has_authored_patch_data"] = bool(patch_data)
        if patch_data is not None:
            Mat["cp77_water_patch_sidecar"] = patch_data["sidecarPath"]
            Mat["cp77_water_patch_grid_size"] = patch_data["gridSize"]
            Mat["cp77_water_patch_frame_count"] = patch_data["frameCount"]
            Mat["cp77_water_patch_anim_length"] = patch_data["animLength"]
            Mat["cp77_water_patch_anim_loop"] = patch_data["animLoop"]
            Mat["cp77_water_patch_size"] = [patch_data["patchSizeX"], patch_data["patchSizeY"]]
            Mat["cp77_water_patch_height_range"] = [patch_data["heightMin"], patch_data["heightMax"]]
            Mat["cp77_water_patch_edge_error"] = patch_data["edgeError"]
            Mat["cp77_water_patch_image"] = patch_data.get("imageName", "")
        Mat["cp77_water_coordinate_space"] = "WORLD_POSITION"
        Mat["cp77_water_map_affects_alpha"] = False
        Mat["cp77_water_map_world_size"] = water_map_world_size
=======
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
>>>>>>> Stashed changes
