import json

import bpy

from .constants import ANIMGRAPH_TREE_ID
from .properties import (
    REDengine_AnimNodeProperty,
    reset_curve_property_from_raw_json,
    sort_curve_points,
)
from . import curve_mapping
from . import math_expression
from . import variable_bindings
from . import node_presenters
try:
    from . import rtti_schema
except Exception:
    rtti_schema = None


_VECTOR_LABELS = {
    'VECTOR2': ('X', 'Y'),
    'VECTOR3': ('X', 'Y', 'Z'),
    'VECTOR4': ('X', 'Y', 'Z', 'W'),
    'QUATERNION': ('i', 'j', 'k', 'r'),
    'FLOAT_CLAMP': ('Min', 'Max'),
}

_QS_VEC_LABELS = {
    'qs_translation': ('X', 'Y', 'Z', 'W'),
    'qs_rotation': ('i', 'j', 'k', 'r'),
    'qs_scale': ('X', 'Y', 'Z', 'W'),
}


class REDENGINE_UL_curve_points(bpy.types.UIList):
    bl_idname = 'REDENGINE_UL_curve_points'

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.label(text=str(index))
            row.prop(item, 'point', text='Point')
            row.prop(item, 'value', text='Value')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=str(index))


def _active_curve_property(context, index):
    node = getattr(context, 'active_node', None)
    if node is None:
        return None
    props = getattr(node, 'red_properties', None)
    if props is None or index < 0 or index >= len(props):
        return None
    item = props[index]
    if item.value_kind != 'CURVE_FLOAT':
        return None
    return item


class REDENGINE_OT_enter_editor_subgraph(bpy.types.Operator):
    bl_idname = 'redengine.enter_editor_subgraph'
    bl_label = 'Enter Editor Subgraph'
    bl_options = {'REGISTER', 'UNDO'}

    tree_name: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return space is not None and space.type == 'NODE_EDITOR'

    def execute(self, context):
        tree = bpy.data.node_groups.get(self.tree_name) if self.tree_name else None
        if tree is None:
            self.report({'WARNING'}, 'Editor subgraph not found')
            return {'CANCELLED'}
        try:
            context.space_data.path.append(tree)
        except TypeError:


            context.space_data.node_tree = tree
        return {'FINISHED'}


class REDENGINE_OT_curve_point_add(bpy.types.Operator):
    bl_idname = 'redengine.curve_point_add'
    bl_label = 'Add Curve Point'
    bl_options = {'REGISTER', 'UNDO'}

    property_index: bpy.props.IntProperty()

    def execute(self, context):
        item = _active_curve_property(context, self.property_index)
        if item is None:
            self.report({'WARNING'}, 'No active REDengine curve property')
            return {'CANCELLED'}

        count = len(item.curve_points)
        idx = max(0, min(item.curve_points_index, count - 1)) if count else 0
        if count == 0:
            x, y = 0.0, 0.0
        elif idx < count - 1:
            a = item.curve_points[idx]
            b = item.curve_points[idx + 1]
            x = (float(a.point) + float(b.point)) * 0.5
            y = (float(a.value) + float(b.value)) * 0.5
        else:
            a = item.curve_points[idx]
            step = 0.1
            if count >= 2:
                prev = item.curve_points[idx - 1]
                step = max(0.01, min(1.0, abs(float(a.point) - float(prev.point))))
            x = float(a.point) + step
            y = float(a.value)

        point = item.curve_points.add()
        point.point = x
        point.value = y
        item.curve_points_index = len(item.curve_points) - 1
        return {'FINISHED'}


class REDENGINE_OT_curve_point_remove(bpy.types.Operator):
    bl_idname = 'redengine.curve_point_remove'
    bl_label = 'Remove Curve Point'
    bl_options = {'REGISTER', 'UNDO'}

    property_index: bpy.props.IntProperty()

    def execute(self, context):
        item = _active_curve_property(context, self.property_index)
        if item is None or not item.curve_points:
            return {'CANCELLED'}
        idx = max(0, min(item.curve_points_index, len(item.curve_points) - 1))
        item.curve_points.remove(idx)
        item.curve_points_index = min(idx, max(0, len(item.curve_points) - 1))
        return {'FINISHED'}


