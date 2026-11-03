from __future__ import annotations

from collections.abc import Mapping

from ....assetio.values import cname_or_empty
from ...model.animgraph.schema import registry, rtti


class GraphTopologyError(ValueError):
    pass


def nested_values(root):
    stack = [root]
    while stack:
        value = stack.pop()
        yield value
        if isinstance(value, dict):
            stack.extend(reversed(value.values()))
        elif isinstance(value, list):
            stack.extend(reversed(value))


def handle_index(root) -> dict[str, dict]:
    result = {}
    for value in nested_values(root):
        if not isinstance(value, dict) or "HandleId" not in value:
            continue
        handle = str(value["HandleId"])
        if handle in result:
            raise GraphTopologyError(f"Duplicate HandleId {handle}")
        if not isinstance(value.get("Data"), dict):
            raise GraphTopologyError(f"HandleId {handle} has no Data object")
        result[handle] = value["Data"]
    return result


def reference_handle(value) -> str:
    if not isinstance(value, dict):
        return ""
    return str(value.get("HandleId", value.get("HandleRefId", "")))


def resolve(value, index: Mapping[str, dict]):
    if not isinstance(value, dict):
        return None
    handle = reference_handle(value)
    if handle:
        if handle not in index:
            raise GraphTopologyError(f"HandleRefId {handle} does not resolve")
        return index[handle]
    return value


def linked_node(node, field):
    """The node reference a link field holds, or None when the field is not a link"""
    link = node.get(field) if isinstance(node, Mapping) else None
    if not isinstance(link, Mapping):
        return None
    return link.get("node")


def has_link(node, field) -> bool:
    """Whether a link field is connected to a node"""
    return isinstance(linked_node(node, field), Mapping)


def link_targets(node, index, *, pose_only=False):
    stack = [(node, "")]
    visited_payloads = set()
    while stack:
        value, path = stack.pop()
        if isinstance(value, list):
            stack.extend(
                (item, f"{path}[{i}]") for i, item in reversed(list(enumerate(value)))
            )
            continue
        if not isinstance(value, dict):
            continue
        if reference_handle(value):
            value = resolve(value, index)
            if rtti.is_graph_node_type(str(value.get("$type", ""))):
                continue
            if id(value) in visited_payloads:
                continue
            visited_payloads.add(id(value))
        node_type = str(value.get("$type", ""))
        if registry.is_link_type(node_type):
            if not pose_only or node_type == "animPoseLink":
                target = value.get("node")
                if target is not None:
                    yield path, target
            continue
        keys = [
            p["name"]
            for p in registry.all_properties(node_type)
            if p.get("name") in value
        ]
        keys.extend(key for key in value if key not in keys and key != "$type")
        stack.extend(
            (value[key], f"{path}.{key}" if path else key) for key in reversed(keys)
        )


def compilation_children(node, index):
    node_type = str(node.get("$type", ""))
    ancestors = registry.parent_chain(node_type)
    if "animAnimNode_Container" in ancestors or node_type in {
        "animAnimNode_Root",
        "animAnimNode_Container",
    }:
        # nodes[0] is the container output whatever its type.
        children = node.get("nodes") or []
        if children:
            if not resolve(children[0], index):
                raise GraphTopologyError(f"{node_type} nodes[0] does not resolve")
            return [children[0]]
        return []
    if (
        "animAnimNode_StateMachine" in ancestors
        or node_type == "animAnimNode_StateMachine"
    ):
        return [node.get("frozenState"), *(node.get("states") or [])]
    return [target for _path, target in link_targets(node, index)]


def _compile_walk(root_reference, index):
    """The graph in compile order, each node once, depth first in link order"""
    visited = set()
    stack = [(root_reference, False)]
    while stack:
        reference, leaving = stack.pop()
        if reference is None:
            continue
        node = resolve(reference, index)
        node_type = str(node.get("$type", ""))
        if leaving:
            yield None, node_type, False
            continue
        handle = reference_handle(reference)
        if not handle or not rtti.is_graph_node_type(node_type):
            raise GraphTopologyError(
                "Initialization traversal requires a handled animation node"
            )
        if handle in visited:
            continue
        visited.add(handle)
        yield handle, node_type, True
        stack.append((reference, True))
        stack.extend(
            (child, False) for child in reversed(compilation_children(node, index))
        )


def layout_order_handles(root_reference, index) -> tuple[str, ...]:
    """Nodes in data-layout order, the order stack extenders and shrinkers pair in"""
    return tuple(
        handle
        for handle, _node_type, entering in _compile_walk(root_reference, index)
        if entering
    )


def initialization_handles(root_reference, index) -> tuple[str, ...]:
    background, foreground = [], []
    in_foreground = False
    segment_types = {
        "animAnimNode_ForegroundSegmentBegin",
        "animAnimNode_ForegroundSegmentEnd",
    }
    for handle, node_type, entering in _compile_walk(root_reference, index):
        if node_type in segment_types:
            in_foreground = not in_foreground
        if entering:
            (foreground if in_foreground else background).append(handle)
    return tuple(background + foreground)


