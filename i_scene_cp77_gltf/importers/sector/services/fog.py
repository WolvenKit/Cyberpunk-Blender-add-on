from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

import bpy
from mathutils import Matrix, Vector

from ....assetio.values import coerce_float, color_bytes, unwrapped
from ....blender.fog_volume import build_fog_volume_material
from ....blender.transactions import track_created_datablock


def _float_value(data, key, default=0.0):
    return coerce_float(
        data.get(key, default) if isinstance(data, dict) else default,
        default,
        finite=False,
    )


def _bool_value(data, key, default=False):
    value = unwrapped(
        data.get(key, default) if isinstance(data, dict) else default, ("$value",)
    )
    return bool(default if isinstance(value, Mapping) else value)


def fog_volume_color(data):
    color = data.get("color") if isinstance(data, dict) else None
    if not isinstance(color, dict):
        return (1.0, 1.0, 0.9, 1.0)

    values = tuple(
        max(0.0, min(1.0, channel / 255.0)) for channel in color_bytes(color, 0.0)
    )
    if max(values) <= 1e-8:
        values = (1.0, 1.0, 0.9)

    return (*values, 1.0)


def fog_volume_parameters(data, source_kind="sector"):
    density_falloff = _float_value(
        data,
        "densityFalloff",
        _float_value(data, "falloff", 0.0),
    )
    density_factor = max(_float_value(data, "densityFactor", 100.0), 0.0)
    absolute = _bool_value(data, "absolute", False)
    preview_density = (
        density_factor
        if source_kind == "sector" and absolute
        else density_factor * 0.001
    )

    absorption = _float_value(data, "absorption", -1.0)
    absorption_multiplier = 0.25 if absorption < 0.0 else max(absorption, 0.0)
    ambient_scale = max(_float_value(data, "ambientScale", 1.0), 0.0)
    color = fog_volume_color(data)

    return {
        "previewDensity": max(preview_density, 0.0),
        "densityFalloff": max(0.0, min(1.0, density_falloff)),
        "blendFalloff": max(0.0, min(1.0, _float_value(data, "blendFalloff", 0.0))),
        "absorptionMultiplier": absorption_multiplier,
        "ambientScale": ambient_scale,
        "color": color,
        "absolute": absolute,
        "applyHeightFalloff": _bool_value(data, "applyHeightFalloff", True),
        "enabled": _bool_value(
            data, "isEnabled", _bool_value(data, "isVisibleInGame", True)
        ),
    }


def _material_signature(parameters):
    payload = {
        key: parameters[key]
        for key in (
            "previewDensity",
            "densityFalloff",
            "blendFalloff",
            "absorptionMultiplier",
            "ambientScale",
            "color",
            "absolute",
            "applyHeightFalloff",
        )
    }
    return hashlib.blake2b(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        digest_size=8,
    ).hexdigest()


def _unit_box_mesh(name):
    vertices = [
        (-1.0, -1.0, -1.0),
        (1.0, -1.0, -1.0),
        (1.0, 1.0, -1.0),
        (-1.0, 1.0, -1.0),
        (-1.0, -1.0, 1.0),
        (1.0, -1.0, 1.0),
        (1.0, 1.0, 1.0),
        (-1.0, 1.0, 1.0),
    ]
    faces = [
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    ]
    mesh = track_created_datablock("meshes", bpy.data.meshes.new(name))
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    return mesh


def configure_fog_volume_object(obj, data, source_kind="sector"):
    parameters = fog_volume_parameters(data, source_kind)
    # Wire, so the box does not hide the scene inside it in the viewport; renders still use the volume material.
    obj.display_type = "WIRE"
    obj.show_wire = True
    obj.color = parameters["color"]
    obj.hide_viewport = not parameters["enabled"]
    obj.hide_render = not parameters["enabled"]
    return parameters


def create_fog_volume_object(
    name,
    data,
    collection,
    *,
    matrix=None,
    size=None,
    source_kind="sector",
):
    mesh = _unit_box_mesh(name)
    obj = track_created_datablock("objects", bpy.data.objects.new(name, mesh))
    collection.objects.link(obj)

    parameters = fog_volume_parameters(data, source_kind)
    material = build_fog_volume_material(parameters, _material_signature(parameters))
    mesh.materials.append(material)

    final_matrix = matrix.copy() if matrix is not None else Matrix.Identity(4)
    if size is not None:
        size = Vector(size)
        final_matrix = final_matrix @ Matrix.Diagonal(
            (float(size.x), float(size.y), float(size.z), 1.0)
        )
    obj.matrix_world = final_matrix
    configure_fog_volume_object(obj, data, source_kind)
    return obj
