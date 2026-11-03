<<<<<<< Updated upstream
import json
=======
import logging
>>>>>>> Stashed changes
import typing

import bpy

<<<<<<< Updated upstream
from ...animation.animgraph_constants import ANIM_NODE_PREFIX, LINK_TYPES
from ...blender.animgraph import curve_mapping
from ...blender.animgraph import index as graph_index, presenters as node_presenters
from ...animation.animgraph.schema import rtti
from ...blender.animgraph.validation import reporting, roundtrip
=======
from ...animation.model.animgraph.constants import ANIM_NODE_PREFIX, LINK_TYPES
from ...animation.model.animgraph.schema import rtti
from ...assetio import animgraph_json as json_io
from ...blender.animgraph import (
    curve_mapping,
)
from ...blender.animgraph import (
    index as graph_index,
)
from ...blender.animgraph import (
    presenters as node_presenters,
)
from ...blender.animgraph.tree_ops import has_link, link_sockets
from ...blender.animgraph.validation import reporting, roundtrip
from ...blender.identity import rna_is_live
from ...blender.transactions import track_mutation
from ...core.log import debug_exception, get_logger
>>>>>>> Stashed changes
from .build import ParserBuildMixin
from .document import ParserDocumentMixin
from .layout import ParserLayoutMixin
from .links import ParserLinksMixin
from .transitions import ParserTransitionsMixin

<<<<<<< Updated upstream
=======
_LOG = get_logger(__name__)

_DEFERRED_TIMERS = set()


def _cancel_deferred_link_timer(callback):
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    try:
        if timers is not None and timers.is_registered(callback):
            timers.unregister(callback)
    finally:
        _DEFERRED_TIMERS.discard(callback)


def _live_link_entries(entries):
    """The deferred links whose nodes still exist"""
    live = []
    for entry in entries:
        src_node, _out_name, tgt_node, _in_name = entry
        try:
            if rna_is_live(src_node.id_data) and rna_is_live(tgt_node.id_data):
                live.append(entry)
        except ReferenceError:
            continue
    return live


def cancel_deferred_link_timers():
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None:
        _DEFERRED_TIMERS.clear()
        return
    for callback in tuple(_DEFERRED_TIMERS):
        _cancel_deferred_link_timer(callback)


>>>>>>> Stashed changes
class AnimGraphParser(
    ParserBuildMixin,
    ParserLinksMixin,
    ParserTransitionsMixin,
    ParserLayoutMixin,
    ParserDocumentMixin,
):
    def __init__(self, root_tree: bpy.types.NodeTree):
        self.root_tree = root_tree
<<<<<<< Updated upstream
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
=======
        self.definitions: dict[str, dict] = {}
        self.handle_data: dict[str, dict] = {}
        self.node_links: dict[str, list[tuple[str, str, dict]]] = {}
        self.container_of: dict[str, str | None] = {}
        self.containers: set[str] = set()
        self.tree_of_container: dict[str, bpy.types.NodeTree] = {}
        self.group_output_node: dict[str, bpy.types.Node] = {}
        self.bl_nodes: dict[str, bpy.types.Node] = {}
        self.referenced_kind: dict[str, str] = {}
        self.output_socket: dict[str, bpy.types.NodeSocket] = {}
        self.input_socket: dict[tuple[str, str], bpy.types.NodeSocket] = {}
        self.pending_container_inputs: list[tuple[str, str, str]] = []

        # Owner -> target state pairs of transition records, used only for layout.
        self.transition_layout_edges: list[tuple[bpy.types.Node, bpy.types.Node]] = []
        # Indices of transitions no state lists (kept on the state machine node).
        self.unowned_transitions: list[int] = []
        self._iface_names: dict[tuple[str, str], set[str]] = {}
        self.problems: list[str] = []
        self.context: bpy.types.Context | None = None
        self.group_wires: list[tuple[bpy.types.Node, bpy.types.Node]] = []
        self.deferred_links: list[tuple[bpy.types.Node, str, bpy.types.Node, str]] = []
        self.boundary_links: list[tuple[bpy.types.Node, str, bpy.types.Node, str]] = []
        self.group_input_node: dict[str, bpy.types.Node] = {}
        self.root_output_node: bpy.types.Node | None = None
        self.root_output_link: dict | None = None
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream

    def execute(self, payload: dict, context: typing.Optional[bpy.types.Context] = None) -> None:
