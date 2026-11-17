import time
from collections import defaultdict

from ...bartmoss.dag import (
    prepare_strict_left_to_right_graph,
    strict_left_to_right_columns_prepared,
)
from ...blender.identity import rna_identity
from .nodes import create_node


def add_bundle_items(node, items):
    for socket_type, name in items:
        node.bundle_items.new(socket_type=socket_type, name=name)
    return node


def combine_bundle_node(tree, items, location, *, name, label=None):
    node = create_node(
        tree.nodes, "NodeCombineBundle", location, hide=False, label=label or name
    )
    node.name = name
    add_bundle_items(node, items)
    return node


def separate_bundle_node(tree, items, location, *, name, label=None):
    node = create_node(
        tree.nodes, "NodeSeparateBundle", location, hide=False, label=label or name
    )
    node.name = name
    if items:
        add_bundle_items(node, items)
    return node


_SURFACE_BUNDLE_CHANNELS = (
    ("Base Color", "RGBA"),
    ("Metallic", "FLOAT"),
    ("Roughness", "FLOAT"),
    ("IOR", "FLOAT"),
    ("Alpha", "FLOAT"),
    ("Normal", "VECTOR"),
    ("Emission Color", "RGBA"),
    ("Emission", "RGBA"),
    ("Emission Strength", "FLOAT"),
)


def bundle_principled_surface_links(material, *, minimum_channels=3):
    tree = getattr(material, "node_tree", None)
    if tree is None:
        return {"bundled": 0, "channels": 0, "timings": {}}

    timings = {
        "bundle_scan": 0.0,
        "bundle_nodes": 0.0,
        "bundle_items": 0.0,
        "bundle_sync": 0.0,
        "bundle_sync_fallback": 0.0,
        "bundle_rewire": 0.0,
        "bundle_rewire_pack": 0.0,
        "bundle_rewire_replace": 0.0,
    }
    phase_started = time.perf_counter()
    principled_nodes = []
    for node in tree.nodes:
        if bool(node.get("cp77_surface_bundle_boundary", False)):
            timings["bundle_scan"] += time.perf_counter() - phase_started
            return {"bundled": 0, "channels": 0, "timings": timings}
        if node.bl_idname == "ShaderNodeBsdfPrincipled" and node.parent is None:
            principled_nodes.append(node)
    timings["bundle_scan"] += time.perf_counter() - phase_started

    bundled = 0
    channel_total = 0
    for bsdf in principled_nodes:
        phase_started = time.perf_counter()
        channels = []
        seen_names = set()
        for socket_name, bundle_type in _SURFACE_BUNDLE_CHANNELS:
            if socket_name in seen_names:
                continue
            socket = (
                bsdf.inputs.get(socket_name) if hasattr(bsdf.inputs, "get") else None
            )
            if socket is None or not getattr(socket, "is_linked", False):
                continue
            links = getattr(socket, "links", ()) or ()
            if len(links) != 1:
                continue
            link = links[0]
            channels.append(
                (
                    socket_name,
                    bundle_type,
                    link.from_socket,
                    socket,
                    link.from_node,
                    link,
                )
            )
            seen_names.add(socket_name)
        timings["bundle_scan"] += time.perf_counter() - phase_started

        if len(channels) < int(minimum_channels):
            continue

        source_nodes = {id(item[4]): item[4] for item in channels}
        if len(source_nodes) == 1:
            only_source = next(iter(source_nodes.values()))
            if getattr(only_source, "bl_idname", "") == "NodeSeparateBundle":
                continue

        items = tuple(
            (bundle_type, socket_name) for socket_name, bundle_type, *_ in channels
        )

        phase_started = time.perf_counter()
        combine = combine_bundle_node(
            tree,
            (),
            (-240.0, 0.0),
            name=f"CP77 Surface Combine {bundled + 1}",
            label="Surface Pack",
        )
        separate = separate_bundle_node(
            tree,
            (),
            (160.0, 0.0),
            name=f"CP77 Surface Separate {bundled + 1}",
            label="Surface Unpack",
        )
        timings["bundle_nodes"] += time.perf_counter() - phase_started

        phase_started = time.perf_counter()
        add_bundle_items(combine, items)
        timings["bundle_items"] += time.perf_counter() - phase_started

        combine["cp77_surface_bundle_boundary"] = True
        separate["cp77_surface_bundle_boundary"] = True

        phase_started = time.perf_counter()
        tree.links.new(combine.outputs["Bundle"], separate.inputs["Bundle"])
        expected_names = tuple(
            socket_name for socket_name, _bundle_type, *_ in channels
        )
        outputs_ready = all(
            separate.outputs.get(name) is not None for name in expected_names
        )
        timings["bundle_sync"] += time.perf_counter() - phase_started

        if not outputs_ready:
            phase_started = time.perf_counter()
            try:
                separate.bundle_items.clear()
            except RuntimeError:
                pass
            add_bundle_items(separate, items)
            timings["bundle_sync_fallback"] += time.perf_counter() - phase_started

        rewire_started = time.perf_counter()
        phase_started = rewire_started
        for (
            socket_name,
            _bundle_type,
            source_socket,
            _target_socket,
            _source_node,
            _link,
        ) in channels:
            tree.links.new(source_socket, combine.inputs[socket_name])
        timings["bundle_rewire_pack"] += time.perf_counter() - phase_started

        phase_started = time.perf_counter()
        for (
            socket_name,
            _bundle_type,
            _source_socket,
            target_socket,
            _source_node,
            link,
        ) in channels:
            separate_socket = separate.outputs[socket_name]
            if getattr(target_socket, "is_multi_input", False):
                tree.links.remove(link)
                tree.links.new(separate_socket, target_socket)
            else:
                tree.links.new(separate_socket, target_socket, verify_limits=True)
        timings["bundle_rewire_replace"] += time.perf_counter() - phase_started
        timings["bundle_rewire"] += time.perf_counter() - rewire_started
        bundled += 1
        channel_total += len(channels)

    return {"bundled": bundled, "channels": channel_total, "timings": timings}


