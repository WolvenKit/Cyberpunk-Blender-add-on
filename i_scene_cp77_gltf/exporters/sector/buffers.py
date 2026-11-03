from __future__ import annotations

import os
from collections import defaultdict

import bpy

from ...assetio.paths import local_path_key, strip_json_suffix
from ...assetio.project_layout import project_layout_for
from ...assetio.values import coerce_int
from .new_sectors import NEW_SECTOR_KEY, new_sector_collections

_WORLD_COLLISION = "WORLD_COLLISION"


def imported_sector_collections(scene) -> tuple[bpy.types.Collection, ...]:
    """The scene's imported sector collections"""
    return tuple(
        collection
        for collection in scene.collection.children_recursive
        if isinstance(collection.get("cp77_sector_path"), str)
        and collection["cp77_sector_path"]
    )


def sector_depot_path(path) -> str | None:
    """The depot path of a source sector file under its project's source/raw"""
    layout = project_layout_for(path)
    return layout.depot_path_for(path) if layout is not None else None


def copied_objects(scene) -> frozenset[int]:
    """The pointers of the objects in the scene's new-sector collections"""
    return frozenset(
        obj.as_pointer()
        for collection in new_sector_collections(scene)
        for obj in collection.all_objects
    )


def sector_tree(collection):
    """The collections of an imported sector"""
    pending, seen = [collection], set()
    while pending:
        current = pending.pop()
        if current.as_pointer() in seen:
            continue
        seen.add(current.as_pointer())
        yield current
        pending.extend(
            child
            for child in current.children
            if not child.get("cp77_sector_path") and not child.get(NEW_SECTOR_KEY)
        )


def _sector_name(collection):
    name = collection.get("cp77_sector_name")
    return (
        name
        if isinstance(name, str) and name
        else strip_json_suffix(os.path.basename(collection["cp77_sector_path"]))
    )


def _entry(item):
    """The node data entry an object or placed collection records, or None"""
    index = coerce_int(item.get("cp77_node_data_index"), -1)
    return index if index >= 0 else None


def placement_record(obj):
    """(sector name, node data entry, kind, index) an object records, or None"""
    physx = getattr(obj, "physx", None)
    if (
        physx is not None
        and physx.source_kind == _WORLD_COLLISION
        and physx.source_node_data_index >= 0
    ):
        return (
            physx.source_sector,
            physx.source_node_data_index,
            "actor",
            physx.source_actor_index,
        )
    sector_name, entry = obj.get("cp77_sector_name"), _entry(obj)
    if not isinstance(sector_name, str) or entry is None:
        return None
    if "cp77_element_idx" in obj:
        return sector_name, entry, "element", coerce_int(obj["cp77_element_idx"], -1)
    return sector_name, entry, "placement", None


def _check_one_collection_per_sector(sectors):
    by_path = defaultdict(list)
    for sector in sectors:
        path = sector["cp77_sector_path"]
        by_path[(sector_depot_path(path) or local_path_key(path)).casefold()].append(
            sector
        )
    for collections in by_path.values():
        if len(collections) > 1:
            path = collections[0]["cp77_sector_path"]
            raise ValueError(
                f"{sector_depot_path(path) or path}: {len(collections)} sector collections were imported from this "
                f"sector ({', '.join(collection.name for collection in collections)}); keep one before exporting."
            )


class SectorSceneIndex:
    """The scene's holdings of an imported sector's node data entries"""

    def __init__(self, sector_name):
        self.sector_name = sector_name
        self.held = set()
        self.counts = {}
        self.roots = {}
        self.elements = defaultdict(lambda: defaultdict(list))
        self.actors = defaultdict(lambda: defaultdict(list))
        self._placing = defaultdict(list)

    def add(self, obj, record):
        _name, entry, kind, index = record
        self.held.add(entry)
        if kind == "actor":
            self.actors[entry][index].append(obj)
        elif kind == "element":
            self.elements[entry][index].append(obj)
        else:
            self._placing[entry].append(obj)

    def finish(self):
        for entry, objects in self._placing.items():
            # A projector's plane or a rotating mesh's spinning child follows the object it hangs from.
            self.roots[entry] = sorted(
                (obj for obj in objects if obj.parent not in objects),
                key=lambda obj: obj.name,
            )


