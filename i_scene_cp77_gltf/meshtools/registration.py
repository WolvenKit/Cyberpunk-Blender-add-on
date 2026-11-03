import bpy

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
        _LEDGER.add_cleanup("mesh tool property caches", clear_property_caches)
    except Exception:
        _LEDGER.cleanup()
        raise


def unregister_meshtools():
    failures = _LEDGER.cleanup()
    if failures:
        raise RuntimeError("; ".join(f"{label}: {error}" for label, error in failures))
