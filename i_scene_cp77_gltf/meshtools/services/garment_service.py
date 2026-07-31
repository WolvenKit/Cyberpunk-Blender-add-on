import bpy

from ..model import MeshToolResult
from .cloth_common import (
    _assign_group_weights,
    _axis_band_indices,
    _ensure_motion_group,
    _ensure_pin_group,
    _physx_ops_module,
    _require_active_mesh,
    _selected_vertex_indices,
)


def execute_assign_avatar_to_garment(context, report):
    garment = _require_active_mesh(context)
    if not garment:
        report({'ERROR'}, 'Active object must be a garment mesh.')
        return MeshToolResult.failure()
    selected_armatures = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
    avatar = selected_armatures[0] if selected_armatures else None
    if not avatar:
        for obj in context.scene.objects:
            if obj.type == 'ARMATURE' and hasattr(obj, 'cp77_avatar') and obj.cp77_avatar.enabled:
                avatar = obj
                break
    if not avatar:
        report({'ERROR'}, 'Select or create an avatar profile armature.')
        return MeshToolResult.failure()
    garment.cp77_cloth.avatar_armature = avatar
    garment.cp77_cloth.workflow_state = 'DRAFT'
    report({'INFO'}, f'Assigned avatar: {avatar.name}')
    return MeshToolResult.success()


def execute_validate_garment(context, report):
    obj = _require_active_mesh(context)
    if not obj:
        report({'ERROR'}, 'Select a mesh garment.')
        return MeshToolResult.failure()
    ops = _physx_ops_module()
    if not ops:
        report({'ERROR'}, 'PxBridge cloth operators are not available.')
        return MeshToolResult.failure()
    obj.cp77_cloth.enabled = True
    errors, warnings, stats = ops.validate_cloth_object(obj, context)
    ops.write_cloth_validation(obj, errors, warnings, stats)
    if errors:
        report({'ERROR'}, obj.cp77_cloth.validation_status)
        return MeshToolResult.failure()
    if warnings:
        report({'WARNING'}, obj.cp77_cloth.validation_status)
    else:
        report({'INFO'}, obj.cp77_cloth.validation_status)
    return MeshToolResult.success()


def execute_prepare_garment(context, report):
    obj = _require_active_mesh(context)
    if not obj:
        report({'ERROR'}, 'Select a mesh garment.')
        return MeshToolResult.failure()
    obj.cp77_cloth.enabled = True
    result = bpy.ops.cp77.validate_garment()
    if 'CANCELLED' in result:
        return MeshToolResult.failure()
    if not context.scene.physx.is_initialized:
        bpy.ops.physx.init_scene(add_ground=False)
    result = bpy.ops.physx.build_scene()
    if 'CANCELLED' in result:
        obj.cp77_cloth.workflow_state = 'ERROR'
        return MeshToolResult.failure()
    report({'INFO'}, obj.cp77_cloth.validation_status or 'Garment prepared')
    return MeshToolResult.success()


def execute_pin_cloth_verts(context, report):
    obj = _require_active_mesh(context)
    if not obj:
        return MeshToolResult.failure()
    vg = _ensure_pin_group(obj)
    obj.vertex_groups.active_index = vg.index
    bpy.ops.object.vertex_group_assign()
    obj.cp77_cloth.workflow_state = 'DRAFT'
    return MeshToolResult.success()


def execute_unpin_cloth_verts(context, report):
    obj = _require_active_mesh(context)
    if not obj:
        return MeshToolResult.failure()
    vg_name = obj.cp77_cloth.pin_vg
    if vg_name and vg_name in obj.vertex_groups:
        vg = obj.vertex_groups.get(vg_name)
        obj.vertex_groups.active_index = vg.index
        bpy.ops.object.vertex_group_remove_from()
        obj.cp77_cloth.workflow_state = 'DRAFT'
    return MeshToolResult.success()


def execute_pin_upper_garment_band(context, report, band_percent):
    obj = _require_active_mesh(context)
    if not obj:
        return MeshToolResult.failure()
    vg = _ensure_pin_group(obj)
    verts = obj.data.vertices
    if not verts:
        return MeshToolResult.failure()
    z_min = min((v.co.z for v in verts))
    z_max = max((v.co.z for v in verts))
    threshold = z_max - max((z_max - z_min) * band_percent, 1e-05)
    indices = [v.index for v in verts if v.co.z >= threshold]
    if not indices:
        return MeshToolResult.failure()
    vg.add(indices, 1.0, 'REPLACE')
    obj.cp77_cloth.workflow_state = 'DRAFT'
    report({'INFO'}, f'Pinned {len(indices)} vertices')
    return MeshToolResult.success()


def execute_clear_cloth_pins(context, report):
    obj = _require_active_mesh(context)
    if not obj:
        return MeshToolResult.failure()
    vg_name = obj.cp77_cloth.pin_vg
    vg = obj.vertex_groups.get(vg_name) if vg_name else None
    if vg:
        vg.remove([v.index for v in obj.data.vertices])
    obj.cp77_cloth.workflow_state = 'DRAFT'
    return MeshToolResult.success()


def execute_create_motion_constraint_group(context, report):
    obj = _require_active_mesh(context)
    if not obj:
        return MeshToolResult.failure()
    name = obj.cp77_cloth.motion_constraint_vg or 'MOTION_LIMIT'
    obj.cp77_cloth.motion_constraint_vg = name
    if name not in obj.vertex_groups:
        obj.vertex_groups.new(name=name)
    obj.cp77_cloth.workflow_state = 'DRAFT'
    report({'INFO'}, f'Motion constraint group ready: {name}')
    return MeshToolResult.success()


