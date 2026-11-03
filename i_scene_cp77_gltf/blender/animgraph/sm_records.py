from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

import bpy

from ...animation.model.animgraph import sm_conditions
from ...animation.model.animgraph.indices import cname
from ...animation.model.animgraph.schema import enums
from ...animation.model.animgraph.sm_assembly import (
    TransitionSpec,
    overlay_data,
    tidy_float,
    tidy_floats,
)
from ...assetio import animgraph_json
from ...assetio.values import cname_text
from . import property_codec
from .sm_properties import (
    BLEND_INTERPOLATOR_TYPE,
    INTERPOLATION_TYPE_ENUM,
    INTERPOLATION_TYPE_ITEMS,
)

ENTRY_OWNER = "__entry__"
ANY_OWNER = "__any__"
DEFAULT_LIST = "default"

ENTRY_RED_TYPE = "editorEntry"
ANY_RED_TYPE = "editorAnyState"
STATE_RED_TYPE = "animAnimNode_State"

TRANSITION_TYPE = "animAnimStateTransitionDescription"
CONDITIONAL_ENTRY_TYPE = "animAnimStateMachineConditionalEntry"

OPAQUE_CONDITION_TEXT = "(shared condition)"
_RAW_CHOICE = "__RAW__"
_KIND_HINTS = {"CNAME": "CName", "FLOAT": "Float", "INT": "Int32", "BOOL": "Bool"}


def _loads(text: str) -> Any:
    if not text:
        return None
    try:
        return animgraph_json.loads(text)
    except ValueError:
        return None


def _new_handle() -> str:
    from .builder import new_handle_id

    return new_handle_id()


def _is_ref(value: Any) -> bool:
    return isinstance(value, dict) and "HandleRefId" in value and "Data" not in value


class _FieldHost:
    """What property_codec._add_array_field needs from its element"""

    def __init__(self, fields, red_type: str):
        self.fields = fields
        self.red_type = red_type


def _field_hint(spec: sm_conditions.FieldSpec | None) -> str:
    if spec is None:
        return ""
    if spec.kind == "ENUM":
        return spec.enum_type
    return _KIND_HINTS.get(spec.kind, "")


def fill_condition(
    cond,
    short: str,
    depth: int,
    handle: str,
    data: dict | None = None,
    original: dict | None = None,
) -> None:
    """(Re)initialise a condition entry from data, or with the catalogue defaults when it is omitted"""
    cond.short = short
    cond.depth = depth
    cond.handle_id = handle or ""
    kept = None
    if isinstance(original, dict):
        kept = {k: v for k, v in original.items() if k != "conditions"}
    cond.original_json = (
        animgraph_json.dumps(kept, indent=None) if kept is not None else ""
    )
    cond.fields.clear()
    if short == sm_conditions.GROUP:
        return
    specs = sm_conditions.CONDITION_TYPES.get(short, ())
    defaults = (
        sm_conditions.default_condition_data(short)
        if short in sm_conditions.CONDITION_TYPES
        else {}
    )
    values = {
        k: v
        for k, v in (data if data is not None else defaults).items()
        if k not in ("$type", "conditions")
    }
    host = _FieldHost(cond.fields, sm_conditions.CONDITION_PREFIX + short)
    known = {spec.name for spec in specs}
    ordered = [(spec.name, spec) for spec in specs if spec.name in values]
    ordered += [(key, None) for key in sorted(values) if key not in known]
    for key, spec in ordered:
        property_codec._add_array_field(
            host, key, values[key], red_type_hint=_field_hint(spec)
        )


def read_condition(cond) -> sm_conditions.FlatCondition:
    """The FlatCondition for one stored entry"""
    short = cond.short
    original = _loads(cond.original_json)
    if not isinstance(original, dict):
        original = None
    fields: dict = {}
    if short != sm_conditions.GROUP:
        # Floats are tidied (see ``tidy_float``); an unchanged value keeps its original token.
        current = {
            f.key: tidy_floats(property_codec.encode_simple_value(f))
            for f in cond.fields
        }
        if (
            original is not None
            and original.get("$type") == sm_conditions.CONDITION_PREFIX + short
        ):
            merged = overlay_data(original, current)
            fields = {
                k: v for k, v in merged.items() if k not in ("$type", "conditions")
            }
        else:
            fields = current
    if (
        original is not None
        and original.get("$type") != sm_conditions.CONDITION_PREFIX + short
    ):
        original = None
    return sm_conditions.FlatCondition(
        short, int(cond.depth), cond.handle_id, fields, original
    )


