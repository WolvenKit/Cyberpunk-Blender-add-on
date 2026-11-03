<<<<<<< Updated upstream
from typing import Any, List, Optional, Tuple

import bpy

from ...blender.animgraph.access import get_attr
from ...blender.animgraph import variables


def root_tree(tree: Optional[bpy.types.NodeTree]) -> Optional[bpy.types.NodeTree]:
=======
from typing import Any

import bpy

from ...blender.animgraph import variables
from ...blender.animgraph.access import get_attr
from ...core.log import debug_exception, get_logger, log_once

_LOG = get_logger(__name__)


def root_tree(tree: bpy.types.NodeTree | None) -> bpy.types.NodeTree | None:
>>>>>>> Stashed changes
    if tree is None:
        return None
    try:
        return variables.root_tree_for(tree) or tree
    except Exception:
<<<<<<< Updated upstream
        return tree


def node_sort_key(node: Any) -> Tuple[int, int, float, float, str]:
    handle = str(get_attr(node, 'red_handle_id', '') or '')
    numeric = handle.isdigit()
    value = int(handle) if numeric else 0
    try:
        location = getattr(node, 'location', None)
        x = float(getattr(location, 'x', 0.0))
        y = float(getattr(location, 'y', 0.0))
    except Exception:
        x = 0.0
        y = 0.0
    return (0 if numeric else 1, value, x, y, str(getattr(node, 'name', '')))


def tree_nodes(tree: bpy.types.NodeTree) -> List[bpy.types.Node]:
    try:
        return list(getattr(tree, 'nodes', []) or [])
    except Exception:
=======
        debug_exception(
            _LOG, "Could not find the root AnimGraph tree; using the tree itself"
        )
        return tree


def node_sort_key(node: Any) -> tuple[int, int, int, int, float, float, str]:
    # Imported nodes keep their source container position; new nodes follow by handle.
    try:
        source_index = int(node.get("red_source_container_index", -1))
    except (AttributeError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("node_sort_key", type(error).__name__),
            "node sort key: fell back after %s",
            error,
            exc_info=True,
        )
        source_index = -1
    handle = str(get_attr(node, "red_handle_id", "") or "")
    numeric = handle.isdigit()
    value = int(handle) if numeric else 0
    try:
        location = getattr(node, "location", None)
        x = float(getattr(location, "x", 0.0))
        y = float(getattr(location, "y", 0.0))
    except (ReferenceError, TypeError, ValueError):
        x = 0.0
        y = 0.0
    return (
        0 if source_index >= 0 else 1,
        max(source_index, 0),
        0 if numeric else 1,
        value,
        x,
        y,
        str(getattr(node, "name", "")),
    )


def tree_nodes(tree: bpy.types.NodeTree) -> list[bpy.types.Node]:
    try:
        return list(getattr(tree, "nodes", []) or [])
    except Exception:
        debug_exception(_LOG, "Could not list the tree's nodes; treating it as empty")
>>>>>>> Stashed changes
        return []
