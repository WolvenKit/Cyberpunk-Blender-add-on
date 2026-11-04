import bpy
import numpy as np
from mathutils import Vector

from ...blender.context import (
    restore_previous_context,
    safe_mode_switch,
    store_current_context,
)
from ...blender.operator_results import OperationResult, require_finished
from ...blender.selection import select_objects, selected_meshes
from ...core.log import get_logger
from ..model import shared_mesh_refusal

_LOG = get_logger(__name__)


def mirror_selected_vertex_groups(context):
    selected = selected_meshes(context)
    if not selected:
        return OperationResult.cancelled("No meshes selected.")
    original_mode = context.mode
    try:
        safe_mode_switch("OBJECT")
        # Vertex groups belong to the mesh, so a mesh several selected objects share is renamed once.
        meshes = {obj.data.as_pointer(): obj for obj in reversed(selected)}
        count = sum(mirror_vertex_groups(obj) for obj in meshes.values())
        return OperationResult.finished(
            f"Mirrored {count} vertex groups.", payload=count
        )
    finally:
        if original_mode != "OBJECT":
            safe_mode_switch(original_mode)


def _largest_face(mesh):
    """The index of the mesh's largest face, whose normal shows which way the faces wind"""
    if not mesh.polygons:
        return None
    areas = np.empty(len(mesh.polygons), dtype=np.float64)
    mesh.polygons.foreach_get("area", areas)
    return int(np.argmax(areas))


def _world_face_normal(obj, index):
    return (
        obj.matrix_world.to_3x3().inverted_safe().transposed()
        @ obj.data.polygons[index].normal
    ).normalized()


def mirror_selected_meshes_x(context):
    selected = selected_meshes(context)
    if not selected:
        return OperationResult.cancelled("No meshes selected.")
    # Mirroring applies each object's transform to its mesh, which a mesh shared with other objects cannot take.
    refusal = shared_mesh_refusal(selected, "mirror")
    if refusal is not None:
        return refusal
    store_current_context()
    try:
        safe_mode_switch("OBJECT")
        count = 0
        for obj in selected:
            select_objects(obj, context=context, reveal=True)
            face = _largest_face(obj.data)
            expected = None
            if face is not None:
                normal = _world_face_normal(obj, face)
                expected = Vector((-normal.x, normal.y, normal.z))
            require_finished(
                bpy.ops.transform.resize(
                    value=(-1, 1, 1),
                    orient_type="GLOBAL",
                    constraint_axis=(True, False, False),
                    mirror=True,
                ),
                f"Mirroring {obj.name}",
            )
            require_finished(
                bpy.ops.object.transform_apply(
                    location=True, rotation=True, scale=True
                ),
                f"Applying the mirrored transform on {obj.name}",
            )
            # Applying a negative scale reverses the winding in Blender 5.1 and later but not in 5.0; flip the faces
            # only where they now point inward.
            if (
                expected is not None
                and _world_face_normal(obj, face).dot(expected) < 0.0
            ):
                safe_mode_switch("EDIT")
                require_finished(
                    bpy.ops.mesh.select_all(action="SELECT"),
                    f"Selecting the mirrored geometry on {obj.name}",
                )
                require_finished(
                    bpy.ops.mesh.flip_normals(),
                    f"Flipping the mirrored normals on {obj.name}",
                )
                safe_mode_switch("OBJECT")
            count += mirror_vertex_groups(obj)
        return OperationResult.finished(
            f"Mirrored {count} vertex groups across {len(selected)} mesh(es).",
            payload=len(selected),
        )
    except Exception as error:
        return OperationResult.cancelled(f"Mirror failed: {error}", error=error)
    finally:
        restore_previous_context()


def mirror_vertex_groups(mesh):
    num_replaced = 0
    vertex_groups = mesh.vertex_groups[:]

    # Delay renaming until both sides are collected to avoid duplicate names.
    for vertex_group in vertex_groups:
        if vertex_group.name.startswith("r_"):
            vertex_group.name = vertex_group.name.replace("r_", "REPLACEME_l_", 1)
            continue
        if vertex_group.name.startswith("l_"):
            vertex_group.name = vertex_group.name.replace("l_", "REPLACEME_r_", 1)
            continue
        if vertex_group.name.startswith("Left"):
            vertex_group.name = vertex_group.name.replace("Left", "REPLACEME_Right", 1)
            continue
        if vertex_group.name.startswith("Right"):
            vertex_group.name = vertex_group.name.replace("Right", "REPLACEME_Left", 1)
            continue

    num_replaced = 0
    for vertex_group in vertex_groups:
        if not "REPLACEME_" in vertex_group.name:
            continue
        num_replaced += 1
        vertex_group.name = vertex_group.name.replace("REPLACEME_", "")

        if vertex_group.name == "l_butterfly_top_CRV_top_out_JNT":
            vertex_group.name = "l_butterfly_top_CRV_bot_out_JNT"
        if vertex_group.name == "r_butterfly_top_CRV_bot_out_JNT":
            vertex_group.name = "r_butterfly_top_CRV_top_out_JNT"
        continue
    return num_replaced
