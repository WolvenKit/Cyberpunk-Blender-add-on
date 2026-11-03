from __future__ import annotations


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
