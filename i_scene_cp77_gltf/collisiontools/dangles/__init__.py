bl_info = {
    "name": "Dangle Physics Editor",
    "author": "",
    "version": (1, 8, 0),
    "blender": (5, 0, 0),
    "location": "3D View > CP77 Modding > Physics Tools > Dangles",
    "description": "Authoring and preview for REDengine Dyng, Position Projection, Spring, Pendulum, and Drag physics.",
    "category": "Animation",
}

from ...registration import RegistrationLedger
from ...blender.animgraph import presenters as animgraph_presenters
from .animgraph_projection import project_imported_dangle_node
from .animgraph_ui import draw_dangle_node
from .draw import register_global_handler, unregister_all as unregister_draw
from .ops import register as register_ops, unregister as unregister_ops
from .props import register as register_props, unregister as unregister_props
from .selection_sync import register as register_selection_sync
from .selection_sync import unregister as unregister_selection_sync
from .ui import register as register_ui, unregister as unregister_ui

_LEDGER = RegistrationLedger("dangles")


def register():
    if _LEDGER.active:
        return
    steps = (
        (register_props, unregister_props, "dangle properties"),
        (register_ui, unregister_ui, "dangle UI"),
        (register_ops, unregister_ops, "dangle operators"),
        (register_global_handler, unregister_draw, "dangle draw handlers"),
        (register_selection_sync, unregister_selection_sync, "dangle selection timer"),
        (
            lambda: animgraph_presenters.register_post_import_hook(
                animgraph_presenters.PRESENTER_DANGLE_RUNTIME,
                project_imported_dangle_node,
            ),
            lambda: animgraph_presenters.unregister_post_import_hook(
                animgraph_presenters.PRESENTER_DANGLE_RUNTIME,
                project_imported_dangle_node,
            ),
            "AnimGraph dangle projection hook",
        ),
        (
            lambda: animgraph_presenters.register_node_draw_hook(
                animgraph_presenters.PRESENTER_DANGLE_PARTICLE,
                draw_dangle_node,
            ),
            lambda: animgraph_presenters.unregister_node_draw_hook(
                animgraph_presenters.PRESENTER_DANGLE_PARTICLE,
                draw_dangle_node,
            ),
            "AnimGraph dangle particle draw hook",
        ),
        (
            lambda: animgraph_presenters.register_node_draw_hook(
                animgraph_presenters.PRESENTER_DANGLE_CONE,
                draw_dangle_node,
            ),
            lambda: animgraph_presenters.unregister_node_draw_hook(
                animgraph_presenters.PRESENTER_DANGLE_CONE,
                draw_dangle_node,
            ),
            "AnimGraph dangle cone draw hook",
        ),
    )
    try:
        for register_step, unregister_step, label in steps:
            register_step()
            _LEDGER.add_cleanup(label, unregister_step)
    except Exception:
        _LEDGER.cleanup()
        raise


def unregister():
    failures = _LEDGER.cleanup()
    if failures:
        raise RuntimeError("; ".join(
            f"{label}: {error}" for label, error in failures
        ))
