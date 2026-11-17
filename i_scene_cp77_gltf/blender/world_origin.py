"""Keep game-world content near Blender's origin.

Night City sits kilometres from the game origin. At that range 32-bit floats only resolve
fractions of a millimetre, which breaks precision-sensitive rendering such as Cycles random
walk subsurface scattering (faceted, ridged skin). Recentring shifts the scene by a whole-metre
offset stored on the scene, so Blender space = game space + offset, and exporters subtract it
again to write true game coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median

import bpy
from mathutils import Matrix, Vector

from .matrix import object_world_matrix

# === Constants ===

WORLD_OFFSET_KEY = "cp77_world_offset"
# Offsets snap to whole metres so game coordinates stay easy to read back by hand.
OFFSET_GRID = 1.0
# Content closer than this to the origin gains nothing from recentring.
RECENTRE_MIN_DISTANCE = 100.0
# Constraints that place their owner from a target, so the owner's own move must not count twice.
_FOLLOW_CONSTRAINTS = frozenset({"COPY_TRANSFORMS"})


# === Stored offset ===


def world_offset(scene) -> Vector:
    """The offset added to game coordinates in scene, zero when it was never recentred"""
    stored = scene.get(WORLD_OFFSET_KEY) if scene is not None else None
    if stored is None:
        return Vector((0.0, 0.0, 0.0))
    try:
        return Vector(tuple(float(value) for value in stored))
    except (TypeError, ValueError):
        return Vector((0.0, 0.0, 0.0))


def has_world_offset(scene) -> bool:
    return world_offset(scene).length > 0.0


def set_world_offset(scene, offset) -> None:
    offset = Vector(offset)
    if offset.length == 0.0:
        if WORLD_OFFSET_KEY in scene:
            del scene[WORLD_OFFSET_KEY]
        return
    scene[WORLD_OFFSET_KEY] = [float(value) for value in offset]


def to_game_matrix(scene, matrix):
    """A Blender-space world matrix in game space"""
    offset = world_offset(scene)
    if offset.length == 0.0:
        return matrix.copy()
    return Matrix.Translation(-offset) @ matrix


def to_game_location(scene, location) -> Vector:
    return Vector(location) - world_offset(scene)


def _owning_scene(obj):
    scenes = getattr(obj, "users_scene", ())
    if scenes:
        return scenes[0]
    return getattr(bpy.context, "scene", None)


def game_world_matrix(obj, scene=None):
    """obj's world matrix (object_world_matrix) in game space"""
    return to_game_matrix(scene or _owning_scene(obj), object_world_matrix(obj))


def snapped_offset(points) -> Vector | None:
    """The offset that brings the middle of points to the origin, or None when they are already close"""
    points = [Vector(point) for point in points]
    if not points:
        return None
    # The per-axis median, not the bounds centre: stray objects left at the origin (or far away)
    # must not drag the offset off the content people work on.
    centre = Vector(tuple(median(point[axis] for point in points) for axis in range(3)))
    if centre.length < RECENTRE_MIN_DISTANCE:
        return None
    return Vector(tuple(-round(value / OFFSET_GRID) * OFFSET_GRID for value in centre))


# === Shifting ===


@dataclass(slots=True)
class ShiftReport:
    moved: int = 0
    templates: int = 0
    followers: int = 0
    keyed: int = 0
    child_of_fixed: int = 0


def instance_source_collections():
    """Names of collections that collection instances copy, nested children included"""
    names = set()

    def add(collection):
        if collection.name in names:
            return
        names.add(collection.name)
        for child in collection.children:
            add(child)

    for obj in bpy.data.objects:
        if obj.instance_type == "COLLECTION" and obj.instance_collection is not None:
            add(obj.instance_collection)
    return names


def template_objects():
    """Pointers of objects that only exist to be copied by collection instances, which carry their placement

    Built from one pass over every collection: Object.users_collection scans all collections on
    each call, which takes minutes across a sector scene's thousands of objects.
    """
    sources = instance_source_collections()
    in_source, elsewhere = set(), set()
    for collection in bpy.data.collections:
        bucket = in_source if collection.name in sources else elsewhere
        bucket.update(obj.as_pointer() for obj in collection.objects)
    for scene in bpy.data.scenes:
        elsewhere.update(obj.as_pointer() for obj in scene.collection.objects)
    return in_source - elsewhere


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


