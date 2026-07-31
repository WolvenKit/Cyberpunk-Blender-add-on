import bpy

from ..model import MeshToolResult
from .cloth_common import (
    _bone_world_pos,
    _bone_world_tail,
    _generate_default_avatar_anchors,
    _invalidate_viz,
    _require_active_armature,
)


def _detect_avatar_region(*bone_names):
    joined = ' '.join([n or '' for n in bone_names]).lower()
    if any((k in joined for k in ('head', 'neck'))):
        return 'HEAD'
    if any((k in joined for k in ('arm', 'hand', 'shoulder', 'forearm'))):
        return 'ARM'
    if any((k in joined for k in ('leg', 'foot', 'toe', 'thigh', 'calf'))):
        return 'LEG'
    if any((k in joined for k in ('hip', 'pelvis'))):
        return 'PELVIS'
    if any((k in joined for k in ('spine', 'chest', 'torso'))):
        return 'TORSO'
    return 'CUSTOM'


def _region_default_radius(region):
    return {'TORSO': 0.105, 'PELVIS': 0.115, 'ARM': 0.055, 'LEG': 0.075, 'HEAD': 0.095, 'CUSTOM': 0.08}.get(region, 0.08)


def _region_fit_max_radius(region):
    return {'TORSO': 0.22, 'PELVIS': 0.22, 'ARM': 0.105, 'LEG': 0.145, 'HEAD': 0.16, 'CUSTOM': 0.18}.get(region, 0.18)


def _avatar_region_inflate(profile, region):
    if not profile:
        return 0.0
    if region == 'TORSO':
        return profile.torso_inflate
    if region == 'PELVIS':
        return profile.pelvis_inflate
    if region == 'ARM':
        return profile.arm_inflate
    if region == 'LEG':
        return profile.leg_inflate
    if region == 'HEAD':
        return profile.head_inflate
    return 0.0


def _find_avatar_body_mesh(armature, context):
    profile = getattr(armature, 'cp77_avatar', None)
    if profile and profile.body_mesh and (profile.body_mesh.type == 'MESH'):
        return profile.body_mesh
    for obj in context.scene.objects:
        if obj.type != 'MESH':
            continue
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object == armature:
                if profile:
                    profile.body_mesh = obj
                return obj
        if obj.parent == armature:
            if profile:
                profile.body_mesh = obj
            return obj
    return None


def _point_segment_distance(p, a, b):
    ab = b - a
    denom = ab.dot(ab)
    if denom <= 1e-12:
        return (p - a).length
    t = max(0.0, min(1.0, (p - a).dot(ab) / denom))
    return (p - (a + ab * t)).length


def _point_segment_projection(p, a, b):
    ab = b - a
    denom = ab.dot(ab)
    if denom <= 1e-12:
        return 0.0
    return (p - a).dot(ab) / denom


def _percentile(values, pct):
    vals = sorted((v for v in values if v is not None and v >= 0.0))
    if not vals:
        return None
    idx = int(round((len(vals) - 1) * max(0.0, min(1.0, pct))))
    return vals[idx]


def _mesh_points_for_bones(mesh_obj, bone_names):
    if not mesh_obj or mesh_obj.type != 'MESH':
        return ([], False)
    group_indices = set()
    for bone_name in bone_names:
        if bone_name and bone_name in mesh_obj.vertex_groups:
            group_indices.add(mesh_obj.vertex_groups[bone_name].index)
    source_mesh = mesh_obj.data
    coords = None
    try:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = mesh_obj.evaluated_get(depsgraph)
        eval_mesh = eval_obj.to_mesh()
        try:
            if len(eval_mesh.vertices) == len(source_mesh.vertices):
                coords = [mesh_obj.matrix_world @ v.co for v in eval_mesh.vertices]
        finally:
            eval_obj.to_mesh_clear()
    except Exception:
        coords = None
    if coords is None:
        coords = [mesh_obj.matrix_world @ v.co for v in source_mesh.vertices]
    points = []
    used_weights = bool(group_indices)
    for i, vert in enumerate(source_mesh.vertices):
        if group_indices:
            if not any((g.group in group_indices and g.weight > 0.03 for g in vert.groups)):
                continue
        if i < len(coords):
            points.append(coords[i])
    return (points, used_weights)


