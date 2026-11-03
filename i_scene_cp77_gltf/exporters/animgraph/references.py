<<<<<<< Updated upstream
from typing import Any, Dict, List, Optional

from .values import clone_json

def _is_full_handle_entry(value: Any) -> bool:
    return isinstance(value, dict) and bool(value.get('HandleId')) and isinstance(value.get('Data'), dict)

def _is_ref_handle_entry(value: Any) -> bool:
    return isinstance(value, dict) and bool(value.get('HandleRefId')) and 'Data' not in value

def _entry_handle_value(value: Any) -> str:
    if not isinstance(value, dict):
        return ''
    return str(value.get('HandleId', '') or value.get('HandleRefId', '') or '')

def _collect_full_handle_entries(value: Any, out: Dict[str, Dict[str, Any]]) -> None:
    if isinstance(value, dict):
        if _is_full_handle_entry(value):
            handle = str(value.get('HandleId') or '')
            if handle and handle not in out:
                out[handle] = value
        for child in value.values():
            _collect_full_handle_entries(child, out)
    elif isinstance(value, list):
        for child in value:
            _collect_full_handle_entries(child, out)
=======
from typing import Any

from ...assetio.values import handle_id
from .values import clone_json


def _is_full_handle_entry(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and bool(value.get("HandleId"))
        and isinstance(value.get("Data"), dict)
    )


def _is_ref_handle_entry(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and bool(value.get("HandleRefId"))
        and "Data" not in value
    )


def _collect_full_handle_entries(value: Any, out: dict[str, dict[str, Any]]) -> None:
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if _is_full_handle_entry(current):
                handle = str(current.get("HandleId") or "")
                if handle and handle not in out:
                    out[handle] = current
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)

>>>>>>> Stashed changes

