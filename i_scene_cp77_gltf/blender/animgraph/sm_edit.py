from __future__ import annotations

import bpy

from ...animation.model.animgraph import sm_conditions
from ...assetio import animgraph_json
from ...core.log import get_logger, log_once
from . import property_codec, sm_overlay, sm_records, sm_sockets
from .builder import build_node, new_handle_id
from .layout import estimated_node_size
from .sm_properties import BLEND_INTERPOLATOR_TYPE, REDengine_SMStateRef
from .sm_records import ANY_RED_TYPE, ENTRY_RED_TYPE, _pseudo_node

_LOG = get_logger(__name__)

STATE_RED_TYPE = "animAnimNode_State"
FROZEN_STATE_RED_TYPE = "animAnimNode_StateFrozen"
STATE_LABEL_PREFIX = "State: "
GROUP_LABEL = "ALL of"

# Condition types grouped as in the design's catalogue (menu order).
CONDITION_FAMILIES = (
    ("Group", (sm_conditions.GROUP,)),
    (
        "Animation",
        ("AnimEnd", "AnyAnimEnd", "AnimEvent", "FootPhaseEvent", "HasAnimation"),
    ),
    ("Events and time", ("ExternalEvent", "Timed")),
    ("Anim feature", ("IntFeature", "FloatFeature", "BoolFeature")),
    (
        "Anim feature edges",
        (
            "IntEdgeFeature",
            "IntEdgeFromToFeature",
            "IntEdgeToFeature",
            "IntEdgeGreaterFromZeroFeature",
            "BoolEdgeFeature",
        ),
    ),
    (
        "Graph variable",
        ("IntVariable", "FloatVariable", "BoolVariable", "ModifiedFloatVariable"),
    ),
    ("Other", ("WrapperValue",)),
)

# What the sidebar shows (and lets the user change) for each kind of row.
_DEFAULT_SECTIONS = frozenset({"target"})
_ENTRY_SECTIONS = frozenset(
    {"enabled", "forced_true", "target", "priority", "condition"}
)
_TRANSITION_SECTIONS = _ENTRY_SECTIONS | {"duration", "blend", "advanced"}


def is_state(node) -> bool:
    return (
        node is not None
        and getattr(node, "red_type", "") == STATE_RED_TYPE
        and not getattr(node, "red_pseudo", False)
    )


def is_transition_owner(node) -> bool:
    """True for nodes whose red_transitions the sidebar edits (States, Entry, Any State, SM containers)"""
    if node is None or getattr(node, "red_transitions", None) is None:
        return False
    red_type = getattr(node, "red_type", "")
    return (
        is_state(node)
        or red_type in (sm_records.ENTRY_RED_TYPE, sm_records.ANY_RED_TYPE)
        or sm_sockets.is_state_machine(node)
    )


def container_of(node):
    """The state machine container node that node belongs to, or None"""
    if node is None:
        return None
    if sm_sockets.is_state_machine(node):
        return node
    return sm_overlay.state_machine_of(getattr(node, "id_data", None))


def states_tree(node):
    """The node tree holding the states that node's rows can target"""
    container = container_of(node)
    return getattr(container, "node_tree", None) if container is not None else None


def owner_node(struct):
    """The node holding struct, found by pointer"""
    tree = getattr(struct, "id_data", None)
    try:
        pointer = struct.as_pointer()
    except AttributeError as error:
        log_once(
            _LOG,
            "DEBUG",
            ("owner_node", type(error).__name__),
            "owner node: fell back after %s",
            error,
            exc_info=True,
        )
        return None
    state_ref = isinstance(struct, REDengine_SMStateRef)
    for node in getattr(tree, "nodes", ()) or ():
        for rec in () if state_ref else (getattr(node, "red_transitions", ()) or ()):
            if rec.as_pointer() == pointer:
                return node
            for cond in rec.conditions:
                if cond.as_pointer() == pointer:
                    return node
        for ref in getattr(node, "red_sm_states", ()) or ():
            if ref.as_pointer() == pointer:
                return node
    return None


