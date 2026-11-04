from __future__ import annotations

from dataclasses import dataclass

from ..assetio.project_layout import project_layout_for
from ..gltf.provenance import SOURCE_PATH_KEY
from .mesh import SOURCE_GEOMETRY_SIGNATURE_KEY, export_signature, geometry_signature

BASE_MESH_KEY = "cp77_base_mesh"
IMPORT_SIGNATURE_KEY = "cp77_entity_mesh_signature"
_ENTITY_MESH_KEY = "meshPath"
_ENTITY_GLB_KEY = "sourcePath"


@dataclass(frozen=True, slots=True)
class MeshSource:
    depot_path: str
    glb_path: str


def _entity_source(obj):
    for collection in getattr(obj, "users_collection", ()):
        depot = str(collection.get(_ENTITY_MESH_KEY, "") or "")
        if depot.casefold().endswith(".mesh"):
            glb = str(
                collection.get(_ENTITY_GLB_KEY, "")
                or obj.get(SOURCE_PATH_KEY, "")
                or ""
            )
            return MeshSource(depot.replace("/", "\\"), glb)
    return None


def _depot_for_glb(glb_path: str) -> str:
    layout = project_layout_for(glb_path)
    if layout is None:
        return ""
    try:
        depot = layout.depot_path_for(glb_path)
    except ValueError:
        return ""
    lowered = depot.casefold()
    if lowered.endswith(".morphtarget.glb"):
        return depot[: -len(".glb")]
    if lowered.endswith(".glb"):
        return depot[: -len(".glb")] + ".mesh"
    return ""


def mesh_source(obj) -> MeshSource | None:
    """The game mesh an object was imported from, or None for a mesh modelled in Blender"""
    if obj is None or getattr(obj, "type", None) != "MESH":
        return None
    source = _entity_source(obj)
    if source is not None:
        return source
    glb = str(obj.get(SOURCE_PATH_KEY, "") or "")
    depot = _depot_for_glb(glb) if glb else ""
    return MeshSource(depot, glb) if depot else None


def base_mesh(obj) -> str:
    return str(obj.get(BASE_MESH_KEY, "") or "")


def set_base_mesh(obj, depot_path: str) -> None:
    obj[BASE_MESH_KEY] = str(depot_path)


def record_import_signature(obj) -> None:
    obj[IMPORT_SIGNATURE_KEY] = export_signature(obj)


def is_edited(obj) -> bool:
    """Whether the mesh changed since import"""
    recorded = str(obj.get(IMPORT_SIGNATURE_KEY, "") or "")
    if recorded:
        return recorded != export_signature(obj)
    imported_geometry = str(obj.data.get(SOURCE_GEOMETRY_SIGNATURE_KEY, "") or "")
    return not imported_geometry or imported_geometry != geometry_signature(obj.data)
