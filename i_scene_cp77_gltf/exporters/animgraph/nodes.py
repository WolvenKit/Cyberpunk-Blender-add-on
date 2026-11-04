from __future__ import annotations

from typing import Any

import bpy

from ...animation.model.animgraph.constants import ANIM_NODE_PREFIX, ANIMGRAPH_TREE_ID
from ...animation.model.animgraph.indices import cname
from ...animation.model.animgraph.sm_assembly import Assembled, AssemblyError, assemble
from ...blender.animgraph import (
    aim_constraint,
    direct_conn,
    point_constraint,
    simple_bounce,
    sm_records,
)
from ...blender.animgraph.access import get_attr, get_idprop
from ...blender.animgraph.builder import new_handle_id
from ...blender.animgraph.property_codec import encode_node_property
from ...blender.animgraph.sm_records import ANY_RED_TYPE, ENTRY_RED_TYPE, _pseudo_node
from .defaults import schema_default_data_for_type
from .paths import (
    _encode_link_wrapper,
    _ensure_list_size,
    _iter_exportable_input_sockets,
    set_export_socket_path,
    set_json_path,
)
from .tree_state import node_sort_key, tree_nodes
from .values import decode_optional

_MATH_EXPRESSION_SOCKET_ARRAYS = {
    "floatSockets": ("animFloatLink", "animAnimMathExpressionFloatSocket"),
    "vectorSockets": ("animVectorLink", "animAnimMathExpressionVectorSocket"),
    "quaternionSockets": (
        "animQuaternionLink",
        "animAnimMathExpressionQuaternionSocket",
    ),
}

_MATH_EXPRESSION_RETURN_BY_TYPE = {
    f"{ANIM_NODE_PREFIX}MathExpressionFloat": 1,
    f"{ANIM_NODE_PREFIX}MathExpressionVector": 2,
    f"{ANIM_NODE_PREFIX}MathExpressionQuaternion": 3,
}


def _runtime_node(node: Any) -> bool:
    red_type = str(get_attr(node, "red_type", "") or "")
    if not red_type.startswith(ANIM_NODE_PREFIX):
        return False
    explicit = get_attr(node, "red_exportable", None)
    if explicit is not None and not bool(explicit):
        return False
    return True


def _new_runtime_data_for_node(node: Any) -> dict[str, Any]:
    """Return current-schema runtime Data for an authored node"""
    red_type = str(get_attr(node, "red_type", "") or "animAnimNode_Unknown")
    data = schema_default_data_for_type(red_type)
    data["$type"] = red_type
    return data


def _container_subtree(node: Any) -> bpy.types.NodeTree | None:
    tree = getattr(node, "node_tree", None)
    if tree is not None and getattr(tree, "bl_idname", "") == ANIMGRAPH_TREE_ID:
        return tree
    return None


def _runtime_nodes_in_tree(tree: bpy.types.NodeTree | None) -> list[bpy.types.Node]:
    if tree is None:
        return []
    nodes = [node for node in tree_nodes(tree) if _runtime_node(node)]
    nodes.sort(key=node_sort_key)
    return nodes


def _json_idprop(obj: Any, key: str, default: Any) -> Any:
    value = decode_optional(get_idprop(obj, key, ""), default)
    return default if value is None and default is not None else value


def _top_path(path: str) -> str:
    text = str(path or "")
    if not text:
        return ""
    head = text.split(".", 1)[0]
    if "[" in head:
        head = head.split("[", 1)[0]
    return head


def _source_data_keys(node: Any) -> set | None:
    raw = decode_optional(get_idprop(node, "red_source_data_keys_json", ""), None)
    if raw is None:
        handle = str(get_attr(node, "red_handle_id", "") or "")
        if handle.startswith("new:"):
            return None
        raise ValueError(
            f"missing required source metadata: red_source_data_keys_json on HandleId {handle or '<unknown>'}"
        )
    if not isinstance(raw, list):
        handle = str(get_attr(node, "red_handle_id", "") or "")
        raise ValueError(
            f"invalid required source metadata: red_source_data_keys_json on HandleId {handle or '<unknown>'}"
        )
    return {str(key) for key in raw if str(key)}