def _sync(node) -> None:
    if node is not None:
        sm_sockets.sync_transition_sockets(node)


def list_name_for(owner) -> str:
    red_type = getattr(owner, "red_type", "")
    if red_type == sm_records.ENTRY_RED_TYPE:
        return "conditionalEntries"
    if red_type == sm_records.ANY_RED_TYPE:
        return "globalTransitions"
    return "transitions"


def _state_label(node) -> str:
    label = str(getattr(node, "label", "") or "")
    label = label.removeprefix(STATE_LABEL_PREFIX)
    return label


def state_choices(container) -> list:
    """(handle, label) for each state of container in state order"""
    tree = getattr(container, "node_tree", None)
    by_handle = {}
    for node in getattr(tree, "nodes", ()) or ():
        if not getattr(node, "red_pseudo", False) and getattr(
            node, "red_handle_id", ""
        ):
            by_handle.setdefault(node.red_handle_id, node)
    pairs = []
    for ref in getattr(container, "red_sm_states", ()) or ():
        node = by_handle.get(ref.handle)
        pairs.append(
            (ref.handle, (_state_label(node) if node is not None else "") or ref.handle)
        )
    counts: dict = {}
    for _handle, label in pairs:
        counts[label] = counts.get(label, 0) + 1
    return [
        (handle, label if counts[label] == 1 else f"{label} ({handle})")
        for handle, label in pairs
    ]


def state_ref_label(ref) -> str:
    """Display label of one red_sm_states entry (for the Target search)"""
    container = owner_node(ref)
    for handle, label in state_choices(container):
        if handle == ref.handle:
            return label
    return ref.handle


def target_name(rec) -> str:
    """The Target field's text for rec"""
    handle = rec.target_handle
    if not handle:
        return ""
    container = container_of(owner_node(rec))
    for choice, label in state_choices(container):
        if choice == handle:
            return label
    return handle


def set_target_name(rec, text: str) -> None:
    """Set rec's target from a Target field text (a choice label, or empty for none)"""
    text = str(text or "")
    try:
        if not text:
            set_target(rec, None)
            return
        container = container_of(owner_node(rec))
        for handle, label in state_choices(container):
            if text in (label, handle):
                node = _state_by_handle(container, handle)
                if node is not None:  # a listed state with no node cannot be targeted
                    set_target(rec, node)
                return
    except ValueError:
        pass  # a refused edit from the Target field leaves the target as it was


def _state_by_handle(container, handle: str):
    tree = getattr(container, "node_tree", None)
    for node in getattr(tree, "nodes", ()) or ():
        if is_state(node) and node.red_handle_id == handle:
            return node
    return None


def source_label(owner) -> str:
    """The "from" side of a row's header"""
    red_type = getattr(owner, "red_type", "")
    if red_type == sm_records.ENTRY_RED_TYPE:
        return "Entry"
    if red_type == sm_records.ANY_RED_TYPE:
        return "Any State"
    if sm_sockets.is_state_machine(owner):
        return "(no source state)"
    return _state_label(owner) or str(getattr(owner, "red_handle_id", "") or owner.name)


def sections(rec) -> set:
    """Which parts of rec the sidebar shows (see the design's Editing section)"""
    if rec.list_name == sm_records.DEFAULT_LIST:
        return set(_DEFAULT_SECTIONS)
    if rec.list_name == "conditionalEntries":
        return set(_ENTRY_SECTIONS)
    return set(_TRANSITION_SECTIONS)


def any_blend_editable(node) -> bool:
    """True when the Any State's shared blend exists, so a curve change is exported"""
    if getattr(node, "red_type", "") != sm_records.ANY_RED_TYPE:
        return False
    text = getattr(node, "red_sm_any_interpolator_json", "") or ""
    try:
        value = animgraph_json.loads(text) if text else None
    except ValueError:
        return False
    return isinstance(value, dict) and isinstance(value.get("Data"), dict)