def _collider_fit_segment(armature, collider):
    if collider.collider_type == 'CAPSULE' and collider.target_bone:
        a = _bone_world_pos(armature, collider.bone)
        b = _bone_world_pos(armature, collider.target_bone)
    else:
        a = _bone_world_pos(armature, collider.bone)
        b = _bone_world_tail(armature, collider.bone)
    if a is None or b is None or (b - a).length <= 1e-05:
        return (None, None)
    return (a, b)


def _fit_collider_radius(armature, mesh_obj, collider, profile):
    if not mesh_obj:
        return None
    points, used_weights = _mesh_points_for_bones(mesh_obj, [collider.bone, collider.target_bone])
    if not points:
        points = [mesh_obj.matrix_world @ v.co for v in mesh_obj.data.vertices]
        used_weights = False
    if not points:
        return None
    a, b = _collider_fit_segment(armature, collider)
    if a is None or b is None:
        center = _bone_world_pos(armature, collider.bone)
        if center is None:
            return None
        distances = [(p - center).length for p in points]
    else:
        candidates = []
        segment_len = max((b - a).length, 1e-05)
        lo, hi = (-0.2, 1.2) if used_weights else (-0.05, 1.05)
        for p in points:
            t = _point_segment_projection(p, a, b)
            if lo <= t <= hi:
                d = _point_segment_distance(p, a, b)
                if d <= max(_region_fit_max_radius(getattr(collider, 'region', 'CUSTOM')) * 2.5, segment_len * 0.85):
                    candidates.append(d)
        if not candidates:
            all_distances = sorted((_point_segment_distance(p, a, b) for p in points))
            keep = max(8, min(len(all_distances), int(len(all_distances) * 0.05)))
            candidates = all_distances[:keep]
        distances = candidates
    fit_pct = profile.auto_fit_percentile if profile else 0.55
    radius = _percentile(distances, fit_pct)
    if radius is None:
        return None
    region = getattr(collider, 'region', 'CUSTOM')
    hard_max = _region_fit_max_radius(region)
    if profile:
        hard_max = min(float(profile.max_radius), hard_max)
        radius = max(float(profile.min_radius), min(hard_max, radius))
    else:
        radius = min(hard_max, radius)
    return radius


def _clear_old_default_avatar_inflates(profile):
    if not profile:
        return
    old_defaults = {'global_inflate': 0.015, 'torso_inflate': 0.015, 'pelvis_inflate': 0.015, 'arm_inflate': 0.01, 'leg_inflate': 0.012, 'head_inflate': 0.01}
    for prop, old_value in old_defaults.items():
        if abs(float(getattr(profile, prop, 0.0)) - old_value) < 1e-06:
            setattr(profile, prop, 0.0)


def _add_avatar_collider(armature, name, collider_type, bone, target_bone='', radius=None, region=None):
    if not bone or bone not in armature.data.bones:
        return None
    if collider_type == 'CAPSULE' and (not target_bone or target_bone not in armature.data.bones):
        return None
    region = region or _detect_avatar_region(bone, target_bone)
    item = armature.cp77_cloth_colliders.add()
    item.name = name
    item.enabled = True
    item.collider_type = collider_type
    item.region = region
    item.bone = bone
    item.target_bone = target_bone
    item.radius = radius if radius is not None else _region_default_radius(region)
    return item


