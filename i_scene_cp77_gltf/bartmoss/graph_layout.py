from __future__ import annotations

import typing
from collections import defaultdict, deque

from .geometry import box_intersects_any_padded


class LayoutItem:
    """One box to place. Items hash by identity"""

    __slots__ = (
        "branch_exempt",
        "height",
        "key",
        "label",
        "pendant_exempt",
        "structural",
        "width",
        "x",
        "y",
    )

    def __init__(
        self,
        key: str,
        label: str,
        width: float,
        height: float,
        *,
        structural: bool = False,
        pendant_exempt: bool = False,
        branch_exempt: bool = False,
        x: float = 0.0,
        y: float = 0.0,
    ):
        self.key = key
        self.label = label
        self.width = float(width)
        self.height = float(height)
        self.structural = bool(structural)
        self.pendant_exempt = bool(pendant_exempt)
        self.branch_exempt = bool(branch_exempt)
        self.x = float(x)
        self.y = float(y)


def layout_graph(
    items: typing.Sequence[LayoutItem],
    edges: typing.Iterable[tuple[LayoutItem, LayoutItem]],
    x_gap: float = 240.0,
    y_gap: float = 170.0,
    component_gap: float = 300.0,
) -> int:
    """Place every item and return the number of overlapping box pairs left"""
    nodes = list(items)
    if not nodes:
        return 0
    known = set(nodes)
    clean_edges = []
    seen_edges = set()
    for a, b in edges:
        if a in known and b in known and a is not b:
            key = (a.key, b.key)
            if key not in seen_edges:
                seen_edges.add(key)
                clean_edges.append((a, b))

    pred: dict[LayoutItem, list[LayoutItem]] = {n: [] for n in nodes}
    succ: dict[LayoutItem, list[LayoutItem]] = {n: [] for n in nodes}
    for a, b in clean_edges:
        succ[a].append(b)
        pred[b].append(a)

    components = _weak_components(nodes, pred, succ)
    clusters = sorted((c for c in components if len(c) > 1), key=len, reverse=True)
    singles = [c[0] for c in components if len(c) == 1]

    y_cursor = 0.0
    for members in clusters:
        y_cursor = _layout_component_packed(
            members, pred, succ, x_gap=x_gap, y_gap=y_gap, y_top=y_cursor
        )
        y_cursor -= component_gap

    if singles:
        _layout_singleton_grid_packed(singles, x_gap=x_gap, y_gap=y_gap, y_top=y_cursor)

    return count_box_overlaps((n.x, n.x + n.width, n.y - n.height, n.y) for n in nodes)


def count_box_overlaps(
    boxes: typing.Iterable[tuple[float, float, float, float]],
) -> int:
    """Overlapping pairs among (x1, x2, y1, y2) boxes"""
    ordered = sorted(boxes)
    count = 0
    # Sweep along x: only boxes starting before this one ends can overlap it.
    for i, (ax1, ax2, ay1, ay2) in enumerate(ordered):
        for j in range(i + 1, len(ordered)):
            bx1, bx2, by1, by2 = ordered[j]
            if bx1 >= ax2:
                break
            if ax1 < bx2 and ay1 < by2 and by1 < ay2:
                count += 1
    return count


def _box(node: LayoutItem, x: float, y: float):
    return (node, x, x + node.width, y - node.height, y)


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