class REDENGINE_OT_curve_points_sort(bpy.types.Operator):
    bl_idname = 'redengine.curve_points_sort'
    bl_label = 'Sort Curve Points'
    bl_options = {'REGISTER', 'UNDO'}

    property_index: bpy.props.IntProperty()

    def execute(self, context):
        item = _active_curve_property(context, self.property_index)
        if item is None:
            return {'CANCELLED'}
        sort_curve_points(item)
        return {'FINISHED'}


class REDENGINE_OT_curve_points_reset(bpy.types.Operator):
    bl_idname = 'redengine.curve_points_reset'
    bl_label = 'Reset Curve From Import'
    bl_options = {'REGISTER', 'UNDO'}

    property_index: bpy.props.IntProperty()

    def execute(self, context):
        item = _active_curve_property(context, self.property_index)
        if item is None:
            return {'CANCELLED'}
        if not reset_curve_property_from_raw_json(item):
            self.report({'WARNING'}, 'The stored raw JSON is not a curveData payload')
            return {'CANCELLED'}
        return {'FINISHED'}


class REDENGINE_OT_curve_widget_init(bpy.types.Operator):
    bl_idname = 'redengine.curve_widget_init'
    bl_label = 'Initialize Native Curve Widget'
    bl_options = {'REGISTER', 'UNDO'}

    property_index: bpy.props.IntProperty()

    def execute(self, context):
        node = getattr(context, 'active_node', None)
        item = _active_curve_property(context, self.property_index)
        if node is None or item is None:
            return {'CANCELLED'}
        helper = curve_mapping.get_helper_node(node, item, create=True)
        if helper is None or not curve_mapping.sync_native_from_property(item, helper):
            self.report({'WARNING'}, 'Could not create the native Blender curve widget')
            return {'CANCELLED'}
        return {'FINISHED'}


class REDENGINE_OT_curve_widget_push(bpy.types.Operator):
    bl_idname = 'redengine.curve_widget_push'
    bl_label = 'Push Points To Native Curve'
    bl_options = {'REGISTER', 'UNDO'}

    property_index: bpy.props.IntProperty()

    def execute(self, context):
        node = getattr(context, 'active_node', None)
        item = _active_curve_property(context, self.property_index)
        if node is None or item is None:
            return {'CANCELLED'}
        helper = curve_mapping.get_helper_node(node, item, create=True)
        if helper is None or not curve_mapping.sync_native_from_property(item, helper):
            self.report({'WARNING'}, 'Could not update the native Blender curve widget')
            return {'CANCELLED'}
        return {'FINISHED'}


class REDENGINE_OT_curve_widget_apply(bpy.types.Operator):
    bl_idname = 'redengine.curve_widget_apply'
    bl_label = 'Apply Native Curve To REDengine Data'
    bl_options = {'REGISTER', 'UNDO'}

    property_index: bpy.props.IntProperty()

    def execute(self, context):
        node = getattr(context, 'active_node', None)
        item = _active_curve_property(context, self.property_index)
        if node is None or item is None:
            return {'CANCELLED'}
        helper = curve_mapping.get_helper_node(node, item, create=False)
        if helper is None or not curve_mapping.sync_property_from_native(item, helper):
            self.report({'WARNING'}, 'Could not read the native Blender curve widget')
            return {'CANCELLED'}
        return {'FINISHED'}


