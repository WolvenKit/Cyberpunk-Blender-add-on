import bpy

from ..model import MeshToolResult
from .cloth_common import (
    _active_seam_pair,
    _assign_group_weights,
    _copy_cloth_defaults,
    _csv_from_indices,
    _ensure_motion_group,
    _ensure_named_group,
    _ensure_pin_group,
    _indices_from_csv,
    _require_active_mesh,
    _safe_group_name,
    _selected_edge_vertex_order,
    _set_vertex_selection,
)


def execute_select_open_boundary_edges(context, report):
    obj = _require_active_mesh(context)
    if not obj:
        return MeshToolResult.failure()
    previous_mode = obj.mode
    if previous_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    edge_use_count = {edge.index: 0 for edge in obj.data.edges}
    edge_lookup = {tuple(sorted(edge.vertices)): edge.index for edge in obj.data.edges}
    for poly in obj.data.polygons:
        verts = list(poly.vertices)
        for i, a in enumerate(verts):
            b = verts[(i + 1) % len(verts)]
            idx = edge_lookup.get(tuple(sorted((a, b))))
            if idx is not None:
                edge_use_count[idx] += 1
    for vert in obj.data.vertices:
        vert.select = False
    count = 0
    for edge in obj.data.edges:
        select = edge_use_count.get(edge.index, 0) <= 1
        edge.select = select
        if select:
            count += 1
            obj.data.vertices[edge.vertices[0]].select = True
            obj.data.vertices[edge.vertices[1]].select = True
    obj.data.update()
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='EDGE')
    report({'INFO'}, f'Selected {count} boundary edges')
    return MeshToolResult.success()


def execute_remove_seam_pair(context, report):
    obj = _require_active_mesh(context)
    if not obj or not hasattr(obj, 'cp77_garment_seams') or (not obj.cp77_garment_seams):
        return MeshToolResult.failure()
    idx = max(0, min(obj.cp77_garment_seam_index, len(obj.cp77_garment_seams) - 1))
    name = obj.cp77_garment_seams[idx].name
    obj.cp77_garment_seams.remove(idx)
    obj.cp77_garment_seam_index = max(0, idx - 1)
    obj.cp77_cloth.workflow_state = 'DRAFT'
    report({'INFO'}, f'Removed seam pair: {name}')
    return MeshToolResult.success()


def execute_create_seam_pair_from_selection(context, report, name):
    source = _require_active_mesh(context)
    if not source:
        return MeshToolResult.failure()
    targets = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj != source]
    target = targets[0] if targets else None
    source_indices = _selected_edge_vertex_order(source)
    target_indices = _selected_edge_vertex_order(target) if target else []
    if len(source_indices) < 2:
        report({'ERROR'}, 'Select at least one source seam edge chain')
        return MeshToolResult.failure()
    pair = source.cp77_garment_seams.add()
    pair.name = name or f'Seam {len(source.cp77_garment_seams)}'
    pair.target_object = target
    pair.source_vertices = _csv_from_indices(source_indices)
    pair.target_vertices = _csv_from_indices(target_indices)
    pair.source_count = len(source_indices)
    pair.target_count = len(target_indices)
    pair.status = 'Source captured' if not target_indices else 'Ready'
    source.cp77_garment_seam_index = len(source.cp77_garment_seams) - 1
    source.cp77_cloth.workflow_state = 'DRAFT'
    msg = f'Captured seam source: {len(source_indices)} verts'
    if target:
        msg += f', target: {len(target_indices)} verts from {target.name}'
    report({'INFO'}, msg)
    return MeshToolResult.success()


def execute_capture_seam_side(context, report, side):
    owner = _require_active_mesh(context)
    if not owner:
        return MeshToolResult.failure()
    pair = _active_seam_pair(owner)
    if not pair:
        pair = owner.cp77_garment_seams.add()
        pair.name = 'Seam Pair'
        owner.cp77_garment_seam_index = len(owner.cp77_garment_seams) - 1
    capture_obj = owner
    if side == 'TARGET':
        targets = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj != owner]
        capture_obj = pair.target_object or (targets[0] if targets else owner)
        pair.target_object = capture_obj if capture_obj != owner else None
    indices = _selected_edge_vertex_order(capture_obj)
    if len(indices) < 2:
        report({'ERROR'}, 'Select at least one seam edge chain')
        return MeshToolResult.failure()
    if side == 'SOURCE':
        pair.source_vertices = _csv_from_indices(indices)
        pair.source_count = len(indices)
    else:
        pair.target_vertices = _csv_from_indices(indices)
        pair.target_count = len(indices)
    pair.status = 'Ready' if pair.source_count and pair.target_count else 'Incomplete'
    owner.cp77_cloth.workflow_state = 'DRAFT'
    report({'INFO'}, f'Captured {side.lower()} seam: {len(indices)} vertices')
    return MeshToolResult.success()