_LAYOUT_VERSION = 3


_LAYOUT_COLUMN_GAP = 140.0


_LAYOUT_ROW_GAP = 70.0


_LAYOUT_MIN_ROW_STEP = 180.0


_LAYOUT_MATERIAL_RIGHT_EDGE = 640.0


_LAYOUT_GROUP_RIGHT_EDGE = 0.0


_SOURCE_NODE_TYPES = frozenset(
    {
        "NodeGroupInput",
        "ShaderNodeTexCoord",
        "ShaderNodeUVMap",
        "ShaderNodeAttribute",
        "ShaderNodeVertexColor",
        "ShaderNodeRGB",
        "ShaderNodeValue",
        "ShaderNodeGeometry",
        "ShaderNodeCameraData",
        "ShaderNodeObjectInfo",
        "ShaderNodeLayerWeight",
        "ShaderNodeLightPath",
        "ShaderNodeFresnel",
    }
)


_COORDINATE_NODE_TYPES = frozenset(
    {
        "ShaderNodeMapping",
        "ShaderNodeVectorRotate",
        "ShaderNodeVectorTransform",
        "ShaderNodeTangent",
    }
)


_TEXTURE_NODE_TYPES = frozenset(
    {
        "ShaderNodeTexImage",
        "ShaderNodeTexNoise",
        "ShaderNodeTexVoronoi",
        "ShaderNodeTexWave",
        "ShaderNodeTexWhiteNoise",
        "ShaderNodeTexGradient",
        "ShaderNodeTexMagic",
        "ShaderNodeTexChecker",
        "ShaderNodeTexEnvironment",
    }
)


_SURFACE_NODE_TYPES = frozenset(
    {
        "ShaderNodeBsdfPrincipled",
        "ShaderNodeBsdfTransparent",
        "ShaderNodeBsdfGlass",
        "ShaderNodeBsdfRefraction",
        "ShaderNodeEmission",
        "ShaderNodeMixShader",
        "ShaderNodeAddShader",
        "ShaderNodeVolumePrincipled",
        "ShaderNodeDisplacement",
    }
)


_OUTPUT_NODE_TYPES = frozenset(
    {
        "ShaderNodeOutputMaterial",
        "NodeGroupOutput",
    }
)


