from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any

import bpy

from ...animation.model.dangle.editor import (
    bone_name,
    clean_name,
    constraint_bones,
    constraint_edge_labels,
    constraint_summary,
    particle_components,
    particle_sort_key,
    payload_data,
    strand_and_index,
    strand_sort_key,
)
from ...core.log import get_logger
from .categories import NODE_CATEGORY_COLORS
from .property_codec import add_node_property, clear_node_properties
from .sockets import bind_red_socket
from .tree_ops import link_sockets, new_editor_node, new_graph_tree, new_socket

_LOG = get_logger(__name__)


EDITOR_SOCKET = "REDengine_AnimGraphSocket_Editor"


def _editor_tree(
    root_tree: bpy.types.NodeTree, name: str, *, parent_handle: str, kind: str
) -> bpy.types.NodeTree:
    tree = bpy.data.node_groups.get(name)
    if tree is None:
        tree = new_graph_tree(name)
    tree["red_internal_subgraph"] = True
    tree["red_editor_subgraph"] = True
    tree["red_public_tree"] = False
    tree["red_parent_graph"] = root_tree.name
    tree["red_parent_dangle_handle"] = str(parent_handle or "")
    tree["red_editor_subgraph_kind"] = kind
    try:
        tree.use_fake_user = False
    except Exception:
        _LOG.debug("Dangle projection operation failed", exc_info=True)
    try:
        tree.nodes.clear()
    except Exception:
        _LOG.debug("Dangle projection operation failed", exc_info=True)
        for node in list(tree.nodes):
            tree.nodes.remove(node)
    return tree


def _new_editor_node(
    tree: bpy.types.NodeTree,
    *,
    node_type: str,
    handle: str,
    label: str,
    color_key: str = "Editor",
) -> bpy.types.Node:
    return new_editor_node(
        tree,
        red_type=node_type,
        handle=handle,
        label=label,
        color=NODE_CATEGORY_COLORS.get(
            color_key, NODE_CATEGORY_COLORS.get("Other", (0.30, 0.30, 0.30))
        ),
        output_kind="editor",
        notes="editor-only dangle projection node",
    )


def _add_editor_output(
    node: bpy.types.Node,
    name: str,
    *,
    handle: str,
    semantics: str,
    link_type: str = "editorObject",
) -> bpy.types.NodeSocket:
    sock = new_socket(node, "OUTPUT", EDITOR_SOCKET, name)
    return bind_red_socket(
        sock,
        role="output",
        owner_handle=handle,
        link_type=link_type,
        exportable=False,
        edge_semantics=semantics,
        pseudo=True,
    )


def _add_editor_input(
    node: bpy.types.Node,
    name: str,
    *,
    handle: str,
    field: str,
    semantics: str,
    link_type: str = "editorObject",
) -> bpy.types.NodeSocket:
    sock = new_socket(node, "INPUT", EDITOR_SOCKET, name)
    return bind_red_socket(
        sock,
        role="input",
        owner_handle=handle,
        field_name=field,
        json_path=field,
        link_type=link_type,
        exportable=False,
        edge_semantics=semantics,
        pseudo=True,
    )


def _link(
    tree: bpy.types.NodeTree,
    out_sock: bpy.types.NodeSocket,
    in_sock: bpy.types.NodeSocket,
) -> None:
    try:
        link_sockets(tree, out_sock, in_sock)
    except Exception:
        _LOG.debug("Dangle projection operation failed", exc_info=True)


def _set_editor_extra(owner, **values: Any) -> None:
    for key, value in values.items():
        try:
            owner[key] = value
        except Exception:
            try:
                setattr(owner, key, value)
            except Exception:
                _LOG.debug(
                    "Cannot set dangle editor property %s on %s",
                    key,
                    getattr(owner, "name", type(owner).__name__),
                    exc_info=True,
                )


def _add_payload_properties(
    node: bpy.types.Node, payload: dict, *, skip: Iterable[str] = ()
) -> None:
    clear_node_properties(node)
    skip_set = {"$type", *skip}
    for key, value in payload.items():
        if key in skip_set:
            continue
        add_node_property(node, key, value, json_path=key)


