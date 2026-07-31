import bpy
from mathutils import Vector


def _invalidate_viz():
    try:
        from ...collisiontools.pxbridge import viz
    except Exception:
        return
    viz.invalidate_visualization_cache()


def _physx_ops_module():
    try:
        from ...collisiontools.pxbridge import physx_ops
    except Exception:
        return None
    return physx_ops


def _require_active_mesh(context):
    obj = context.active_object
    if not obj or obj.type != 'MESH':
        return None
    return obj


def _ensure_pin_group(obj):
    vg_name = obj.cp77_cloth.pin_vg or 'PINNED_VERTS'
    obj.cp77_cloth.pin_vg = vg_name
    vg = obj.vertex_groups.get(vg_name)
    if not vg:
        vg = obj.vertex_groups.new(name=vg_name)
    return vg


def _ensure_motion_group(obj):
    vg_name = obj.cp77_cloth.motion_constraint_vg or 'MOTION_LIMIT'
    obj.cp77_cloth.motion_constraint_vg = vg_name
    vg = obj.vertex_groups.get(vg_name)
    if not vg:
        vg = obj.vertex_groups.new(name=vg_name)
    return vg


def _selected_vertex_indices(obj):
    previous_mode = obj.mode
    if previous_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    indices = [v.index for v in obj.data.vertices if v.select]
    if previous_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode=previous_mode)
    return indices


def _csv_from_indices(indices):
    seen = set()
    ordered = []
    for idx in indices:
        idx = int(idx)
        if idx not in seen:
            seen.add(idx)
            ordered.append(idx)
    return ','.join((str(i) for i in ordered))


def _indices_from_csv(value):
    result = []
    for token in (value or '').split(','):
        token = token.strip()
        if not token:
            continue
        try:
            result.append(int(token))
        except ValueError:
            continue
    return result


def _selected_edge_vertex_order(obj):
    previous_mode = obj.mode
    if previous_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    selected_edges = [edge for edge in obj.data.edges if edge.select]
    if not selected_edges:
        indices = [v.index for v in obj.data.vertices if v.select]
        if previous_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode=previous_mode)
        return _order_vertices_by_nearest(obj, indices)
    adjacency = {}
    for edge in selected_edges:
        a, b = edge.vertices
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    remaining = set(adjacency.keys())
    chains = []
    while remaining:
        endpoints = [idx for idx in remaining if len(adjacency.get(idx, ())) <= 1]
        start = endpoints[0] if endpoints else min(remaining)
        chain = []
        prev = None
        cur = start
        while cur in remaining:
            chain.append(cur)
            remaining.remove(cur)
            next_candidates = [n for n in adjacency.get(cur, ()) if n != prev and n in remaining]
            if not next_candidates:
                break
            next_candidates.sort(key=lambda n: (obj.data.vertices[n].co - obj.data.vertices[cur].co).length_squared)
            prev, cur = (cur, next_candidates[0])
        chains.append(chain)
    if previous_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode=previous_mode)
    if not chains:
        return []
    ordered = chains.pop(0)
    while chains:
        last = obj.data.vertices[ordered[-1]].co
        best_i = 0
        best_flip = False
        best_d = None
        for i, chain in enumerate(chains):
            d0 = (obj.data.vertices[chain[0]].co - last).length_squared
            d1 = (obj.data.vertices[chain[-1]].co - last).length_squared
            if best_d is None or d0 < best_d:
                best_i, best_flip, best_d = (i, False, d0)
            if d1 < best_d:
                best_i, best_flip, best_d = (i, True, d1)
        chain = chains.pop(best_i)
        if best_flip:
            chain.reverse()
        ordered.extend(chain)
    return ordered


def _order_vertices_by_nearest(obj, indices):
    remaining = list(dict.fromkeys(indices))
    if len(remaining) <= 2:
        return remaining
    ordered = [remaining.pop(0)]
    while remaining:
        last = obj.data.vertices[ordered[-1]].co
        best = min(range(len(remaining)), key=lambda i: (obj.data.vertices[remaining[i]].co - last).length_squared)
        ordered.append(remaining.pop(best))
    return ordered


