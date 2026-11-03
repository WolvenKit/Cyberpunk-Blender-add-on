import bpy

from ...blender.operator_results import finish_operator
from ...core.log import get_logger
from ...core.notifications import report
from ...physics.runtime.bridge import require_bridge
from ..runtime.simulation import (
    _ACTIVE_SIM_SESSIONS,
    end_runtime_session,
    register_simulation_session,
    remove_manipulator,
    run_steps,
    simulation_timestep,
    step_scene,
    stop_simulation,
    update_manipulator,
)
from ..runtime.vehicle_preview import handle_vehicle_event
from ..services.scene import (
    build_scene,
    initialize_scene,
    reset_session,
    start_simulation,
    update_gravity,
    validate_scene,
)

_LOG = get_logger(__name__)


class PHYSX_OT_init_scene(bpy.types.Operator):
    bl_idname = "physx.init_scene"
    bl_label = "Initialize Scene"

    add_ground: bpy.props.BoolProperty(name="Add Ground Plane", default=True)

    def execute(self, context):
        return finish_operator(self, initialize_scene(context, self.add_ground))


class PHYSX_OT_validate_scene(bpy.types.Operator):
    bl_idname = "physx.validate_scene"
    bl_label = "Validate Scene"

    def execute(self, context):
        return finish_operator(self, validate_scene(context))


class PHYSX_OT_build_scene(bpy.types.Operator):
    bl_idname = "physx.build_scene"
    bl_label = "Build PhysX Scene"

    def execute(self, context):
        return finish_operator(self, build_scene(context))


class PHYSX_OT_run_steps(bpy.types.Operator):
    bl_idname = "physx.run_steps"
    bl_label = "Step N"

    @classmethod
    def poll(cls, context):
        return context.scene.physx.is_initialized

    def execute(self, context):
        return finish_operator(self, run_steps(context))


class PHYSX_OT_sim_step(bpy.types.Operator):
    bl_idname = "physx.sim_step"
    bl_label = "Run Simulation"

    cursor_radius: bpy.props.FloatProperty(name="Cursor Radius", default=1.0)

    _timer = None
    _cursor_handle = "0"
    _window_manager = None
    _scene = None
    _session_key = None
    _timestep = 1.0 / 60.0

    @classmethod
    def poll(cls, context):
        px_scene = context.scene.physx
        return px_scene.is_initialized and not px_scene.sim_running

    def invoke(self, context, event):
        result = start_simulation(context)
        if not result.ok:
            return finish_operator(self, result)
        self._window_manager = context.window_manager
        self._scene = context.scene
        self._session_key = id(self)
        self._timestep = simulation_timestep(context.scene)
        self._timer = context.window_manager.event_timer_add(
            self._timestep, window=context.window
        )
        register_simulation_session(
            self._session_key, self._shutdown_session, owner="collisiontools"
        )
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if not context.scene.physx.sim_running or event.type in {"ESC", "RIGHTMOUSE"}:
            return self.cancel(context)
        try:
            bridge = require_bridge()
            if handle_vehicle_event(context, event):
                return {"RUNNING_MODAL"}
            self._cursor_handle = update_manipulator(
                context,
                event,
                bridge,
                self._cursor_handle,
                self.cursor_radius,
            )
            if event.type == "TIMER":
                step_scene(context, bridge, self._timestep, update_view_layer=True)
        except Exception as error:
            report(
                self,
                "ERROR",
                f"PhysX simulation stopped: {error}",
                logger=_LOG,
                error=error,
            )
            self._shutdown_session(context)
            return {"CANCELLED"}
        return {"PASS_THROUGH"}

    def execute(self, context):
        return self.invoke(context, None)

    def _shutdown_session(self, context=None):
        if context is not None:
            stop_simulation(context)
        elif self._scene is not None and hasattr(self._scene, "physx"):
            end_runtime_session(self._scene)
        if self._timer is not None and self._window_manager is not None:
            try:
                self._window_manager.event_timer_remove(self._timer)
            except (ReferenceError, ValueError):
                pass
            self._timer = None
        remove_manipulator(self._cursor_handle)
        self._cursor_handle = "0"
        if self._session_key is not None:
            _ACTIVE_SIM_SESSIONS.pop(self._session_key, None)
            self._session_key = None
        self._window_manager = None
        self._scene = None

    def cancel(self, context):
        self._shutdown_session(context)
        return {"CANCELLED"}


class PHYSX_OT_stop_sim(bpy.types.Operator):
    bl_idname = "physx.stop_sim"
    bl_label = "Stop"

    def execute(self, context):
        return finish_operator(self, stop_simulation(context))


class PHYSX_OT_update_gravity(bpy.types.Operator):
    bl_idname = "physx.update_gravity"
    bl_label = "Update Gravity"

    def execute(self, context):
        return finish_operator(self, update_gravity(context))


class PHYSX_OT_reset_session(bpy.types.Operator):
    bl_idname = "physx.reset_session"
    bl_label = "Reset"

    def execute(self, context):
        return finish_operator(self, reset_session(context))
