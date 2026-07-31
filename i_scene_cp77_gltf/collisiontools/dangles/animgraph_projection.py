from __future__ import annotations

import json
import re
from collections import Counter, defaultdict, deque
from typing import Any, Dict, Iterable, List, Optional, Tuple

import bpy

from ...blender.animgraph.property_codec import add_node_property, clear_node_properties
from ...blender.animgraph.sockets import bind_red_socket
from ...blender.animgraph.categories import NODE_CATEGORY_COLORS
from ...blender.transactions import track_created_datablock


EDITOR_SOCKET = 'REDengine_AnimGraphSocket_Editor'
TREE_TYPE = 'REDengine_AnimGraphTree'

_PARTICLE_X_SPACING = 300
_PARTICLE_Y_SPACING = 210
_COMPONENT_GAP = 120
_ROW_GAP = 260
_CONE_Y_OFFSET = 105
_CONE_STACK_OFFSET = 70

_TOKEN_ORDER = {
    'back': 0,
    'front': 1,
    'left': 0,
    'mid': 1,
    'right': 2,
    'top': 0,
    'bot': 1,
    'bottom': 1,
}


def _payload(value: Any) -> Optional[dict]:
    if isinstance(value, dict):
        if isinstance(value.get('Data'), dict):
            return value['Data']
        if '$type' in value:
            return value
    return None


def _safe_cname(value: Any) -> str:
    if isinstance(value, dict):
        name = value.get('name')
        if isinstance(name, dict):
            text = name.get('$value', '')
            return '' if text == 'None' else str(text)
        text = value.get('$value', '')
        return '' if text == 'None' else str(text)
    if isinstance(value, str):
        return '' if value == 'None' else value
    return ''


def _bone_name(value: Any) -> str:
    if not isinstance(value, dict):
        return ''
    return _safe_cname(value) or _safe_cname(value.get('name'))


def _clean_name(value: str) -> str:
    text = ''.join(ch if ch.isalnum() or ch in '_-' else '_' for ch in str(value or ''))
    return text.strip('_') or 'item'


def _strand_and_index(name: str, default_index: int = -1) -> Tuple[str, int]:
    text = str(name or '')
    m = re.search(r'^(.*?)(?:_)?(\d+)$', text)
    if not m:
        return text, default_index
    try:
        idx = int(m.group(2))
    except Exception:
        idx = default_index
    return m.group(1), idx


def _strand_sort_key(strand: str) -> Tuple[int, int, int, str]:
    tokens = [t for t in str(strand or '').replace('-', '_').split('_') if t and t != 'dyng']

    region = 99
    lateral = 99
    vertical = 99
    for token in tokens:
        if token in {'back', 'front'}:
            region = min(region, _TOKEN_ORDER[token])
        elif token in {'left', 'mid', 'right'}:
            lateral = min(lateral, _TOKEN_ORDER[token])
        elif token in {'top', 'bot', 'bottom'}:
            vertical = min(vertical, _TOKEN_ORDER[token])
    return region, lateral, vertical, str(strand or '')


def _particle_sort_key(name: str, default_index: int) -> Tuple[Tuple[int, int, int, str], int, str, int]:
    strand, idx = _strand_and_index(name, default_index)
    return (_strand_sort_key(strand), idx if idx >= 0 else default_index, str(name or ''), default_index)


def _editor_tree(root_tree: bpy.types.NodeTree, name: str, *, parent_handle: str, kind: str) -> bpy.types.NodeTree:
    tree = bpy.data.node_groups.get(name)
    if tree is None:
        tree = track_created_datablock(
            "node_groups",
            bpy.data.node_groups.new(name=name, type=TREE_TYPE),
        )
    tree['red_internal_subgraph'] = True
    tree['red_editor_subgraph'] = True
    tree['red_public_tree'] = False
    tree['red_parent_graph'] = root_tree.name
    tree['red_parent_dangle_handle'] = str(parent_handle or '')
    tree['red_editor_subgraph_kind'] = kind
    try:
        tree.use_fake_user = False
    except Exception:
        pass
    try:
        tree.nodes.clear()
    except Exception:
        for node in list(tree.nodes):
            tree.nodes.remove(node)
    return tree


