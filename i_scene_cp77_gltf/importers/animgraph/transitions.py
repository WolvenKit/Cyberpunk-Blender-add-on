import copy
import typing

import bpy

from ...animation.model.animgraph.schema import enums
from ...assetio import animgraph_json
from ...blender.animgraph import sm_records, sm_sockets
from ...blender.animgraph.builder import new_handle_id
from ...blender.animgraph.sm_properties import INTERPOLATION_TYPE_ENUM
from ...core.log import debug_exception, get_logger

_LOG = get_logger(__name__)

_LIST_LABELS = {
    "transitions": "transition",
    "globalTransitions": "global transition",
    "conditionalEntries": "conditional entry",
}


class ParserTransitionsMixin:
    def _plan_transitions(self) -> None:
        """Store each state machine's transitions as records on the nodes that own them"""
        for sm_hid, data in self.definitions.items():
            states = data.get("states")
            if not isinstance(states, list) or not states:
                continue
            sm_tree = self.tree_of_container.get(sm_hid) or self._resolve_tree(sm_hid)
            sm_node = self.bl_nodes.get(sm_hid)
            if sm_tree is None or sm_node is None:
                continue
            marks = (len(self.transition_layout_edges), len(self.unowned_transitions))
            try:
                self._import_state_machine_records(sm_hid, data, sm_node, sm_tree)
            except Exception as exc:
                debug_exception(
                    _LOG,
                    "Could not import the transitions of state machine %s; they stay read-only",
                    sm_hid,
                )
                self.problems.append(
                    f"state machine {sm_hid}: transition import failed: {exc}; "
                    f"its transitions stay read-only (exported as imported)"
                )
                del self.transition_layout_edges[marks[0] :]
                del self.unowned_transitions[marks[1] :]
                self._discard_state_machine_records(sm_node, sm_tree)

    @staticmethod
    def _discard_state_machine_records(
        sm_node: bpy.types.Node, sm_tree: bpy.types.NodeTree
    ) -> None:
        """Undo a partial records import"""
        sm_node.red_sm_records = False
        sm_node.red_sm_states.clear()
        sm_node.red_transitions.clear()
        sm_node.red_sm_import_notes = ""
        for node in list(sm_tree.nodes):
            if getattr(node, "red_type", "") in (
                sm_records.ENTRY_RED_TYPE,
                sm_records.ANY_RED_TYPE,
            ):
                sm_tree.nodes.remove(node)
                continue
            records = getattr(node, "red_transitions", None)
            if records is not None:
                records.clear()
                node.red_transitions_index = 0
            sm_sockets.remove_transition_sockets(node)

    def _import_state_machine_records(
        self,
        sm_hid: str,
        data: dict,
        sm_node: bpy.types.Node,
        sm_tree: bpy.types.NodeTree,
    ) -> None:
        handles = [self._entry_handle(entry) for entry in data.get("states")]
        transitions = data.get("transitions") or []

        sm_node.red_sm_states.clear()
        for handle in handles:
            if handle is not None:
                sm_node.red_sm_states.add().handle = handle

        state_nodes: dict[str, bpy.types.Node] = {}
        for handle in handles:
            node = self.bl_nodes.get(handle) if handle is not None else None
            if node is not None and node.id_data is sm_tree:
                state_nodes[handle] = node

        def state_text(handle: str) -> str:
            node = state_nodes.get(handle)
            label = str(getattr(node, "label", "") or "")
            label = label.removeprefix("State: ")
            return f"{label} ({handle})" if label else handle

        notes: list[str] = []
        sm_node.red_sm_import_notes = ""

        owner_of: dict[int, str] = {}
        orphan_of: dict[
            int, str
        ] = {}  # listed by a state that has no State node here
        rows_of: dict[str, list[int]] = {}
        for handle in handles:
            if handle is None:
                continue
            rows_of.setdefault(handle, [])
            state_data = self.definitions.get(handle)
            listed = (
                state_data.get("outTransitionIndices")
                if isinstance(state_data, dict)
                else None
            )
            for index in listed or []:
                if not isinstance(index, int) or not 0 <= index < len(transitions):
                    self.problems.append(
                        f"state machine {sm_hid}: state {handle} lists transition {index!r}, "
                        f"which does not exist"
                    )
                    continue
                if handle not in state_nodes:
                    orphan_of.setdefault(index, handle)
                    continue
                if index in owner_of:
                    self.problems.append(
                        f"state machine {sm_hid}: transition {index} is listed by states "
                        f"{owner_of[index]} and {handle}; kept on {owner_of[index]}"
                    )
                    notes.append(
                        f"transition {index} is also listed by state {state_text(handle)}; "
                        f"that listing was dropped (the transition is kept on state "
                        f"{state_text(owner_of[index])})"
                    )
                    continue
                owner_of[index] = handle
                rows_of[handle].append(index)

        def add_rows(owner: bpy.types.Node, list_name: str, entries, indices) -> None:
            owner.red_transitions_index = 0
            for index in indices:
                self._add_transition_record(
                    sm_hid,
                    owner,
                    list_name,
                    index,
                    entries[index],
                    handles,
                    state_nodes,
                )

        for handle, node in state_nodes.items():
            node.red_transitions.clear()
            add_rows(node, "transitions", transitions, rows_of.get(handle, ()))

        entry = sm_records.new_pseudo_node(sm_tree, sm_hid, "Entry", "Entry")
        entry.red_transitions.clear()
        default_index = data.get("defaultStateIndex", 0)
        default_target = None
        if isinstance(default_index, int) and 0 <= default_index < len(handles):
            default_target = handles[default_index]
        else:
            self.problems.append(
                f"state machine {sm_hid}: default state index {default_index!r} is not a state"
            )
        sm_records.record_from_wrapper(
            entry.red_transitions.add(),
            None,
            sm_records.DEFAULT_LIST,
            -1,
            default_target,
        )
        self._link_layout(entry, state_nodes.get(default_target))
        entries = data.get("conditionalEntries") or []
        add_rows(entry, "conditionalEntries", entries, range(len(entries)))

        any_state = sm_records.new_pseudo_node(sm_tree, sm_hid, "AnyState", "Any State")
        any_state.red_transitions.clear()
        globals_ = data.get("globalTransitions") or []
        add_rows(any_state, "globalTransitions", globals_, range(len(globals_)))
        self._import_any_state_interpolator(any_state, data.get("anyStateInterpolator"))

        sm_node.red_transitions.clear()
        unowned = [index for index in range(len(transitions)) if index not in owner_of]
        for index in unowned:
            self.unowned_transitions.append(index)
            if index in orphan_of:
                self.problems.append(
                    f"state machine {sm_hid}: transition {index} is listed by state {orphan_of[index]}, "
                    f"which has no State node in this state machine; kept on the state machine"
                )
                continue
            self.problems.append(
                f"state machine {sm_hid}: transition {index} is not listed by any state; "
                f"kept on the state machine"
            )
        add_rows(sm_node, "transitions", transitions, unowned)

        sm_node.red_sm_records = True
        sm_node.red_sm_import_notes = "\n".join(notes)
        for node in (*state_nodes.values(), entry, any_state):
            sm_sockets.sync_transition_sockets(node)

    def _add_transition_record(
        self,
        sm_hid: str,
        owner: bpy.types.Node,
        list_name: str,
        index: int,
        entry: typing.Any,
        handles: list[str | None],
        state_nodes: dict[str, bpy.types.Node],
    ) -> None:
        what = f"state machine {sm_hid}: {_LIST_LABELS[list_name]} {index}"
        shared = [False]

        def resolve(ref_id: str) -> dict | None:
            copied = self._private_copy(ref_id)
            if copied is not None:
                shared[0] = True
            return copied

        wrapper = (
            entry
            if isinstance(entry, dict) and isinstance(entry.get("Data"), dict)
            else None
        )
        if wrapper is None and isinstance(entry, dict) and "HandleRefId" in entry:
            wrapper = resolve(str(entry["HandleRefId"]))
        if wrapper is None:
            self.problems.append(f"{what} could not be read; it was dropped")
            return

        target_index = self._transition_target_index(wrapper["Data"])
        target = None
        if isinstance(target_index, int) and 0 <= target_index < len(handles):
            target = handles[target_index]
        if target is None:
            self.problems.append(f"{what} has no valid target state ({target_index!r})")

        rec = owner.red_transitions.add()
        sm_records.record_from_wrapper(
            rec, wrapper, list_name, index, target, resolve=resolve
        )
        if shared[0]:
            self.problems.append(f"{what} shared handle id; copied")
        self._link_layout(owner, state_nodes.get(target))

    def _link_layout(
        self, src: bpy.types.Node | None, dst: bpy.types.Node | None
    ) -> None:
        """Let layout place src near the state it transitions to"""
        if src is not None and dst is not None and src is not dst:
            self.transition_layout_edges.append((src, dst))

    def _private_copy(self, ref_id: str) -> dict | None:
        """A copy of the wrapper ref_id names, with fresh handles throughout"""
        data = self.handle_data.get(str(ref_id))
        if not isinstance(data, dict):
            return None
        wrapper = {"HandleId": str(ref_id), "Data": copy.deepcopy(data)}
        stack: list[typing.Any] = [wrapper]
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                if "HandleId" in value and isinstance(value.get("Data"), dict):
                    value["HandleId"] = new_handle_id()
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)
        return wrapper

    def _import_any_state_interpolator(
        self, node: bpy.types.Node, value: typing.Any
    ) -> None:
        node.red_sm_any_interpolator_json = animgraph_json.dumps(value, indent=None)
        idata = value.get("Data") if isinstance(value, dict) else None
        choice = "Linear"
        if isinstance(idata, dict) and "interpolationType" in idata:
            choice = enums.normalize_choice(
                INTERPOLATION_TYPE_ENUM, idata["interpolationType"]
            )
        try:
            node.red_sm_any_interpolation = choice
        except TypeError:
            self.problems.append(
                f"any state interpolation {choice!r} is not a known value; kept in the original JSON"
            )

    @staticmethod
    def _transition_target_index(data: dict) -> int | None:
        for key in ("targetStateIndex", "stateIndex", "targetIndex"):
            value = data.get(key)
            if isinstance(value, int):
                return value
        return None

    def _payload_of(self, entry: typing.Any) -> dict | None:
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

    def _unique_socket_name(self, node: bpy.types.Node, in_out: str, base: str) -> str:
        collection = node.outputs if in_out == "OUTPUT" else node.inputs
        name = base
        suffix = 2
        while collection.get(name) is not None:
            name = f"{base} ({suffix})"
            suffix += 1
        return name
