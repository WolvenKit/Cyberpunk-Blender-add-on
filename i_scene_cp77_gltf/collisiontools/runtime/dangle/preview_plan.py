def preview_operations(state):
    if state.preview_mode == "SELECTED":
        index = int(state.active_dangle_node)
        if not 0 <= index < len(state.dangle_nodes):
            raise ValueError("Select a Dangle node before starting preview.")
        return (("DANGLE", index, ""),)

    boundary = str(state.evaluation_boundary or "")
    if boundary:
        raise ValueError(
            "Graph preview unavailable: "
            + boundary
            + ". Use Selected Dangle to preview one solver against the Blender pose."
        )
    operations = tuple(
        (
            operation.node_type,
            int(operation.node_index),
            str(operation.source_handle or ""),
        )
        for operation in state.evaluation_order
    )
    if not operations and not state.graph_compiled:
        operations = tuple(
            (kind, index, "")
            for kind, nodes in (
                ("DANGLE", state.dangle_nodes),
                ("DRAG", state.drag_nodes),
            )
            for index in range(len(nodes))
        )
    for kind, index, _handle in operations:
        nodes = state.dangle_nodes if kind == "DANGLE" else state.drag_nodes
        if kind not in {"DANGLE", "DRAG"} or not 0 <= index < len(nodes):
            raise ValueError(
                "Preview operation does not resolve to an imported node; reimport the graph."
            )
    return operations


def executable_node_indices(state):
    operations = preview_operations(state)
    return (
        {index for kind, index, _ in operations if kind == "DANGLE"},
        {index for kind, index, _ in operations if kind == "DRAG"},
    )


def preview_vector_values(state):
    return {str(item.key): tuple(item.value) for item in state.preview_vector_inputs}


def external_force(state, node, linked_runtime=None):
    if state.preview_mode == "SELECTED":
        return state.preview_force_ws
    if node.external_force_linked:
        if linked_runtime is None:
            raise ValueError("Linked external force has no compiled preview runtime")
        return linked_runtime.evaluate(node.source_handle, preview_vector_values(state))
    return node.external_force_ws


def preview_input_errors(state, active_dangles):
    errors = []
    if state.preview_mode == "GRAPH" and state.preview_input_error:
        errors.append("Preview unavailable: " + state.preview_input_error)
    for index in sorted(active_dangles):
        node = state.dangle_nodes[index]
        if node.external_force_preview_error:
            errors.append("Preview unavailable: " + node.external_force_preview_error)
        if node.import_warnings:
            errors.append("Preview unavailable: " + node.import_warnings)
    return errors
