import bpy

from ..blender.animgraph import presenters as animgraph_presenters
from ..blender.animgraph.dangle_editor import project_imported_dangle_node
from ..blender.animgraph.tree import (
    register_tree_change_hook,
    unregister_tree_change_hook,
)
from ..blender.physics.bridge_session import BRIDGE_HOST
from ..core.log import get_logger
from ..core.registration import RegistrationLedger
from ..physics.runtime.bridge import (
    install_host,
    invalidate_physx_runtime,
    shutdown_physx_capability,
    uninstall_host,
)
from .operators import COLLISION_OPERATOR_CLASSES
from .properties import (
    COLLISION_PROPERTY_CLASSES,
    DANGLE_AddonState,
    PhysXObjectProperties,
    PhysXSceneProperties,
    PhysXVehicleProperties,
    clear_property_item_caches,
)
from .runtime.dangle.overlay import register_global_handler, unregister_all
from .runtime.dangle.preview import stop_active_previews
from .runtime.dangle.rigs import clear_dangle_rigs
from .runtime.overlay import register_viz, unregister_viz
from .runtime.simulation import stop_active_simulations
from .runtime.vehicle_camera import stop_vehicle_camera
from .runtime.vehicle_guides import register_vehicle_guides, unregister_vehicle_guides
from .runtime.vehicle_preview import invalidate_vehicle_runtime_state
from .services.dangles import selection
from .services.dangles.sync import cancel_pending_graph_syncs, notify_graph_tree_changed
from .services.dangles.view import clear_view_return_states
from .ui import COLLISION_UI_CLASSES
from .ui.dangle_animgraph import draw_dangle_node

_CLASSES = (
    *COLLISION_PROPERTY_CLASSES,
    *COLLISION_OPERATOR_CLASSES,
    *COLLISION_UI_CLASSES,
)

_LEDGER = RegistrationLedger("collisiontools")
_LOG = get_logger(__name__)


@bpy.app.handlers.persistent
def _depsgraph_update_handler(scene, depsgraph):
    vehicle = getattr(scene, "physx_vehicle", None)
    vehicle_object_ptrs = {
        obj.as_pointer()
        for obj in (
            getattr(vehicle, "rig", None),
            getattr(vehicle, "chassis", None),
            getattr(vehicle, "front_left", None),
            getattr(vehicle, "front_right", None),
            getattr(vehicle, "rear_left", None),
            getattr(vehicle, "rear_right", None),
            getattr(vehicle, "bike_front", None),
            getattr(vehicle, "bike_rear", None),
        )
        if obj is not None
    }
    for update in depsgraph.updates:
        datablock = update.id
        if isinstance(datablock, bpy.types.Armature):
            clear_property_item_caches()
            return
        if isinstance(datablock, bpy.types.Mesh):
            return
        if not isinstance(datablock, bpy.types.Object):
            continue
        physx = getattr(datablock, "physx", None)
        if datablock.type == "ARMATURE":
            clear_property_item_caches()
        if (
            datablock.type == "ARMATURE"
            or datablock.as_pointer() in vehicle_object_ptrs
            or (physx is not None and len(physx.shapes) > 0)
        ):
            return


@bpy.app.handlers.persistent
def _native_runtime_invalidation_handler(*_args):
    def run_cleanup(callback):
        try:
            callback()
        except Exception:
            _LOG.warning("A Physics Tools cleanup step failed", exc_info=True)

    for callback in (
        stop_active_previews,
        cancel_pending_graph_syncs,
        stop_active_simulations,
        lambda: invalidate_vehicle_runtime_state(restore=False),
        invalidate_physx_runtime,
    ):
        run_cleanup(callback)


