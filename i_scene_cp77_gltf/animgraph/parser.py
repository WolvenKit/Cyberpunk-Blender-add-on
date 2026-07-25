import bpy
import json
import typing
from collections import defaultdict, deque
from mathutils import Vector

from . import categories, rtti_schema, curve_mapping, graph_index, variable_bindings, math_expression, node_presenters, roundtrip_audit
from .constants import (
    ANIM_NODE_PREFIX, LINK_TYPES, LINK_SOCKET,
    COMPARE_OPS, CONTAINER_FIELDS, CONTAINER_OUTPUT_NAME, OUTPUT_NODE_TYPE,
    HIDDEN_FIELDS, HIDDEN_FIELD_PREFIXES, VAR_ARRAYS,
)
from .categories import NODE_CATEGORY_COLORS, CONTAINER_TYPES
from .properties import add_node_property, clear_node_properties
from .sockets import bind_input_socket, bind_output_socket, bind_red_socket


class AnimGraphParser:
    """Import a WolvenKit animGraph into editable Blender node trees."""


    def __init__(self, root_tree: bpy.types.NodeTree):
        self.root_tree = root_tree
        self.definitions: typing.Dict[str, dict] = {}
        self.handle_data: typing.Dict[str, dict] = {}
        self.node_links: typing.Dict[str, typing.List[typing.Tuple[str, str, dict]]] = {}
        self.container_of: typing.Dict[str, typing.Optional[str]] = {}
        self.containers: typing.Set[str] = set()
        self.tree_of_container: typing.Dict[str, bpy.types.NodeTree] = {}
        self.group_output_node: typing.Dict[str, bpy.types.Node] = {}
        self.bl_nodes: typing.Dict[str, bpy.types.Node] = {}
        self.referenced_kind: typing.Dict[str, str] = {}
        self.output_socket: typing.Dict[str, bpy.types.NodeSocket] = {}
        self.input_socket: typing.Dict[typing.Tuple[str, str], bpy.types.NodeSocket] = {}
        self.pending_container_inputs: typing.List[typing.Tuple[str, str, str]] = []


        self.planned_transitions: typing.List[bpy.types.Node] = []
        self.transition_layout_edges: typing.List[typing.Tuple[bpy.types.Node, bpy.types.Node]] = []
        self.drawn_transition_edges = 0
        self.drawn_state_aggregation_edges = 0
        self.failed_transition_edges: typing.List[typing.Tuple[str, str]] = []
        self._iface_names: typing.Dict[typing.Tuple[str, str], typing.Set[str]] = {}
        self.problems: typing.List[str] = []
        self.context: typing.Optional[bpy.types.Context] = None
        self.group_wires: typing.List[typing.Tuple[bpy.types.Node, bpy.types.Node]] = []
        self.deferred_links: typing.List[typing.Tuple[bpy.types.Node, str, bpy.types.Node, str]] = []
        self.boundary_links: typing.List[typing.Tuple[bpy.types.Node, str, bpy.types.Node, str]] = []
        self.group_input_node: typing.Dict[str, bpy.types.Node] = {}
        self.state_machine_output_node: typing.Dict[str, bpy.types.Node] = {}
        self.root_output_node: typing.Optional[bpy.types.Node] = None
        self.root_output_link: typing.Optional[dict] = None
        self.drawn_link_edges = 0
        self.routed_cross_tree_links = 0
        self.unroutable_cross_tree_links = 0
        self.skipped_cross_tree_links = 0
        self.layout_overlap_count = 0
        self.layout_trees_checked = 0
        self.curve_widgets_initialized = 0
        self.curve_widgets_failed = 0
        self.source_alignment_report = {}
        self.roundtrip_audit_report = {}
        self.dangle_editor_particles = 0
        self.dangle_editor_constraints = 0
        self.dangle_editor_shapes = 0
        self.math_expression_nodes = 0
        self.math_expression_inputs = 0

    def execute(self, payload: dict, context: typing.Optional[bpy.types.Context] = None) -> None:
        self.context = context
        self._annotate_document_identity(payload)
        root_chunk = payload.get("Data", {}).get("RootChunk", {})
        self._discover(root_chunk)
        self._annotate_tree_identity(root_chunk)
        self._build_subgraph_trees()
        self._instantiate_nodes()
        self._enumerate_all_links()
        self._validate_referenced_output_kinds()


        self._build_group_io()
        self._build_node_sockets()
        self._plan_root_output(root_chunk)
        self._plan_boundary_links()
        self._plan_transitions()
        self._sync_container_nodes()

        self._resolve_links()
        self._link_boundary_links()
        self._wire_group_outputs()
        self._link_root_output()
        self._link_transitions()
        self._schedule_deferred()
        self._layout_all()
        self._import_variables(root_chunk)
        self._import_features(root_chunk)
        self._initialize_curve_widgets()
        self._audit_source_alignment()
        self._audit_roundtrip_readiness()
        self._emit_report()



    def _annotate_document_identity(self, payload: dict) -> None:
        try:
            header = payload.get("Header", {}) if isinstance(payload, dict) else {}
            data = payload.get("Data", {}) if isinstance(payload, dict) else {}
            data_meta = {
                key: value for key, value in data.items()
                if key != "RootChunk"
            } if isinstance(data, dict) else {}
            self.root_tree["red_source_header_json"] = json.dumps(
                header if isinstance(header, dict) else {},
                ensure_ascii=False, separators=(",", ":"),
            )
            self.root_tree["red_source_data_meta_json"] = json.dumps(
                data_meta, ensure_ascii=False, separators=(",", ":"),
            )
        except Exception as exc:
            self.problems.append(f"document identity annotation failed: {exc}")

    def _initialize_curve_widgets(self) -> None:
        try:
            ok, failed = curve_mapping.initialize_native_curves_for_tree(self.root_tree)
        except Exception as exc:
            self.problems.append(f"native curve widget initialization failed: {exc}")
            return
        self.curve_widgets_initialized = ok
        self.curve_widgets_failed = failed
        if failed:
            self.problems.append(f"{failed} native curve widget helper(s) could not be initialized")

    def _annotate_tree_identity(self, root_chunk: dict) -> None:
        try:
            root_handle = self._entry_handle(root_chunk.get("rootNode"))
            if root_handle is None:
                for hid, data in self.definitions.items():
                    if isinstance(data, dict) and data.get("$type") == f"{ANIM_NODE_PREFIX}Root":
                        root_handle = hid
                        break

            nodes_to_init = root_chunk.get("nodesToInit") or []
            init_root_handle = ""
            init_refs: typing.List[str] = []
            init_inline_after_root = 0
            if isinstance(nodes_to_init, list):
                for index, entry in enumerate(nodes_to_init):
                    hid = self._entry_handle(entry)
                    if hid is None:
                        continue
                    if index == 0 and isinstance(entry, dict) and isinstance(entry.get("Data"), dict):
                        init_root_handle = str(hid)
                        continue


                    init_refs.append(str(hid))
                    if isinstance(entry, dict) and isinstance(entry.get("Data"), dict):
                        init_inline_after_root += 1


            root_nodes_order: typing.List[typing.Dict[str, typing.Any]] = []
            root_entry = None
            if isinstance(nodes_to_init, list) and nodes_to_init:
                first = nodes_to_init[0]
                if isinstance(first, dict) and isinstance(first.get("Data"), dict):
                    root_entry = first
            if root_entry is None:
                rn = root_chunk.get("rootNode")
                if isinstance(rn, dict) and isinstance(rn.get("Data"), dict):
                    root_entry = rn
            root_data = root_entry.get("Data") if isinstance(root_entry, dict) else None
            root_nodes = root_data.get("nodes") if isinstance(root_data, dict) else None
            if isinstance(root_nodes, list):
                for item in root_nodes:
                    hid = self._entry_handle(item)
                    if hid is None:
                        continue
                    inline = isinstance(item, dict) and isinstance(item.get("Data"), dict) and bool(item.get("HandleId"))
                    root_nodes_order.append({"handle": str(hid), "inline": bool(inline)})

            root_output_spec: typing.Dict[str, typing.Any] = {"present": False, "link_type": "animPoseLink", "handle": "", "null": True}
            if isinstance(root_data, dict):
                root_output = root_data.get("outputNode")
                if isinstance(root_output, dict) and root_output.get("$type") in LINK_TYPES:
                    target = self._link_target_handle(root_output)
                    root_output_spec = {
                        "present": True,
                        "link_type": str(root_output.get("$type") or "animPoseLink"),
                        "handle": str(target or ""),
                        "null": target is None,
                    }


            root_data_fields: typing.Dict[str, typing.Any] = {}
            if isinstance(root_data, dict):
                for key, value in root_data.items():
                    if key in {"nodes", "outputNode"}:
                        continue
                    root_data_fields[str(key)] = value

            scalar_keys = (
                "additionalAnimDatabases",
                "cookingPlatform",
                "hackAlwaysSample",
                "hasMixerSlot",
                "isPaused",
                "jsonFilesDirectory",
                "oneFrameToggle",
                "staticCommandsRig",
                "timeDeltaMultiplier",
                "useAnimCommands",
                "useAnimCommandsForCrowd",
                "useAnimStaticCommands",
                "useLunaticMode",
            )
            scalars = {key: root_chunk.get(key) for key in scalar_keys if key in root_chunk}

            self.root_tree["red_root_handle"] = str(root_handle or init_root_handle or "")
            self.root_tree["red_nodes_to_init_count"] = len(nodes_to_init) if isinstance(nodes_to_init, list) else 0
            self.root_tree["red_nodes_to_init_root_handle"] = str(init_root_handle or root_handle or "")
            self.root_tree["red_nodes_to_init_refs_json"] = json.dumps(init_refs, separators=(",", ":"))
            self.root_tree["red_nodes_to_init_inline_after_root"] = int(init_inline_after_root)
            self.root_tree["red_root_nodes_order_json"] = json.dumps(root_nodes_order, separators=(",", ":"))
            self.root_tree["red_root_output_json"] = json.dumps(root_output_spec, separators=(",", ":"))
            self.root_tree["red_root_data_fields_json"] = json.dumps(root_data_fields, separators=(",", ":"))
            self.root_tree["red_rootchunk_scalars_json"] = json.dumps(scalars, separators=(",", ":"))
            self.root_tree["red_public_tree"] = True
            self.root_tree["red_source_alignment_version"] = "source-alignment-2-nodes-to-init"
            if init_inline_after_root:
                self.problems.append(
                    f"nodesToInit contained {init_inline_after_root} inline entry/entries after the root; "
                    f"export will reconstruct them as HandleRefId entries")
        except Exception as exc:
            self.problems.append(f"tree source identity annotation failed: {exc}")

    def _audit_source_alignment(self) -> None:
        try:
            report = graph_index.audit_parser(self)
            self.source_alignment_report = report
            graph_index.write_report_to_tree(self.root_tree, report)
            for problem in report.get('problems', []):
                self.problems.append(f"source alignment: {problem}")
        except Exception as exc:
            self.source_alignment_report = {}
            self.problems.append(f"source alignment audit failed: {exc}")

    def _schedule_deferred(self) -> None:
        if not self.deferred_links:
            return
        self.deferred_links = self._link_named(self.deferred_links)
        if not self.deferred_links:
            return
        timers = getattr(getattr(bpy, "app", None), "timers", None)
        if timers is not None:
            pending = list(self.deferred_links)

            def finish():
                remaining = self._link_named(pending)
                print(f"[animgraph import] deferred links connected: "
                      f"{len(pending) - len(remaining)}/{len(pending)}")
                for src_node, out_name, tgt_node, in_name in remaining:
                    print(f"[animgraph import] WARNING: could not link "
                          f"{src_node.name}.{out_name} -> {tgt_node.name}.{in_name}")
                return None

            timers.register(finish, first_interval=0.0)
        else:
            self.problems.append(
                f"{len(self.deferred_links)} links could not be made and no timer "
                f"API is available to retry after the update flush")

    @staticmethod
    def _link_named(entries):
        remaining = []
        for src_node, out_name, tgt_node, in_name in entries:
            if src_node.id_data is not tgt_node.id_data:
                remaining.append((src_node, out_name, tgt_node, in_name))
                continue
            out_sock = src_node.outputs.get(out_name)
            in_sock = tgt_node.inputs.get(in_name)
            if out_sock is not None and in_sock is not None:
                if not any(l.from_socket is out_sock and l.to_socket is in_sock
                           for l in src_node.id_data.links):
                    src_node.id_data.links.new(out_sock, in_sock)
            else:
                remaining.append((src_node, out_name, tgt_node, in_name))
        return remaining

    def _audit_roundtrip_readiness(self) -> None:
        try:
            report = roundtrip_audit.report_for_tree(self.root_tree)
            self.roundtrip_audit_report = report
            roundtrip_audit.write_report_to_tree(self.root_tree, report)
            blockers = int((report.get('counters') or {}).get('blocking_issues', 0) or 0)
            if blockers:
                self.problems.append(f"round-trip audit found {blockers} blocking issue(s)")
        except Exception as exc:
            self.roundtrip_audit_report = {}
            self.problems.append(f"round-trip audit failed: {exc}")

    def _emit_report(self) -> None:
        internal_subgraphs = sum(
            1 for hid, tree in self.tree_of_container.items()
            if tree is not self.root_tree
        )
        enumerated = sum(len(self.node_links.get(h, ())) for h in self.bl_nodes)
        unresolved = enumerated - len(self.input_socket)
        planned = len(self.planned_transitions)
        represented = planned - len(self.failed_transition_edges)
        deferred = len(self.deferred_links)
        if unresolved:
            self.problems.append(f"{unresolved} link sockets could not be materialised")
        if self.failed_transition_edges:
            self.problems.append(f"{len(self.failed_transition_edges)} transition record(s) failed during creation")
        meta = rtti_schema.stats()
        presenter_stats = node_presenters.summary()
        meta_tag = f"schema=(nodes={meta.get('concrete_anim_nodes', 0)}/{meta.get('anim_nodes', 0)} enums={meta.get('enum_definitions', 0)} flags={meta.get('flag_enums', 0)} presenters={presenter_stats.get('presenters', 0)}) " if meta.get('metadata_loaded') else "schema=(nodes=0/0 enums=0 flags=0 presenters=0) "
        audit_summary = (self.source_alignment_report or {}).get("summary", "")
        audit_tag = f"source-alignment=({audit_summary}) " if audit_summary else ""
        var_bound = int(self.root_tree.get('red_variable_bound_nodes', 0)) if hasattr(self.root_tree, 'get') else 0
        var_unbound = int(self.root_tree.get('red_variable_unbound_nodes', 0)) if hasattr(self.root_tree, 'get') else 0
        variable_tag = f"variables=(declared={len(self.root_tree.variables)} bound-nodes={var_bound} unbound-nodes={var_unbound}) "
        math_tag = f"math-expressions=(nodes={self.math_expression_nodes} inputs={self.math_expression_inputs}) "
        roundtrip_tag = ''
        try:
            rc = (self.roundtrip_audit_report or {}).get('counters', {})
            if rc:
                roundtrip_tag = (
                    f"roundtrip=(ready={bool(rc.get('ready', 0))} "
                    f"nodes={rc.get('runtime_nodes_schema_known', 0)}/{rc.get('runtime_nodes', 0)} "
                    f"props={rc.get('properties_encodable', 0)}/{rc.get('properties_total', 0)} "
                    f"links={rc.get('dataflow_links_encodable', 0)}/{rc.get('dataflow_links', 0)} "
                    f"blockers={rc.get('blocking_issues', 0)} warnings={rc.get('warnings', 0)}) "
                )
        except Exception:
            roundtrip_tag = ''
        enum_tag = ''
        print(f"[animgraph import] nodes={len(self.bl_nodes)} public-trees=1 internal-subgraphs={internal_subgraphs} "
              f"{meta_tag}"
              f"{audit_tag}"
              f"{variable_tag}"
              f"{math_tag}"
              f"{enum_tag}"
              f"{roundtrip_tag}"
              f"link-sockets={len(self.input_socket)} link-edges={self.drawn_link_edges} "
              f"transitions={represented}/{planned} transition-records={represented} "
              f"state-aggregation-edges={self.drawn_state_aggregation_edges} "
              f"transition-aggregation-edges={self.drawn_transition_edges} "
              f"deferred-links={deferred} "
              f"cross-tree-routed={self.routed_cross_tree_links} "
              f"cross-tree-unroutable={self.unroutable_cross_tree_links} "
              f"unresolved-inputs={unresolved} "
              f"curve-widgets={self.curve_widgets_initialized}"
              f"/{self.curve_widgets_initialized + self.curve_widgets_failed} "
              f"layout-overlaps={self.layout_overlap_count} "
              f"dangle-editor=(particles={self.dangle_editor_particles} "
              f"constraints={self.dangle_editor_constraints} shapes={self.dangle_editor_shapes})")
        for problem in self.problems:
            print(f"[animgraph import] WARNING: {problem}")

    def _discover(self, root_chunk: dict) -> None:
        """Discover handle payloads and handle references before node construction."""
        stack: typing.List[typing.Any] = [root_chunk]
        while stack:
            obj = stack.pop()
            if isinstance(obj, dict):
                if "HandleId" in obj and isinstance(obj.get("Data"), dict):
                    data = obj["Data"]
                    self.handle_data.setdefault(str(obj["HandleId"]), data)
                    if data.get("$type", "").startswith(ANIM_NODE_PREFIX):
                        self.definitions.setdefault(str(obj["HandleId"]), data)
                stack.extend(obj.values())
            elif isinstance(obj, list):
                stack.extend(obj)

        for hid, data in self.definitions.items():
            if self._has_children(data):
                self.containers.add(hid)
        for chid in self.containers:
            data = self.definitions[chid]
            for field in CONTAINER_FIELDS:
                value = data.get(field)
                entries = value if isinstance(value, list) else [value]
                for entry in entries:
                    child = self._entry_handle(entry)
                    if child is not None and child in self.definitions:
                        self.container_of.setdefault(child, chid)
        top_level = [hid for hid in self.definitions if hid not in self.container_of]
        for hid in top_level:
            self.container_of[hid] = None


        orphans = {hid for hid in top_level if not self._has_children(self.definitions[hid])}
        if orphans:
            referrer_of: typing.Dict[str, str] = {}
            for owner, data in self.definitions.items():
                for _key, _caption, wrapper in self._enumerate_links(owner):
                    target = self._link_target_handle(wrapper)
                    if target in orphans:
                        referrer_of.setdefault(target, owner)
            for _ in range(len(orphans)):
                changed = False
                for orphan in list(orphans):
                    referrer = referrer_of.get(orphan)
                    if referrer is not None and (
                            referrer not in orphans or self.container_of.get(referrer) is not None):
                        self.container_of[orphan] = self.container_of.get(referrer)
                        orphans.discard(orphan)
                        changed = True
                if not changed:
                    break
            if orphans:
                self.problems.append(
                    f"{len(orphans)} node(s) not listed in any container and never "
                    f"referenced; placed in the root tree")

    @staticmethod
    def _entry_handle(entry: typing.Any) -> typing.Optional[str]:
        """Return a serialized HandleId without treating zero as false."""
        if not isinstance(entry, dict):
            return None
        if "HandleId" in entry:
            return str(entry["HandleId"])
        if "HandleRefId" in entry:
            return str(entry["HandleRefId"])
        return None

    @classmethod
    def _has_children(cls, data: dict) -> bool:
        """Return whether a node owns nested container data."""
        for field in CONTAINER_FIELDS:
            value = data.get(field)
            if isinstance(value, list) and value:
                return True
            if isinstance(value, dict) and ("HandleId" in value or "HandleRefId" in value):
                return True
        return False

    def _build_subgraph_trees(self) -> None:
        for hid in self.containers:
            data = self.definitions.get(hid, {})
            is_outer_root = (
                self.container_of.get(hid) is None
                and data.get("$type") == f"{ANIM_NODE_PREFIX}Root"
            )
            if is_outer_root:
                self.tree_of_container[hid] = self.root_tree
                continue


            sub_tree = bpy.data.node_groups.new(
                name=self._subtree_name(hid),
                type='REDengine_AnimGraphTree',
            )
            sub_tree["red_internal_subgraph"] = True
            sub_tree["red_parent_graph"] = self.root_tree.name
            sub_tree.use_fake_user = False
            self.tree_of_container[hid] = sub_tree

    def _subtree_name(self, handle_id: str) -> str:
        """Return the internal NodeTree name for a container subgraph."""
        data = self.definitions[handle_id]
        short = data.get("$type", "Container").replace(ANIM_NODE_PREFIX, "")
        safe_root = ''.join(ch if ch.isalnum() or ch in "_-" else "_" for ch in self.root_tree.name)
        for field in ("name", "debugName"):
            value = data.get(field)
            if isinstance(value, dict):
                text = value.get("$value", "")
                if text and text != "None":
                    return f".{safe_root}_{short}_{text}_{handle_id}"
        return f".{safe_root}_{short}_{handle_id}"

    def _resolve_tree(self, handle_id: str) -> bpy.types.NodeTree:
        container = self.container_of.get(handle_id)
        if container is None:
            return self.root_tree
        return self.tree_of_container[container]

    def _instantiate_nodes(self) -> None:
        for hid, data in self.definitions.items():
            node_type = data.get("$type", "Unknown")
            is_outer_root = (
                hid in self.containers
                and self.container_of.get(hid) is None
                and node_type == f"{ANIM_NODE_PREFIX}Root"
            )


            if is_outer_root:
                continue
            target_tree = self._resolve_tree(hid)
            is_nested_container = hid in self.containers

            if is_nested_container:
                bl_node = target_tree.nodes.new('REDengine_AnimGraphContainer')
                bl_node.node_tree = self.tree_of_container[hid]
                if bl_node.node_tree is None:


                    self.problems.append(
                        f"container {node_type}({hid}) rejected its sub-tree; grouping degraded")
                bl_node.red_type = node_type
                bl_node.red_handle_id = hid
                self._annotate_real_node(bl_node, node_type, hid)
                self._attach_properties(bl_node, data)
                self._annotate_container_export_metadata(bl_node, data)
                node_presenters.post_import_projection(self, bl_node, hid, data)
            else:
                bl_node = target_tree.nodes.new('REDengine_AnimGraphNode_Generic')
                bl_node.red_type = node_type
                bl_node.red_handle_id = hid
                self._annotate_real_node(bl_node, node_type, hid)
                self._attach_properties(bl_node, data)
                self._annotate_container_export_metadata(bl_node, data)
                node_presenters.post_import_projection(self, bl_node, hid, data)

            bl_node.name = f"{node_type}_{hid}"
            bl_node.label = self._node_label(node_type, data)
            short = node_type.replace(ANIM_NODE_PREFIX, "")
            bl_node.use_custom_color = True
            bl_node.color = NODE_CATEGORY_COLORS[categories.node_category(short)]
            self.bl_nodes[hid] = bl_node


    def _annotate_real_node(self, node: bpy.types.Node, node_type: str, handle_id: str) -> None:
        """Attach source metadata and presenter state to an imported runtime node."""


        try:
            try:
                source_data = self.handle_data.get(str(handle_id))
                if isinstance(source_data, dict):
                    node['red_source_data_keys_json'] = json.dumps(list(source_data.keys()), ensure_ascii=False, separators=(',', ':'))
            except Exception:
                pass
            node.red_exportable = True
            node.red_pseudo = False
            node.red_metadata_known = bool(rtti_schema.has_class(node_type))
            node.red_parent_class = rtti_schema.parent_of(node_type)
            out_kind = self._node_output_kind(handle_id)
            node.red_output_kind = out_kind or ""
            node.red_presenter = node_presenters.presenter_id_for(node_type)
            node.red_roundtrip_ready = bool(handle_id)
            node.red_roundtrip_notes = "" if handle_id else "missing HandleId"
            node.red_layout_auto = True
        except Exception:

            pass

    def _annotate_container_export_metadata(self, node: bpy.types.Node, data: dict) -> None:
        """Persist compact container metadata required for export."""
        try:
            red_type = str(data.get('$type', '') or '') if isinstance(data, dict) else ''
            if red_type in {f"{ANIM_NODE_PREFIX}StateMachine", f"{ANIM_NODE_PREFIX}LocomotionMachine"}:
                for key in ('transitions', 'conditionalEntries', 'globalTransitions'):
                    value = data.get(key, []) if isinstance(data, dict) else []
                    if value is None:
                        value = []
                    node[f'red_sm_{key}_json'] = json.dumps(value, ensure_ascii=False)
                node['red_sm_anyStateInterpolator_json'] = json.dumps(
                    data.get('anyStateInterpolator') if isinstance(data, dict) else None,
                    ensure_ascii=False,
                )
            if red_type in {f"{ANIM_NODE_PREFIX}State", f"{ANIM_NODE_PREFIX}StateFrozen"}:
                value = data.get('outTransitionIndices', []) if isinstance(data, dict) else []
                if value is None:
                    value = []
                node['red_state_outTransitionIndices_json'] = json.dumps(value, ensure_ascii=False)
        except Exception:
            pass

    def _node_label(self, node_type: str, data: dict) -> str:
        short = node_type.replace(ANIM_NODE_PREFIX, "")
        for field in ("name", "debugName"):
            value = data.get(field)
            if isinstance(value, dict):
                text = value.get("$value", "")
                if text and text != "None":
                    return f"{short}: {text}"
        return short

    @staticmethod
    def _math_expression_socket_caption(obj: dict, key_prefix: str) -> typing.Optional[str]:
        if not math_expression.is_math_expression_socket_struct(obj):
            return None
        for array_name in math_expression.SOCKET_ARRAYS:
            needle = f'{array_name}['
            pos = key_prefix.rfind(needle)
            if pos < 0:
                continue
            start = pos + len(needle)
            end = key_prefix.find(']', start)
            if end < 0:
                continue
            try:
                index = int(key_prefix[start:end])
            except Exception:
                index = 0
            return math_expression.socket_caption(array_name, index, obj)
        return None

    def _attach_properties(self, bl_node: bpy.types.Node, data: dict) -> None:
        """Attach typed editable REDengine fields to a Blender node."""
        clear_node_properties(bl_node)
        type_map = rtti_schema.property_type_map(data.get('$type', ''))
        node_presenters.before_attach_properties(self, bl_node, data)
        for key in self._ordered_fields(data):
            value = data.get(key)
            if node_presenters.should_skip_property(str(data.get('$type', '')), key, value):
                self._preserve_export_field_if_needed(bl_node, key, value)
                continue
            if self._skip_node_property(key, value):
                self._preserve_export_field_if_needed(bl_node, key, value)
                continue
            add_node_property(bl_node, key, value, json_path=key,
                              red_type_hint=type_map.get(key))


    def _preserve_export_field_if_needed(self, bl_node: bpy.types.Node, key: str, value: typing.Any) -> None:
        """Preserve owned-payload fields that are edited through specialized UI."""
        if not self._should_preserve_export_field(key, value):
            return
        try:
            raw = bl_node.get('red_preserved_export_fields_json', '')
        except Exception:
            raw = ''
        try:
            fields = json.loads(raw) if raw else {}
        except Exception:
            fields = {}
        if not isinstance(fields, dict):
            fields = {}
        fields[str(key)] = value
        try:
            bl_node['red_preserved_export_fields_json'] = json.dumps(fields, ensure_ascii=False, separators=(',', ':'))
        except Exception:
            pass

    def _should_preserve_export_field(self, key: str, value: typing.Any) -> bool:
        if not key or key in HIDDEN_FIELDS or str(key).startswith('$'):
            return False

        if str(key) == 'expressionData':
            return False

        if isinstance(value, dict) and value.get('$type') in LINK_TYPES:
            return False


        return self._contains_owned_payload_handle(value)

    def _contains_owned_payload_handle(self, value: typing.Any) -> bool:
        if isinstance(value, dict):
            if 'HandleId' in value and isinstance(value.get('Data'), dict):
                payload_type = str(value.get('Data', {}).get('$type', '') or '')
                return bool(payload_type and not payload_type.startswith(ANIM_NODE_PREFIX))
            if 'HandleRefId' in value:
                return False
            return any(self._contains_owned_payload_handle(child) for child in value.values())
        if isinstance(value, list):
            return any(self._contains_owned_payload_handle(child) for child in value)
        return False

    def _ordered_fields(self, obj: dict) -> typing.List[str]:
        """Return object keys in metadata declaration order."""
        node_type = obj.get('$type') if isinstance(obj, dict) else ''
        if not node_type:
            return list(obj.keys()) if isinstance(obj, dict) else []
        return rtti_schema.ordered_field_names(node_type, obj.keys())

    def _skip_node_property(self, key: str, value: typing.Any) -> bool:
        if key in HIDDEN_FIELDS:
            return True
        if any(key.startswith(p) for p in HIDDEN_FIELD_PREFIXES):
            return True
        if isinstance(value, dict) and value.get("$type") in LINK_TYPES:
            return True
        if isinstance(value, list) and self._array_contains_link(value):
            return True


        if isinstance(value, dict) and ("HandleId" in value or "HandleRefId" in value):
            payload = self._payload_of(value)
            if isinstance(payload, dict) and payload.get("$type", "").startswith(ANIM_NODE_PREFIX):
                return True
        return False

    def _array_contains_link(self, value: list) -> bool:
        for element in value:
            if isinstance(element, dict):
                if element.get("$type") in LINK_TYPES:
                    return True
                target = self._descend_target(element, set())
                if isinstance(target, dict) and self._object_contains_link(target):
                    return True
        return False

    def _object_contains_link(self, obj: typing.Any) -> bool:
        if isinstance(obj, dict):
            if obj.get("$type") in LINK_TYPES:
                return True
            return any(self._object_contains_link(v) for k, v in obj.items() if k != "$type")
        if isinstance(obj, list):
            return any(self._object_contains_link(v) for v in obj)
        return False

    @staticmethod
    def _flatten_value(value: typing.Any) -> typing.Optional[str]:
        if isinstance(value, bool):
            return str(value)
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return value
        if value is None:
            return None
        if isinstance(value, dict):
            if "HandleId" in value and isinstance(value.get("Data"), dict) and "$type" not in value:
                return AnimGraphParser._flatten_value(value["Data"])
            t = value.get("$type")
            if t == "CName":
                v = str(value.get("$value", ""))
                return v if v and v != "None" else None
            if t == "animTransformIndex":
                inner = value.get("name") or {}
                v = str(inner.get("$value", ""))
                return v if v and v != "None" else None
            if t == "animNamedTrackIndex":
                inner = value.get("name") or {}
                v = str(inner.get("$value", ""))
                return v if v and v != "None" else None
            if t == "animVisualTagCondition":
                inner = value.get("visualTag") or {}
                v = str(inner.get("$value", ""))
                return f"visualTag={v}" if v and v != "None" else None
            if t == "animFloatClamp":
                lo = value.get("min", "?")
                hi = value.get("max", "?")
                return f"[{lo}, {hi}]"
            if t == "Vector3":
                return f"({value.get('X', 0)}, {value.get('Y', 0)}, {value.get('Z', 0)})"
            if t == "Vector4":
                return f"({value.get('X', 0)}, {value.get('Y', 0)}, {value.get('Z', 0)}, {value.get('W', 0)})"
            if t == "Quaternion":
                return f"({value.get('i', 0)}, {value.get('j', 0)}, {value.get('k', 0)}, {value.get('r', 0)})"
        return None

    def _link_target_handle(self, link_wrapper: dict) -> typing.Optional[str]:
        inner = link_wrapper.get("node")
        if not isinstance(inner, dict):
            return None
        if "HandleId" in inner:
            return str(inner["HandleId"])
        if "HandleRefId" in inner:
            return str(inner["HandleRefId"])
        return None

    @staticmethod
    def _link_ref_style(link_wrapper: typing.Optional[dict]) -> str:
        if not isinstance(link_wrapper, dict):
            return ''
        inner = link_wrapper.get("node")
        if not isinstance(inner, dict):
            return ''
        if "HandleRefId" in inner:
            return 'HandleRefId'
        if "HandleId" in inner:
            return 'HandleIdInline'
        return ''

    @staticmethod
    def _socket_caption(prop_name: str) -> str:
        if not prop_name:
            return prop_name
        out = [prop_name[0].upper()]
        for ch in prop_name[1:]:
            if ch == '_':
                out.append(' ')
                continue
            if ch.isupper():
                out.append(' ')
            out.append(ch)
        friendly = ''.join(out)
        for suffix in (" Link", " Node"):
            if friendly.endswith(suffix):
                return friendly[: -len(suffix)]
        return friendly

    def _enumerate_all_links(self) -> None:
        for hid in self.definitions:
            self.node_links[hid] = self._enumerate_links(hid)

    def _enumerate_links(self, handle_id: str) -> typing.List[typing.Tuple[str, str, dict]]:
        """Enumerate nested REDengine link fields in editor traversal order."""
        entries: typing.List[typing.Tuple[str, str, dict]] = []
        self._gather_links(self.definitions[handle_id], "", "", entries, set())
        return entries

    def _gather_links(
        self, obj: dict, key_prefix: str, name_prefix: str,
        entries: typing.List[typing.Tuple[str, str, dict]], visited: typing.Set[str],
    ) -> None:
        for field in self._ordered_fields(obj):
            value = obj.get(field)
            if field == "$type":
                continue
            if isinstance(value, dict):
                if field == 'expressionData' and math_expression.is_math_expression_data(value):
                    expr_string = obj.get('expressionString', '') if isinstance(obj, dict) else ''
                    for rel_path, caption, wrapper, _summary in math_expression.iter_expression_socket_links(value, expr_string):
                        entries.append((f"{key_prefix}{field}.{rel_path}", caption, wrapper))
                    continue
                if value.get("$type") in LINK_TYPES:
                    caption = self._math_expression_socket_caption(obj, key_prefix)
                    if not caption:
                        caption = self._socket_caption(name_prefix + field)
                    entries.append((key_prefix + field, caption, value))
                    continue
                target = self._descend_target(value, visited)
                if target is not None:
                    self._gather_links(target, f"{key_prefix}{field}.", name_prefix, entries, visited)
            elif isinstance(value, list):
                for index, element in enumerate(value):
                    if not isinstance(element, dict):
                        continue
                    if element.get("$type") in LINK_TYPES:
                        entries.append((f"{key_prefix}{field}[{index}]", str(index), element))
                        continue
                    target = self._descend_target(element, visited)
                    if target is not None:
                        self._gather_links(target, f"{key_prefix}{field}[{index}].",
                                           f"{name_prefix}[{field} {index}] ", entries, visited)

    def _descend_target(self, value: dict, visited: typing.Set[str]) -> typing.Optional[dict]:
        """Resolve the payload reached through a serialized field."""
        if "HandleId" in value and isinstance(value.get("Data"), dict):
            hid, data = str(value["HandleId"]), value["Data"]
        elif "HandleRefId" in value:
            hid = str(value["HandleRefId"])
            data = self.handle_data.get(hid)
            if data is None:
                return None
        else:
            return value
        if data.get("$type", "").startswith(ANIM_NODE_PREFIX) or hid in visited:
            return None
        visited.add(hid)
        return data

    def _validate_referenced_output_kinds(self) -> None:
        """Validate link kind against the referenced node output kind."""
        for owner, entries in self.node_links.items():
            for key, _caption, wrapper in entries:
                tgt = self._link_target_handle(wrapper)
                if tgt is None or tgt not in self.definitions:
                    continue
                expected = self._node_output_kind(tgt)
                actual = wrapper.get("$type")
                if expected is not None and actual != expected:
                    self.problems.append(
                        f"link type mismatch: {owner}.{key} expects {actual} but "
                        f"source {tgt} outputs {expected}")

    def _node_output_kind(self, handle_id: str) -> typing.Optional[str]:
        data = self.definitions.get(handle_id, {})
        node_type = data.get("$type", "")
        if node_type == OUTPUT_NODE_TYPE:
            return None
        short = node_type.replace(ANIM_NODE_PREFIX, "")
        return rtti_schema.output_kind(short)

    @staticmethod
    def _grouped(node: bpy.types.Node) -> bool:
        return False

    def _build_node_sockets(self) -> None:
        """Materialize node sockets from serialized link fields and presenter metadata."""
        for hid, node in self.bl_nodes.items():
            data = self.definitions[hid]
            node_type = data.get("$type", "")
            is_container = node.bl_idname == 'REDengine_AnimGraphContainer'

            if is_container:
                socket = self._ensure_socket(
                    node, 'OUTPUT', CONTAINER_OUTPUT_NAME, 'REDengine_AnimGraphSocket_Pose')
                self.output_socket[hid] = bind_output_socket(
                    socket, owner_handle=hid, link_type='animPoseLink',
                    edge_semantics='dataflow')
            elif node_type != OUTPUT_NODE_TYPE:
                kind = self._node_output_kind(hid)
                socket_bl, _ = LINK_SOCKET[kind]
                caption = "Out Pose" if kind == "animPoseLink" else "Out Value"
                socket = node.outputs.new(socket_bl, caption)
                self.output_socket[hid] = bind_output_socket(
                    socket, owner_handle=hid, link_type=kind,
                    edge_semantics='dataflow')

            used: typing.Set[str] = set()
            for key, caption, wrapper in self.node_links.get(hid, ()):
                self._add_input_socket(node, hid, key, caption, wrapper["$type"], used, wrapper)

    def _add_input_socket(
        self, node: bpy.types.Node, handle_id: str, key: str, caption: str,
        link_type: str, used: typing.Set[str], wrapper: typing.Optional[dict] = None,
    ) -> None:
        socket_bl, _ = LINK_SOCKET[link_type]
        if caption in used:
            caption = key
        used.add(caption)
        socket = self._ensure_socket(node, 'INPUT', caption, socket_bl)
        bind_input_socket(
            socket,
            owner_handle=handle_id,
            json_path=key,
            link_type=link_type,
            source_handle=(self._link_target_handle(wrapper) if isinstance(wrapper, dict) else '') or '',
            ref_style=(self._link_ref_style(wrapper) if isinstance(wrapper, dict) else ''),
            edge_semantics='dataflow',
        )
        self.input_socket[(handle_id, key)] = socket

    @staticmethod
    def _ensure_socket(node: bpy.types.Node, in_out: str, name: str, socket_type: str) -> bpy.types.NodeSocket:
        """Return an existing socket by name or create it on the node."""
        collection = node.outputs if in_out == 'OUTPUT' else node.inputs
        existing = collection.get(name)
        if existing is not None:
            return existing
        return collection.new(socket_type, name)

    def _container_interface_new(self, hid: str, name: str, in_out: str, socket_type: str) -> str:
        taken = self._iface_names.setdefault((hid, in_out), set())
        actual = name
        suffix = 2
        while actual in taken:
            actual = f"{name} ({suffix})"
            suffix += 1
        self.tree_of_container[hid].interface.new_socket(
            name=actual, in_out=in_out, socket_type=socket_type)
        taken.add(actual)
        return actual

    def _build_group_io(self) -> None:
        return

    def _wire_group_outputs(self) -> None:
        return

    def _container_terminal(self, handle_id: str) -> typing.Optional[typing.Tuple[bpy.types.Node, str]]:
        """Resolve the pose output exposed by a container node."""
        data = self.definitions[handle_id]
        if isinstance(data.get("states"), list) and data.get("states"):
            node = self.state_machine_output_node.get(handle_id)
            return (node, CONTAINER_OUTPUT_NAME) if node is not None else None
        if isinstance(data.get("nodes"), list):
            return self._output_child_source(data)
        return None

    def _output_child_source(self, data: dict) -> typing.Optional[typing.Tuple[bpy.types.Node, str]]:
        out_handle = self._first_child_output(data)
        if out_handle is None:
            return None
        out_data = self.definitions.get(out_handle)
        if not isinstance(out_data, dict):
            return None
        link = out_data.get("node")
        if not (isinstance(link, dict) and link.get("$type") in LINK_TYPES):
            return None
        src_handle = self._link_target_handle(link)
        if src_handle is None or src_handle not in self.bl_nodes:
            return None
        src_node = self.bl_nodes[src_handle]
        if self._grouped(src_node):
            return src_node, CONTAINER_OUTPUT_NAME
        socket = self.output_socket.get(src_handle)
        return (src_node, socket.name) if socket is not None else None

    def _first_child_output(self, data: dict) -> typing.Optional[str]:
        nodes = data.get("nodes") or []
        if not nodes:
            return None
        first = self._entry_handle(nodes[0])
        if first is None:
            return None
        payload = self.definitions.get(first) or self.handle_data.get(first)
        if isinstance(payload, dict) and payload.get("$type") == OUTPUT_NODE_TYPE:
            return first
        return None

    def _default_state_terminal(self, data: dict) -> typing.Optional[typing.Tuple[bpy.types.Node, str]]:
        states = data.get("states") or []
        index = data.get("defaultStateIndex", 0)
        if not isinstance(index, int) or not (0 <= index < len(states)):
            return None
        handle = self._entry_handle(states[index])
        node = self.bl_nodes.get(handle) if handle is not None else None
        if node is None:
            return None
        return node, CONTAINER_OUTPUT_NAME

    def _resolve_links(self) -> None:
        for hid, entries in self.node_links.items():
            target_node = self.bl_nodes.get(hid)
            if target_node is None:
                continue
            target_tree = target_node.id_data
            for key, caption, wrapper in entries:
                self._connect_link(hid, key, caption, wrapper, target_tree)

    def _connect_link(self, target_hid: str, key: str, caption: str, wrapper: dict,
                      target_tree: bpy.types.NodeTree) -> None:
        source_hid = self._link_target_handle(wrapper)
        if source_hid is None or source_hid not in self.bl_nodes:
            return
        source_node = self.bl_nodes[source_hid]
        if source_node.id_data is not target_tree:


            return
        target_node = self.bl_nodes[target_hid]
        out_socket = self._output_socket_of(source_node, source_hid)
        in_socket = self.input_socket.get((target_hid, key))
        if out_socket is None or in_socket is None:


            out_name = (CONTAINER_OUTPUT_NAME if self._grouped(source_node)
                        else (out_socket.name if out_socket is not None else None))
            in_name = in_socket.name if in_socket is not None else caption
            if out_name is not None and in_name is not None:
                self.deferred_links.append((source_node, out_name, target_node, in_name))
            return
        target_tree.links.new(out_socket, in_socket)
        self.drawn_link_edges += 1

    def _output_socket_of(self, node: bpy.types.Node, handle_id: str) -> typing.Optional[bpy.types.NodeSocket]:
        return self.output_socket.get(handle_id) or node.outputs.get(CONTAINER_OUTPUT_NAME)

    def _output_socket_name_of(self, node: bpy.types.Node, handle_id: str) -> typing.Optional[str]:
        sock = self._output_socket_of(node, handle_id)
        return sock.name if sock is not None else None

    def _new_pseudo_node(self, tree: bpy.types.NodeTree, short: str, label: str,
                         handle_id: str) -> bpy.types.Node:
        """Create an editor-derived helper node that is excluded from export."""
        node = tree.nodes.new('REDengine_AnimGraphNode_Generic')
        node.red_type = f"editor{short}"
        node.red_handle_id = handle_id
        try:
            node.red_exportable = False
            node.red_pseudo = True
            node.red_metadata_known = False
            node.red_parent_class = ""
            node.red_output_kind = ""
            node.red_roundtrip_ready = True
            node.red_roundtrip_notes = "editor-only node"
            node.red_layout_auto = True
        except Exception:
            pass
        node.name = handle_id
        node.label = label
        node.use_custom_color = True
        node.color = NODE_CATEGORY_COLORS[categories.node_category(short)]
        return node

    def _plan_root_output(self, root_chunk: dict) -> None:
        """Represent Root.outputNode in the editor when it returns a pose."""
        root = self._payload_of(root_chunk.get("rootNode"))
        if not isinstance(root, dict):

            for hid, data in self.definitions.items():
                if self.container_of.get(hid) is None and data.get("$type") == f"{ANIM_NODE_PREFIX}Root":
                    root = data
                    break
        if not isinstance(root, dict):
            return
        wrapper = root.get("outputNode")
        if not (isinstance(wrapper, dict) and wrapper.get("$type") in LINK_TYPES):
            return
        if self._link_target_handle(wrapper) is None:
            return
        node = self._new_pseudo_node(
            self.root_tree, "RootOutput", "Root Output", "editorRootOutput")
        sock = node.inputs.new('REDengine_AnimGraphSocket_Pose', "Output")
        bind_red_socket(
            sock, role='input', owner_handle=getattr(node, 'red_handle_id', ''),
            field_name='outputNode', json_path='outputNode',
            link_type=wrapper.get('$type', 'animPoseLink'),
            source_handle=(self._link_target_handle(wrapper) or ''),
            ref_style=self._link_ref_style(wrapper), exportable=False,
            edge_semantics='root_output', pseudo=True)
        self.root_output_node = node
        self.root_output_link = wrapper

    def _link_root_output(self) -> None:
        if self.root_output_node is None or self.root_output_link is None:
            return
        self._connect_wrapper_to_node(
            self.root_output_link, self.root_output_node, "Output", self.root_tree)

    def _ancestor_containers(self, handle_id: str) -> typing.List[str]:
        chain: typing.List[str] = []
        current = self.container_of.get(handle_id)
        while current is not None:
            data = self.definitions.get(current, {})
            if not (self.container_of.get(current) is None and data.get("$type") == f"{ANIM_NODE_PREFIX}Root"):
                chain.append(current)
            current = self.container_of.get(current)
        return chain

    def _container_chain_from_tree_to_target(
        self, source_tree: bpy.types.NodeTree, target_hid: str,
    ) -> typing.Optional[typing.List[str]]:
        outer_to_inner = list(reversed(self._ancestor_containers(target_hid)))
        for i, container_hid in enumerate(outer_to_inner):
            node = self.bl_nodes.get(container_hid)
            if node is not None and node.id_data is source_tree:
                return outer_to_inner[i:]
        return [] if self.bl_nodes.get(target_hid, None) is not None and self.bl_nodes[target_hid].id_data is source_tree else None

    def _group_input_for(self, container_hid: str) -> typing.Optional[bpy.types.Node]:
        tree = self.tree_of_container.get(container_hid)
        if tree is None:
            return None
        node = self.group_input_node.get(container_hid)
        if node is None:
            node = self._new_pseudo_node(
                tree, "BoundaryInput", "Boundary Inputs",
                f"editorBoundaryInput_{container_hid}")
            self.group_input_node[container_hid] = node
        return node

    def _safe_link_label(self, source_hid: str, target_hid: str, caption: str) -> str:
        src = self.definitions.get(source_hid, {}).get("$type", source_hid).replace(ANIM_NODE_PREFIX, "")
        tgt = self.definitions.get(target_hid, {}).get("$type", target_hid).replace(ANIM_NODE_PREFIX, "")
        base = f"{src} → {tgt}.{caption}"
        return base[:80]

    def _plan_boundary_links(self) -> None:
        """Declare editor boundary links for references crossing into subgraphs."""
        for target_hid, entries in self.node_links.items():
            target_node = self.bl_nodes.get(target_hid)
            if target_node is None:
                continue
            for key, caption, wrapper in entries:
                source_hid = self._link_target_handle(wrapper)
                if source_hid is None or source_hid not in self.bl_nodes:
                    continue
                source_node = self.bl_nodes[source_hid]
                if source_node.id_data is target_node.id_data:
                    continue
                if not self._plan_one_boundary_link(source_hid, target_hid, key, caption, wrapper):
                    self.unroutable_cross_tree_links += 1
                    self.skipped_cross_tree_links = self.unroutable_cross_tree_links
                    self.problems.append(
                        f"unroutable cross-tree link: {source_hid} -> {target_hid}.{key}")

    def _plan_one_boundary_link(self, source_hid: str, target_hid: str, key: str,
                                caption: str, wrapper: dict) -> bool:
        source_node = self.bl_nodes[source_hid]
        target_node = self.bl_nodes[target_hid]
        chain = self._container_chain_from_tree_to_target(source_node.id_data, target_hid)
        if not chain:
            return False
        socket_type, _kind_label = LINK_SOCKET[wrapper["$type"]]
        prev_node = source_node
        prev_out_name = self._output_socket_name_of(source_node, source_hid)
        if prev_out_name is None:
            return False
        base = self._safe_link_label(source_hid, target_hid, caption)

        for depth, container_hid in enumerate(chain):
            container_node = self.bl_nodes.get(container_hid)
            boundary_node = self._group_input_for(container_hid)
            if container_node is None or boundary_node is None:
                return False
            sock_name = self._unique_socket_name(
                container_node, 'INPUT', base if depth == 0 else f"{base} ({depth + 1})")
            container_sock = self._ensure_socket(container_node, 'INPUT', sock_name, socket_type)
            bind_red_socket(
                container_sock, role='input', owner_handle=container_hid,
                field_name=key, json_path=key, link_type=wrapper.get('$type', ''),
                source_handle=source_hid, target_handle=target_hid,
                ref_style=self._link_ref_style(wrapper), exportable=False,
                edge_semantics='container_boundary', pseudo=True)
            boundary_sock = self._ensure_socket(boundary_node, 'OUTPUT', sock_name, socket_type)
            bind_red_socket(
                boundary_sock, role='output', owner_handle=getattr(boundary_node, 'red_handle_id', ''),
                field_name=key, json_path=key, link_type=wrapper.get('$type', ''),
                source_handle=source_hid, target_handle=target_hid,
                ref_style=self._link_ref_style(wrapper), exportable=False,
                edge_semantics='container_boundary', pseudo=True)


            self.boundary_links.append((prev_node, prev_out_name, container_node, sock_name))


            prev_node = boundary_node
            prev_out_name = sock_name

        final_in = self.input_socket.get((target_hid, key))
        final_name = final_in.name if final_in is not None else caption
        self.boundary_links.append((prev_node, prev_out_name, target_node, final_name))
        self.routed_cross_tree_links += 1
        return True

    def _link_boundary_links(self) -> None:
        if not self.boundary_links:
            return
        remaining = self._link_named(self.boundary_links)
        self.deferred_links.extend(remaining)

    def _connect_wrapper_to_node(self, wrapper: dict, target_node: bpy.types.Node,
                                 in_name: str, target_tree: bpy.types.NodeTree) -> None:
        source_hid = self._link_target_handle(wrapper)
        if source_hid is None or source_hid not in self.bl_nodes:
            return
        source_node = self.bl_nodes[source_hid]
        out_name = self._output_socket_name_of(source_node, source_hid)
        if out_name is None:
            return
        if source_node.id_data is target_tree:
            remaining = self._link_named([(source_node, out_name, target_node, in_name)])
            self.deferred_links.extend(remaining)
        else:


            self.problems.append(
                f"Root output source {source_hid} is not in the root tree; not linked")

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

    def _layout_all(self) -> None:
        """Lay out all imported node trees with conservative spacing."""
        edges_by_tree: typing.Dict[int, typing.Set[typing.Tuple[bpy.types.Node, bpy.types.Node]]] = {}

        def add(src: typing.Optional[bpy.types.Node], dst: typing.Optional[bpy.types.Node]) -> None:
            if src is None or dst is None or src is dst or src.id_data is not dst.id_data:
                return
            edges_by_tree.setdefault(id(src.id_data), set()).add((src, dst))

        for hid, entries in self.node_links.items():
            dst = self.bl_nodes.get(hid)
            for _key, _caption, wrapper in entries:
                source_hid = self._link_target_handle(wrapper)
                add(self.bl_nodes.get(source_hid) if source_hid is not None else None, dst)


        for src, dst in self.transition_layout_edges:
            add(src, dst)
        for src, _out_name, dst, _in_name in self.boundary_links:
            add(src, dst)
        if self.root_output_node is not None and self.root_output_link is not None:
            source_hid = self._link_target_handle(self.root_output_link)
            add(self.bl_nodes.get(source_hid) if source_hid is not None else None, self.root_output_node)
        for src, group_out in self.group_wires:
            add(src, group_out)

        trees = {id(self.root_tree): self.root_tree}
        for tree in self.tree_of_container.values():
            trees[id(tree)] = tree

        self.layout_overlap_count = 0
        self.layout_trees_checked = 0
        self.curve_widgets_initialized = 0
        self.curve_widgets_failed = 0
        self.source_alignment_report = {}
        for tree_id, tree in trees.items():
            edges = list(edges_by_tree.get(tree_id, ()))
            self._layout_tree(tree, edges)
            overlaps = self._count_estimated_overlaps(tree)
            self.layout_overlap_count += overlaps
            self.layout_trees_checked += 1
        if self.layout_overlap_count:
            self.problems.append(
                f"estimated layout still has {self.layout_overlap_count} overlapping node pair(s)")

    @staticmethod
    def _node_property_count(node: bpy.types.Node) -> int:
        props = getattr(node, 'red_properties', None)
        if props is None:
            return 0
        try:
            rows = 0
            for prop in props:
                if getattr(prop, 'value_kind', '') == 'CURVE_FLOAT':


                    rows += 3
                else:
                    rows += 1
            return rows
        except Exception:
            return 0

    @classmethod
    def _estimated_size(cls, node: bpy.types.Node) -> typing.Tuple[float, float]:
        """Estimate node rectangle size for import-time layout."""
        sockets = len(list(node.inputs)) + len(list(node.outputs))
        prop_rows = cls._node_property_count(node)
        label = getattr(node, 'label', '') or getattr(node, 'name', '') or ''
        red_type = getattr(node, 'red_type', '') or getattr(node, 'bl_idname', '') or ''
        short = red_type.replace(ANIM_NODE_PREFIX, '').replace('editorPseudo_', '').replace('editor', '')

        min_width = 240.0
        if node.bl_idname == 'REDengine_AnimGraphContainer':
            min_width = 300.0
        if 'StateMachineOutput' in short:
            min_width = 360.0
        elif 'Transition' in short:
            min_width = 340.0
        elif short in {'State', 'StateFrozen', 'StateMachine', 'LocomotionMachine'}:
            min_width = 300.0

        width = max(min_width, 10.0 * len(label) + 96.0)
        height = 76.0
        height += 26.0 * max(1, sockets)
        if prop_rows:


            height += 46.0 + 28.0 * prop_rows
        if 'StateMachineOutput' in short:
            height += 10.0 + 20.0 * len(list(node.inputs))
        if 'Transition' in short:
            height = max(height, 132.0)

        try:
            node.width = max(float(getattr(node, 'width', 0.0) or 0.0), width)
        except Exception:
            pass
        return width, height

    @classmethod
    def _layout_tree(cls, tree: bpy.types.NodeTree,
                     edges: typing.List[typing.Tuple[bpy.types.Node, bpy.types.Node]],
                     x_gap: float = 240.0,
                     y_gap: float = 170.0,
                     component_gap: float = 300.0) -> None:
        """Lay out one node tree using layered, component-aware placement."""
        nodes = list(tree.nodes)
        if not nodes:
            return

        node_set = set(nodes)
        clean_edges = []
        seen_edges = set()
        for a, b in edges:
            if a in node_set and b in node_set and a is not b:
                key = (a.name, b.name)
                if key not in seen_edges:
                    seen_edges.add(key)
                    clean_edges.append((a, b))

        pred: typing.Dict[bpy.types.Node, typing.List[bpy.types.Node]] = {n: [] for n in nodes}
        succ: typing.Dict[bpy.types.Node, typing.List[bpy.types.Node]] = {n: [] for n in nodes}
        for a, b in clean_edges:
            succ[a].append(b)
            pred[b].append(a)

        components = cls._weak_components(nodes, pred, succ)
        clusters = sorted((c for c in components if len(c) > 1), key=len, reverse=True)
        singles = [c[0] for c in components if len(c) == 1]

        y_cursor = 0.0
        for members in clusters:
            y_cursor = cls._layout_component_packed(
                members, pred, succ, x_gap=x_gap, y_gap=y_gap, y_top=y_cursor)
            y_cursor -= component_gap

        if singles:
            cls._layout_singleton_grid_packed(
                singles, x_gap=x_gap, y_gap=y_gap, y_top=y_cursor)

    @staticmethod
    def _weak_components(nodes, pred, succ):
        components = []
        seen = set()
        for node in nodes:
            if node in seen:
                continue
            stack = [node]
            seen.add(node)
            members = []
            while stack:
                cur = stack.pop()
                members.append(cur)
                for nxt in pred[cur] + succ[cur]:
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
            components.append(members)
        return components

    @classmethod
    def _layout_component_packed(cls, members, pred, succ,
                                 x_gap: float, y_gap: float, y_top: float) -> float:
        member_set = set(members)
        scc_list = cls._strong_components(members, succ)
        scc_of = {node: index for index, group in enumerate(scc_list) for node in group}

        dag_pred: typing.Dict[int, typing.Set[int]] = {i: set() for i in range(len(scc_list))}
        dag_succ: typing.Dict[int, typing.Set[int]] = {i: set() for i in range(len(scc_list))}
        for node in members:
            a = scc_of[node]
            for nxt in succ[node]:
                if nxt in member_set:
                    b = scc_of[nxt]
                    if a != b:
                        dag_succ[a].add(b)
                        dag_pred[b].add(a)

        topo = cls._toposort_component_ids(len(scc_list), dag_pred, dag_succ)
        scc_layer = {i: 0 for i in range(len(scc_list))}
        for comp_id in topo:
            base = scc_layer[comp_id]
            for nxt in dag_succ[comp_id]:
                scc_layer[nxt] = max(scc_layer[nxt], base + 1)

        layers: typing.Dict[int, typing.List[bpy.types.Node]] = {}
        for node in members:
            layers.setdefault(scc_layer[scc_of[node]], []).append(node)
        keys = sorted(layers)

        for key in keys:
            layers[key].sort(key=lambda n: (getattr(n, 'label', '') or getattr(n, 'name', ''), getattr(n, 'name', '')))
        cls._barycenter_order_layers(layers, keys, pred, succ)

        size = {node: cls._estimated_size(node) for node in members}
        col_width = {key: max(size[n][0] for n in layers[key]) for key in keys}
        col_height = {
            key: sum(size[n][1] for n in layers[key]) + y_gap * max(0, len(layers[key]) - 1)
            for key in keys
        }
        component_height = max(col_height.values()) if col_height else 0.0

        x = 0.0
        col_x = {}
        for key in keys:
            col_x[key] = x
            x += col_width[key] + x_gap

        for key in keys:
            y = y_top - (component_height - col_height[key]) / 2.0
            for node in layers[key]:
                node.location = Vector((col_x[key], y))
                y -= size[node][1] + y_gap


        cls._pull_pendant_nodes_near_neighbors(members, pred, succ, size, x_gap, y_gap)
        cls._pull_fanout_sources_near_consumers(members, pred, succ, size, x_gap, y_gap)
        cls._pull_fanout_pendant_clusters_near_consumers(members, pred, succ, size, x_gap, y_gap)
        cls._pull_small_pendant_branches_near_neighbors(members, pred, succ, size, x_gap, y_gap)
        cls._resolve_component_overlaps(members, size, y_gap)
        return cls._component_bottom(members, size)

    @staticmethod
    def _layout_is_structural(node: bpy.types.Node) -> bool:
        red_type = (getattr(node, 'red_type', '') or '').lower()
        bl_idname = (getattr(node, 'bl_idname', '') or '').lower()
        text = red_type + ' ' + bl_idname
        return any(token in text for token in (
            'statemachineoutput', 'editortransition', 'transition_',
            'statefrozen', 'animanimnode_state', 'animanimnode_output',
            'animanimnode_root', 'editordangle', 'editorrounded',
        ))

    @staticmethod
    def _median(values: typing.Sequence[float]) -> float:
        if not values:
            return 0.0
        ordered = sorted(float(v) for v in values)
        mid = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[mid]
        return (ordered[mid - 1] + ordered[mid]) * 0.5

    @classmethod
    def _component_bottom(cls, members, size) -> float:
        if not members:
            return 0.0
        return min(float(node.location.y) - size[node][1] for node in members)

    @classmethod
    def _resolve_component_overlaps(cls, members, size, y_gap: float) -> None:
        placed = []
        ordered = sorted(
            members,
            key=lambda n: (float(n.location.x), -float(n.location.y), getattr(n, 'name', ''))
        )
        for node in ordered:
            w, h = size[node]
            x = float(node.location.x)
            y = float(node.location.y)
            step = max(80.0, min(260.0, h * 0.35 + y_gap * 0.55))
            attempts = 0
            box = (node, x, x + w, y - h, y)
            while cls._box_intersects_any_padded(box, placed, pad=44.0) and attempts < 400:
                y -= step
                box = (node, x, x + w, y - h, y)
                attempts += 1
            node.location = Vector((x, y))
            placed.append(box)

    @staticmethod
    def _box_intersects_any_padded(box, boxes, pad: float = 0.0) -> bool:
        _node, ax1, ax2, ay1, ay2 = box
        ax1 -= pad; ax2 += pad; ay1 -= pad; ay2 += pad
        for other, bx1, bx2, by1, by2 in boxes:
            if other is _node:
                continue
            if ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2:
                return True
        return False

    @classmethod
    def _pull_fanout_sources_near_consumers(cls, members, pred, succ, size,
                                            x_gap: float, y_gap: float) -> None:
        member_set = set(members)
        placed = []
        for node in members:
            w, h = size[node]
            x = float(node.location.x)
            y = float(node.location.y)
            placed.append((node, x, x + w, y - h, y))

        candidates = []
        for node in members:
            if cls._layout_is_structural(node):
                continue
            out_nodes = [n for n in succ[node] if n in member_set]
            in_nodes = [n for n in pred[node] if n in member_set]
            if len(out_nodes) < 2:
                continue
            if in_nodes:


                continue
            if len(out_nodes) > 24:
                continue
            nw, nh = size[node]
            consumer_left = min(float(n.location.x) for n in out_nodes)
            current_x = float(node.location.x)
            if consumer_left - (current_x + nw) < max(480.0, x_gap * 1.8):
                continue
            candidates.append((node, out_nodes))

        if not candidates:
            return

        candidates.sort(key=lambda item: (-len(item[1]), getattr(item[0], 'name', '')))
        for node, out_nodes in candidates:
            nw, nh = size[node]
            consumer_left = min(float(n.location.x) for n in out_nodes)
            centers = []
            for dst in out_nodes:
                _dw, dh = size[dst]
                centers.append(float(dst.location.y) - dh * 0.5)
            target_center = cls._median(centers)
            x = consumer_left - nw - max(120.0, x_gap * 0.60)
            y_base = target_center + nh * 0.5

            placed = [b for b in placed if b[0] is not node]
            step = max(90.0, nh * 0.45 + y_gap * 0.35)
            offsets = [0.0]
            for i in range(1, 160):
                offsets.append(i * step)
                offsets.append(-i * step)
            best = None
            for offset in offsets:
                y = y_base + offset
                box = (node, x, x + nw, y - nh, y)
                if not cls._box_intersects_any_padded(box, placed, pad=52.0):
                    best = (x, y, box)
                    break
            if best is None:
                y = y_base
                box = (node, x, x + nw, y - nh, y)
                while cls._box_intersects_any_padded(box, placed, pad=52.0):
                    y -= step
                    box = (node, x, x + nw, y - nh, y)
                best = (x, y, box)
            x, y, box = best
            node.location = Vector((x, y))
            placed.append(box)

    @classmethod
    def _pull_fanout_pendant_clusters_near_consumers(cls, members, pred, succ, size,
                                                      x_gap: float, y_gap: float) -> None:
        member_set = set(members)

        def structural(node):
            return cls._layout_is_structural(node)

        def degree(node):
            return len([n for n in pred[node] + succ[node] if n in member_set])

        def collect_upstream_chain(hub):
            chain = []
            frontier = [p for p in pred[hub] if p in member_set and not structural(p)]
            seen = {hub}
            while frontier and len(chain) < 3:


                nxt = frontier.pop(0)
                if nxt in seen or degree(nxt) > 2:
                    return []
                outs = [s for s in succ[nxt] if s in member_set]
                if hub not in outs and not any(c in outs for c in chain):
                    return []
                seen.add(nxt)
                chain.append(nxt)
                for pp in pred[nxt]:
                    if pp in member_set and pp not in seen and not structural(pp):
                        frontier.append(pp)
            if frontier:
                return []
            return chain

        def topo_order(nodes):
            nodes_set = set(nodes)
            indeg = {n: len([p for p in pred[n] if p in nodes_set]) for n in nodes}
            queue = deque(sorted((n for n in nodes if indeg[n] == 0), key=lambda n: getattr(n, 'name', '')))
            result = []
            while queue:
                cur = queue.popleft()
                result.append(cur)
                for nxt in sorted((n for n in succ[cur] if n in nodes_set), key=lambda n: getattr(n, 'name', '')):
                    indeg[nxt] -= 1
                    if indeg[nxt] == 0:
                        queue.append(nxt)
            return result if len(result) == len(nodes) else sorted(nodes, key=lambda n: (float(n.location.x), getattr(n, 'name', '')))

        def boxes_excluding(exclude):
            exclude = set(exclude)
            boxes = []
            for node in members:
                if node in exclude:
                    continue
                w, h = size[node]
                x = float(node.location.x)
                y = float(node.location.y)
                boxes.append((node, x, x + w, y - h, y))
            return boxes

        candidates = []
        for hub in members:
            if structural(hub):
                continue
            out_nodes = [n for n in succ[hub] if n in member_set]
            if len(out_nodes) < 2 or len(out_nodes) > 32:
                continue
            hw, _hh = size[hub]
            consumer_left = min(float(n.location.x) for n in out_nodes)
            if consumer_left - (float(hub.location.x) + hw) < max(560.0, x_gap * 2.0):
                continue
            chain = collect_upstream_chain(hub)
            cluster = topo_order(chain + [hub])
            candidates.append((hub, out_nodes, cluster))

        moved = set()
        for hub, out_nodes, cluster in sorted(candidates, key=lambda item: (-len(item[1]), getattr(item[0], 'name', ''))):
            if any(n in moved for n in cluster):
                continue
            widths = [size[n][0] for n in cluster]
            heights = [size[n][1] for n in cluster]
            gap = max(95.0, x_gap * 0.48)
            total_w = sum(widths) + max(0, len(cluster) - 1) * gap
            max_h = max(heights) if heights else 120.0
            consumer_left = min(float(n.location.x) for n in out_nodes)
            centers = [float(n.location.y) - size[n][1] * 0.5 for n in out_nodes]
            target_center = cls._median(centers)
            start_x = consumer_left - total_w - max(150.0, x_gap * 0.72)
            base_top = target_center + max_h * 0.5
            placed = boxes_excluding(cluster)
            step = max(110.0, max_h * 0.55 + y_gap * 0.45)
            offsets = [0.0]
            for i in range(1, 120):
                offsets.append(i * step)
                offsets.append(-i * step)
            best = None
            for offset in offsets:
                top = base_top + offset
                boxes = []
                x = start_x
                for node, width, height in zip(cluster, widths, heights):
                    boxes.append((node, x, x + width, top - height, top))
                    x += width + gap
                if not any(cls._box_intersects_any_padded(box, placed, pad=56.0) for box in boxes):
                    best = boxes
                    break
            if best is None:
                top = base_top
                while True:
                    boxes = []
                    x = start_x
                    for node, width, height in zip(cluster, widths, heights):
                        boxes.append((node, x, x + width, top - height, top))
                        x += width + gap
                    if not any(cls._box_intersects_any_padded(box, placed, pad=56.0) for box in boxes):
                        best = boxes
                        break
                    top -= step
            for node, x1, _x2, _y1, y2 in best:
                node.location = Vector((x1, y2))
                moved.add(node)


    @classmethod
    def _pull_pendant_nodes_near_neighbors(cls, members, pred, succ, size,
                                           x_gap: float, y_gap: float) -> None:
        if len(members) < 3:
            return
        member_set = set(members)

        neighbours: typing.Dict[bpy.types.Node, typing.List[bpy.types.Node]] = {}
        for node in members:
            seen = []
            for other in pred[node] + succ[node]:
                if other in member_set and other not in seen:
                    seen.append(other)
            neighbours[node] = seen


        leaves = [
            node for node in members
            if len(neighbours[node]) == 1
            and 'editorTransition' not in (getattr(node, 'red_type', '') or '')
        ]
        if not leaves:
            return

        leaf_set = set(leaves)
        placed = []
        for node in members:
            if node in leaf_set:
                continue
            width, height = size[node]
            x = float(node.location.x)
            y = float(node.location.y)
            placed.append((node, x, x + width, y - height, y))


        def leaf_sort_key(node):
            anchor = neighbours[node][0]
            anchor_is_leaf = anchor in leaf_set
            return (anchor_is_leaf, getattr(anchor, 'name', ''), getattr(node, 'name', ''))

        for leaf in sorted(leaves, key=leaf_sort_key):
            anchor = neighbours[leaf][0]
            if anchor not in size:
                continue
            leaf_w, leaf_h = size[leaf]
            anchor_w, anchor_h = size[anchor]
            ax = float(anchor.location.x)
            ay = float(anchor.location.y)
            anchor_center_y = ay - anchor_h / 2.0
            target_y = anchor_center_y + leaf_h / 2.0


            if anchor in succ[leaf]:
                preferred = 'LEFT'
            elif anchor in pred[leaf]:
                preferred = 'RIGHT'
            else:
                preferred = 'LEFT' if float(leaf.location.x) < ax else 'RIGHT'

            lane_gap = max(90.0, x_gap * 0.62)
            side_x = {
                'LEFT': ax - leaf_w - lane_gap,
                'RIGHT': ax + anchor_w + lane_gap,
            }
            side_order = [preferred, 'RIGHT' if preferred == 'LEFT' else 'LEFT']

            best = None
            step = max(48.0, leaf_h * 0.55 + y_gap * 0.45)
            offsets = [0.0]
            for i in range(1, 80):
                offsets.append(i * step)
                offsets.append(-i * step)

            for side_index, side in enumerate(side_order):
                x = side_x[side]
                for offset in offsets:
                    y = target_y + offset
                    box = (leaf, x, x + leaf_w, y - leaf_h, y)
                    if cls._box_intersects_any(box, placed):
                        continue


                    score = abs(offset) + side_index * (leaf_h + y_gap) * 3.0
                    best = (score, x, y, box)
                    break
                if best is not None:
                    break

            if best is None:


                side = preferred
                x = side_x[side]
                y = target_y
                while cls._box_intersects_any((leaf, x, x + leaf_w, y - leaf_h, y), placed):
                    y -= leaf_h + y_gap
                best = (0.0, x, y, (leaf, x, x + leaf_w, y - leaf_h, y))

            _score, x, y, box = best
            leaf.location = Vector((x, y))
            placed.append(box)

    @classmethod
    def _pull_small_pendant_branches_near_neighbors(cls, members, pred, succ, size,
                                                     x_gap: float, y_gap: float) -> None:
        if len(members) < 5:
            return
        member_set = set(members)
        undirected = {node: set() for node in members}
        for node in members:
            for other in pred[node] + succ[node]:
                if other in member_set and other is not node:
                    undirected[node].add(other)
                    undirected[other].add(node)

        def excluded(node) -> bool:
            red_type = getattr(node, 'red_type', '') or ''
            if red_type.startswith('editorDangle') or red_type.startswith('editorRounded'):
                return True


            lowered = red_type.lower()
            return any(token in lowered for token in (
                'statemachineoutput', 'editortransition', 'statefrozen',
                'animanimnode_state', 'animanimnode_output', 'animanimnode_root',
            ))


        candidates = {
            node for node in members
            if not excluded(node) and len(undirected[node]) <= 2
        }
        if not candidates:
            return

        seen = set()
        branches = []
        for seed in sorted(candidates, key=lambda n: getattr(n, 'name', '')):
            if seed in seen:
                continue
            stack = [seed]
            seen.add(seed)
            comp = []
            while stack:
                cur = stack.pop()
                comp.append(cur)
                for nxt in undirected[cur]:
                    if nxt in candidates and nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
            if not (2 <= len(comp) <= 4):
                continue
            outside = set()
            for node in comp:
                outside.update(n for n in undirected[node] if n not in comp)
            if len(outside) != 1:
                continue
            anchor = next(iter(outside))
            if anchor not in member_set or anchor in comp:
                continue


            branches.append((anchor, comp))

        if not branches:
            return

        moved_nodes = set()
        branches.sort(key=lambda item: (getattr(item[0], 'name', ''), len(item[1]), getattr(item[1][0], 'name', '')))

        def topo_order(comp):
            comp_set = set(comp)
            indeg = {n: len([p for p in pred[n] if p in comp_set]) for n in comp}
            queue = deque(sorted((n for n in comp if indeg[n] == 0), key=lambda n: getattr(n, 'name', '')))
            result = []
            while queue:
                cur = queue.popleft()
                result.append(cur)
                for nxt in sorted((n for n in succ[cur] if n in comp_set), key=lambda n: getattr(n, 'name', '')):
                    indeg[nxt] -= 1
                    if indeg[nxt] == 0:
                        queue.append(nxt)
            if len(result) != len(comp):

                return sorted(comp, key=lambda n: (float(n.location.x), getattr(n, 'name', '')))
            return result

        def boxes_excluding(exclude):
            result = []
            exclude = set(exclude)
            for node in members:
                if node in exclude:
                    continue
                w, h = size[node]
                x = float(node.location.x)
                y = float(node.location.y)
                result.append((node, x, x + w, y - h, y))
            return result

        anchor_slots = defaultdict(int)
        for anchor, comp in branches:
            if any(node in moved_nodes for node in comp):
                continue
            comp_set = set(comp)


            feeds_anchor = any(anchor in succ[node] for node in comp)
            from_anchor = any(anchor in pred[node] for node in comp)
            side = 'LEFT' if feeds_anchor or not from_anchor else 'RIGHT'
            order = topo_order(comp)
            if side == 'LEFT':


                pass
            else:

                pass

            aw, ah = size[anchor]
            ax = float(anchor.location.x)
            ay = float(anchor.location.y)
            anchor_center = ay - ah * 0.5
            widths = [size[n][0] for n in order]
            heights = [size[n][1] for n in order]
            total_width = sum(widths) + max(0, len(order) - 1) * max(70.0, x_gap * 0.45)
            max_height = max(heights) if heights else 0.0
            lane_gap = max(120.0, x_gap * 0.70)
            if side == 'LEFT':
                start_x = ax - lane_gap - total_width
            else:
                start_x = ax + aw + lane_gap

            slot = anchor_slots[anchor]
            anchor_slots[anchor] += 1
            base_top = anchor_center + max_height * 0.5 + (slot % 2) * (max_height + y_gap * 0.65)
            if slot >= 2:
                base_top -= (slot // 2) * (max_height + y_gap * 0.85)

            best = None
            placed = boxes_excluding(comp)
            step = max(70.0, max_height * 0.45 + y_gap * 0.35)
            offsets = [0.0]
            for i in range(1, 80):
                offsets.append(i * step)
                offsets.append(-i * step)
            gap = max(70.0, x_gap * 0.45)
            for offset in offsets:
                boxes = []
                x = start_x
                top = base_top + offset
                for node, width, height in zip(order, widths, heights):
                    boxes.append((node, x, x + width, top - height, top))
                    x += width + gap
                if not any(cls._box_intersects_any(box, placed) for box in boxes):
                    best = (top, boxes)
                    break
            if best is None:

                top = base_top
                placed = boxes_excluding(comp)
                while True:
                    boxes = []
                    x = start_x
                    for node, width, height in zip(order, widths, heights):
                        boxes.append((node, x, x + width, top - height, top))
                        x += width + gap
                    if not any(cls._box_intersects_any(box, placed) for box in boxes):
                        best = (top, boxes)
                        break
                    top -= max_height + y_gap

            _top, boxes = best
            for node, x1, _x2, _y1, y2 in boxes:
                node.location = Vector((x1, y2))
                moved_nodes.add(node)

    @staticmethod
    def _box_intersects_any(box, boxes) -> bool:
        _node, ax1, ax2, ay1, ay2 = box
        for _other, bx1, bx2, by1, by2 in boxes:
            if ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2:
                return True
        return False

    @staticmethod
    def _strong_components(members, succ):
        member_set = set(members)
        index = 0
        stack = []
        on_stack = set()
        indices = {}
        lowlink = {}
        result = []

        def visit(node):
            nonlocal index
            indices[node] = index
            lowlink[node] = index
            index += 1
            stack.append(node)
            on_stack.add(node)
            for nxt in succ[node]:
                if nxt not in member_set:
                    continue
                if nxt not in indices:
                    visit(nxt)
                    lowlink[node] = min(lowlink[node], lowlink[nxt])
                elif nxt in on_stack:
                    lowlink[node] = min(lowlink[node], indices[nxt])
            if lowlink[node] == indices[node]:
                group = []
                while True:
                    nxt = stack.pop()
                    on_stack.remove(nxt)
                    group.append(nxt)
                    if nxt is node:
                        break
                result.append(group)

        for node in members:
            if node not in indices:
                visit(node)
        return result

    @staticmethod
    def _toposort_component_ids(count, dag_pred, dag_succ):
        indeg = {i: len(dag_pred[i]) for i in range(count)}
        queue = deque(i for i in range(count) if indeg[i] == 0)
        result = []
        while queue:
            item = queue.popleft()
            result.append(item)
            for nxt in sorted(dag_succ[item]):
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    queue.append(nxt)
        if len(result) != count:
            result.extend(i for i in range(count) if i not in result)
        return result

    @staticmethod
    def _barycenter_order_layers(layers, keys, pred, succ) -> None:
        for _ in range(6):
            for key in keys[1:]:
                ref = layers.get(key - 1)
                if not ref:
                    continue
                ref_pos = {node: i for i, node in enumerate(ref)}
                layer_order_index = {node: i for i, node in enumerate(layers[key])}

                def bary(node):
                    values = [ref_pos[p] for p in pred[node] if p in ref_pos]
                    return sum(values) / len(values) if values else float(layer_order_index[node])

                layers[key].sort(key=lambda n: (bary(n), layer_order_index[n]))
            for key in reversed(keys[:-1]):
                ref = layers.get(key + 1)
                if not ref:
                    continue
                ref_pos = {node: i for i, node in enumerate(ref)}
                layer_order_index = {node: i for i, node in enumerate(layers[key])}

                def bary(node):
                    values = [ref_pos[s] for s in succ[node] if s in ref_pos]
                    return sum(values) / len(values) if values else float(layer_order_index[node])

                layers[key].sort(key=lambda n: (bary(n), layer_order_index[n]))

    @classmethod
    def _layout_singleton_grid_packed(cls, singles, x_gap: float, y_gap: float,
                                      y_top: float, per_row: int = 4) -> None:
        row_y = y_top
        for start in range(0, len(singles), per_row):
            row = singles[start:start + per_row]
            x = 0.0
            row_height = 0.0
            for node in row:
                width, height = cls._estimated_size(node)
                node.location = Vector((x, row_y))
                x += width + x_gap
                row_height = max(row_height, height)
            row_y -= row_height + y_gap

    @classmethod
    def _count_estimated_overlaps(cls, tree: bpy.types.NodeTree) -> int:
        nodes = list(tree.nodes)
        boxes = []
        for node in nodes:
            width, height = cls._estimated_size(node)
            x = float(node.location.x)
            y = float(node.location.y)
            boxes.append((node, x, x + width, y - height, y))
        count = 0
        for i, (a, ax1, ax2, ay1, ay2) in enumerate(boxes):
            for b, bx1, bx2, by1, by2 in boxes[i + 1:]:
                if ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2:
                    count += 1
        return count

    def _import_variables(self, root_chunk: dict) -> None:
        container = root_chunk.get("variables")
        if not isinstance(container, dict):
            return
        data = container.get("Data")
        if not isinstance(data, dict) or data.get("$type") != "animAnimVariableContainer":
            return

        try:
            self.root_tree['red_variables_handle'] = str(container.get('HandleId', '') or '')
        except Exception:
            pass

        target = self.root_tree.variables
        target.clear()

        try:
            self.root_tree.red_variable_sync_suspended = True
        except Exception:
            pass
        try:
            for array_name, var_type in VAR_ARRAYS:
                entries = data.get(array_name) or []
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    inner = entry.get("Data") or {}
                    slot = target.add()
                    variable_bindings.set_variable_from_json(slot, var_type, inner, entry, array_name)
        finally:
            try:
                self.root_tree.red_variable_sync_suspended = False
            except Exception:
                pass

        try:
            variable_bindings.bind_all_variables(self.root_tree)
        except Exception as exc:
            self.problems.append(f"variable binding failed: {exc}")

    @classmethod
    def _format_variable_value(cls, value: typing.Any) -> str:
        if value is None:
            return ""
        rendered = cls._flatten_value(value)
        return rendered if rendered is not None else ""

    def _import_features(self, root_chunk: dict) -> None:
        entries = root_chunk.get("animFeatures")
        if not isinstance(entries, list):
            return
        target = self.root_tree.features
        target.clear()
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("$type") != "animAnimFeatureEntry":
                continue
            slot = target.add()
            slot.name = (entry.get("name") or {}).get("$value", "") or "<unnamed>"
            slot.class_name = (entry.get("className") or {}).get("$value", "")
            slot.debug_enabled = bool(entry.get("debugEnabled"))
            slot.force_allocate = bool(entry.get("forceAllocate"))