def _is_link_wrapper(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
<<<<<<< Updated upstream
    link_type = str(value.get('$type', '') or '')
    return bool(link_type) and link_type.startswith('anim') and link_type.endswith('Link') and 'node' in value

def normalize_inline_first_references(root_entry: Dict[str, Any], extra_entries: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Rewrite handle references into WolvenKit inline-first shape."""
    handle_map: Dict[str, Dict[str, Any]] = {}
    _collect_full_handle_entries(root_entry, handle_map)


=======
    link_type = str(value.get("$type", "") or "")
    return (
        bool(link_type)
        and link_type.startswith("anim")
        and link_type.endswith("Link")
        and "node" in value
    )


def normalize_inline_first_references(
    root_entry: dict[str, Any], extra_entries: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Rewrite handle references into WolvenKit inline-first shape"""
    handle_map: dict[str, dict[str, Any]] = {}
    _collect_full_handle_entries(root_entry, handle_map)

>>>>>>> Stashed changes
    if extra_entries:
        _collect_full_handle_entries(extra_entries, handle_map)

    stats = {
<<<<<<< Updated upstream
        'knownHandles': len(handle_map),
        'fullEntries': 0,
        'refEntries': 0,
        'linkInlined': 0,
        'linkRefs': 0,
        'repeatEntriesCollapsed': 0,
        'unknownRefs': 0,
        'cycleRefs': 0,
    }
    seen: set = set()
    stack: set = set()

    def normalize_value(value: Any) -> Any:
        if _is_full_handle_entry(value):
            return normalize_entry(value)
        if _is_ref_handle_entry(value):


            handle = _entry_handle_value(value)
            if handle and handle not in handle_map:
                stats['unknownRefs'] += 1
            stats['refEntries'] += 1
            return {'HandleRefId': handle} if handle else value
        if isinstance(value, dict):
            if _is_link_wrapper(value):
                node_ref = value.get('node')
                if isinstance(node_ref, dict):
                    if _is_full_handle_entry(node_ref):
                        value['node'] = normalize_entry(node_ref)
                    else:
                        target = str(node_ref.get('HandleRefId', '') or node_ref.get('HandleId', '') or '')
                        if target:
                            value['node'] = inline_or_ref(target)
                        else:
                            value['node'] = None
                elif node_ref is not None:
                    value['node'] = None


                for key, child in list(value.items()):
                    if key == 'node':
                        continue
                    value[key] = normalize_value(child)
                return value
            for key, child in list(value.items()):
                value[key] = normalize_value(child)
            return value
        if isinstance(value, list):
            return [normalize_value(child) for child in value]
        return value

    def normalize_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        handle = str(entry.get('HandleId', '') or '')
        if not handle or not isinstance(entry.get('Data'), dict):
            return entry
        if handle in seen:
            stats['repeatEntriesCollapsed'] += 1
            stats['refEntries'] += 1
            return {'HandleRefId': handle}
        if handle in stack:
            stats['cycleRefs'] += 1
            stats['refEntries'] += 1
            return {'HandleRefId': handle}
        seen.add(handle)
        stack.add(handle)
        stats['fullEntries'] += 1
        try:
            entry['Data'] = normalize_value(entry.get('Data'))
        finally:
            stack.discard(handle)
        return entry

    def inline_or_ref(target: str) -> Dict[str, Any]:
        target = str(target or '')
        if not target:
            return {'HandleRefId': target}
        if target in seen:
            stats['linkRefs'] += 1
            return {'HandleRefId': target}
        if target in stack:
            stats['cycleRefs'] += 1
            stats['linkRefs'] += 1
            return {'HandleRefId': target}
        source = handle_map.get(target)
        if source is None:
            stats['unknownRefs'] += 1
            stats['linkRefs'] += 1
            return {'HandleRefId': target}
        stats['linkInlined'] += 1
        return normalize_entry(clone_json(source))

    normalized = normalize_entry(root_entry)
    return {'root': normalized, 'stats': stats}
=======
        "knownHandles": len(handle_map),
        "fullEntries": 0,
        "refEntries": 0,
        "linkInlined": 0,
        "linkRefs": 0,
        "repeatEntriesCollapsed": 0,
        "unknownRefs": 0,
        "cycleRefs": 0,
    }
    seen: set[str] = set()
    active: set[str] = set()
    holder = {"root": root_entry}
    work = [("visit", holder, "root", root_entry)]

    while work:
        action, parent, key, value = work.pop()
        if action == "exit_handle":
            active.discard(str(value))
            continue

        if _is_full_handle_entry(value):
            handle = str(value.get("HandleId") or "")
            if handle in active:
                stats["cycleRefs"] += 1
                stats["refEntries"] += 1
                parent[key] = {"HandleRefId": handle}
                continue
            if handle in seen:
                stats["repeatEntriesCollapsed"] += 1
                stats["refEntries"] += 1
                parent[key] = {"HandleRefId": handle}
                continue
            seen.add(handle)
            active.add(handle)
            stats["fullEntries"] += 1
            parent[key] = value
            work.append(("exit_handle", parent, key, handle))
            work.append(("visit", value, "Data", value.get("Data")))
            continue

        if _is_ref_handle_entry(value):
            handle = handle_id(value)
            if handle and handle not in handle_map:
                stats["unknownRefs"] += 1
            stats["refEntries"] += 1
            parent[key] = {"HandleRefId": handle} if handle else value
            continue

        if isinstance(value, dict):
            parent[key] = value
            skipped = set()
            node_task = None
            if _is_link_wrapper(value):
                skipped.add("node")
                node_ref = value.get("node")
                if isinstance(node_ref, dict) and _is_full_handle_entry(node_ref):
                    node_task = ("visit", value, "node", node_ref)
                elif isinstance(node_ref, dict):
                    target = str(
                        node_ref.get("HandleRefId", "")
                        or node_ref.get("HandleId", "")
                        or ""
                    )
                    if not target:
                        value["node"] = None
                    elif target in active:
                        stats["cycleRefs"] += 1
                        stats["linkRefs"] += 1
                        value["node"] = {"HandleRefId": target}
                    elif target in seen:
                        stats["linkRefs"] += 1
                        value["node"] = {"HandleRefId": target}
                    elif target not in handle_map:
                        stats["unknownRefs"] += 1
                        stats["linkRefs"] += 1
                        value["node"] = {"HandleRefId": target}
                    else:
                        stats["linkInlined"] += 1
                        node_task = (
                            "visit",
                            value,
                            "node",
                            clone_json(handle_map[target]),
                        )
                elif node_ref is not None:
                    value["node"] = None
            items = tuple(value.items())
            for child_key, child in reversed(items):
                if child_key not in skipped:
                    work.append(("visit", value, child_key, child))
            if node_task is not None:
                work.append(node_task)
            continue

        if isinstance(value, list):
            parent[key] = value
            for index in range(len(value) - 1, -1, -1):
                work.append(("visit", value, index, value[index]))
            continue

        parent[key] = value

    return {"root": holder["root"], "stats": stats}
>>>>>>> Stashed changes