def condition_label(short: str) -> str:
    return GROUP_LABEL if short == sm_conditions.GROUP else short


def _target_handle(owner, target_node) -> str:
    if target_node is None:
        return ""
    if not is_state(target_node) or not target_node.red_handle_id:
        raise ValueError(
            f"{getattr(target_node, 'name', target_node)!r} is not a state"
        )
    tree = states_tree(owner) if owner is not None else None
    if tree is not None and target_node.id_data != tree:
        raise ValueError(f"{target_node.name!r} is not a state of this state machine")
    return str(target_node.red_handle_id)


def add_transition(owner_node, target_node=None):
    """Append a new transition (a conditional entry on Entry, a global one on Any State)"""
    if sm_sockets.is_state_machine(owner_node):
        raise ValueError("add transitions on a state, Entry or Any State")
    target = _target_handle(owner_node, target_node)
    rec = owner_node.red_transitions.add()
    sm_records.record_from_wrapper(
        rec, None, list_name_for(owner_node), -1, target
    )  # assigns handles
    owner_node.red_transitions_index = len(owner_node.red_transitions) - 1
    _sync(owner_node)
    return rec


def delete_transition(owner_node, index: int) -> None:
    records = owner_node.red_transitions
    if not 0 <= index < len(records):
        raise IndexError(index)
    if records[index].list_name == sm_records.DEFAULT_LIST:
        raise ValueError(
            "the default-state row cannot be deleted; change its target instead"
        )
    records.remove(index)
    active = owner_node.red_transitions_index
    if active > index or active >= len(records):
        owner_node.red_transitions_index = max(0, active - 1)
    _sync(owner_node)


def _first_movable(records) -> int:
    """Rows above this index are default-state rows, which stay first"""
    first = 0
    while first < len(records) and records[first].list_name == sm_records.DEFAULT_LIST:
        first += 1
    return first


def can_move(owner_node, index: int, delta: int) -> bool:
    """True when move_transition(owner_node, index, delta) would move the row"""
    records = owner_node.red_transitions
    if (
        not 0 <= index < len(records)
        or records[index].list_name == sm_records.DEFAULT_LIST
    ):
        return False
    target = max(_first_movable(records), min(len(records) - 1, index + int(delta)))
    return target != index


def move_transition(owner_node, index: int, delta: int) -> int:
    """Move row index by delta in the export order and return its new index"""
    records = owner_node.red_transitions
    if not 0 <= index < len(records):
        raise IndexError(index)
    if records[index].list_name == sm_records.DEFAULT_LIST:
        raise ValueError("the default-state row stays first")
    first = _first_movable(records)
    if first and index == first and int(delta) < 0:
        raise ValueError("a row cannot move above the default-state row")
    new_index = max(first, min(len(records) - 1, index + int(delta)))
    if new_index != index:
        records.move(index, new_index)
    owner_node.red_transitions_index = new_index
    _sync(owner_node)
    return new_index


def set_target(rec, target_node) -> None:
    """Retarget rec"""
    owner = owner_node(rec)
    if target_node is None and rec.list_name == sm_records.DEFAULT_LIST:
        raise ValueError("the default-state row needs a target")
    rec.target_handle = _target_handle(owner, target_node)
    _sync(owner)


def _subtree_end(conditions, index: int) -> int:
    """One past the last entry of index's subtree"""
    depth = conditions[index].depth
    end = index + 1
    while end < len(conditions) and conditions[end].depth > depth:
        end += 1
    return end


def _check_index(rec, index: int, *, allow_root: bool = False) -> None:
    """Raise IndexError unless index names an entry"""
    if allow_root and index == -1:
        return
    count = 1 if bool(rec.condition_opaque_json) else len(rec.conditions)
    if not 0 <= index < count:
        raise IndexError(index)


def _check_type(short: str) -> None:
    if short not in sm_conditions.CONDITION_TYPES:
        raise ValueError(f"unknown condition type {short!r}")


