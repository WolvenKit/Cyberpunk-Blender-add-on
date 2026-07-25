import bpy

from .properties import REDengine_AnimVariable, REDengine_AnimFeature


class REDengine_AnimGraphTree(bpy.types.NodeTree):
    bl_idname = 'REDengine_AnimGraphTree'
    bl_label = "REDengine AnimGraph"
    bl_icon = 'ACTION'

    variables: bpy.props.CollectionProperty(type=REDengine_AnimVariable)
    variables_index: bpy.props.IntProperty()
    red_variable_sync_suspended: bpy.props.BoolProperty(default=False, options={'HIDDEN'})
    features: bpy.props.CollectionProperty(type=REDengine_AnimFeature)
    features_index: bpy.props.IntProperty()
    inputs_tab: bpy.props.EnumProperty(
        name='Inputs Tab',
        description='Active Inputs panel tab',
        items=(
            ('VARIABLES', 'Variables', 'Graph variable declarations'),
            ('FEATURES', 'Features', 'Anim feature declarations'),
        ),
        default='VARIABLES',
        options={'HIDDEN'},
    )


    variables_bool_expanded: bpy.props.BoolProperty(name='Bool Variables Expanded', default=True, options={'HIDDEN'})
    variables_int_expanded: bpy.props.BoolProperty(name='Int Variables Expanded', default=True, options={'HIDDEN'})
    variables_float_expanded: bpy.props.BoolProperty(name='Float Variables Expanded', default=True, options={'HIDDEN'})
    variables_vector_expanded: bpy.props.BoolProperty(name='Vector Variables Expanded', default=True, options={'HIDDEN'})
    variables_quaternion_expanded: bpy.props.BoolProperty(name='Quaternion Variables Expanded', default=True, options={'HIDDEN'})
    variables_transform_expanded: bpy.props.BoolProperty(name='Transform Variables Expanded', default=True, options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return True