def execute_copy_pins_to_motion_constraints(context, report):
    obj = _require_active_mesh(context)
    if not obj:
        return MeshToolResult.failure()
    source_name = obj.cp77_cloth.pin_vg
    if not source_name or source_name not in obj.vertex_groups:
        report({'ERROR'}, 'Pin group does not exist')
        return MeshToolResult.failure()
    target_name = obj.cp77_cloth.motion_constraint_vg or 'MOTION_LIMIT'
    obj.cp77_cloth.motion_constraint_vg = target_name
    source = obj.vertex_groups[source_name]
    target = obj.vertex_groups.get(target_name) or obj.vertex_groups.new(name=target_name)
    copied = 0
    for vert in obj.data.vertices:
        weight = 0.0
        for group in vert.groups:
            if group.group == source.index:
                weight = max(weight, group.weight)
        if weight > 0.0:
            target.add([vert.index], weight, 'REPLACE')
            copied += 1
    obj.cp77_cloth.motion_constraint_source = 'MOTION_GROUP'
    obj.cp77_cloth.workflow_state = 'DRAFT'
    report({'INFO'}, f'Copied {copied} pin weights to {target.name}')
    return MeshToolResult.success()


def execute_create_separation_constraint_group(context, report):
    obj = _require_active_mesh(context)
    if not obj:
        return MeshToolResult.failure()
    name = obj.cp77_cloth.separation_constraint_vg or 'SEPARATION'
    obj.cp77_cloth.separation_constraint_vg = name
    if name not in obj.vertex_groups:
        obj.vertex_groups.new(name=name)
    obj.cp77_cloth.workflow_state = 'DRAFT'
    report({'INFO'}, f'Separation constraint group ready: {name}')
    return MeshToolResult.success()


def execute_apply_sample_cloth_defaults(context, report):
    obj = _require_active_mesh(context)
    if not obj:
        report({'ERROR'}, 'Active object must be a garment mesh.')
        return MeshToolResult.failure()
    cloth = obj.cp77_cloth
    cloth.enabled = True
    cloth.quality_preset = 'PREVIEW'
    if cloth.fabric_preset == 'CUSTOM':
        cloth.fabric_preset = 'COTTON'
    cloth.continuous_collision = True
    cloth.collision_mass_scale = 3.0
    cloth.friction = 0.5
    cloth.solver_frequency = 300.0
    cloth.stiffness_frequency = 120.0
    cloth.damping = 0.12
    cloth.linear_drag = 0.05
    cloth.self_collision_distance = 0.004
    cloth.self_collision_stiffness = 0.5
    cloth.motion_constraint_radius = 0.08
    cloth.motion_constraint_min_radius = 0.0
    cloth.motion_constraint_stiffness = 0.85
    cloth.motion_constraint_scale = 1.0
    cloth.motion_constraint_bias = 0.0
    cloth.workflow_state = 'DRAFT'
    report({'INFO'}, 'Applied sample-aligned cloth defaults')
    return MeshToolResult.success()


def execute_create_fixed_seam_pins(context, report, band_percent, fallback_band):
    obj = _require_active_mesh(context)
    if not obj:
        return MeshToolResult.failure()
    indices = _selected_vertex_indices(obj)
    if not indices and fallback_band == 'UPPER':
        indices = _axis_band_indices(obj, 'Z', 'MAX', band_percent)
    elif not indices and fallback_band == 'LOWER':
        indices = _axis_band_indices(obj, 'Z', 'MIN', band_percent)
    if not indices:
        report({'ERROR'}, 'Select seam vertices or choose a band fallback')
        return MeshToolResult.failure()
    vg = _ensure_pin_group(obj)
    count = _assign_group_weights(vg, indices, 1.0)
    obj.cp77_cloth.workflow_state = 'DRAFT'
    report({'INFO'}, f'Pinned {count} fixed seam vertices')
    return MeshToolResult.success()


def execute_add_motion_constraint_zone(context, report, band_percent, weight, zone_type):
    obj = _require_active_mesh(context)
    if not obj:
        return MeshToolResult.failure()
    indices = _selected_vertex_indices(obj)
    if not indices:
        if zone_type == 'COLLAR':
            indices = _axis_band_indices(obj, 'Z', 'MAX', band_percent)
        elif zone_type == 'WAIST':
            indices = _axis_band_indices(obj, 'Z', 'MAX', band_percent)
        elif zone_type == 'LEFT_CUFF':
            indices = _axis_band_indices(obj, 'X', 'MIN', band_percent)
        elif zone_type == 'RIGHT_CUFF':
            indices = _axis_band_indices(obj, 'X', 'MAX', band_percent)
    if not indices:
        report({'ERROR'}, 'Select vertices for this motion zone')
        return MeshToolResult.failure()
    cloth = obj.cp77_cloth
    vg = _ensure_motion_group(obj)
    count = _assign_group_weights(vg, indices, weight)
    cloth.motion_constraint_source = 'MOTION_GROUP'
    if zone_type in {'COLLAR', 'WAIST'}:
        cloth.motion_constraint_radius = 0.07
        cloth.motion_constraint_stiffness = 0.85
    elif zone_type in {'LEFT_CUFF', 'RIGHT_CUFF'}:
        cloth.motion_constraint_radius = 0.055
        cloth.motion_constraint_stiffness = 0.8
    elif zone_type == 'TACKS':
        cloth.motion_constraint_radius = 0.035
        cloth.motion_constraint_stiffness = 0.95
    cloth.motion_constraint_min_radius = 0.0
    cloth.motion_constraint_scale = 1.0
    cloth.motion_constraint_bias = 0.0
    cloth.workflow_state = 'DRAFT'
    report({'INFO'}, f'Added {count} vertices to {vg.name}')
    return MeshToolResult.success()