def _begin_edit(rec) -> bool:
    """Replace a shared condition by an empty editable tree, returning True if it did"""
    if not bool(rec.condition_opaque_json):
        return False
    rec.conditions.clear()
    sm_records.clear_opaque_condition(rec)
    return True


def _insert(
    rec,
    position: int,
    short: str,
    depth: int,
    data: dict | None = None,
    handle: str | None = None,
):
    cond = rec.conditions.add()
    sm_records.fill_condition(cond, short, depth, handle or new_handle_id(), data)
    last = len(rec.conditions) - 1
    if position != last:
        rec.conditions.move(last, position)
    return rec.conditions[position]


def _replace_shared(rec, short: str) -> int:
    """Replace a shared condition by a new root short entry with default fields"""
    _begin_edit(rec)
    _insert(rec, 0, short, 0)
    rec.conditions_index = 0
    _sync(owner_node(rec))
    return 0


def wrap_in_all(rec, index: int) -> int:
    """Wrap the subtree at index in a new ALL-of group and return the group's index"""
    _check_index(rec, index)
    if bool(rec.condition_opaque_json):
        return _replace_shared(rec, sm_conditions.GROUP)
    end = _subtree_end(rec.conditions, index)
    depth = rec.conditions[index].depth
    for pos in range(index, end):
        rec.conditions[pos].depth += 1
    _insert(rec, index, sm_conditions.GROUP, depth)
    rec.conditions_index = index
    _sync(owner_node(rec))
    return index


def add_condition(rec, short: str, after_index: int = -1) -> int:
    """Add a short leaf as the last child of the group at after_index and return its index"""
    _check_type(short)
    _check_index(rec, after_index, allow_root=True)
    if bool(rec.condition_opaque_json):
        return _replace_shared(rec, short)
    conditions = rec.conditions
    if after_index < 0:
        if len(conditions) == 0:
            _insert(rec, 0, short, 0)
            rec.conditions_index = 0
            _sync(owner_node(rec))
            return 0
        after_index = 0
    if conditions[after_index].short != sm_conditions.GROUP:
        after_index = wrap_in_all(rec, after_index)
    position = _subtree_end(conditions, after_index)
    _insert(rec, position, short, conditions[after_index].depth + 1)
    rec.conditions_index = position
    _sync(owner_node(rec))
    return position


def remove_condition(rec, index: int) -> None:
    """Remove the entry at index and its subtree (a shared condition, index 0, is removed whole)"""
    _check_index(rec, index)
    if _begin_edit(rec):
        rec.conditions_index = 0
        _sync(owner_node(rec))
        return
    end = _subtree_end(rec.conditions, index)
    for pos in reversed(range(index, end)):
        rec.conditions.remove(pos)
    rec.conditions_index = max(0, min(index, len(rec.conditions) - 1))
    _sync(owner_node(rec))


def _spec_map(short: str) -> dict:
    return {spec.name: spec for spec in sm_conditions.CONDITION_TYPES.get(short, ())}


def change_condition_type(rec, index: int, short: str) -> None:
    """Change the entry at index to short, keeping its handle"""
    _check_type(short)
    _check_index(rec, index)
    if bool(rec.condition_opaque_json):
        _replace_shared(rec, short)
        return
    cond = rec.conditions[index]
    old_short = cond.short
    if old_short == short:
        return
    if old_short == sm_conditions.GROUP:
        end = _subtree_end(rec.conditions, index)
        for pos in reversed(range(index + 1, end)):
            rec.conditions.remove(pos)
        cond = rec.conditions[index]
    data = None
    if short != sm_conditions.GROUP:
        old_specs = _spec_map(old_short)
        current = {field.key: field for field in cond.fields}
        data = sm_conditions.default_condition_data(short)
        for spec in sm_conditions.CONDITION_TYPES[short]:
            old = old_specs.get(spec.name)
            field = current.get(spec.name)
            if (
                field is not None
                and old is not None
                and old.kind == spec.kind
                and old.enum_type == spec.enum_type
            ):
                data[spec.name] = property_codec.encode_simple_value(field)
    sm_records.fill_condition(
        cond, short, cond.depth, cond.handle_id or new_handle_id(), data
    )
    rec.conditions_index = index
    _sync(owner_node(rec))


