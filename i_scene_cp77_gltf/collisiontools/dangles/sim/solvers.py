import bpy
from mathutils import Matrix, Vector

from ....animation.blender_pose import blend_matrix_trs, model_matrix_to_basis
from . import spaces


def update_simulation(sim, raw_dt, time_dilation=1.0):
    sim.step_simulation(
        raw_dt,
        time_dilation,
        operation_callback=_apply_graph_operation,
    )
    sim.capture_output_pose()


def _apply_graph_operation(sim, operation_type, operation_index):
    if operation_type == 'DANGLE':
        _apply_dangle_node(sim, operation_index)
    elif operation_type == 'DRAG':
        _apply_drag_runtime(sim, operation_index)


def _compile_lookat_map(sim, node_index):
    lookat_map = {}
    seen = set()

    selections = getattr(sim, '_node_link_sel', ())
    selection = selections[node_index] if node_index < len(selections) else None
    if selection is not None and getattr(sim, 'link_idx_a', None) is not None:
        for raw_index in selection:
            link_index = int(raw_index)
            source_index = int(sim.link_idx_a[link_index])
            target_index = int(sim.link_idx_b[link_index])
            key = (source_index, target_index)
            axis = Vector(sim.link_look_axes[link_index])
            if axis.length_squared < 1e-8:
                axis = Vector((0.0, 0.0, 1.0))
            record = (source_index, axis.normalized(), True)
            entries = lookat_map.setdefault(target_index, [])
            if key in seen:
                for entry_index, entry in enumerate(entries):
                    if entry[0] == source_index:
                        entries[entry_index] = record
                        break
            else:
                seen.add(key)
                entries.append(record)

    for runtime_map in (
        getattr(sim, '_position_projection_nodes', {}),
        getattr(sim, '_spring_nodes', {}),
        getattr(sim, '_pendulum_nodes', {}),
    ):
        runtime = runtime_map.get(node_index)
        if runtime is None:
            continue
        source_index = int(runtime['parent_index'])
        target_index = int(runtime['particle_index'])
        if source_index < 0:
            continue
        axis = spaces.re_axis_to_blender_bone(
            sim.state.dangle_nodes[node_index].look_at_axis,
            sim.arm_obj,
        )
        if axis.length_squared < 1e-8:
            axis = Vector((0.0, 0.0, 1.0))
        record = (source_index, axis.normalized(), False)
        entries = lookat_map.setdefault(target_index, [])
        replaced = False
        for entry_index, entry in enumerate(entries):
            if entry[0] == source_index:
                entries[entry_index] = record
                replaced = True
                break
        if not replaced:
            entries.append(record)

    return lookat_map


def _subtree_names(pose_bone):
    names = []
    stack = [pose_bone]
    while stack:
        current = stack.pop()
        names.append(current.name)
        stack.extend(reversed(current.children))
    return tuple(names)


