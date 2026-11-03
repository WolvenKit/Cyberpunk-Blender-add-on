from __future__ import annotations

from ...animation.model.animgraph.constants import ANIM_NODE_PREFIX
from ...core.log import get_logger, log_once
from . import sm_records
from .sockets import bind_red_socket

_LOG = get_logger(__name__)

NEW_ROW = "+ new transition"

ROW_SOCKET_ID = "REDengine_AnimGraphSocket_TransitionOut"
IN_SOCKET_ID = "REDengine_AnimGraphSocket_Transition"
IN_NAME = "In"
NEW_NAME = "T+"
IN_LINK_LIMIT = 4095
SUMMARY_LIMIT = 48
SELF_LABEL = "self"
NO_TARGET_LABEL = "(no target)"
SELECT_OPERATOR = "redengine.sm_select_transition"

STATE_MACHINE_TYPES = frozenset(
    {
        f"{ANIM_NODE_PREFIX}StateMachine",
        f"{ANIM_NODE_PREFIX}LocomotionMachine",
    }
)
_STATE_LABEL_PREFIX = "State: "


def is_state_machine(node) -> bool:
    return str(getattr(node, "red_type", "") or "") in STATE_MACHINE_TYPES


def row_name(index: int) -> str:
    return f"T{index}"


def clip_summary(text: str) -> str:
    """text cut to 47 characters plus an ellipsis when longer than 48"""
    if len(text) <= SUMMARY_LIMIT:
        return text
    return text[: SUMMARY_LIMIT - 1] + "\u2026"


def _states_tree(node):
    """The tree holding the states that node's rows target"""
    if is_state_machine(node):
        return getattr(node, "node_tree", None)
    return getattr(node, "id_data", None)


def target_label(node, rec) -> str:
    """Display name of rec's target state"""
    handle = str(rec.target_handle or "")
    if not handle:
        return NO_TARGET_LABEL
    if not is_state_machine(node) and handle == str(
        getattr(node, "red_handle_id", "") or ""
    ):
        return SELF_LABEL
    tree = _states_tree(node)
    for other in getattr(tree, "nodes", ()) or ():
        if (
            getattr(other, "red_pseudo", False)
            or getattr(other, "red_handle_id", "") != handle
        ):
            continue
        label = str(getattr(other, "label", "") or "")
        label = label.removeprefix(_STATE_LABEL_PREFIX)
        return label or handle
    return handle


def row_text(node, index: int) -> tuple[str, str]:
    """(button text, full text) for row index of node"""
    rec = node.red_transitions[index]
    try:
        text = sm_records.summary(rec)
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("row_text", type(error).__name__),
            "row text: fell back after %s",
            error,
            exc_info=True,
        )
        text = "?"
    target = target_label(node, rec)
    return f"{clip_summary(text)}  to {target}", f"{text}  to {target}"


def draw_row(socket, _context, layout, node, text) -> None:
    """Draw one row socket (see REDengine_AnimGraphSocket_TransitionOut.draw)"""
    index = int(getattr(socket, "red_row_index", -1))
    records = getattr(node, "red_transitions", None)
    if index < 0 or records is None:
        layout.label(text=NEW_ROW)
        return
    if index >= len(records):
        layout.label(text=text)
        return
    button, _full = row_text(node, index)
    if not records[index].enabled:
        layout.active = False
    op = layout.operator(
        SELECT_OPERATOR,
        text=button,
        depress=(index == node.red_transitions_index),
        emboss=True,
    )
    op.node_name = node.name
    op.tree_name = node.id_data.name
    op.index = index


def _bind(socket, node, role: str) -> None:
    bind_red_socket(
        socket,
        role=role,
        owner_handle=str(getattr(node, "red_handle_id", "") or ""),
        field_name="transitions",
        exportable=False,
        edge_semantics="transition_summary",
        pseudo=True,
    )


def _ensure_in_socket(node) -> None:
    for sock in node.inputs:
        if sock.name == IN_NAME and sock.bl_idname == IN_SOCKET_ID:
            return
    sock = node.inputs.new(IN_SOCKET_ID, IN_NAME)
    sock.link_limit = IN_LINK_LIMIT
    _bind(sock, node, "input")


def sync_transition_sockets(node) -> None:
    """Make node.outputs end with a transition socket per record and T+"""
    if node is None or is_state_machine(node):
        return
    outputs = node.outputs
    wanted = [row_name(i) for i in range(len(node.red_transitions))] + [NEW_NAME]
    wanted_set = set(wanted)

    by_name = {}
    for sock in list(outputs):
        if sock.bl_idname != ROW_SOCKET_ID:
            continue
        if sock.name in wanted_set and sock.name not in by_name:
            by_name[sock.name] = sock
        else:
            outputs.remove(sock)
    for name in wanted:
        if name not in by_name:
            sock = outputs.new(ROW_SOCKET_ID, name)
            _bind(sock, node, "output")
            by_name[name] = sock

    tail = list(outputs)[len(outputs) - len(wanted) :]
    if any(sock != by_name[name] for sock, name in zip(tail, wanted)):
        # Moving each row to the end in order leaves them last, in ``wanted`` order.
        for name in wanted:
            current = next(
                i for i, other in enumerate(outputs) if other == by_name[name]
            )
            outputs.move(current, len(outputs) - 1)
    for position, name in enumerate(wanted):
        sock = by_name[name]
        row_index = -1 if name == NEW_NAME else position
        if sock.red_row_index != row_index:
            sock.red_row_index = row_index

    _ensure_in_socket(node)


def remove_transition_sockets(node) -> None:
    """Remove node's row sockets (T<i> / T+) and its In socket"""
    if node is None:
        return
    for sock in [s for s in node.outputs if s.bl_idname == ROW_SOCKET_ID]:
        node.outputs.remove(sock)
    for sock in [
        s for s in node.inputs if s.bl_idname == IN_SOCKET_ID and s.name == IN_NAME
    ]:
        node.inputs.remove(sock)