class REDENGINE_OT_curve_point_move(bpy.types.Operator):
    bl_idname = 'redengine.curve_point_move'
    bl_label = 'Move Curve Point'
    bl_options = {'REGISTER', 'UNDO'}

    property_index: bpy.props.IntProperty()
    direction: bpy.props.EnumProperty(
        items=(('UP', 'Up', ''), ('DOWN', 'Down', '')),
        default='UP',
    )

    def execute(self, context):
        item = _active_curve_property(context, self.property_index)
        if item is None or len(item.curve_points) < 2:
            return {'CANCELLED'}
        idx = max(0, min(item.curve_points_index, len(item.curve_points) - 1))
        new_idx = idx - 1 if self.direction == 'UP' else idx + 1
        if new_idx < 0 or new_idx >= len(item.curve_points):
            return {'CANCELLED'}
        item.curve_points.move(idx, new_idx)
        item.curve_points_index = new_idx
        return {'FINISHED'}


def _prop_by_key(owner, key: str):
    props = getattr(owner, 'red_properties', None)
    if not props:
        return None
    for item in props:
        if item.key == key:
            return item
    return None


def _variable_decl_for_node(owner):
    try:
        root = variable_bindings.root_tree_for(getattr(owner, 'id_data', None))
    except Exception:
        root = None
    if root is None:
        return None
    vt = variable_bindings.variable_type_for_node(owner)
    name = variable_bindings.node_variable_name(owner)
    for var in getattr(root, 'variables', []):
        if str(getattr(var, 'var_type', '')) == vt and str(getattr(var, 'name', '')) == name:
            return var
    return None


def _draw_variable_value_controls(layout, var):
    vt = str(getattr(var, 'var_type', ''))
    if vt == 'Bool':
        row = layout.row(align=True)
        row.prop(var, 'current_bool', text='Value')
        row.prop(var, 'default_bool', text='Default')
    elif vt == 'Int':
        row = layout.row(align=True)
        row.prop(var, 'current_int', text='Value')
        row.prop(var, 'default_int', text='Default')
    elif vt == 'Float':
        row = layout.row(align=True)
        row.prop(var, 'current_float', text='Value')
        row.prop(var, 'default_float', text='Default')
        if bool(getattr(var, 'has_float_range', False)):
            row = layout.row(align=True)
            row.label(text='Range')
            row.prop(var, 'min_float', text='Min')
            row.prop(var, 'max_float', text='Max')
    elif vt in {'Vector', 'Quaternion'}:
        labels = ('i', 'j', 'k', 'r') if vt == 'Quaternion' else ('X', 'Y', 'Z', 'W')
        row = layout.row(align=True)
        row.label(text='Value')
        for idx, label in enumerate(labels):
            row.prop(var, 'current_vector', index=idx, text=label)
        row = layout.row(align=True)
        row.label(text='Default')
        for idx, label in enumerate(labels):
            row.prop(var, 'default_vector', index=idx, text=label)
    else:
        layout.prop(var, 'current_value', text='Value')
        layout.prop(var, 'default_value', text='Default')


def _draw_variable_binding_box(owner, layout):
    typ = getattr(owner, 'red_type', '')
    if not typ.startswith('animAnimNode_') or not typ.endswith('Variable'):
        return
    if typ.endswith(('FloatVariable', 'IntVariable', 'BoolVariable', 'VectorVariable', 'QuaternionVariable', 'TransformVariable')) is False:
        return

    var = _variable_decl_for_node(owner)
    if var is None:
        name = ''
        try:
            name = variable_bindings.node_variable_name(owner)
        except Exception:
            pass
        box = layout.box()
        row = box.row(align=True)
        row.label(text=name or 'Variable', icon='UNLINKED')
        box.label(text='No matching graph variable declaration.', icon='INFO')
        return

    box = layout.box()
    row = box.row(align=True)
    row.label(text=str(getattr(var, 'name', '') or 'Variable'), icon='LINKED')
    _draw_variable_value_controls(box, var)