def _apply_source_field_shape(
    node: Any, data: dict[str, Any], preserved_keys: set | None = None
) -> None:
    """Remove schema defaults that were absent from the imported node"""
    keys = _source_data_keys(node)
    if keys is None:
        return
    allowed = set(keys)
    allowed.add("$type")
    if str(get_attr(node, "red_type", "") or "") == "animAnimNode_SimpleBounce":
        allowed.update({"areChannelsResaved", "transformOutputs", "trackOutputs"})
    if str(get_attr(node, "red_type", "") or "") == "animAnimNode_PointConstraint":
        allowed.update(
            {
                "areSourceChannelsResaved",
                "inputTransforms",
                "preprocessedWeights",
                "inputWeightedTransforms",
            }
        )

    for item in getattr(node, "red_properties", []) or []:
        top = _top_path(
            str(getattr(item, "json_path", "") or getattr(item, "key", "") or "")
        )
        if top:
            allowed.add(top)

    for sock in _iter_exportable_input_sockets(node):
        top = _top_path(str(get_attr(sock, "red_json_path", "") or ""))
        if top:
            allowed.add(top)

    if preserved_keys is None:
        preserved = _json_idprop(node, "red_preserved_export_fields_json", {})
        preserved_keys = (
            {str(key) for key in preserved} if isinstance(preserved, dict) else set()
        )
    allowed.update(preserved_keys)

    for field in (
        "nodes",
        "states",
        "frozenState",
        "transitions",
        "globalTransitions",
        "conditionalEntries",
        "anyStateInterpolator",
        "outTransitionIndices",
    ):
        if field in data and field in keys:
            allowed.add(field)
    # Transitions authored in the editor (e.g. the first Any State transition)
    # are written even when the source had no such list.
    if getattr(node, "red_sm_records", False):
        for field in ("transitions", "globalTransitions", "conditionalEntries"):
            if data.get(field):
                allowed.add(field)
    # A default state picked in the editor must be written even when the source
    # relied on the implicit 0.
    if getattr(node, "red_sm_records", False) and data.get("defaultStateIndex") not in (
        None,
        0,
    ):
        allowed.add("defaultStateIndex")

    for key in tuple(data):
        if key not in allowed:
            data.pop(key, None)


def _red_type(node: Any) -> str:
    return str(get_attr(node, "red_type", "") or "")


def _handle(node: Any) -> str:
    return str(get_attr(node, "red_handle_id", "") or "")


def _is_type(node: Any, short_name: str) -> bool:
    return _red_type(node) == f"{ANIM_NODE_PREFIX}{short_name}"


def _state_order_handles(sm_node: Any) -> list[str]:
    """State handles in states order"""
    refs = getattr(sm_node, "red_sm_states", None)
    return [str(ref.handle) for ref in refs if ref.handle] if refs is not None else []


def _ordered_state_nodes(
    sm_node: Any, sm_tree: bpy.types.NodeTree
) -> list[bpy.types.Node]:
    states = [
        node for node in _runtime_nodes_in_tree(sm_tree) if _is_type(node, "State")
    ]
    by_handle = {_handle(node): node for node in states if _handle(node)}
    ordered: list[bpy.types.Node] = []
    for handle in _state_order_handles(sm_node):
        node = by_handle.pop(handle, None)
        if node is not None:
            ordered.append(node)
    ordered.extend(sorted(by_handle.values(), key=node_sort_key))
    return ordered


def _state_frozen_node(sm_tree: bpy.types.NodeTree) -> bpy.types.Node | None:
    frozen = [
        node
        for node in _runtime_nodes_in_tree(sm_tree)
        if _is_type(node, "StateFrozen")
    ]
    if not frozen:
        return None
    frozen.sort(key=node_sort_key)
    return frozen[0]