def _absolute_location(node):
    x = float(node.location.x)
    y = float(node.location.y)
    parent = getattr(node, "parent", None)
    seen = set()
    while parent is not None:
        pointer = rna_identity(parent)
        if pointer in seen:
            break
        seen.add(pointer)
        x += float(parent.location.x)
        y += float(parent.location.y)
        parent = getattr(parent, "parent", None)
    return (x, y)


def _set_absolute_location(node, location):
    x, y = float(location[0]), float(location[1])
    parent = getattr(node, "parent", None)
    if parent is not None:
        parent_x, parent_y = _absolute_location(parent)
        x -= parent_x
        y -= parent_y
    node.location = (x, y)


def set_absolute_locations(tree, targets):
    """Move nodes of tree to absolute locations"""
    if not targets:
        return False
    nodes = tree.nodes
    all_nodes = tuple(nodes)
    if not any(
        node.type == "FRAME" for node in all_nodes
    ) and _bulk_set_absolute_locations(nodes, all_nodes, targets):
        return True
    by_pointer = {rna_identity(node): node for node in all_nodes}
    for pointer, target in targets.items():
        _set_absolute_location(by_pointer[pointer], target)
    return False


def _bulk_set_absolute_locations(nodes, all_nodes, targets):
    values = [0.0] * (len(all_nodes) * 2)
    try:
        nodes.foreach_get("location", values)
    except (RuntimeError, ValueError):
        return False

    parent_locations = {}
    for index, node in enumerate(all_nodes):
        pointer = rna_identity(node)
        target = targets.get(pointer)
        if target is None:
            continue
        x, y = float(target[0]), float(target[1])
        parent = getattr(node, "parent", None)
        if parent is not None:
            parent_pointer = rna_identity(parent)
            parent_location = parent_locations.get(parent_pointer)
            if parent_location is None:
                parent_location = _absolute_location(parent)
                parent_locations[parent_pointer] = parent_location
            x -= parent_location[0]
            y -= parent_location[1]
        offset = index * 2
        values[offset] = x
        values[offset + 1] = y

    try:
        nodes.foreach_set("location", values)
        return True
    except (RuntimeError, ValueError):
        return False


def _layout_stage(node):
    node_type = str(getattr(node, "bl_idname", ""))
    if node_type in _OUTPUT_NODE_TYPES:
        return "Output"
    if node_type in _SURFACE_NODE_TYPES:
        return "Surface"
    if node_type in _SOURCE_NODE_TYPES:
        return "Inputs"
    if node_type in _TEXTURE_NODE_TYPES:
        return "Textures"
    if node_type in _COORDINATE_NODE_TYPES:
        return "Coordinates"
    return "Processing"


def _node_height(node):
    try:
        value = float(node.height)
    except (ReferenceError, RuntimeError, ValueError):
        value = 0.0
    if getattr(node, "bl_idname", "") in {
        "ShaderNodeGroup",
        "NodeGroupInput",
        "NodeGroupOutput",
    }:
        rows = 0
        for is_input, collection in ((True, node.inputs), (False, node.outputs)):
            for socket in collection:
                if getattr(socket, "hide", False) or getattr(
                    socket, "is_unavailable", False
                ):
                    continue
                rows += 1
                if (
                    is_input
                    and getattr(socket, "type", "") == "VECTOR"
                    and not getattr(socket, "is_linked", False)
                    and not getattr(socket, "hide_value", False)
                ):
                    rows += 3
        value = max(value, 80.0 + 24.0 * rows)
    return max(_LAYOUT_MIN_ROW_STEP - _LAYOUT_ROW_GAP, value)


def _node_width(node):
    try:
        value = float(node.width)
    except (ReferenceError, RuntimeError, ValueError):
        value = 140.0
    return max(100.0, value)


def _semantic_minimum_columns(pointers, base_columns, stages):
    non_surface = [
        base_columns[pointer]
        for pointer in pointers
        if stages[pointer] not in {"Surface", "Output"}
    ]
    surface_floor = max(non_surface, default=0) + 1
    surface_columns = [
        max(base_columns[pointer], surface_floor)
        for pointer in pointers
        if stages[pointer] == "Surface"
    ]
    output_floor = max(surface_columns or non_surface or [0]) + 1
    minimum = {}
    for pointer in pointers:
        stage = stages[pointer]
        if stage == "Surface":
            minimum[pointer] = surface_floor
        elif stage == "Output":
            minimum[pointer] = output_floor
    return minimum


