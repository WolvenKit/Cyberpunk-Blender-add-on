from typing import Any

NEW_PREFIX = "new:"
_ID_KEYS = ("HandleId", "HandleRefId")


def _walk(root: Any):
    """Yield every dict in depth-first document order"""
    stack: list[Any] = [root]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            yield current
            children = [v for v in current.values() if isinstance(v, (dict, list))]
        elif isinstance(current, list):
            children = [v for v in current if isinstance(v, (dict, list))]
        else:
            continue
        stack.extend(reversed(children))


def finalize_new_handles(root_chunk: dict[str, Any]) -> dict[str, str]:
    """Replace new: handle ids in place and return the mapping to numeric ids"""
    maximum = 0
    order: list[str] = []
    seen = set()
    for value in _walk(root_chunk):
        for key in _ID_KEYS:
            handle = value.get(key)
            if not isinstance(handle, str):
                continue
            if handle.startswith(NEW_PREFIX):
                if handle not in seen:
                    seen.add(handle)
                    order.append(handle)
            elif key == "HandleId" and handle.isascii() and handle.isdecimal():
                maximum = max(maximum, int(handle))
    mapping = {handle: str(maximum + 1 + index) for index, handle in enumerate(order)}
    if mapping:
        for value in _walk(root_chunk):
            for key in _ID_KEYS:
                handle = value.get(key)
                if isinstance(handle, str) and handle in mapping:
                    value[key] = mapping[handle]
    return mapping