=======
        self.presenter_import_failures: dict[str, int] = {}

    def execute(self, payload: dict, context: bpy.types.Context | None = None) -> None:
>>>>>>> Stashed changes
        self.context = context
        self._annotate_document_identity(payload)
        root_chunk = payload.get("Data", {}).get("RootChunk", {})
        self._discover(root_chunk)
        self._annotate_tree_identity(root_chunk)
        self._build_subgraph_trees()
<<<<<<< Updated upstream
        self._instantiate_nodes()
        self._enumerate_all_links()
        self._validate_referenced_output_kinds()


        self._build_group_io()
=======
        self._enumerate_all_links()
        self._infer_referenced_output_kinds()
        self._instantiate_nodes()
        self._validate_referenced_output_kinds()

>>>>>>> Stashed changes
        self._build_node_sockets()
        self._plan_root_output(root_chunk)
        self._plan_boundary_links()
        self._plan_transitions()
        self._sync_container_nodes()

        self._resolve_links()
        self._link_boundary_links()
<<<<<<< Updated upstream
        self._wire_group_outputs()
        self._link_root_output()
        self._link_transitions()
=======
        self._link_root_output()
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
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
=======
            data_meta = (
                {key: value for key, value in data.items() if key != "RootChunk"}
                if isinstance(data, dict)
                else {}
            )
            self.root_tree["red_source_header_json"] = json_io.dumps(
                header if isinstance(header, dict) else {}, indent=None
            )
            self.root_tree["red_source_data_meta_json"] = json_io.dumps(
                data_meta, indent=None
            )
        except Exception as exc:
            debug_exception(
                _LOG, "Could not record the document identity on the AnimGraph tree"
            )
>>>>>>> Stashed changes
            self.problems.append(f"document identity annotation failed: {exc}")

    def _initialize_curve_widgets(self) -> None:
        try:
            ok, failed = curve_mapping.initialize_native_curves_for_tree(self.root_tree)
        except Exception as exc:
<<<<<<< Updated upstream
=======
            debug_exception(_LOG, "Could not initialize the native curve widgets")
>>>>>>> Stashed changes
            self.problems.append(f"native curve widget initialization failed: {exc}")
            return
        self.curve_widgets_initialized = ok
        self.curve_widgets_failed = failed
        if failed:
<<<<<<< Updated upstream
            self.problems.append(f"{failed} native curve widget helper(s) could not be initialized")
=======
            self.problems.append(
                f"{failed} native curve widget helper(s) could not be initialized"
            )
>>>>>>> Stashed changes

    def _annotate_tree_identity(self, root_chunk: dict) -> None:
        try:
            root_handle = self._entry_handle(root_chunk.get("rootNode"))
            if root_handle is None:
                for hid, data in self.definitions.items():
<<<<<<< Updated upstream
                    if isinstance(data, dict) and data.get("$type") == f"{ANIM_NODE_PREFIX}Root":
=======
                    if (
                        isinstance(data, dict)
                        and data.get("$type") == f"{ANIM_NODE_PREFIX}Root"
                    ):
>>>>>>> Stashed changes
                        root_handle = hid
                        break

            nodes_to_init = root_chunk.get("nodesToInit") or []
            init_root_handle = ""
<<<<<<< Updated upstream
            init_refs: typing.List[str] = []
=======
            init_refs: list[str] = []
>>>>>>> Stashed changes
            init_inline_after_root = 0
            if isinstance(nodes_to_init, list):
                for index, entry in enumerate(nodes_to_init):
                    hid = self._entry_handle(entry)
                    if hid is None:
                        continue
<<<<<<< Updated upstream
                    if index == 0 and isinstance(entry, dict) and isinstance(entry.get("Data"), dict):
                        init_root_handle = str(hid)
                        continue


=======
                    if (
                        index == 0
                        and isinstance(entry, dict)
                        and isinstance(entry.get("Data"), dict)
                    ):
                        init_root_handle = str(hid)
                        continue

>>>>>>> Stashed changes
                    init_refs.append(str(hid))
                    if isinstance(entry, dict) and isinstance(entry.get("Data"), dict):
                        init_inline_after_root += 1

<<<<<<< Updated upstream

            root_nodes_order: typing.List[typing.Dict[str, typing.Any]] = []