def _new_editor_node(
    tree: bpy.types.NodeTree,
    *,
    node_type: str,
    handle: str,
    label: str,
    color_key: str = 'Editor',
) -> bpy.types.Node:
    node = tree.nodes.new('REDengine_AnimGraphNode_Generic')
    node.red_type = node_type
    node.red_handle_id = handle
    try:
        node.red_exportable = False
        node.red_pseudo = True
        node.red_metadata_known = False
        node.red_parent_class = ''
        node.red_output_kind = 'editor'
        node.red_roundtrip_ready = True
        node.red_roundtrip_notes = 'editor-only dangle projection node'
        node.red_layout_auto = True
    except Exception:
        pass
    node.name = handle
    node.label = label
    node.use_custom_color = True
    try:
        node.color = NODE_CATEGORY_COLORS.get(color_key, NODE_CATEGORY_COLORS.get('Other', (0.30, 0.30, 0.30)))
    except Exception:
        pass
    return node


def _add_editor_output(node: bpy.types.Node, name: str, *, handle: str, semantics: str, link_type: str = 'editorObject') -> bpy.types.NodeSocket:
    sock = node.outputs.new(EDITOR_SOCKET, name)
    return bind_red_socket(
        sock, role='output', owner_handle=handle, link_type=link_type,
        exportable=False, edge_semantics=semantics, pseudo=True)


def _add_editor_input(node: bpy.types.Node, name: str, *, handle: str, field: str, semantics: str, link_type: str = 'editorObject') -> bpy.types.NodeSocket:
    sock = node.inputs.new(EDITOR_SOCKET, name)
    return bind_red_socket(
        sock, role='input', owner_handle=handle, field_name=field,
        json_path=field, link_type=link_type, exportable=False,
        edge_semantics=semantics, pseudo=True)


def _link(tree: bpy.types.NodeTree, out_sock: bpy.types.NodeSocket, in_sock: bpy.types.NodeSocket) -> None:
    try:
        tree.links.new(out_sock, in_sock)
    except Exception:
        pass


def _set_socket_extra(socket: bpy.types.NodeSocket, **values: Any) -> None:
    for key, value in values.items():
        try:
            socket[key] = value
        except Exception:
            try:
                setattr(socket, key, value)
            except Exception:
                pass


def _set_node_extra(node: bpy.types.Node, **values: Any) -> None:
    for key, value in values.items():
        try:
            node[key] = value
        except Exception:
            try:
                setattr(node, key, value)
            except Exception:
                pass


def _add_payload_properties(node: bpy.types.Node, payload: dict, *, skip: Iterable[str] = ()) -> None:
    clear_node_properties(node)
    skip_set = {'$type', *skip}
    for key, value in payload.items():
        if key in skip_set:
            continue
        add_node_property(node, key, value, json_path=key)


def _add_particle_properties(node: bpy.types.Node, payload: dict, *, bone: str, strand: str, strand_index: int, source_index: int) -> None:
    clear_node_properties(node)
    add_node_property(node, 'bone', bone, json_path='bone.name', label='Bone', editable=False)
    add_node_property(node, 'strand', strand, json_path='editor.strand', label='Strand', editable=False)
    add_node_property(node, 'strandIndex', strand_index, json_path='editor.strandIndex', label='Strand Index', editable=False)
    add_node_property(node, 'sourceIndex', source_index, json_path='particlesContainer.particles.index', label='Source Index', editable=False)


    preferred = [
        'isFree', 'mass', 'damping', 'pullForceFactor', 'projectionType',
        'collisionCapsuleRadius', 'collisionCapsuleHeightExtent', 'collisionCapsuleAxisLS',
        'isDebugEnabled',
    ]
    used = {'$type', 'bone'}
    for key in preferred:
        if key in payload:
            add_node_property(node, key, payload[key], json_path=f'particlesContainer.particles[{source_index}].{key}')
            used.add(key)
    for key, value in payload.items():
        if key in used:
            continue
        add_node_property(node, key, value, json_path=f'particlesContainer.particles[{source_index}].{key}')