def _set_vertex_selection(obj, indices):
    previous_mode = obj.mode
    if previous_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    wanted = set(indices)
    for vert in obj.data.vertices:
        vert.select = vert.index in wanted
    for edge in obj.data.edges:
        edge.select = edge.vertices[0] in wanted and edge.vertices[1] in wanted
    obj.data.update()
    if previous_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode=previous_mode)


def _active_seam_pair(obj):
    if not obj or not hasattr(obj, 'cp77_garment_seams') or (not obj.cp77_garment_seams):
        return None
    idx = max(0, min(obj.cp77_garment_seam_index, len(obj.cp77_garment_seams) - 1))
    obj.cp77_garment_seam_index = idx
    return obj.cp77_garment_seams[idx]


def _ensure_named_group(obj, name):
    vg = obj.vertex_groups.get(name)
    if not vg:
        vg = obj.vertex_groups.new(name=name)
    return vg


def _safe_group_name(prefix, name):
    cleaned = ''.join((c if c.isalnum() or c in '_-' else '_' for c in name or 'Seam'))
    return f'{prefix}_{cleaned}'[:63]


def _copy_cloth_defaults(source, target):
    if not hasattr(source, 'cp77_cloth') or not hasattr(target, 'cp77_cloth'):
        return
    src = source.cp77_cloth
    dst = target.cp77_cloth
    for attr in ('enabled', 'avatar_armature', 'workflow_state', 'garment_type', 'fabric_preset', 'quality_preset', 'pin_vg', 'motion_constraint_source', 'motion_constraint_vg', 'motion_constraint_radius', 'motion_constraint_min_radius', 'motion_constraint_scale', 'motion_constraint_bias', 'motion_constraint_stiffness', 'separation_constraint_source', 'separation_constraint_vg', 'collision_inflate', 'continuous_collision', 'collision_mass_scale', 'mass', 'drag', 'friction', 'damping', 'linear_drag', 'solver_frequency', 'stiffness_frequency', 'tether_scale', 'tether_stiffness', 'self_collision_distance', 'self_collision_stiffness', 'bake_target', 'bake_shape_key'):
        try:
            setattr(dst, attr, getattr(src, attr))
        except Exception:
            pass
    dst.enabled = True
    dst.workflow_state = 'DRAFT'


def _axis_band_indices(obj, axis='Z', side='MAX', fraction=0.08):
    axis_index = {'X': 0, 'Y': 1, 'Z': 2}.get(axis, 2)
    verts = obj.data.vertices
    if not verts:
        return []
    values = [v.co[axis_index] for v in verts]
    v_min = min(values)
    v_max = max(values)
    span = max(v_max - v_min, 1e-05)
    fraction = max(0.001, min(0.95, float(fraction)))
    if side == 'MIN':
        threshold = v_min + span * fraction
        return [v.index for v in verts if v.co[axis_index] <= threshold]
    if side == 'MID':
        center = (v_min + v_max) * 0.5
        half = span * fraction * 0.5
        return [v.index for v in verts if abs(v.co[axis_index] - center) <= half]
    threshold = v_max - span * fraction
    return [v.index for v in verts if v.co[axis_index] >= threshold]


def _assign_group_weights(vg, indices, weight=1.0):
    if not indices:
        return 0
    vg.add(list(sorted(set(indices))), max(0.0, min(1.0, float(weight))), 'REPLACE')
    return len(set(indices))


def _bone_world_pos(armature, bone_name):
    if not armature or not bone_name:
        return None
    if hasattr(armature, 'pose') and bone_name in armature.pose.bones:
        return armature.matrix_world @ armature.pose.bones[bone_name].matrix.translation
    if bone_name in armature.data.bones:
        return armature.matrix_world @ armature.data.bones[bone_name].head_local
    return None


