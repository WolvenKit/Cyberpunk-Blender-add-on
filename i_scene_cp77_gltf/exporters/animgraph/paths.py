from __future__ import annotations

import re
from collections.abc import Iterable
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from ...blender.animgraph.access import get_attr

if TYPE_CHECKING:
    import bpy


def _path_parts(path: str) -> list[tuple[str, int | None]]:
    """Parse REDengine JSON paths such as a.b[0].c"""
    out: list[tuple[str, int | None]] = []
    for segment in str(path or "").split("."):
        if not segment:
            continue
        m = re.match(r"^([^\[]+)(?:\[(\d+)\])?$", segment)
        if not m:
            out.append((segment, None))
            continue
        name = m.group(1)
        idx = int(m.group(2)) if m.group(2) is not None else None
        out.append((name, idx))
    return out


def _ensure_list_size(values: list[Any], index: int) -> None:
    while len(values) <= index:
        values.append({})


def set_json_path(root: dict[str, Any], path: str, value: Any) -> None:
    """Set a dotted or indexed JSON path, creating containers as needed"""
    parts = _path_parts(path)
    if not parts:
        return
    obj: Any = root
    for i, (name, idx) in enumerate(parts):
        last = i == len(parts) - 1
        if idx is None:
            if last:
                if isinstance(obj, dict):
                    obj[name] = value
                return
            if not isinstance(obj, dict):
                return
            current = obj.get(name)
            if not isinstance(current, dict):
                current = {}
                obj[name] = current
            obj = current
        else:
            if not isinstance(obj, dict):
                return
            current = obj.get(name)
            if not isinstance(current, list):
                current = []
                obj[name] = current
            _ensure_list_size(current, idx)
            if last:
                current[idx] = value
                return
            if not isinstance(current[idx], dict):
                current[idx] = {}
            obj = current[idx]


def _handled_payload_path(root: dict[str, Any], path: str) -> str:
    """Map editable paths through preserved HandleId/Data wrappers"""
    parts = _path_parts(path)
    if not parts or not isinstance(root, dict):
        return path
    name, idx = parts[0]
    if idx is None:
        current = root.get(name)
        if (
            isinstance(current, dict)
            and isinstance(current.get("Data"), dict)
            and len(parts) > 1
        ):
            return f"{name}.Data." + ".".join(
                f"{n}[{i}]" if i is not None else n for n, i in parts[1:]
            )
    else:
        arr = root.get(name)
        if isinstance(arr, list) and 0 <= idx < len(arr):
            current = arr[idx]
            if (
                isinstance(current, dict)
                and isinstance(current.get("Data"), dict)
                and len(parts) > 1
            ):
                return f"{name}[{idx}].Data." + ".".join(
                    f"{n}[{i}]" if i is not None else n for n, i in parts[1:]
                )
    return path


def set_export_socket_path(root: dict[str, Any], path: str, value: Any) -> None:
    """Set a socket-link path through owned-payload wrappers"""
    set_json_path(root, _handled_payload_path(root, path), value)


# NodeSocket.links scans every link of the tree, so whole-graph encodes index each
# tree's links by target socket once instead.
_LINKS_BY_TARGET: dict[int, dict[int, Any]] | None = None


@contextmanager
def indexed_socket_links():
    global _LINKS_BY_TARGET
    previous = _LINKS_BY_TARGET
    _LINKS_BY_TARGET = {}
    try:
        yield
    finally:
        _LINKS_BY_TARGET = previous


def _socket_links(socket: Any) -> list[Any]:
    if socket is None or not bool(getattr(socket, "is_linked", False)):
        return []
    if _LINKS_BY_TARGET is None:
        return list(getattr(socket, "links", []) or [])
    tree = getattr(socket, "id_data", None)
    key = tree.as_pointer() if tree is not None else 0
    by_target = _LINKS_BY_TARGET.get(key)
    if by_target is None:
        by_target = {}
        for link in getattr(tree, "links", ()) or ():
            by_target.setdefault(link.to_socket.as_pointer(), []).append(link)
        _LINKS_BY_TARGET[key] = by_target
    return list(by_target.get(socket.as_pointer(), ()))


def _link_source_handle(input_socket: bpy.types.NodeSocket) -> str:
    links = _socket_links(input_socket)
    visited = set()
    while links:
        link = links[0]
        source_node = getattr(link, "from_node", None)
        if source_node is None or id(source_node) in visited:
            break
        visited.add(id(source_node))
        if str(getattr(source_node, "bl_idname", "") or "") == "NodeReroute":
            inputs = list(getattr(source_node, "inputs", []) or [])
            links = _socket_links(inputs[0]) if inputs else []
            continue
        if bool(get_attr(source_node, "red_pseudo", False)):
            # Editor-only boundary/group nodes carry the real runtime source on their socket.
            handle = str(
                get_attr(getattr(link, "from_socket", None), "red_source_handle", "")
                or ""
            )
        else:
            handle = str(get_attr(source_node, "red_handle_id", "") or "")
        if handle:
            return handle
        break
    return str(get_attr(input_socket, "red_source_handle", "") or "")


def _encode_link_wrapper(input_socket: bpy.types.NodeSocket) -> dict[str, Any]:
    link_type = str(get_attr(input_socket, "red_link_type", "") or "")
    source_handle = _link_source_handle(input_socket)
    wrapper: dict[str, Any] = {"$type": link_type or "animPoseLink"}
    if source_handle:
        wrapper["node"] = {"HandleRefId": str(source_handle)}
    else:
        wrapper["node"] = None
    return wrapper


def _iter_exportable_input_sockets(
    node: bpy.types.Node,
) -> Iterable[bpy.types.NodeSocket]:
    for sock in getattr(node, "inputs", []) or []:
        if not bool(get_attr(sock, "red_exportable", True)):
            continue
        if str(get_attr(sock, "red_socket_role", "") or "") not in {"", "input"}:
            continue
        if str(get_attr(sock, "red_edge_semantics", "") or "dataflow") != "dataflow":
            continue
        path = str(get_attr(sock, "red_json_path", "") or "")
        link_type = str(get_attr(sock, "red_link_type", "") or "")
        if path and link_type:
            yield sock


def _json_path_get(root: Any, path: str) -> tuple[bool, Any]:
    def resolve(use_wrappers: bool) -> tuple[bool, Any]:
        obj = root
        parts = _path_parts(path)
        for pos, (name, idx) in enumerate(parts):
            if idx is None:
                if not isinstance(obj, dict) or name not in obj:
                    return False, None
                obj = obj[name]
            else:
                if not isinstance(obj, dict):
                    return False, None
                arr = obj.get(name)
                if not isinstance(arr, list) or idx < 0 or idx >= len(arr):
                    return False, None
                obj = arr[idx]
            if (
                use_wrappers
                and pos < len(parts) - 1
                and isinstance(obj, dict)
                and isinstance(obj.get("Data"), dict)
            ):
                obj = obj.get("Data")
        return True, obj

    ok, value = resolve(False)
    if ok:
        return ok, value
    return resolve(True)