def _draw_dangle_particle_node(owner, layout):
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
        item = _prop_by_key(owner, key)
        if item is not None:
            _draw_scalar_target(item, sim_box, item.label or item.key)
            shown.add(key)

    cap_box = col.box()
    cap_box.label(text='Collision Capsule', icon='MESH_CAPSULE')
    any_cap = False
    for key in cap_keys:
        item = _prop_by_key(owner, key)
        if item is not None:
            _draw_scalar_target(item, cap_box, item.label or item.key)
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

    dbg_items = [item for key in debug_keys if (item := _prop_by_key(owner, key)) is not None]
    if dbg_items:
        dbg_box = col.box()
        dbg_box.label(text='Debug', icon='TOOL_SETTINGS')
        for item in dbg_items:
            _draw_scalar_target(item, dbg_box, item.label or item.key)
            shown.add(item.key)

    props = getattr(owner, 'red_properties', None)
    other = [item for item in props or [] if item.key not in shown]
    if other:
        other_box = col.box()
        other_box.label(text='Other Particle Fields', icon='PROPERTIES')
        for item in other:
            _draw_property_row(owner, other_box, item, -1)


def _draw_dangle_cone_constraint_node(owner, layout):
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
        item = _prop_by_key(owner, key)
        if item is not None:
            _draw_property_row(owner, geom_box, item, -1)
            shown.add(key)
            any_geom = True
    if not any_geom:
        geom_box.label(text='No cone parameter fields on this constraint.', icon='INFO')

    dbg_items = [item for key in debug_keys if (item := _prop_by_key(owner, key)) is not None]
    if dbg_items:
        dbg_box = col.box()
        dbg_box.label(text='Debug', icon='TOOL_SETTINGS')
        for item in dbg_items:
            _draw_scalar_target(item, dbg_box, item.label or item.key)
            shown.add(item.key)

    props = getattr(owner, 'red_properties', None)
    other = [item for item in props or [] if item.key not in shown]
    if other:
        other_box = col.box()
        other_box.label(text='Other Constraint Fields', icon='PROPERTIES')
        for item in other:
            _draw_property_row(owner, other_box, item, -1)

def _draw_node_properties(owner, layout):
    presenter_id = node_presenters.node_presenter_id(owner)
    if presenter_id == node_presenters.PRESENTER_VARIABLE_READER:
        _draw_variable_binding_box(owner, layout)
    if presenter_id == node_presenters.PRESENTER_DANGLE_PARTICLE:
        _draw_dangle_particle_node(owner, layout)
        return
    if presenter_id == node_presenters.PRESENTER_DANGLE_CONE:
        _draw_dangle_cone_constraint_node(owner, layout)
        return
    col = layout.column(align=True)
    col.label(text=f"ID {owner.red_handle_id}")
    if presenter_id and presenter_id != node_presenters.PRESENTER_GENERIC:
        col.label(text=f"Presenter: {node_presenters.presenter_info(presenter_id).label}", icon="PLUGIN")
    if getattr(owner, 'red_pseudo', False) or getattr(owner, 'red_parent_class', '') or getattr(owner, 'red_output_kind', ''):
        row = col.row(align=True)
        row.label(text=("Editor" if getattr(owner, 'red_pseudo', False) else "Runtime"), icon=('GHOST_ENABLED' if getattr(owner, 'red_pseudo', False) else 'NODE'))
        out_kind = getattr(owner, 'red_output_kind', '') or 'sink/editor'
        row.label(text=f"Out: {out_kind}")

    editor_names = []
    for suffix in ('a', 'b'):
        tree_name = getattr(owner, f'red_editor_subgraph_{suffix}_name', '')
        label = getattr(owner, f'red_editor_subgraph_{suffix}_label', '')
        if tree_name:
            editor_names.append((tree_name, label or tree_name))
    if editor_names:
        box = col.box()
        box.label(text='Editor Subgraphs', icon='NODETREE')
        for tree_name, label in editor_names:
            op = box.operator('redengine.enter_editor_subgraph', text=label, icon='NODETREE')
            op.tree_name = tree_name

    props = getattr(owner, 'red_properties', None)
    if not props:
        col.label(text="No editable properties.", icon='INFO')
        return

    box = col.box()
    header = box.row(align=True)
    header.label(text="REDengine Properties", icon='PROPERTIES')

    for index, item in enumerate(props):
        _draw_property_row(owner, box, item, index)