def _generate_default_avatar_colliders(armature):
    armature.cp77_cloth_colliders.clear()
    bones_to_spheres = ['Head', 'Hips', 'LeftArm', 'LeftFoot', 'LeftForeArm', 'LeftHand', 'LeftHandMiddle2', 'LeftLeg', 'LeftToeBase', 'LeftUpLeg', 'Neck1', 'RightArm', 'RightFoot', 'RightForeArm', 'RightHand', 'RightHandMiddle2', 'RightLeg', 'RightToeBase', 'RightUpLeg', 'Spine', 'Spine1', 'Spine2', 'Spine3']
    for bone_name in bones_to_spheres:
        region = _detect_avatar_region(bone_name)
        _add_avatar_collider(armature, f'Sphere_{bone_name}', 'SPHERE', bone_name, radius=_region_default_radius(region), region=region)
    capsules = [('Hips', 'Spine'), ('Hips', 'LeftUpLeg'), ('Hips', 'RightUpLeg'), ('Spine', 'Spine1'), ('Spine1', 'Spine2'), ('Spine2', 'Spine3'), ('Spine3', 'LeftArm'), ('Spine3', 'RightArm'), ('Spine3', 'Neck1'), ('Neck1', 'Head'), ('LeftArm', 'LeftForeArm'), ('LeftForeArm', 'LeftHand'), ('LeftHand', 'LeftHandMiddle2'), ('LeftUpLeg', 'LeftLeg'), ('LeftLeg', 'LeftFoot'), ('LeftFoot', 'LeftToeBase'), ('RightArm', 'RightForeArm'), ('RightForeArm', 'RightHand'), ('RightHand', 'RightHandMiddle2'), ('RightUpLeg', 'RightLeg'), ('RightLeg', 'RightFoot'), ('RightFoot', 'RightToeBase')]
    for parent_bone, child_bone in capsules:
        region = _detect_avatar_region(parent_bone, child_bone)
        _add_avatar_collider(armature, f'Capsule_{parent_bone}_{child_bone}', 'CAPSULE', parent_bone, child_bone, radius=_region_default_radius(region), region=region)
    armature.cp77_avatar.last_sphere_count = len([c for c in armature.cp77_cloth_colliders if c.collider_type == 'SPHERE'])
    armature.cp77_avatar.last_capsule_count = len([c for c in armature.cp77_cloth_colliders if c.collider_type == 'CAPSULE'])


def _validate_avatar_profile(armature):
    errors = []
    warnings = []
    profile = armature.cp77_avatar
    spheres = 0
    capsules = 0
    for col in armature.cp77_cloth_colliders:
        if not getattr(col, 'enabled', True):
            continue
        if not col.bone or col.bone not in armature.data.bones:
            errors.append(f"{col.name}: missing source bone '{col.bone}'")
            continue
        if col.collider_type == 'CAPSULE':
            if not col.target_bone or col.target_bone not in armature.data.bones:
                errors.append(f"{col.name}: missing target bone '{col.target_bone}'")
                continue
            capsules += 1
        else:
            spheres += 1
        if col.radius <= 0.001:
            warnings.append(f'{col.name}: radius is very small')
    uses_mesh = bool(getattr(profile, 'use_mesh_collision', False))
    has_body_mesh = bool(profile.body_mesh and profile.body_mesh.type == 'MESH')
    if spheres + capsules == 0 and (not (uses_mesh and has_body_mesh)):
        errors.append('Avatar profile has no body mesh collision source or enabled primitive colliders')
    if uses_mesh and (not has_body_mesh):
        warnings.append('No body mesh assigned; mesh avatar collision will fall back to primitives')
    elif not uses_mesh and (not profile.body_mesh):
        warnings.append('No body mesh assigned; auto-fit will use defaults')
    if not armature.cp77_avatar_anchors:
        warnings.append('No arrangement anchors generated')
    profile.last_sphere_count = spheres
    profile.last_capsule_count = capsules
    profile.last_anchor_count = len(armature.cp77_avatar_anchors)
    if errors:
        profile.state = 'ERROR'
        profile.status = '; '.join(errors[:3])
    else:
        profile.state = 'READY'
        mesh_label = 'mesh' if getattr(profile, 'use_mesh_collision', False) and has_body_mesh else 'primitives'
        profile.status = f'Ready: {mesh_label}, {spheres} spheres, {capsules} capsules, {len(armature.cp77_avatar_anchors)} anchors'
    profile.errors = '\n'.join(errors + warnings)
    return (errors, warnings)


def execute_setup_cloth_colliders(context, report):
    armature = _require_active_armature(context)
    if not armature:
        report({'ERROR'}, 'Select an armature.')
        return MeshToolResult.failure()
    profile = armature.cp77_avatar
    profile.enabled = True
    profile.profile_name = profile.profile_name or f'{armature.name} Avatar'
    _generate_default_avatar_colliders(armature)
    if len(armature.cp77_avatar_anchors) == 0:
        _generate_default_avatar_anchors(armature)
    errors, warnings = _validate_avatar_profile(armature)
    _invalidate_viz()
    if errors:
        report({'ERROR'}, profile.status)
        return MeshToolResult.failure()
    report({'INFO'}, profile.status)
    return MeshToolResult.success()


