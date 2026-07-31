from ...blender.animgraph import presenters
from ...blender.animgraph.property_ui import (
    draw_property_row,
    draw_scalar_target,
    property_by_key,
)

def draw_dangle_particle_node(owner, layout):
    col = layout.column(align=True)
    bone = owner.get('red_dangle_bone', '') if hasattr(owner, 'get') else ''
    strand = owner.get('red_dangle_strand', '') if hasattr(owner, 'get') else ''
    strand_index = owner.get('red_dangle_strand_index', -1) if hasattr(owner, 'get') else -1
    source_index = owner.get('red_dangle_source_index', -1) if hasattr(owner, 'get') else -1
    degree = owner.get('red_dangle_degree', 0) if hasattr(owner, 'get') else 0
    incoming = owner.get('red_dangle_incoming', 0) if hasattr(owner, 'get') else 0
    outgoing = owner.get('red_dangle_outgoing', 0) if hasattr(owner, 'get') else 0
    cones = owner.get('red_dangle_cone_constraints', 0) if hasattr(owner, 'get') else 0

    head = col.box()
    row = head.row(align=True)
    row.label(text='Dangle Particle', icon='PARTICLE_POINT')
    row.label(text=f"#{source_index}" if source_index >= 0 else 'placeholder')
    if bone:
        head.label(text=bone, icon='BONE_DATA')
    row = head.row(align=True)
    row.label(text=f"Strand: {strand or '-'}")
    row.label(text=f"Index: {strand_index}" if strand_index >= 0 else 'Index: -')

    sim_keys = ('isFree', 'mass', 'damping', 'pullForceFactor', 'projectionType')
    cap_keys = ('collisionCapsuleRadius', 'collisionCapsuleHeightExtent', 'collisionCapsuleAxisLS')
    debug_keys = ('isDebugEnabled',)
    shown = {'bone', 'strand', 'strandIndex', 'sourceIndex'}

    sim_box = col.box()
    sim_box.label(text='Simulation', icon='PHYSICS')
    for key in sim_keys:
        item = property_by_key(owner, key)
        if item is not None:
            draw_scalar_target(item, sim_box, item.label or item.key)
            shown.add(key)

    cap_box = col.box()
    cap_box.label(text='Collision Capsule', icon='MESH_CAPSULE')
    any_cap = False
    for key in cap_keys:
        item = property_by_key(owner, key)
        if item is not None:
            draw_scalar_target(item, cap_box, item.label or item.key)
            shown.add(key)
            any_cap = True
    if not any_cap:
        cap_box.label(text='No capsule fields on this particle.', icon='INFO')

    conn_box = col.box()
    conn_box.label(text='Constraint Links', icon='LINKED')
    row = conn_box.row(align=True)
    row.label(text=f"In: {incoming}")
    row.label(text=f"Out: {outgoing}")
    row.label(text=f"Total: {degree}")
    if cones:
        row.label(text=f"Cone: {cones}")
    socket_col = conn_box.column(align=True)
    socket_col.label(text='Socket labels show connected particles; constraint details are stored on sockets.', icon='INFO')

    dbg_items = [item for key in debug_keys if (item := property_by_key(owner, key)) is not None]
    if dbg_items:
        dbg_box = col.box()
        dbg_box.label(text='Debug', icon='TOOL_SETTINGS')
        for item in dbg_items:
            draw_scalar_target(item, dbg_box, item.label or item.key)
            shown.add(item.key)

    props = getattr(owner, 'red_properties', None)
    other = [item for item in props or [] if item.key not in shown]
    if other:
        other_box = col.box()
        other_box.label(text='Other Particle Fields', icon='PROPERTIES')
        for item in other:
            draw_property_row(owner, other_box, item, -1)

def draw_dangle_cone_constraint_node(owner, layout):
    col = layout.column(align=True)
    ctype = owner.get('red_constraint_type', '') if hasattr(owner, 'get') else ''
    summary = owner.get('red_constraint_summary', '') if hasattr(owner, 'get') else ''
    bone_a = owner.get('red_constraint_bone_a', '') if hasattr(owner, 'get') else ''
    bone_b = owner.get('red_constraint_bone_b', '') if hasattr(owner, 'get') else ''
    index = owner.get('red_constraint_index', -1) if hasattr(owner, 'get') else -1
    handle = owner.get('red_constraint_handle', '') if hasattr(owner, 'get') else ''

    head = col.box()
    row = head.row(align=True)
    row.label(text='Dangle Cone Constraint', icon='MESH_CONE')
    if index >= 0:
        row.label(text=f"#{index}")
    if summary:
        head.label(text=summary, icon='DRIVER_ROTATIONAL_DIFFERENCE')
    row = head.row(align=True)
    row.label(text=f"Attachment: {bone_a or '-'}")
    row.label(text=f"Constrained: {bone_b or '-'}")
    if handle:
        head.label(text=f"HandleId: {handle}", icon='KEYINGSET')
    if ctype:
        head.label(text=ctype, icon='INFO')

    shown = {'constraintHandle', 'sourceIndex', 'attachmentBone', 'constrainedBone'}
    geometry_keys = (
        'constraintType', 'halfOfMaxApertureAngle', 'projectionType',
        'coneTransformLS', 'collisionCapsuleRadius', 'collisionCapsuleHeightExtent',
    )
    debug_keys = ('isDebugEnabled',)

    geom_box = col.box()
    geom_box.label(text='Cone Parameters', icon='MESH_CONE')
    any_geom = False
    for key in geometry_keys:
        item = property_by_key(owner, key)
        if item is not None:
            draw_property_row(owner, geom_box, item, -1)
            shown.add(key)
            any_geom = True
    if not any_geom:
        geom_box.label(text='No cone parameter fields on this constraint.', icon='INFO')

    dbg_items = [item for key in debug_keys if (item := property_by_key(owner, key)) is not None]
    if dbg_items:
        dbg_box = col.box()
        dbg_box.label(text='Debug', icon='TOOL_SETTINGS')
        for item in dbg_items:
            draw_scalar_target(item, dbg_box, item.label or item.key)
            shown.add(item.key)

    props = getattr(owner, 'red_properties', None)
    other = [item for item in props or [] if item.key not in shown]
    if other:
        other_box = col.box()
        other_box.label(text='Other Constraint Fields', icon='PROPERTIES')
        for item in other:
            draw_property_row(owner, other_box, item, -1)

def draw_dangle_node(node, context, layout):
    presenter_id = presenters.node_presenter_id(node)
    if presenter_id == presenters.PRESENTER_DANGLE_PARTICLE:
        draw_dangle_particle_node(node, layout)
        return
    if presenter_id == presenters.PRESENTER_DANGLE_CONE:
        draw_dangle_cone_constraint_node(node, layout)
