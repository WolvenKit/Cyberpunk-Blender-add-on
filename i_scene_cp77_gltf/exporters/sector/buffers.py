from __future__ import annotations

<<<<<<< Updated upstream

_BUFFER_TYPE = (
    "WolvenKit.RED4.Archive.Buffer.WorldTransformsBuffer, "
    "WolvenKit.RED4.Archive, Version=1.61.0.0, Culture=neutral, "
    "PublicKeyToken=null"
)


def _integer_handles(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"HandleId", "HandleRefId"}:
                try:
                    yield int(child)
                except (TypeError, ValueError):
                    pass
            yield from _integer_handles(child)
    elif isinstance(value, list):
        for child in value:
            yield from _integer_handles(child)


class HandleAllocator:
    def __init__(self, document):
        self._next = max(_integer_handles(document), default=0) + 1

    def allocate(self):
        value = str(self._next)
        self._next += 1
        return value


def remap_owned_handles(value, allocator):
    """Assign unique IDs to every owned handle and preserve local references."""

    mapping = {}

    def allocate(item):
        if isinstance(item, dict):
            if "HandleId" in item:
                previous = str(item["HandleId"])
                current = allocator.allocate()
                item["HandleId"] = current
                mapping[previous] = current
            for child in item.values():
                allocate(child)
        elif isinstance(item, list):
            for child in item:
                allocate(child)

    def remap_references(item):
        if isinstance(item, dict):
            if "HandleRefId" in item:
                previous = str(item["HandleRefId"])
                if previous in mapping:
                    item["HandleRefId"] = mapping[previous]
            for child in item.values():
                remap_references(child)
        elif isinstance(item, list):
            for child in item:
                remap_references(child)

    allocate(value)
    if isinstance(value, dict) and "HandleId" not in value:
        value["HandleId"] = allocator.allocate()
    remap_references(value)
    return mapping


class SharedTransformBufferRegistry:
    """Owns RED shared transform buffers and keeps all slices coherent."""

    BUFFER_KEYS = (
        "worldTransformsBuffer",
        "cookedInstanceTransforms",
    )

    def __init__(self, nodes, allocator=None):
        self.nodes = nodes
        self.allocator = allocator or HandleAllocator(nodes)
        self._buffers = {}
        self._owners = {key: [] for key in self.BUFFER_KEYS}
        self._scan()

    @staticmethod
    def _inline_transforms(shared):
        transforms = (
            shared.get("Data", {})
            .get("buffer", {})
            .get("Data", {})
            .get("Transforms")
        )
        return transforms if isinstance(transforms, list) else None

    def _scan(self):
        pending_refs = []
        for node in self.nodes:
            data = node.get("Data", {}) if isinstance(node, dict) else {}
            for buffer_key in self.BUFFER_KEYS:
                owner = data.get(buffer_key)
                if not isinstance(owner, dict):
                    continue
                self._owners[buffer_key].append(owner)
                shared = owner.get("sharedDataBuffer")
                if not isinstance(shared, dict):
                    continue
                transforms = self._inline_transforms(shared)
                if transforms is not None:
                    handle = shared.get("HandleId")
                    if handle is None:
                        handle = self.allocator.allocate()
                        shared["HandleId"] = handle
                    handle = str(handle)
                    self._buffers[(buffer_key, handle)] = transforms
                elif shared.get("HandleRefId") is not None:
                    pending_refs.append(
                        (buffer_key, str(shared["HandleRefId"]), owner)
                    )
        for buffer_key, handle, owner in pending_refs:
            if (buffer_key, handle) not in self._buffers:
                raise ValueError(
                    f"{buffer_key} references missing shared buffer {handle}"
                )

    def _resolve(self, buffer_key, owner):
        shared = owner.get("sharedDataBuffer")
        if not isinstance(shared, dict):
            raise ValueError(f"{buffer_key} has no sharedDataBuffer")
        transforms = self._inline_transforms(shared)
        if transforms is not None:
            handle = shared.get("HandleId")
            if handle is None:
                handle = self.allocator.allocate()
                shared["HandleId"] = handle
            handle = str(handle)
            self._buffers[(buffer_key, handle)] = transforms
            return handle, transforms
        handle = shared.get("HandleRefId")
        if handle is None:
            raise ValueError(
                f"{buffer_key}.sharedDataBuffer has neither Data nor HandleRefId"
            )
        handle = str(handle)
        try:
            return handle, self._buffers[(buffer_key, handle)]
        except KeyError as error:
            raise ValueError(
                f"{buffer_key} references missing shared buffer {handle}"
            ) from error

    def insert(self, buffer_key, owner, transform):
        handle, transforms = self._resolve(buffer_key, owner)
        start = int(owner.get("startIndex", 0) or 0)
        count = int(owner.get("numElements", 0) or 0)
        index = start + count
        if start < 0 or count < 0 or index > len(transforms):
            raise ValueError(
                f"Invalid {buffer_key} slice start={start}, count={count}, "
                f"buffer={len(transforms)}"
            )
        transforms.insert(index, transform)
        owner["numElements"] = count + 1
        for candidate in self._owners[buffer_key]:
            if candidate is owner:
                continue
            candidate_handle, _ = self._resolve(buffer_key, candidate)
            if candidate_handle != handle:
                continue
            candidate_start = int(candidate.get("startIndex", 0) or 0)
            if candidate_start >= index:
                candidate["startIndex"] = candidate_start + 1
        return index

    def attach_slice(self, buffer_key, owner, transforms):
        values = list(transforms)
        available = next(
            (
                (handle, buffer)
                for (key, handle), buffer in self._buffers.items()
                if key == buffer_key
            ),
            None,
        )
        shared = owner.setdefault("sharedDataBuffer", {})
        shared.clear()
        if available is None:
            handle = self.allocator.allocate()
            buffer = []
            shared.update({
                "HandleId": handle,
                "Data": {
                    "$type": "worldSharedDataBuffer",
                    "buffer": {
                        "BufferId": handle,
                        "Flags": 4063232,
                        "Type": _BUFFER_TYPE,
                        "Data": {"Transforms": buffer},
                    },
                },
            })
            self._buffers[(buffer_key, handle)] = buffer
        else:
            handle, buffer = available
            shared["HandleRefId"] = handle
        owner["startIndex"] = len(buffer)
        owner["numElements"] = len(values)
        buffer.extend(values)
        if owner not in self._owners[buffer_key]:
            self._owners[buffer_key].append(owner)
        return handle


class SectorSceneIndex:
    def __init__(self, collection):
        self._collections = {}
        self._world_instances = {}
        self._decals = {}
        for child in collection.children:
            node_index = child.get("nodeIndex")
            if node_index is None:
                continue
            instance_index = child.get("instance_idx", 0)
            self._collections.setdefault(
                (int(node_index), int(instance_index)), child
            )
            self._world_instances.setdefault(
                (
                    int(node_index),
                    int(child.get("tl_instance_idx", 0)),
                    int(child.get("sub_instance_idx", 0)),
                ),
                child,
            )
        for obj in collection.objects:
            node_index = obj.get("nodeIndex")
            if node_index is None:
                continue
            self._decals.setdefault(
                (int(node_index), int(obj.get("instance_idx", 0))), obj
            )

    def collection(self, node_index, instance_index):
        return self._collections.get((int(node_index), int(instance_index)))

    def world_instance(self, node_index, top_index, sub_index):
        return self._world_instances.get(
            (int(node_index), int(top_index), int(sub_index))
        )

    def decal(self, node_index, instance_index):
        return self._decals.get((int(node_index), int(instance_index)))
=======
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
>>>>>>> Stashed changes