def _tree_links(tree, node_pointers):
    edges = []
    for link in tree.links:
        source = rna_identity(link.from_node)
        target = rna_identity(link.to_node)
        if source in node_pointers and target in node_pointers:
            edges.append((source, target))
    return tuple(edges)


def _layout_node_tree(tree, *, right_edge, recursive, visited, timings):
    tree_pointer = rna_identity(tree)
    if tree_pointer in visited:
        return {"nodes": 0, "links": 0, "cycles": 0, "backward_links": 0}
    visited.add(tree_pointer)
    if right_edge == _LAYOUT_GROUP_RIGHT_EDGE:
        try:
            if int(tree.get("cp77_graph_layout_version", 0)) == _LAYOUT_VERSION:
                return {
                    "nodes": len(tree.nodes),
                    "links": len(tree.links),
                    "cycles": 0,
                    "backward_links": 0,
                }
        except (ReferenceError, RuntimeError, ValueError):
            pass

    nodes = [
        node for node in tree.nodes if node.type != "FRAME" and node.parent is None
    ]
    if not nodes:
        return {"nodes": 0, "links": 0, "cycles": 0, "backward_links": 0}

    if recursive:
        for node in nodes:
            if node.bl_idname != "ShaderNodeGroup":
                continue
            group = getattr(node, "node_tree", None)
            if (
                group is None
                or group is tree
                or getattr(group, "library", None) is not None
            ):
                continue
            _layout_node_tree(
                group,
                right_edge=_LAYOUT_GROUP_RIGHT_EDGE,
                recursive=True,
                visited=visited,
                timings=timings,
            )

    phase_started = time.perf_counter()
    pointers = tuple(rna_identity(node) for node in nodes)
    by_pointer = dict(zip(pointers, nodes))
    pointer_set = set(pointers)
    stages = {pointer: _layout_stage(node) for pointer, node in by_pointer.items()}
    edges = _tree_links(tree, pointer_set)
    prepared_graph = prepare_strict_left_to_right_graph(pointers, edges)
    base_columns, base_cycles = strict_left_to_right_columns_prepared(prepared_graph)
    minimum = _semantic_minimum_columns(pointers, base_columns, stages)
    columns, cycles = strict_left_to_right_columns_prepared(prepared_graph, minimum)
    if base_cycles and not cycles:
        cycles = base_cycles

    predecessors = {pointer: [] for pointer in pointers}
    for source, target in edges:
        predecessors[target].append(source)
    by_column = {}
    for pointer, column in columns.items():
        by_column.setdefault(column, []).append(pointer)
    timings["topology"] += time.perf_counter() - phase_started

    placement_started = time.perf_counter()
    phase_started = placement_started
    original_locations = {
        pointer: _absolute_location(node) for pointer, node in by_pointer.items()
    }
    for node in by_pointer.values():
        try:
            if node.hide:
                node.hide = False
        except (ReferenceError, RuntimeError):
            pass
    dimensions = {
        pointer: (_node_width(node), _node_height(node))
        for pointer, node in by_pointer.items()
    }
    sort_names = {
        pointer: (
            str(node.label or node.name).casefold(),
            str(node.name).casefold(),
        )
        for pointer, node in by_pointer.items()
    }
    placed_y = {}
    target_locations = {}
    placement_order = []
    column_x = {}
    ordered_columns = sorted(by_column)
    cursor = 0.0
    for column in ordered_columns:
        column_x[column] = cursor
        width = max(dimensions[pointer][0] for pointer in by_column[column])
        cursor += width + _LAYOUT_COLUMN_GAP
    if column_x:
        rightmost = column_x[max(column_x)]
        shift = float(right_edge) - rightmost
        for column in column_x:
            column_x[column] += shift

    for column in ordered_columns:
        column_nodes = by_column[column]

        def row_order(pointer):
            upstream = [
                placed_y[source]
                for source in predecessors[pointer]
                if source in placed_y
            ]
            center = (
                sum(upstream) / len(upstream)
                if upstream
                else original_locations[pointer][1]
            )
            return (
                -center,
                -original_locations[pointer][1],
                sort_names[pointer][0],
                sort_names[pointer][1],
            )

        column_nodes.sort(key=row_order)
        y = 720.0
        for pointer in column_nodes:
            placed_y[pointer] = y
            target_locations[pointer] = (column_x[column], y)
            placement_order.append(pointer)
            y -= dimensions[pointer][1] + _LAYOUT_ROW_GAP
    timings["placement_prepare"] += time.perf_counter() - phase_started

    phase_started = time.perf_counter()
    changed_targets = {
        pointer: target_locations[pointer]
        for pointer in placement_order
        if original_locations[pointer] != target_locations[pointer]
    }
    if set_absolute_locations(tree, changed_targets):
        elapsed = time.perf_counter() - phase_started
        timings["placement_write"] += elapsed
        timings["placement_write_bulk"] += elapsed
    else:
        elapsed = time.perf_counter() - phase_started
        timings["placement_write"] += elapsed
        timings["placement_write_scalar"] += elapsed
    timings["placement"] += time.perf_counter() - placement_started

    phase_started = time.perf_counter()
    backward = 0
    cycle_set = set(cycles)
    for source, target in edges:
        if source in cycle_set or target in cycle_set:
            continue
        if columns[target] <= columns[source]:
            backward += 1

    try:
        tree["cp77_graph_layout_version"] = _LAYOUT_VERSION
    except (ReferenceError, RuntimeError):
        pass
    timings["metadata"] += time.perf_counter() - phase_started
    return {
        "nodes": len(nodes),
        "links": len(edges),
        "cycles": len(cycles),
        "backward_links": int(backward),
    }


