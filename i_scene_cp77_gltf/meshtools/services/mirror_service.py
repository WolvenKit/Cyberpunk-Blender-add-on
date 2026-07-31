import bpy

from ...blender.context import restore_previous_context, safe_mode_switch, store_current_context
from ..model import MeshToolResult


def mirror_selected_vertex_groups(context):
    selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
    if not selected:
        return MeshToolResult.failure("No meshes selected.")
    original_mode = context.mode
    try:
        safe_mode_switch("OBJECT")
        count = sum(mirror_vertex_groups(obj) for obj in selected)
        return MeshToolResult.success(f"Mirrored {count} vertex groups.", payload=count)
    finally:
        if original_mode != "OBJECT":
            safe_mode_switch(original_mode)


def mirror_selected_meshes_x(context):
    selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
    if not selected:
        return MeshToolResult.failure("No meshes selected.")
    store_current_context()
    try:
        safe_mode_switch("OBJECT")
        count = 0
        for obj in selected:
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            context.view_layer.objects.active = obj
            bpy.ops.transform.resize(
                value=(-1, 1, 1),
                orient_type="GLOBAL",
                constraint_axis=(True, False, False),
                mirror=True,
            )
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            safe_mode_switch("EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.flip_normals()
            safe_mode_switch("OBJECT")
            count += mirror_vertex_groups(obj)
        return MeshToolResult.success(
            f"Mirrored {count} vertex groups across {len(selected)} mesh(es).",
            payload=len(selected),
        )
    except Exception as error:
        return MeshToolResult.failure(f"Mirror failed: {error}")
    finally:
        restore_previous_context()


def mirror_vertex_groups(mesh):
    num_replaced = 0
    vertex_groups = mesh.vertex_groups[:]

    # we'll end up with duplicate names if we rename right away
    for vertex_group in vertex_groups:
        if vertex_group.name.startswith('r_'):
            vertex_group.name = vertex_group.name.replace('r_', 'REPLACEME_l_', 1)
            continue
        if vertex_group.name.startswith('l_'):
            vertex_group.name = vertex_group.name.replace('l_', 'REPLACEME_r_', 1)
            continue
        if vertex_group.name.startswith('Left'):
            vertex_group.name = vertex_group.name.replace('Left', 'REPLACEME_Right', 1)
            continue
        if vertex_group.name.startswith('Right'):
            vertex_group.name = vertex_group.name.replace('Right', 'REPLACEME_Left', 1)
            continue

    num_replaced = 0
    for vertex_group in vertex_groups:
        if not 'REPLACEME_' in vertex_group.name:
            continue
        num_replaced += 1
        vertex_group.name = vertex_group.name.replace('REPLACEME_', '')
        # two extra cases just for CDPR
        if vertex_group.name == 'l_butterfly_top_CRV_top_out_JNT':
            vertex_group.name = 'l_butterfly_top_CRV_bot_out_JNT'
        if vertex_group.name == 'r_butterfly_top_CRV_bot_out_JNT':
            vertex_group.name = 'r_butterfly_top_CRV_top_out_JNT'
        continue
    return num_replaced
