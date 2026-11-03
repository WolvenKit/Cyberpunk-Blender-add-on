
import bpy

from ...animation.model.animgraph.constants import ANIMGRAPH_TREE_ID


def get_active_rig(context):
    objects = context.scene.objects
    index = context.scene.dangle_active_rig_index
    if 0 <= index < len(objects):
        obj = objects[index]
        if obj.type == "ARMATURE" and obj.dangle_state.is_dangle_rig:
            return obj
    return None


def get_active_dangle_node(context):
    rig = get_active_rig(context)
    if rig is None:
        return None
    state = rig.dangle_state
    index = state.active_dangle_node
    if 0 <= index < len(state.dangle_nodes):
        return state.dangle_nodes[index]
    return None


def get_active_chain(context):
    dangle_node = get_active_dangle_node(context)
    if dangle_node is None:
        return None
    index = dangle_node.active_chain
    if 0 <= index < len(dangle_node.chains):
        return dangle_node.chains[index]
    return None


def root_graph_tree(tree: bpy.types.NodeTree | None) -> bpy.types.NodeTree | None:
    current = tree
    visited: set[int] = set()
    while current is not None:
        try:
            pointer = int(current.as_pointer())
        except ReferenceError:
            pointer = id(current)
        if pointer in visited:
            break
        visited.add(pointer)
        parent_name = str(current.get("red_parent_graph", "") or "")
        if not parent_name:
            break
        parent = bpy.data.node_groups.get(parent_name)
        if parent is None:
            break
        current = parent
    return current


def rig_for_graph_tree(
    tree: bpy.types.NodeTree | None,
) -> bpy.types.Object | None:
    root = root_graph_tree(tree)
    if root is None or getattr(root, "bl_idname", "") != ANIMGRAPH_TREE_ID:
        return None
    rig_name = str(root.get("cp77_dangle_rig", "") or "")
    rig = bpy.data.objects.get(rig_name) if rig_name else None
    if rig is None or getattr(rig, "type", "") != "ARMATURE":
        return None
    return rig


def rig_for_context(context: bpy.types.Context) -> bpy.types.Object | None:
    space = getattr(context, "space_data", None)
    tree = getattr(space, "node_tree", None) if space is not None else None
    return rig_for_graph_tree(tree)
