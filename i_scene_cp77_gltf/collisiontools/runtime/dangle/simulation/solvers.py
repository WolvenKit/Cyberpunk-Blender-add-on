from mathutils import Matrix, Vector

from .....bartmoss.hierarchy import parent_depth
from .....blender.pose import (
    apply_model_space_matrices,
    apply_model_space_matrix,
    blend_matrix_trs,
    pose_bone_subtree_names,
)
from . import spaces


def update_simulation(sim, raw_dt, time_dilation=1.0):
    from time import perf_counter

    started = perf_counter()
    try:
        sim.step_simulation(
            raw_dt,
            time_dilation,
            operation_callback=_apply_graph_operation,
        )
    except Exception:
        sim.restore_upstream_pose(discard_partial_output=True)
        raise
    sim.capture_output_pose()
    runtime = getattr(sim, "animgraph_runtime", None)
    if (
        runtime is not None
        and runtime.structured
        and hasattr(runtime, "record_step_total")
    ):
        runtime.record_step_total(perf_counter() - started)


def _apply_graph_operation(sim, operation_type, operation_index):
    if operation_type == "DANGLE":
        _apply_dangle_node(sim, operation_index)
    elif operation_type == "DRAG":
        _apply_drag_runtime(sim, operation_index)


def _finish_graph_pose_write(sim):
    runtime = getattr(sim, "animgraph_runtime", None)
    if runtime is not None and runtime.structured:
        runtime.mark_blender_pose_dirty()
        return
    sim.arm_obj.update_tag(refresh={"OBJECT"})
    callback = getattr(sim, "_view_layer_update", None)
    if callable(callback):
        callback()


def _compile_lookat_map(sim, node_index):
    lookat_map = {}
    seen = set()

    system = sim.system
    selection = system.node_link_sel[node_index]
    if selection is not None and system.link_idx_a is not None:
        for raw_index in selection:
            link_index = int(raw_index)
            source_index = int(system.link_idx_a[link_index])
            target_index = int(system.link_idx_b[link_index])
            key = (source_index, target_index)
            axis = Vector(system.link_look_axes[link_index])
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
        system.position_projection_nodes,
        system.spring_nodes,
        system.pendulum_nodes,
    ):
        runtime = runtime_map.get(node_index)
        if runtime is None:
            continue
        source_index = int(runtime["parent_index"])
        target_index = int(runtime["particle_index"])
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


def compile_output_topology(sim):
    sim._node_output_topology = []
    arm = sim.arm_obj
    bone_indices = {bone.name: index for index, bone in enumerate(arm.data.bones)}

    for node_index, (start, end) in enumerate(sim.system.node_ranges):
        selected = {}
        for particle_index in range(start, end):
            selected[sim.particles[particle_index].bone_name] = particle_index
        particle_order = tuple(
            sorted(
                selected.values(),
                key=lambda index: bone_indices.get(sim.bone_names[index], -1),
            )
        )
        lookat_map = _compile_lookat_map(sim, node_index)

        relevant_names = set()
        subtree_by_name = {}
        for particle_index in particle_order:
            names = [sim.bone_names[particle_index]]
            names.extend(
                sim.bone_names[source_index]
                for source_index, _axis, _obligatory in lookat_map.get(
                    particle_index, ()
                )
                if 0 <= source_index < len(sim.bone_names)
            )
            for name in names:
                pose_bone = arm.pose.bones.get(name)
                if pose_bone is None:
                    continue
                if name not in subtree_by_name:
                    subtree_by_name[name] = pose_bone_subtree_names(pose_bone)
                subtree = subtree_by_name[name]
                relevant_names.update(subtree)

        pose_bones = {}
        for name in relevant_names:
            pose_bone = arm.pose.bones.get(name)
            if pose_bone is not None:
                pose_bones[name] = pose_bone
                if name not in subtree_by_name:
                    subtree_by_name[name] = pose_bone_subtree_names(pose_bone)

        correction_groups = {}
        for particle_index in particle_order:
            target_name = sim.bone_names[particle_index]
            target_bone = pose_bones.get(target_name)
            if target_bone is not None:
                correction_groups[("CHILDREN", target_name)] = tuple(
                    name for name in subtree_by_name[target_name] if name != target_name
                )
            for source_index, _axis, _obligatory in lookat_map.get(particle_index, ()):
                source_name = sim.bone_names[source_index]
                source_bone = pose_bones.get(source_name)
                if source_bone is None:
                    continue
                dangle_children = []
                other_children = []
                for child in source_bone.children:
                    if child.name not in subtree_by_name:
                        subtree_by_name[child.name] = pose_bone_subtree_names(child)
                    subtree = subtree_by_name[child.name]
                    if child.name == target_name:
                        dangle_children.extend(subtree)
                    else:
                        other_children.extend(subtree)
                correction_groups[("DANGLE", source_name, target_name)] = tuple(
                    dangle_children
                )
                correction_groups[("OTHER", source_name, target_name)] = tuple(
                    other_children
                )

        depth_cache = {}
        apply_order = tuple(
            sorted(
                pose_bones,
                key=lambda name: (
                    parent_depth(pose_bones[name], depth_cache),
                    bone_indices.get(name, -1),
                ),
            )
        )
        sim._node_output_topology.append(
            {
                "particle_order": particle_order,
                "lookat_map": lookat_map,
                "pose_bones": pose_bones,
                "subtrees": subtree_by_name,
                "correction_groups": correction_groups,
                "apply_order": apply_order,
            }
        )