def _register_animgraph_hooks():
    hooks = (
        (
            "post",
            animgraph_presenters.PRESENTER_DANGLE_RUNTIME,
            project_imported_dangle_node,
        ),
        ("draw", animgraph_presenters.PRESENTER_DANGLE_PARTICLE, draw_dangle_node),
        ("draw", animgraph_presenters.PRESENTER_DANGLE_CONE, draw_dangle_node),
    )
    for kind, presenter, callback in hooks:
        if kind == "post":
            animgraph_presenters.register_post_import_hook(presenter, callback)
            _LEDGER.add_cleanup(
                f"AnimGraph post-import hook {presenter}",
                lambda presenter=presenter, callback=callback: (
                    animgraph_presenters.unregister_post_import_hook(
                        presenter, callback
                    )
                ),
            )
            continue
        animgraph_presenters.register_node_draw_hook(presenter, callback)
        _LEDGER.add_cleanup(
            f"AnimGraph draw hook {presenter}",
            lambda presenter=presenter, callback=callback: (
                animgraph_presenters.unregister_node_draw_hook(presenter, callback)
            ),
        )


def register_collisiontools():
    if _LEDGER.active:
        return
    try:
        _LEDGER.register_classes(_CLASSES)
        _LEDGER.add_property(
            bpy.types.Object,
            "dangle_state",
            bpy.props.PointerProperty(type=DANGLE_AddonState),
        )
        _LEDGER.add_property(
            bpy.types.Scene,
            "dangle_active_rig_index",
            bpy.props.IntProperty(default=0),
        )
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
        _LEDGER.add_property(
            bpy.types.Scene,
            "physx_vehicle",
            bpy.props.PointerProperty(type=PhysXVehicleProperties),
        )

        install_host(BRIDGE_HOST)
        _LEDGER.add_cleanup("PhysX bridge host", lambda: uninstall_host(BRIDGE_HOST))
        _LEDGER.add_cleanup("native PhysX capability", shutdown_physx_capability)
        for handlers in (
            bpy.app.handlers.load_pre,
            bpy.app.handlers.load_post,
            bpy.app.handlers.undo_pre,
            bpy.app.handlers.undo_post,
        ):
            _LEDGER.add_handler(handlers, _native_runtime_invalidation_handler)
        for handlers in (
            bpy.app.handlers.load_pre,
            bpy.app.handlers.undo_post,
            bpy.app.handlers.redo_post,
        ):
            _LEDGER.add_handler(handlers, clear_dangle_rigs)
        _LEDGER.add_cleanup("dangle rig list", clear_dangle_rigs)

        register_global_handler()
        _LEDGER.add_cleanup("dangle draw handlers", unregister_all)
        selection.register()
        _LEDGER.add_cleanup("dangle selection timer", selection.unregister)
        register_viz()
        _LEDGER.add_cleanup("PhysX visualization", unregister_viz)
        register_vehicle_guides()
        _LEDGER.add_cleanup("vehicle authoring guides", unregister_vehicle_guides)
        _LEDGER.add_cleanup("vehicle game camera", stop_vehicle_camera)
        _LEDGER.add_handler(
            bpy.app.handlers.depsgraph_update_post, _depsgraph_update_handler
        )

        _register_animgraph_hooks()
        register_tree_change_hook(notify_graph_tree_changed)
        _LEDGER.add_cleanup(
            "AnimGraph tree change hook",
            lambda: unregister_tree_change_hook(notify_graph_tree_changed),
        )
        _LEDGER.add_cleanup("dangle editor view state", clear_view_return_states)
        _LEDGER.add_cleanup("active dangle previews", stop_active_previews)
        _LEDGER.add_cleanup(
            "AnimGraph topology sync timers", cancel_pending_graph_syncs
        )
        _LEDGER.add_cleanup("active PhysX simulations", stop_active_simulations)
        _LEDGER.add_cleanup(
            "vehicle runtime", lambda: invalidate_vehicle_runtime_state(restore=True)
        )
        _LEDGER.add_cleanup("PhysX enum caches", clear_property_item_caches)
    except Exception:
        _LEDGER.cleanup()
        raise


def unregister_collisiontools():
    _LEDGER.cleanup_or_raise()