=======
            root_nodes_order: list[dict[str, typing.Any]] = []
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
                    inline = isinstance(item, dict) and isinstance(item.get("Data"), dict) and bool(item.get("HandleId"))
                    root_nodes_order.append({"handle": str(hid), "inline": bool(inline)})

            root_output_spec: typing.Dict[str, typing.Any] = {"present": False, "link_type": "animPoseLink", "handle": "", "null": True}
            if isinstance(root_data, dict):
                root_output = root_data.get("outputNode")
                if isinstance(root_output, dict) and root_output.get("$type") in LINK_TYPES:
=======
                    inline = (
                        isinstance(item, dict)
                        and isinstance(item.get("Data"), dict)
                        and bool(item.get("HandleId"))
                    )
                    root_nodes_order.append(
                        {"handle": str(hid), "inline": bool(inline)}
                    )

            root_output_spec: dict[str, typing.Any] = {
                "present": False,
                "link_type": "animPoseLink",
                "handle": "",
                "null": True,
            }
            if isinstance(root_data, dict):
                root_output = root_data.get("outputNode")
                if (
                    isinstance(root_output, dict)
                    and root_output.get("$type") in LINK_TYPES
                ):
>>>>>>> Stashed changes
                    target = self._link_target_handle(root_output)
                    root_output_spec = {
                        "present": True,
                        "link_type": str(root_output.get("$type") or "animPoseLink"),
                        "handle": str(target or ""),
                        "null": target is None,
                    }

<<<<<<< Updated upstream

            root_data_fields: typing.Dict[str, typing.Any] = {}
=======
            root_data_fields: dict[str, typing.Any] = {}
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
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
=======
            scalars = {
                key: root_chunk.get(key) for key in scalar_keys if key in root_chunk
            }

            self.root_tree["red_root_handle"] = str(
                root_handle or init_root_handle or ""
            )
            self.root_tree["red_nodes_to_init_count"] = (
                len(nodes_to_init) if isinstance(nodes_to_init, list) else 0
            )
            self.root_tree["red_nodes_to_init_root_handle"] = str(
                init_root_handle or root_handle or ""
            )
            self.root_tree["red_nodes_to_init_refs_json"] = json_io.dumps(
                init_refs, indent=None
            )
            self.root_tree["red_nodes_to_init_inline_after_root"] = int(
                init_inline_after_root
            )
            self.root_tree["red_root_nodes_order_json"] = json_io.dumps(
                root_nodes_order, indent=None
            )
            self.root_tree["red_root_output_json"] = json_io.dumps(
                root_output_spec, indent=None
            )
            self.root_tree["red_root_data_fields_json"] = json_io.dumps(
                root_data_fields, indent=None
            )
            self.root_tree["red_rootchunk_scalars_json"] = json_io.dumps(
                scalars, indent=None
            )
            self.root_tree["red_public_tree"] = True
            if init_inline_after_root:
                self.problems.append(
                    f"nodesToInit contained {init_inline_after_root} inline entry/entries after the root; "
                    f"export will reconstruct them as HandleRefId entries"
                )
        except Exception as exc:
            debug_exception(
                _LOG, "Could not record the source identity on the AnimGraph tree"
            )
>>>>>>> Stashed changes
            self.problems.append(f"tree source identity annotation failed: {exc}")

    def _audit_source_alignment(self) -> None:
        try:
            report = graph_index.audit_parser(self)
            self.source_alignment_report = report
            graph_index.write_report_to_tree(self.root_tree, report)
<<<<<<< Updated upstream
            for problem in report.get('problems', []):
                self.problems.append(f"source alignment: {problem}")
        except Exception as exc:
=======
            for problem in report.get("problems", []):
                self.problems.append(f"source alignment: {problem}")
        except Exception as exc:
            debug_exception(_LOG, "The source alignment audit failed")
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
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
=======
                try:
                    live = _live_link_entries(pending)
                    if len(live) < len(pending):
                        _LOG.debug(
                            "Deferred links dropped for %d freed node(s)",
                            len(pending) - len(live),
                        )
                    remaining = self._link_named(live)
                    _LOG.debug(
                        "Deferred links connected: %d/%d",
                        len(live) - len(remaining),
                        len(live),
                    )
                    for src_node, out_name, tgt_node, in_name in remaining:
                        _LOG.warning(
                            "Could not link %s.%s -> %s.%s",
                            src_node.name,
                            out_name,
                            tgt_node.name,
                            in_name,
                        )
                    return
                finally:
                    _DEFERRED_TIMERS.discard(finish)

            _DEFERRED_TIMERS.add(finish)
            try:
                timers.register(finish, first_interval=0.0)
            except Exception:
                _DEFERRED_TIMERS.discard(finish)
                raise
            # A rolled-back import removes its tree, so its pending links must not run afterwards.
            track_mutation(
                ("animgraph_deferred_links", id(finish)),
                lambda callback=finish: _cancel_deferred_link_timer(callback),
                label="AnimGraph deferred links",
            )
        else:
            self.problems.append(
                f"{len(self.deferred_links)} links could not be made and no timer "
                f"API is available to retry after the update flush"
            )
>>>>>>> Stashed changes

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
<<<<<<< Updated upstream
                if not any(l.from_socket is out_sock and l.to_socket is in_sock
                           for l in src_node.id_data.links):
                    src_node.id_data.links.new(out_sock, in_sock)
=======
                if not has_link(src_node.id_data, out_sock, in_sock):
                    link_sockets(src_node.id_data, out_sock, in_sock)
>>>>>>> Stashed changes
            else:
                remaining.append((src_node, out_name, tgt_node, in_name))
        return remaining

    def _audit_roundtrip_readiness(self) -> None:
        try:
            report = roundtrip.report_for_tree(self.root_tree)
            self.roundtrip_audit_report = report
            reporting.write_report(
<<<<<<< Updated upstream
                self.root_tree, report,
=======
                self.root_tree,
                report,
>>>>>>> Stashed changes
                report_key=roundtrip.REPORT_KEY,
                summary_key=roundtrip.SUMMARY_KEY,
                ready_key=roundtrip.READY_KEY,
            )