def _correct_children_matrices(
    matrices,
    child_names,
    correction,
    alpha,
    apply_names,
):
    for child_name in child_names:
        current = matrices.get(child_name)
        if current is None:
            continue
        target = correction @ current
        matrices[child_name] = blend_matrix_trs(current, target, alpha)
        apply_names.add(child_name)


def _compose_dangle_node_matrices(sim, node_index, base_matrices=None):
    dnode = sim.state.dangle_nodes[node_index]
    topology = sim._node_output_topology[node_index]
    lookat_map = topology["lookat_map"]
    pose_bones = topology["pose_bones"]
    subtrees = topology["subtrees"]
    correction_groups = topology["correction_groups"]
    matrices = {}
    for name, pose_bone in pose_bones.items():
        matrix = base_matrices.get(name) if base_matrices is not None else None
        matrices[name] = (
            matrix.copy() if matrix is not None else pose_bone.matrix.copy()
        )
    apply_names = set()
    alpha = max(0.0, min(1.0, float(getattr(dnode, "alpha", 1.0))))

    for particle_index in topology["particle_order"]:
        if not sim.system.active_mask[particle_index]:
            continue

        target_name = sim.bone_names[particle_index]
        target_bone = pose_bones.get(target_name)
        if target_bone is None or target_name not in matrices:
            continue
        target_position = Vector(sim.system.pos_ms[particle_index])

        for source_index, look_axis, obligatory in lookat_map.get(particle_index, ()):
            if not 0 <= source_index < len(sim.bone_names):
                continue
            source_name = sim.bone_names[source_index]
            parent_matrix = matrices.get(source_name)
            reference_target = matrices.get(target_name)
            if parent_matrix is None or reference_target is None:
                continue

            result_parent = parent_matrix.copy()
            if getattr(dnode, "rotate_parent_to_look_at", True):
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
                        or abs(current_look.dot(reference_direction) - 1.0) < 0.001
                    ):
                        simulated_direction = (
                            target_position - parent_matrix.translation
                        )
                        if simulated_direction.length_squared > 1e-8:
                            simulated_direction.normalize()
                            result_rotation = (
                                current_look.rotation_difference(simulated_direction)
                                @ parent_rotation
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
            if getattr(dnode, "parent_rotation_alters_dangle_children", False):
                _correct_children_matrices(
                    matrices,
                    correction_groups.get(("DANGLE", source_name, target_name), ()),
                    correction,
                    alpha,
                    apply_names,
                )
            if getattr(dnode, "parent_rotation_alters_non_dangle_children", False):
                _correct_children_matrices(
                    matrices,
                    correction_groups.get(("OTHER", source_name, target_name), ()),
                    correction,
                    alpha,
                    apply_names,
                )

        current_dangle = matrices[target_name]
        result_dangle = current_dangle.copy()
        result_dangle.translation = target_position
        matrices[target_name] = blend_matrix_trs(current_dangle, result_dangle, alpha)
        apply_names.update(subtrees.get(target_name, (target_name,)))

        if getattr(dnode, "dangle_alters_children", False):
            correction = result_dangle @ current_dangle.inverted_safe()
            _correct_children_matrices(
                matrices,
                correction_groups.get(("CHILDREN", target_name), ()),
                correction,
                alpha,
                apply_names,
            )

    return matrices, apply_names


def _apply_model_space_matrices(matrices, apply_names, topology):
    apply_model_space_matrices(
        [
            topology["pose_bones"][name]
            for name in topology["apply_order"]
            if name in apply_names and name in matrices
        ],
        matrices,
    )


def _apply_dangle_node(sim, node_index):
    arm = sim.arm_obj
    if arm.mode != "POSE":
        return
    cached = getattr(sim, "_node_bones_cached", ())
    if not 0 <= int(node_index) < len(cached) or not cached[int(node_index)]:
        return

    matrices, apply_names = _compose_dangle_node_matrices(sim, node_index)
    if not apply_names:
        return

    sim.prepare_output_bones(apply_names)
    _apply_model_space_matrices(
        matrices, apply_names, sim._node_output_topology[node_index]
    )
    sim.mark_output_bones(apply_names)
    _finish_graph_pose_write(sim)


def _apply_drag_runtime(sim, runtime_index):
    drag_post = sim.drag_post
    if not 0 <= runtime_index < drag_post.num_drags:
        return
    target_index = int(drag_post.drag_indices[runtime_index])
    if not sim.system.active_mask[target_index]:
        return
    pose_bone = sim.arm_obj.pose.bones.get(sim.bone_names[target_index])
    if pose_bone is None:
        return
    result = spaces.red_model_transform_to_blender_bone(
        Matrix.Translation(Vector(drag_post.source_pos[runtime_index])), sim.arm_obj
    )
    sim.prepare_output_bones((pose_bone.name,))
    parent = pose_bone.parent
    apply_model_space_matrix(
        pose_bone, result, parent.matrix.copy() if parent is not None else None
    )
    sim.mark_output_bones((pose_bone.name,))
    _finish_graph_pose_write(sim)
