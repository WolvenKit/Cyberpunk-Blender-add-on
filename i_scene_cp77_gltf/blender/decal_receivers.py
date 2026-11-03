from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from ..bartmoss.uv import triangle_uv_densities, triangle_uv_transfer
from .mesh import PREVIEW_ONLY_FLAG, is_preview_only_modifier
from .morphs import mesh_corner_frame
from .transactions import track_created_datablock

RECEIVER_UV_ATTRIBUTE_PREFIX = "CP77_ReceiverUV_"
RECEIVER_ATTRIBUTE = "CP77_DecalReceiver"
DECAL_SLOT_ATTRIBUTE = "CP77_DecalReceiverSlot"
PREVIEW_MODIFIER_NAME = "CP77 Decal Receiver Preview"
_PREVIEW_GROUP_PREFIX = "CP77 Decal Receiver Preview v1"
_FACE_NUDGE = 1.0e-3
# Receiver votes sample a face about every 5 cm (object space), at most 8 steps from its centre to each edge.
_VOTE_SPACING = 0.05
_VOTE_MAX_STEPS = 8
# Largest corner UV deviation from the face anchor's mapping, as a fraction of the face's UV extent.
_SEAM_TOLERANCE = 0.5


@dataclass(frozen=True, slots=True)
class DecalReceiverBinding:
    """The receiver under each decal face and the receiver UV layer names"""

    face_receivers: np.ndarray
    uv_layers: tuple


@dataclass(frozen=True, slots=True)
class _ReceiverTriangles:
    tree: BVHTree
    points: np.ndarray
    triangles: np.ndarray
    triangle_loops: np.ndarray
    triangle_receiver: np.ndarray
    receiver_uvs: tuple
    receiver_trees: tuple


def receiver_uv_attribute(layer_name):
    return RECEIVER_UV_ATTRIBUTE_PREFIX + layer_name


def receiver_uv_layers(mesh):
    """The receiver UV layer names a bound decal mesh carries"""
    prefix = RECEIVER_UV_ATTRIBUTE_PREFIX
    return tuple(
        attribute.name[len(prefix) :]
        for attribute in mesh.attributes
        if attribute.name.startswith(prefix)
    )


def _receiver_triangles(decal, receivers):
    """All receiver triangles in the decal's object space, with a tree per receiver"""
    to_decal = decal.matrix_world.inverted_safe()
    points, triangles, triangle_loops, owners = [], [], [], []
    receiver_uvs = [{} for _ in receivers]
    receiver_trees = [None for _ in receivers]
    point_offset = triangle_offset = 0
    for receiver_index, receiver in enumerate(receivers):
        mesh = receiver.data
        if not len(mesh.polygons):
            continue
        mesh.calc_loop_triangles()
        count = len(mesh.loop_triangles)
        if not count:
            continue
        coordinates = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
        mesh.vertices.foreach_get("co", coordinates)
        matrix = np.array(to_decal @ receiver.matrix_world, dtype=np.float64)
        coordinates = coordinates.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3]
        vertices = np.empty(count * 3, dtype=np.int64)
        mesh.loop_triangles.foreach_get("vertices", vertices)
        loops = np.empty(count * 3, dtype=np.int64)
        mesh.loop_triangles.foreach_get("loops", loops)
        layer_values = {}
        for layer in mesh.uv_layers:
            values = np.empty(len(mesh.loops) * 2, dtype=np.float64)
            layer.uv.foreach_get("vector", values)
            layer_values[layer.name] = values.reshape(-1, 2)
        vertices = vertices.reshape(-1, 3)
        local_tree = BVHTree.FromPolygons(
            coordinates.tolist(), vertices.tolist(), all_triangles=True
        )
        points.append(coordinates)
        triangles.append(vertices + point_offset)
        triangle_loops.append(loops.reshape(-1, 3))
        owners.append(np.full(count, receiver_index, dtype=np.int64))
        receiver_uvs[receiver_index] = layer_values
        receiver_trees[receiver_index] = (local_tree, triangle_offset)
        point_offset += len(coordinates)
        triangle_offset += count
    if not triangles:
        return None
    points = np.concatenate(points)
    triangles = np.concatenate(triangles)
    tree = BVHTree.FromPolygons(points.tolist(), triangles.tolist(), all_triangles=True)
    return _ReceiverTriangles(
        tree,
        points,
        triangles,
        np.concatenate(triangle_loops),
        np.concatenate(owners),
        tuple(receiver_uvs),
        tuple(receiver_trees),
    )