def record_conditions(rec) -> list:
    return [read_condition(cond) for cond in rec.conditions]


def set_conditions(rec, flat) -> None:
    """Replace a record's conditions with flat (a list of FlatCondition)"""
    clear_opaque_condition(rec)
    rec.conditions.clear()
    for entry in flat:
        cond = rec.conditions.add()
        fill_condition(
            cond, entry.short, entry.depth, entry.handle, entry.fields, entry.original
        )
    rec.conditions_index = 0


def clear_opaque_condition(rec) -> None:
    """Forget the verbatim condition so the record's conditions become authoritative"""
    rec.condition_opaque_json = ""


def has_unresolved_ref(value: Any) -> bool:
    """True when a condition tree holds a HandleRefId"""
    if _is_ref(value):
        return True
    if isinstance(value, dict) and isinstance(value.get("Data"), dict):
        children = value["Data"].get("conditions")
        if isinstance(children, list):
            return any(has_unresolved_ref(child) for child in children)
    return False


def summary(rec) -> str:
    """Human-readable condition summary of a record"""
    if rec.condition_opaque_json:
        return OPAQUE_CONDITION_TEXT
    rebuilt = sm_conditions.build_condition(record_conditions(rec), lambda: "")
    return sm_conditions.summarize_condition(rebuilt)


def _resolve_refs(value: Any, resolve: Callable[[str], dict | None]) -> Any:
    """Replace HandleRefId wrappers by the resolver's private copy"""
    if _is_ref(value):
        resolved = resolve(str(value["HandleRefId"]))
        if not isinstance(resolved, dict):
            return value
        return _resolve_refs(copy.deepcopy(resolved), resolve)
    if isinstance(value, dict) and isinstance(value.get("Data"), dict):
        children = value["Data"].get("conditions")
        if isinstance(children, list):
            value["Data"]["conditions"] = [
                _resolve_refs(child, resolve) for child in children
            ]
    return value


def _reset(rec) -> None:
    rec.original_json = ""
    rec.handle_id = ""
    rec.enabled = True
    rec.forced_true = False
    rec.priority = 0
    rec.duration = 0.0
    rec.can_request_inertialization = False
    rec.support_blend_from_pose = False
    rec.is_out_transition_from_action = False
    rec.interpolator_type = BLEND_INTERPOLATOR_TYPE
    rec.interpolator_handle = ""
    rec.interpolation_type = "Linear"
    rec.anim_feature_name = "None"
    rec.action_db_path = ""
    rec.sync_method_json = ""
    rec.condition_opaque_json = ""


def _depot_text(ref: Any) -> str:
    path = ref.get("DepotPath") if isinstance(ref, dict) else None
    if isinstance(path, dict):
        return str(path.get("$value", ""))
    return ""


def _set_interpolator(rec, interp: Any) -> None:
    idata = interp.get("Data") if isinstance(interp, dict) else None
    if not isinstance(idata, dict):
        rec.interpolator_type = ""
        rec.interpolator_handle = ""
        return
    rec.interpolator_type = str(idata.get("$type", ""))
    rec.interpolator_handle = str(interp.get("HandleId", ""))
    choice = "Linear"
    if "interpolationType" in idata:
        choice = enums.normalize_choice(
            INTERPOLATION_TYPE_ENUM, idata["interpolationType"]
        )
    try:
        rec.interpolation_type = choice
    except TypeError:
        rec.interpolation_type = _RAW_CHOICE


