from __future__ import annotations

import os

import bpy

from ...assetio.archive_xl import (
    ActorMutation,
    InstanceMutation,
    NodeDeletion,
    NodeMutation,
    SectorEdits,
)
from ...assetio.paths import strip_json_suffix
from ...assetio.streaming_sector import destructible_transforms, transform_range
from ...assetio.values import coerce_int, json_array, json_object
from ...bartmoss.matrix import placements_near
from ...blender.matrix import instance_matrix
from ...entity.domain.lights import light_settings_changed, static_light_settings
from ...importers.common.light_channels import stored_light_channel_records
from .buffers import ScenePlacements, sector_depot_path
from .transforms import moved_matrix, moved_placement, scale_change, transform_values

_COLLISION = "worldCollisionNode"
_DESTRUCTIBLE = "worldInstancedDestructibleMeshNode"
_FOLIAGE = "worldFoliageNode"
_INSTANCED_MESH = "worldInstancedMeshNode"
_LIGHT = "worldStaticLightNode"
_OCCLUDER = "worldInstancedOccluderNode"
_TERRAIN_COLLISION = "worldTerrainCollisionNode"


def placed_entries(source) -> dict:
    """Each node data entry of source that places a node, by index"""
    return {
        instance.index: (instance, node)
        for node in source.nodes
        for instance in node.instances
    }


def _apart(entry, node, count, what):
    return (
        f"node data {entry} ({node.source_node_type}) is placed by {count} {what} that do not match; keep one "
        "and move the others into a new sector."
    )


def _joint(matrices, problem):
    """The one matrix matrices agree on, or None while none moved"""
    if all(matrix is None for matrix in matrices):
        return None
    first = matrices[0]
    if any(matrix is None or not placements_near(matrix, first) for matrix in matrices):
        raise ValueError(problem)
    return first


def _edited_light(entry, node, roots):
    """The light of a light entry whose game settings differ from its node's, or None"""
    settings = static_light_settings(node.data)
    edited = [root for root in roots if light_settings_changed(root, settings)]
    if edited and len(roots) > 1:
        raise ValueError(_apart(entry, node, len(roots), "lights"))
    return edited[0] if edited else None


def edited_lights(collection, source, placements=None) -> tuple[bpy.types.Object, ...]:
    """The lights of an imported sector collection whose game settings differ from their node's"""
    if placements is None:
        placements = ScenePlacements(bpy.context.scene)
    index = placements.index(collection)
    found = (
        _edited_light(entry, node, index.roots.get(entry, ()))
        for entry, (_instance, node) in sorted(placed_entries(source).items())
        if node.node_type == _LIGHT
    )
    return tuple(light for light in found if light is not None)


class _SectorHoldings:
    """What the scene holds of one imported sector"""

    def __init__(self, collection, source, placements):
        self.name = source.sector_name
        self.index = placements.index(collection)
        self.placements = placements
        recorded = collection.get("cp77_imported_node_data")
        # An entry-less occluder records -1.
        self.imported = (
            frozenset(
                index
                for index in (coerce_int(value, -1) for value in json_array(recorded))
                if index >= 0
            )
            if isinstance(recorded, str)
            else frozenset()
        )
        recorded = collection.get("cp77_imported_collision_actors")
        self.imported_actors = (
            {
                coerce_int(entry, -1): frozenset(
                    coerce_int(actor, -1) for actor in actors
                )
                for entry, actors in json_object(recorded).items()
            }
            if isinstance(recorded, str)
            else {}
        )
        self.recorded_nodes = frozenset(
            coerce_int(record["node_index"], -1)
            for record in stored_light_channel_records((collection,))
            if not record["component"]
            and record["node_index"] is not None
            and record["sector_name"] in ("", self.name)
        )

    def holds(self, entry, node):
        return (
            entry in self.index.held
            or (self.name, entry) in self.placements.copy_entries
            or node.index in self.recorded_nodes
        )

    def held_elements(self, entry):
        return set(
            self.index.elements.get(entry, ())
        ) | self.placements.copy_elements.get((self.name, entry), set())

    def holds_actor(self, entry, actor):
        return actor in self.index.actors.get(
            entry, ()
        ) or actor in self.placements.copy_actors.get((self.name, entry), ())