def _bone_world_tail(armature, bone_name):
    if not armature or not bone_name:
        return None
    if hasattr(armature, 'pose') and bone_name in armature.pose.bones:
        return armature.matrix_world @ armature.pose.bones[bone_name].tail
    if bone_name in armature.data.bones:
        return armature.matrix_world @ armature.data.bones[bone_name].tail_local
    return None


def _anchor_world_pos(armature, anchor):
    if not armature or not anchor:
        return None
    try:
        return armature.matrix_world @ Vector(anchor.local_pos)
    except Exception:
        return _bone_world_pos(armature, getattr(anchor, 'bone', ''))


def _find_anchor(armature, anchor_type, name_contains=''):
    name_contains = name_contains.lower()
    for anchor in getattr(armature, 'cp77_avatar_anchors', []):
        if anchor.anchor_type != anchor_type:
            continue
        if name_contains and name_contains not in anchor.name.lower():
            continue
        pos = _anchor_world_pos(armature, anchor)
        if pos is not None:
            return (anchor, pos)
    return (None, None)


def _avatar_basis(armature):
    q = armature.matrix_world.to_quaternion()
    right = q @ Vector((1.0, 0.0, 0.0))
    forward = q @ Vector((0.0, -1.0, 0.0))
    up = q @ Vector((0.0, 0.0, 1.0))
    return (right.normalized(), forward.normalized(), up.normalized())


def _create_grid_panel(name, center, right, up, width, height, segments_x, segments_y, flip=False):
    segments_x = max(1, int(segments_x))
    segments_y = max(1, int(segments_y))
    verts = []
    faces = []
    for y in range(segments_y + 1):
        fy = y / segments_y - 0.5
        for x in range(segments_x + 1):
            fx = x / segments_x - 0.5
            p = center + right * (fx * width) + up * (fy * height)
            verts.append((p.x, p.y, p.z))
    row = segments_x + 1
    for y in range(segments_y):
        for x in range(segments_x):
            a = x + y * row
            b = x + 1 + y * row
            c = x + 1 + (y + 1) * row
            d = x + (y + 1) * row
            faces.append((a, d, c, b) if flip else (a, b, c, d))
    mesh = bpy.data.meshes.new(f'{name}_Mesh')
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def _restore_disabled_cloth_modifiers(obj):
    names = obj.get('pxbridge_disabled_cloth_modifiers', '')
    if not names:
        return
    for name in [n for n in names.split(';') if n]:
        mod = obj.modifiers.get(name)
        if mod:
            mod.show_viewport = True
    del obj['pxbridge_disabled_cloth_modifiers']


def _require_active_armature(context):
    obj = context.active_object
    if not obj or obj.type != 'ARMATURE':
        return None
    return obj


def _generate_default_avatar_anchors(armature):
    armature.cp77_avatar_anchors.clear()
    candidates = [('Collar', 'COLLAR', 'Neck1'), ('Head', 'COLLAR', 'Head'), ('Left Shoulder', 'SHOULDER', 'LeftArm'), ('Right Shoulder', 'SHOULDER', 'RightArm'), ('Chest', 'CHEST', 'Spine3'), ('Waist', 'WAIST', 'Hips'), ('Left Wrist', 'WRIST', 'LeftHand'), ('Right Wrist', 'WRIST', 'RightHand'), ('Left Ankle', 'ANKLE', 'LeftFoot'), ('Right Ankle', 'ANKLE', 'RightFoot')]
    inv = armature.matrix_world.inverted_safe()
    for name, anchor_type, bone in candidates:
        pos = _bone_world_pos(armature, bone)
        if pos is None:
            continue
        item = armature.cp77_avatar_anchors.add()
        item.name = name
        item.anchor_type = anchor_type
        item.bone = bone
        item.local_pos = inv @ pos
    armature.cp77_avatar.last_anchor_count = len(armature.cp77_avatar_anchors)