def record_from_wrapper(
    rec,
    wrapper: dict | None,
    list_name: str,
    index: int,
    target_handle: str | None,
    *,
    resolve: Callable[[str], dict | None] | None = None,
) -> None:
    """Fill rec from a RED transition / conditional-entry wrapper, or as a new record when it is None"""
    rec.list_name = list_name
    rec.original_index = int(index)
    rec.target_handle = target_handle or ""
    rec.conditions.clear()
    rec.conditions_index = 0
    _reset(rec)
    if wrapper is None:
        if list_name != DEFAULT_LIST:
            rec.handle_id = _new_handle()
            if list_name != "conditionalEntries":
                rec.interpolator_handle = _new_handle()
        return

    wrapper = copy.deepcopy(wrapper)
    data = wrapper.get("Data") if isinstance(wrapper.get("Data"), dict) else {}
    if resolve is not None:
        if "condition" in data:
            data["condition"] = _resolve_refs(data["condition"], resolve)
        if list_name != "conditionalEntries" and _is_ref(data.get("interpolator")):
            data["interpolator"] = _resolve_refs(data["interpolator"], resolve)

    rec.original_json = animgraph_json.dumps(wrapper, indent=None)
    rec.handle_id = str(wrapper.get("HandleId", ""))
    rec.enabled = bool(data.get("isEnabled", True))
    rec.forced_true = bool(data.get("isForcedToTrue", False))
    rec.priority = int(data.get("priority", 0) or 0)

    if list_name != "conditionalEntries":
        rec.duration = float(data.get("duration", 0.0) or 0.0)
        rec.can_request_inertialization = bool(
            data.get("canRequestInertialization", False)
        )
        rec.support_blend_from_pose = bool(data.get("supportBlendFromPose", False))
        rec.is_out_transition_from_action = bool(
            data.get("isOutTransitionFromAction", False)
        )
        _set_interpolator(rec, data.get("interpolator"))
        rec.anim_feature_name = cname_text(data.get("animFeatureName"), "None")
        rec.action_db_path = _depot_text(data.get("actionAnimDatabaseRef"))
        sync = data.get("syncMethod")
        rec.sync_method_json = (
            "" if sync is None else animgraph_json.dumps(sync, indent=None)
        )

    condition = data.get("condition")
    if has_unresolved_ref(condition):
        rec.condition_opaque_json = animgraph_json.dumps(condition, indent=None)
    else:
        set_conditions(rec, sm_conditions.flatten_condition(condition))


def renew_record(rec) -> None:
    """Turn rec, a copied row, into a new transition that keeps its edited values"""
    if rec.list_name == DEFAULT_LIST:
        return
    rec.original_index = -1
    rec.original_json = ""
    rec.handle_id = _new_handle()
    entry = rec.list_name == "conditionalEntries"
    rec.interpolator_handle = (
        "" if entry or not rec.interpolator_type else _new_handle()
    )
    for cond in rec.conditions:
        cond.handle_id = _new_handle()


def _depot_ref(text: str, original: Any) -> dict:
    text = (text or "").strip() or "0"
    if isinstance(original, dict) and _depot_text(original) == text:
        return copy.deepcopy(original)
    ref = (
        copy.deepcopy(original)
        if isinstance(original, dict)
        else {"DepotPath": None, "Flags": "Default"}
    )
    storage = "uint64" if text.isdigit() else "string"
    ref["DepotPath"] = {"$type": "ResourcePath", "$storage": storage, "$value": text}
    return ref


def _interpolation_value(rec, original_value: Any) -> Any:
    choice = rec.interpolation_type
    if isinstance(original_value, int) and not isinstance(original_value, bool):
        value = enums.value_for_name(INTERPOLATION_TYPE_ENUM, choice)
        return int(value) if value is not None else original_value
    return choice


def _interpolator_wrapper(rec, interp_type: str, original_interp: Any) -> dict:
    handle = rec.interpolator_handle
    if not handle and isinstance(original_interp, dict):
        handle = str(original_interp.get("HandleId", ""))
    if not handle:
        handle = (
            _new_handle()
        )  # a placeholder for this export only; the record is not changed
    original_data = (
        original_interp.get("Data") if isinstance(original_interp, dict) else None
    )
    if isinstance(original_data, dict) and original_data.get("$type") == interp_type:
        idata = copy.deepcopy(original_data)
    else:
        idata = {"$type": interp_type}
        if interp_type == BLEND_INTERPOLATOR_TYPE:
            idata["visTransitionDuration"] = 1
    if rec.interpolation_type != _RAW_CHOICE:
        idata["interpolationType"] = _interpolation_value(
            rec, idata.get("interpolationType")
        )
    if original_data is None:
        idata = {
            "$type": idata["$type"],
            **{k: idata[k] for k in sorted(idata) if k != "$type"},
        }
    return {"HandleId": handle, "Data": idata}


