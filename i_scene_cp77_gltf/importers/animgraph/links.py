
import bpy

from ...animation.model.animgraph import math_expression
from ...animation.model.animgraph.constants import (
    ANIM_NODE_PREFIX,
    CONTAINER_OUTPUT_NAME,
    LINK_SOCKET,
    LINK_TYPES,
    OUTPUT_NODE_TYPE,
)
from ...animation.model.animgraph.schema import registry, rtti
from ...blender.animgraph import categories
from ...blender.animgraph.categories import NODE_CATEGORY_COLORS
from ...blender.animgraph.sockets import bind_input_socket, bind_red_socket
from ...blender.animgraph.tree_ops import (
    ensure_socket,
    link_sockets,
    new_editor_node,
    new_socket,
)


class ParserLinksMixin:
    def _enumerate_all_links(self) -> None:
        for hid in self.definitions:
            self.node_links[hid] = self._enumerate_links(hid)

    def _enumerate_links(
        self, handle_id: str
    ) -> list[tuple[str, str, dict]]:
        """Enumerate nested REDengine link fields in editor traversal order"""
        entries: list[tuple[str, str, dict]] = []
        self._gather_links(self.definitions[handle_id], "", "", entries, set())
        return entries

    def _gather_links(
        self,
        obj: dict,
        key_prefix: str,
        name_prefix: str,
        entries: list[tuple[str, str, dict]],
        visited: set[str],
    ) -> None:
        stack = [("object", obj, key_prefix, name_prefix)]
        while stack:
            action, value, current_key, current_name = stack.pop()
            if action == "object":
                fields = self._ordered_fields(value)
                for field in reversed(fields):
                    if field != "$type":
                        stack.append(
                            ("field", (value, field), current_key, current_name)
                        )
                continue

            if action == "array_element":
                element, array_field, index = value
                if element.get("$type") in LINK_TYPES:
                    entries.append(
                        (f"{current_key}{array_field}[{index}]", str(index), element)
                    )
                    continue
                target = self._descend_target(element, visited)
                if target is not None:
                    stack.append(
                        (
                            "object",
                            target,
                            f"{current_key}{array_field}[{index}].",
                            f"{current_name}[{array_field} {index}] ",
                        )
                    )
                continue

            owner, field = value
            field_value = owner.get(field)
            if isinstance(field_value, dict):
                if (
                    field == "expressionData"
                    and math_expression.is_math_expression_data(field_value)
                ):
                    for (
                        rel_path,
                        caption,
                        wrapper,
                        _summary,
                    ) in math_expression.iter_expression_socket_links(field_value):
                        entries.append(
                            (f"{current_key}{field}.{rel_path}", caption, wrapper)
                        )
                    continue
                if field_value.get("$type") in LINK_TYPES:
                    caption = self._math_expression_socket_caption(owner, current_key)
                    if not caption:
                        caption = registry.friendly_label(current_name + field)
                    entries.append((current_key + field, caption, field_value))
                    continue
                target = self._descend_target(field_value, visited)
                if target is not None:
                    stack.append(
                        ("object", target, f"{current_key}{field}.", current_name)
                    )
                continue
            if not isinstance(field_value, list):
                continue
            for index in range(len(field_value) - 1, -1, -1):
                element = field_value[index]
                if not isinstance(element, dict):
                    continue
                stack.append(
                    (
                        "array_element",
                        (element, field, index),
                        current_key,
                        current_name,
                    )
                )

    def _descend_target(
        self, value: dict, visited: set[str]
    ) -> dict | None:
        """Resolve the payload reached through a serialized field"""
        if "HandleId" in value and isinstance(value.get("Data"), dict):
            hid, data = str(value["HandleId"]), value["Data"]
        elif "HandleRefId" in value:
            hid = str(value["HandleRefId"])
            data = self.handle_data.get(hid)
            if data is None:
                return None
        else:
            return value
        if rtti.is_graph_node_type(str(data.get("$type", ""))) or hid in visited:
            return None
        visited.add(hid)
        return data

    def _infer_referenced_output_kinds(self) -> None:
        """Infer missing node output metadata from serialized link wrappers"""
        observed: dict[str, set[str]] = {}
        for entries in self.node_links.values():
            for _key, _caption, wrapper in entries:
                target = self._link_target_handle(wrapper)
                link_type = wrapper.get("$type") if isinstance(wrapper, dict) else None
                if (
                    target is None
                    or target not in self.definitions
                    or link_type not in LINK_SOCKET
                ):
                    continue
                observed.setdefault(target, set()).add(str(link_type))

        for handle_id, kinds in observed.items():
            if len(kinds) == 1:
                self.referenced_kind[handle_id] = next(iter(kinds))
            else:
                self.problems.append(
                    f"source {handle_id} is referenced through conflicting link kinds: "
                    + ", ".join(sorted(kinds))
                )

    def _validate_referenced_output_kinds(self) -> None:
        """Validate link kind against the referenced node output kind"""
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
                        f"source {tgt} outputs {expected}"
                    )

    def _node_output_kind(self, handle_id: str) -> str | None:
        data = self.definitions.get(handle_id, {})
        node_type = data.get("$type", "")
        if node_type == OUTPUT_NODE_TYPE:
            return None
        short = node_type.replace(ANIM_NODE_PREFIX, "")
        metadata_kind = registry.output_kind(short)
        if metadata_kind is not None:
            return metadata_kind
        return self.referenced_kind.get(handle_id)

    def _build_node_sockets(self) -> None:
        """Materialize node sockets from serialized link fields and presenter metadata"""
        for hid, node in self.bl_nodes.items():
            data = self.definitions[hid]
            node_type = data.get("$type", "")
            is_container = node.bl_idname == "REDengine_AnimGraphContainer"

            if is_container:
                socket = ensure_socket(
                    node,
                    "OUTPUT",
                    CONTAINER_OUTPUT_NAME,
                    "REDengine_AnimGraphSocket_Pose",
                )
                self.output_socket[hid] = bind_red_socket(
                    socket,
                    role="output",
                    owner_handle=hid,
                    link_type="animPoseLink",
                    exportable=True,
                    edge_semantics="dataflow",
                    source_handle=hid,
                    pseudo=False,
                )
            elif node_type != OUTPUT_NODE_TYPE:
                kind = self._node_output_kind(hid)
                if kind in LINK_SOCKET:
                    socket_bl, _ = LINK_SOCKET[kind]
                    caption = "Out Pose" if kind == "animPoseLink" else "Out Value"
                    socket = new_socket(node, "OUTPUT", socket_bl, caption)
                    self.output_socket[hid] = bind_red_socket(
                        socket,
                        role="output",
                        owner_handle=hid,
                        link_type=kind,
                        exportable=True,
                        edge_semantics="dataflow",
                        source_handle=hid,
                        pseudo=False,
                    )
                else:
                    self.problems.append(
                        f"node {node_type}({hid}) has no known or inferable output kind; "
                        "its unused output socket was omitted"
                    )

            used: set[str] = set()
            for key, caption, wrapper in self.node_links.get(hid, ()):
                self._add_input_socket(
                    node, hid, key, caption, wrapper["$type"], used, wrapper
                )

    def _add_input_socket(
        self,
        node: bpy.types.Node,
        handle_id: str,
        key: str,
        caption: str,
        link_type: str,
        used: set[str],
        wrapper: dict | None = None,
    ) -> None:
        socket_bl, _ = LINK_SOCKET[link_type]
        if caption in used:
            caption = key
        used.add(caption)
        socket = ensure_socket(node, "INPUT", caption, socket_bl)
        bind_input_socket(
            socket,
            owner_handle=handle_id,
            json_path=key,
            link_type=link_type,
            source_handle=(
                self._link_target_handle(wrapper) if isinstance(wrapper, dict) else ""
            )
            or "",
            ref_style=(
                self._link_ref_style(wrapper) if isinstance(wrapper, dict) else ""
            ),
            edge_semantics="dataflow",
        )
        self.input_socket[(handle_id, key)] = socket

    def _resolve_links(self) -> None:
        for hid, entries in self.node_links.items():
            target_node = self.bl_nodes.get(hid)
            if target_node is None:
                continue
            target_tree = target_node.id_data
            for key, caption, wrapper in entries:
                self._connect_link(hid, key, caption, wrapper, target_tree)

    def _connect_link(
        self,
        target_hid: str,
        key: str,
        caption: str,
        wrapper: dict,
        target_tree: bpy.types.NodeTree,
    ) -> None:
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
            out_name = out_socket.name if out_socket is not None else None
            in_name = in_socket.name if in_socket is not None else caption
            if out_name is not None and in_name is not None:
                self.deferred_links.append(
                    (source_node, out_name, target_node, in_name)
                )
            return
        link_sockets(target_tree, out_socket, in_socket)
        self.drawn_link_edges += 1

    def _output_socket_of(
        self, node: bpy.types.Node, handle_id: str
    ) -> bpy.types.NodeSocket | None:
        return self.output_socket.get(handle_id) or node.outputs.get(
            CONTAINER_OUTPUT_NAME
        )

    def _output_socket_name_of(
        self, node: bpy.types.Node, handle_id: str
    ) -> str | None:
        sock = self._output_socket_of(node, handle_id)
        return sock.name if sock is not None else None

    def _new_pseudo_node(
        self, tree: bpy.types.NodeTree, short: str, label: str, handle_id: str
    ) -> bpy.types.Node:
        """Create an editor-derived helper node that is excluded from export"""
        return new_editor_node(
            tree,
            red_type=f"editor{short}",
            handle=handle_id,
            label=label,
            color=NODE_CATEGORY_COLORS[categories.node_category(short)],
        )

    def _plan_root_output(self, root_chunk: dict) -> None:
        """Represent Root.outputNode in the editor when it returns a pose"""
        root = self._payload_of(root_chunk.get("rootNode"))
        if not isinstance(root, dict):
            for hid, data in self.definitions.items():
                if (
                    self.container_of.get(hid) is None
                    and data.get("$type") == f"{ANIM_NODE_PREFIX}Root"
                ):
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
            self.root_tree, "RootOutput", "Root Output", "editorRootOutput"
        )
        sock = new_socket(node, "INPUT", "REDengine_AnimGraphSocket_Pose", "Output")
        bind_red_socket(
            sock,
            role="input",
            owner_handle=getattr(node, "red_handle_id", ""),
            field_name="outputNode",
            json_path="outputNode",
            link_type=wrapper.get("$type", "animPoseLink"),
            source_handle=(self._link_target_handle(wrapper) or ""),
            ref_style=self._link_ref_style(wrapper),
            exportable=False,
            edge_semantics="root_output",
            pseudo=True,
        )
        self.root_output_node = node
        self.root_output_link = wrapper

    def _link_root_output(self) -> None:
        if self.root_output_node is None or self.root_output_link is None:
            return
        self._connect_wrapper_to_node(
            self.root_output_link, self.root_output_node, "Output", self.root_tree
        )

    def _ancestor_containers(self, handle_id: str) -> list[str]:
        chain: list[str] = []
        current = self.container_of.get(handle_id)
        while current is not None:
            data = self.definitions.get(current, {})
            if not (
                self.container_of.get(current) is None
                and data.get("$type") == f"{ANIM_NODE_PREFIX}Root"
            ):
                chain.append(current)
            current = self.container_of.get(current)
        return chain

    def _container_chain_from_tree_to_target(
        self,
        source_tree: bpy.types.NodeTree,
        target_hid: str,
    ) -> list[str] | None:
        outer_to_inner = list(reversed(self._ancestor_containers(target_hid)))
        for i, container_hid in enumerate(outer_to_inner):
            node = self.bl_nodes.get(container_hid)
            if node is not None and node.id_data is source_tree:
                return outer_to_inner[i:]
        return (
            []
            if self.bl_nodes.get(target_hid, None) is not None
            and self.bl_nodes[target_hid].id_data is source_tree
            else None
        )

    def _group_input_for(self, container_hid: str) -> bpy.types.Node | None:
        tree = self.tree_of_container.get(container_hid)
        if tree is None:
            return None
        node = self.group_input_node.get(container_hid)
        if node is None:
            node = self._new_pseudo_node(
                tree,
                "BoundaryInput",
                "Boundary Inputs",
                f"editorBoundaryInput_{container_hid}",
            )
            self.group_input_node[container_hid] = node
        return node

    def _safe_link_label(self, source_hid: str, target_hid: str, caption: str) -> str:
        src = (
            self.definitions.get(source_hid, {})
            .get("$type", source_hid)
            .replace(ANIM_NODE_PREFIX, "")
        )
        tgt = (
            self.definitions.get(target_hid, {})
            .get("$type", target_hid)
            .replace(ANIM_NODE_PREFIX, "")
        )
        base = f"{src} → {tgt}.{caption}"
        return base[:80]

    def _plan_boundary_links(self) -> None:
        """Declare editor boundary links for references crossing into subgraphs"""
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
                if not self._plan_one_boundary_link(
                    source_hid, target_hid, key, caption, wrapper
                ):
                    self.unroutable_cross_tree_links += 1
                    self.skipped_cross_tree_links = self.unroutable_cross_tree_links
                    self.problems.append(
                        f"unroutable cross-tree link: {source_hid} -> {target_hid}.{key}"
                    )

    def _plan_one_boundary_link(
        self, source_hid: str, target_hid: str, key: str, caption: str, wrapper: dict
    ) -> bool:
        source_node = self.bl_nodes[source_hid]
        target_node = self.bl_nodes[target_hid]
        chain = self._container_chain_from_tree_to_target(
            source_node.id_data, target_hid
        )
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
                container_node, "INPUT", base if depth == 0 else f"{base} ({depth + 1})"
            )
            container_sock = ensure_socket(
                container_node, "INPUT", sock_name, socket_type
            )
            bind_red_socket(
                container_sock,
                role="input",
                owner_handle=container_hid,
                field_name=key,
                json_path=key,
                link_type=wrapper.get("$type", ""),
                source_handle=source_hid,
                target_handle=target_hid,
                ref_style=self._link_ref_style(wrapper),
                exportable=False,
                edge_semantics="container_boundary",
                pseudo=True,
            )
            boundary_sock = ensure_socket(
                boundary_node, "OUTPUT", sock_name, socket_type
            )
            bind_red_socket(
                boundary_sock,
                role="output",
                owner_handle=getattr(boundary_node, "red_handle_id", ""),
                field_name=key,
                json_path=key,
                link_type=wrapper.get("$type", ""),
                source_handle=source_hid,
                target_handle=target_hid,
                ref_style=self._link_ref_style(wrapper),
                exportable=False,
                edge_semantics="container_boundary",
                pseudo=True,
            )

            self.boundary_links.append(
                (prev_node, prev_out_name, container_node, sock_name)
            )

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

    def _connect_wrapper_to_node(
        self,
        wrapper: dict,
        target_node: bpy.types.Node,
        in_name: str,
        target_tree: bpy.types.NodeTree,
    ) -> None:
        source_hid = self._link_target_handle(wrapper)
        if source_hid is None or source_hid not in self.bl_nodes:
            return
        source_node = self.bl_nodes[source_hid]
        out_name = self._output_socket_name_of(source_node, source_hid)
        if out_name is None:
            return
        if source_node.id_data is target_tree:
            remaining = self._link_named(
                [(source_node, out_name, target_node, in_name)]
            )
            self.deferred_links.extend(remaining)
        else:
            self.problems.append(
                f"Root output source {source_hid} is not in the root tree; not linked"
            )
