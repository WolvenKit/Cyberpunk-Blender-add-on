from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MeshExportScope:
    meshes: tuple
    source: str
    excluded_count: int = 0

    def __bool__(self):
        return bool(self.meshes)


def _view_layer_objects(context):
    view_layer = getattr(context, "view_layer", None)
    objects = getattr(view_layer, "objects", ()) if view_layer is not None else ()
    try:
        return tuple(objects)
    except TypeError:
        return tuple(getattr(context, "scene", ()).objects)


def _object_identity(value):
    try:
        return int(value.as_pointer())
    except (AttributeError, ReferenceError):
        return id(value)


def _selected_identities(context):
    return {
        _object_identity(obj)
        for obj in tuple(getattr(context, "selected_objects", ()) or ())
    }


def _is_visible(obj, context):
    try:
        return bool(obj.visible_get(view_layer=context.view_layer))
    except (AttributeError, TypeError):
        try:
            return bool(obj.visible_get())
        except (AttributeError, TypeError):
            return not bool(getattr(obj, "hide_viewport", False))


def resolve_mesh_export_scope(
    context,
    *,
    limit_selected: bool,
    export_visible: bool,
    excluded_objects=(),
):
    objects = _view_layer_objects(context)
    excluded = {_object_identity(obj) for obj in tuple(excluded_objects or ())}
    selected = _selected_identities(context) if limit_selected else frozenset()
    source = "selected" if limit_selected else ("visible" if export_visible else "view_layer")
    meshes = []
    excluded_count = 0

    for obj in objects:
        if getattr(obj, "type", None) != "MESH":
            continue
        identity = _object_identity(obj)
        if identity in excluded:
            excluded_count += 1
            continue
        if limit_selected and identity not in selected:
            continue
        if not limit_selected and export_visible and not _is_visible(obj, context):
            continue
        meshes.append(obj)

    return MeshExportScope(tuple(meshes), source, excluded_count)
