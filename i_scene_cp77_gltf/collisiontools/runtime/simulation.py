from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d

from ...blender.operator_results import OperationResult
from ...blender.physics.bridge_session import require_initialized_bridge
from ...blender.physics.objects import set_bone_world_matrix
from ...blender.physics.vehicle_geometry import matrix_from_pose
from ...core.log import debug_exception, get_logger
from ...physics.model.collision_layers import COLLISION_PRESETS, get_layer_bit
from ...physics.runtime.bridge import require_bridge
from ...physics.runtime.cloth_provider import (
    apply_cloth_particles,
    prepare_cloth_step,
    refresh_cloth_substep,
    set_active_cloth_state,
)
from .vehicle_preview import (
    _flush_vehicle_live_updates_for_scene,
    apply_vehicle_inputs,
    clear_vehicle_inputs,
    sync_vehicle_preview,
    vehicle_step_schedule,
)

_LOG = get_logger(__name__)

_ACTIVE_SIM_SESSIONS = {}


def simulation_timestep(scene):
    fps = float(scene.render.fps)
    fps_base = float(scene.render.fps_base)
    if fps <= 0.0 or fps_base <= 0.0:
        return 1.0 / 60.0
    return min(1.0, fps_base / fps)


def register_simulation_session(key, stop_callback, *, owner="collisiontools"):
    if not callable(stop_callback):
        raise TypeError("Simulation stop callback must be callable")
    _ACTIVE_SIM_SESSIONS[key] = (str(owner or "collisiontools"), stop_callback)


def stop_active_simulations(*, owner=None):
    failures = []
    for key, (session_owner, stop_callback) in tuple(_ACTIVE_SIM_SESSIONS.items()):
        if owner is not None and session_owner != owner:
            continue
        try:
            stop_callback()
        except Exception as error:
            debug_exception(_LOG, "Could not stop an active PhysX simulation")
            failures.append(error)
        finally:
            _ACTIVE_SIM_SESSIONS.pop(key, None)
    if failures:
        raise RuntimeError("; ".join(str(error) for error in failures))


def step_bridge_batch(context, bridge, dt, steps=1, poses=None):
    """Steps the native scene"""
    count = max(1, int(steps))
    prepare_cloth_step(context, bridge)
    _flush_vehicle_live_updates_for_scene(context.scene, bridge)
    completed = 0
    for step_index in range(count):
        if step_index:
            refresh_cloth_substep(context, bridge)
        apply_vehicle_inputs(context, bridge, dt)
        bridge.start_step(dt)
        if not bridge.fetch_results(True):
            break
        completed += 1
        if poses is not None:
            poses.update(bridge.get_active_poses())
    apply_cloth_particles(context, bridge)
    return completed


def apply_actor_poses(context, poses):
    if not poses:
        return 0
    updated = 0
    for item in context.scene.physx.actors:
        handle = item.actor_handle
        if handle not in poses or item.obj_ref is None:
            continue
        pose = poses[handle]
        world_matrix = matrix_from_pose(pose)
        if (
            item.use_bone_parent
            and item.parent_armature != "NONE"
            and item.target_bone != "NONE"
        ):
            armature = context.scene.objects.get(item.parent_armature)
            if armature is None:
                continue
            set_bone_world_matrix(armature, item.target_bone, world_matrix)
        else:
            item.obj_ref.matrix_world = world_matrix
        updated += 1
    return updated


def _step_schedule(context, dt, steps):
    """(step count, step length) that advance the scene by steps steps of dt"""
    schedule = vehicle_step_schedule(context.scene, dt * steps)
    return schedule if schedule is not None else (steps, dt)


def step_scene(context, bridge, dt, *, update_view_layer=False):
    count, step_dt = _step_schedule(context, dt, 1)
    poses = {}
    if count:
        step_bridge_batch(context, bridge, step_dt, count, poses)
    apply_actor_poses(context, poses)
    sync_vehicle_preview(context, bridge, poses, dt)
    if update_view_layer:
        context.view_layer.update()
    return poses