def record_to_spec(rec, owner: str) -> TransitionSpec:
    """The assembly spec for rec owned by owner (State handle, ENTRY_OWNER or ANY_OWNER)"""
    original = _loads(rec.original_json)
    if not isinstance(original, dict) or not isinstance(original.get("Data"), dict):
        original = None
    original_data = original["Data"] if original else {}
    entry = rec.list_name == "conditionalEntries"

    handle = rec.handle_id or _new_handle()

    data: dict = {
        "$type": original_data.get("$type")
        or (CONDITIONAL_ENTRY_TYPE if entry else TRANSITION_TYPE),
        "isEnabled": bool(rec.enabled),
        "isForcedToTrue": bool(rec.forced_true),
        "priority": int(rec.priority),
    }
    if not entry:
        data["duration"] = tidy_float(rec.duration)
        data["canRequestInertialization"] = bool(rec.can_request_inertialization)
        data["supportBlendFromPose"] = bool(rec.support_blend_from_pose)
        data["isOutTransitionFromAction"] = bool(rec.is_out_transition_from_action)
        data["animFeatureName"] = cname(rec.anim_feature_name)
        data["actionAnimDatabaseRef"] = _depot_ref(
            rec.action_db_path, original_data.get("actionAnimDatabaseRef")
        )
        sync = _loads(rec.sync_method_json) if rec.sync_method_json.strip() else None
        data["syncMethod"] = sync
        if rec.interpolator_type:
            data["interpolator"] = _interpolator_wrapper(
                rec, rec.interpolator_type, original_data.get("interpolator")
            )
        elif original is None:
            data["interpolator"] = _interpolator_wrapper(
                rec, BLEND_INTERPOLATOR_TYPE, None
            )

    opaque = _loads(rec.condition_opaque_json) if rec.condition_opaque_json else None
    return TransitionSpec(
        owner=owner,
        list_name=rec.list_name,
        original_index=int(rec.original_index),
        original=original,
        handle=handle,
        data=data,
        conditions=[] if opaque is not None else record_conditions(rec),
        target=rec.target_handle or None,
        condition_raw=opaque,
    )


_KNOWN_INTERPOLATIONS = frozenset(item[0] for item in INTERPOLATION_TYPE_ITEMS) - {
    _RAW_CHOICE
}


def any_state_interpolator(node) -> Any:
    """anyStateInterpolator for an Any State node with the edited interpolation applied"""
    value = _loads(getattr(node, "red_sm_any_interpolator_json", ""))
    idata = value.get("Data") if isinstance(value, dict) else None
    if not isinstance(idata, dict):
        return value
    choice = getattr(node, "red_sm_any_interpolation", "Linear")
    if choice not in _KNOWN_INTERPOLATIONS:
        return value
    if "interpolationType" in idata:
        current = idata["interpolationType"]
        normalized = enums.normalize_choice(INTERPOLATION_TYPE_ENUM, current)
        if normalized == choice or normalized not in _KNOWN_INTERPOLATIONS:
            return value
        if isinstance(current, int) and not isinstance(current, bool):
            number = enums.value_for_name(INTERPOLATION_TYPE_ENUM, choice)
            idata["interpolationType"] = int(number) if number is not None else current
        else:
            idata["interpolationType"] = choice
    elif choice != "Linear":
        idata["interpolationType"] = choice
        value["Data"] = {
            "$type": idata.get("$type"),
            **{k: idata[k] for k in sorted(idata) if k != "$type"},
        }
    return value


_GRAPH_GENERATION = 0


def graph_generation() -> int:
    """Counter bumped whenever the graph structure may have changed"""
    return _GRAPH_GENERATION


def bump_graph_generation() -> None:
    """Invalidate answers derived from a scan of every node group"""
    global _GRAPH_GENERATION
    _GRAPH_GENERATION += 1


