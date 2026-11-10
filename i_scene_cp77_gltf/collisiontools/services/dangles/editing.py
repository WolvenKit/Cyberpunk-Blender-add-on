from functools import wraps

from ....animation.model.animgraph.handles import normalized_source_handle
from ....blender.operator_results import OperationResult
from ....core.log import debug_exception, get_logger
from ...blender.dangle_context import (
    get_active_chain,
    get_active_dangle_node,
    get_active_rig,
)

_LOG = get_logger(__name__)


def _sync_rig_if_linked(rig, context, result, *, removed_handles=()):
    if not result.ok or rig is None:
        return result
    state = rig.dangle_state
    if not str(getattr(state, "animgraph_source_text", "") or ""):
        return result
    if not str(getattr(state, "animgraph_tree_name", "") or ""):
        return result
    try:
        from ...blender.dangle_source import load_source_payload
        from .sync import sync_editor_to_graph

        sync_editor_to_graph(
            rig,
            context,
            removed_handles=tuple(removed_handles),
        )
    except Exception as exc:
        try:
            from ...runtime.dangle.editor_state import import_chains_data

            import_chains_data(load_source_payload(rig), state)
        except Exception:
            debug_exception(
                _LOG, "Could not reload the Dangle chains from the linked AnimGraph"
            )
        return OperationResult.cancelled(
            f"Dangle edit could not synchronize with Graph View: {exc}", error=exc
        )
    return result


def _sync_if_linked(context, result, *, removed_handles=()):
    return _sync_rig_if_linked(
        get_active_rig(context),
        context,
        result,
        removed_handles=removed_handles,
    )


def _waits_for_preview(edit):
    """Wait until the rig's preview stops before adding or removing items"""

    @wraps(edit)
    def guarded(context, *args, **kwargs):
        rig = get_active_rig(context)
        if rig is not None and rig.dangle_state.is_playing:
            return OperationResult.cancelled(
                "Stop Dangle preview before adding or removing items."
            )
        return edit(context, *args, **kwargs)

    return guarded


@_waits_for_preview
def remove_dangle_node(context):
    rig = get_active_rig(context)
    if rig is None or not rig.dangle_state.dangle_nodes:
        return OperationResult.cancelled()
    state = rig.dangle_state
    removed_index = state.active_dangle_node
    removed_handles = []
    source_handle = str(
        getattr(state.dangle_nodes[removed_index], "source_handle", "") or ""
    )
    if not source_handle:
        for operation in state.evaluation_order:
            if (
                operation.node_type == "DANGLE"
                and operation.node_index == removed_index
            ):
                source_handle = str(operation.source_handle or "")
                break
    source_handle = normalized_source_handle(source_handle)
    if source_handle and source_handle not in {"editor", "fallback", "editor-fallback"}:
        removed_handles.append(source_handle)
    state.dangle_nodes.remove(removed_index)
    for operation_index in reversed(range(len(state.evaluation_order))):
        operation = state.evaluation_order[operation_index]
        if operation.node_type != "DANGLE":
            continue
        if operation.node_index == removed_index:
            state.evaluation_order.remove(operation_index)
        elif operation.node_index > removed_index:
            operation.node_index -= 1
    state.active_dangle_node = max(0, state.active_dangle_node - 1)
    return _sync_if_linked(
        context, OperationResult.finished(), removed_handles=removed_handles
    )


@_waits_for_preview
def add_chain(context):
    node = get_active_dangle_node(context)
    if node is None:
        return OperationResult.cancelled()
    chain = node.chains.add()
    chain.name = f"Chain_{len(node.chains)}"
    node.active_chain = len(node.chains) - 1
    return _sync_if_linked(context, OperationResult.finished())


@_waits_for_preview
def remove_chain(context):
    node = get_active_dangle_node(context)
    if node is None or not node.chains:
        return OperationResult.cancelled()
    node.chains.remove(node.active_chain)
    node.active_chain = max(0, node.active_chain - 1)
    return _sync_if_linked(context, OperationResult.finished())


def _single_particle_solver_message(chain):
    names = {"PBD": "Position Projection", "SPRING": "Spring", "PENDULUM": "Pendulum"}
    return names.get(chain.solver)


@_waits_for_preview
def add_particle(context):
    chain = get_active_chain(context)
    if chain is None:
        return OperationResult.cancelled()
    solver_name = _single_particle_solver_message(chain)
    if solver_name and chain.particles:
        return OperationResult.cancelled(
            f"{solver_name} supports one bone only.", "WARNING"
        )
    chain.particles.add()
    chain.active_particle_index = len(chain.particles) - 1
    return _sync_if_linked(context, OperationResult.finished())


@_waits_for_preview
def remove_particle(context):
    chain = get_active_chain(context)
    if chain is None or not chain.particles:
        return OperationResult.cancelled()
    chain.particles.remove(chain.active_particle_index)
    chain.active_particle_index = max(0, chain.active_particle_index - 1)
    return _sync_if_linked(context, OperationResult.finished())


def _copy_shape(source, target):
    for attribute in (
        "name",
        "bone_name",
        "shape_type",
        "radius",
        "x_box_extent",
        "y_box_extent",
        "height_extent",
        "offset_ls",
        "rotation_ls_quat",
    ):
        setattr(target, attribute, getattr(source, attribute))