def organize_material_groups(material):
    """Lay out the node groups a material's tree uses that are not laid out yet"""
    tree = getattr(material, "node_tree", None)
    if tree is None:
        return
    timings = defaultdict(float)
    visited = {rna_identity(tree)}
    for node in tree.nodes:
        if (
            node.type == "FRAME"
            or node.parent is not None
            or node.bl_idname != "ShaderNodeGroup"
        ):
            continue
        group = getattr(node, "node_tree", None)
        if (
            group is None
            or group is tree
            or getattr(group, "library", None) is not None
        ):
            continue
        _layout_node_tree(
            group,
            right_edge=_LAYOUT_GROUP_RIGHT_EDGE,
            recursive=True,
            visited=visited,
            timings=timings,
        )


def organize_material_graph(material, *, bundled=None):
    """Bundle the principled surface links and lay the graph out"""
    tree = getattr(material, "node_tree", None)
    if tree is None or not len(tree.nodes):
        return {"nodes": 0, "links": 0, "cycles": 0, "backward_links": 0}
    timings = {
        "bundle": 0.0,
        "bundle_scan": 0.0,
        "bundle_nodes": 0.0,
        "bundle_items": 0.0,
        "bundle_sync": 0.0,
        "bundle_sync_fallback": 0.0,
        "bundle_rewire": 0.0,
        "bundle_rewire_pack": 0.0,
        "bundle_rewire_replace": 0.0,
        "topology": 0.0,
        "placement": 0.0,
        "placement_prepare": 0.0,
        "placement_write": 0.0,
        "placement_write_bulk": 0.0,
        "placement_write_scalar": 0.0,
        "metadata": 0.0,
    }
    if bundled is None:
        phase_started = time.perf_counter()
        bundle_stats = bundle_principled_surface_links(material)
        timings["bundle"] += time.perf_counter() - phase_started
    else:
        bundle_stats = bundled
        timings["bundle"] += float(bundled.get("seconds", 0.0))
    for name, seconds in bundle_stats.get("timings", {}).items():
        if name in timings:
            timings[name] += max(0.0, float(seconds))
    stats = _layout_node_tree(
        tree,
        right_edge=_LAYOUT_MATERIAL_RIGHT_EDGE,
        recursive=True,
        visited=set(),
        timings=timings,
    )
    stats["surface_bundles"] = int(bundle_stats.get("bundled", 0))
    stats["surface_bundle_channels"] = int(bundle_stats.get("channels", 0))
    stats["timings"] = timings
    try:
        material["cp77_graph_layout_version"] = _LAYOUT_VERSION
    except (ReferenceError, RuntimeError):
        pass
    return stats