def _location_fcurves(obj):
    animation = obj.animation_data
    action = animation.action if animation is not None else None
    if action is None:
        return []
    layers = getattr(action, "layers", None)
    if layers:
        curves = []
        for layer in layers:
            for strip in layer.strips:
                for bag in getattr(strip, "channelbags", ()):
                    curves.extend(
                        fc for fc in bag.fcurves if fc.data_path == "location"
                    )
        return curves
    return [fc for fc in getattr(action, "fcurves", ()) if fc.data_path == "location"]


def _shift_keys(obj, delta) -> int:
    curves = _location_fcurves(obj)
    for curve in curves:
        amount = delta[curve.array_index]
        for key in curve.keyframe_points:
            key.co.y += amount
            key.handle_left.y += amount
            key.handle_right.y += amount
        curve.update()
    return len(curves)


def _root(obj):
    while obj.parent is not None:
        obj = obj.parent
    return obj


def shift_objects(objects, delta) -> ShiftReport:
    """Move objects by delta in world space without double-moving anything that follows another object

    Only parentless objects move (children follow their parents). Templates that collection
    instances copy stay put, because the instancing empties carry the move. A Child Of
    constraint applies its target's motion on top of its owner's own world matrix, so when
    both moved its inverse matrix absorbs one copy of the shift.
    """
    delta = Vector(delta)
    report = ShiftReport()
    if delta.length == 0.0:
        return report
    templates = template_objects()
    moved = set()
    for obj in objects:
        if obj.parent is not None or obj.library is not None:
            continue
        if obj.as_pointer() in templates:
            report.templates += 1
            continue
        if _follows_target(obj):
            report.followers += 1
            continue
        report.keyed += _shift_keys(obj, delta)
        obj.location += delta
        moved.add(obj.as_pointer())
        report.moved += 1

    absorb = Matrix.Translation(-delta)
    for obj in bpy.data.objects:
        if _root(obj).as_pointer() not in moved:
            continue
        for constraint in obj.constraints:
            target = getattr(constraint, "target", None)
            if constraint.type != "CHILD_OF" or target is None:
                continue
            if _root(target).as_pointer() in moved:
                constraint.inverse_matrix = constraint.inverse_matrix @ absorb
                report.child_of_fixed += 1
    return report


def _sample_points(objects):
    """World positions of the objects that a recentre places by their own location"""
    templates = template_objects()
    return [
        object_world_matrix(obj).translation
        for obj in objects
        if obj.parent is None
        and obj.library is None
        and obj.as_pointer() not in templates
        and not _follows_target(obj)
    ]


def recentre_objects(
    scene, objects, *, offset=None
) -> tuple[Vector | None, ShiftReport]:
    """Shift newly added game-space objects into scene's Blender space

    Uses the scene's stored offset so new content lines up with what is already there;
    without one it picks offset (or the snapped centre of objects) and stores it.
    """
    objects = list(objects)
    if has_world_offset(scene):
        offset = world_offset(scene)
    elif offset is None:
        offset = snapped_offset(_sample_points(objects))
        if offset is None:
            return None, ShiftReport()
    report = shift_objects(objects, offset)
    set_world_offset(scene, offset)
    return Vector(offset), report


def recentre_scene(scene, *, offset=None) -> tuple[Vector | None, ShiftReport]:
    """Shift a whole scene so its content sits near the origin, adding to any stored offset"""
    objects = list(scene.objects)
    if offset is None:
        offset = snapped_offset(_sample_points(objects))
        if offset is None:
            return None, ShiftReport()
    offset = Vector(offset)
    report = shift_objects(objects, offset)
    scene.cursor.location += offset
    set_world_offset(scene, world_offset(scene) + offset)
    return offset, report


def restore_world_position(scene) -> tuple[Vector | None, ShiftReport]:
    """Undo every recentre of scene so it holds true game coordinates again"""
    offset = world_offset(scene)
    if offset.length == 0.0:
        return None, ShiftReport()
    report = shift_objects(list(scene.objects), -offset)
    scene.cursor.location -= offset
    set_world_offset(scene, (0.0, 0.0, 0.0))
    return -offset, report
