from ..model import MeshToolResult
from .cloth_common import (
    _assign_group_weights,
    _avatar_basis,
    _axis_band_indices,
    _create_grid_panel,
    _ensure_motion_group,
    _ensure_pin_group,
    _find_anchor,
    _generate_default_avatar_anchors,
    _require_active_armature,
)


def execute_create_arrangement_panel(context, report, height, offset, panel_type, segments_x, segments_y, width):
    armature = _require_active_armature(context)
    if not armature:
        report({'ERROR'}, 'Select an avatar armature.')
        return MeshToolResult.failure()
    if not armature.cp77_avatar_anchors:
        _generate_default_avatar_anchors(armature)
    right, forward, up = _avatar_basis(armature)
    _, collar = _find_anchor(armature, 'COLLAR', 'collar')
    _, chest = _find_anchor(armature, 'CHEST')
    _, waist = _find_anchor(armature, 'WAIST')
    _, left_shoulder = _find_anchor(armature, 'SHOULDER', 'left')
    _, right_shoulder = _find_anchor(armature, 'SHOULDER', 'right')
    _, left_wrist = _find_anchor(armature, 'WRIST', 'left')
    _, right_wrist = _find_anchor(armature, 'WRIST', 'right')
    panel = panel_type
    flip = False
    garment_type = 'CUSTOM'
    if panel in {'TORSO_FRONT', 'TORSO_BACK'}:
        if chest is None or waist is None:
            report({'ERROR'}, 'Chest and waist anchors are required')
            return MeshToolResult.failure()
        shoulder_width = (left_shoulder - right_shoulder).length if left_shoulder and right_shoulder else 0.55
        height = height or max((chest - waist).length * 1.25, 0.35)
        width = width or max(shoulder_width * 1.15, 0.35)
        direction = forward if panel == 'TORSO_FRONT' else -forward
        center = (chest + waist) * 0.5 + direction * offset
        name = 'Garment_Front_Torso' if panel == 'TORSO_FRONT' else 'Garment_Back_Torso'
        flip = panel == 'TORSO_BACK'
        garment_type = 'SHIRT'
    elif panel == 'SKIRT_FRONT':
        if waist is None:
            report({'ERROR'}, 'Waist anchor is required')
            return MeshToolResult.failure()
        width = width or 0.65
        height = height or 0.75
        center = waist + forward * offset - up * (height * 0.5)
        name = 'Garment_Front_Skirt'
        garment_type = 'SKIRT'
    elif panel == 'CAPE_BACK':
        anchor = collar or chest
        if anchor is None:
            report({'ERROR'}, 'Collar or chest anchor is required')
            return MeshToolResult.failure()
        shoulder_width = (left_shoulder - right_shoulder).length if left_shoulder and right_shoulder else 0.6
        width = width or max(shoulder_width * 1.45, 0.45)
        height = height or 1.05
        center = anchor - forward * max(offset, 0.12) - up * (height * 0.5)
        name = 'Garment_Back_Cape'
        garment_type = 'CAPE'
        flip = True
    elif panel in {'LEFT_SLEEVE', 'RIGHT_SLEEVE'}:
        shoulder = left_shoulder if panel == 'LEFT_SLEEVE' else right_shoulder
        wrist = left_wrist if panel == 'LEFT_SLEEVE' else right_wrist
        if shoulder is None or wrist is None:
            report({'ERROR'}, 'Shoulder and wrist anchors are required')
            return MeshToolResult.failure()
        arm_axis = (shoulder - wrist).normalized()
        width = width or 0.34
        height = height or max((shoulder - wrist).length, 0.45)
        center = (shoulder + wrist) * 0.5 + forward * offset
        name = 'Garment_Left_Sleeve' if panel == 'LEFT_SLEEVE' else 'Garment_Right_Sleeve'
        up = arm_axis
        garment_type = 'STRAP'
    else:
        report({'ERROR'}, 'Unsupported panel type')
        return MeshToolResult.failure()
    obj = _create_grid_panel(name, center, right, up, width, height, segments_x, segments_y, flip=flip)
    obj.cp77_cloth.enabled = True
    obj.cp77_cloth.avatar_armature = armature
    obj.cp77_cloth.garment_type = garment_type
    obj.cp77_cloth.fabric_preset = 'COTTON'
    obj.cp77_cloth.quality_preset = 'PREVIEW'
    obj.cp77_cloth.continuous_collision = True
    obj.cp77_cloth.collision_mass_scale = 3.0
    obj.cp77_cloth.friction = 0.5
    obj.cp77_cloth.solver_frequency = 300.0
    obj.cp77_cloth.self_collision_distance = 0.004
    obj.cp77_cloth.motion_constraint_source = 'MOTION_GROUP'
    obj.cp77_cloth.motion_constraint_radius = 0.07
    obj.cp77_cloth.motion_constraint_stiffness = 0.85
    pin = _ensure_pin_group(obj)
    motion = _ensure_motion_group(obj)
    top_indices = _axis_band_indices(obj, 'Z', 'MAX', 0.08)
    _assign_group_weights(pin, top_indices, 1.0)
    _assign_group_weights(motion, top_indices, 1.0)
    obj.cp77_cloth.workflow_state = 'DRAFT'
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    context.view_layer.objects.active = obj
    report({'INFO'}, f'Created {obj.name} with {len(obj.data.vertices)} particles')
    return MeshToolResult.success()