DEFAULT_STATE_NAME = "State"
_STATE_GAP = 120.0
_PSEUDO_GAP = 80.0
_HIDDEN_SM_PROPERTIES = frozenset({"defaultStateIndex"})


def hidden_property_keys(node) -> set:
    """Generic node properties the property list does not draw for node"""
    if sm_sockets.is_state_machine(node) and getattr(node, "red_sm_records", False):
        return set(_HIDDEN_SM_PROPERTIES)
    return set()


def _is_frozen_state(node) -> bool:
    return getattr(node, "red_type", "") == FROZEN_STATE_RED_TYPE


def _require_state_machine(sm_node):
    tree = getattr(sm_node, "node_tree", None)
    if not sm_sockets.is_state_machine(sm_node) or tree is None:
        raise ValueError(
            f"{getattr(sm_node, 'name', sm_node)!r} is not a state machine"
        )
    return tree


def _require_state_of(sm_node, state_node):
    tree = _require_state_machine(sm_node)
    if not is_state(state_node) or not state_node.red_handle_id:
        raise ValueError(f"{getattr(state_node, 'name', state_node)!r} is not a state")
    if state_node.id_data != tree:
        raise ValueError(f"{state_node.name!r} is not a state of this state machine")
    return tree


def default_row(entry):
    """Entry's default-state row, or None"""
    for rec in getattr(entry, "red_transitions", ()) or ():
        if rec.list_name == sm_records.DEFAULT_LIST:
            return rec
    return None


def default_state_handle(sm_node) -> str:
    """Handle of the default state (the target of Entry's default row), or "" """
    tree = getattr(sm_node, "node_tree", None)
    rec = default_row(_pseudo_node(tree, ENTRY_RED_TYPE)) if tree is not None else None
    return str(rec.target_handle) if rec is not None else ""


def state_rows(sm_node) -> tuple:
    """(handle, label, missing, is_default) for each listed state, from one pass over the subtree"""
    tree = getattr(sm_node, "node_tree", None)
    states = set()
    for node in getattr(tree, "nodes", ()) or ():
        if is_state(node):
            states.add(node.red_handle_id)
    labels = dict(state_choices(sm_node))
    default = default_state_handle(sm_node)
    return tuple(
        (
            ref.handle,
            labels.get(ref.handle, ref.handle),
            ref.handle not in states,
            ref.handle == default,
        )
        for ref in getattr(sm_node, "red_sm_states", ()) or ()
    )


def state_for_ref(sm_node, index: int):
    """The State node at position index of sm_node.red_sm_states, or None"""
    refs = getattr(sm_node, "red_sm_states", ())
    if not 0 <= index < len(refs):
        return None
    return _state_by_handle(sm_node, refs[index].handle)


def _state_index(sm_node, handle: str) -> int:
    for index, ref in enumerate(sm_node.red_sm_states):
        if ref.handle == handle:
            return index
    return -1


def _unique_state_name(tree, base: str) -> str:
    taken = {_state_label(node) for node in tree.nodes if is_state(node)}
    name, suffix = base, 2
    while name in taken:
        name = f"{base} {suffix}"
        suffix += 1
    return name


def _name_state(node, name: str) -> None:
    node.label = STATE_LABEL_PREFIX + name
    for item in node.red_properties:
        if item.key == "name":
            item.string_value = name


def _fit_width(node) -> None:
    node.width = estimated_node_size(node)[0]


def _place_right_of(node, others) -> None:
    """Put node to the right of others, level with the highest of them"""
    others = [other for other in others if other is not None and other != node]
    if not others:
        node.location = (0.0, 0.0)
        return
    right = max(other.location.x + other.width for other in others)
    top = max(other.location.y for other in others)
    node.location = (right + _STATE_GAP, top)


