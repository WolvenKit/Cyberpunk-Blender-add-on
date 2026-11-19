"""Show or hide the pre-fractured chunks of destruction meshes on their mesh masters

The chunks are tagged on the master objects, so every copy an import makes afterwards (sector placements, entity
components, collection instances of the master) carries the state. Hiding is idempotent and reversible: a later import
with the other mode shows the chunks this module hid.
"""

from __future__ import annotations

import os

from ...assetio.mesh_destruction import destruction_chunks_for_glb
from ...assetio.paths import local_path_key
from ...core.log import get_logger
from ...gltf.submesh import submesh_index_for_object

_LOG = get_logger(__name__)

DESTRUCTION_CHUNK_MODES = ("INTACT", "ALL")
DEFAULT_DESTRUCTION_CHUNKS = "INTACT"
# Set on a submesh object whose chunk is only drawn once the object breaks.
FRACTURED_KEY = "cp77_destruction_fractured"
# Set on a fractured submesh object this module hid, so another mode can show it again.
HIDDEN_KEY = "cp77_destruction_hidden"

_SOURCE_KEY = "sourcePath"


def configured_depot_root(explicit="") -> str:
    """explicit, or the depot folder set in the add-on preferences when it exists"""
    if explicit:
        return str(explicit)
    from ...core.addon_identity import get_addon_preferences

    preferences = get_addon_preferences(required=False)
    configured = str(getattr(preferences, "depotfolder_path", "") or "")
    return configured if configured and os.path.isdir(configured) else ""


def normalize_destruction_mode(value) -> str:
    mode = str(value or DEFAULT_DESTRUCTION_CHUNKS).upper()
    if mode not in DESTRUCTION_CHUNK_MODES:
        raise ValueError(f"Unsupported destruction chunk mode: {value}")
    return mode


def _glb_source(owner) -> str:
    value = str(owner.get(_SOURCE_KEY, "") or "")
    return value if value.casefold().endswith(".glb") else ""


def _set_hidden(obj, hidden):
    obj.hide_viewport = hidden
    obj.hide_render = hidden


def apply_destruction_chunks(objects, mode, *, depot_root="") -> dict:
    """Tag the fractured chunks among objects and hide or show them for mode

    Returns counts: the fractured chunks hidden and shown, and the destruction-named meshes whose .mesh or
    .mesh.json could not be found.
    """
    mode = normalize_destruction_mode(mode)
    hidden = shown = 0
    unresolved = set()
    lookups = {}
    for obj in objects:
        if getattr(obj, "type", "") != "MESH":
            continue
        index = submesh_index_for_object(obj)
        if index is None:
            continue
        source = _glb_source(obj)
        if not source:
            continue
        chunks = lookups.get(source)
        if chunks is None:
            chunks = destruction_chunks_for_glb(source, depot_root)
            lookups[source] = chunks
            if not chunks.resolved and "_dst" in os.path.basename(source).casefold():
                unresolved.add(source)
        if not chunks.is_fractured(index):
            continue
        obj[FRACTURED_KEY] = True
        if mode == "INTACT":
            if not obj.get(HIDDEN_KEY) and not (obj.hide_viewport and obj.hide_render):
                obj[HIDDEN_KEY] = True
                _set_hidden(obj, True)
                hidden += 1
        elif obj.get(HIDDEN_KEY):
            del obj[HIDDEN_KEY]
            # A disabled entity component stays hidden.
            if obj.get("cp77_component_enabled", True):
                _set_hidden(obj, False)
                shown += 1
    return {"hidden": hidden, "shown": shown, "unresolved": tuple(sorted(unresolved))}


def apply_to_master_sources(masters, mode, source_paths, *, depot_root="") -> dict:
    """apply_destruction_chunks on the master collections built from source_paths, the glb exports just prepared

    Skips the walk entirely when none of the sources is a destruction mesh, which is the usual case.
    """
    destruction = set()
    for path in source_paths:
        if not path or not str(path).casefold().endswith(".glb"):
            continue
        chunks = destruction_chunks_for_glb(path, depot_root)
        if chunks.intact_mask is not None or (
            not chunks.resolved and "_dst" in os.path.basename(path).casefold()
        ):
            destruction.add(local_path_key(path))
    if not destruction:
        return {"hidden": 0, "shown": 0, "unresolved": ()}
    objects = []
    for collection in masters.children:
        source = _glb_source(collection)
        if source and local_path_key(source) in destruction:
            objects.extend(collection.all_objects)
    return apply_destruction_chunks(objects, mode, depot_root=depot_root)


def unresolved_warning(unresolved) -> str:
    if not unresolved:
        return ""
    names = ", ".join(os.path.basename(path) for path in unresolved[:3])
    more = f" and {len(unresolved) - 3} more" if len(unresolved) > 3 else ""
    return (
        f"Destruction chunks left visible for {names}{more}: neither the binary .mesh (in the project's "
        "source/archive or the depot folder) nor a .mesh.json export was found to tell the intact chunks from "
        "the fractured ones"
    )


def log_result(result, label) -> None:
    if result["hidden"] or result["shown"]:
        _LOG.debug(
            "%s destruction chunks: %d fractured chunk(s) hidden, %d shown",
            label,
            result["hidden"],
            result["shown"],
        )