def _draw_vector_target(target, layout, label: str):
    row = layout.row(align=True)
    row.enabled = target.editable
    row.label(text=label)
    for idx, component in enumerate(_VECTOR_LABELS.get(target.value_kind, ())):
        row.prop(target, 'vector_value', index=idx, text=component)


def _draw_qstransform_target(target, layout, label: str):
    box = layout.box()
    header = box.row(align=True)
    icon = 'TRIA_DOWN' if target.expanded else 'TRIA_RIGHT'
    header.prop(target, 'expanded', text='', icon=icon, emboss=False)
    header.label(text=label, icon='EMPTY_AXIS')
    if not target.expanded:
        return
    col = box.column(align=True)
    col.enabled = target.editable
    for prop_name, title in (('qs_translation', 'Translation'), ('qs_rotation', 'Rotation'), ('qs_scale', 'Scale')):
        row = col.row(align=True)
        row.label(text=title)
        for idx, component in enumerate(_QS_VEC_LABELS[prop_name]):
            row.prop(target, prop_name, index=idx, text=component)


def _draw_scalar_target(target, layout, label: str):
    kind = target.value_kind
    if kind in {'VECTOR2', 'VECTOR3', 'VECTOR4', 'QUATERNION', 'FLOAT_CLAMP'}:
        _draw_vector_target(target, layout, label)
        return
    if kind == 'QSTRANSFORM':
        _draw_qstransform_target(target, layout, label)
        return

    row = layout.row(align=True)
    row.enabled = target.editable
    if kind == 'BOOL':
        row.prop(target, 'bool_value', text=label)
    elif kind == 'INT':
        row.prop(target, 'int_value', text=label)
    elif kind == 'UINT':
        row.prop(target, 'string_value', text=label)
    elif kind == 'FLOAT':
        row.prop(target, 'float_value', text=label)
    elif kind == 'ENUM':
        enum_type = getattr(target, 'enum_type', '') or getattr(target, 'red_type', '')
        if rtti_schema is not None and enum_type and rtti_schema.has_enum(enum_type):
            row.prop(target, 'enum_choice', text=label)
            if getattr(target, 'enum_choice', '') == '__RAW__':
                raw = layout.row(align=True)
                raw.enabled = target.editable
                raw.prop(target, 'string_value', text='Raw')
        else:
            row.prop(target, 'string_value', text=label)
    elif kind == 'FLAGS_ENUM':
        enum_type = getattr(target, 'enum_type', '') or getattr(target, 'red_type', '')
        row.prop(target, 'string_value', text=label)
    elif kind in {'STRING', 'CNAME', 'TRANSFORM_INDEX', 'NAMED_TRACK_INDEX', 'VISUAL_TAG_CONDITION'}:
        row.prop(target, 'string_value', text=label)
    elif kind == 'NULL':
        row.label(text=label, icon='RADIOBUT_OFF')
    elif kind == 'RAW_JSON':
        icon = 'TRIA_DOWN' if target.expanded else 'TRIA_RIGHT'
        row.prop(target, 'expanded', text='', icon=icon, emboss=False)
        row.label(text=label)
        if target.expanded:
            sub = layout.column(align=True)
            sub.enabled = target.editable
            sub.prop(target, 'raw_json', text='')
    else:
        row.label(text=label, icon='ERROR')


def _node_property_text(owner, key: str) -> str:
    for prop in getattr(owner, 'red_properties', ()):
        if getattr(prop, 'key', '') == key:
            return str(getattr(prop, 'string_value', '') or '')
    return ''