def register_new_state(sm_node, state_node) -> None:
    """Make state_node one of its state machine's states"""
    _require_state_of(sm_node, state_node)
    handle = str(state_node.red_handle_id)
    index = _state_index(sm_node, handle)
    if index < 0:
        sm_node.red_sm_states.add().handle = handle
        index = len(sm_node.red_sm_states) - 1
    sm_node.red_sm_states_index = index
    _sync(state_node)


def add_state(sm_node, name: str = DEFAULT_STATE_NAME):
    """Add a new, empty State to sm_node, after its other states and to their right"""
    tree = _require_state_machine(sm_node)
    existing = sm_records.state_nodes(tree)
    unique = _unique_state_name(tree, str(name or DEFAULT_STATE_NAME))
    node = build_node(tree, "State")
    _name_state(node, unique)
    register_new_state(sm_node, node)
    _fit_width(node)
    _place_right_of(node, existing or [_pseudo_node(tree, ENTRY_RED_TYPE)])
    return node


def on_node_added(node) -> None:
    """Hook for the Add-node operator"""
    if sm_sockets.is_state_machine(node):
        scaffold_state_machine(node)
    elif is_state(node):
        container = sm_records.sm_container_for(getattr(node, "id_data", None))
        if sm_sockets.is_state_machine(container):
            register_new_state(container, node)


def _rebind_socket_handles(node, old: str, new: str) -> None:
    for sock in (*node.inputs, *node.outputs):
        for attr in ("red_owner_handle", "red_source_handle", "red_target_handle"):
            if getattr(sock, attr, None) == old:
                setattr(sock, attr, new)


# The handles of the tree the last copy landed in. Copying a whole tree calls
# Node.copy once per node, so reusing this set keeps that copy linear:
# (tree pointer, node count, last copy's name, last copy's pointer, handles).
_COPY_HANDLES: list = []


def _tree_handles(node) -> set:
    """The handles of every other node in node's tree (reused across a whole-tree copy)"""
    tree = node.id_data
    nodes = tree.nodes
    if _COPY_HANDLES:
        pointer, count, last_name, last_pointer, handles = _COPY_HANDLES
        last = nodes.get(last_name)
        if (
            pointer == tree.as_pointer()
            and len(nodes) == count + 1
            and last is not None
            and last.as_pointer() == last_pointer
        ):
            return handles
    own = node.as_pointer()
    return {
        str(getattr(other, "red_handle_id", "") or "")
        for other in nodes
        if other.as_pointer() != own
    }


def _remember_copy(node, handles: set) -> None:
    handles.add(str(getattr(node, "red_handle_id", "") or ""))
    _COPY_HANDLES[:] = [
        node.id_data.as_pointer(),
        len(node.id_data.nodes),
        node.name,
        node.as_pointer(),
        handles,
    ]


def on_node_copied(node, original) -> None:
    """Hook for Blender's node copy"""
    old = str(getattr(original, "red_handle_id", "") or "")
    if getattr(getattr(node, "id_data", None), "nodes", None) is None:
        return
    handles = _tree_handles(node)
    if not old or old not in handles:
        _remember_copy(node, handles)
        return
    new = new_handle_id()
    node.red_handle_id = new
    _rebind_socket_handles(node, old, new)
    _remember_copy(node, handles)
    for key in ("red_source_container_index", "red_source_unlisted"):
        if key in node:
            del node[key]
    for rec in getattr(node, "red_transitions", ()) or ():
        sm_records.renew_record(rec)
    if not is_state(node):
        return
    tree = getattr(node, "id_data", None)
    nodes = getattr(tree, "nodes", None)
    if nodes is None or nodes.get(node.name) != node:
        return  # e.g. the clipboard's temporary copy
    container = sm_records.sm_container_for(tree)
    if not (
        sm_sockets.is_state_machine(container)
        and getattr(container, "red_sm_records", False)
    ):
        return
    _name_state(
        node, _unique_state_name(tree, _state_label(node) or DEFAULT_STATE_NAME)
    )
    register_new_state(container, node)


