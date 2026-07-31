import bpy

from ...animation.animgraph.schema import rtti

NODE_VALUE_KIND_ITEMS = (
    ('BOOL', 'Bool', 'Boolean value'),
    ('INT', 'Int', 'Integer value'),
    ('UINT', 'Unsigned Int', 'Unsigned integer stored losslessly as text to avoid Blender signed IntProperty limits'),
    ('FLOAT', 'Float', 'Floating-point value'),
    ('STRING', 'String', 'Plain string'),
    ('CNAME', 'CName', 'REDengine CName'),
    ('ENUM', 'Enum', 'REDengine enum value'),
    ('FLAGS_ENUM', 'Flags Enum', 'REDengine bitflag enum value'),
    ('TRANSFORM_INDEX', 'Transform Index', 'animTransformIndex bone reference'),
    ('NAMED_TRACK_INDEX', 'Named Track Index', 'animNamedTrackIndex float-track reference'),
    ('VISUAL_TAG_CONDITION', 'Visual Tag', 'animVisualTagCondition'),
    ('VECTOR2', 'Vector2', 'Two-component vector'),
    ('VECTOR3', 'Vector3', 'Three-component vector'),
    ('VECTOR4', 'Vector4', 'Four-component vector'),
    ('QUATERNION', 'Quaternion', 'Quaternion stored as i, j, k, r'),
    ('QSTRANSFORM', 'QsTransform', 'Translation / rotation / scale transform'),
    ('FLOAT_CLAMP', 'Float Clamp', 'animFloatClamp min/max pair'),
    ('CURVE_FLOAT', 'Float Curve', 'Curve data with editable point/value keys'),
    ('ARRAY', 'Typed Array', 'Editable array of primitive/simple REDengine values'),
    ('STRUCT', 'Struct', 'RTTI-owned structured payload'),
    ('HANDLE_STRUCT', 'Handle Struct', 'RTTI-owned handled payload with HandleId/HandleRefId'),
    ('MATH_EXPRESSION', 'Math Expression', 'Compiled animMathExpressionNodeData payload'),
    ('NULL', 'Null', 'Explicit null value'),
    ('RAW_JSON', 'Raw JSON', 'Unsupported complex value retained as JSON'),
)

def _on_anim_variable_updated(self, context):
    try:
        from . import variables
        variables.on_variable_value_updated(self, context)
    except Exception:

        pass

def _enum_choice_items(self, context):
    enum_type = getattr(self, 'enum_type', '') or getattr(self, 'red_type', '')
    if rtti is None:
        return [('__RAW__', 'Raw / unknown', 'Enum registry unavailable')]
    try:
        return rtti.enum_items(enum_type, include_sentinel=False)
    except Exception:
        return [('__RAW__', 'Raw / unknown', 'Enum registry error')]

def _on_enum_choice_updated(self, context):
    choice = getattr(self, 'enum_choice', '')
    if not choice or choice == '__RAW__':
        return
    try:
        self.string_value = str(choice)
        enum_type = getattr(self, 'enum_type', '') or getattr(self, 'red_type', '')
        if rtti is not None:
            value = rtti.enum_value_for_name(enum_type, choice)
            if value is not None:
                self.enum_raw_value = str(value)
    except Exception:
        pass

class REDengine_AnimCurvePoint(bpy.types.PropertyGroup):

    point: bpy.props.FloatProperty(name='Point')
    value: bpy.props.FloatProperty(name='Value')
    selected: bpy.props.BoolProperty(name='Selected', default=False)

class REDengine_AnimArrayField(bpy.types.PropertyGroup):
    key: bpy.props.StringProperty(name='Key')
    label: bpy.props.StringProperty(name='Label')
    red_type: bpy.props.StringProperty(name='REDengine Type')
    value_kind: bpy.props.EnumProperty(name='Kind', items=NODE_VALUE_KIND_ITEMS, default='STRING')
    editable: bpy.props.BoolProperty(name='Editable', default=True)
    expanded: bpy.props.BoolProperty(name='Expanded', default=False)

    bool_value: bpy.props.BoolProperty(name='Value')
    int_value: bpy.props.IntProperty(name='Value')
    float_value: bpy.props.FloatProperty(name='Value')
    string_value: bpy.props.StringProperty(name='Value')
    enum_type: bpy.props.StringProperty(name='Enum Type')
    enum_choice: bpy.props.EnumProperty(name='Value', items=_enum_choice_items, update=_on_enum_choice_updated)
    enum_storage: bpy.props.StringProperty(name='Enum Storage', default='name')
    enum_raw_value: bpy.props.StringProperty(name='Enum Raw Value')
    vector_value: bpy.props.FloatVectorProperty(name='Value', size=4)
    vector_size: bpy.props.IntProperty(name='Vector Size', default=4, min=0, max=4)
    qs_translation: bpy.props.FloatVectorProperty(name='Translation', size=4, default=(0.0, 0.0, 0.0, 1.0))
    qs_rotation: bpy.props.FloatVectorProperty(name='Rotation', size=4, default=(0.0, 0.0, 0.0, 1.0))
    qs_scale: bpy.props.FloatVectorProperty(name='Scale', size=4, default=(1.0, 1.0, 1.0, 1.0))
    raw_json: bpy.props.StringProperty(name='Raw JSON')
    struct_handle_id: bpy.props.StringProperty(name='Struct HandleId')
    struct_ref_id: bpy.props.StringProperty(name='Struct HandleRefId')

