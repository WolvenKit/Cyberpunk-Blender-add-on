from mathutils import Matrix

from ...blender.context import (
    restore_previous_context,
    safe_mode_switch,
    store_current_context,
)
from ...blender.operator_results import OperationResult
from ...blender.selection import selected_meshes
from ...blender.transactions import track_mesh_object, transactional
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


@transactional("Mesh mirror")
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
            track_mesh_object(obj)
            world = obj.matrix_world.copy()
            origin = world.translation
            mirrored = (
                Matrix.Translation(origin)
                @ Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0))
                @ Matrix.Translation(-origin)
                @ world
            )
            parent = world @ obj.matrix_basis.inverted_safe()
            obj.data.transform(parent.inverted_safe() @ mirrored, shape_keys=True)
            obj.data.flip_normals()
            obj.data.update()
            obj.matrix_basis = Matrix.Identity(4)
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