def _encode_tree_runtime_entries(
    tree: bpy.types.NodeTree | None,
    *,
    embed_containers: bool,
    _stack: set | None = None,
    exclude_handles: set | None = None,
    predicate=None,
) -> list[dict[str, Any]]:
    if tree is None:
        return []
    entries: list[dict[str, Any]] = []
    exclude_handles = exclude_handles or set()
    for child in _runtime_nodes_in_tree(tree):
        handle = _handle(child)
        if handle in exclude_handles:
            continue
        if predicate is not None and not predicate(child):
            continue
        entries.append(
            encode_runtime_node_entry(
                child, embed_containers=embed_containers, _stack=_stack
            )
        )
    return entries


# Per export: each state machine's assembled outTransitionIndices, and the state machine of the subtree
# being encoded.
_SM_OUT_INDICES: dict[str, dict[str, list[int]]] = {}
_SM_OF_TREE: dict[int, str] = {}
# Per export: the encoded nodes that containers leave out of their nodes lists.
_UNLISTED_ENTRIES: list[dict[str, Any]] = []


def _assembled_out_indices(state: bpy.types.Node) -> list[int] | None:
    tree = getattr(state, "id_data", None)
    sm_handle = _SM_OF_TREE.get(tree.as_pointer()) if tree is not None else None
    out = _SM_OUT_INDICES.get(sm_handle) if sm_handle is not None else None
    if out is None:
        return None
    return list(out.get(_handle(state), []))


def _embed_state_out_transition_indices(
    node: bpy.types.Node, data: dict[str, Any]
) -> None:
    if not (_is_type(node, "State") or _is_type(node, "StateFrozen")):
        return
    if _is_type(node, "State"):
        indices = _assembled_out_indices(node)
        if indices is not None:
            data["outTransitionIndices"] = indices
            return
    if "red_state_outTransitionIndices_json" in node:
        indices = _json_idprop(node, "red_state_outTransitionIndices_json", [])
        data["outTransitionIndices"] = indices if isinstance(indices, list) else []


def _assemble_state_machine(
    node: bpy.types.Node, sm_tree: bpy.types.NodeTree, states: list[bpy.types.Node]
) -> Assembled:
    """Assemble the state machine lists from the transition records of every owner"""
    sm_handle = _handle(node)
    owners: list[tuple[Any, str]] = [(state, _handle(state)) for state in states]
    for pseudo in (
        _pseudo_node(sm_tree, ENTRY_RED_TYPE),
        _pseudo_node(sm_tree, ANY_RED_TYPE),
    ):
        if pseudo is not None:
            owners.append((pseudo, sm_records.owner_key(pseudo)))
    owners.append((node, sm_records.owner_key(node)))

    specs = []
    default_target: str | None = None
    for owner, key in owners:
        for rec in owner.red_transitions:
            if rec.list_name == sm_records.DEFAULT_LIST:
                if default_target is None and rec.target_handle:
                    default_target = rec.target_handle
                continue
            specs.append(sm_records.record_to_spec(rec, key))

    # Entry's default row is the only source of the default state: the hidden
    # generic ``defaultStateIndex`` property is never used for a records state machine.
    if default_target is None:
        label = str(
            getattr(node, "label", "") or getattr(node, "name", "") or "state machine"
        )
        raise AssemblyError(
            f'state machine "{label}" ({sm_handle}): the default state is not set; '
            f"pick a default state in the States panel"
        )
    try:
        return assemble(
            specs, [_handle(state) for state in states], default_target, new_handle_id
        )
    except AssemblyError as exc:
        raise AssemblyError(f"state machine {sm_handle}: {exc}") from exc


