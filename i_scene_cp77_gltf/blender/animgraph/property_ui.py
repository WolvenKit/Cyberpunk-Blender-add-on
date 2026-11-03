import json

from . import curve_mapping
from .properties import REDengine_AnimNodeProperty
from ...animation.animgraph.model import math_expression
from ...animation.animgraph.schema import rtti

_VECTOR_LABELS = {
    "VECTOR2": ("X", "Y"),
    "VECTOR3": ("X", "Y", "Z"),
    "VECTOR4": ("X", "Y", "Z", "W"),
    "QUATERNION": ("i", "j", "k", "r"),
    "FLOAT_CLAMP": ("Min", "Max"),
}

_QS_VEC_LABELS = {
    "qs_translation": ("X", "Y", "Z", "W"),
    "qs_rotation": ("i", "j", "k", "r"),
    "qs_scale": ("X", "Y", "Z", "W"),
}

def property_by_key(owner, key: str):
    props = getattr(owner, 'red_properties', None)
    if not props:
        return None
    for item in props:
        if item.key == key:
            return item
    return None

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

def draw_scalar_target(target, layout, label: str):
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
        if rtti is not None and enum_type and rtti.has_enum(enum_type):
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
                draw_scalar_target(field, col, field.label or field.key)
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
            draw_scalar_target(field, col, field.label or field.key)
    else:
        box.label(text='No editable fields decoded; raw JSON is preserved.', icon='INFO')
        box.prop(element, 'raw_json', text='Raw JSON')

def draw_property_row(owner, layout, item: REDengine_AnimNodeProperty, index: int):
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
    draw_scalar_target(item, layout, label)

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
