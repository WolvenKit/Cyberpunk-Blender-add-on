import os
import time
from contextlib import contextmanager
from typing import NamedTuple

import bpy
import numpy as np

from ...assetio.resources import get_resources_dir
from ...bartmoss.uv import (
    density_colors,
    polygon_uv_areas,
    polygon_world_areas,
    texel_densities,
)
from ...blender.context import get_safe_mode, safe_mode_switch
from ...blender.operator_results import OperationResult
from ...blender.selection import selected_meshes
from ...blender.shader_nodes import principled_bsdf
from ...core.log import get_logger
from ..ownership import find_owned_material, is_owned, tag_owned

_CHECKER_ACTIVE_INDEX = "cp77_uv_checker_active_index"
_LOG = get_logger(__name__)


class _ViewMode(NamedTuple):
    material: str
    previous_index_attribute: str
    role: str
    color_attribute: str = ""


_CHECKER = _ViewMode("UV_Checker", "CP77_UV_Checker_PreviousMaterial", "UV_CHECKER")
_DENSITY = _ViewMode(
    "CP77_UV_Density_View",
    "CP77_UV_Density_PreviousMaterial",
    "UV_DENSITY",
    "CP77_UV_Density",
)

_DENSITY_GRADIENT = (
    (0.0, 0.0, 0.0, 1.0),
    (0.0, 5.0 / 255.0, 100.0 / 255.0, 1.0),
    (5.0 / 255.0, 75.0 / 255.0, 200.0 / 255.0, 1.0),
    (5.0 / 255.0, 180.0 / 255.0, 110.0 / 255.0, 1.0),
    (5.0 / 255.0, 240.0 / 255.0, 5.0 / 255.0, 1.0),
    (250.0 / 255.0, 250.0 / 255.0, 0.0, 1.0),
    (1.0, 120.0 / 255.0, 0.0, 1.0),
    (1.0, 0.0, 0.0, 1.0),
)


def ensure_uv_checker_material():
    material = find_owned_material(bpy.data.materials, _CHECKER.role)
    if material is not None:
        return material

    image_path = os.path.join(get_resources_dir(), "uvchecker.png")
    if not os.path.exists(image_path):
        return None
    image = bpy.data.images.load(image_path, check_existing=True)
    material = bpy.data.materials.new(name=_CHECKER.material)
    tag_owned(material, _CHECKER.role)
    material.use_nodes = True
    texture_node = material.node_tree.nodes.new(type="ShaderNodeTexImage")
    texture_node.location = (-200, 0)
    texture_node.image = image
    shader_node = principled_bsdf(material.node_tree.nodes)
    color_output = texture_node.outputs.get("Color")
    base_color_input = shader_node.inputs.get("Base Color") if shader_node else None
    if color_output is None or base_color_input is None:
        bpy.data.materials.remove(material)
        return None
    material.node_tree.links.new(color_output, base_color_input)
    return material


def ensure_uv_density_material():
    material = find_owned_material(bpy.data.materials, _DENSITY.role)
    if material is not None:
        return material
    material = bpy.data.materials.new(name=_DENSITY.material)
    tag_owned(material, _DENSITY.role)
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.location = (360, 0)
    emission = tree.nodes.new("ShaderNodeEmission")
    emission.location = (120, 0)
    emission.inputs["Strength"].default_value = 1.0
    attribute = tree.nodes.new("ShaderNodeAttribute")
    attribute.location = (-160, 0)
    attribute.attribute_name = _DENSITY.color_attribute
    tree.links.new(attribute.outputs["Color"], emission.inputs["Color"])
    tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return material


def _has_owned_material(obj, role):
    return any(
        is_owned(slot.material, role)
        for slot in obj.material_slots
        if slot.material is not None
    )


def has_uv_density(obj):
    if obj is None or getattr(obj, "type", None) != "MESH":
        return False
    return (
        _DENSITY.previous_index_attribute in obj.data.attributes
        or _has_owned_material(obj, _DENSITY.role)
    )


def _ensure_color_attribute(mesh):
    attribute = mesh.color_attributes.get(_DENSITY.color_attribute)
    if attribute is not None and (
        attribute.domain != "CORNER" or attribute.data_type != "BYTE_COLOR"
    ):
        mesh.color_attributes.remove(attribute)
        attribute = None
    if attribute is None:
        attribute = mesh.color_attributes.new(
            name=_DENSITY.color_attribute,
            type="BYTE_COLOR",
            domain="CORNER",
        )
    return attribute


