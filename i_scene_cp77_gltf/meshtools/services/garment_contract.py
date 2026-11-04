from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from ...bartmoss.geometry import triangle_area_squared
from ...gltf.garment_support import GARMENT_CAP_ATTRIBUTE, GARMENT_WEIGHT_ATTRIBUTE

GARMENT_ATTRIBUTE_DOMAIN = "POINT"
GARMENT_ATTRIBUTE_TYPE = "BYTE_COLOR"
GARMENT_ATTRIBUTE_DEFAULTS = {
    GARMENT_WEIGHT_ATTRIBUTE: (1.0, 0.0, 0.0, 1.0),
    GARMENT_CAP_ATTRIBUTE: (0.0, 0.0, 0.0, 1.0),
}


@dataclass(frozen=True, slots=True)
class NativeClothFeatures:
    triangle_collision: bool
    motion_constraints: bool
    separation_constraints: bool
    continuous_collision: bool
    collision_mass_scale: bool

    @property
    def constraint_summary(self):
        parts = ["hard pins"]
        if self.motion_constraints:
            parts.append("motion")
        if self.separation_constraints:
            parts.append("separation")
        return " + ".join(parts)


@dataclass(frozen=True, slots=True)
class TopologyAudit:
    vertex_count: int
    triangle_count: int
    boundary_edge_count: int
    component_count: int
    isolated_vertex_count: int
    degenerate_triangle_count: int
    duplicate_triangle_count: int
    nonmanifold_edge_count: int
    coincident_boundary_pair_count: int
    nonfinite_vertex_count: int
    invalid_index_count: int


def native_cloth_features(method_names) -> NativeClothFeatures:
    names = frozenset(method_names)
    return NativeClothFeatures(
        triangle_collision="nvcloth_set_triangles" in names,
        motion_constraints="nvcloth_set_motion_constraints" in names,
        separation_constraints="nvcloth_set_separation_constraints" in names,
        continuous_collision="nvcloth_enable_continuous_collision" in names,
        collision_mass_scale="nvcloth_set_collision_mass_scale" in names,
    )


def audit_topology(vertices, triangles, *, tolerance=1.0e-6) -> TopologyAudit:
    positions = [tuple(map(float, vertex[:3])) for vertex in vertices]
    finite_positions = [
        all(math.isfinite(value) for value in position) for position in positions
    ]
    vertex_count = len(positions)
    parent = list(range(vertex_count))
    used = set()
    edges = {}
    triangle_keys = set()
    duplicate_triangles = 0
    degenerate_triangles = 0
    invalid_indices = 0

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(a, b):
        root_a = find(a)
        root_b = find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    valid_triangle_count = 0
    for raw_triangle in triangles:
        if len(raw_triangle) != 3:
            invalid_indices += len(raw_triangle) or 1
            continue
        triangle = tuple(map(int, raw_triangle))
        triangle_invalid_indices = sum(
            index < 0 or index >= vertex_count for index in triangle
        )
        invalid_indices += triangle_invalid_indices
        if triangle_invalid_indices:
            continue
        valid_triangle_count += 1
        key = tuple(sorted(triangle))
        if key in triangle_keys:
            duplicate_triangles += 1
        else:
            triangle_keys.add(key)
        a, b, c = triangle
        if (a == b or b == c or c == a) or triangle_area_squared(
            positions[a], positions[b], positions[c]
        ) <= tolerance**4:
            degenerate_triangles += 1
        used.update(triangle)
        union(a, b)
        union(b, c)
        for edge in ((a, b), (b, c), (c, a)):
            edge = edge if edge[0] <= edge[1] else (edge[1], edge[0])
            edges[edge] = edges.get(edge, 0) + 1

    boundary_vertices = set()
    boundary_edge_count = 0
    nonmanifold_edge_count = 0
    for edge, count in edges.items():
        if count == 1:
            boundary_edge_count += 1
            boundary_vertices.update(edge)
        elif count > 2:
            nonmanifold_edge_count += 1

    components = {find(index) for index in used}
    isolated = vertex_count - len(used)
    if isolated:
        components.update(index for index in range(vertex_count) if index not in used)

    nonfinite = finite_positions.count(False)
    coincident_pairs = 0
    if tolerance > 0.0 and boundary_vertices:
        buckets = {}
        tolerance_squared = tolerance * tolerance
        for index in sorted(boundary_vertices):
            position = positions[index]
            if not finite_positions[index]:
                continue
            cell = tuple(int(math.floor(value / tolerance)) for value in position)
            for x in range(cell[0] - 1, cell[0] + 2):
                for y in range(cell[1] - 1, cell[1] + 2):
                    for z in range(cell[2] - 1, cell[2] + 2):
                        for other in buckets.get((x, y, z), ()):
                            other_position = positions[other]
                            distance_squared = sum(
                                (position[axis] - other_position[axis]) ** 2
                                for axis in range(3)
                            )
                            if distance_squared <= tolerance_squared:
                                coincident_pairs += 1
            buckets.setdefault(cell, []).append(index)

    return TopologyAudit(
        vertex_count=vertex_count,
        triangle_count=valid_triangle_count,
        boundary_edge_count=boundary_edge_count,
        component_count=len(components),
        isolated_vertex_count=isolated,
        degenerate_triangle_count=degenerate_triangles,
        duplicate_triangle_count=duplicate_triangles,
        nonmanifold_edge_count=nonmanifold_edge_count,
        coincident_boundary_pair_count=coincident_pairs,
        nonfinite_vertex_count=nonfinite,
        invalid_index_count=invalid_indices,
    )


def preparation_signature(payload) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.blake2b(
        encoded,
        digest_size=16,
        person=b"CP77GarmentPrep",
    ).hexdigest()