def _closest_hit(tree, point, directions, max_distance):
    """The triangle hit from point along directions, else the nearest one within reach"""
    best = None
    for direction in directions:
        _location, _normal, index, distance = tree.ray_cast(
            point, direction, max_distance
        )
        if index is not None and (best is None or distance < best[1]):
            best = (index, distance)
    if best is None:
        _location, _normal, index, distance = tree.find_nearest(point, max_distance)
        if index is not None:
            best = (index, distance)
    return best


def _face_samples(center, corners, extent):
    """Points spread evenly over a face"""
    steps = min(_VOTE_MAX_STEPS, max(1, math.ceil(extent / _VOTE_SPACING)))
    samples = []
    for first, second in zip(corners, (*corners[1:], corners[0])):
        for i in range(steps + 1):
            for j in range(steps + 1 - i):
                point = (
                    center
                    + (first - center) * (i / steps)
                    + (second - center) * (j / steps)
                )
                samples.append(point + (center - point) * _FACE_NUDGE)
    return samples


def _sample_receiver_uvs(
    receiver_data,
    receiver,
    corners,
    corner_triangles,
    anchors,
    positions,
    extents,
    corner_uvs,
):
    """Write the receiver's UVs at the given decal corners"""
    layers = receiver_data.receiver_uvs[receiver]
    if not layers:
        return
    surface = (
        receiver_data.points,
        receiver_data.triangles,
        receiver_data.triangle_loops,
    )
    sampled, sampled_valid = triangle_uv_transfer(
        *surface, layers, corner_triangles, positions
    )
    extended, extended_valid = triangle_uv_transfer(
        *surface, layers, anchors, positions
    )
    densities = triangle_uv_densities(*surface, next(iter(layers.values())), anchors)
    tolerances = _SEAM_TOLERANCE * densities * extents + 1.0e-4
    deviations = np.max(
        [np.linalg.norm(sampled[name] - extended[name], axis=1) for name in layers],
        axis=0,
    )
    use_anchor = (corner_triangles != anchors) & (
        ~sampled_valid | (extended_valid & (deviations > tolerances))
    )
    written = np.where(use_anchor, extended_valid, sampled_valid)
    for name in layers:
        values = np.where(use_anchor[:, None], extended[name], sampled[name])
        corner_uvs[name][corners[written], :2] = values[written]


