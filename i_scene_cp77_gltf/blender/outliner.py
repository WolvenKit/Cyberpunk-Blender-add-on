from __future__ import annotations

from functools import cmp_to_key

import bpy

from ..gltf.submesh import lod_from_name, submesh_name
from .naming import fit_id_name

_DIGITS = frozenset("0123456789")


def _sign(value):
    return (value > 0) - (value < 0)


def _number_compare(first, i, second, j):
    """(order, leading-zero tiebreak) of the digit runs of first at i and second at j"""
    start_i, start_j = i, j
    while i < len(first) and first[i] == "0":
        i += 1
    while j < len(second) and second[j] == "0":
        j += 1
    end_i, end_j = i, j
    while end_i < len(first) and first[end_i] in _DIGITS:
        end_i += 1
    while end_j < len(second) and second[end_j] in _DIGITS:
        end_j += 1
    digits_i, digits_j = first[i:end_i], second[j:end_j]
    if len(digits_i) != len(digits_j):
        return _sign(len(digits_i) - len(digits_j)), 0
    if digits_i != digits_j:
        return (1 if digits_i > digits_j else -1), 0
    return 0, _sign((i - start_i) - (j - start_j))


def _ascii_lower(character):
    return character.lower() if character.isascii() else character


def natural_compare(first, second):
    """Blender's natural, case-insensitive name order, the one the Outliner sorts by"""
    i = j = 0
    tiebreak = 0
    while True:
        if (
            i < len(first)
            and j < len(second)
            and first[i] in _DIGITS
            and second[j] in _DIGITS
        ):
            order, zeros = _number_compare(first, i, second, j)
            if order:
                return order
            tiebreak = tiebreak or zeros
            i += 1
            while i < len(first) and first[i] in _DIGITS:
                i += 1
            j += 1
            while j < len(second) and second[j] in _DIGITS:
                j += 1
        if i >= len(first) or j >= len(second):
            break
        a, b = _ascii_lower(first[i]), _ascii_lower(second[j])
        if a != b:
            if a == ".":
                return -1
            if b == ".":
                return 1
            return -1 if a < b else 1
        i += 1
        j += 1
    if tiebreak:
        return tiebreak
    encoded_first, encoded_second = first.encode("utf-8"), second.encode("utf-8")
    return (encoded_first > encoded_second) - (encoded_first < encoded_second)


_NAME_ORDER = cmp_to_key(lambda first, second: natural_compare(first.name, second.name))


def _screens(context):
    screen = getattr(context, "screen", None)
    if screen is not None:
        yield screen
    manager = getattr(context, "window_manager", None)
    for window in getattr(manager, "windows", ()) or ():
        if window.screen is not None:
            yield window.screen


def _default_sort_method():
    properties = bpy.types.SpaceOutliner.bl_rna.properties
    if "sort_method" in properties:
        return properties["sort_method"].default
    return "ALPHA" if properties["use_sort_alpha"].default else "NONE"


def outliner_sort_method(context):
    """How the Outliner showing the view layer orders its rows, ALPHA, CUSTOM or NONE, or Blender's default without one"""
    for screen in _screens(context):
        for area in screen.areas:
            if area.type != "OUTLINER":
                continue
            space = area.spaces.active
            if getattr(space, "display_mode", "") != "VIEW_LAYER":
                continue
            method = getattr(space, "sort_method", None)
            if method is not None:
                return method
            return "ALPHA" if space.use_sort_alpha else "NONE"
    return _default_sort_method()


def _custom_index(entry, name):
    return int(getattr(entry, name, -1))


def _ordered_objects(pairs, method, index_name):
    """The objects of (object, collection entry) pairs in Outliner order: custom indices first, then by name"""
    if method == "CUSTOM":
        placed = sorted(
            (pair for pair in pairs if _custom_index(pair[1], index_name) >= 0),
            key=lambda pair: _custom_index(pair[1], index_name),
        )
        rest = sorted(
            (obj for obj, entry in pairs if _custom_index(entry, index_name) < 0),
            key=_NAME_ORDER,
        )
        return [obj for obj, _entry in placed] + rest
    objects = [obj for obj, _entry in pairs]
    return sorted(objects, key=_NAME_ORDER) if method == "ALPHA" else objects


def _collection_rows(collection, top, method):
    """The rows the Outliner lists directly in collection, ("collection", child) or ("object", obj), in order"""
    children = list(zip(collection.children, collection.collection_children))
    if method != "CUSTOM":
        return [("collection", child) for child, _entry in children] + [
            ("object", obj) for obj in _ordered_objects(top, method, "sort_index")
        ]
    rows = [
        (_custom_index(entry, "sort_index"), 0, position, ("collection", child))
        for position, (child, entry) in enumerate(children)
    ] + [
        (_custom_index(entry, "sort_index"), 1, position, ("object", obj))
        for position, (obj, entry) in enumerate(top)
    ]
    placed = sorted((row for row in rows if row[0] >= 0), key=lambda row: row[:3])
    unset_collections = [row[3] for row in rows if row[0] < 0 and row[1] == 0]
    unset_objects = sorted(
        (row[3][1] for row in rows if row[0] < 0 and row[1] == 1), key=_NAME_ORDER
    )
    return (
        [row[3] for row in placed]
        + unset_collections
        + [("object", obj) for obj in unset_objects]
    )


def outliner_object_order(context, objects):
    """objects in the order the Outliner lists them, followed by the ones it does not show in their given order"""
    wanted = {obj.as_pointer(): obj for obj in objects}
    method = outliner_sort_method(context)
    ordered, seen = [], set()

    def visit(obj, children):
        pointer = obj.as_pointer()
        if pointer in wanted and pointer not in seen:
            seen.add(pointer)
            ordered.append(obj)
        for child in _ordered_objects(
            children.get(pointer, ()), method, "parented_sort_index"
        ):
            visit(child, children)

    def walk(collection):
        pairs = list(zip(collection.objects, collection.collection_objects))
        inside = {obj.as_pointer() for obj, _entry in pairs}
        children, top = {}, []
        for obj, entry in pairs:
            parent = obj.parent
            if parent is not None and parent.as_pointer() in inside:
                children.setdefault(parent.as_pointer(), []).append((obj, entry))
            else:
                top.append((obj, entry))
        for kind, item in _collection_rows(collection, top, method):
            if kind == "collection":
                walk(item)
            else:
                visit(item, children)

    view_layer = getattr(context, "view_layer", None)
    if view_layer is not None:
        walk(view_layer.layer_collection.collection)
    ordered.extend(obj for pointer, obj in wanted.items() if pointer not in seen)
    return ordered


def name_submeshes(context, objects):
    """Name objects submesh_NN_LOD_L for their Outliner position unless that reorders them, returning the old and new names changed"""
    order = outliner_object_order(context, objects)
    changes = [
        (obj, obj.name, submesh_name(index, lod_from_name(obj.name)))
        for index, obj in enumerate(order)
    ]
    changes = [change for change in changes if change[1] != change[2]]
    # The names are freed first, as one submesh may want the name another holds.
    for obj, old, _new in changes:
        obj.name = fit_id_name(f"CP77_Rename_{old}")
    for obj, _old, new in changes:
        obj.name = new
    if outliner_object_order(context, objects) != order:
        for obj, old, _new in changes:
            obj.name = fit_id_name(f"CP77_Rename_{old}")
        for obj, old, _new in changes:
            obj.name = old
        return ()
    return tuple((old, obj.name) for obj, old, _new in changes)
