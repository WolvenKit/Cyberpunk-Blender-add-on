from __future__ import annotations

import copy
import ntpath
import os
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

from mathutils import Matrix, Quaternion, Vector

from ...assetio.handles import HandleIndex
from ...assetio.json_style import JsonStyle, styled_dumps
from ...assetio.paths import depot_path_key, is_plain_file_name
from ...assetio.project_layout import ProjectLayout
from ...assetio.streaming_block import SectorDescriptor, streaming_box
from ...assetio.streaming_sector import (
    COOKED_PLAIN_TYPES,
    PLAIN_NODE_FIELDS,
    NodeInstance,
    collision_actor_scale,
    collision_actor_shapes,
    collision_shape_rotation,
    copied_entry_source,
    copied_global_node_id,
    entry_global_node_id,
    node_instance_entry,
    one_actor_collision_node,
    plain_node_data,
    resource_depot_paths,
    streaming_sector_document,
)
from ...assetio.transform_values import vector3_from_data
from ...assetio.values import nested_dict, resource_path_text
from ...bartmoss.matrix import box_around, scale_shears
from ...blender.matrix import instance_matrix, object_world_matrix
from ...entity.domain.lights import edited_light_data
from ...importers.sector.model import ParsedSector
from ..collision.heightfield import (
    TERRAIN_STREAMING_DISTANCE,
    cooked_heightfield_shapes,
    terrain_collision_node,
)
from .buffers import placement_record
from .edits import placed_entries
from .new_sectors import NEW_SECTOR_KEY
from .transforms import placement_matrix, scale_change, scales_near, transform_values

_COOKED_COLLISION = "worldCookedCollisionNode"
_DEFAULT_CATEGORY = "Exterior"
_DESTRUCTIBLE = "worldInstancedDestructibleMeshNode"
_HEIGHTFIELD = "worldTerrainCollisionNode"
_INSTANCED_MESH = "worldInstancedMeshNode"
_LIGHT = "worldStaticLightNode"
_SECTOR_EXTENSION = ".streamingsector"
_STATIC_MESH = "worldStaticMeshNode"
# Placements no node of a new sector can hold one of alone, by the class of their node: a foliage destruction actor
# stands for instances of its sector's foliage, and a foliage or instanced occluder instance is one record of its
# node's resource or buffer.
_UNCOPIED = {
    "worldFoliageDestructionNode": "foliage destruction actors",
    "worldFoliageNode": "foliage instances",
    "worldInstancedOccluderNode": "instanced occluder instances",
}
# The cooked collision shapes that hold one radius across their axes, so a scale that differs between axes would
# reach the game as some other shape.
_ROUND_SHAPES = {
    "PhysicsGeometryCapsuleData": "capsule",
    "PhysicsGeometrySphereData": "sphere",
}
_BOX_SHAPE = "PhysicsGeometryBoxData"
_IDENTITY_TRANSFORM = {
    "$type": "Transform",
    "orientation": {"$type": "Quaternion", "i": 0, "j": 0, "k": 0, "r": 1},
    "position": {"$type": "Vector4", "W": 0, "X": 0, "Y": 0, "Z": 0},
}


@dataclass(frozen=True, slots=True)
class _Copy:
    """One node of a written sector"""

    node: dict
    matrix: Matrix
    instance: NodeInstance | None
    source: ParsedSector | None
    inner_index: int | None = None


class _Sources:
    """The source sectors copies come from and the project they are written into"""

    def __init__(self, sources: Mapping[str, ParsedSector], project: ProjectLayout):
        self.sources = sources
        self.project = project
        self._entries = {}
        self._handles = {}

    def entries(self, source):
        key = source.source_path
        if key not in self._entries:
            self._entries[key] = placed_entries(source)
        return self._entries[key]

    def standalone(self, obj, source, node):
        """A copy of a plain node's Data with the handles it references copied in"""
        key = source.source_path
        if key not in self._handles:
            entries = {id(item.raw_entry): item.raw_entry for item in source.nodes}
            self._handles[key] = HandleIndex.build(list(entries.values()))
        data = self._handles[key].standalone(node.data)
        if _shares_buffer(data):
            raise ValueError(
                f"{obj.name}: its node shares a buffer with another node of {source.sector_name}, which "
                "no other sector can hold; keep it in its sector with its scale cleared, or delete it."
            )
        return data