def static_condition_result(
    condition_reference,
    index,
    *,
    visual_tags=None,
    available_animations=None,
    rig_tags=None,
    parent_tags=None,
):
    """Evaluate one serialized static condition against explicit preview context"""
    if condition_reference is None:
        raise GraphTopologyError("Static condition reference is null")
    condition = resolve(condition_reference, index)
    if not isinstance(condition, Mapping):
        raise GraphTopologyError("Static condition does not resolve")
    condition_type = str(condition.get("$type", "") or "")
    if condition_type == "animVisualTagCondition":
        tag = cname_or_empty(condition.get("visualTag"))
        if visual_tags is None:
            raise GraphTopologyError(
                f"animVisualTagCondition tag={tag or '<empty>'!r} has no visual-tag preview context"
            )
        return bool(tag and tag in visual_tags)
    if condition_type == "animHasAnimationCondition":
        name = cname_or_empty(condition.get("animationName"))
        if available_animations is None:
            raise GraphTopologyError(
                f"animHasAnimationCondition animation={name or '<empty>'!r} "
                "has no animation-availability preview context"
            )
        return bool(name and name in available_animations)
    if condition_type == "animRigTagCondition":
        tag = cname_or_empty(condition.get("tag"))
        if rig_tags is None:
            raise GraphTopologyError(
                f"animRigTagCondition tag={tag or '<empty>'!r} has no rig-tag preview context"
            )
        return bool(tag and tag in rig_tags)
    if condition_type == "animComponentTagCondition":
        tag = cname_or_empty(condition.get("animTag"))
        if parent_tags is None:
            raise GraphTopologyError(
                f"animComponentTagCondition tag={tag or '<empty>'!r} has no parent-tag preview context"
            )
        return bool(tag and tag in parent_tags)
    raise GraphTopologyError(
        f"Static condition {condition_type or '<unknown>'} cannot be evaluated in preview"
    )


def static_switch_branch(
    node,
    index,
    *,
    visual_tags=None,
    available_animations=None,
    rig_tags=None,
    parent_tags=None,
):
    """Resolve a static branch against an explicit preview context"""
    condition = node.get("condition")
    if condition is None:
        return "True"
    result = static_condition_result(
        condition,
        index,
        visual_tags=visual_tags,
        available_animations=available_animations,
        rig_tags=rig_tags,
        parent_tags=parent_tags,
    )
    return "True" if result else "False"


def visual_tag_requirements(root_reference, index):
    requirements = []
    seen_requirements = set()
    visited = set()
    stack = [(root_reference, "root")]
    while stack:
        reference, path = stack.pop()
        if reference is None:
            continue
        node = resolve(reference, index)
        if not isinstance(node, dict):
            continue
        handle = reference_handle(reference) or f"inline:{id(node)}"
        if handle in visited:
            continue
        visited.add(handle)
        node_type = str(node.get("$type", ""))
        if node_type == "animAnimNode_StaticSwitch":
            condition = node.get("condition")
            if condition is not None:
                condition = resolve(condition, index)
                if (
                    isinstance(condition, dict)
                    and condition.get("$type") == "animVisualTagCondition"
                ):
                    tag = condition.get("visualTag", "")
                    if isinstance(tag, dict):
                        tag = tag.get("$value", "")
                    tag = str(tag or "")
                    key = (tag, path)
                    if tag and tag != "None" and key not in seen_requirements:
                        seen_requirements.add(key)
                        requirements.append(key)
            for branch in ("True", "False"):
                link = node.get(branch)
                target = link.get("node") if isinstance(link, dict) else None
                if target is not None:
                    stack.append((target, f"{path}.{branch}"))
            continue
        ancestors = registry.parent_chain(node_type)
        if "animAnimNode_Container" in ancestors or node_type in {
            "animAnimNode_Root",
            "animAnimNode_Container",
        }:
            children = [
                ("nodes[0]", child) for child in compilation_children(node, index)
            ]
        else:
            children = list(link_targets(node, index, pose_only=True))
        stack.extend((child, f"{path}.{field}") for field, child in reversed(children))
    return tuple(requirements)


def state_machine_diagnostics(index):
    errors, warnings = [], []
    for handle, node in index.items():
        if "animAnimNode_StateMachine" not in registry.parent_chain(
            node.get("$type", "")
        ):
            continue
        states = node.get("states") or []
        transitions = node.get("transitions") or []
        referenced = set()
        for state_i, reference in enumerate(states):
            state = resolve(reference, index)
            if not state:
                errors.append(f"StateMachine {handle}: state {state_i} is null")
                continue
            for transition_i in state.get("outTransitionIndices") or []:
                if type(transition_i) is not int or not 0 <= transition_i < len(
                    transitions
                ):
                    errors.append(
                        f"StateMachine {handle}: state {state_i} has invalid transition index {transition_i}"
                    )
                else:
                    referenced.add(transition_i)
        for field in ("transitions", "globalTransitions", "conditionalEntries"):
            for entry_i, reference in enumerate(node.get(field) or []):
                entry = resolve(reference, index)
                if not entry:
                    errors.append(f"StateMachine {handle}: {field}[{entry_i}] is null")
                    continue
                target = entry.get("targetStateIndex")
                if type(target) is not int or not 0 <= target < len(states):
                    errors.append(
                        f"StateMachine {handle}: {field}[{entry_i}] has invalid target state {target}"
                    )
                if field != "conditionalEntries" and not resolve(
                    entry.get("interpolator"), index
                ):
                    errors.append(
                        f"StateMachine {handle}: {field}[{entry_i}] has no interpolator"
                    )
        for transition_i in sorted(set(range(len(transitions))) - referenced):
            warnings.append(
                f"StateMachine {handle}: transition {transition_i} is unreferenced"
            )
    return errors, warnings


class PreviewBoundary(Exception):
    """A graph construct the preview does not evaluate"""
