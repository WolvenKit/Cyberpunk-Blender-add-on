import json
import typing

import bpy

from ...animation.animgraph_constants import COMPARE_OPS, CONTAINER_OUTPUT_NAME
from ...blender.animgraph.sockets import bind_output_socket, bind_red_socket

class ParserTransitionsMixin:
    def _plan_transitions(self) -> None:
        """Declare editor-derived state-machine flow constructs."""
        for sm_hid, data in self.definitions.items():
            states = data.get("states")
            if not isinstance(states, list) or not states:
                continue
            transitions = data.get("transitions") or []
            handles, names = self._state_handles_and_names(states)
            sm_tree = self.tree_of_container.get(sm_hid) or self._resolve_tree(sm_hid)
            if sm_tree is None:
                continue

            entry_node = self._make_state_machine_pseudo(sm_tree, sm_hid, "Entry", "Entry")
            output_node = self._make_state_machine_output(sm_tree, sm_hid, handles, names)
            self.state_machine_output_node[sm_hid] = output_node

            default_index = data.get("defaultStateIndex", 0)
            if isinstance(default_index, int) and 0 <= default_index < len(handles):
                self._plan_transition_edge(
                    entry_node, f"Default -> {names[default_index]}",
                    handles[default_index], f"Default <- Entry", output_node)

            for entry in data.get("conditionalEntries") or []:
                cond_entry = self._payload_of(entry) or (entry if isinstance(entry, dict) else None)
                if not isinstance(cond_entry, dict):
                    continue
                target_index = self._transition_target_index(cond_entry)
                if target_index is None or not (0 <= target_index < len(handles)):
                    continue
                cond = self._summarize_condition(cond_entry.get("condition"))
                label = self._transition_label(cond_entry, cond)
                self._plan_transition_edge(
                    entry_node, f"{label} -> {names[target_index]}",
                    handles[target_index], f"{label} <- Entry", output_node)

            for si, src_handle in enumerate(handles):
                source_data = self.definitions.get(src_handle) if src_handle is not None else None
                if not isinstance(source_data, dict) or src_handle not in self.bl_nodes:
                    continue
                for ti in source_data.get("outTransitionIndices", []) or []:
                    if not isinstance(ti, int) or not (0 <= ti < len(transitions)):
                        continue
                    trans = self._payload_of(transitions[ti])
                    if not isinstance(trans, dict):
                        continue
                    tgt_idx = self._transition_target_index(trans)
                    if tgt_idx is None or not (0 <= tgt_idx < len(handles)):
                        continue
                    tgt_handle = handles[tgt_idx]
                    if tgt_handle is None or tgt_handle not in self.bl_nodes or tgt_handle == src_handle:
                        continue
                    cond = self._transition_label(trans, self._summarize_condition(trans.get("condition")))
                    self._plan_transition_edge(
                        self.bl_nodes[src_handle], f"{cond} -> {names[tgt_idx]}",
                        tgt_handle, f"{cond} <- {names[si]}", output_node)

            global_transitions = data.get("globalTransitions") or []
            if global_transitions:
                any_node = self._make_state_machine_pseudo(sm_tree, sm_hid, "AnyState", "Any State")
                for gi, entry in enumerate(global_transitions):
                    trans = self._payload_of(entry)
                    if not isinstance(trans, dict):
                        continue
                    tgt_idx = self._transition_target_index(trans)
                    if tgt_idx is None or not (0 <= tgt_idx < len(handles)):
                        continue
                    label = self._transition_label(
                        trans, self._summarize_condition(trans.get("condition")) or f"Global {gi}")
                    interp = self._summarize_interpolator(data.get("anyStateInterpolator"))
                    if interp:
                        label = f"{label} [{interp}]"
                    self._plan_transition_edge(
                        any_node, f"{label} -> {names[tgt_idx]}",
                        handles[tgt_idx], f"{label} <- Any State", output_node)

    def _state_handles_and_names(self, states: typing.List[typing.Any]) -> typing.Tuple[typing.List[typing.Optional[str]], typing.List[str]]:
        handles: typing.List[typing.Optional[str]] = []
        names: typing.List[str] = []
        for entry in states:
            handle = self._entry_handle(entry)
            inner = self.definitions.get(handle) if handle is not None else None
            name = (inner.get("name") or {}).get("$value") if isinstance(inner, dict) else None
            handles.append(handle)
            names.append(name or (handle if handle is not None else "?"))
        return handles, names

    def _make_state_machine_pseudo(self, tree: bpy.types.NodeTree, sm_hid: str,
                                   short: str, label: str) -> bpy.types.Node:
        key = f"editor{short}_{sm_hid}"
        existing = tree.nodes.get(key)
        if existing is not None:
            return existing
        node = self._new_pseudo_node(tree, short, label, key)
        return node

    def _make_state_machine_output(self, tree: bpy.types.NodeTree, sm_hid: str,
                                   state_handles: typing.List[typing.Optional[str]],
                                   state_names: typing.List[str]) -> bpy.types.Node:
        key = f"editorStateMachineOutput_{sm_hid}"
        existing = tree.nodes.get(key)
        node = existing if existing is not None else self._new_pseudo_node(
            tree, "StateMachineOutput", "StateMachine Runtime Output", key)

        if node.outputs.get(CONTAINER_OUTPUT_NAME) is None:
            sock = node.outputs.new('REDengine_AnimGraphSocket_Pose', CONTAINER_OUTPUT_NAME)
        else:
            sock = node.outputs.get(CONTAINER_OUTPUT_NAME)
        if sock is not None:
            bind_output_socket(
                sock, owner_handle=getattr(node, 'red_handle_id', ''),
                link_type='animPoseLink', exportable=False,
                edge_semantics='state_summary', pseudo=True)

        node["red_state_handles"] = json.dumps([h for h in state_handles if h is not None])
        node["red_state_names"] = json.dumps(state_names)


        for handle, name in zip(state_handles, state_names):
            if handle is None:
                continue
            state_node = self.bl_nodes.get(handle)
            if state_node is None or state_node.id_data is not tree:
                continue
            in_name = self._unique_socket_name(node, 'INPUT', f"State: {name}")
            in_sock = node.inputs.new('REDengine_AnimGraphSocket_Pose', in_name)
            bind_red_socket(
                in_sock, role='input', owner_handle=getattr(node, 'red_handle_id', ''),
                field_name='states', json_path=f'states[{state_handles.index(handle)}]',
                link_type='animPoseLink', source_handle=handle,
                target_handle=getattr(node, 'red_handle_id', ''), exportable=False,
                edge_semantics='state_summary', pseudo=True)
            out_sock = self._output_socket_of(state_node, handle)
            if out_sock is None:
                continue
            if self._safe_new_link(tree, state_node, out_sock.name, node, in_sock.name):
                self.drawn_state_aggregation_edges += 1
                self.transition_layout_edges.append((state_node, node))
        return node

    def _plan_transition_edge(self, src_node: bpy.types.Node, out_label: str,
                              target_handle: typing.Optional[str], in_label: str,
                              output_node: typing.Optional[bpy.types.Node] = None) -> None:
        if target_handle is None or target_handle not in self.bl_nodes:
            self.failed_transition_edges.append((src_node.name, f"missing target {target_handle}"))
            return
        tgt_node = self.bl_nodes[target_handle]
        if src_node.id_data is not tgt_node.id_data:
            self.failed_transition_edges.append((src_node.name, f"tree mismatch to {target_handle}"))
            self.problems.append(
                f"transition endpoint tree mismatch: {src_node.name} -> {target_handle}")
            return

        condition = out_label.split(" -> ", 1)[0]
        target_label = out_label.split(" -> ", 1)[1] if " -> " in out_label else tgt_node.label
        source_label = in_label.split(" <- ", 1)[1] if " <- " in in_label else src_node.label
        index = len(self.planned_transitions) + 1
        key = f"editorTransition_{src_node.red_handle_id}_{target_handle}_{index}"
        node = self._new_pseudo_node(src_node.id_data, "Transition", f"Transition: {source_label} → {target_label}", key)
        node["red_transition_condition"] = condition
        node["red_transition_source"] = str(source_label)
        node["red_transition_target"] = str(target_label)
        node["red_transition_source_node"] = src_node.name
        node["red_transition_target_node"] = tgt_node.name
        node["red_transition_source_handle"] = str(getattr(src_node, "red_handle_id", ""))
        node["red_transition_target_handle"] = str(target_handle)


        self.transition_layout_edges.append((src_node, node))


        out_sock = node.outputs.new('REDengine_AnimGraphSocket_Transition', "Transition")
        bind_red_socket(
            out_sock, role='output', owner_handle=getattr(node, 'red_handle_id', ''),
            field_name='transition', json_path='transition', link_type='editorTransition',
            source_handle=getattr(src_node, 'red_handle_id', ''), target_handle=str(target_handle),
            exportable=False, edge_semantics='transition_summary', pseudo=True)
        if output_node is not None and output_node.id_data is node.id_data:
            in_name = self._unique_socket_name(
                output_node, 'INPUT', f"Transition: {source_label} → {target_label}")
            in_sock = output_node.inputs.new('REDengine_AnimGraphSocket_Transition', in_name)
            bind_red_socket(
                in_sock, role='input', owner_handle=getattr(output_node, 'red_handle_id', ''),
                field_name='transitions', json_path=f'transitions[{index - 1}]',
                link_type='editorTransition', source_handle=getattr(src_node, 'red_handle_id', ''),
                target_handle=str(target_handle), exportable=False,
                edge_semantics='transition_summary', pseudo=True)
            if self._safe_new_link(node.id_data, node, out_sock.name, output_node, in_sock.name):
                self.drawn_transition_edges += 1
                self.transition_layout_edges.append((node, output_node))

        self.planned_transitions.append(node)

    @staticmethod
    def _transition_target_index(data: dict) -> typing.Optional[int]:
        for key in ("targetStateIndex", "stateIndex", "targetIndex"):
            value = data.get(key)
            if isinstance(value, int):
                return value
        return None

    def _transition_label(self, data: dict, condition: str) -> str:
        parts = [condition or "?"]
        priority = data.get("priority")
        if isinstance(priority, int) and priority:
            parts.append(f"p{priority}")
        if data.get("isForcedToTrue"):
            parts.append("forced")
        if data.get("isEnabled") is False:
            parts.append("disabled")
        duration = data.get("duration")
        if isinstance(duration, (int, float)) and duration:
            parts.append(f"{duration:.2f}s")
        return " ".join(parts)

    def _summarize_interpolator(self, value: typing.Any) -> str:
        data = self._payload_of(value) if isinstance(value, dict) else None
        if not isinstance(data, dict):
            return ""
        return data.get("$type", "").replace("anim", "").replace("AnimStateTransitionInterpolator", "Interp")

    def _payload_of(self, entry: typing.Any) -> typing.Optional[dict]:
        if not isinstance(entry, dict):
            return None
        if isinstance(entry.get("Data"), dict):
            return entry["Data"]
        if "$type" in entry:
            return entry
        if "HandleRefId" in entry:
            return self.handle_data.get(str(entry["HandleRefId"]))
        if "HandleId" in entry:
            return self.handle_data.get(str(entry["HandleId"]))
        return None

    def _sync_container_nodes(self) -> None:
        for hid, key, caption in self.pending_container_inputs:
            node = self.bl_nodes.get(hid)
            socket = node.inputs.get(caption) if node is not None else None
            if socket is not None:
                self.input_socket[(hid, key)] = socket

    def _link_transitions(self) -> None:
        return

    def _summarize_condition(self, condition: typing.Any) -> str:
        if not isinstance(condition, dict):
            return "?"
        data = self._payload_of(condition) or condition
        if not isinstance(data, dict):
            return "?"
        ctype = data.get("$type", "")
        short = ctype.replace("animAnimStateTransitionCondition_", "")
        lower = short.lower()

        if "compositesimultaneous" in lower:
            children = []
            for key in ("conditions", "conditionList", "childConditions"):
                value = data.get(key)
                if isinstance(value, list):
                    children.extend(value)
            rendered = [self._summarize_condition(c) for c in children]
            rendered = [r for r in rendered if r and r != "?"]
            return " AND ".join(rendered) if rendered else "AND(?)"

        if "externalevent" in lower:
            ev = self._cname(data.get("eventName")) or self._cname(data.get("name"))
            return f"evt:{ev}" if ev else "evt"
        if "animevent" in lower:
            ev = self._cname(data.get("eventName")) or self._cname(data.get("event"))
            return f"animEvt:{ev}" if ev else "animEvt"
        if "footphase" in lower:
            phase = data.get("phase") or self._cname(data.get("phaseName"))
            return f"foot:{phase}" if phase else "footPhase"
        if "animend" in lower or "anyanimend" in lower:
            ev = self._cname(data.get("eventName"))
            return f"animEnd:{ev}" if ev else "animEnd"
        if "hasanimation" in lower:
            name = self._cname(data.get("animationName")) or self._cname(data.get("animName"))
            return f"hasAnim:{name}" if name else "hasAnim"
        if "timed" in lower or "time" == lower:
            value = data.get("time") or data.get("duration") or data.get("seconds")
            return f"time>={value}" if value is not None else "timed"
        if "feature" in lower:
            feature = self._cname(data.get("featureName")) or self._cname(data.get("animFeatureName"))
            return f"feature:{feature}" if feature else short or "feature"
        if "wrappervalue" in lower:
            return "wrapperValue"
        if "locomotion" in lower:
            return short or "locomotion"

        if "variable" in lower:
            var = self._cname(data.get("variableName")) or "?"
            op = COMPARE_OPS.get(data.get("compareFunc"), data.get("compareFunc", "=="))
            if "bool" in lower and "compareValue" not in data:
                return f"{var}==True"
            return f"{var}{op}{data.get('compareValue', '?')}"

        return short or "?"

    @staticmethod
    def _cname(value: typing.Any) -> str:
        if isinstance(value, dict):
            text = value.get("$value", "")
            return "" if text == "None" else str(text)
        if isinstance(value, str):
            return "" if value == "None" else value
        return ""

    def _safe_new_link(self, tree: bpy.types.NodeTree,
                       src_node: bpy.types.Node, out_name: str,
                       dst_node: bpy.types.Node, in_name: str) -> bool:
        if src_node.id_data is not tree or dst_node.id_data is not tree:
            return False
        out_sock = src_node.outputs.get(out_name)
        in_sock = dst_node.inputs.get(in_name)
        if out_sock is None or in_sock is None:
            return False
        for link in tree.links:
            if (getattr(link.from_node, 'name', None) == src_node.name
                    and getattr(link.to_node, 'name', None) == dst_node.name
                    and getattr(link.from_socket, 'name', None) == out_name
                    and getattr(link.to_socket, 'name', None) == in_name):
                return False
        try:
            tree.links.new(out_sock, in_sock)
            return True
        except Exception as exc:
            self.problems.append(
                f"could not create visual helper link {src_node.name}.{out_name} -> "
                f"{dst_node.name}.{in_name}: {exc}")
            return False

    def _unique_socket_name(self, node: bpy.types.Node, in_out: str, base: str) -> str:
        collection = node.outputs if in_out == 'OUTPUT' else node.inputs
        name = base
        suffix = 2
        while collection.get(name) is not None:
            name = f"{base} ({suffix})"
            suffix += 1
        return name

    def _declare_transition_socket(self, node: bpy.types.Node, name: str, in_out: str) -> None:
        self._ensure_socket(node, in_out, name, 'REDengine_AnimGraphSocket_Transition')