def import_notes(sm_node) -> list:
    """The import notes kept on sm_node (e.g. a transition two states listed), one per line"""
    text = str(getattr(sm_node, "red_sm_import_notes", "") or "")
    return [line for line in text.splitlines() if line.strip()]


def clear_import_notes(sm_node) -> None:
    """Dismiss sm_node's import notes (the Graph Validator stops warning about them)"""
    sm_node.red_sm_import_notes = ""


def _row_description(owner, index: int) -> str:
    return f"{source_label(owner)}: {sm_sockets.row_text(owner, index)[1]}"


def transition_owners(sm_node) -> list:
    """Every node of sm_node holding transition rows (its subtree's owners, then itself)"""
    return [node for node in sm_node.node_tree.nodes if is_transition_owner(node)] + [
        sm_node
    ]


def state_delete_preview(sm_node, state_node) -> list:
    """Descriptions of the transitions delete_state would delete"""
    _require_state_of(sm_node, state_node)
    return [
        _row_description(state_node, i) for i in range(len(state_node.red_transitions))
    ]


def state_retarget_preview(sm_node, state_node) -> list:
    """Descriptions of the rows of other owners that would lose their target"""
    _require_state_of(sm_node, state_node)
    return _retarget_preview(sm_node, str(state_node.red_handle_id), state_node)


def _retarget_preview(sm_node, handle: str, skip=None) -> list:
    out = []
    for owner in transition_owners(sm_node):
        if owner == skip:
            continue
        for index, rec in enumerate(owner.red_transitions):
            if rec.target_handle != handle:
                continue
            if rec.list_name == sm_records.DEFAULT_LIST:
                out.append("Entry: default state")
            else:
                out.append(_row_description(owner, index))
    return out


def _subtrees(node) -> list:
    """node's subtree and every subtree nested in it, each before its children"""
    out, seen = [], set()
    stack = [getattr(node, "node_tree", None)]
    while stack:
        tree = stack.pop()
        if tree is None or tree.as_pointer() in seen:
            continue
        seen.add(tree.as_pointer())
        out.append(tree)
        stack.extend(getattr(child, "node_tree", None) for child in tree.nodes)
    return out


def delete_state(sm_node, state_node) -> list:
    """Delete state_node with its transitions and return their descriptions"""
    tree = _require_state_of(sm_node, state_node)
    deleted = state_delete_preview(sm_node, state_node)
    _forget_state(sm_node, str(state_node.red_handle_id), state_node)
    subtrees = _subtrees(state_node)
    tree.nodes.remove(state_node)
    for sub in subtrees:
        if sub.users == 0:
            bpy.data.node_groups.remove(sub)
    return deleted


def _forget_state(sm_node, handle: str, skip=None) -> int:
    """Clear every row targeting handle and drop its refs, returning the rows cleared"""
    cleared = 0
    for owner in transition_owners(sm_node):
        if owner == skip:
            continue
        changed = False
        for rec in owner.red_transitions:
            if rec.target_handle == handle:
                rec.target_handle = ""
                changed = True
                cleared += 1
        if changed:
            _sync(owner)
    refs = sm_node.red_sm_states
    for index in reversed(range(len(refs))):
        if refs[index].handle == handle:
            refs.remove(index)
    sm_node.red_sm_states_index = max(
        0, min(sm_node.red_sm_states_index, len(refs) - 1)
    )
    return cleared


def missing_state_handle(sm_node, index: int) -> str:
    """The handle at index of red_sm_states when its State node is gone, else "" """
    refs = getattr(sm_node, "red_sm_states", ())
    if not 0 <= index < len(refs) or state_for_ref(sm_node, index) is not None:
        return ""
    return str(refs[index].handle)


def missing_state_preview(sm_node, index: int) -> list:
    """Descriptions of the rows remove_missing_state would leave without a target"""
    handle = missing_state_handle(sm_node, index)
    return _retarget_preview(sm_node, handle) if handle else []


