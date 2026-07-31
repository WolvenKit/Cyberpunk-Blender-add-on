import bpy

from ..model import MeshToolResult
from .cloth_common import (
    _invalidate_viz,
    _require_active_mesh,
    _restore_disabled_cloth_modifiers,
)


def execute_apply_cloth_sim(context, report):
    obj = _require_active_mesh(context)
    if not obj:
        return MeshToolResult.failure()
    target = getattr(obj.cp77_cloth, 'bake_target', 'SHAPE_KEY')
    if target == 'DUPLICATE':
        dup = obj.copy()
        dup.data = obj.data.copy()
        dup.name = f'{obj.name}_cloth_bake'
        dup.data.name = f'{obj.data.name}_cloth_bake'
        context.collection.objects.link(dup)
        dup.matrix_world = obj.matrix_world.copy()
        obj.cp77_cloth.workflow_state = 'BAKED'
        report({'INFO'}, f'Baked duplicate: {dup.name}')
        return MeshToolResult.success()
    if target == 'SHAPE_KEY':
        if obj.data.shape_keys is None:
            obj.shape_key_add(name='Basis', from_mix=False)
        key_name = obj.cp77_cloth.bake_shape_key or 'Cloth Sim'
        key = obj.data.shape_keys.key_blocks.get(key_name)
        if key is None:
            key = obj.shape_key_add(name=key_name, from_mix=False)
        for v in obj.data.vertices:
            key.data[v.index].co = v.co
        key.value = 1.0
        obj.cp77_cloth.workflow_state = 'BAKED'
        report({'INFO'}, f'Baked shape key: {key.name}')
        return MeshToolResult.success()
    bpy.ops.ed.undo_push(message='Apply Cloth Simulation')
    obj.data.update()
    obj.cp77_cloth.workflow_state = 'BAKED'
    report({'INFO'}, 'Cloth pose committed to mesh')
    return MeshToolResult.success()


def execute_reset_garment_sim(context, report):
    obj = _require_active_mesh(context)
    if not obj:
        return MeshToolResult.failure()
    try:
        context.scene.physx.sim_running = False
    except Exception:
        pass
    try:
        from ...collisiontools.pxbridge import pxbridge as _bridge
        if obj.cp77_cloth_handle not in {'', '0', '-1'}:
            _bridge.nvcloth_remove_cloth(int(obj.cp77_cloth_handle))
    except Exception:
        pass
    obj.cp77_cloth_handle = '-1'
    obj.cp77_cloth.workflow_state = 'DRAFT'
    obj.cp77_cloth.validation_status = 'Reset'
    _restore_disabled_cloth_modifiers(obj)
    _invalidate_viz()
    report({'INFO'}, 'Garment simulation reset')
    return MeshToolResult.success()