def _constraint_bones(data: dict) -> Tuple[str, str]:
    ctype = str(data.get('$type', ''))
    if ctype.endswith('ConstraintLink'):
        return _bone_name(data.get('bone1')), _bone_name(data.get('bone2'))
    if ctype.endswith('ConstraintCone'):
        return _bone_name(data.get('coneAttachmentBone')), _bone_name(data.get('constrainedBone'))
    found: List[str] = []
    for _key, value in data.items():
        if isinstance(value, dict) and value.get('$type') == 'animTransformIndex':
            text = _bone_name(value)
            if text:
                found.append(text)
        if len(found) >= 2:
            break
    return (found[0] if len(found) > 0 else '', found[1] if len(found) > 1 else '')


def _constraint_summary(data: dict) -> str:
    short = str(data.get('$type', 'animDyngConstraint')).replace('animDyngConstraint', '') or 'Constraint'
    if short == 'Link':
        lower = data.get('lengthLowerBoundRatioPercentage')
        upper = data.get('lengthUpperBoundRatioPercentage')
        if lower is not None and upper is not None:
            return f"{data.get('linkType', 'Link')} {lower:g}-{upper:g}%"
        return str(data.get('linkType', 'Link'))
    if short == 'Cone':
        ctype = data.get('constraintType', 'Cone')
        angle = data.get('halfOfMaxApertureAngle')
        return f"{ctype} {angle:g}°" if isinstance(angle, (int, float)) else str(ctype)
    return short


def _constraint_edge_labels(data: dict, bone_a: str, bone_b: str) -> Tuple[str, str]:
    summary = _constraint_summary(data)
    ctype = str(data.get('$type', '')).replace('animDyngConstraint', '') or 'Constraint'
    if ctype == 'Link':


        return f"to {bone_b or '?'}", f"from {bone_a or '?'}"
    return f"{summary} →", f"← {summary}"


def _build_particle_components(particle_names: Iterable[str], edge_pairs: Iterable[Tuple[str, str]]) -> List[List[str]]:
    adj: Dict[str, set] = defaultdict(set)
    all_names = set(particle_names)
    for a, b in edge_pairs:
        if a:
            all_names.add(a)
        if b:
            all_names.add(b)
        if a and b:
            adj[a].add(b)
            adj[b].add(a)
    seen = set()
    components: List[List[str]] = []
    for seed in sorted(all_names, key=lambda n: _particle_sort_key(n, 0)):
        if seed in seen:
            continue
        q = deque([seed])
        seen.add(seed)
        comp = []
        while q:
            cur = q.popleft()
            comp.append(cur)
            for nxt in sorted(adj.get(cur, ()), key=lambda n: _particle_sort_key(n, 0)):
                if nxt not in seen:
                    seen.add(nxt)
                    q.append(nxt)
        components.append(sorted(comp, key=lambda n: _particle_sort_key(n, 0)))
    return components


def _estimate_editor_node_size(node: bpy.types.Node) -> Tuple[float, float]:
    red_type = getattr(node, 'red_type', '') or ''
    props = getattr(node, 'red_properties', None)
    try:
        prop_count = len(props) if props is not None else 0
    except Exception:
        prop_count = 0
    if red_type == 'editorDangleParticle':
        width = 285.0
        height = max(245.0, 112.0 + 24.0 * prop_count)
    elif red_type == 'editorDangleConeConstraint':
        width = 360.0
        height = max(250.0, 120.0 + 24.0 * prop_count)
    elif red_type == 'editorRoundedShape':
        width = 310.0
        height = max(260.0, 120.0 + 24.0 * prop_count)
    elif red_type == 'editorRoundedShapeCollector':
        width = 300.0
        height = max(160.0, 95.0 + 22.0 * prop_count)
    else:
        width = 280.0
        height = max(180.0, 95.0 + 22.0 * prop_count)
    try:
        node.width = max(float(getattr(node, 'width', 0.0) or 0.0), width)
    except Exception:
        pass
    return width, height


def _node_box(node: bpy.types.Node) -> Tuple[bpy.types.Node, float, float, float, float]:
    width, height = _estimate_editor_node_size(node)
    x = float(node.location.x if hasattr(node.location, 'x') else node.location[0])
    y = float(node.location.y if hasattr(node.location, 'y') else node.location[1])
    return (node, x, x + width, y - height, y)


def _box_hits(box: Tuple[bpy.types.Node, float, float, float, float], boxes: List[Tuple[bpy.types.Node, float, float, float, float]], pad: float = 28.0) -> bool:
    _node, ax1, ax2, ay1, ay2 = box
    ax1 -= pad; ax2 += pad; ay1 -= pad; ay2 += pad
    for other, bx1, bx2, by1, by2 in boxes:
        if other is _node:
            continue
        if ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2:
            return True
    return False