def bind_decal_receivers(
    decal, receivers, *, frame_attributes, max_distance=0.03, surfaces=None
):
    """Bind each face of decal to the receiver surface beneath it"""
    mesh = decal.data
    if not receivers or not len(mesh.polygons) or not len(mesh.uv_layers):
        return None
    key = (
        tuple(receiver.as_pointer() for receiver in receivers),
        tuple(map(tuple, decal.matrix_world)),
    )
    receiver_data = surfaces.get(key) if surfaces is not None else None
    if receiver_data is None:
        receiver_data = _receiver_triangles(decal, receivers)
        if surfaces is not None:
            surfaces[key] = receiver_data
    if receiver_data is None:
        return None

    coordinates = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
    mesh.vertices.foreach_get("co", coordinates)
    coordinates = coordinates.reshape(-1, 3)
    loop_vertices = np.empty(len(mesh.loops), dtype=np.int64)
    mesh.loops.foreach_get("vertex_index", loop_vertices)
    centers = np.empty(len(mesh.polygons) * 3, dtype=np.float64)
    mesh.polygons.foreach_get("center", centers)
    centers = centers.reshape(-1, 3)
    normals = np.empty(len(mesh.polygons) * 3, dtype=np.float64)
    mesh.polygons.foreach_get("normal", normals)
    normals = normals.reshape(-1, 3)
    loop_starts = np.empty(len(mesh.polygons), dtype=np.int64)
    mesh.polygons.foreach_get("loop_start", loop_starts)
    loop_totals = np.empty(len(mesh.polygons), dtype=np.int64)
    mesh.polygons.foreach_get("loop_total", loop_totals)

    layer_names = tuple(
        dict.fromkeys(name for uvs in receiver_data.receiver_uvs for name in uvs)
    )
    corner_uvs = {
        name: np.zeros((len(mesh.loops), 3), dtype=np.float32) for name in layer_names
    }
    face_receivers = np.full(len(mesh.polygons), -1, dtype=np.int64)
    # A face's corners are its contiguous run of loops.
    loop_faces = np.repeat(np.arange(len(mesh.polygons)), loop_totals)
    corner_positions = coordinates[loop_vertices]
    probes = (
        corner_positions + (centers[loop_faces] - corner_positions) * _FACE_NUDGE
    ).tolist()
    # Each face's largest centre-to-corner distance, in the single precision the tree works in.
    spans = corner_positions.astype(np.float32) - centers.astype(np.float32)[loop_faces]
    extents = np.maximum.reduceat(
        np.sqrt((spans * spans).sum(axis=1)), loop_starts
    ).astype(np.float64)
    face_directions = tuple(zip((-normals).tolist(), normals.tolist()))
    face_centers = centers.tolist()
    anchors = np.zeros(len(mesh.polygons), dtype=np.int64)
    corner_triangles = np.zeros(len(mesh.loops), dtype=np.int64)
    tree = receiver_data.tree
    triangle_receiver = receiver_data.triangle_receiver
    for face, (start, total) in enumerate(
        zip(loop_starts.tolist(), loop_totals.tolist())
    ):
        directions = face_directions[face]
        loops = range(start, start + total)
        hits = []
        for loop in loops:
            hit = _closest_hit(tree, probes[loop], directions, max_distance)
            hits.append(None if hit is None else hit[0])
        votes = Counter(
            int(triangle_receiver[triangle])
            for triangle in hits
            if triangle is not None
        )
        if len(votes) > 1 or (votes and None in hits):
            # The corners disagree: vote by area instead.
            votes = Counter()
            corners = [coordinates[loop_vertices[loop]] for loop in loops]
            for point in _face_samples(centers[face], corners, float(extents[face])):
                hit = _closest_hit(tree, Vector(point), directions, max_distance)
                if hit is not None:
                    votes[int(triangle_receiver[hit[0]])] += 1
        if not votes:
            continue
        receiver = votes.most_common(1)[0][0]
        face_receivers[face] = receiver
        receiver_tree, triangle_offset = receiver_data.receiver_trees[receiver]

        def receiver_triangle(probe):
            hit = (
                _closest_hit(receiver_tree, probe, directions, max_distance)
                or receiver_tree.find_nearest(probe)[2:]
            )
            return triangle_offset + hit[0]

        anchors[face] = receiver_triangle(face_centers[face])
        for loop, triangle in zip(loops, hits):
            if triangle is None or triangle_receiver[triangle] != receiver:
                triangle = receiver_triangle(probes[loop])
            corner_triangles[loop] = triangle

    corner_receivers = face_receivers[loop_faces]
    for receiver in np.unique(face_receivers[face_receivers >= 0]).tolist():
        corners = np.flatnonzero(corner_receivers == receiver)
        _sample_receiver_uvs(
            receiver_data,
            receiver,
            corners,
            corner_triangles[corners],
            anchors[loop_faces[corners]],
            corner_positions[corners],
            extents[loop_faces[corners]],
            corner_uvs,
        )

    attributes = mesh.attributes
    for name, values in corner_uvs.items():
        _write_corner_vectors(attributes, receiver_uv_attribute(name), values)
    _write_decal_frame(mesh, mesh.uv_layers[0].name, frame_attributes)
    return DecalReceiverBinding(face_receivers, layer_names)


def _write_corner_vectors(attributes, name, values):
    existing = attributes.get(name)
    if existing is not None:
        attributes.remove(existing)
    attribute = attributes.new(name=name, type="FLOAT_VECTOR", domain="CORNER")
    attribute.data.foreach_set(
        "vector", np.ascontiguousarray(values, dtype=np.float32).reshape(-1)
    )


def _write_decal_frame(mesh, uv_name, names):
    """The decal's UV tangent frame per corner, bitangent oriented along the DirectX normal-map Y axis"""
    try:
        normals, tangents, signs = mesh_corner_frame(mesh, uv_name)
    finally:
        mesh.free_tangents()
    bitangents = -signs[:, None] * np.cross(normals, tangents)
    for name, values in zip(names, (tangents, bitangents, normals)):
        _write_corner_vectors(mesh.attributes, name, values)


def write_face_values(mesh, name, values):
    """A per-face integer attribute (the face receivers, or the material slot the preview assigns)"""
    attributes = mesh.attributes
    existing = attributes.get(name)
    if existing is not None:
        attributes.remove(existing)
    attribute = attributes.new(name=name, type="INT", domain="FACE")
    attribute.data.foreach_set("value", np.asarray(values, dtype=np.int32))


