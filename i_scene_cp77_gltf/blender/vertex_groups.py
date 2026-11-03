from __future__ import annotations

from dataclasses import dataclass


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
