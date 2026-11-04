from __future__ import annotations

from ...blender.mesh import export_signature
from ...blender.mesh_source import IMPORT_SIGNATURE_KEY
from ...entity.model.import_record import (
    IMPORT_RECORD_KEY,
    ImportedAppearance,
    encode_import_record,
)

COMPONENT_TAG_KEY = "cp77_entity_component"


def _component_collections(collection):
    for child in collection.children_recursive:
        if not child.get("meshPath"):
            continue
        component = next(
            (
                str(obj["componentName"])
                for obj in child.objects
                if obj.get("componentName")
            ),
            "",
        )
        if component:
            # The tag finds the collection again after the author renames it.
            child[COMPONENT_TAG_KEY] = component
            yield component, child.name


def record_imported_appearance(
    collection,
    *,
    import_id,
    ent_path,
    app_path,
    app_depot,
    appearance,
    entry_name,
    mesh_cache=None,
):
    """Store the import record on the appearance collection and fingerprint its meshes"""
    collection[IMPORT_RECORD_KEY] = encode_import_record(
        ImportedAppearance(
            import_id=import_id,
            ent_path=ent_path,
            app_path=app_path,
            app_depot=app_depot,
            appearance=appearance,
            entry_name=entry_name,
            collection_names=tuple(_component_collections(collection)),
        )
    )
    # Objects sharing a mesh (and the same slots) share one fingerprint, computed once.
    mesh_cache = {} if mesh_cache is None else mesh_cache
    signatures = {}
    for obj in collection.all_objects:
        if obj.type != "MESH":
            continue
        key = (
            obj.data.as_pointer(),
            tuple(
                slot.material.as_pointer() if slot.material else 0
                for slot in obj.material_slots
            ),
            str(obj.get("cp77_direct_mesh_extras", "")),
        )
        if key not in signatures:
            signatures[key] = export_signature(obj, mesh_cache=mesh_cache)
        obj[IMPORT_SIGNATURE_KEY] = signatures[key]