def face_values(mesh, name):
    attribute = mesh.attributes.get(name)
    if attribute is None or attribute.domain != "FACE":
        return None
    values = np.empty(len(attribute.data), dtype=np.int32)
    attribute.data.foreach_get("value", values)
    return values


def set_preview_slots(obj, materials):
    """Fill the object's material slots after the first with materials, as object-level links"""
    mesh = obj.data
    while len(mesh.materials) < len(materials) + 1:
        mesh.materials.append(None)
    for index, material in enumerate(materials, start=1):
        slot = obj.material_slots[index]
        slot.link = "OBJECT"
        slot.material = material


def _preview_group(source_uv_layer, uv_layers, decal_uv_layer):
    """Geometry Nodes group that writes the decal's receiver UVs and face materials"""
    signature = json.dumps((source_uv_layer, uv_layers, decal_uv_layer))
    name = (
        f"{_PREVIEW_GROUP_PREFIX} {hashlib.sha1(signature.encode()).hexdigest()[:10]}"
    )
    group = bpy.data.node_groups.get(name)
    if group is not None and group.bl_idname == "GeometryNodeTree":
        return group
    group = track_created_datablock(
        "node_groups", bpy.data.node_groups.new(name, "GeometryNodeTree")
    )
    group[PREVIEW_ONLY_FLAG] = True
    group.interface.new_socket(
        name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
    )
    group.interface.new_socket(
        name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
    )
    nodes, links = group.nodes, group.links
    incoming = nodes.new("NodeGroupInput")
    incoming.location = (-200, 0)
    outgoing = nodes.new("NodeGroupOutput")
    geometry = incoming.outputs["Geometry"]

    def store(target_name, source, x):
        node = nodes.new("GeometryNodeStoreNamedAttribute")
        node.data_type = "FLOAT2"
        node.domain = "CORNER"
        node.location = (x, 0)
        node.inputs["Name"].default_value = target_name
        links.new(geometry, node.inputs["Geometry"])
        links.new(source, node.inputs["Value"])
        return node.outputs["Geometry"]

    x = 0
    decal_uv = nodes.new("GeometryNodeInputNamedAttribute")
    decal_uv.data_type = "FLOAT_VECTOR"
    decal_uv.location = (x, -200)
    decal_uv.inputs["Name"].default_value = source_uv_layer
    x += 200
    geometry = store(decal_uv_layer, decal_uv.outputs["Attribute"], x)
    for layer in uv_layers:
        source = nodes.new("GeometryNodeInputNamedAttribute")
        source.data_type = "FLOAT_VECTOR"
        source.location = (x, -200)
        source.inputs["Name"].default_value = receiver_uv_attribute(layer)
        x += 200
        geometry = store(layer, source.outputs["Attribute"], x)
    slot = nodes.new("GeometryNodeInputNamedAttribute")
    slot.data_type = "INT"
    slot.location = (x, -200)
    slot.inputs["Name"].default_value = DECAL_SLOT_ATTRIBUTE
    x += 200
    set_index = nodes.new("GeometryNodeSetMaterialIndex")
    set_index.location = (x, 0)
    links.new(geometry, set_index.inputs["Geometry"])
    links.new(slot.outputs["Attribute"], set_index.inputs["Material Index"])
    outgoing.location = (x + 200, 0)
    links.new(set_index.outputs["Geometry"], outgoing.inputs["Geometry"])
    return group


def remove_receiver_preview(obj):
    """Remove the receiver preview modifiers"""
    for modifier in tuple(obj.modifiers):
        if is_preview_only_modifier(modifier) and modifier.node_group.name.startswith(
            _PREVIEW_GROUP_PREFIX
        ):
            obj.modifiers.remove(modifier)


def ensure_receiver_preview(obj, uv_layers, decal_uv_layer):
    """Add (or refresh) the preview-only modifier that renders obj with its receivers' UVs"""
    remove_receiver_preview(obj)
    modifier = obj.modifiers.new(PREVIEW_MODIFIER_NAME, "NODES")
    modifier.node_group = _preview_group(
        obj.data.uv_layers[0].name, tuple(uv_layers), decal_uv_layer
    )
    modifier.show_in_editmode = False
    return modifier