def _embed_state_machine_fields(
    node: bpy.types.Node, data: dict[str, Any], _stack: set
) -> None:
    sm_tree = _container_subtree(node)
    if sm_tree is None:
        return

    # Duplicated states, shared pose graphs and missing / extra Entry or Any State
    # nodes would otherwise be dropped or picked arbitrarily without a word.
    problems = sm_records.structure_problems(node)
    if problems:
        raise AssemblyError("; ".join(problems))

    states = _ordered_state_nodes(node, sm_tree)
    assembled = (
        _assemble_state_machine(node, sm_tree, states)
        if getattr(node, "red_sm_records", False)
        else None
    )

    tree_key = sm_tree.as_pointer()
    sm_handle = _handle(node)
    previous = (_SM_OF_TREE.get(tree_key), _SM_OUT_INDICES.get(sm_handle))
    if assembled is not None:
        _SM_OF_TREE[tree_key] = sm_handle
        _SM_OUT_INDICES[sm_handle] = assembled.out_indices
    try:
        data["states"] = [
            encode_runtime_node_entry(state, embed_containers=True, _stack=_stack)
            for state in states
        ]
    finally:
        if assembled is not None:
            for cache, key, value in (
                (_SM_OF_TREE, tree_key, previous[0]),
                (_SM_OUT_INDICES, sm_handle, previous[1]),
            ):
                if value is None:
                    cache.pop(key, None)
                else:
                    cache[key] = value

    frozen = _state_frozen_node(sm_tree)
    data["frozenState"] = (
        encode_runtime_node_entry(frozen, embed_containers=True, _stack=_stack)
        if frozen is not None
        else None
    )

    if assembled is not None:
        data["transitions"] = assembled.transitions
        data["conditionalEntries"] = assembled.conditionalEntries
        data["globalTransitions"] = assembled.globalTransitions
        data["defaultStateIndex"] = assembled.default_state_index
        any_state = _pseudo_node(sm_tree, ANY_RED_TYPE)
        if any_state is not None:
            data["anyStateInterpolator"] = sm_records.any_state_interpolator(any_state)
        return

    for key in ("transitions", "conditionalEntries", "globalTransitions"):
        prop = f"red_sm_{key}_json"
        if prop in node:
            value = _json_idprop(node, prop, [])
            data[key] = value if isinstance(value, list) else []
    if "red_sm_anyStateInterpolator_json" in node:
        data["anyStateInterpolator"] = decode_optional(
            get_idprop(node, "red_sm_anyStateInterpolator_json", ""), None
        )


def take_unlisted_entries() -> list[dict[str, Any]]:
    """The encoded nodes containers left out of their lists since the last call, for the reference pass"""
    entries = list(_UNLISTED_ENTRIES)
    _UNLISTED_ENTRIES.clear()
    return entries


def _embed_generic_nodes_container(
    node: bpy.types.Node, data: dict[str, Any], _stack: set
) -> None:
    child_tree = _container_subtree(node)
    if child_tree is None:
        return
    if "nodes" in data or _is_type(node, "State") or _is_type(node, "StateFrozen"):
        # Nodes the source reached through links only stay out of the list; the reference pass writes them where a
        # link first reaches them.
        data["nodes"] = _encode_tree_runtime_entries(
            child_tree,
            embed_containers=True,
            _stack=_stack,
            predicate=lambda child: "red_source_unlisted" not in child,
        )
        _UNLISTED_ENTRIES.extend(
            _encode_tree_runtime_entries(
                child_tree,
                embed_containers=True,
                _stack=_stack,
                predicate=lambda child: "red_source_unlisted" in child,
            )
        )


def _embed_container_fields(
    node: bpy.types.Node, data: dict[str, Any], _stack: set
) -> None:
    red_type = _red_type(node)
    if not red_type:
        return
    _embed_state_out_transition_indices(node, data)
    short = red_type.replace(ANIM_NODE_PREFIX, "")
    if short in {"StateMachine", "LocomotionMachine"} or "states" in data:
        _embed_state_machine_fields(node, data, _stack)
        return
    _embed_generic_nodes_container(node, data, _stack)