def _shares_buffer(value) -> bool:
    if isinstance(value, dict):
        return "BufferRefId" in value or any(
            _shares_buffer(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_shares_buffer(item) for item in value)
    return False


def _sector_objects(collection):
    """The objects of a new-sector collection, by name"""
    pending, seen, found = [collection], set(), {}
    while pending:
        current = pending.pop()
        if current.as_pointer() in seen:
            continue
        seen.add(current.as_pointer())
        found.update((obj.as_pointer(), obj) for obj in current.objects)
        pending.extend(
            child for child in current.children if not child.get(NEW_SECTOR_KEY)
        )
    return sorted(found.values(), key=lambda obj: obj.name)


def _copied_records(collection):
    """(object, record) of each copy a new-sector collection holds"""
    records = [
        (obj, placement_record(obj))
        for obj in _sector_objects(collection)
        if "cp77_node_data_index" in obj
    ]
    placing = defaultdict(set)
    for obj, record in records:
        if record is not None and record[2] == "placement":
            placing[record[:2]].add(obj.as_pointer())
    return [
        (obj, record)
        for obj, record in records
        if record is not None
        and not (
            record[2] == "placement"
            and obj.parent is not None
            and obj.parent.as_pointer() in placing[record[:2]]
        )
    ]


def skipped_objects(collection):
    """The objects of a new-sector collection that nothing is written for, by name"""
    copies = {obj.as_pointer() for obj, _record in _copied_records(collection)}

    def written(obj):
        owner = obj
        while owner is not None and owner.as_pointer() not in copies:
            owner = owner.parent
        return owner is not None or any(
            True for _shape in cooked_heightfield_shapes(obj)
        )

    return [obj for obj in _sector_objects(collection) if not written(obj)]


def _plain_data(obj, node, source, sources):
    """The Data of the plain node a placement copy is written as"""
    if node.source_node_type not in COOKED_PLAIN_TYPES:
        data = sources.standalone(obj, source, node)
    elif node.node_type in PLAIN_NODE_FIELDS:
        data = plain_node_data(node.node_type, node.data)
    else:
        raise ValueError(
            f"{obj.name}: {node.source_node_type} placements cannot be written as {node.node_type} "
            "nodes; move it back into its sector or delete it."
        )
    return edited_light_data(data, obj) if node.node_type == _LIGHT else data


def _placed(obj, record, sources):
    """(source sector, node data entry, node) of the placement the copy obj records"""
    sector_name, entry, _kind, _element = record
    source = sources.sources.get(sector_name)
    if source is None:
        raise ValueError(
            f"{obj.name} copies a placement of {sector_name}, but the scene holds no one imported sector "
            "of that name; import it, or delete the copy."
        )
    placed = sources.entries(source).get(entry)
    if placed is None:
        raise ValueError(
            f"{obj.name} copies node data {entry} of {sector_name}, which places nothing in it now; "
            "import the sector again."
        )
    return source, *placed


def _require_scalable(obj, inner, actor, change):
    """Raise ValueError when the collision actor's scale change would give other shapes"""
    if scales_near(change, (change[0],) * 3):
        return
    shapes = collision_actor_shapes(inner, actor)
    classes = {
        nested_dict(shape, "collisionSourceKey").get("$type") for shape in shapes
    }
    rounded = sorted(
        _ROUND_SHAPES[name] for name in classes.intersection(_ROUND_SHAPES)
    )
    if rounded:
        raise ValueError(
            f"{obj.name}: its {' and '.join(rounded)} collision shapes can only be scaled alike on "
            "every axis; scale it evenly."
        )
    for shape in shapes:
        rotation = collision_shape_rotation(inner, shape)
        if (
            nested_dict(shape, "collisionSourceKey").get("$type") == _BOX_SHAPE
            and rotation is not None
            and scale_shears(Quaternion(rotation).normalized().to_matrix(), change)
        ):
            raise ValueError(
                f"{obj.name}: its box collision shapes are turned across its axes, so a scale that "
                "differs along them would shear the boxes, which no box can hold; scale it evenly."
            )


def _collision_copy(obj, record, source, instance, node):
    """The _Copy of the collision actor obj copies"""
    sector_name, entry, _kind, actor_index = record
    if node.source_node_type != _COOKED_COLLISION:
        raise ValueError(
            f"{obj.name}: collision actors of {node.source_node_type} nodes cannot be written into "
            f"another sector (node data {entry} of {sector_name}); keep it in its sector with its scale "
            "cleared, or delete it."
        )
    actors = node.data.get("actors")
    if not isinstance(actors, list) or not 0 <= actor_index < len(actors):
        raise ValueError(
            f"{obj.name} copies actor {actor_index} of node data {entry} of {sector_name}, which holds "
            "no such actor now; import the sector again."
        )
    actor = actors[actor_index]
    scale, change = collision_actor_scale(node.data, actor), scale_change(obj)
    if change is not None:
        _require_scalable(obj, node.data, actor, change)
        scale = tuple(
            value * factor for value, factor in zip(scale or (1.0, 1.0, 1.0), change)
        )
    position, orientation, _scale = transform_values(object_world_matrix(obj))
    half = vector3_from_data(node.data.get("extents"), (0.0, 0.0, 0.0))
    bounds = instance_matrix(instance) @ Matrix.Diagonal(Vector(half)).to_4x4()
    centre, extents = box_around(
        placement_matrix(obj, bounds) if "cp77_matrix" in obj else bounds
    )
    try:
        data = one_actor_collision_node(
            node.raw_entry["Data"],
            node.inner_index,
            actor_index,
            position=position,
            orientation=orientation,
            scale=scale,
            extents=tuple(extents),
        )
    except ValueError as error:
        raise ValueError(
            f"{obj.name} (node data {entry} of {sector_name}): {error}."
        ) from error
    return _Copy(
        {"HandleId": node.handle_id, "Data": data},
        Matrix.Translation(Vector(centre)),
        instance,
        source,
        inner_index=0,
    )


def _copied_node(obj, record, sources):
    """The _Copy of a copied placement, instance or actor, or None for a heightfield"""
    sector_name, entry, kind, _element = record
    source, instance, node = _placed(obj, record, sources)
    if node.node_type == _HEIGHTFIELD:
        return None
    what = _UNCOPIED.get(node.node_type)
    if what is not None:
        raise ValueError(
            f"{obj.name}: {what} cannot be copied into a new sector (node data {entry} of "
            f"{sector_name}); move it back into its sector or delete it."
        )
    if kind == "actor":
        return _collision_copy(obj, record, source, instance, node)
    if kind == "element" and node.node_type == _INSTANCED_MESH:
        data, matrix = (
            plain_node_data(_STATIC_MESH, node.data),
            object_world_matrix(obj),
        )
    elif kind == "element" and node.node_type == _DESTRUCTIBLE:
        # The copy holds the one instance where its entry stands.
        data = sources.standalone(obj, source, node)
        data["instanceTransforms"] = [copy.deepcopy(_IDENTITY_TRANSFORM)]
        matrix = object_world_matrix(obj)
    else:
        data, matrix = (
            _plain_data(obj, node, source, sources),
            placement_matrix(obj, instance_matrix(instance)),
        )
    _require_reachable(obj, data, source, sources.project)
    return _Copy({"HandleId": node.handle_id, "Data": data}, matrix, instance, source)


def _terrain_entry(obj, sources):
    """(node data entry, sector) of the imported terrain collision the copy obj records"""
    record = placement_record(obj) if "cp77_node_data_index" in obj else None
    if record is None:
        return None, None
    source, instance, node = _placed(obj, record, sources)
    return (instance, source) if node.node_type == _HEIGHTFIELD else (None, None)


def _heightfield_copies(collection, sources):
    """The _Copy of each cooked heightfield shape a new-sector collection holds"""
    copies = []
    for obj in _sector_objects(collection):
        shapes = tuple(cooked_heightfield_shapes(obj))
        instance, source = _terrain_entry(obj, sources) if shapes else (None, None)
        for shape in shapes:
            node, matrix = terrain_collision_node(obj, shape)
            copies.append(_Copy(node, matrix, instance, source))
    return copies


def _require_reachable(obj, data, source, project: ProjectLayout):
    """Raise ValueError when the copy obj names a resource only its source sector embeds"""
    embedded = {depot_path_key(path) for path in source.local_inplace_paths}
    for path in resource_depot_paths(data) if embedded else ():
        if depot_path_key(path) in embedded and not os.path.isfile(
            project.archive_file(path)
        ):
            raise ValueError(
                f"{obj.name}: {path} is embedded in {source.sector_name} and is not a file of the "
                "project's source/archive, so no other sector can reach it; add it to the project, or "
                "keep the object in its sector with its scale cleared."
            )


def _depot_path(project: ProjectLayout, name):
    if not project.name:
        raise ValueError(
            f"{project.root} has no .cpmodproj to name the folder of its new sectors."
        )
    if not is_plain_file_name(name):
        raise ValueError(
            f"{name}: a new sector is written to a file of its name, which cannot hold / \\ or :; "
            "rename it."
        )
    return f"{project.name}\\{name}.streamingsector"


def _inplace_resource(owner, copies):
    """The inplace resource the sector of copies names, or None"""
    named = {}
    for item in copies:
        path = (
            resource_path_text(item.instance.raw.get("externalInplaceResourceHash"))
            if item.instance
            else None
        )
        if path:
            named.setdefault(depot_path_key(path), (path, item.source))
    if not named:
        return None
    if len(named) > 1:
        (_path, first), (_other, second) = list(named.values())[:2]
        raise ValueError(
            f"{owner} holds copies whose resources lie in the inplace resources of {first.sector_name} "
            f"and {second.sector_name}, but a sector names one; move the copies of one of them into "
            "another new sector."
        )
    ((path, source),) = named.values()
    if depot_path_key(
        resource_path_text(source.extern_inplace_resource)
    ) != depot_path_key(path):
        raise ValueError(
            f"{source.source_path} does not name the inplace resource {path} that its node data names; "
            "export the sector again from the game."
        )
    return source.extern_inplace_resource


def _global_node_ids(owner, copies, depot_path):
    """The global node id of each copy"""
    occurrences, ids = Counter(), []
    for item in copies:
        if item.source is None:
            ids.append(0)
            continue
        original = (item.source.source_path, item.instance.index)
        ids.append(
            copied_global_node_id(item.instance.raw, depot_path, occurrences[original])
        )
        occurrences[original] += 1
    sources = {
        item.source.source_path: item.source
        for item in copies
        if item.source is not None
    }.values()
    taken = {
        entry_global_node_id(instance.raw)
        for source in sources
        for instance in source.instances
    }
    made = [value for value in ids if value]
    if len(set(made)) != len(made) or taken.intersection(made):
        raise ValueError(
            f"{owner}: two of its copies, or a copy and a node of its source sector, would share a global "
            "node id; rename the new sector."
        )
    return ids


def _written(
    copies, owner, depot_path, category, project: ProjectLayout
) -> tuple[str, SectorDescriptor]:
    """The sector of copies as JSON text, and its descriptor"""
    entries, placements = [], []
    for index, (item, global_node_id) in enumerate(
        zip(copies, _global_node_ids(owner, copies, depot_path))
    ):
        values = transform_values(item.matrix)
        if item.instance is None:
            distance, entry = TERRAIN_STREAMING_DISTANCE, None
        else:
            distance = item.instance.streaming_distance
            entry = copied_entry_source(
                item.instance.raw, global_node_id=global_node_id
            )
        entries.append(
            node_instance_entry(
                index,
                values,
                streaming_distance=distance,
                source=entry,
                inner_index=item.inner_index,
            )
        )
        placements.append((values[0], distance))
    document = streaming_sector_document(
        [item.node for item in copies],
        entries,
        category=category,
        archive_file_name=project.archive_file(depot_path),
        extern_inplace_resource=_inplace_resource(owner, copies),
    )
    return styled_dumps(document, JsonStyle()), SectorDescriptor(
        depot_path, category, streaming_box(placements)
    )


def _category(source: ParsedSector) -> str:
    return str(source.category or "") or _DEFAULT_CATEGORY


def write_new_sector(
    collection,
    sources: Mapping[str, ParsedSector],
    project: ProjectLayout,
    *,
    include_heightfields: bool,
) -> tuple[str, SectorDescriptor] | None:
    """A new-sector collection as a patch 2.5 sector, or None when nothing is written"""
    entries = _Sources(sources, project)
    copies = [
        item
        for item in (
            _copied_node(obj, record, entries)
            for obj, record in _copied_records(collection)
        )
        if item is not None
    ]
    if include_heightfields:
        copies.extend(_heightfield_copies(collection, entries))
    if not copies:
        return None
    by_path = {
        item.source.source_path: item.source
        for item in copies
        if item.source is not None
    }
    counts = Counter(
        item.source.source_path for item in copies if item.source is not None
    )
    category = (
        _category(by_path[counts.most_common(1)[0][0]]) if counts else _DEFAULT_CATEGORY
    )
    return _written(
        copies,
        collection.name,
        _depot_path(project, collection.name),
        category,
        project,
    )


def write_generated_sector(
    source_name: str, objects, source: ParsedSector, project, suffix: str
) -> tuple[str, SectorDescriptor]:
    """The objects the export deletes from source for a copy, as a patch 2.5 sector"""
    entries = _Sources({source_name: source}, project)
    copies = [
        _copied_node(obj, (source_name, *placement_record(obj)[1:]), entries)
        for obj in objects
    ]
    stem, extension = ntpath.splitext(source_name)
    name = (
        f"{stem if extension.casefold() == _SECTOR_EXTENSION else source_name}{suffix}"
    )
    return _written(
        copies, name, _depot_path(project, name), _category(source), project
    )