def execute_add_cloth_collider(context, report):
    obj = context.active_object
    if obj and obj.type == 'ARMATURE':
        item = obj.cp77_cloth_colliders.add()
        item.name = 'New Collider'
        item.collider_type = 'SPHERE'
        obj.cp77_cloth_collider_index = len(obj.cp77_cloth_colliders) - 1
        _invalidate_viz()
    return MeshToolResult.success()


def execute_remove_cloth_collider(context, report):
    obj = context.active_object
    if obj and obj.type == 'ARMATURE' and (len(obj.cp77_cloth_colliders) > 0):
        idx = obj.cp77_cloth_collider_index
        obj.cp77_cloth_colliders.remove(idx)
        obj.cp77_cloth_collider_index = max(0, idx - 1)
        _invalidate_viz()
    return MeshToolResult.success()


def execute_fit_avatar_colliders(context, report):
    armature = _require_active_armature(context)
    if not armature:
        report({'ERROR'}, 'Select an armature.')
        return MeshToolResult.failure()
    if len(armature.cp77_cloth_colliders) == 0:
        _generate_default_avatar_colliders(armature)
    profile = armature.cp77_avatar
    mesh_obj = _find_avatar_body_mesh(armature, context)
    if not mesh_obj:
        profile.state = 'ERROR'
        profile.status = 'Assign a body mesh before auto-fitting.'
        profile.errors = profile.status
        report({'ERROR'}, profile.status)
        return MeshToolResult.failure()
    _clear_old_default_avatar_inflates(profile)
    fitted = 0
    for col in armature.cp77_cloth_colliders:
        radius = _fit_collider_radius(armature, mesh_obj, col, profile)
        if radius is not None:
            col.radius = radius
            fitted += 1
    errors, warnings = _validate_avatar_profile(armature)
    _invalidate_viz()
    if fitted == 0:
        profile.state = 'ERROR'
        profile.status = 'No collider radii could be fitted from the body mesh.'
        report({'ERROR'}, profile.status)
        return MeshToolResult.failure()
    report({'INFO'}, f'Fitted {fitted} avatar colliders from {mesh_obj.name}')
    return MeshToolResult.success()


def execute_generate_avatar_anchors(context, report):
    armature = _require_active_armature(context)
    if not armature:
        report({'ERROR'}, 'Select an armature.')
        return MeshToolResult.failure()
    _generate_default_avatar_anchors(armature)
    _validate_avatar_profile(armature)
    report({'INFO'}, f'Generated {len(armature.cp77_avatar_anchors)} arrangement anchors')
    return MeshToolResult.success()


def execute_validate_avatar_profile(context, report):
    armature = _require_active_armature(context)
    if not armature:
        report({'ERROR'}, 'Select an armature.')
        return MeshToolResult.failure()
    errors, warnings = _validate_avatar_profile(armature)
    _invalidate_viz()
    if errors:
        report({'ERROR'}, armature.cp77_avatar.status)
        return MeshToolResult.failure()
    if warnings:
        report({'WARNING'}, armature.cp77_avatar.status)
    else:
        report({'INFO'}, armature.cp77_avatar.status)
    return MeshToolResult.success()


def execute_clear_avatar_profile(context, report):
    armature = _require_active_armature(context)
    if not armature:
        report({'ERROR'}, 'Select an armature.')
        return MeshToolResult.failure()
    armature.cp77_cloth_colliders.clear()
    armature.cp77_avatar_anchors.clear()
    armature.cp77_avatar.state = 'DRAFT'
    armature.cp77_avatar.status = 'Cleared'
    armature.cp77_avatar.errors = ''
    armature.cp77_avatar.last_sphere_count = 0
    armature.cp77_avatar.last_capsule_count = 0
    armature.cp77_avatar.last_anchor_count = 0
    _invalidate_viz()
    report({'INFO'}, 'Avatar profile cleared')
    return MeshToolResult.success()
