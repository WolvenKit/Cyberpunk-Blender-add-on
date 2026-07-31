from typing import Any, List, Optional, Tuple

import bpy

from ...blender.animgraph.access import get_attr
from ...blender.animgraph import variables


def root_tree(tree: Optional[bpy.types.NodeTree]) -> Optional[bpy.types.NodeTree]:
    if tree is None:
        return None
    try:
        return variables.root_tree_for(tree) or tree
    except Exception:
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
        return []