def compile_output_topology(sim):
    sim._node_particle_order = []
    sim._node_lookat_maps = []
    sim._node_output_topology = []
    arm = sim.arm_obj

    for node_index in range(len(sim._node_ranges)):
        start, end = sim._node_ranges[node_index]
        selected = {}
        for particle_index in range(start, end):
            selected[sim.particles[particle_index].bone_name] = particle_index
        particle_order = tuple(sorted(
            selected.values(),
            key=lambda index: arm.data.bones.find(sim.bone_names[index]),
        ))
        sim._node_particle_order.append(particle_order)
        lookat_map = _compile_lookat_map(sim, node_index)
        sim._node_lookat_maps.append(lookat_map)

        relevant_names = set()
        subtree_by_name = {}
        for particle_index in particle_order:
            names = [sim.bone_names[particle_index]]
            names.extend(
                sim.bone_names[source_index]
                for source_index, _axis, _obligatory
                in lookat_map.get(particle_index, ())
                if 0 <= source_index < len(sim.bone_names)
            )
            for name in names:
                pose_bone = arm.pose.bones.get(name)
                if pose_bone is None:
                    continue
                subtree = subtree_by_name.setdefault(
                    name, _subtree_names(pose_bone)
                )
                relevant_names.update(subtree)

        pose_bones = {}
        for name in relevant_names:
            pose_bone = arm.pose.bones.get(name)
            if pose_bone is not None:
                pose_bones[name] = pose_bone
                subtree_by_name.setdefault(name, _subtree_names(pose_bone))

        correction_groups = {}
        for particle_index in particle_order:
            target_name = sim.bone_names[particle_index]
            target_bone = pose_bones.get(target_name)
            if target_bone is not None:
                correction_groups[('CHILDREN', target_name)] = tuple(
                    name for name in subtree_by_name[target_name]
                    if name != target_name
                )
            for source_index, _axis, _obligatory in lookat_map.get(
                particle_index, ()
            ):
                source_name = sim.bone_names[source_index]
                source_bone = pose_bones.get(source_name)
                if source_bone is None:
                    continue
                dangle_children = []
                other_children = []
                for child in source_bone.children:
                    subtree = subtree_by_name.setdefault(
                        child.name, _subtree_names(child)
                    )
                    if child.name == target_name:
                        dangle_children.extend(subtree)
                    else:
                        other_children.extend(subtree)
                correction_groups[
                    ('DANGLE', source_name, target_name)
                ] = tuple(dangle_children)
                correction_groups[
                    ('OTHER', source_name, target_name)
                ] = tuple(other_children)

        apply_order = tuple(sorted(
            pose_bones,
            key=lambda name: (
                _bone_depth(pose_bones[name]),
                arm.data.bones.find(name),
            ),
        ))
        sim._node_output_topology.append({
            'particle_order': particle_order,
            'lookat_map': lookat_map,
            'pose_bones': pose_bones,
            'subtrees': subtree_by_name,
            'correction_groups': correction_groups,
            'apply_order': apply_order,
        })


def _correct_children_matrices(
    matrices, child_names, correction, alpha, apply_names,
):
    for child_name in child_names:
        current = matrices.get(child_name)
        if current is None:
            continue
        target = correction @ current
        matrices[child_name] = blend_matrix_trs(
            current, target, alpha
        )
        apply_names.add(child_name)


def _compose_dangle_node_matrices(sim, node_index):
    dnode = sim.state.dangle_nodes[node_index]
    topology = sim._node_output_topology[node_index]
    lookat_map = topology['lookat_map']
    pose_bones = topology['pose_bones']
    subtrees = topology['subtrees']
    correction_groups = topology['correction_groups']
    matrices = {
        name: pose_bone.matrix.copy()
        for name, pose_bone in pose_bones.items()
    }
    apply_names = set()
    alpha = max(0.0, min(1.0, float(getattr(dnode, 'alpha', 1.0))))

    for particle_index in topology['particle_order']:
        if not sim.active_mask[particle_index]:
            continue

        target_name = sim.bone_names[particle_index]
        target_bone = pose_bones.get(target_name)
        if target_bone is None or target_name not in matrices:
            continue
        target_position = Vector(sim.pos_ms[particle_index])

        for source_index, look_axis, obligatory in lookat_map.get(
            particle_index, ()
        ):
            if not 0 <= source_index < len(sim.bone_names):
                continue
            source_name = sim.bone_names[source_index]
            parent_matrix = matrices.get(source_name)
            reference_target = matrices.get(target_name)
            if parent_matrix is None or reference_target is None:
                continue

            result_parent = parent_matrix.copy()
            if getattr(dnode, 'rotate_parent_to_look_at', True):
                parent_rotation = parent_matrix.to_quaternion()
                reference_direction = (
                    reference_target.translation - parent_matrix.translation
                )
                if reference_direction.length_squared > 1e-8:
                    reference_direction.normalize()
                    current_look = parent_rotation @ look_axis
                    if current_look.length_squared > 1e-8:
                        current_look.normalize()
                    if (
                        obligatory
                        or abs(current_look.dot(reference_direction) - 1.0)
                        < 0.001
                    ):
                        simulated_direction = (
                            target_position - parent_matrix.translation
                        )
                        if simulated_direction.length_squared > 1e-8:
                            simulated_direction.normalize()
                            result_rotation = (
                                current_look.rotation_difference(
                                    simulated_direction
                                ) @ parent_rotation
                            )
                            result_parent = Matrix.LocRotScale(
                                parent_matrix.translation,
                                result_rotation,
                                parent_matrix.to_scale(),
                            )

            matrices[source_name] = blend_matrix_trs(
                parent_matrix, result_parent, alpha
            )
            apply_names.update(subtrees.get(source_name, (source_name,)))
            correction = result_parent @ parent_matrix.inverted_safe()
            if getattr(
                dnode, 'parent_rotation_alters_dangle_children', False
            ):
                _correct_children_matrices(
                    matrices,
                    correction_groups.get(
                        ('DANGLE', source_name, target_name), ()
                    ),
                    correction,
                    alpha,
                    apply_names,
                )
            if getattr(
                dnode, 'parent_rotation_alters_non_dangle_children', False
            ):
                _correct_children_matrices(
                    matrices,
                    correction_groups.get(
                        ('OTHER', source_name, target_name), ()
                    ),
                    correction,
                    alpha,
                    apply_names,
                )

        current_dangle = matrices[target_name]
        result_dangle = current_dangle.copy()
        result_dangle.translation = target_position
        matrices[target_name] = blend_matrix_trs(
            current_dangle, result_dangle, alpha
        )
        apply_names.update(subtrees.get(target_name, (target_name,)))

        if getattr(dnode, 'dangle_alters_children', False):
            correction = result_dangle @ current_dangle.inverted_safe()
            _correct_children_matrices(
                matrices,
                correction_groups.get(('CHILDREN', target_name), ()),
                correction,
                alpha,
                apply_names,
            )

    return matrices, apply_names