def _add_particle_properties(
    node: bpy.types.Node,
    payload: dict,
    *,
    bone: str,
    strand: str,
    strand_index: int,
    source_index: int,
) -> None:
    clear_node_properties(node)
    add_node_property(
        node, "bone", bone, json_path="bone.name", label="Bone", editable=False
    )
    add_node_property(
        node,
        "strand",
        strand,
        json_path="editor.strand",
        label="Strand",
        editable=False,
    )
    add_node_property(
        node,
        "strandIndex",
        strand_index,
        json_path="editor.strandIndex",
        label="Strand Index",
        editable=False,
    )
    add_node_property(
        node,
        "sourceIndex",
        source_index,
        json_path="particlesContainer.particles.index",
        label="Source Index",
        editable=False,
    )

    preferred = [
        "isFree",
        "mass",
        "damping",
        "pullForceFactor",
        "projectionType",
        "collisionCapsuleRadius",
        "collisionCapsuleHeightExtent",
        "collisionCapsuleAxisLS",
        "isDebugEnabled",
    ]
    used = {"$type", "bone"}
    for key in preferred:
        if key in payload:
            add_node_property(
                node,
                key,
                payload[key],
                json_path=f"particlesContainer.particles[{source_index}].{key}",
            )
            used.add(key)
    for key, value in payload.items():
        if key in used:
            continue
        add_node_property(
            node,
            key,
            value,
            json_path=f"particlesContainer.particles[{source_index}].{key}",
        )


def _estimate_editor_node_size(node: bpy.types.Node) -> tuple[float, float]:
    red_type = getattr(node, "red_type", "") or ""
    props = getattr(node, "red_properties", None)
    try:
        prop_count = len(props) if props is not None else 0
    except Exception:
        _LOG.debug("Dangle projection operation failed", exc_info=True)
        prop_count = 0
    if red_type == "editorDangleParticle":
        width = 285.0
        height = max(245.0, 112.0 + 24.0 * prop_count)
    elif red_type == "editorDangleConeConstraint":
        width = 360.0
        height = max(250.0, 120.0 + 24.0 * prop_count)
    elif red_type == "editorRoundedShape":
        width = 310.0
        height = max(260.0, 120.0 + 24.0 * prop_count)
    elif red_type == "editorRoundedShapeCollector":
        width = 300.0
        height = max(160.0, 95.0 + 22.0 * prop_count)
    else:
        width = 280.0
        height = max(180.0, 95.0 + 22.0 * prop_count)
    try:
        node.width = max(float(getattr(node, "width", 0.0) or 0.0), width)
    except Exception:
        _LOG.debug("Dangle projection operation failed", exc_info=True)
    return width, height


