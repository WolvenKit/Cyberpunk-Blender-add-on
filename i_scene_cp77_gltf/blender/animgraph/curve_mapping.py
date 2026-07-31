from __future__ import annotations

import re
from typing import Iterable, List, Optional, Tuple

import bpy

HELPER_MATERIAL_NAME = ".REDengine AnimGraph Curve Widgets"


def _safe_fragment(text: str) -> str:
    text = str(text or "curve")
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text)
    return text[:80] or "curve"


def helper_name(owner, item) -> str:
    owner_id = _safe_fragment(getattr(owner, "red_handle_id", "owner"))
    key = _safe_fragment(getattr(item, "json_path", "") or getattr(item, "key", "curve"))
    return f"REDcurve_{owner_id}_{key}"


def helper_material(*, create: bool = False) -> Optional[bpy.types.Material]:
    """Return the hidden material used to host CurveMapping helper nodes."""
    mat = bpy.data.materials.get(HELPER_MATERIAL_NAME)
    if mat is None:
        if not create:
            return None
        mat = bpy.data.materials.new(HELPER_MATERIAL_NAME)
        try:
            mat.use_fake_user = True
        except Exception:

            pass
    if not getattr(mat, "use_nodes", False):
        if not create:
            return None
        mat.use_nodes = True
    return mat


def _curve_node_tree(*, create: bool = False):
    mat = helper_material(create=create)
    if mat is None:
        return None
    return getattr(mat, "node_tree", None)


def get_helper_node(owner, item, *, create: bool = False):
    """Return the helper ShaderNodeFloatCurve for one REDengine curve property."""
    tree = _curve_node_tree(create=create)
    if tree is None:
        return None

    name = getattr(item, "curve_helper_node", "") or helper_name(owner, item)
    node = tree.nodes.get(name)
    if node is None and create:
        try:
            node = tree.nodes.new("ShaderNodeFloatCurve")
        except Exception:
            return None
        node.name = name
        node.label = f"{getattr(owner, 'label', '')}.{getattr(item, 'key', 'curve')}"
        node.hide = True
        item.curve_helper_node = node.name
        sync_native_from_property(item, node)
    elif node is not None and create:

        item.curve_helper_node = node.name
    return node


def _curve_points_from_property(item) -> List[Tuple[float, float]]:
    pts = [(float(p.point), float(p.value)) for p in getattr(item, "curve_points", ())]
    pts.sort(key=lambda xy: xy[0])
    if not pts:
        pts = [(0.0, 0.0), (1.0, 1.0)]
    if len(pts) == 1:
        x, y = pts[0]
        pts.append((x + 1.0, y))
    return pts


def _bounds(points: Iterable[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    pts = list(points)
    xs = [p[0] for p in pts] or [0.0, 1.0]
    ys = [p[1] for p in pts] or [0.0, 1.0]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if min_x == max_x:
        min_x -= 1.0
        max_x += 1.0
    if min_y == max_y:
        min_y -= 1.0
        max_y += 1.0
    pad_x = max(0.05, (max_x - min_x) * 0.08)
    pad_y = max(0.05, (max_y - min_y) * 0.08)
    return min_x - pad_x, max_x + pad_x, min_y - pad_y, max_y + pad_y


def _set_curve_points(curve, points: List[Tuple[float, float]]) -> bool:
    pts = curve.points
    target_count = max(2, len(points))
    try:
        while len(pts) < target_count:
            x, y = points[min(len(pts), len(points) - 1)]
            pts.new(float(x), float(y))
    except Exception:
        pass

    try:
        while len(pts) > target_count:
            pts.remove(pts[-1])
    except Exception:
        pass

    count = min(len(pts), target_count)
    for i in range(count):
        x, y = points[min(i, len(points) - 1)]
        try:
            pts[i].location = (float(x), float(y))
        except Exception:
            try:
                pts[i].location[0] = float(x)
                pts[i].location[1] = float(y)
            except Exception:
                return False
    return True


def sync_native_from_property(item, node=None) -> bool:
    """Push editable REDengine curve data into the native CurveMapping helper."""
    if node is None:
        return False
    mapping = getattr(node, "mapping", None)
    if mapping is None:
        return False
    try:
        mapping.initialize()
    except Exception:
        pass
    points = _curve_points_from_property(item)
    try:
        mapping.use_clip = True
        min_x, max_x, min_y, max_y = _bounds(points)
        mapping.clip_min_x = min_x
        mapping.clip_max_x = max_x
        mapping.clip_min_y = min_y
        mapping.clip_max_y = max_y
    except Exception:
        pass
    try:
        curve = mapping.curves[0]
    except Exception:
        return False
    ok = _set_curve_points(curve, points)
    try:
        mapping.update()
    except Exception:
        pass
    item.curve_widget_initialized = True
    item.curve_widget_dirty = False
    return ok


def sync_property_from_native(item, node=None) -> bool:
    """Pull native CurveMapping edits back into REDengine curve data."""
    if node is None:
        return False
    mapping = getattr(node, "mapping", None)
    if mapping is None:
        return False
    try:
        curve = mapping.curves[0]
    except Exception:
        return False
    values: List[Tuple[float, float]] = []
    try:
        for p in curve.points:
            loc = p.location
            values.append((float(loc[0]), float(loc[1])))
    except Exception:
        return False
    values.sort(key=lambda xy: xy[0])
    item.curve_points.clear()
    for x, y in values:
        pt = item.curve_points.add()
        pt.point = x
        pt.value = y
    item.curve_points_index = min(max(0, item.curve_points_index), max(0, len(item.curve_points) - 1))
    item.curve_widget_dirty = False
    item.curve_widget_initialized = True
    return True


def ensure_native_curve(owner, item):
    """Create or update the native helper curve for one editable property."""
    node = get_helper_node(owner, item, create=True)
    if node is None:
        return None
    if not getattr(item, "curve_widget_initialized", False):
        sync_native_from_property(item, node)
    return node


def iter_curve_properties_in_tree(tree: bpy.types.NodeTree):
    if tree is None:
        return
    for node in getattr(tree, "nodes", ()):
        for item in getattr(node, "red_properties", ()):
            if getattr(item, "value_kind", "") == "CURVE_FLOAT":
                yield node, item
        sub_tree = getattr(node, "node_tree", None)
        if sub_tree is not None and sub_tree is not tree:
            yield from iter_curve_properties_in_tree(sub_tree)


def initialize_native_curves_for_tree(tree: bpy.types.NodeTree) -> Tuple[int, int]:
    """Create native curve helpers for all editable curve properties in a tree."""
    done = set()
    ok = 0
    failed = 0
    for owner, item in iter_curve_properties_in_tree(tree):
        token = (getattr(owner, "name", ""), getattr(item, "json_path", "") or getattr(item, "key", ""))
        if token in done:
            continue
        done.add(token)
        node = get_helper_node(owner, item, create=True)
        if node is not None and sync_native_from_property(item, node):
            ok += 1
        else:
            failed += 1
    return ok, failed


def remove_all_helpers() -> int:
    mat = bpy.data.materials.get(HELPER_MATERIAL_NAME)
    if mat is None or mat.node_tree is None:
        return 0
    tree = mat.node_tree
    count = 0
    for node in list(tree.nodes):
        if node.bl_idname == "ShaderNodeFloatCurve" and node.name.startswith("REDcurve_"):
            tree.nodes.remove(node)
            count += 1
    return count