def _instances(node):
    """(placed instances, node instance count) of an instanced mesh or destructible node"""
    if node.source_node_type == _INSTANCED_MESH:
        span = transform_range(node.raw_entry.get("Data"), node.inner_index)
        return (tuple(range(len(span))), len(span)) if span is not None else ((), 0)
    items = destructible_transforms(node.data)
    return tuple(index for index, item in enumerate(items) if item is not None), len(
        items
    )


def _item_moves(entry, node, index):
    """The moved actors or instances of a collision or instanced entry"""
    if node.node_type == _COLLISION:
        items, what = index.actors.get(entry, {}), "objects per actor"
    else:
        items, what = index.elements.get(entry, {}), "objects per instance"
    moves = []
    for item, objects in sorted(items.items()):
        moved = _joint(
            [moved_matrix(obj) for obj in objects],
            _apart(entry, node, len(objects), what),
        )
        if moved is not None:
            moves.append((item, moved, objects[0]))
    return moves


def _scaled(node, obj):
    """Whether obj was scaled where ArchiveXL cannot scale it"""
    return node.source_node_type != _INSTANCED_MESH and scale_change(obj) is not None


def _instance_edits(entry, node, holdings):
    """The edits of an instanced mesh or destructible entry"""
    node_type = node.source_node_type
    placed, count = _instances(node)
    if count <= 0:
        return None, None
    deleted = set()
    if entry in holdings.imported:
        held = holdings.held_elements(entry)
        missing = tuple(element for element in placed if element not in held)
        # An item the import skipped is never deleted, so the entry goes only when it holds no other.
        if len(missing) == count:
            return NodeDeletion(entry, node_type), None
        deleted.update(missing)
    moves = []
    for element, now, obj in _item_moves(entry, node, holdings.index):
        if _scaled(node, obj):
            deleted.add(element)
            continue
        position, orientation, scale = transform_values(now)
        # A destructible's instances take the entry's scale.
        moves.append(
            InstanceMutation(
                element,
                position,
                orientation,
                scale if node_type == _INSTANCED_MESH else None,
            )
        )
    deletion = (
        NodeDeletion(
            entry,
            node_type,
            instance_deletions=tuple(sorted(deleted)),
            expected_instances=count,
        )
        if deleted
        else None
    )
    mutation = (
        NodeMutation(
            entry, node_type, instance_mutations=tuple(moves), expected_instances=count
        )
        if moves
        else None
    )
    return deletion, mutation


def _actor_edits(entry, node, holdings):
    """The edits of a collision entry"""
    node_type, count = node.source_node_type, coerce_int(node.data.get("numActors"), 0)
    deleted = {
        actor
        for actor in holdings.imported_actors.get(entry, ())
        if actor >= 0 and not holdings.holds_actor(entry, actor)
    }
    moves = []
    for actor, now, obj in _item_moves(entry, node, holdings.index):
        if _scaled(node, obj):
            deleted.add(actor)
            continue
        position, orientation, _scale = transform_values(now)
        moves.append(ActorMutation(actor, position, orientation))
    deletion = (
        NodeDeletion(
            entry,
            node_type,
            actor_deletions=tuple(sorted(deleted)),
            expected_actors=count,
        )
        if deleted
        else None
    )
    mutation = (
        NodeMutation(
            entry, node_type, actor_mutations=tuple(moves), expected_actors=count
        )
        if moves
        else None
    )
    return deletion, mutation


def scaled_objects(collection, source, placements=None) -> tuple[bpy.types.Object, ...]:
    """The objects of an imported sector collection whose collision actor or instance scale changed"""
    if placements is None:
        placements = ScenePlacements(bpy.context.scene)
    index = placements.index(collection)
    found = []
    for entry, (_instance, node) in sorted(placed_entries(source).items()):
        if node.node_type == _COLLISION or node.source_node_type == _DESTRUCTIBLE:
            found.extend(
                obj
                for _item, _now, obj in _item_moves(entry, node, index)
                if _scaled(node, obj)
            )
    return tuple(found)