def _draw_math_expression_editor(owner, layout, item: REDengine_AnimNodeProperty, label: str):
    box = layout.box()
    header = box.row(align=True)
    icon = 'TRIA_DOWN' if item.expanded else 'TRIA_RIGHT'
    header.prop(item, 'expanded', text='', icon=icon, emboss=False)
    header.label(text=label, icon='SCRIPT')

    if not item.expanded:
        return

    try:
        payload = json.loads(getattr(item, 'raw_json', '') or '{}')
    except Exception:
        payload = {}
    expression_string = _node_property_text(owner, 'expressionString')
    parsed = math_expression.parse_expression_data(payload, expression_string=expression_string) if math_expression is not None else {}

    col = box.column(align=True)
    formula = str(parsed.get('expressionString', '') or '')
    if formula:
        col.label(text=f'Formula: {formula}')
    return_type = str(parsed.get('returnType', '') or '')
    if return_type:
        col.label(text=f'Return: {return_type}')
    col.label(text=f"Tokens: {int(parsed.get('tokenCount', 0) or 0)}")
    col.label(text=f"Values: {int(parsed.get('valueCount', 0) or 0)}")
    inputs = len(parsed.get('sockets', []) or [])
    col.label(text=f'Inputs: {inputs}')

def _draw_array_editor(owner, layout, item: REDengine_AnimNodeProperty, index: int, label: str):
    box = layout.box()
    header = box.row(align=True)
    icon = 'TRIA_DOWN' if item.expanded else 'TRIA_RIGHT'
    header.prop(item, 'expanded', text='', icon=icon, emboss=False)
    header.label(text=label, icon='LINENUMBERS_ON')

    if not item.expanded:
        return

    for element_index, element in enumerate(item.array_items):
        elem_box = box.box()
        row = elem_box.row(align=True)
        eicon = 'TRIA_DOWN' if element.expanded else 'TRIA_RIGHT'
        row.prop(element, 'expanded', text='', icon=eicon, emboss=False)
        row.label(text=f"[{element_index}]")
        if not element.expanded:
            continue
        if element.fields:
            col = elem_box.column(align=True)
            for field in element.fields:
                _draw_scalar_target(field, col, field.label or field.key)
        else:
            elem_box.prop(element, 'raw_json', text='Raw JSON')


def _draw_struct_editor(layout, item, label: str):
    box = layout.box()
    header = box.row(align=True)
    icon = 'TRIA_DOWN' if item.expanded else 'TRIA_RIGHT'
    header.prop(item, 'expanded', text='', icon=icon, emboss=False)
    header.label(text=label, icon='OUTLINER_OB_EMPTY')
    elements = list(getattr(item, 'array_items', ()))
    element = elements[0] if elements else None
    if not item.expanded:
        return
    if element is None:
        box.prop(item, 'raw_json', text='Raw JSON')
        return
    if element.fields:
        col = box.column(align=True)
        for field in element.fields:
            _draw_scalar_target(field, col, field.label or field.key)
    else:
        box.label(text='No editable fields decoded; raw JSON is preserved.', icon='INFO')
        box.prop(element, 'raw_json', text='Raw JSON')


def _draw_property_row(owner, layout, item: REDengine_AnimNodeProperty, index: int):
    kind = item.value_kind
    label = item.label or item.key

    if kind == 'CURVE_FLOAT':
        _draw_curve_editor(owner, layout, item, index, label)
        return
    if kind == 'ARRAY':
        _draw_array_editor(owner, layout, item, index, label)
        return
    if kind in {'STRUCT', 'HANDLE_STRUCT'}:
        _draw_struct_editor(layout, item, label)
        return
    if kind == 'MATH_EXPRESSION':
        _draw_math_expression_editor(owner, layout, item, label)
        return
    _draw_scalar_target(item, layout, label)


