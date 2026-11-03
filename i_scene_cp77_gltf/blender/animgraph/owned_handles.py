from __future__ import annotations

import copy
from collections.abc import Iterable, Sequence
from typing import Any

from ...assetio import animgraph_json as json_io
from ...core.log import get_logger, log_once
from . import variables
from .access import get_attr, get_idprop

_LOG = get_logger(__name__)

_HANDLE_IDPROP_KEYS = (
    "red_direct_conn_source_handle_id",
    "red_math_expression_handle",
)
_JSON_IDPROP_KEYS = (
    "red_preserved_export_fields_json",
    "red_direct_conn_source_json",
    "red_point_constraint_input_transforms_json",
)


def copied_wrapper_data(wrapper: Any) -> dict:
    if not isinstance(wrapper, dict):
        return {}
    data = wrapper.get("Data")
    return copy.deepcopy(data) if isinstance(data, dict) else {}


def related_trees(node: Any) -> Iterable[Any]:
    tree = get_attr(node, "id_data", None)
    if tree is None:
        return ()
    try:
        root = variables.root_tree_for(tree) or tree
        return tuple(variables.related_trees(root) or (root,))
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("related_trees", type(error).__name__),
            "related trees: fell back after %s",
            error,
            exc_info=True,
        )
        return (tree,)


def collect_numeric_handles(value: Any, used: set[int]) -> None:
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key in ("HandleId", "HandleRefId"):
                text = str(current.get(key, "") or "")
                if text.isdigit():
                    used.add(int(text))
            stack.extend(current.values())
        elif isinstance(current, (list, tuple)):
            stack.extend(current)


def collect_json_handles(text: Any, used: set[int]) -> None:
    if not text:
        return
    try:
        collect_numeric_handles(json_io.loads(str(text)), used)
    except (TypeError, ValueError):
        pass


def used_handle_ids(
    node: Any,
    *,
    extra_idprop_keys: Sequence[str] = (),
    extra_json_keys: Sequence[str] = (),
) -> set[int]:
    used: set[int] = set()
    idprop_keys = (*_HANDLE_IDPROP_KEYS, *extra_idprop_keys)
    json_keys = (*_JSON_IDPROP_KEYS, *extra_json_keys)
    for tree in related_trees(node):
        # Tree-level metadata holds handles too (the variable container, root output, source metadata).
        try:
            tree_keys = [str(key) for key in tree.keys()]
        except (AttributeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("used_handle_ids 1", type(error).__name__),
                "used handle ids: fell back after %s",
                error,
                exc_info=True,
            )
            tree_keys = []
        for key in tree_keys:
            if key.endswith("_handle"):
                text = str(get_idprop(tree, key, "") or "")
                if text.isdigit():
                    used.add(int(text))
            elif key.endswith("_json"):
                collect_json_handles(get_idprop(tree, key, ""), used)
        for variable in get_attr(tree, "variables", ()) or ():
            text = str(get_attr(variable, "handle_id", "") or "")
            if text.isdigit():
                used.add(int(text))
        for item in get_attr(tree, "nodes", ()) or ():
            values = [get_attr(item, "red_handle_id", "")]
            values.extend(get_idprop(item, key, "") for key in idprop_keys)
            for value in values:
                text = str(value or "")
                if text.isdigit():
                    used.add(int(text))
            # Every adapter keeps its owned wrappers in a *_json idprop; scan them all so a
            # newly allocated id can never collide with a handle held by another node.
            try:
                stored_keys = {
                    str(key) for key in item.keys() if str(key).endswith("_json")
                }
            except (AttributeError, TypeError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    ("used_handle_ids 2", type(error).__name__),
                    "used handle ids: fell back after %s",
                    error,
                    exc_info=True,
                )
                stored_keys = set()
            for key in stored_keys.union(json_keys):
                collect_json_handles(get_idprop(item, key, ""), used)
            for prop in get_attr(item, "red_properties", ()) or ():
                for value in (
                    get_attr(prop, "struct_handle_id", ""),
                    get_attr(prop, "struct_ref_id", ""),
                ):
                    text = str(value or "")
                    if text.isdigit():
                        used.add(int(text))
                collect_json_handles(get_attr(prop, "raw_json", ""), used)
    return used


def allocate_owned_handle_ids(
    node: Any,
    count: int = 1,
    *,
    extra_idprop_keys: Sequence[str] = (),
    extra_json_keys: Sequence[str] = (),
) -> tuple[str, ...]:
    if count <= 0:
        return ()
    used = used_handle_ids(
        node,
        extra_idprop_keys=extra_idprop_keys,
        extra_json_keys=extra_json_keys,
    )
    next_id = max(used) + 1 if used else 1
    result = []
    while len(result) < count:
        if next_id not in used:
            result.append(str(next_id))
        next_id += 1
    return tuple(result)


def allocate_owned_handle_id(node: Any) -> str:
    return allocate_owned_handle_ids(node, 1)[0]
