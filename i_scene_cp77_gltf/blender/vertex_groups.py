from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from mathutils.kdtree import KDTree

from ..gltf.mesh_contract import SKIN_WEIGHT_EPSILON


@dataclass(frozen=True)
class VertexGroupSnapshot:
    groups: tuple[tuple[str, bool], ...]
    # Per group, the vertex indices at each weight.
    weights: tuple[dict[float, list[int]], ...]
    active_index: int


def capture_vertex_groups(obj) -> VertexGroupSnapshot:
    groups = tuple((group.name, bool(group.lock_weight)) for group in obj.vertex_groups)
    weights = tuple({} for _group in groups)
    # Reading vertex weights on a mesh without groups corrupts memory in Blender 5.0.0, so a groupless mesh is not read.
    if groups:
        for vertex in obj.data.vertices:
            for element in vertex.groups:
                if 0 <= element.group < len(weights):
                    weights[element.group].setdefault(float(element.weight), []).append(
                        vertex.index
                    )
    return VertexGroupSnapshot(groups, weights, int(obj.vertex_groups.active_index))


def restore_vertex_groups(obj, snapshot: VertexGroupSnapshot) -> None:
    obj.vertex_groups.clear()
    for (name, locked), by_weight in zip(snapshot.groups, snapshot.weights):
        group = obj.vertex_groups.new(name=name)
        for weight, indices in by_weight.items():
            group.add(indices, weight, "REPLACE")
        group.lock_weight = locked
    if snapshot.groups:
        obj.vertex_groups.active_index = min(
            max(0, snapshot.active_index), len(snapshot.groups) - 1
        )


def vertex_weights(obj, groups=None):
    """Each vertex's group index and weight pairs above SKIN_WEIGHT_EPSILON, of the group indices groups when given"""
    # Reading vertex weights on a mesh without groups corrupts memory in Blender 5.0.0, so a groupless mesh is not read.
    if not obj.vertex_groups:
        return [()] * len(obj.data.vertices)
    return [
        tuple(
            (element.group, element.weight)
            for element in vertex.groups
            if element.weight > SKIN_WEIGHT_EPSILON
            and (groups is None or element.group in groups)
        )
        for vertex in obj.data.vertices
    ]


def _set_weights(obj, updates):
    for (group, weight), indices in updates.items():
        obj.vertex_groups[group].add(indices, weight, "REPLACE")


def give_nearest_weights(obj, indices, groups=None):
    """Give the vertices indices the normalized weights of the nearest other vertex weighted in groups, returning how many got them"""
    weights = vertex_weights(obj, groups)
    targets = sorted(set(indices))
    chosen = set(targets)
    sources = [
        index
        for index, entries in enumerate(weights)
        if entries and index not in chosen
    ]
    if not targets or not sources:
        return 0
    vertices = obj.data.vertices
    tree = KDTree(len(sources))
    for index in sources:
        tree.insert(vertices[index].co, index)
    tree.balance()
    updates = defaultdict(list)
    for index in targets:
        entries = weights[tree.find(vertices[index].co)[1]]
        total = sum(weight for _group, weight in entries)
        for group, weight in entries:
            updates[group, weight / total].append(index)
    _set_weights(obj, updates)
    return len(targets)


def normalize_vertex_weights(obj, indices, groups=None):
    """Scale the weights in groups of the vertices indices to sum to one, returning how many changed"""
    weights = vertex_weights(obj, groups)
    updates = defaultdict(list)
    changed = 0
    for index in sorted(set(indices)):
        entries = weights[index]
        total = sum(weight for _group, weight in entries)
        if not entries or abs(total - 1.0) <= 1e-6:
            continue
        for group, weight in entries:
            updates[group, weight / total].append(index)
        changed += 1
    _set_weights(obj, updates)
    return changed