<<<<<<< Updated upstream
            blockers = int((report.get('counters') or {}).get('blocking_issues', 0) or 0)
            if blockers:
                self.problems.append(f"round-trip audit found {blockers} blocking issue(s)")
        except Exception as exc:
            self.roundtrip_audit_report = {}
            self.problems.append(f"round-trip audit failed: {exc}")

    def _emit_report(self) -> None:
        internal_subgraphs = sum(
            1 for hid, tree in self.tree_of_container.items()
=======
            blockers = int(
                (report.get("counters") or {}).get("blocking_issues", 0) or 0
            )
            if blockers:
                self.problems.append(
                    f"round-trip audit found {blockers} blocking issue(s)"
                )
        except Exception as exc:
            debug_exception(_LOG, "The round-trip readiness audit failed")
            self.roundtrip_audit_report = {}
            self.problems.append(f"round-trip audit failed: {exc}")

    def _count_transition_records(self) -> int:
        trees = [self.root_tree, *self.tree_of_container.values()]
        seen: set[int] = set()
        count = 0
        for tree in trees:
            if tree is None or id(tree) in seen:
                continue
            seen.add(id(tree))
            for node in tree.nodes:
                count += len(getattr(node, "red_transitions", ()) or ())
        return count

    def _emit_report(self) -> None:
        internal_subgraphs = sum(
            1
            for hid, tree in self.tree_of_container.items()
>>>>>>> Stashed changes
            if tree is not self.root_tree
        )
        enumerated = sum(len(self.node_links.get(h, ())) for h in self.bl_nodes)
        unresolved = enumerated - len(self.input_socket)
<<<<<<< Updated upstream
        planned = len(self.planned_transitions)
        represented = planned - len(self.failed_transition_edges)
        deferred = len(self.deferred_links)
        if unresolved:
            self.problems.append(f"{unresolved} link sockets could not be materialised")
        if self.failed_transition_edges:
            self.problems.append(f"{len(self.failed_transition_edges)} transition record(s) failed during creation")
        meta = rtti.stats()
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
=======
        transition_records = self._count_transition_records()
        deferred = len(self.deferred_links)
        if unresolved:
            self.problems.append(f"{unresolved} link sockets could not be materialised")
        summary_logger = _LOG.warning if unresolved else _LOG.info
        summary_logger(
            "Imported AnimGraph: nodes=%d transition_records=%d unresolved_inputs=%d",
            len(self.bl_nodes),
            transition_records,
            unresolved,
        )
        if self.presenter_import_failures:
            total_presenter_failures = sum(self.presenter_import_failures.values())
            detail = ", ".join(
                f"{name}={count}"
                for name, count in sorted(self.presenter_import_failures.items())
            )
            _LOG.warning(
                "AnimGraph specialized presenter state was unavailable for %d node(s): %s. "
                "Core graph import continued, but specialized editor state may be incomplete; "
                "the first failure per presenter is logged at DEBUG.",
                total_presenter_failures,
                detail,
            )
        if _LOG.isEnabledFor(logging.DEBUG):
            try:
                meta = rtti.stats()
                presenter_stats = node_presenters.summary()
                meta_tag = (
                    "schema=(nodes=%d/%d enums=%d flags=%d presenters=%d) "
                    % (
                        meta.get("concrete_anim_nodes", 0),
                        meta.get("anim_nodes", 0),
                        meta.get("enum_definitions", 0),
                        meta.get("flag_enums", 0),
                        presenter_stats.get("presenters", 0),
                    )
                    if meta.get("metadata_loaded")
                    else "schema=(nodes=0/0 enums=0 flags=0 presenters=0) "
                )
                audit_summary = (self.source_alignment_report or {}).get("summary", "")
                audit_tag = (
                    f"source-alignment=({audit_summary}) " if audit_summary else ""
                )
                var_bound = (
                    int(self.root_tree.get("red_variable_bound_nodes", 0))
                    if hasattr(self.root_tree, "get")
                    else 0
                )
                var_unbound = (
                    int(self.root_tree.get("red_variable_unbound_nodes", 0))
                    if hasattr(self.root_tree, "get")
                    else 0
                )
                variable_tag = (
                    f"variables=(declared={len(self.root_tree.variables)} "
                    f"bound-nodes={var_bound} unbound-nodes={var_unbound}) "
                )
                math_tag = (
                    f"math-expressions=(nodes={self.math_expression_nodes} "
                    f"inputs={self.math_expression_inputs}) "
                )
                roundtrip_tag = ""
                try:
                    counters = (self.roundtrip_audit_report or {}).get("counters", {})
                    if counters:
                        roundtrip_tag = (
                            f"roundtrip=(ready={bool(counters.get('ready', 0))} "
                            f"nodes={counters.get('runtime_nodes_schema_known', 0)}/{counters.get('runtime_nodes', 0)} "
                            f"props={counters.get('properties_encodable', 0)}/{counters.get('properties_total', 0)} "
                            f"links={counters.get('dataflow_links_encodable', 0)}/{counters.get('dataflow_links', 0)} "
                            f"blockers={counters.get('blocking_issues', 0)} warnings={counters.get('warnings', 0)}) "
                        )
                except Exception:
                    debug_exception(
                        _LOG,
                        "Could not summarize the round-trip audit for the import report",
                    )
                    roundtrip_tag = ""
                _LOG.debug(
                    "nodes=%d public-trees=1 internal-subgraphs=%d %s%s%s%s%s"
                    "link-sockets=%d link-edges=%d transition-records=%d "
                    "unowned-transitions=%d deferred-links=%d "
                    "cross-tree-routed=%d cross-tree-unroutable=%d unresolved-inputs=%d "
                    "curve-widgets=%d/%d layout-overlaps=%d "
                    "dangle-editor=(particles=%d constraints=%d shapes=%d)",
                    len(self.bl_nodes),
                    internal_subgraphs,
                    meta_tag,
                    audit_tag,
                    variable_tag,
                    math_tag,
                    roundtrip_tag,
                    len(self.input_socket),
                    self.drawn_link_edges,
                    transition_records,
                    len(self.unowned_transitions),
                    deferred,
                    self.routed_cross_tree_links,
                    self.unroutable_cross_tree_links,
                    unresolved,
                    self.curve_widgets_initialized,
                    self.curve_widgets_initialized + self.curve_widgets_failed,
                    self.layout_overlap_count,
                    self.dangle_editor_particles,
                    self.dangle_editor_constraints,
                    self.dangle_editor_shapes,
                )
            except Exception:
                debug_exception(_LOG, "AnimGraph import diagnostics failed")
        for problem in self.problems:
            _LOG.warning("%s", problem)
>>>>>>> Stashed changes