def _group_edits(entry, instance, node, holdings):
    """The edits of a foliage or instanced occluder entry"""
    node_type, held = node.source_node_type, holdings.held_elements(entry)
    if entry in holdings.imported:
        if not held:
            return NodeDeletion(entry, node_type), None
        if len(held) < holdings.index.counts.get(entry, 0):
            raise ValueError(
                f"some instances of node data {entry} ({node_type}) were deleted, which ArchiveXL cannot "
                "write; delete all of them or none."
            )
    objects = [
        obj
        for _element, items in sorted(holdings.index.elements.get(entry, {}).items())
        for obj in items
    ]
    if node.node_type == _OCCLUDER:
        if any(moved_matrix(obj) is not None for obj in objects):
            raise ValueError(
                f"node data {entry} ({node_type}) cannot be moved, only deleted; put its instances back "
                "where they were."
            )
        return None, None
    placement = _joint(
        [moved_placement(obj, instance_matrix(instance)) for obj in objects],
        (
            f"the instances of node data {entry} ({node_type}) move only together; move all of them as one or put them "
            "back where they were."
        ),
    )
    return None, None if placement is None else NodeMutation(
        entry, node_type, *transform_values(placement)
    )


def _placement_edits(entry, instance, node, holdings):
    """The edits of any other entry"""
    node_type = node.source_node_type
    if entry in holdings.imported and not holdings.holds(entry, node):
        return NodeDeletion(entry, node_type), None
    roots = holdings.index.roots.get(entry, ())
    placement = _joint(
        [moved_placement(root, instance_matrix(instance)) for root in roots],
        _apart(entry, node, len(roots), "objects"),
    )
    if node.node_type == _LIGHT and _edited_light(entry, node, roots) is not None:
        return NodeDeletion(entry, node_type), None
    if placement is None:
        return None, None
    if node.node_type == _TERRAIN_COLLISION:
        # Its actor stands where the node puts it, which an entry's mutation does not change.
        raise ValueError(
            f"node data {entry} ({node_type}) cannot be moved, only deleted; put it back where it was."
        )
    return None, NodeMutation(entry, node_type, *transform_values(placement))


def sector_edits(collection, source, placements=None) -> SectorEdits:
    """The ArchiveXL edits of an imported sector collection against its source"""
    expected = coerce_int(collection.get("expectedNodes"), source.node_data_count)
    if expected != source.node_data_count:
        raise ValueError(
            f"{source.source_path}: the sector holds {source.node_data_count} node data entries but held "
            f"{expected} when it was imported; import it again before exporting its edits."
        )
    if placements is None:
        placements = ScenePlacements(bpy.context.scene)
    deletions, mutations = [], []
    try:
        holdings = _SectorHoldings(collection, source, placements)
        for entry, (instance, node) in sorted(placed_entries(source).items()):
            if node.node_type == _COLLISION:
                deletion, mutation = _actor_edits(entry, node, holdings)
            elif node.source_node_type in (_INSTANCED_MESH, _DESTRUCTIBLE):
                deletion, mutation = _instance_edits(entry, node, holdings)
            elif node.node_type in (_FOLIAGE, _OCCLUDER):
                deletion, mutation = _group_edits(entry, instance, node, holdings)
            else:
                deletion, mutation = _placement_edits(entry, instance, node, holdings)
            if deletion is not None:
                deletions.append(deletion)
            if mutation is not None:
                mutations.append(mutation)
    except ValueError as error:
        raise ValueError(f"{source.source_path}: {error}") from error
    path = sector_depot_path(source.source_path)
    if path is None:
        if deletions or mutations:
            raise ValueError(
                f"{source.source_path}: the sector lies outside a project's source/raw, so its depot path "
                "is unknown; import it from its project."
            )
        path = strip_json_suffix(os.path.basename(source.source_path))
    return SectorEdits(path, source.node_data_count, tuple(deletions), tuple(mutations))