def _draw_curve_editor(owner, layout, item: REDengine_AnimNodeProperty, index: int, label: str):
    box = layout.box()
    header = box.row(align=True)
    icon = 'TRIA_DOWN' if item.expanded else 'TRIA_RIGHT'
    header.prop(item, 'expanded', text='', icon=icon, emboss=False)
    header.label(text=label, icon='FCURVE')

    if not item.expanded:
        return

    meta = box.column(align=True)
    meta.enabled = item.editable
    row = meta.row(align=True)
    row.prop(item, 'curve_interpolation_type', text='Interpolation')
    row.prop(item, 'curve_link_type', text='Link Type')


    helper = curve_mapping.get_helper_node(owner, item, create=False) if owner is not None else None
    widget_box = box.box()
    widget_header = widget_box.row(align=True)
    widget_header.label(text='Native Blender Float Curve', icon='IPO_BEZIER')
    if helper is not None:
        push = widget_header.operator('redengine.curve_widget_push', text='Push Points', icon='EXPORT')
        push.property_index = index
        apply = widget_header.operator('redengine.curve_widget_apply', text='Apply Widget', icon='IMPORT')
        apply.property_index = index
        try:
            widget_box.template_curve_mapping(helper, 'mapping')
        except Exception as exc:
            widget_box.label(text=f'Curve widget unavailable: {exc}', icon='ERROR')
        hint = widget_box.row(align=True)
        hint.label(text='Use Apply Widget after editing the native curve to update REDengine Elements[].', icon='INFO')
    else:
        init = widget_header.operator('redengine.curve_widget_init', text='Initialize Widget', icon='ADD')
        init.property_index = index
        widget_box.label(text='Native curve helper has not been created yet.', icon='INFO')
        widget_box.label(text='Click Initialize Widget or re-import to build it outside the draw callback.')

    split = box.split(factor=0.86)
    split.template_list(
        'REDENGINE_UL_curve_points',
        '',
        item,
        'curve_points',
        item,
        'curve_points_index',
        rows=min(8, max(3, len(item.curve_points))),
    )
    buttons = split.column(align=True)
    add = buttons.operator('redengine.curve_point_add', text='', icon='ADD')
    add.property_index = index
    remove = buttons.operator('redengine.curve_point_remove', text='', icon='REMOVE')
    remove.property_index = index
    buttons.separator()
    up = buttons.operator('redengine.curve_point_move', text='', icon='TRIA_UP')
    up.property_index = index
    up.direction = 'UP'
    down = buttons.operator('redengine.curve_point_move', text='', icon='TRIA_DOWN')
    down.property_index = index
    down.direction = 'DOWN'
    buttons.separator()
    sort_op = buttons.operator('redengine.curve_points_sort', text='', icon='SORT_ASC')
    sort_op.property_index = index
    reset = buttons.operator('redengine.curve_points_reset', text='', icon='LOOP_BACK')
    reset.property_index = index

    if item.curve_points:
        xs = [float(p.point) for p in item.curve_points]
        ys = [float(p.value) for p in item.curve_points]
        footer = box.row(align=True)
        footer.label(text=f"Point range: {min(xs):g} .. {max(xs):g}")
        footer.label(text=f"Value range: {min(ys):g} .. {max(ys):g}")


def _draw_math_expression_node_box(node, layout):
    return