def _apply_preserved_export_fields(node: Any, data: dict[str, Any]) -> set:
    """Restore preserved owned-payload fields and return their keys"""
    fields = _json_idprop(node, "red_preserved_export_fields_json", {})
    source_keys = _source_data_keys(node)
    required = {
        key
        for key in source_keys or ()
        if key == "poseInfoLogger"
        or key.startswith("vis")
        or key
        in {
            "shrinkerNodeId",
            "extenderNodeId",
            "segmentBeginNodeId",
            "segmentEndNodeId",
        }
    }
    if required - set(fields if isinstance(fields, dict) else ()):
        raise ValueError(
            "Hidden source fields are missing; reimport the AnimGraph before exporting"
        )
    if not isinstance(fields, dict):
        return set()
    # The idprop was just decoded, so its values are already private copies.
    for key, value in fields.items():
        if not key or str(key).startswith("$"):
            continue
        data[str(key)] = value
    return {str(key) for key in fields}


def _apply_preserved_math_expression_data(node: Any, data: dict[str, Any]) -> None:
    """Restore hidden MathExpression payload state before editable overlays"""
    red_type = str(get_attr(node, "red_type", "") or "")
    if not red_type.startswith(f"{ANIM_NODE_PREFIX}MathExpression"):
        return
    expr = _json_idprop(node, "red_math_expression_data_json", None)
    if isinstance(expr, dict):
        data["expressionData"] = expr


def _is_math_expression_node(node: Any) -> bool:
    return str(get_attr(node, "red_type", "") or "").startswith(
        f"{ANIM_NODE_PREFIX}MathExpression"
    )


def _math_expression_data(data: dict[str, Any]) -> dict[str, Any]:
    expr = data.get("expressionData")
    if not isinstance(expr, dict):
        expr = {"$type": "animMathExpressionNodeData"}
        data["expressionData"] = expr
    expr.setdefault("$type", "animMathExpressionNodeData")
    for array_name in _MATH_EXPRESSION_SOCKET_ARRAYS:
        if not isinstance(expr.get(array_name), list):
            expr[array_name] = []
    return expr


def _math_expression_payload_data(node: Any, expr: dict[str, Any]) -> dict[str, Any]:
    expression = expr.get("expression")
    if not isinstance(expression, dict):
        expression = {}
        expr["expression"] = expression
    handle = str(get_idprop(node, "red_math_expression_handle", "") or "")
    if handle and not expression.get("HandleId") and not expression.get("HandleRefId"):
        expression["HandleId"] = handle
    payload = expression.get("Data")
    if not isinstance(payload, dict):
        payload = {}
        expression["Data"] = payload
    payload.setdefault("$type", "mathExprExpression")
    payload.setdefault(
        "returnVarType",
        _MATH_EXPRESSION_RETURN_BY_TYPE.get(
            str(get_attr(node, "red_type", "") or ""), 0
        ),
    )
    payload.setdefault("tokenData", [])
    payload.setdefault("valuesData", [])
    return payload


def _math_socket_path(path: str) -> tuple[str, int] | None:
    for array_name in _MATH_EXPRESSION_SOCKET_ARRAYS:
        prefix = f"expressionData.{array_name}["
        if not str(path or "").startswith(prefix):
            continue
        rest = str(path)[len(prefix) :]
        index_text = rest.split("]", 1)[0]
        try:
            return array_name, int(index_text)
        except ValueError:
            return None
    return None


