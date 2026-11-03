import json
import typing

import bpy

from ...animation.animgraph_constants import (
    ANIM_NODE_PREFIX, CONTAINER_FIELDS, HIDDEN_FIELDS, HIDDEN_FIELD_PREFIXES, LINK_TYPES,
)
from ...blender.animgraph import categories, presenters as node_presenters
from ...blender.animgraph.categories import NODE_CATEGORY_COLORS
from ...animation.animgraph.model import math_expression
from ...blender.animgraph.property_codec import add_node_property, clear_node_properties
from ...animation.animgraph.schema import rtti
from ...blender.transactions import track_created_datablock

class ParserBuildMixin:
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


            sub_tree = track_created_datablock(
                "node_groups",
                bpy.data.node_groups.new(
                    name=self._subtree_name(hid),
                    type='REDengine_AnimGraphTree',
                ),
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
            node.red_metadata_known = bool(rtti.has_class(node_type))
            node.red_parent_class = rtti.parent_of(node_type)
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
        type_map = rtti.property_type_map(data.get('$type', ''))
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
        return rtti.ordered_field_names(node_type, obj.keys())

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
                return ParserBuildMixin._flatten_value(value["Data"])
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