def _layout_particles(
    nodes_by_bone: dict[str, bpy.types.Node],
    order: list[str],
    link_edges: list[tuple[str, str]],
    cone_nodes: list[tuple[bpy.types.Node, str, str, int]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Lay out dangle particles deterministically by strand and depth"""
    if not nodes_by_bone:
        return {}

    groups: dict[str, list[str]] = defaultdict(list)
    source_order = {name: i for i, name in enumerate(order)}
    for bone in nodes_by_bone:
        strand, _idx = strand_and_index(bone, source_order.get(bone, 0))
        groups[strand].append(bone)

    components = particle_components(nodes_by_bone.keys(), link_edges)
    comp_index = {bone: ci for ci, comp in enumerate(components) for bone in comp}

    cone_counts: Counter = Counter()
    for _cone, bone_a, bone_b, _index in cone_nodes or []:
        strand_a, _ = strand_and_index(bone_a, source_order.get(bone_a, 0))
        strand_b, _ = strand_and_index(bone_b, source_order.get(bone_b, 0))
        strand = strand_a or strand_b or "<unassigned>"
        cone_counts[strand] += 1

    sorted_strands = sorted(
        groups.keys(),
        key=lambda strand: (
            min((comp_index.get(b, 10**6) for b in groups[strand]), default=10**6),
            strand_sort_key(strand),
            strand,
        ),
    )

    x_spacing = 520.0
    base_band_gap = 190.0
    cone_lane_height = 390.0
    layout: dict[str, dict[str, Any]] = {}
    row_bands: dict[int, dict[str, Any]] = {}
    y = 0.0
    last_component = None

    for row_index, strand in enumerate(sorted_strands):
        bones = groups[strand]
        bones.sort(key=lambda b: particle_sort_key(b, source_order.get(b, 0)))
        comps = {comp_index.get(b, -1) for b in bones}
        comp = min(comps) if comps else -1
        if last_component is not None and comp != last_component:
            y -= 260.0
        last_component = comp

        numeric = [strand_and_index(b, source_order.get(b, 0))[1] for b in bones]
        numeric = [n for n in numeric if n >= 0]
        min_idx = min(numeric) if numeric else 0
        max_particle_height = 0.0
        x_values: list[float] = []

        for pos, bone in enumerate(bones):
            node = nodes_by_bone.get(bone)
            if node is None:
                continue
            _strand, idx = strand_and_index(bone, source_order.get(bone, pos))
            x_pos = (idx - min_idx) * x_spacing if idx >= 0 else pos * x_spacing
            node.location = (x_pos, y)
            width, height = _estimate_editor_node_size(node)
            max_particle_height = max(max_particle_height, height)
            x_values.append(x_pos)
            layout[bone] = {
                "strand": strand,
                "row": row_index,
                "x": x_pos,
                "y": y,
                "width": width,
                "height": height,
                "center_y": y - height * 0.5,
            }

        lanes = max(1, int(cone_counts.get(strand, 0)))
        row_bands[row_index] = {
            "strand": strand,
            "top": y,
            "particle_height": max_particle_height or 260.0,
            "cone_lanes": lanes,
            "x_min": min(x_values) if x_values else 0.0,
            "x_max": max(x_values) if x_values else 0.0,
        }

        y -= (max_particle_height or 260.0) + base_band_gap + lanes * cone_lane_height

    layout["__rows__"] = row_bands  # type: ignore[assignment]
    return layout


def _layout_cone_constraints(
    cone_nodes: list[tuple[bpy.types.Node, str, str, int]],
    particle_nodes: dict[str, bpy.types.Node],
    particle_layout: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Place cone constraints in reserved lanes next to their particles"""
    if not cone_nodes:
        return
    particle_layout = particle_layout or {}
    row_bands = (
        particle_layout.get("__rows__", {}) if isinstance(particle_layout, dict) else {}
    )

    def row_for(bone: str) -> int:
        info = (
            particle_layout.get(bone, {}) if isinstance(particle_layout, dict) else {}
        )
        try:
            return int(info.get("row", 999999))
        except Exception:
            _LOG.debug("Dangle projection operation failed", exc_info=True)
            return 999999

    def cone_sort(item: tuple[bpy.types.Node, str, str, int]):
        _node, bone_a, bone_b, index = item
        ra = row_for(bone_a)
        rb = row_for(bone_b)
        row = min(ra, rb)
        la = (
            particle_layout.get(bone_a, {}) if isinstance(particle_layout, dict) else {}
        )
        strand = str(la.get("strand") or "")
        return (row, strand_sort_key(strand), index)

    lane_counts: Counter = Counter()
    cross_counts: Counter = Counter()
    for cone_node, bone_a, bone_b, index in sorted(cone_nodes, key=cone_sort):
        cone_w, cone_h = _estimate_editor_node_size(cone_node)
        node_a = particle_nodes.get(bone_a)
        node_b = particle_nodes.get(bone_b)
        ra = row_for(bone_a)
        rb = row_for(bone_b)
        row = ra if ra != 999999 else rb

        if node_a is not None and node_b is not None:
            ax, ay = float(node_a.location.x), float(node_a.location.y)
            bx, by = float(node_b.location.x), float(node_b.location.y)
        elif node_a is not None:
            ax = bx = float(node_a.location.x)
            ay = by = float(node_a.location.y)
        elif node_b is not None:
            ax = bx = float(node_b.location.x)
            ay = by = float(node_b.location.y)
        else:
            ax = bx = 0.0
            ay = by = -index * 420.0

        same_row = ra == rb and ra != 999999
        if same_row:
            row_meta = row_bands.get(row, {}) if isinstance(row_bands, dict) else {}
            particle_top = float(row_meta.get("top", max(ay, by)))
            particle_height = float(row_meta.get("particle_height", 300.0))
            slot_key = ("row", row)
            slot = lane_counts[slot_key]
            lane_counts[slot_key] += 1
            x = (ax + bx) * 0.5 + 70.0
            y = particle_top - particle_height - 120.0 - slot * (cone_h + 120.0)
        else:
            slot_key = ("cross", min(ra, rb), max(ra, rb))
            slot = cross_counts[slot_key]
            cross_counts[slot_key] += 1
            x = max(ax, bx) + 620.0 + slot * 90.0
            center_y = ((ay + by) * 0.5) - cone_h * 0.25
            y = center_y + cone_h * 0.5

        cone_node.location = (x, y)


def _layout_shapes(
    shape_nodes: list[bpy.types.Node], collector: bpy.types.Node
) -> None:
    if not shape_nodes:
        collector.location = (520, 0)
        return
    for index, node in enumerate(shape_nodes):
        node.location = (0, -index * 230)
        node.width = 280
    collector.location = (560, -(len(shape_nodes) - 1) * 115)
    collector.width = 260


def create_dangle_editor_subgraphs(
    root_tree: bpy.types.NodeTree,
    dangle_node: bpy.types.Node,
    dangle_handle: str,
    dangle_constraint_wrapper: Any,
) -> tuple[int, int, int]:
    """Create editor-only dangle subgraphs for readable constraint editing"""
    payload = payload_data(dangle_constraint_wrapper)
    if not isinstance(payload, dict):
        return (0, 0, 0)

    root_safe = clean_name(root_tree.name)
    base = f".{root_safe}_Dangle_{clean_name(dangle_handle)}"
    particle_tree = _editor_tree(
        root_tree,
        f"{base}_ParticlesAndConstraints",
        parent_handle=dangle_handle,
        kind="particles_constraints",
    )
    shape_tree = _editor_tree(
        root_tree,
        f"{base}_CollisionRoundedShapes",
        parent_handle=dangle_handle,
        kind="collision_rounded_shapes",
    )

    try:
        dangle_node.red_editor_subgraph_a_name = particle_tree.name
        dangle_node.red_editor_subgraph_a_label = "Particles / Constraints"
        dangle_node.red_editor_subgraph_b_name = shape_tree.name
        dangle_node.red_editor_subgraph_b_label = "Collision Rounded Shapes"
    except Exception:
        _LOG.debug("Dangle projection operation failed", exc_info=True)
        try:
            dangle_node["red_editor_subgraph_a_name"] = particle_tree.name
            dangle_node["red_editor_subgraph_a_label"] = "Particles / Constraints"
            dangle_node["red_editor_subgraph_b_name"] = shape_tree.name
            dangle_node["red_editor_subgraph_b_label"] = "Collision Rounded Shapes"
        except Exception:
            _LOG.debug("Dangle projection operation failed", exc_info=True)

    particles_container = (
        payload.get("particlesContainer") if isinstance(payload, dict) else None
    )
    particles = (
        particles_container.get("particles")
        if isinstance(particles_container, dict)
        else []
    )
    if not isinstance(particles, list):
        particles = []

    particle_nodes: dict[str, bpy.types.Node] = {}
    particle_order: list[str] = []
    particle_source_payloads: dict[str, tuple[dict, int]] = {}

    def ensure_particle_node(
        bone: str, source_payload: dict | None = None, index: int = -1
    ) -> bpy.types.Node:
        nonlocal particle_nodes, particle_order
        bone = bone or f"Particle {len(particle_nodes)}"
        if bone in particle_nodes:
            return particle_nodes[bone]
        handle_index = index if index >= 0 else len(particle_nodes)
        strand, strand_index = strand_and_index(bone, handle_index)
        handle = (
            f"editorDangleParticle_{dangle_handle}_{handle_index}_{clean_name(bone)}"
        )
        label_idx = f" #{strand_index}" if strand_index >= 0 else ""
        node = _new_editor_node(
            particle_tree,
            node_type="editorDangleParticle",
            handle=handle,
            label=f"{strand}{label_idx}",
            color_key="Value",
        )
        if isinstance(source_payload, dict):
            _add_particle_properties(
                node,
                source_payload,
                bone=bone,
                strand=strand,
                strand_index=strand_index,
                source_index=handle_index,
            )
        else:
            clear_node_properties(node)
            add_node_property(
                node, "bone", bone, json_path="bone.name", label="Bone", editable=False
            )
            add_node_property(
                node,
                "strand",
                strand,
                json_path="editor.strand",
                label="Strand",
                editable=False,
            )
            add_node_property(
                node,
                "strandIndex",
                strand_index,
                json_path="editor.strandIndex",
                label="Strand Index",
                editable=False,
            )
            add_node_property(
                node,
                "placeholder",
                True,
                json_path="placeholder",
                label="Placeholder",
                editable=False,
            )
        _set_editor_extra(
            node,
            red_dangle_bone=bone,
            red_dangle_strand=strand,
            red_dangle_strand_index=int(strand_index),
            red_dangle_source_index=int(handle_index),
            red_dangle_is_placeholder=not isinstance(source_payload, dict),
        )
        particle_nodes[bone] = node
        particle_order.append(bone)
        return node

    for index, particle in enumerate(particles):
        if not isinstance(particle, dict):
            continue
        bone = bone_name(particle.get("bone")) or f"Particle {index}"
        particle_source_payloads[bone] = (particle, index)
        ensure_particle_node(bone, particle, index)

    dyng = payload_data(payload.get("dyngConstraint"))
    constraints = dyng.get("innerConstraints") if isinstance(dyng, dict) else []
    if not isinstance(constraints, list):
        constraints = []

    constraint_edges = 0
    link_edges: list[tuple[str, str]] = []
    degree = Counter()
    incoming = Counter()
    outgoing = Counter()
    cone_degree = Counter()

    cone_nodes: list[tuple[bpy.types.Node, str, str, int]] = []

    for index, wrapper in enumerate(constraints):
        data = payload_data(wrapper)
        if not isinstance(data, dict):
            continue
        handle_id = wrapper.get("HandleId") if isinstance(wrapper, dict) else None
        bone_a, bone_b = constraint_bones(data)
        if not bone_a and not bone_b:
            continue
        node_a = ensure_particle_node(bone_a or f"Constraint {index} A")
        node_b = ensure_particle_node(bone_b or f"Constraint {index} B")
        summary = constraint_summary(data)
        field_path = f"dyngConstraint.Data.innerConstraints[{index}]"
        ctype = str(data.get("$type", "animDyngConstraint"))
        extra = {
            "red_constraint_handle": str(handle_id if handle_id is not None else ""),
            "red_constraint_index": int(index),
            "red_constraint_type": ctype,
            "red_constraint_summary": summary,
            "red_constraint_bone_a": bone_a,
            "red_constraint_bone_b": bone_b,
        }
        try:
            extra["red_constraint_payload_json"] = json.dumps(
                data, separators=(",", ":"), ensure_ascii=False
            )
        except Exception:
            _LOG.debug("Dangle projection operation failed", exc_info=True)

        if ctype.endswith("ConstraintCone"):
            cone_handle = f"editorDangleConeConstraint_{dangle_handle}_{index}_{clean_name(str(handle_id or index))}"
            cone_node = _new_editor_node(
                particle_tree,
                node_type="editorDangleConeConstraint",
                handle=cone_handle,
                label=f"{summary}: {bone_a or '?'} → {bone_b or '?'}",
                color_key="Constraint",
            )
            clear_node_properties(cone_node)
            add_node_property(
                cone_node,
                "constraintHandle",
                str(handle_id if handle_id is not None else ""),
                json_path=f"{field_path}.HandleId",
                label="HandleId",
                editable=False,
            )
            add_node_property(
                cone_node,
                "sourceIndex",
                index,
                json_path=f"{field_path}.index",
                label="Source Index",
                editable=False,
            )
            add_node_property(
                cone_node,
                "attachmentBone",
                bone_a,
                json_path=f"{field_path}.Data.coneAttachmentBone.name",
                label="Attachment Bone",
                editable=False,
            )
            add_node_property(
                cone_node,
                "constrainedBone",
                bone_b,
                json_path=f"{field_path}.Data.constrainedBone.name",
                label="Constrained Bone",
                editable=False,
            )
            for key, value in data.items():
                if key in {"$type", "coneAttachmentBone", "constrainedBone"}:
                    continue
                add_node_property(
                    cone_node, key, value, json_path=f"{field_path}.Data.{key}"
                )
            _set_editor_extra(
                cone_node,
                red_constraint_handle=str(handle_id if handle_id is not None else ""),
                red_constraint_index=int(index),
                red_constraint_type=ctype,
                red_constraint_summary=summary,
                red_constraint_bone_a=bone_a,
                red_constraint_bone_b=bone_b,
            )

            from_particle = _add_editor_output(
                node_a,
                f"cone → {bone_b or '?'}",
                handle=getattr(node_a, "red_handle_id", ""),
                semantics="editor_dangle_constraint",
                link_type=ctype,
            )
            cone_in = _add_editor_input(
                cone_node,
                f"Attachment: {bone_a or '?'}",
                handle=cone_handle,
                field=f"{field_path}.Data.coneAttachmentBone",
                semantics="editor_dangle_constraint",
                link_type=ctype,
            )
            cone_out = _add_editor_output(
                cone_node,
                f"Constrained: {bone_b or '?'}",
                handle=cone_handle,
                semantics="editor_dangle_constraint",
                link_type=ctype,
            )
            to_particle = _add_editor_input(
                node_b,
                f"cone ← {bone_a or '?'}",
                handle=getattr(node_b, "red_handle_id", ""),
                field=f"{field_path}.Data.constrainedBone",
                semantics="editor_dangle_constraint",
                link_type=ctype,
            )
            for sock in (from_particle, cone_in, cone_out, to_particle):
                _set_editor_extra(sock, **extra)
            _link(particle_tree, from_particle, cone_in)
            _link(particle_tree, cone_out, to_particle)
            cone_nodes.append((cone_node, bone_a, bone_b, index))
        else:
            out_label, in_label = constraint_edge_labels(data, bone_a, bone_b)
            out_sock = _add_editor_output(
                node_a,
                out_label,
                handle=getattr(node_a, "red_handle_id", ""),
                semantics="editor_dangle_constraint",
                link_type=ctype,
            )
            in_sock = _add_editor_input(
                node_b,
                in_label,
                handle=getattr(node_b, "red_handle_id", ""),
                field=field_path,
                semantics="editor_dangle_constraint",
                link_type=ctype,
            )
            _set_editor_extra(out_sock, **extra)
            _set_editor_extra(in_sock, **extra)
            _link(particle_tree, out_sock, in_sock)

        constraint_edges += 1
        if bone_a and bone_b:
            link_edges.append((bone_a, bone_b))
        degree[bone_a] += 1
        degree[bone_b] += 1
        outgoing[bone_a] += 1
        incoming[bone_b] += 1
        if ctype.endswith("ConstraintCone"):
            cone_degree[bone_a] += 1
            cone_degree[bone_b] += 1

    for bone, node in particle_nodes.items():
        _set_editor_extra(
            node,
            red_dangle_degree=int(degree.get(bone, 0)),
            red_dangle_incoming=int(incoming.get(bone, 0)),
            red_dangle_outgoing=int(outgoing.get(bone, 0)),
            red_dangle_cone_constraints=int(cone_degree.get(bone, 0)),
        )

    particle_layout = _layout_particles(
        particle_nodes, particle_order, link_edges, cone_nodes
    )
    _layout_cone_constraints(cone_nodes, particle_nodes, particle_layout)

    shapes = payload.get("collisionRoundedShapes") or []
    if not isinstance(shapes, list):
        shapes = []
    collector = _new_editor_node(
        shape_tree,
        node_type="editorRoundedShapeCollector",
        handle=f"editorRoundedShapeCollector_{dangle_handle}",
        label="Rounded Shape Collector",
        color_key="StateMachine",
    )
    clear_node_properties(collector)
    add_node_property(
        collector,
        "shapeCount",
        len(shapes),
        json_path="collisionRoundedShapes.length",
        label="Shape Count",
        editable=False,
    )

    shape_nodes: list[bpy.types.Node] = []
    for index, shape in enumerate(shapes):
        if not isinstance(shape, dict):
            continue
        bone = bone_name(shape.get("bone")) or f"Shape {index}"
        handle = f"editorRoundedShape_{dangle_handle}_{index}_{clean_name(bone)}"
        node = _new_editor_node(
            shape_tree,
            node_type="editorRoundedShape",
            handle=handle,
            label=f"Rounded Shape: {bone}",
            color_key="Value",
        )
        _add_payload_properties(node, shape, skip={"bone"})
        add_node_property(node, "bone", bone, json_path="bone.name", label="Bone")
        out = _add_editor_output(
            node, "Object", handle=handle, semantics="editor_collision_shape"
        )
        in_sock = _add_editor_input(
            collector,
            f"Shape {index}: {bone}",
            handle=getattr(collector, "red_handle_id", ""),
            field=f"collisionRoundedShapes[{index}]",
            semantics="editor_collision_shape",
        )
        _link(shape_tree, out, in_sock)
        shape_nodes.append(node)

    _layout_shapes(shape_nodes, collector)
    return (len(particle_nodes), constraint_edges, len(shapes))


def project_imported_dangle_node(parser, node, handle_id: str, data: dict):
    wrapper = data.get("dangleConstraint") if isinstance(data, dict) else None
    if not isinstance(wrapper, dict):
        return 0, 0, 0
    return create_dangle_editor_subgraphs(parser.root_tree, node, handle_id, wrapper)
