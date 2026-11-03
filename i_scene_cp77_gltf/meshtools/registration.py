import bpy

<<<<<<< Updated upstream
from ..registration import RegistrationLedger
from .operators import MESH_OPERATOR_CLASSES
from .properties import MeshValidationProperties, Vertex_Group_Properties, clear_property_caches
from .ui import MESH_UI_CLASSES


_CLASSES = (
    Vertex_Group_Properties,
    MeshValidationProperties,
    *MESH_OPERATOR_CLASSES,
    *MESH_UI_CLASSES,
)

=======
from ..core.registration import RegistrationLedger
from .operators import MESH_OPERATOR_CLASSES
from .properties import (
    MeshAnalysisProperties,
    MeshValidationProperties,
    Vertex_Group_Properties,
    clear_property_caches,
)
from .runtime.characters import clear_character_sections
from .ui import MESH_UI_CLASSES

_CLASSES = (
    Vertex_Group_Properties,
    MeshValidationProperties,
    MeshAnalysisProperties,
    *MESH_OPERATOR_CLASSES,
    *MESH_UI_CLASSES,
)
>>>>>>> Stashed changes
_LEDGER = RegistrationLedger("meshtools")


def register_meshtools():
    if _LEDGER.active:
        return
    try:
        _LEDGER.register_classes(_CLASSES)
        _LEDGER.add_property(
            bpy.types.Scene,
            "vertex_group_props",
            bpy.props.PointerProperty(type=Vertex_Group_Properties),
        )
        _LEDGER.add_property(
            bpy.types.Scene,
            "cp77_mesh_validation",
            bpy.props.PointerProperty(type=MeshValidationProperties),
        )
<<<<<<< Updated upstream
        _LEDGER.add_cleanup("mesh tool property caches", clear_property_caches)
=======
        _LEDGER.add_property(
            bpy.types.Scene,
            "cp77_mesh_analysis",
            bpy.props.PointerProperty(type=MeshAnalysisProperties),
        )
        _LEDGER.add_cleanup("mesh property caches", clear_property_caches)
        for handlers in (
            bpy.app.handlers.load_pre,
            bpy.app.handlers.undo_post,
            bpy.app.handlers.redo_post,
        ):
            _LEDGER.add_handler(handlers, clear_character_sections)
        _LEDGER.add_cleanup("character tab sections", clear_character_sections)
>>>>>>> Stashed changes
    except Exception:
        _LEDGER.cleanup()
        raise


def unregister_meshtools():
<<<<<<< Updated upstream
    failures = _LEDGER.cleanup()
    if failures:
        raise RuntimeError("; ".join(f"{label}: {error}" for label, error in failures))
=======
    _LEDGER.cleanup_or_raise()
>>>>>>> Stashed changes