class REDengine_AnimArrayElement(bpy.types.PropertyGroup):
    label: bpy.props.StringProperty(name='Label')
    red_type: bpy.props.StringProperty(name='REDengine Type')
    raw_json: bpy.props.StringProperty(name='Raw JSON')
    summary: bpy.props.StringProperty(name='Summary')
    expanded: bpy.props.BoolProperty(name='Expanded', default=False)
    fields: bpy.props.CollectionProperty(type=REDengine_AnimArrayField)
    fields_index: bpy.props.IntProperty(name='Field Index', default=0)

class REDengine_AnimNodeProperty(bpy.types.PropertyGroup):
    key: bpy.props.StringProperty(name='Key')
    label: bpy.props.StringProperty(name='Label')
    json_path: bpy.props.StringProperty(name='JSON Path')
    red_type: bpy.props.StringProperty(name='REDengine Type')
    value_kind: bpy.props.EnumProperty(name='Kind', items=NODE_VALUE_KIND_ITEMS, default='STRING')
    editable: bpy.props.BoolProperty(name='Editable', default=True)
    expanded: bpy.props.BoolProperty(name='Expanded', default=False)

    bool_value: bpy.props.BoolProperty(name='Value')
    int_value: bpy.props.IntProperty(name='Value')
    float_value: bpy.props.FloatProperty(name='Value')
    string_value: bpy.props.StringProperty(name='Value')
    enum_type: bpy.props.StringProperty(name='Enum Type')
    enum_choice: bpy.props.EnumProperty(name='Value', items=_enum_choice_items, update=_on_enum_choice_updated)
    enum_storage: bpy.props.StringProperty(name='Enum Storage', default='name')
    enum_raw_value: bpy.props.StringProperty(name='Enum Raw Value')
    vector_value: bpy.props.FloatVectorProperty(name='Value', size=4)
    vector_size: bpy.props.IntProperty(name='Vector Size', default=4, min=0, max=4)
    qs_translation: bpy.props.FloatVectorProperty(name='Translation', size=4, default=(0.0, 0.0, 0.0, 1.0))
    qs_rotation: bpy.props.FloatVectorProperty(name='Rotation', size=4, default=(0.0, 0.0, 0.0, 1.0))
    qs_scale: bpy.props.FloatVectorProperty(name='Scale', size=4, default=(1.0, 1.0, 1.0, 1.0))
    raw_json: bpy.props.StringProperty(name='Raw JSON')
    struct_handle_id: bpy.props.StringProperty(name='Struct HandleId')
    struct_ref_id: bpy.props.StringProperty(name='Struct HandleRefId')

    curve_interpolation_type: bpy.props.StringProperty(name='Interpolation', default='BezierCubic')
    curve_link_type: bpy.props.StringProperty(name='Link Type', default='ESLT_Normal')
    curve_points: bpy.props.CollectionProperty(type=REDengine_AnimCurvePoint)
    curve_points_index: bpy.props.IntProperty(name='Point Index', default=0)
    curve_helper_node: bpy.props.StringProperty(name='Curve Helper Node')
    curve_widget_initialized: bpy.props.BoolProperty(name='Native Curve Initialized', default=False)
    curve_widget_dirty: bpy.props.BoolProperty(name='Native Curve Dirty', default=False)

    array_element_type: bpy.props.StringProperty(name='Array Element Type')
    array_items: bpy.props.CollectionProperty(type=REDengine_AnimArrayElement)
    array_items_index: bpy.props.IntProperty(name='Array Item Index', default=0)

class REDengine_AnimVariable(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name", update=_on_anim_variable_updated)
    handle_id: bpy.props.StringProperty(name="Handle ID")
    var_type: bpy.props.StringProperty(name="Type")
    source_array: bpy.props.StringProperty(name="Source Array")
    value_kind: bpy.props.StringProperty(name="Kind")


    default_value: bpy.props.StringProperty(name="Default")
    current_value: bpy.props.StringProperty(name="Value")
    default_json: bpy.props.StringProperty(name="Default JSON")
    current_json: bpy.props.StringProperty(name="Value JSON")
    raw_json: bpy.props.StringProperty(name="Raw JSON")

    default_bool: bpy.props.BoolProperty(name="Default", update=_on_anim_variable_updated)
    current_bool: bpy.props.BoolProperty(name="Value", update=_on_anim_variable_updated)
    default_int: bpy.props.IntProperty(name="Default", update=_on_anim_variable_updated)
    current_int: bpy.props.IntProperty(name="Value", update=_on_anim_variable_updated)
    default_float: bpy.props.FloatProperty(name="Default", update=_on_anim_variable_updated)
    current_float: bpy.props.FloatProperty(name="Value", update=_on_anim_variable_updated)
    min_float: bpy.props.FloatProperty(name="Min", update=_on_anim_variable_updated)
    max_float: bpy.props.FloatProperty(name="Max", update=_on_anim_variable_updated)
    has_float_range: bpy.props.BoolProperty(name="Has Float Range", default=False)
    default_vector: bpy.props.FloatVectorProperty(name="Default", size=4, update=_on_anim_variable_updated)
    current_vector: bpy.props.FloatVectorProperty(name="Value", size=4, update=_on_anim_variable_updated)

    enable_debug: bpy.props.BoolProperty(name="Debug", update=_on_anim_variable_updated)
    expanded: bpy.props.BoolProperty(name="Expanded", default=False)
    bound_name: bpy.props.StringProperty(name="Bound Name")
    consumer_count: bpy.props.IntProperty(name="Consumers", default=0)
    consumer_handles: bpy.props.StringProperty(name="Consumer Handles")

class REDengine_AnimFeature(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name")
    class_name: bpy.props.StringProperty(name="Class")
    debug_enabled: bpy.props.BoolProperty(name="Debug")
    force_allocate: bpy.props.BoolProperty(name="Force Allocate")
