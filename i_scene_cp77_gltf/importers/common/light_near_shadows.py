"""Keep a light's own fixture from shadowing it, as the game's shadow near plane does.

Game lights often sit inside their lamp head (housing, lens). The game's local shadows ignore
geometry that close to the light, but Blender traces it, so the light stays dark. Each light
gets a shadow-link blocker collection that excludes the objects whose surface is within
NEAR_PLANE of it; those objects still shadow every other light.
"""

from __future__ import annotations

import bpy
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

from ...blender.naming import fit_id_name
from ...blender.transactions import track_created_datablock
from ...core.log import debug_exception, get_logger
from .light_channels import children_of

_LOG = get_logger(__name__)

# Assumed, not read from the game: covers lamp housings (~3.5 cm) and lenses (~8.5 cm) around the light.
NEAR_PLANE = 0.15


def _mesh_parts(obj):
    """(mesh object, world matrix) pairs that make up obj's rendered surface"""
    if obj.type == "MESH":
        return [(obj, obj.matrix_world)]
    if (
        obj.type == "EMPTY"
        and obj.instance_type == "COLLECTION"
        and obj.instance_collection
    ):
        base = obj.matrix_world @ Matrix.Translation(
            -Vector(obj.instance_collection.instance_offset)
        )
        return [
            (sub, base @ sub.matrix_world)
            for sub in obj.instance_collection.all_objects
            if sub.type == "MESH"
        ]
    return []


def _near_objects(scoped, lights):
    """Light index -> {pointer: object} of the objects whose surface is within NEAR_PLANE"""
    tree = KDTree(len(lights))
    for index, light in enumerate(lights):
        tree.insert(light.matrix_world.translation, index)
    tree.balance()

    near = {}
    for obj in scoped:
        for mesh_obj, matrix in _mesh_parts(obj):
            if not mesh_obj.data or not mesh_obj.data.polygons:
                continue
            corners = [matrix @ Vector(corner) for corner in mesh_obj.bound_box]
            centre = sum(corners, Vector()) / len(corners)
            radius = max((corner - centre).length for corner in corners) + NEAR_PLANE
            inverse = matrix.inverted_safe()
            for point, index, _distance in tree.find_range(centre, radius):
                hit, location, _normal, _index = mesh_obj.closest_point_on_mesh(
                    inverse @ point
                )
                if hit and ((matrix @ location) - point).length <= NEAR_PLANE:
                    near.setdefault(index, {})[obj.as_pointer()] = obj
    return near


def _new_blocker_collection(scope_collection, excluded, serial):
    name = fit_id_name(f"CP77_SL_{scope_collection.name}", f"_{serial}")
    collection = track_created_datablock("collections", bpy.data.collections.new(name))
    for obj in excluded:
        collection.objects.link(obj)
    # A blocker collection holding only excluded objects keeps every other object blocking.
    for entry in collection.collection_objects:
        entry.light_linking.link_state = "EXCLUDE"
    return collection


def unblock_near_geometry(scope_collection):
    """Give each light in scope a blocker collection that leaves out its own fixture"""
    scoped = tuple(scope_collection.all_objects)
    lights = [
        obj
        for obj in scoped
        if obj.type == "LIGHT" and not obj.get("cp77_light_proxy", False)
    ]
    if not lights:
        return

    children = children_of(lights)
    collections = {}
    linked = 0
    for index, objects in _near_objects(scoped, lights).items():
        light = lights[index]
        key = frozenset(objects)
        collection = collections.get(key)
        if collection is None:
            try:
                collection = _new_blocker_collection(
                    scope_collection, objects.values(), len(collections) + 1
                )
            except (RuntimeError, TypeError, ReferenceError):
                debug_exception(
                    _LOG, "No shadow link collection for light %s", light.name
                )
                continue
            collections[key] = collection
        light.light_linking.blocker_collection = collection
        # Capsule/proxy sample lights sit with their source light, so they share its fixture.
        for child in children.get(light.as_pointer(), ()):
            if child.get("cp77_light_proxy", False):
                child.light_linking.blocker_collection = collection
        linked += 1

    _LOG.debug(
        "Near-plane shadows %s: %d/%d light(s), %d collection(s)",
        scope_collection.name,
        linked,
        len(lights),
        len(collections),
    )