def execute_select_seam_side(context, report, side):
    owner = _require_active_mesh(context)
    if not owner:
        return MeshToolResult.failure()
    pair = _active_seam_pair(owner)
    if not pair:
        return MeshToolResult.failure()
    target_obj = owner if side == 'SOURCE' else pair.target_object or owner
    indices = _indices_from_csv(pair.source_vertices if side == 'SOURCE' else pair.target_vertices)
    if not indices:
        report({'ERROR'}, 'Seam side has not been captured')
        return MeshToolResult.failure()
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    target_obj.select_set(True)
    context.view_layer.objects.active = target_obj
    _set_vertex_selection(target_obj, indices)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='VERT')
    report({'INFO'}, f'Selected {len(indices)} seam vertices')
    return MeshToolResult.success()


def execute_build_seam_constraint_groups(context, report):
    owner = _require_active_mesh(context)
    if not owner:
        return MeshToolResult.failure()
    pair = _active_seam_pair(owner)
    if not pair:
        report({'ERROR'}, 'Create or select a seam pair first')
        return MeshToolResult.failure()
    source_indices = _indices_from_csv(pair.source_vertices)
    target_obj = pair.target_object or owner
    target_indices = _indices_from_csv(pair.target_vertices)
    if len(source_indices) < 2:
        report({'ERROR'}, 'Source seam is empty')
        return MeshToolResult.failure()
    source_group = _ensure_named_group(owner, _safe_group_name('SEAM_A', pair.name))
    _assign_group_weights(source_group, source_indices, pair.stitch_strength)
    if pair.use_motion_constraints:
        motion = _ensure_motion_group(owner)
        _assign_group_weights(motion, source_indices, pair.stitch_strength)
        owner.cp77_cloth.motion_constraint_source = 'MOTION_GROUP'
        owner.cp77_cloth.motion_constraint_radius = pair.motion_radius
        owner.cp77_cloth.motion_constraint_stiffness = max(owner.cp77_cloth.motion_constraint_stiffness, pair.stitch_strength)
    if pair.pin_endpoints and source_indices:
        pin = _ensure_pin_group(owner)
        _assign_group_weights(pin, [source_indices[0], source_indices[-1]], 1.0)
    if target_obj and target_indices:
        target_group = _ensure_named_group(target_obj, _safe_group_name('SEAM_B', pair.name))
        _assign_group_weights(target_group, target_indices, pair.stitch_strength)
        if hasattr(target_obj, 'cp77_cloth') and pair.use_motion_constraints:
            motion = _ensure_motion_group(target_obj)
            _assign_group_weights(motion, target_indices, pair.stitch_strength)
            target_obj.cp77_cloth.motion_constraint_source = 'MOTION_GROUP'
            target_obj.cp77_cloth.motion_constraint_radius = pair.motion_radius
        if pair.pin_endpoints:
            pin = _ensure_pin_group(target_obj)
            _assign_group_weights(pin, [target_indices[0], target_indices[-1]], 1.0)
    pair.status = 'Groups built'
    owner.cp77_cloth.workflow_state = 'DRAFT'
    if target_obj and hasattr(target_obj, 'cp77_cloth'):
        target_obj.cp77_cloth.workflow_state = 'DRAFT'
    report({'INFO'}, 'Seam vertex groups updated')
    return MeshToolResult.success()


