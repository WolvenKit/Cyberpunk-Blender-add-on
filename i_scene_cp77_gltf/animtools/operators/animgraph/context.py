from ....animation.model.animgraph.constants import ANIMGRAPH_TREE_ID


def animgraph_editor_poll(context) -> bool:
    space = context.space_data
    if space is None or space.type != "NODE_EDITOR":
        return False
    return getattr(space.node_tree, "bl_idname", "") == ANIMGRAPH_TREE_ID


def active_node(context, red_types):
    """(edited AnimGraph tree, its active node) when that node's $type is in red_types, else (None, None)"""
    space = getattr(context, "space_data", None)
    tree = getattr(space, "edit_tree", None) if space is not None else None
    nodes = getattr(tree, "nodes", None) if tree is not None else None
    node = getattr(nodes, "active", None) if nodes is not None else None
    if (
        tree is None
        or getattr(tree, "bl_idname", "") != ANIMGRAPH_TREE_ID
        or getattr(node, "red_type", "") not in red_types
    ):
        return None, None
    return tree, node


def active_tree(context):
    space = getattr(context, "space_data", None)
    tree = getattr(space, "edit_tree", None) if space is not None else None
    if tree is None:
        tree = getattr(space, "node_tree", None) if space is not None else None
    if tree is None or getattr(tree, "bl_idname", "") != ANIMGRAPH_TREE_ID:
        return None
    return tree


def active_curve_property(context, index):
    node = getattr(context, "active_node", None)
    if node is None:
        return None
    props = getattr(node, "red_properties", None)
    if props is None or index < 0 or index >= len(props):
        return None
    item = props[index]
    if item.value_kind != "CURVE_FLOAT":
        return None
    return item