def _bone_depth(pose_bone):
    depth = 0
    parent = pose_bone.parent
    while parent is not None:
        depth += 1
        parent = parent.parent
    return depth


def _apply_model_space_matrices(
    matrices, apply_names, topology
):
    pose_bones = [
        topology['pose_bones'][name]
        for name in topology['apply_order']
        if name in apply_names and name in matrices
    ]
    basis_by_name = {}
    for pose_bone in pose_bones:
        parent = pose_bone.parent
        parent_matrix = (
            matrices[parent.name]
            if parent is not None and parent.name in matrices
            else (
                parent.matrix.copy()
                if parent is not None else Matrix.Identity(4)
            )
        )
        basis_by_name[pose_bone.name] = model_matrix_to_basis(
            pose_bone,
            matrices[pose_bone.name],
            parent_matrix,
        )

    for pose_bone in pose_bones:
        basis = basis_by_name[pose_bone.name]
        if basis is None:
            pose_bone.matrix = matrices[pose_bone.name]
        else:
            pose_bone.matrix_basis = basis


def _apply_dangle_node(sim, node_index):
    arm = sim.arm_obj
    if arm.mode != 'POSE':
        return

    matrices, apply_names = _compose_dangle_node_matrices(sim, node_index)
    if not apply_names:
        return

    _apply_model_space_matrices(
        matrices, apply_names, sim._node_output_topology[node_index]
    )
    arm.update_tag(refresh={'OBJECT'})
    bpy.context.view_layer.update()


def _apply_drag_runtime(sim, runtime_index):
    drag_post = sim.drag_post
    if not 0 <= runtime_index < drag_post.num_drags:
        return
    target_index = int(drag_post.drag_indices[runtime_index])
    if not sim.active_mask[target_index]:
        return
    pose_bone = sim.arm_obj.pose.bones.get(sim.bone_names[target_index])
    if pose_bone is None:
        return
    result = pose_bone.matrix.copy()
    result.translation = Vector(drag_post.source_pos[runtime_index])
    pose_bone.matrix = result
    sim.arm_obj.update_tag(refresh={'OBJECT'})
    bpy.context.view_layer.update()


def _apply_transforms_to_armature(sim):
    for operation_type, operation_index in sim.execution_plan:
        _apply_graph_operation(sim, operation_type, operation_index)