@_waits_for_preview
def add_shape(context):
    rig = get_active_rig(context)
    node = get_active_dangle_node(context)
    if rig is None or node is None:
        return OperationResult.cancelled()
    if not node.collision_shapes and rig.dangle_state.collision_shapes:
        for legacy_shape in rig.dangle_state.collision_shapes:
            _copy_shape(legacy_shape, node.collision_shapes.add())
    node.collision_shapes.add()
    node.active_shape_index = len(node.collision_shapes) - 1
    return _sync_if_linked(context, OperationResult.finished())


@_waits_for_preview
def remove_shape(context):
    node = get_active_dangle_node(context)
    if node is None or not node.collision_shapes:
        return OperationResult.cancelled()
    node.collision_shapes.remove(node.active_shape_index)
    node.active_shape_index = min(
        node.active_shape_index, max(0, len(node.collision_shapes) - 1)
    )
    return _sync_if_linked(context, OperationResult.finished())


def _active_particle(context):
    chain = get_active_chain(context)
    if chain is None or not chain.particles:
        return None
    index = chain.active_particle_index
    return chain.particles[index] if 0 <= index < len(chain.particles) else None


@_waits_for_preview
def mutate_particle_constraint(context, collection_name, action, index=-1):
    particle = _active_particle(context)
    if particle is None:
        return OperationResult.cancelled()
    collection = getattr(particle, collection_name)
    if action == "ADD":
        collection.add()
    else:
        if index < 0 or index >= len(collection):
            return OperationResult.cancelled()
        collection.remove(index)
    return _sync_if_linked(context, OperationResult.finished())


def _copy_collection(source_collection, target_collection, attributes):
    for source in source_collection:
        target = target_collection.add()
        for attribute in attributes:
            setattr(target, attribute, getattr(source, attribute))


@_waits_for_preview
def copy_chain(context):
    node = get_active_dangle_node(context)
    if node is None or not node.chains:
        return OperationResult.cancelled()
    source_chain = node.chains[node.active_chain]
    new_chain = node.chains.add()
    new_chain.name = source_chain.name + "_copy"
    new_chain.solver = source_chain.solver

    particle_attributes = (
        "bone_name",
        "mass",
        "damping",
        "pull_force",
        "is_pinned",
        "capsule_radius",
        "capsule_height",
        "capsule_axis_ls",
        "dyng_projection_type",
        "pos_projection_type",
        "direction_reference_bone",
        "spring_simulation_fps",
        "spring_constraint_radius",
        "spring_constraint_scale1",
        "spring_constraint_scale2",
        "spring_constraint_orientation",
        "spring_pull_force_origin_ls",
        "spring_projection_type",
        "spring_collision_radius",
        "pendulum_simulation_fps",
        "pendulum_constraint_type",
        "pendulum_half_aperture_angle",
        "pendulum_constraint_orientation",
        "pendulum_pull_force_direction_ls",
        "pendulum_projection_type",
        "pendulum_collision_radius",
        "pendulum_collision_height",
    )
    link_attributes = (
        "target_bone",
        "link_type",
        "lower_ratio",
        "upper_ratio",
        "explicit_rest_distance",
        "stiffness",
        "look_at_axis",
    )
    ellipsoid_attributes = (
        "target_bone",
        "radius",
        "scale1",
        "scale2",
        "ellipsoid_transform_ls_quat",
        "ellipsoid_transform_ls_offset",
    )
    pendulum_attributes = (
        "target_bone",
        "constraint_type",
        "half_aperture_angle",
        "projection_type",
        "cone_collision_radius",
        "cone_collision_height",
        "cone_transform_ls_quat",
        "cone_transform_ls_offset",
    )

    for source_particle in source_chain.particles:
        new_particle = new_chain.particles.add()
        for attribute in particle_attributes:
            setattr(new_particle, attribute, getattr(source_particle, attribute))
        _copy_collection(
            source_particle.link_constraints,
            new_particle.link_constraints,
            link_attributes,
        )
        _copy_collection(
            source_particle.ellipsoid_constraints,
            new_particle.ellipsoid_constraints,
            ellipsoid_attributes,
        )
        _copy_collection(
            source_particle.pendulum_constraints,
            new_particle.pendulum_constraints,
            pendulum_attributes,
        )

    node.active_chain = len(node.chains) - 1
    return _sync_if_linked(context, OperationResult.finished())


@_waits_for_preview
def add_selected_bones_to_chain(context):
    chain = get_active_chain(context)
    if chain is None:
        return OperationResult.cancelled()
    obj = context.active_object
    if obj is None or obj.type != "ARMATURE" or obj.mode != "POSE":
        return OperationResult.cancelled(
            "Must be in Pose Mode with bones selected.", "WARNING"
        )
    selected_bones = list(context.selected_pose_bones)
    solver_name = _single_particle_solver_message(chain)
    if solver_name:
        if chain.particles:
            return OperationResult.cancelled(
                f"{solver_name} supports one bone only.", "WARNING"
            )
        if len(selected_bones) != 1:
            return OperationResult.cancelled(
                f"Select exactly one bone for {solver_name}.", "WARNING"
            )
    for pose_bone in selected_bones:
        particle = chain.particles.add()
        particle.bone_name = pose_bone.name
    if selected_bones:
        chain.active_particle_index = len(chain.particles) - 1
    return _sync_if_linked(
        context,
        OperationResult.finished(
            f"Added {len(selected_bones)} bones to chain." if selected_bones else ""
        ),
    )