def run_steps(context):
    px_scene = context.scene.physx
    if not px_scene.is_initialized:
        return OperationResult.cancelled("PhysX is not initialized")
    try:
        bridge = require_initialized_bridge(context)
        dt = simulation_timestep(context.scene)
        poses = {}
        count, step_dt = _step_schedule(context, dt, int(px_scene.sim_steps))
        completed = (
            step_bridge_batch(context, bridge, step_dt, count, poses) if count else 0
        )
        if completed != count:
            return OperationResult.cancelled(
                f"Native simulation stopped after {completed} of {count} steps"
            )
        apply_actor_poses(context, poses)
        sync_vehicle_preview(context, bridge, poses, dt * px_scene.sim_steps)
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
    except Exception as error:
        return OperationResult.cancelled(str(error), error=error)
    return OperationResult.finished(f"Stepped {px_scene.sim_steps}")


def _runtime_scene(context_or_scene):
    scene = getattr(context_or_scene, "scene", None) or context_or_scene
    if scene is None or not hasattr(scene, "physx"):
        raise ValueError("Physics runtime session requires a Blender scene or context")
    return scene


def begin_runtime_session(context_or_scene):
    px_scene = _runtime_scene(context_or_scene).physx
    if px_scene.sim_running:
        return OperationResult.cancelled(
            "Another physics simulation is already running"
        )
    px_scene.sim_running = True
    return OperationResult.finished()


def end_runtime_session(context_or_scene):
    px_scene = _runtime_scene(context_or_scene).physx
    px_scene.sim_running = False
    px_scene.manipulator_handle = "0"
    return OperationResult.finished()


def stop_simulation(context):
    end_runtime_session(context)
    clear_vehicle_inputs(context)
    set_active_cloth_state(context, "PAUSED", "Simulation paused")
    return OperationResult.finished()


def _manipulator_filter():
    words = [0, 0, 0, 0]
    data = COLLISION_PRESETS.get("All Collision Touch All")
    if not data:
        return words
    for name in data[0]:
        index = get_layer_bit(name, is_query=False)
        if index >= 0:
            words[0] |= 1 << index
    for name in data[1]:
        index = get_layer_bit(name, is_query=False)
        if index >= 0:
            words[1] |= 1 << index
    for name in data[2]:
        index = get_layer_bit(name, is_query=True)
        if index >= 0:
            words[2] |= 1 << index
    return words


def update_manipulator(context, event, bridge, cursor_handle, cursor_radius):
    if (
        event.type != "MOUSEMOVE"
        or context.region is None
        or context.region_data is None
    ):
        return cursor_handle
    vector = region_2d_to_vector_3d(
        context.region,
        context.region_data,
        (event.mouse_region_x, event.mouse_region_y),
    )
    origin = region_2d_to_origin_3d(
        context.region,
        context.region_data,
        (event.mouse_region_x, event.mouse_region_y),
    )
    if abs(vector.z) <= 0.0001:
        return cursor_handle
    distance = -origin.z / vector.z
    if distance <= 0.0:
        return cursor_handle
    position = origin + vector * distance
    px_scene = context.scene.physx
    px_scene.manipulator_pos = position
    if not px_scene.use_grab_mode:
        return cursor_handle
    if cursor_handle == "0":
        shape = {
            "type": "SPHERE",
            "data": "",
            "dims": [cursor_radius, 0, 0],
            "pos": [0, 0, 0],
            "rot": [0, 0, 0, 1],
            "mat": [0.5, 0.5, 0.5],
            "filter": _manipulator_filter(),
        }
        handle = bridge.create_actor(
            "KINEMATIC",
            [position.x, position.y, position.z, 0, 0, 0, 1],
            [shape],
            1.0,
            [0, 0, 0],
            [1, 1, 1],
        )
        cursor_handle = str(handle)
        px_scene.manipulator_handle = cursor_handle
        return cursor_handle
    try:
        bridge.set_kinematic_target(
            int(cursor_handle),
            [position.x, position.y, position.z],
            [0, 0, 0, 1],
        )
    except Exception:
        debug_exception(_LOG, "Could not move the manipulator's kinematic target")
    return cursor_handle


def remove_manipulator(cursor_handle):
    if cursor_handle == "0":
        return
    try:
        require_bridge().remove_actor(int(cursor_handle))
    except (ImportError, RuntimeError, ValueError):
        pass