def _layout_component_packed(
    members, pred, succ, x_gap: float, y_gap: float, y_top: float
) -> float:
    member_set = set(members)
    scc_list = _strong_components(members, succ)
    scc_of = {node: index for index, group in enumerate(scc_list) for node in group}

    dag_pred: dict[int, set[int]] = {
        i: set() for i in range(len(scc_list))
    }
    dag_succ: dict[int, set[int]] = {
        i: set() for i in range(len(scc_list))
    }
    for node in members:
        a = scc_of[node]
        for nxt in succ[node]:
            if nxt in member_set:
                b = scc_of[nxt]
                if a != b:
                    dag_succ[a].add(b)
                    dag_pred[b].add(a)

    topo = _toposort_component_ids(len(scc_list), dag_pred, dag_succ)
    scc_layer = {i: 0 for i in range(len(scc_list))}
    for comp_id in topo:
        base = scc_layer[comp_id]
        for nxt in dag_succ[comp_id]:
            scc_layer[nxt] = max(scc_layer[nxt], base + 1)

    layers: dict[int, list[LayoutItem]] = {}
    for node in members:
        layers.setdefault(scc_layer[scc_of[node]], []).append(node)
    keys = sorted(layers)

    for key in keys:
        layers[key].sort(key=lambda n: (n.label or n.key, n.key))
    _barycenter_order_layers(layers, keys, pred, succ)

    col_width = {key: max(n.width for n in layers[key]) for key in keys}
    col_height = {
        key: sum(n.height for n in layers[key]) + y_gap * max(0, len(layers[key]) - 1)
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
            node.x, node.y = col_x[key], y
            y -= node.height + y_gap

    _pull_pendant_nodes_near_neighbors(members, pred, succ, x_gap, y_gap)
    _pull_fanout_sources_near_consumers(members, pred, succ, x_gap, y_gap)
    _pull_fanout_pendant_clusters_near_consumers(members, pred, succ, x_gap, y_gap)
    _pull_small_pendant_branches_near_neighbors(members, pred, succ, x_gap, y_gap)
    _resolve_component_overlaps(members, y_gap)
    return min(node.y - node.height for node in members) if members else 0.0


def _median(values: typing.Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(v) for v in values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) * 0.5


def _search_offsets(step: float, count: int) -> list[float]:
    offsets = [0.0]
    for i in range(1, count):
        offsets.append(i * step)
        offsets.append(-i * step)
    return offsets


def _resolve_component_overlaps(members, y_gap: float) -> None:
    placed = []
    for node in sorted(members, key=lambda n: (n.x, -n.y, n.key)):
        x, y = node.x, node.y
        step = max(80.0, min(260.0, node.height * 0.35 + y_gap * 0.55))
        attempts = 0
        box = _box(node, x, y)
        # The node only moves vertically, so only boxes overlapping its padded x span matter.
        left, right = x - 44.0, x + node.width + 44.0
        column = [b for b in placed if left < b[2] and b[1] < right]
        while box_intersects_any_padded(box, column, pad=44.0) and attempts < 400:
            y -= step
            box = _box(node, x, y)
            attempts += 1
        node.x, node.y = x, y
        placed.append(box)


def _pull_fanout_sources_near_consumers(
    members, pred, succ, x_gap: float, y_gap: float
) -> None:
    member_set = set(members)
    placed = [_box(node, node.x, node.y) for node in members]

    candidates = []
    for node in members:
        if node.structural:
            continue
        out_nodes = [n for n in succ[node] if n in member_set]
        in_nodes = [n for n in pred[node] if n in member_set]
        if len(out_nodes) < 2 or in_nodes or len(out_nodes) > 24:
            continue
        consumer_left = min(n.x for n in out_nodes)
        if consumer_left - (node.x + node.width) < max(480.0, x_gap * 1.8):
            continue
        candidates.append((node, out_nodes))

    if not candidates:
        return

    candidates.sort(key=lambda item: (-len(item[1]), item[0].key))
    for node, out_nodes in candidates:
        nw, nh = node.width, node.height
        consumer_left = min(n.x for n in out_nodes)
        target_center = _median([dst.y - dst.height * 0.5 for dst in out_nodes])
        x = consumer_left - nw - max(120.0, x_gap * 0.60)
        y_base = target_center + nh * 0.5

        placed = [b for b in placed if b[0] is not node]
        step = max(90.0, nh * 0.45 + y_gap * 0.35)
        best = None
        column = [b for b in placed if x - 52.0 < b[2] and b[1] < x + nw + 52.0]
        for offset in _search_offsets(step, 160):
            y = y_base + offset
            box = _box(node, x, y)
            if not box_intersects_any_padded(box, column, pad=52.0):
                best = (x, y, box)
                break
        if best is None:
            y = y_base
            box = _box(node, x, y)
            while box_intersects_any_padded(box, column, pad=52.0):
                y -= step
                box = _box(node, x, y)
            best = (x, y, box)
        x, y, box = best
        node.x, node.y = x, y
        placed.append(box)


def _topo_order(nodes, pred, succ):
    nodes_set = set(nodes)
    indeg = {n: len([p for p in pred[n] if p in nodes_set]) for n in nodes}
    queue = deque(sorted((n for n in nodes if indeg[n] == 0), key=lambda n: n.key))
    result = []
    while queue:
        cur = queue.popleft()
        result.append(cur)
        for nxt in sorted(
            (n for n in succ[cur] if n in nodes_set), key=lambda n: n.key
        ):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    return (
        result
        if len(result) == len(nodes)
        else sorted(nodes, key=lambda n: (n.x, n.key))
    )


def _boxes_excluding(members, exclude):
    exclude = set(exclude)
    return [_box(node, node.x, node.y) for node in members if node not in exclude]


def _row_boxes(order, start_x: float, top: float, gap: float):
    boxes = []
    x = start_x
    for node in order:
        boxes.append((node, x, x + node.width, top - node.height, top))
        x += node.width + gap
    return boxes


def _pull_fanout_pendant_clusters_near_consumers(
    members, pred, succ, x_gap: float, y_gap: float
) -> None:
    member_set = set(members)

    def degree(node):
        return len([n for n in pred[node] + succ[node] if n in member_set])

    def collect_upstream_chain(hub):
        chain = []
        frontier = [p for p in pred[hub] if p in member_set and not p.structural]
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
                if pp in member_set and pp not in seen and not pp.structural:
                    frontier.append(pp)
        if frontier:
            return []
        return chain

    candidates = []
    for hub in members:
        if hub.structural:
            continue
        out_nodes = [n for n in succ[hub] if n in member_set]
        if len(out_nodes) < 2 or len(out_nodes) > 32:
            continue
        consumer_left = min(n.x for n in out_nodes)
        if consumer_left - (hub.x + hub.width) < max(560.0, x_gap * 2.0):
            continue
        chain = collect_upstream_chain(hub)
        cluster = _topo_order(chain + [hub], pred, succ)
        candidates.append((hub, out_nodes, cluster))

    moved = set()
    for hub, out_nodes, cluster in sorted(
        candidates, key=lambda item: (-len(item[1]), item[0].key)
    ):
        if any(n in moved for n in cluster):
            continue
        heights = [n.height for n in cluster]
        gap = max(95.0, x_gap * 0.48)
        total_w = sum(n.width for n in cluster) + max(0, len(cluster) - 1) * gap
        max_h = max(heights) if heights else 120.0
        consumer_left = min(n.x for n in out_nodes)
        target_center = _median([n.y - n.height * 0.5 for n in out_nodes])
        start_x = consumer_left - total_w - max(150.0, x_gap * 0.72)
        base_top = target_center + max_h * 0.5
        placed = _boxes_excluding(members, cluster)
        step = max(110.0, max_h * 0.55 + y_gap * 0.45)
        best = None
        for offset in _search_offsets(step, 120):
            boxes = _row_boxes(cluster, start_x, base_top + offset, gap)
            if not any(
                box_intersects_any_padded(box, placed, pad=56.0) for box in boxes
            ):
                best = boxes
                break
        if best is None:
            top = base_top
            while True:
                boxes = _row_boxes(cluster, start_x, top, gap)
                if not any(
                    box_intersects_any_padded(box, placed, pad=56.0) for box in boxes
                ):
                    best = boxes
                    break
                top -= step
        for node, x1, _x2, _y1, y2 in best:
            node.x, node.y = x1, y2
            moved.add(node)


def _pull_pendant_nodes_near_neighbors(
    members, pred, succ, x_gap: float, y_gap: float
) -> None:
    if len(members) < 3:
        return
    member_set = set(members)

    neighbours: dict[LayoutItem, list[LayoutItem]] = {}
    for node in members:
        seen = []
        for other in pred[node] + succ[node]:
            if other in member_set and other not in seen:
                seen.append(other)
        neighbours[node] = seen

    leaves = [
        node
        for node in members
        if len(neighbours[node]) == 1 and not node.pendant_exempt
    ]
    if not leaves:
        return

    leaf_set = set(leaves)
    placed = [_box(node, node.x, node.y) for node in members if node not in leaf_set]

    def leaf_sort_key(node):
        anchor = neighbours[node][0]
        return (anchor in leaf_set, anchor.key, node.key)

    for leaf in sorted(leaves, key=leaf_sort_key):
        anchor = neighbours[leaf][0]
        if anchor not in member_set:
            continue
        leaf_w, leaf_h = leaf.width, leaf.height
        ax, ay = anchor.x, anchor.y
        target_y = ay - anchor.height / 2.0 + leaf_h / 2.0

        if anchor in succ[leaf]:
            preferred = "LEFT"
        elif anchor in pred[leaf]:
            preferred = "RIGHT"
        else:
            preferred = "LEFT" if leaf.x < ax else "RIGHT"

        lane_gap = max(90.0, x_gap * 0.62)
        side_x = {
            "LEFT": ax - leaf_w - lane_gap,
            "RIGHT": ax + anchor.width + lane_gap,
        }
        side_order = [preferred, "RIGHT" if preferred == "LEFT" else "LEFT"]

        best = None
        step = max(48.0, leaf_h * 0.55 + y_gap * 0.45)
        offsets = _search_offsets(step, 80)
        for side_index, side in enumerate(side_order):
            x = side_x[side]
            for offset in offsets:
                y = target_y + offset
                box = _box(leaf, x, y)
                if box_intersects_any_padded(box, placed):
                    continue
                score = abs(offset) + side_index * (leaf_h + y_gap) * 3.0
                best = (score, x, y, box)
                break
            if best is not None:
                break

        if best is None:
            x = side_x[preferred]
            y = target_y
            while box_intersects_any_padded(_box(leaf, x, y), placed):
                y -= leaf_h + y_gap
            best = (0.0, x, y, _box(leaf, x, y))

        _score, x, y, box = best
        leaf.x, leaf.y = x, y
        placed.append(box)


def _pull_small_pendant_branches_near_neighbors(
    members, pred, succ, x_gap: float, y_gap: float
) -> None:
    if len(members) < 5:
        return
    member_set = set(members)
    undirected = {node: set() for node in members}
    for node in members:
        for other in pred[node] + succ[node]:
            if other in member_set and other is not node:
                undirected[node].add(other)
                undirected[other].add(node)

    candidates = {
        node
        for node in members
        if not node.branch_exempt and len(undirected[node]) <= 2
    }
    if not candidates:
        return

    seen = set()
    branches = []
    for seed in sorted(candidates, key=lambda n: n.key):
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
    branches.sort(key=lambda item: (item[0].key, len(item[1]), item[1][0].key))
    anchor_slots = defaultdict(int)
    for anchor, comp in branches:
        if any(node in moved_nodes for node in comp):
            continue
        feeds_anchor = any(anchor in succ[node] for node in comp)
        from_anchor = any(anchor in pred[node] for node in comp)
        side = "LEFT" if feeds_anchor or not from_anchor else "RIGHT"
        order = _topo_order(comp, pred, succ)

        anchor_center = anchor.y - anchor.height * 0.5
        heights = [n.height for n in order]
        gap = max(70.0, x_gap * 0.45)
        total_width = sum(n.width for n in order) + max(0, len(order) - 1) * gap
        max_height = max(heights) if heights else 0.0
        lane_gap = max(120.0, x_gap * 0.70)
        start_x = (
            anchor.x - lane_gap - total_width
            if side == "LEFT"
            else anchor.x + anchor.width + lane_gap
        )

        slot = anchor_slots[anchor]
        anchor_slots[anchor] += 1
        base_top = (
            anchor_center + max_height * 0.5 + (slot % 2) * (max_height + y_gap * 0.65)
        )
        if slot >= 2:
            base_top -= (slot // 2) * (max_height + y_gap * 0.85)

        best = None
        placed = _boxes_excluding(members, comp)
        step = max(70.0, max_height * 0.45 + y_gap * 0.35)
        for offset in _search_offsets(step, 80):
            boxes = _row_boxes(order, start_x, base_top + offset, gap)
            if not any(box_intersects_any_padded(box, placed) for box in boxes):
                best = boxes
                break
        if best is None:
            top = base_top
            while True:
                boxes = _row_boxes(order, start_x, top, gap)
                if not any(box_intersects_any_padded(box, placed) for box in boxes):
                    best = boxes
                    break
                top -= max_height + y_gap

        for node, x1, _x2, _y1, y2 in best:
            node.x, node.y = x1, y2
            moved_nodes.add(node)


def _strong_components(members, succ):
    member_set = set(members)
    member_order = {node: index for index, node in enumerate(members)}
    adjacency = {
        node: sorted(
            (nxt for nxt in succ[node] if nxt in member_set), key=member_order.get
        )
        for node in members
    }
    reverse = {node: [] for node in members}
    for node, targets in adjacency.items():
        for target in targets:
            reverse[target].append(node)
    visited = set()
    finish_order = []
    for node in members:
        if node in visited:
            continue
        visited.add(node)
        stack = [(node, 0)]
        while stack:
            current, index = stack[-1]
            targets = adjacency[current]
            if index < len(targets):
                target = targets[index]
                stack[-1] = (current, index + 1)
                if target not in visited:
                    visited.add(target)
                    stack.append((target, 0))
                continue
            finish_order.append(current)
            stack.pop()

    result = []
    assigned = set()
    for node in reversed(finish_order):
        if node in assigned:
            continue
        assigned.add(node)
        group = []
        stack = [node]
        while stack:
            current = stack.pop()
            group.append(current)
            for target in reversed(reverse[current]):
                if target not in assigned:
                    assigned.add(target)
                    stack.append(target)
        result.append(group)
    return result


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


def _barycenter_order_layers(layers, keys, pred, succ) -> None:
    for _ in range(6):
        for key in keys[1:]:
            ref = layers.get(key - 1)
            if not ref:
                continue
            ref_pos = {node: i for i, node in enumerate(ref)}
            layer_order_index = {node: i for i, node in enumerate(layers[key])}

            def predecessor_barycenter(node):
                values = [ref_pos[p] for p in pred[node] if p in ref_pos]
                return (
                    sum(values) / len(values)
                    if values
                    else float(layer_order_index[node])
                )

            layers[key].sort(
                key=lambda n: (predecessor_barycenter(n), layer_order_index[n])
            )
        for key in reversed(keys[:-1]):
            ref = layers.get(key + 1)
            if not ref:
                continue
            ref_pos = {node: i for i, node in enumerate(ref)}
            layer_order_index = {node: i for i, node in enumerate(layers[key])}

            def successor_barycenter(node):
                values = [ref_pos[s] for s in succ[node] if s in ref_pos]
                return (
                    sum(values) / len(values)
                    if values
                    else float(layer_order_index[node])
                )

            layers[key].sort(
                key=lambda n: (successor_barycenter(n), layer_order_index[n])
            )


def _layout_singleton_grid_packed(
    singles, x_gap: float, y_gap: float, y_top: float, per_row: int = 4
) -> None:
    row_y = y_top
    for start in range(0, len(singles), per_row):
        row = singles[start : start + per_row]
        x = 0.0
        row_height = 0.0
        for node in row:
            node.x, node.y = x, row_y
            x += node.width + x_gap
            row_height = max(row_height, node.height)
        row_y -= row_height + y_gap