def has_uv_checker(obj):
    return bool(
        obj is not None
        and getattr(obj, "type", None) == "MESH"
        and (
            _CHECKER.previous_index_attribute in obj.data.attributes
            or _has_owned_material(obj, _CHECKER.role)
        )
    )


@contextmanager
def _batch_object_mode():
    previous_mode = get_safe_mode()
    if previous_mode != "OBJECT":
        safe_mode_switch("OBJECT")
    try:
        yield
    finally:
        if previous_mode != "OBJECT":
            safe_mode_switch(previous_mode)


def _mesh_groups(objects):
    groups = {}
    for obj in objects:
        groups.setdefault(obj.data.as_pointer(), []).append(obj)
    return tuple(groups.values())


def _read_array(collection, name, width=1, dtype=np.int32):
    values = np.empty(len(collection) * width, dtype=dtype)
    collection.foreach_get(name, values)
    return values.reshape(-1, width) if width > 1 else values


def _ensure_previous_indices(mesh, name):
    attribute = mesh.attributes.get(name)
    if attribute is not None:
        if attribute.domain != "FACE" or attribute.data_type != "INT":
            raise ValueError(f"{mesh.name}: invalid UV preview material backup")
        return attribute
    indices = _read_array(mesh.polygons, "material_index")
    attribute = mesh.attributes.new(name=name, type="INT", domain="FACE")
    attribute.data.foreach_set("value", indices)
    return attribute


def _assign_preview(mesh, material, backup_name):
    _ensure_previous_indices(mesh, backup_name)
    slot = mesh.materials.find(material.name)
    if slot < 0:
        mesh.materials.append(material)
        slot = len(mesh.materials) - 1
    mesh.polygons.foreach_set(
        "material_index", np.full(len(mesh.polygons), slot, dtype=np.int32)
    )
    return slot


def _restore_preview(mesh, material_role, backup_name):
    previous = mesh.attributes.get(backup_name)
    slot = next(
        (
            index
            for index, material in enumerate(mesh.materials)
            if is_owned(material, material_role)
        ),
        -1,
    )
    if previous is None and slot < 0:
        return False
    if previous is not None:
        if previous.domain != "FACE" or previous.data_type != "INT":
            raise ValueError(f"{mesh.name}: invalid UV preview material backup")
        values = _read_array(previous.data, "value")
        indices = _read_array(mesh.polygons, "material_index")
        limit = min(len(indices), len(values))
        indices[:limit] = values[:limit]
        mesh.polygons.foreach_set("material_index", indices)
        mesh.attributes.remove(previous)
    if slot >= 0:
        mesh.materials.pop(index=slot)
    return True


def _density_arrays(mesh):
    return (
        _read_array(mesh.vertices, "co", 3, np.float32).astype(np.float64),
        _read_array(mesh.loops, "vertex_index"),
        _read_array(mesh.polygons, "loop_start"),
        _read_array(mesh.polygons, "loop_total"),
        _read_array(mesh.uv_layers.active.uv, "vector", 2, np.float32).astype(
            np.float64
        ),
    )


def _density_statistics(obj, densities):
    nonzero = densities[densities > 0.0]
    if len(nonzero):
        middle = len(nonzero) // 2
        obj["cp77_uv_density_min"] = float(np.min(nonzero))
        obj["cp77_uv_density_max"] = float(np.max(nonzero))
        obj["cp77_uv_density_median"] = float(np.partition(nonzero, middle)[middle])
    else:
        for key in (
            "cp77_uv_density_min",
            "cp77_uv_density_max",
            "cp77_uv_density_median",
        ):
            obj.pop(key, None)


def _batch_result(action, objects, meshes, faces, started, skipped=0):
    _LOG.debug(
        "%s: %d selected object(s), %d mesh datablock(s), %d face(s), %d skipped in %.3fs",
        action,
        objects,
        meshes,
        faces,
        skipped,
        time.perf_counter() - started,
    )
    suffix = f" Skipped {skipped} mesh(es) without usable UVs." if skipped else ""
    return OperationResult.finished(f"{action} on {objects} mesh(es).{suffix}")


