from __future__ import annotations

import bpy

from ....blender.animgraph import sm_edit, sm_overlay, sm_sockets
from ....blender.operator_results import OperationResult

_LISTED_LIMIT = 12


def find_node(context, tree_name: str, node_name: str):
    """The node named node_name in tree tree_name, or in the edited tree when tree_name is empty"""
    tree = bpy.data.node_groups.get(tree_name) if tree_name else None
    if tree is None:
        space = getattr(context, "space_data", None)
        tree = getattr(space, "edit_tree", None)
    nodes = getattr(tree, "nodes", None)
    return nodes.get(node_name) if nodes is not None and node_name else None


def context_state_machine(context):
    """The state machine whose states the sidebar lists, or None"""
    node = getattr(context, "active_node", None)
    space = getattr(context, "space_data", None)
    if sm_sockets.is_state_machine(node):
        sm = node
    else:
        tree = (
            getattr(node, "id_data", None)
            if node is not None
            else getattr(space, "edit_tree", None)
        )
        sm = sm_overlay.state_machine_of(tree, space)
    if (
        sm is None
        or not getattr(sm, "red_sm_records", False)
        or getattr(sm, "node_tree", None) is None
    ):
        return None
    return sm


def editable_state_machine(context, tree_name: str, node_name: str):
    if not node_name:
        return context_state_machine(context)
    sm = find_node(context, tree_name, node_name)
    return (
        sm
        if sm_sockets.is_state_machine(sm) and getattr(sm, "red_sm_records", False)
        else None
    )


def count_text(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _listed(lines: list, texts: list) -> None:
    lines.extend(f"  {text}" for text in texts[:_LISTED_LIMIT])
    if len(texts) > _LISTED_LIMIT:
        lines.append(f"  ... and {len(texts) - _LISTED_LIMIT} more")


def delete_state_message(sm, state) -> str:
    """The confirmation text for deleting state"""
    deleted = sm_edit.state_delete_preview(sm, state)
    retargeted = sm_edit.state_retarget_preview(sm, state)
    name = sm_edit.source_label(state)
    if deleted:
        lines = [
            f'Delete state "{name}" and its {count_text(len(deleted), "transition")}:'
        ]
        _listed(lines, deleted)
    else:
        lines = [f'Delete state "{name}"? It has no transitions.']
    if retargeted:
        verb = "loses its" if len(retargeted) == 1 else "lose their"
        lines.append(
            f"{count_text(len(retargeted), 'transition')} from other states {verb} target:"
        )
        _listed(lines, retargeted)
    return "\n".join(lines)


def missing_state_message(sm, index: int) -> str:
    """The confirmation text for dropping a listed state whose node was deleted"""
    handle = sm_edit.missing_state_handle(sm, index)
    retargeted = sm_edit.missing_state_preview(sm, index)
    lines = [f"Remove state {handle}? Its node was deleted."]
    if retargeted:
        verb = "loses its" if len(retargeted) == 1 else "lose their"
        lines.append(f"{count_text(len(retargeted), 'transition')} {verb} target:")
        _listed(lines, retargeted)
    return "\n".join(lines)


def apply_edit(function, *args) -> OperationResult:
    """Run one sm_edit change, turning its validation errors into a cancelled result"""
    try:
        function(*args)
    except (ValueError, IndexError) as exc:
        return OperationResult.cancelled(str(exc) or "Invalid edit", error=exc)
    return OperationResult.finished()


def select_transition(node, index: int) -> OperationResult:
    records = getattr(node, "red_transitions", None)
    if records is None or not 0 <= index < len(records):
        return OperationResult.cancelled("Transition not found", "WARNING")
    node.red_transitions_index = index
    # Like a click on a node: only this node of its tree ends up selected, and active.
    for other in node.id_data.nodes:
        if other != node and other.select:
            other.select = False
    node.select = True
    node.id_data.nodes.active = node
    return OperationResult.finished()


def transition_description(node, index: int) -> str:
    records = getattr(node, "red_transitions", None)
    if records is None or not 0 <= index < len(records):
        return "Select this transition"
    return sm_sockets.row_text(node, index)[1]


def delete_selected_state(sm) -> OperationResult:
    index = sm.red_sm_states_index
    state = sm_edit.state_for_ref(sm, index)
    missing = "" if state is not None else sm_edit.missing_state_handle(sm, index)
    try:
        if state is not None:
            deleted = sm_edit.delete_state(sm, state)
            return OperationResult.finished(
                f"Deleted the state and {count_text(len(deleted), 'transition')}"
            )
        if missing:
            cleared = sm_edit.remove_missing_state(sm, index)
            return OperationResult.finished(
                f"Removed missing state {missing}; {count_text(cleared, 'transition')} lost their target"
            )
    except (ValueError, IndexError) as exc:
        return OperationResult.cancelled(str(exc), error=exc)
    return OperationResult.cancelled("No state selected", "ERROR_INVALID_CONTEXT")