def _ensure_math_socket(
    expr: dict[str, Any], array_name: str, index: int
) -> dict[str, Any]:
    link_type, struct_type = _MATH_EXPRESSION_SOCKET_ARRAYS[array_name]
    arr = expr.get(array_name)
    if not isinstance(arr, list):
        arr = []
        expr[array_name] = arr
    _ensure_list_size(arr, index)
    item = arr[index]
    if not isinstance(item, dict):
        item = {}
        arr[index] = item
    item.setdefault("$type", struct_type)
    item.setdefault("expressionVarId", index)
    if array_name == "floatSockets":
        item.setdefault(
            "inputFloatTrack", {"$type": "animNamedTrackIndex", "name": cname("None")}
        )
    link = item.get("link")
    if not isinstance(link, dict):
        item["link"] = {"$type": link_type, "node": None}
    else:
        link.setdefault("$type", link_type)
        link.setdefault("node", None)
    return item


def _finalize_math_expression_data(node: Any, data: dict[str, Any]) -> None:
    """Finalize MathExpression payload structure after editable overlays"""
    if not _is_math_expression_node(node):
        return
    expr = _math_expression_data(data)
    payload = _math_expression_payload_data(node, expr)

    for item in getattr(node, "red_properties", []) or []:
        path = str(getattr(item, "json_path", "") or getattr(item, "key", "") or "")
        if path == "expressionData.expression.Data.tokenData":
            payload["tokenData"] = encode_node_property(item)
        elif path == "expressionData.expression.Data.valuesData":
            payload["valuesData"] = encode_node_property(item)

    for sock in _iter_exportable_input_sockets(node):
        parsed = _math_socket_path(str(get_attr(sock, "red_json_path", "") or ""))
        if parsed is None:
            continue
        array_name, index = parsed
        item = _ensure_math_socket(expr, array_name, index)
        item["link"] = _encode_link_wrapper(sock)


def encode_runtime_node_data(
    node: bpy.types.Node,
    *,
    embed_containers: bool = False,
    _stack: set | None = None,
) -> dict[str, Any]:
    """Encode one runtime node Data object from editable properties and sockets"""
    if not _runtime_node(node):
        raise ValueError("active node is not an exportable REDengine runtime node")
    data = _new_runtime_data_for_node(node)
    data["$type"] = str(get_attr(node, "red_type", "") or data.get("$type", ""))
    preserved_keys = _apply_preserved_export_fields(node, data)
    _apply_preserved_math_expression_data(node, data)

    for item in getattr(node, "red_properties", []) or []:
        path = str(getattr(item, "json_path", "") or getattr(item, "key", "") or "")
        if not path:
            continue
        set_json_path(data, path, encode_node_property(item))

    for sock in _iter_exportable_input_sockets(node):
        set_export_socket_path(
            data, str(sock.red_json_path), _encode_link_wrapper(sock)
        )

    _finalize_math_expression_data(node, data)
    data = direct_conn.canonicalize_node_data(node, data)
    data = simple_bounce.canonicalize_node_data(node, data)
    data = point_constraint.canonicalize_node_data(node, data)
    data = aim_constraint.canonicalize_node_data(node, data)

    if embed_containers:
        if _stack is None:
            _stack = set()
        handle = _handle(node)
        if handle and handle in _stack:
            _apply_source_field_shape(node, data, preserved_keys)
            return data
        if handle:
            _stack.add(handle)
        try:
            _embed_container_fields(node, data, _stack)
        finally:
            if handle:
                _stack.discard(handle)

    _apply_source_field_shape(node, data, preserved_keys)
    return data


def encode_runtime_node_entry(
    node: bpy.types.Node,
    *,
    embed_containers: bool = False,
    _stack: set | None = None,
) -> dict[str, Any]:
    handle = str(get_attr(node, "red_handle_id", "") or "")
    if not handle:
        raise ValueError("runtime node is missing red_handle_id")
    return {
        "HandleId": handle,
        "Data": encode_runtime_node_data(
            node, embed_containers=embed_containers, _stack=_stack
        ),
    }


def encode_selected_node(context: bpy.types.Context) -> dict[str, Any]:
    node = getattr(context, "active_node", None)
    if node is None:
        raise ValueError("no active node")
    return encode_runtime_node_entry(node)