def apply_uv_density(context, reference):
    selected = selected_meshes(context)
    if not selected:
        return OperationResult.cancelled("No meshes selected.")
    if any(has_uv_checker(obj) for obj in selected):
        return OperationResult.cancelled(
            "Remove the UV Checker before enabling UV Density."
        )
    started = time.perf_counter()
    updated = meshes = faces = skipped = 0
    with _batch_object_mode():
        material = ensure_uv_density_material()
        for objects in _mesh_groups(selected):
            mesh = objects[0].data
            if mesh.uv_layers.active is None:
                skipped += len(objects)
                continue
            positions, loop_vertices, starts, counts, uvs = _density_arrays(mesh)
            uv_areas = polygon_uv_areas(uvs, starts, counts)
            by_transform = {}
            for obj in objects:
                linear = np.asarray(obj.matrix_world.to_3x3(), dtype=np.float64)
                key = tuple(linear.reshape(-1))
                densities = by_transform.get(key)
                if densities is None:
                    world_areas = polygon_world_areas(
                        positions, loop_vertices, starts, counts, linear
                    )
                    densities = texel_densities(uv_areas, world_areas)
                    if len(by_transform) < 8:
                        by_transform[key] = densities
                _density_statistics(obj, densities)
            colors = density_colors(densities, reference, _DENSITY_GRADIENT)
            corner_colors = np.empty((len(mesh.loops), 4), dtype=np.float32)
            face_ids = np.repeat(np.arange(len(counts)), counts)
            loop_ids = (
                np.repeat(starts, counts)
                + np.arange(len(face_ids))
                - np.repeat(np.cumsum(counts) - counts, counts)
            )
            corner_colors[loop_ids] = colors[face_ids]
            _ensure_color_attribute(mesh).data.foreach_set(
                "color", corner_colors.reshape(-1)
            )
            _assign_preview(mesh, material, _DENSITY.previous_index_attribute)
            updated += len(objects)
            meshes += 1
            faces += len(mesh.polygons)
    if not updated:
        return OperationResult.cancelled(
            "UV Density could not be applied: selected meshes have no active UV layer."
        )
    return _batch_result("UV Density enabled", updated, meshes, faces, started, skipped)


def remove_uv_density(context):
    selected = selected_meshes(context)
    if not selected:
        return OperationResult.cancelled("No meshes selected.")
    started = time.perf_counter()
    restored = meshes = faces = 0
    with _batch_object_mode():
        for objects in _mesh_groups(selected):
            mesh = objects[0].data
            if not _restore_preview(
                mesh, _DENSITY.role, _DENSITY.previous_index_attribute
            ):
                continue
            color = mesh.color_attributes.get(_DENSITY.color_attribute)
            if color is not None:
                mesh.color_attributes.remove(color)
            for obj in objects:
                for key in (
                    "cp77_uv_density_min",
                    "cp77_uv_density_max",
                    "cp77_uv_density_median",
                ):
                    obj.pop(key, None)
            restored += len(objects)
            meshes += 1
            faces += len(mesh.polygons)
    if not restored:
        return OperationResult.cancelled(
            "UV Density is not enabled on the selected meshes."
        )
    return _batch_result("UV Density removed", restored, meshes, faces, started)


def apply_uv_checker(context):
    selected = selected_meshes(context)
    if not selected:
        return OperationResult.cancelled("No meshes selected.")
    if any(has_uv_density(obj) for obj in selected):
        return OperationResult.cancelled(
            "Remove UV Density before enabling the UV Checker."
        )
    started = time.perf_counter()
    updated = meshes = faces = 0
    with _batch_object_mode():
        material = ensure_uv_checker_material()
        if material is None:
            return OperationResult.cancelled("UV checker image could not be loaded.")
        for objects in _mesh_groups(selected):
            mesh = objects[0].data
            if has_uv_checker(objects[0]):
                continue
            for obj in objects:
                obj[_CHECKER_ACTIVE_INDEX] = obj.active_material_index
            slot = _assign_preview(mesh, material, _CHECKER.previous_index_attribute)
            for obj in objects:
                obj.active_material_index = slot
            updated += len(objects)
            meshes += 1
            faces += len(mesh.polygons)
    return _batch_result("UV Checker applied", updated, meshes, faces, started)


def remove_uv_checker(context):
    selected = selected_meshes(context)
    if not selected:
        return OperationResult.cancelled("No meshes selected.")
    started = time.perf_counter()
    restored = meshes = faces = 0
    with _batch_object_mode():
        for objects in _mesh_groups(selected):
            mesh = objects[0].data
            if not _restore_preview(
                mesh, _CHECKER.role, _CHECKER.previous_index_attribute
            ):
                continue
            for obj in objects:
                active = obj.pop(_CHECKER_ACTIVE_INDEX, None)
                if active is not None:
                    obj.active_material_index = max(
                        0, min(int(active), len(mesh.materials) - 1)
                    )
            restored += len(objects)
            meshes += 1
            faces += len(mesh.polygons)
    if not restored:
        return OperationResult.cancelled(
            "UV Checker is not enabled on the selected meshes."
        )
    return _batch_result("UV Checker removed", restored, meshes, faces, started)
