from __future__ import annotations

import bpy
from bpy.app.handlers import persistent

from ...blender.identity import rna_is_live
from ..blender.mesh_appearance import ComponentView, scan_component
from ..blender.scene import EntityIndex, scan_entities

# The entity index and the collection count it was built at.
_INDEX: list = [None, -1]
# The last component view: (appearance collection session id, component name, its object count, the file's object
# and collection counts), view.
_VIEW: list = [None, None]


@persistent
def clear_entity_caches(_unused=None):
    _INDEX[:] = (None, -1)
    _VIEW[:] = (None, None)


def entity_index() -> EntityIndex:
    """The file's imported entities"""
    index, count = _INDEX
    if (
        index is None
        or count != len(bpy.data.collections)
        or not all(
            rna_is_live(collection)
            for ref in index.entities
            for collection in ref.collections
        )
    ):
        index = scan_entities()
        _INDEX[:] = (index, len(bpy.data.collections))
    return index


def component_view(collection, name: str) -> ComponentView:
    """What the panel shows of one component"""
    key = (
        collection.session_uid,
        name,
        len(collection.all_objects),
        len(bpy.data.objects),
        len(bpy.data.collections),
    )
    view = _VIEW[1]
    if _VIEW[0] != key or not all(rna_is_live(obj) for obj in view.objects):
        view = scan_component(collection, name)
        _VIEW[:] = (key, view)
    return view
