from __future__ import annotations

import math

from ...blender.ink.materials import preview_material
from ...blender.ink.screens import PENDING_EDITS_KEY
from ...blender.transactions import new_tracked_datablock
from ...ink.domain.layout import LaidOutItem, LaidOutWidget

WIDGET_PATH_KEY = "inkWidgetPath"
PREVIEW_KEY = "inkPreview"
# Where a handle was last placed: [location x, location y, rotation z, scale x, scale y].
BASE_KEY = "inkBase"
# Handles float this many pixels in front of the preview.
_HANDLE_DEPTH = 1.0


def path_text(path) -> str:
    return "/".join(str(index) for index in path)


def widget_path(obj) -> tuple[int, ...] | None:
    """The child-index path of the widget obj is the handle of, or None"""
    value = obj.get(WIDGET_PATH_KEY) if obj is not None else None
    if value is None:
        return None
    return tuple(int(part) for part in str(value).split("/") if part)


def is_screen_root(obj) -> bool:
    """Whether obj itself shows a widget library"""
    return bool(obj.get("cp77_ink_render_texture"))


def screen_root(obj):
    """The object showing a widget library that obj is, holds or sits under"""
    current = obj
    while current is not None:
        if is_screen_root(current):
            return current
        held = next(
            (child for child in current.children if is_screen_root(child)), None
        )
        if held is not None:
            return held
        current = current.parent
    return None


def picked_widget(scene):
    """The widget picked in the ink Widgets list, None when none is picked or it has left scene"""
    widget = scene.cp77_ink_tools.widget
    return (
        widget
        if widget is not None and scene.objects.get(widget.name) == widget
        else None
    )


def standalone_root(obj):
    """The root of the standalone widget import obj belongs to, or None"""
    root = screen_root(obj)
    return root if root is not None and PENDING_EDITS_KEY in root else None


def handles(root) -> dict[tuple[int, ...], object]:
    return {
        path: obj
        for obj in root.children_recursive
        if (path := widget_path(obj)) is not None
    }


def preview(root):
    return next((child for child in root.children if child.get(PREVIEW_KEY)), None)


def _preview_corners(size: tuple[float, float]):
    width, height = size
    return (
        (0.0, 0.0, 0.0),
        (0.0, -height, 0.0),
        (width, -height, 0.0),
        (width, 0.0, 0.0),
    )


def _new_preview(name: str, size: tuple[float, float], image, collection, root):
    mesh = new_tracked_datablock("meshes", f"{name}_preview")
    mesh.from_pydata(_preview_corners(size), [], [(0, 1, 2, 3)])
    # The raster's first row is the image's first row, which a V of 0 samples.
    mesh.uv_layers.new(name="UVMap").uv.foreach_set(
        "vector", (0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 0.0)
    )
    mesh.materials.append(preview_material(f"{name}_preview", image))
    obj = new_tracked_datablock("objects", f"{name}_preview", mesh)
    collection.objects.link(obj)
    obj.parent = root
    obj.hide_select = True
    obj[PREVIEW_KEY] = 1
    return obj


def _new_handle(entry: LaidOutWidget, parent, collection):
    name = entry.widget.name or entry.widget.type
    mesh = new_tracked_datablock("meshes", name)
    mesh.from_pydata([(0.0, 0.0, 0.0)] * 4, [(0, 1), (1, 2), (2, 3), (3, 0)], [])
    obj = new_tracked_datablock("objects", name, mesh)
    collection.objects.link(obj)
    obj.parent = parent
    obj.rotation_mode = "XYZ"
    obj.hide_render = True
    obj[WIDGET_PATH_KEY] = path_text(entry.widget.path)
    obj["cp77_type"] = entry.widget.type
    return obj


def create(scene, name: str, laid_out: LaidOutItem, image, *, unit_scale: float):
    """A new collection holding the root empty, the preview plane and a handle per widget"""
    collection = new_tracked_datablock("collections", name)
    scene.collection.children.link(collection)
    root = new_tracked_datablock("objects", name, None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 32.0
    root.scale = (float(unit_scale),) * 3
    collection.objects.link(root)
    _new_preview(name, laid_out.size, image, collection, root)
    created = {}
    for entry in laid_out.widgets:
        parent = created[entry.parent.widget.path] if entry.parent is not None else root
        created[entry.widget.path] = _new_handle(entry, parent, collection)
    sync(root, laid_out)
    return root


def _pivot(entry: LaidOutWidget | None) -> tuple[float, float]:
    if entry is None:
        return 0.0, 0.0
    pivot = entry.widget.render.pivot
    return pivot[0] * entry.width, pivot[1] * entry.height


def placement(
    entry: LaidOutWidget,
) -> tuple[tuple[float, float], float, tuple[float, float]]:
    """(location, z rotation, scale) of a widget's handle in its parent handle's space"""
    render = entry.widget.render
    pivot_x, pivot_y = _pivot(entry)
    parent_x, parent_y = _pivot(entry.parent)
    x = entry.x + render.translation[0] + pivot_x
    y = entry.y + render.translation[1] + pivot_y
    return (x - parent_x, parent_y - y), -math.radians(render.rotation), render.scale


def sync(root, laid_out: LaidOutItem) -> None:
    """Place every handle, size its rectangle and the preview plane"""
    found = handles(root)
    for entry in laid_out.widgets:
        handle = found.get(entry.widget.path)
        if handle is None:
            continue
        (x, y), turn, (scale_x, scale_y) = placement(entry)
        handle.location = (x, y, _HANDLE_DEPTH if entry.parent is None else 0.0)
        handle.rotation_euler = (0.0, 0.0, turn)
        handle.scale = (scale_x, scale_y, 1.0)
        pivot_x, pivot_y = _pivot(entry)
        left, top = -pivot_x, pivot_y
        right, bottom = entry.width - pivot_x, pivot_y - entry.height
        handle.data.vertices.foreach_set(
            "co",
            (left, top, 0.0, right, top, 0.0, right, bottom, 0.0, left, bottom, 0.0),
        )
        handle.data.update()
        handle[BASE_KEY] = [
            handle.location.x,
            handle.location.y,
            handle.rotation_euler.z,
            handle.scale.x,
            handle.scale.y,
        ]
        handle.hide_set(not entry.visible)
    plane = preview(root)
    if plane is not None:
        plane.data.vertices.foreach_set(
            "co",
            [value for corner in _preview_corners(laid_out.size) for value in corner],
        )
        plane.data.update()
