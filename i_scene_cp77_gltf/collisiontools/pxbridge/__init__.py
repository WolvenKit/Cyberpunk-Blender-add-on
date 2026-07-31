import bpy

from ...registration import RegistrationLedger
from .capability import shutdown_physx_capability
from .io_phys import (
    PHYSX_OT_confirm_import,
    PHYSX_OT_export_phys,
    PHYSX_OT_export_scene,
    PHYSX_OT_import_phys,
    PHYSX_OT_import_scene,
    PHYSX_OT_load_cooked,
    PHYSX_OT_save_cooked,
)
from .physx_ops import (
    PHYSX_OT_apply_force,
    PHYSX_OT_build_scene,
    PHYSX_OT_calc_dynamics,
    PHYSX_OT_cook_mesh,
    PHYSX_OT_fit_bounds_shape,
    PHYSX_OT_init_scene,
    PHYSX_OT_list_action,
    PHYSX_OT_reset_session,
    PHYSX_OT_run_steps,
    PHYSX_OT_shape_action,
    PHYSX_OT_sim_step,
    PHYSX_OT_stop_sim,
    PHYSX_OT_update_gravity,
    PHYSX_OT_validate_scene,
)
from .physx_props import (
    PhysXActorItem,
    PhysXObjectProperties,
    PhysXSceneProperties,
    PhysXShapeItem,
)
from .physx_ui import PhysXToolsGizmoGroup, PHYSX_UL_actor_list, PHYSX_UL_shape_list
from .viz import invalidate_visualization_cache, register_viz, unregister_viz


classes = (
    PhysXShapeItem,
    PhysXActorItem,
    PhysXObjectProperties,
    PhysXSceneProperties,
    PHYSX_OT_init_scene,
    PHYSX_OT_validate_scene,
    PHYSX_OT_sim_step,
    PHYSX_OT_stop_sim,
    PHYSX_OT_apply_force,
    PHYSX_OT_update_gravity,
    PHYSX_OT_run_steps,
    PHYSX_OT_shape_action,
    PHYSX_OT_list_action,
    PHYSX_OT_fit_bounds_shape,
    PHYSX_OT_cook_mesh,
    PHYSX_OT_calc_dynamics,
    PHYSX_OT_build_scene,
    PHYSX_OT_reset_session,
    PHYSX_OT_save_cooked,
    PHYSX_OT_load_cooked,
    PHYSX_OT_export_phys,
    PHYSX_OT_import_phys,
    PHYSX_OT_confirm_import,
    PHYSX_OT_export_scene,
    PHYSX_OT_import_scene,
    PHYSX_UL_actor_list,
    PHYSX_UL_shape_list,
    PhysXToolsGizmoGroup,
)

_LEDGER = RegistrationLedger("pxbridge")


@bpy.app.handlers.persistent
def depsgraph_update_handler(scene, depsgraph):
    invalidate_visualization_cache()


def register():
    if _LEDGER.active:
        return
    try:
        _LEDGER.register_classes(classes)
        _LEDGER.add_property(
            bpy.types.Object,
            "physx",
            bpy.props.PointerProperty(type=PhysXObjectProperties),
        )
        _LEDGER.add_property(
            bpy.types.Scene,
            "physx",
            bpy.props.PointerProperty(type=PhysXSceneProperties),
        )
        register_viz()
        _LEDGER.add_cleanup("physx visualization", unregister_viz)
        _LEDGER.add_handler(
            bpy.app.handlers.depsgraph_update_post,
            depsgraph_update_handler,
        )
    except Exception:
        _LEDGER.cleanup()
        raise


def unregister():
    failures = list(_LEDGER.cleanup())
    try:
        shutdown_physx_capability()
    except Exception as error:
        failures.append(("native capability", error))
    if failures:
        raise RuntimeError("; ".join(
            f"{label}: {error}" for label, error in failures
        ))
