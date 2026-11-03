from __future__ import annotations

import os
from dataclasses import dataclass

import bpy

from ...blender.collections import collection_parent_map
from ...entity.domain.light_zones import ZONES, zone_strength_property
from ...entity.model.import_record import (
    IMPORT_RECORD_KEY,
    ImportedAppearance,
    decode_import_record,
)
from ...importers.entity.policy import LIGHT_COMPONENT_TYPES

COMPONENT_NAME_KEY = "componentName"


@dataclass(frozen=True, slots=True)
class EntityRef:
    """One import of an entity"""

    import_id: str
    label: str
    ent_path: str
    collections: tuple


class EntityIndex:
    """The file's imported entities in picker order"""

    def __init__(self, entities: tuple[EntityRef, ...], records: dict):
        self.entities = entities
        self._collections = {ref.import_id: ref.collections for ref in entities}
        self._records = records

    def collections(self, import_id: str) -> tuple:
        """The appearance collections of one import, in the file's collection order"""
        return self._collections.get(import_id, ())

    def record(self, collection) -> ImportedAppearance | None:
        return self._records.get(collection.session_uid)


def appearance_record(collection) -> ImportedAppearance | None:
    text = collection.get(IMPORT_RECORD_KEY) if collection is not None else None
    if not text:
        return None
    try:
        return decode_import_record(str(text))
    except (TypeError, ValueError, KeyError):
        return None


def _entity_name(ent_path: str) -> str:
    name = os.path.basename(ent_path)
    for suffix in (".json", ".ent"):
        if name.casefold().endswith(suffix):
            name = name[: -len(suffix)]
    return name


def scan_entities() -> EntityIndex:
    """The entities and appearance records the file's collections hold"""
    grouped: dict[str, list] = {}
    paths: dict[str, str] = {}
    records = {}
    for collection in bpy.data.collections:
        record = appearance_record(collection)
        if record is None:
            continue
        records[collection.session_uid] = record
        grouped.setdefault(record.import_id, []).append(collection)
        paths.setdefault(record.import_id, record.ent_path)
    refs = []
    seen_labels: dict[str, int] = {}
    order = {
        import_id: min(collection.name for collection in collections)
        for import_id, collections in grouped.items()
    }
    for import_id in sorted(
        grouped, key=lambda key: (_entity_name(paths[key]).casefold(), order[key])
    ):
        name = _entity_name(paths[import_id])
        seen_labels[name] = seen_labels.get(name, 0) + 1
        label = name if seen_labels[name] == 1 else f"{name} ({seen_labels[name]})"
        refs.append(
            EntityRef(import_id, label, paths[import_id], tuple(grouped[import_id]))
        )
    return EntityIndex(tuple(refs), records)


def holds_imported_lights(collections) -> bool:
    """Whether an entity's appearance collections hold lights or light zones from its import"""
    strengths = tuple(zone_strength_property(zone) for zone in range(len(ZONES)))
    return any(
        (obj.type == "LIGHT" and obj.get("cp77_type") in LIGHT_COMPONENT_TYPES)
        or any(name in obj for name in strengths)
        for collection in collections
        for obj in collection.all_objects
    )


def component_objects(collection, component_name: str) -> tuple:
    return tuple(
        obj
        for obj in collection.all_objects
        if str(obj.get(COMPONENT_NAME_KEY, "")) == component_name
    )


def component_for_object(obj):
    """The appearance collection holding obj and its component name, or None"""
    name = str(obj.get(COMPONENT_NAME_KEY, "")) if obj is not None else ""
    if not name:
        return None
    parents = collection_parent_map()
    pending = list(obj.users_collection)
    seen = set()
    while pending:
        collection = pending.pop()
        pointer = collection.as_pointer()
        if pointer in seen:
            continue
        seen.add(pointer)
        if collection.get(IMPORT_RECORD_KEY):
            return collection, name
        pending.extend(parents.get(pointer, ()))
    return None