def remove_missing_state(sm_node, index: int) -> int:
    """Drop the red_sm_states entry index whose State node was deleted outside the editor"""
    _require_state_machine(sm_node)
    refs = sm_node.red_sm_states
    if not 0 <= index < len(refs):
        raise IndexError(index)
    handle = missing_state_handle(sm_node, index)
    if not handle:
        raise ValueError("this state still exists; delete it as a state")
    return _forget_state(sm_node, handle)


def move_state(sm_node, index: int, delta: int) -> int:
    """Move state index by delta in red_sm_states and return its new index"""
    _require_state_machine(sm_node)
    refs = sm_node.red_sm_states
    if not 0 <= index < len(refs):
        raise IndexError(index)
    new_index = max(0, min(len(refs) - 1, index + int(delta)))
    if new_index != index:
        refs.move(index, new_index)
    sm_node.red_sm_states_index = new_index
    return new_index


def set_default_state(sm_node, state_node) -> None:
    """Make state_node the default state (the target of Entry's default row)"""
    tree = _require_state_of(sm_node, state_node)
    entry = _pseudo_node(tree, ENTRY_RED_TYPE)
    if entry is None:
        raise ValueError("this state machine has no Entry node")
    rec = default_row(entry)
    if rec is None:
        rec = entry.red_transitions.add()
        sm_records.record_from_wrapper(rec, None, sm_records.DEFAULT_LIST, -1, None)
        entry.red_transitions.move(len(entry.red_transitions) - 1, 0)
        rec = entry.red_transitions[0]
    rec.target_handle = str(state_node.red_handle_id)
    _sync(entry)


def _new_any_state_interpolator() -> str:
    """The Any State blend every shipped state machine has (Blend, Linear)"""
    return animgraph_json.dumps(
        {
            "HandleId": new_handle_id(),
            "Data": {
                "$type": BLEND_INTERPOLATOR_TYPE,
                "interpolationType": "Linear",
                "visTransitionDuration": 1,
            },
        },
        indent=None,
    )


def scaffold_state_machine(sm_node) -> None:
    """Give a new, empty state machine its Entry, Any State, frozen state and one default State"""
    tree = _require_state_machine(sm_node)
    if sm_node.red_sm_records:
        return
    if (
        any(is_state(node) or _is_frozen_state(node) for node in tree.nodes)
        or _pseudo_node(tree, ENTRY_RED_TYPE) is not None
        or _pseudo_node(tree, ANY_RED_TYPE) is not None
        or len(sm_node.red_sm_states)
    ):
        raise ValueError(f"{sm_node.name!r} already has states")
    handle = str(sm_node.red_handle_id)
    entry = sm_records.new_pseudo_node(tree, handle, "Entry", "Entry")
    entry.red_transitions.clear()
    sm_records.record_from_wrapper(
        entry.red_transitions.add(), None, sm_records.DEFAULT_LIST, -1, None
    )
    any_state = sm_records.new_pseudo_node(tree, handle, "AnyState", "Any State")
    any_state.red_transitions.clear()
    any_state.red_sm_any_interpolator_json = _new_any_state_interpolator()
    any_state.red_sm_any_interpolation = "Linear"
    for node in (entry, any_state):
        _sync(node)
        _fit_width(node)
    entry.location = (0.0, 0.0)
    any_state.location = (0.0, -(estimated_node_size(entry)[1] + _PSEUDO_GAP))

    # Every shipped state machine has a frozen state; it is not one of ``states``.
    frozen = build_node(tree, "StateFrozen")
    _fit_width(frozen)
    frozen.location = (
        0.0,
        any_state.location.y - estimated_node_size(any_state)[1] - _PSEUDO_GAP,
    )

    sm_node.red_sm_records = True
    state = add_state(sm_node)
    set_default_state(sm_node, state)
    for node in tree.nodes:
        if node.bl_idname == "NodeGroupOutput":
            _place_right_of(node, [state])
