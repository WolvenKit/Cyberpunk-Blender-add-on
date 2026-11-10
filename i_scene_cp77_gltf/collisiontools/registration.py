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
from .runtime.dangle.overlay import (
    invalidate_static_draw_cache,
    register_global_handler,
    unregister_all,
)
from .runtime.dangle.preview import stop_active_previews
from .runtime.dangle.rigs import clear_dangle_rigs
from .runtime.overlay import mark_overlay_dirty, register_viz, unregister_viz
from .runtime.simulation import stop_active_simulations
from .runtime.vehicle_camera import stop_vehicle_camera
from .runtime.vehicle_guides import register_vehicle_guides, unregister_vehicle_guides
from .runtime.vehicle_preview import (
    forget_logged_bridge_builds,
    invalidate_vehicle_runtime_state,
)
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
def _depsgraph_update_handler(_scene, depsgraph):
    caches_cleared = False
    for update in depsgraph.updates:
        datablock = update.id
        is_object = isinstance(datablock, bpy.types.Object)
        if is_object or isinstance(datablock, bpy.types.Scene):
            mark_overlay_dirty()
        if not caches_cleared and (
            isinstance(datablock, bpy.types.Armature)
            or (is_object and datablock.type == "ARMATURE")
        ):
            clear_property_item_caches()
            caches_cleared = True
    selection.ensure_polling()


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
        for handlers in (
            bpy.app.handlers.depsgraph_update_post,
            bpy.app.handlers.load_pre,
        ):
            _LEDGER.add_handler(handlers, invalidate_static_draw_cache)
        _LEDGER.add_handler(bpy.app.handlers.load_pre, selection.reset_selection_state)
        _LEDGER.add_cleanup("dangle selection state", selection.reset_selection_state)
        selection.reset_selection_state()
        _LEDGER.add_cleanup("dangle selection timer", selection.stop_polling)
        _LEDGER.add_handler(bpy.app.handlers.load_pre, forget_logged_bridge_builds)
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
