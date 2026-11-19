"""Keep game-world content near Blender's origin.

Night City sits kilometres from the game origin. At that range 32-bit floats only resolve
fractions of a millimetre, which breaks precision-sensitive rendering such as Cycles random
walk subsurface scattering (faceted, ridged skin). Recentring shifts the scene by a whole-metre
offset stored on the scene, so Blender space = game space + offset, and exporters subtract it
again to write true game coordinates.
"""

from __future__ import annotations

import bpy
from mathutils import Matrix, Vector

from ..assetio.values import coerce_float
from ..bartmoss.vector3 import snapped_offset
from ..redSpace.transforms import game_matrix_to_scene, scene_matrix_to_game
from .collections import MASTER_INSTANCES_COLLECTION, object_owners
from .identity import rna_identity, rna_is_live
from .keyframes import assigned_channelbags
from .light_channels import shift_light_channel_records
from .matrix import object_world_matrix
from .operator_results import OperationResult
from .transactions import track_mutation

# === Constants ===

WORLD_OFFSET_KEY = "cp77_world_offset"
# Constraints that place their owner from a target, so the owner's own move must not count twice.
_FOLLOW_CONSTRAINTS = frozenset({"COPY_TRANSFORMS"})


# === Stored offset ===


def world_offset(scene) -> Vector:
    """The offset added to game coordinates in scene, zero when it was never recentred"""
    stored = scene.get(WORLD_OFFSET_KEY) if scene is not None else None
    if not hasattr(stored, "__len__") or len(stored) != 3:
        return Vector((0.0, 0.0, 0.0))
    return Vector(tuple(coerce_float(value) for value in stored))


def has_world_offset(scene) -> bool:
    return world_offset(scene).length > 0.0


def set_world_offset(scene, offset) -> None:
    offset = Vector(offset)
    if offset.length == 0.0:
        if WORLD_OFFSET_KEY in scene:
            del scene[WORLD_OFFSET_KEY]
        return
    scene[WORLD_OFFSET_KEY] = [float(value) for value in offset]


# === Matrices ===


def scene_matrix(offset, matrix) -> Matrix:
    """A game-space world matrix in the space of a scene recentred by offset"""
    if not any(offset):
        return matrix.copy()
    return Matrix(game_matrix_to_scene(offset, matrix).tolist())


def game_matrix(offset, matrix) -> Matrix:
    """A world matrix of a scene recentred by offset in game space"""
    if not any(offset):
        return matrix.copy()
    return Matrix(scene_matrix_to_game(offset, matrix).tolist())


def game_world_matrix(obj, offset) -> Matrix:
    """obj's world matrix (object_world_matrix) in game space, for a scene recentred by offset"""
    return game_matrix(offset, object_world_matrix(obj))


# === Shifting ===


def instance_source_collections():
    """Identities of collections that collection instances copy, nested children included

    The import masters collection counts too: imports copy masters as well as instancing them,
    and the next import builds from the master's own matrix, so a master no instance points at
    still must not move.
    """
    sources = set()
    masters = bpy.data.collections.get(MASTER_INSTANCES_COLLECTION)
    if masters is not None:
        sources.add(rna_identity(masters))
        sources.update(rna_identity(child) for child in masters.children_recursive)
    for obj in bpy.data.objects:
        collection = (
            obj.instance_collection if obj.instance_type == "COLLECTION" else None
        )
        if collection is None:
            continue
        sources.add(rna_identity(collection))
        sources.update(rna_identity(child) for child in collection.children_recursive)
    return sources


def template_objects(owners=None):
    """Identities of objects that only exist to be copied by collection instances, which carry their placement

    An object is a template when every collection holding it is an instance source.
    """
    if owners is None:
        owners = object_owners()
    sources = instance_source_collections()
    return {
        identity
        for identity, holders in owners.items()
        if all(rna_identity(holder) in sources for holder in holders)
    }


def _follows_target(obj) -> bool:
    """Whether obj's location comes from a target that moves with the shift anyway"""
    for constraint in obj.constraints:
        if not constraint.enabled or constraint.influence == 0.0:
            continue
        target = getattr(constraint, "target", None)
        if target is None:
            continue
        if constraint.type in _FOLLOW_CONSTRAINTS:
            return True
        if constraint.type == "COPY_LOCATION" and constraint.use_offset:
            return True
    return False


