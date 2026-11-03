import typing
from collections import defaultdict, deque

import bpy
from mathutils import Vector

from ...animation.animgraph_constants import ANIM_NODE_PREFIX

class ParserLayoutMixin:
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