class REDengine_AnimGraphNode_Generic(bpy.types.Node):
    bl_idname = 'REDengine_AnimGraphNode_Generic'
    bl_label = "AnimGraph Node"

    red_type: bpy.props.StringProperty(name="Node Type")
    red_handle_id: bpy.props.StringProperty(name="Handle ID")
    red_exportable: bpy.props.BoolProperty(name="Exportable", default=True)
    red_pseudo: bpy.props.BoolProperty(name="Editor Node", default=False)
    red_parent_class: bpy.props.StringProperty(name="Parent Class")
    red_output_kind: bpy.props.StringProperty(name="Output Kind")
    red_presenter: bpy.props.StringProperty(name="Presenter", default="generic")
    red_metadata_known: bpy.props.BoolProperty(name="Metadata Known", default=False)
    red_roundtrip_ready: bpy.props.BoolProperty(name="Roundtrip Ready", default=False)
    red_roundtrip_notes: bpy.props.StringProperty(name="Roundtrip Notes")
    red_layout_auto: bpy.props.BoolProperty(name="Auto Layout", default=True)
    red_layout_locked: bpy.props.BoolProperty(name="Layout Locked", default=False)
    red_editor_subgraph_a_name: bpy.props.StringProperty(name="Editor Subgraph A")
    red_editor_subgraph_a_label: bpy.props.StringProperty(name="Editor Subgraph A Label")
    red_editor_subgraph_b_name: bpy.props.StringProperty(name="Editor Subgraph B")
    red_editor_subgraph_b_label: bpy.props.StringProperty(name="Editor Subgraph B Label")
    red_properties: bpy.props.CollectionProperty(type=REDengine_AnimNodeProperty)
    red_properties_index: bpy.props.IntProperty(name="Property")

    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == ANIMGRAPH_TREE_ID

    def init(self, context):
        pass

    def draw_buttons(self, context, layout):
        _draw_math_expression_node_box(self, layout)
        _draw_node_properties(self, layout)


class REDengine_AnimGraphContainer(bpy.types.NodeCustomGroup):
    bl_idname = 'REDengine_AnimGraphContainer'
    bl_label = "AnimGraph Container"

    red_type: bpy.props.StringProperty(name="Node Type")
    red_handle_id: bpy.props.StringProperty(name="Handle ID")
    red_exportable: bpy.props.BoolProperty(name="Exportable", default=True)
    red_pseudo: bpy.props.BoolProperty(name="Editor Node", default=False)
    red_parent_class: bpy.props.StringProperty(name="Parent Class")
    red_output_kind: bpy.props.StringProperty(name="Output Kind")
    red_presenter: bpy.props.StringProperty(name="Presenter", default="generic")
    red_metadata_known: bpy.props.BoolProperty(name="Metadata Known", default=False)
    red_roundtrip_ready: bpy.props.BoolProperty(name="Roundtrip Ready", default=False)
    red_roundtrip_notes: bpy.props.StringProperty(name="Roundtrip Notes")
    red_layout_auto: bpy.props.BoolProperty(name="Auto Layout", default=True)
    red_layout_locked: bpy.props.BoolProperty(name="Layout Locked", default=False)
    red_editor_subgraph_a_name: bpy.props.StringProperty(name="Editor Subgraph A")
    red_editor_subgraph_a_label: bpy.props.StringProperty(name="Editor Subgraph A Label")
    red_editor_subgraph_b_name: bpy.props.StringProperty(name="Editor Subgraph B")
    red_editor_subgraph_b_label: bpy.props.StringProperty(name="Editor Subgraph B Label")
    red_properties: bpy.props.CollectionProperty(type=REDengine_AnimNodeProperty)
    red_properties_index: bpy.props.IntProperty(name="Property")

    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == ANIMGRAPH_TREE_ID

    def draw_buttons(self, context, layout):
        enter = layout.operator("redengine.enter_group", text="Enter Subgraph", icon='NODETREE')
        enter.node_name = self.name
        _draw_math_expression_node_box(self, layout)
        _draw_node_properties(self, layout)


curve_editor_classes = (
    REDENGINE_OT_enter_editor_subgraph,
    REDENGINE_UL_curve_points,
    REDENGINE_OT_curve_point_add,
    REDENGINE_OT_curve_point_remove,
    REDENGINE_OT_curve_points_sort,
    REDENGINE_OT_curve_points_reset,
    REDENGINE_OT_curve_widget_init,
    REDENGINE_OT_curve_widget_push,
    REDENGINE_OT_curve_widget_apply,
    REDENGINE_OT_curve_point_move,
)