def _shift_keys(obj, delta, shifted) -> None:
    """Move obj's location keys by delta, skipping channelbags in shifted (by pointer) and adding the rest"""
    for channelbag in assigned_channelbags(obj):
        pointer = channelbag.as_pointer()
        if pointer in shifted:
            continue
        shifted.add(pointer)
        for curve in channelbag.fcurves:
            if curve.data_path != "location":
                continue
            amount = delta[curve.array_index]
            for key in curve.keyframe_points:
                key.co.y += amount
                key.handle_left.y += amount
                key.handle_right.y += amount
            curve.update()


def _root(obj):
    while obj.parent is not None:
        obj = obj.parent
    return obj


def _placed_by_location(obj, templates) -> bool:
    """Whether a shift moves obj through its own location"""
    return (
        obj.parent is None
        and obj.library is None
        and rna_identity(obj) not in templates
        and not _follows_target(obj)
    )


def shift_objects(objects, delta, templates) -> int:
    """Move objects by delta in world space without double-moving anything that follows another object

    Only parentless objects move (children follow their parents). Templates that collection
    instances copy stay put, because the instancing empties carry the move. A Child Of
    constraint applies its target's motion on top of its owner's own world matrix, so when
    both moved its inverse matrix absorbs one copy of the shift. Returns how many objects moved.
    """
    delta = Vector(delta)
    if delta.length == 0.0:
        return 0
    moved = set()
    shifted_channelbags = set()
    for obj in objects:
        if not _placed_by_location(obj, templates):
            continue
        _shift_keys(obj, delta, shifted_channelbags)
        obj.location += delta
        moved.add(rna_identity(obj))

    absorb = Matrix.Translation(-delta)
    for obj in bpy.data.objects:
        if rna_identity(_root(obj)) not in moved:
            continue
        for constraint in obj.constraints:
            target = getattr(constraint, "target", None)
            if constraint.type != "CHILD_OF" or target is None:
                continue
            if rna_identity(_root(target)) in moved:
                constraint.inverse_matrix = constraint.inverse_matrix @ absorb
    return len(moved)


def _shift_scene(scene, delta, objects, templates) -> int:
    """Move objects, the scene's stored light-channel volumes and its cursor by delta, and add it to the offset"""
    moved = shift_objects(objects, delta, templates)
    shift_light_channel_records(scene.collection.children_recursive, delta)
    scene.cursor.location += Vector(delta)
    set_world_offset(scene, world_offset(scene) + Vector(delta))
    return moved


def _sample_points(objects, templates):
    """World positions of the objects that a recentre places by their own location"""
    return [
        tuple(object_world_matrix(obj).translation)
        for obj in objects
        if _placed_by_location(obj, templates)
    ]


def _xyz(vector) -> str:
    return f"({vector[0]:g}, {vector[1]:g}, {vector[2]:g})"


def recentre_scene(scene) -> OperationResult:
    """Shift a whole scene so its content sits near the origin, adding to any stored offset"""
    objects = tuple(scene.objects)
    templates = template_objects()
    offset = snapped_offset(_sample_points(objects, templates))
    if offset is None:
        return OperationResult.cancelled(
            "The scene already sits near the origin", level="INFO"
        )
    moved = _shift_scene(scene, offset, objects, templates)
    return OperationResult.finished(
        f"Recentred the scene by {_xyz(offset)}, moving {moved} objects; sector export adds the offset back"
    )


def restore_world_position(scene) -> OperationResult:
    """Undo every recentre of scene so it holds true game coordinates again"""
    offset = world_offset(scene)
    if offset.length == 0.0:
        return OperationResult.cancelled(
            "The scene already holds game coordinates", level="INFO"
        )
    moved = _shift_scene(scene, -offset, tuple(scene.objects), template_objects())
    return OperationResult.finished(
        f"Moved the scene back by {_xyz(-offset)}, moving {moved} objects"
    )


def recentre_for_import(scene, positions) -> Vector:
    """The offset an import places its content by: the scene's own, or one it now takes from positions

    A scene without an offset takes the snapped centre of the game positions the import is about to
    fill, moving what it already holds along. The import transaction rolls that back.
    """
    if has_world_offset(scene):
        return world_offset(scene)
    offset = snapped_offset(positions)
    if offset is None:
        return Vector((0.0, 0.0, 0.0))
    objects = tuple(scene.objects)
    templates = template_objects()
    track_mutation(
        ("world_offset", rna_identity(scene)),
        lambda: _shift_scene(
            scene,
            tuple(-value for value in offset),
            tuple(obj for obj in objects if rna_is_live(obj)),
            templates,
        ),
        label="scene world offset",
    )
    _shift_scene(scene, offset, objects, templates)
    return Vector(offset)