def _candidate_offsets(step: float, count: int = 80) -> List[float]:
    values = [0.0]
    for i in range(1, count):
        values.append(i * step)
        values.append(-i * step)
    return values


def _layout_particles(
    nodes_by_bone: Dict[str, bpy.types.Node],
    order: List[str],
    link_edges: List[Tuple[str, str]],
    cone_nodes: Optional[List[Tuple[bpy.types.Node, str, str, int]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Lay out dangle particles deterministically by strand and depth."""
    if not nodes_by_bone:
        return {}

    groups: Dict[str, List[str]] = defaultdict(list)
    source_order = {name: i for i, name in enumerate(order)}
    for bone in nodes_by_bone:
        strand, _idx = _strand_and_index(bone, source_order.get(bone, 0))
        groups[strand].append(bone)

    components = _build_particle_components(nodes_by_bone.keys(), link_edges)
    comp_index = {bone: ci for ci, comp in enumerate(components) for bone in comp}

    cone_counts: Counter = Counter()
    for _cone, bone_a, bone_b, _index in cone_nodes or []:
        strand_a, _ = _strand_and_index(bone_a, source_order.get(bone_a, 0))
        strand_b, _ = _strand_and_index(bone_b, source_order.get(bone_b, 0))
        strand = strand_a or strand_b or '<unassigned>'
        cone_counts[strand] += 1

    sorted_strands = sorted(
        groups.keys(),
        key=lambda strand: (
            min((comp_index.get(b, 10**6) for b in groups[strand]), default=10**6),
            _strand_sort_key(strand),
            strand,
        ),
    )

    x_spacing = 520.0
    base_band_gap = 190.0
    cone_lane_height = 390.0
    layout: Dict[str, Dict[str, Any]] = {}
    row_bands: Dict[int, Dict[str, Any]] = {}
    y = 0.0
    last_component = None

    for row_index, strand in enumerate(sorted_strands):
        bones = groups[strand]
        bones.sort(key=lambda b: _particle_sort_key(b, source_order.get(b, 0)))
        comps = {comp_index.get(b, -1) for b in bones}
        comp = min(comps) if comps else -1
        if last_component is not None and comp != last_component:
            y -= 260.0
        last_component = comp

        numeric = [_strand_and_index(b, source_order.get(b, 0))[1] for b in bones]
        numeric = [n for n in numeric if n >= 0]
        min_idx = min(numeric) if numeric else 0
        max_particle_height = 0.0
        x_values: List[float] = []

        for pos, bone in enumerate(bones):
            node = nodes_by_bone.get(bone)
            if node is None:
                continue
            _strand, idx = _strand_and_index(bone, source_order.get(bone, pos))
            x_pos = (idx - min_idx) * x_spacing if idx >= 0 else pos * x_spacing
            node.location = (x_pos, y)
            width, height = _estimate_editor_node_size(node)
            max_particle_height = max(max_particle_height, height)
            x_values.append(x_pos)
            layout[bone] = {
                'strand': strand,
                'row': row_index,
                'x': x_pos,
                'y': y,
                'width': width,
                'height': height,
                'center_y': y - height * 0.5,
            }

        lanes = max(1, int(cone_counts.get(strand, 0)))
        row_bands[row_index] = {
            'strand': strand,
            'top': y,
            'particle_height': max_particle_height or 260.0,
            'cone_lanes': lanes,
            'x_min': min(x_values) if x_values else 0.0,
            'x_max': max(x_values) if x_values else 0.0,
        }


        y -= (max_particle_height or 260.0) + base_band_gap + lanes * cone_lane_height


    layout['__rows__'] = row_bands  # type: ignore[assignment]
    return layout


def _layout_cone_constraints(
    cone_nodes: List[Tuple[bpy.types.Node, str, str, int]],
    particle_nodes: Dict[str, bpy.types.Node],
    particle_layout: Optional[Dict[str, Dict[str, Any]]] = None,
) -> None:
    """Place cone constraints in reserved lanes next to their particles."""
    if not cone_nodes:
        return
    particle_layout = particle_layout or {}
    row_bands = particle_layout.get('__rows__', {}) if isinstance(particle_layout, dict) else {}

    def row_for(bone: str) -> int:
        info = particle_layout.get(bone, {}) if isinstance(particle_layout, dict) else {}
        try:
            return int(info.get('row', 999999))
        except Exception:
            return 999999

    def cone_sort(item: Tuple[bpy.types.Node, str, str, int]):
        _node, bone_a, bone_b, index = item
        ra = row_for(bone_a)
        rb = row_for(bone_b)
        row = min(ra, rb)
        la = particle_layout.get(bone_a, {}) if isinstance(particle_layout, dict) else {}
        strand = str(la.get('strand') or '')
        return (row, _strand_sort_key(strand), index)

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
            particle_top = float(row_meta.get('top', max(ay, by)))
            particle_height = float(row_meta.get('particle_height', 300.0))
            slot_key = ('row', row)
            slot = lane_counts[slot_key]
            lane_counts[slot_key] += 1
            x = (ax + bx) * 0.5 + 70.0
            y = particle_top - particle_height - 120.0 - slot * (cone_h + 120.0)
        else:


            slot_key = ('cross', min(ra, rb), max(ra, rb))
            slot = cross_counts[slot_key]
            cross_counts[slot_key] += 1
            x = max(ax, bx) + 620.0 + slot * 90.0
            center_y = ((ay + by) * 0.5) - cone_h * 0.25
            y = center_y + cone_h * 0.5

        cone_node.location = (x, y)


def _layout_shapes(shape_nodes: List[bpy.types.Node], collector: bpy.types.Node) -> None:
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
) -> Tuple[int, int, int]:
    """Create editor-only dangle subgraphs for readable constraint editing."""
    payload = _payload(dangle_constraint_wrapper)
    if not isinstance(payload, dict):
        return (0, 0, 0)

    root_safe = _clean_name(root_tree.name)
    base = f".{root_safe}_Dangle_{_clean_name(dangle_handle)}"
    particle_tree = _editor_tree(
        root_tree, f"{base}_ParticlesAndConstraints",
        parent_handle=dangle_handle, kind='particles_constraints')
    shape_tree = _editor_tree(
        root_tree, f"{base}_CollisionRoundedShapes",
        parent_handle=dangle_handle, kind='collision_rounded_shapes')

    try:
        dangle_node.red_editor_subgraph_a_name = particle_tree.name
        dangle_node.red_editor_subgraph_a_label = 'Particles / Constraints'
        dangle_node.red_editor_subgraph_b_name = shape_tree.name
        dangle_node.red_editor_subgraph_b_label = 'Collision Rounded Shapes'
    except Exception:
        try:
            dangle_node['red_editor_subgraph_a_name'] = particle_tree.name
            dangle_node['red_editor_subgraph_a_label'] = 'Particles / Constraints'
            dangle_node['red_editor_subgraph_b_name'] = shape_tree.name
            dangle_node['red_editor_subgraph_b_label'] = 'Collision Rounded Shapes'
        except Exception:
            pass

    particles_container = payload.get('particlesContainer') if isinstance(payload, dict) else None
    particles = particles_container.get('particles') if isinstance(particles_container, dict) else []
    if not isinstance(particles, list):
        particles = []

    particle_nodes: Dict[str, bpy.types.Node] = {}
    particle_order: List[str] = []
    particle_source_payloads: Dict[str, Tuple[dict, int]] = {}

    def ensure_particle_node(bone: str, source_payload: Optional[dict] = None, index: int = -1) -> bpy.types.Node:
        nonlocal particle_nodes, particle_order
        bone = bone or f'Particle {len(particle_nodes)}'
        if bone in particle_nodes:
            return particle_nodes[bone]
        handle_index = index if index >= 0 else len(particle_nodes)
        strand, strand_index = _strand_and_index(bone, handle_index)
        handle = f"editorDangleParticle_{dangle_handle}_{handle_index}_{_clean_name(bone)}"
        label_idx = f" #{strand_index}" if strand_index >= 0 else ''
        node = _new_editor_node(
            particle_tree, node_type='editorDangleParticle', handle=handle,
            label=f"{strand}{label_idx}", color_key='Value')
        if isinstance(source_payload, dict):
            _add_particle_properties(node, source_payload, bone=bone, strand=strand, strand_index=strand_index, source_index=handle_index)
        else:
            clear_node_properties(node)
            add_node_property(node, 'bone', bone, json_path='bone.name', label='Bone', editable=False)
            add_node_property(node, 'strand', strand, json_path='editor.strand', label='Strand', editable=False)
            add_node_property(node, 'strandIndex', strand_index, json_path='editor.strandIndex', label='Strand Index', editable=False)
            add_node_property(node, 'placeholder', True, json_path='placeholder', label='Placeholder', editable=False)
        _set_node_extra(
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
        bone = _bone_name(particle.get('bone')) or f'Particle {index}'
        particle_source_payloads[bone] = (particle, index)
        ensure_particle_node(bone, particle, index)

    dyng = _payload(payload.get('dyngConstraint'))
    constraints = dyng.get('innerConstraints') if isinstance(dyng, dict) else []
    if not isinstance(constraints, list):
        constraints = []

    constraint_edges = 0
    link_edges: List[Tuple[str, str]] = []
    degree = Counter()
    incoming = Counter()
    outgoing = Counter()
    cone_degree = Counter()

    cone_nodes: List[Tuple[bpy.types.Node, str, str, int]] = []

    for index, wrapper in enumerate(constraints):
        data = _payload(wrapper)
        if not isinstance(data, dict):
            continue
        handle_id = wrapper.get('HandleId') if isinstance(wrapper, dict) else None
        bone_a, bone_b = _constraint_bones(data)
        if not bone_a and not bone_b:
            continue
        node_a = ensure_particle_node(bone_a or f'Constraint {index} A')
        node_b = ensure_particle_node(bone_b or f'Constraint {index} B')
        summary = _constraint_summary(data)
        field_path = f'dyngConstraint.Data.innerConstraints[{index}]'
        ctype = str(data.get('$type', 'animDyngConstraint'))
        extra = {
            'red_constraint_handle': str(handle_id if handle_id is not None else ''),
            'red_constraint_index': int(index),
            'red_constraint_type': ctype,
            'red_constraint_summary': summary,
            'red_constraint_bone_a': bone_a,
            'red_constraint_bone_b': bone_b,
        }
        try:
            extra['red_constraint_payload_json'] = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        except Exception:
            pass

        if ctype.endswith('ConstraintCone'):


            cone_handle = f"editorDangleConeConstraint_{dangle_handle}_{index}_{_clean_name(str(handle_id or index))}"
            cone_node = _new_editor_node(
                particle_tree,
                node_type='editorDangleConeConstraint',
                handle=cone_handle,
                label=f"{summary}: {bone_a or '?'} → {bone_b or '?'}",
                color_key='Constraint',
            )
            clear_node_properties(cone_node)
            add_node_property(cone_node, 'constraintHandle', str(handle_id if handle_id is not None else ''), json_path=f'{field_path}.HandleId', label='HandleId', editable=False)
            add_node_property(cone_node, 'sourceIndex', index, json_path=f'{field_path}.index', label='Source Index', editable=False)
            add_node_property(cone_node, 'attachmentBone', bone_a, json_path=f'{field_path}.Data.coneAttachmentBone.name', label='Attachment Bone', editable=False)
            add_node_property(cone_node, 'constrainedBone', bone_b, json_path=f'{field_path}.Data.constrainedBone.name', label='Constrained Bone', editable=False)
            for key, value in data.items():
                if key in {'$type', 'coneAttachmentBone', 'constrainedBone'}:
                    continue
                add_node_property(cone_node, key, value, json_path=f'{field_path}.Data.{key}')
            _set_node_extra(
                cone_node,
                red_constraint_handle=str(handle_id if handle_id is not None else ''),
                red_constraint_index=int(index),
                red_constraint_type=ctype,
                red_constraint_summary=summary,
                red_constraint_bone_a=bone_a,
                red_constraint_bone_b=bone_b,
            )

            from_particle = _add_editor_output(
                node_a, f"cone → {bone_b or '?'}", handle=getattr(node_a, 'red_handle_id', ''),
                semantics='editor_dangle_constraint', link_type=ctype)
            cone_in = _add_editor_input(
                cone_node, f"Attachment: {bone_a or '?'}", handle=cone_handle,
                field=f'{field_path}.Data.coneAttachmentBone', semantics='editor_dangle_constraint', link_type=ctype)
            cone_out = _add_editor_output(
                cone_node, f"Constrained: {bone_b or '?'}", handle=cone_handle,
                semantics='editor_dangle_constraint', link_type=ctype)
            to_particle = _add_editor_input(
                node_b, f"cone ← {bone_a or '?'}", handle=getattr(node_b, 'red_handle_id', ''),
                field=f'{field_path}.Data.constrainedBone', semantics='editor_dangle_constraint', link_type=ctype)
            for sock in (from_particle, cone_in, cone_out, to_particle):
                _set_socket_extra(sock, **extra)
            _link(particle_tree, from_particle, cone_in)
            _link(particle_tree, cone_out, to_particle)
            cone_nodes.append((cone_node, bone_a, bone_b, index))
        else:


            out_label, in_label = _constraint_edge_labels(data, bone_a, bone_b)
            out_sock = _add_editor_output(
                node_a, out_label, handle=getattr(node_a, 'red_handle_id', ''),
                semantics='editor_dangle_constraint', link_type=ctype)
            in_sock = _add_editor_input(
                node_b, in_label, handle=getattr(node_b, 'red_handle_id', ''),
                field=field_path, semantics='editor_dangle_constraint', link_type=ctype)
            _set_socket_extra(out_sock, **extra)
            _set_socket_extra(in_sock, **extra)
            _link(particle_tree, out_sock, in_sock)

        constraint_edges += 1
        if bone_a and bone_b:
            link_edges.append((bone_a, bone_b))
        degree[bone_a] += 1
        degree[bone_b] += 1
        outgoing[bone_a] += 1
        incoming[bone_b] += 1
        if ctype.endswith('ConstraintCone'):
            cone_degree[bone_a] += 1
            cone_degree[bone_b] += 1


    for bone, node in particle_nodes.items():
        _set_node_extra(
            node,
            red_dangle_degree=int(degree.get(bone, 0)),
            red_dangle_incoming=int(incoming.get(bone, 0)),
            red_dangle_outgoing=int(outgoing.get(bone, 0)),
            red_dangle_cone_constraints=int(cone_degree.get(bone, 0)),
        )

    particle_layout = _layout_particles(particle_nodes, particle_order, link_edges, cone_nodes)
    _layout_cone_constraints(cone_nodes, particle_nodes, particle_layout)


    shapes = payload.get('collisionRoundedShapes') or []
    if not isinstance(shapes, list):
        shapes = []
    collector = _new_editor_node(
        shape_tree, node_type='editorRoundedShapeCollector',
        handle=f"editorRoundedShapeCollector_{dangle_handle}",
        label='Rounded Shape Collector', color_key='StateMachine')
    clear_node_properties(collector)
    add_node_property(collector, 'shapeCount', len(shapes), json_path='collisionRoundedShapes.length', label='Shape Count', editable=False)

    shape_nodes: List[bpy.types.Node] = []
    for index, shape in enumerate(shapes):
        if not isinstance(shape, dict):
            continue
        bone = _bone_name(shape.get('bone')) or f'Shape {index}'
        handle = f"editorRoundedShape_{dangle_handle}_{index}_{_clean_name(bone)}"
        node = _new_editor_node(
            shape_tree, node_type='editorRoundedShape', handle=handle,
            label=f"Rounded Shape: {bone}", color_key='Value')
        _add_payload_properties(node, shape, skip={'bone'})
        add_node_property(node, 'bone', bone, json_path='bone.name', label='Bone')
        out = _add_editor_output(node, 'Object', handle=handle, semantics='editor_collision_shape')
        in_sock = _add_editor_input(
            collector, f'Shape {index}: {bone}', handle=getattr(collector, 'red_handle_id', ''),
            field=f'collisionRoundedShapes[{index}]', semantics='editor_collision_shape')
        _link(shape_tree, out, in_sock)
        shape_nodes.append(node)

    _layout_shapes(shape_nodes, collector)
    return (len(particle_nodes), constraint_edges, len(shapes))


def project_imported_dangle_node(parser, node, handle_id: str, data: dict):
    wrapper = data.get("dangleConstraint") if isinstance(data, dict) else None
    if not isinstance(wrapper, dict):
        return 0, 0, 0
    return create_dangle_editor_subgraphs(parser.root_tree, node, handle_id, wrapper)