class ScenePlacements:
    """The scene's imported sector placements"""

    def __init__(self, scene):
        self.sectors = imported_sector_collections(scene)
        _check_one_collection_per_sector(self.sectors)
        self.copies = copied_objects(scene)
        self.copy_entries = set()
        self.copy_elements = defaultdict(set)
        self.copy_actors = defaultdict(set)
        self._by_name = defaultdict(list)
        for sector in self.sectors:
            self._by_name[_sector_name(sector)].append(sector)
        self._indexes = {
            sector.as_pointer(): SectorSceneIndex(_sector_name(sector))
            for sector in self.sectors
        }
        self._trees = {}
        for sectors in self._by_name.values():
            for sector in sectors if len(sectors) > 1 else ():
                collections = tuple(sector_tree(sector))
                self._trees[sector.as_pointer()] = (
                    {collection.as_pointer() for collection in collections},
                    {
                        obj.as_pointer()
                        for collection in collections
                        for obj in collection.objects
                    },
                )
        copied_collections = {
            collection.as_pointer()
            for new_sector in new_sector_collections(scene)
            for collection in (new_sector, *new_sector.children_recursive)
        }
        for obj in scene.collection.all_objects:
            record = placement_record(obj) if "cp77_node_data_index" in obj else None
            if record is None:
                continue
            if obj.as_pointer() in self.copies:
                self._add_copy(record)
                continue
            sector = self._owner(record[0], obj)
            if sector is not None:
                self._indexes[sector.as_pointer()].add(obj, record)
        for collection in scene.collection.children_recursive:
            self._add_collection(
                collection, collection.as_pointer() in copied_collections
            )
        for index in self._indexes.values():
            index.finish()

    def _add_copy(self, record):
        sector_name, entry, kind, index = record
        self.copy_entries.add((sector_name, entry))
        if kind == "actor":
            self.copy_actors[(sector_name, entry)].add(index)
        elif kind == "element":
            self.copy_elements[(sector_name, entry)].add(index)

    def _add_collection(self, collection, copied):
        """Whether a collection that places an entry still holds it"""
        sector_name, entry = collection.get("cp77_sector_name"), _entry(collection)
        if (
            not isinstance(sector_name, str)
            or entry is None
            or collection.get("cp77_sector_path")
        ):
            return
        placed = not collection.get("cp77_organizational_collection") and len(
            collection.all_objects
        )
        if copied:
            if placed:
                self.copy_entries.add((sector_name, entry))
            return
        sector = self._owner(sector_name, collection, collection=True)
        if sector is None:
            return
        index = self._indexes[sector.as_pointer()]
        if placed:
            index.held.add(entry)
        if "cp77_placed_count" in collection:
            index.counts[entry] = coerce_int(collection["cp77_placed_count"], -1)

    def _owner(self, sector_name, item, *, collection=False):
        """The imported sector the object or collection item belongs to, or None"""
        sectors = self._by_name.get(sector_name, ())
        if len(sectors) <= 1:
            return sectors[0] if sectors else None
        tree = 0 if collection else 1
        holding = [
            sector
            for sector in sectors
            if item.as_pointer() in self._trees[sector.as_pointer()][tree]
        ]
        if len(holding) == 1:
            return holding[0]
        raise ValueError(
            f"{item.name} places a node of {sector_name}, a name {len(sectors)} imported sectors share "
            f"({', '.join(sector['cp77_sector_path'] for sector in sectors)}), but sits under "
            f"{'none' if not holding else 'more than one'} of them; move it back under its own sector, or into a new "
            "sector to copy it."
        )

    def index(self, collection) -> SectorSceneIndex:
        """What the scene holds of the imported sector collection"""
        return self._indexes[collection.as_pointer()]
