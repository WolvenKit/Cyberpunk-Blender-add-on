from collections import deque


def prepare_strict_left_to_right_graph(node_ids, edges):
    ordered = tuple(dict.fromkeys(node_ids))
    order_index = {node_id: index for index, node_id in enumerate(ordered)}
    known = set(ordered)
    outgoing = {node_id: [] for node_id in ordered}
    indegree = {node_id: 0 for node_id in ordered}
    seen_edges = set()
    for source, target in edges:
        if source not in known or target not in known or source == target:
            continue
        edge = (source, target)
        if edge in seen_edges:
            continue
        seen_edges.add(edge)
        outgoing[source].append(target)
        indegree[target] += 1

    for targets in outgoing.values():
        targets.sort(key=order_index.__getitem__)

    ready = deque(node_id for node_id in ordered if indegree[node_id] == 0)
    topological = []
    while ready:
        node_id = ready.popleft()
        topological.append(node_id)
        for target in outgoing[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)

    topological_set = set(topological)
    cyclic = tuple(node_id for node_id in ordered if node_id not in topological_set)
    return ordered, outgoing, tuple(topological), topological_set, cyclic


def strict_left_to_right_columns_prepared(prepared, minimum_columns=None):
    ordered, outgoing, topological, topological_set, cyclic = prepared
    minimum_columns = minimum_columns or {}
    columns = {
        node_id: max(0, int(minimum_columns.get(node_id, 0))) for node_id in ordered
    }
    for source in topological:
        source_column = columns[source]
        for target in outgoing[source]:
            if target in topological_set:
                columns[target] = max(
                    columns[target],
                    source_column + 1,
                    int(minimum_columns.get(target, 0)),
                )

    if cyclic:
        acyclic_max = max(
            (columns[node_id] for node_id in topological),
            default=0,
        )
        for offset, node_id in enumerate(cyclic):
            columns[node_id] = max(
                columns[node_id],
                acyclic_max + 1 + offset,
            )

    return columns, cyclic


def strict_left_to_right_columns(node_ids, edges, minimum_columns=None):
    """Return deterministic longest-path columns for a directed graph, and the nodes on cycles separately"""
    prepared = prepare_strict_left_to_right_graph(node_ids, edges)
    return strict_left_to_right_columns_prepared(prepared, minimum_columns)