def sm_container_for(sm_tree) -> bpy.types.Node | None:
    """The node whose node_tree is sm_tree (the state machine container)"""
    if sm_tree is None:
        return None
    for group in bpy.data.node_groups:
        for node in group.nodes:
            if getattr(node, "node_tree", None) == sm_tree:
                return node
    return None


def state_nodes(sm_tree) -> list:
    """State nodes of sm_tree in red_sm_states order (handles with no node are skipped)"""
    container = sm_container_for(sm_tree)
    if container is None:
        return []
    by_handle = {}
    for node in sm_tree.nodes:
        if not getattr(node, "red_pseudo", False) and getattr(
            node, "red_handle_id", ""
        ):
            by_handle.setdefault(node.red_handle_id, node)
    return [
        by_handle[ref.handle]
        for ref in container.red_sm_states
        if ref.handle in by_handle
    ]


def owner_key(node) -> str:
    red_type = getattr(node, "red_type", "")
    if red_type == ENTRY_RED_TYPE:
        return ENTRY_OWNER
    if red_type == ANY_RED_TYPE:
        return ANY_OWNER
    return str(getattr(node, "red_handle_id", ""))


def _pseudo_node(sm_tree, red_type: str):
    if sm_tree is None:
        return None
    for node in sm_tree.nodes:
        if getattr(node, "red_type", "") == red_type:
            return node
    return None


def new_pseudo_node(sm_tree, sm_handle: str, short: str, label: str):
    """The Entry or Any State node of a state machine subtree, created on first use"""
    from . import categories
    from .tree_ops import new_editor_node

    key = f"editor{short}_{sm_handle}"
    existing = sm_tree.nodes.get(key)
    if existing is not None:
        return existing
    return new_editor_node(
        sm_tree,
        red_type=f"editor{short}",
        handle=key,
        label=label,
        color=categories.NODE_CATEGORY_COLORS[categories.node_category(short)],
    )


_STATE_LABEL_PREFIX = "State: "


def _node_text(node) -> str:
    label = str(getattr(node, "label", "") or "")
    label = label.removeprefix(_STATE_LABEL_PREFIX)
    return label or str(
        getattr(node, "name", "") or getattr(node, "red_handle_id", "") or "?"
    )


def structure_problems(sm_node) -> list:
    """Why sm_node's subtree cannot be exported as one state machine (empty when it can)"""
    tree = getattr(sm_node, "node_tree", None)
    if tree is None:
        return []
    label = _node_text(sm_node)
    states = [
        node
        for node in tree.nodes
        if getattr(node, "red_type", "") == STATE_RED_TYPE
        and not getattr(node, "red_pseudo", False)
    ]
    problems = []
    by_handle: dict = {}
    for node in states:
        handle = str(getattr(node, "red_handle_id", "") or "")
        if handle:
            by_handle.setdefault(handle, []).append(node)
    for handle, nodes in by_handle.items():
        for duplicate in nodes[1:]:
            problems.append(
                f'state machine "{label}": state "{_node_text(duplicate)}" is a duplicate of state '
                f'"{_node_text(nodes[0])}" (both have handle {handle}); delete the duplicate, or add '
                f'new states with the "+" button of the States panel'
            )
    by_graph: dict = {}
    for node in states:
        sub = getattr(node, "node_tree", None)
        if sub is not None:
            by_graph.setdefault(sub.as_pointer(), []).append(node)
    for nodes in by_graph.values():
        for other in nodes[1:]:
            problems.append(
                f'state machine "{label}": state "{_node_text(other)}" shares its pose graph with '
                f'"{_node_text(nodes[0])}"; duplicate states need their own graph (delete the duplicate '
                f'and add new states with the "+" button of the States panel)'
            )
    if getattr(sm_node, "red_sm_records", False):
        for red_type, name in ((ENTRY_RED_TYPE, "Entry"), (ANY_RED_TYPE, "Any State")):
            count = sum(
                1 for node in tree.nodes if getattr(node, "red_type", "") == red_type
            )
            if count == 0:
                problems.append(
                    f'state machine "{label}" has no {name} node; undo its deletion (Ctrl+Z) '
                    f"or reimport the AnimGraph"
                )
            elif count > 1:
                problems.append(
                    f'state machine "{label}" has {count} {name} nodes; delete the extra copies '
                    f"(a state machine has exactly one)"
                )
    return problems