def execute_create_stitched_panel_mesh(context, report, hide_sources, reverse_target):
    source = _require_active_mesh(context)
    if not source:
        return MeshToolResult.failure()
    pair = _active_seam_pair(source)
    if not pair:
        report({'ERROR'}, 'Create or select a seam pair first')
        return MeshToolResult.failure()
    target = pair.target_object
    if not target or target.type != 'MESH':
        report({'ERROR'}, 'Assign a target panel before creating a stitched mesh')
        return MeshToolResult.failure()
    source_chain = _indices_from_csv(pair.source_vertices)
    target_chain = _indices_from_csv(pair.target_vertices)
    if len(source_chain) < 2 or len(target_chain) < 2:
        report({'ERROR'}, 'Both seam sides need at least two captured vertices')
        return MeshToolResult.failure()
    if reverse_target:
        target_chain = list(reversed(target_chain))
    else:
        src0 = source.matrix_world @ source.data.vertices[source_chain[0]].co
        src1 = source.matrix_world @ source.data.vertices[source_chain[-1]].co
        tgt0 = target.matrix_world @ target.data.vertices[target_chain[0]].co
        tgt1 = target.matrix_world @ target.data.vertices[target_chain[-1]].co
        if (src0 - tgt1).length + (src1 - tgt0).length < (src0 - tgt0).length + (src1 - tgt1).length:
            target_chain = list(reversed(target_chain))
    source_inv = source.matrix_world.inverted_safe()
    verts = [tuple(v.co) for v in source.data.vertices]
    faces = [tuple(poly.vertices) for poly in source.data.polygons]
    target_offset = len(verts)
    target_local = []
    for v in target.data.vertices:
        co = source_inv @ (target.matrix_world @ v.co)
        target_local.append(co.copy())
        verts.append((co.x, co.y, co.z))
    faces.extend((tuple((target_offset + i for i in poly.vertices)) for poly in target.data.polygons))
    pair_count = min(len(source_chain), len(target_chain))
    for i in range(pair_count):
        a = Vector(verts[source_chain[i]])
        b_idx = target_offset + target_chain[i]
        b = Vector(verts[b_idx])
        direction = b - a
        distance = direction.length
        if distance > 1e-08:
            adjusted = a + direction.normalized() * pair.stitch_distance
            verts[b_idx] = (adjusted.x, adjusted.y, adjusted.z)
    bridge_faces = []
    for i in range(pair_count - 1):
        a0 = source_chain[i]
        a1 = source_chain[i + 1]
        b0 = target_offset + target_chain[i]
        b1 = target_offset + target_chain[i + 1]
        if len({a0, a1, b0, b1}) == 4:
            bridge_faces.append((a0, a1, b1, b0))
    faces.extend(bridge_faces)
    mesh = bpy.data.meshes.new(f'{source.name}_{target.name}_Stitched_Mesh')
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    stitched = bpy.data.objects.new(f'{source.name}_{target.name}_Stitched', mesh)
    context.collection.objects.link(stitched)
    stitched.matrix_world = source.matrix_world.copy()
    _copy_cloth_defaults(source, stitched)
    stitched.cp77_cloth.pin_vg = source.cp77_cloth.pin_vg
    stitched.cp77_cloth.motion_constraint_vg = source.cp77_cloth.motion_constraint_vg
    seam_a = _ensure_named_group(stitched, _safe_group_name('SEAM_A', pair.name))
    seam_b = _ensure_named_group(stitched, _safe_group_name('SEAM_B', pair.name))
    _assign_group_weights(seam_a, source_chain[:pair_count], pair.stitch_strength)
    _assign_group_weights(seam_b, [target_offset + i for i in target_chain[:pair_count]], pair.stitch_strength)
    if pair.use_motion_constraints:
        motion = _ensure_motion_group(stitched)
        _assign_group_weights(motion, source_chain[:pair_count], pair.stitch_strength)
        _assign_group_weights(motion, [target_offset + i for i in target_chain[:pair_count]], pair.stitch_strength)
        stitched.cp77_cloth.motion_constraint_source = 'MOTION_GROUP'
        stitched.cp77_cloth.motion_constraint_radius = pair.motion_radius
    if pair.pin_endpoints:
        pin = _ensure_pin_group(stitched)
        endpoints = [source_chain[0], source_chain[pair_count - 1], target_offset + target_chain[0], target_offset + target_chain[pair_count - 1]]
        _assign_group_weights(pin, endpoints, 1.0)
    new_pair = stitched.cp77_garment_seams.add()
    new_pair.name = pair.name
    new_pair.source_vertices = _csv_from_indices(source_chain[:pair_count])
    new_pair.target_vertices = _csv_from_indices([target_offset + i for i in target_chain[:pair_count]])
    new_pair.source_count = pair_count
    new_pair.target_count = pair_count
    new_pair.stitch_distance = pair.stitch_distance
    new_pair.stitch_strength = pair.stitch_strength
    new_pair.motion_radius = pair.motion_radius
    new_pair.pin_endpoints = pair.pin_endpoints
    new_pair.use_motion_constraints = pair.use_motion_constraints
    new_pair.status = f'Stitched with {len(bridge_faces)} bridge faces'
    if hide_sources:
        source.hide_viewport = True
        target.hide_viewport = True
    bpy.ops.object.select_all(action='DESELECT')
    stitched.select_set(True)
    context.view_layer.objects.active = stitched
    report({'INFO'}, f'Created {stitched.name}: {len(bridge_faces)} stitch faces')
    return MeshToolResult.success()
