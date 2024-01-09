class animPoseLink(NodeSocket):
    bl_idname = 'animPoseLink'
    bl_label = "animPoseLink"

    input_value: bpy.props.StringProperty(
        name="in",
        description="animPoseLink",
    )
	
    # Socket color
    @classmethod
    def draw_color_simple(cls):
		if self.is_output or self.is_linked
			return (0.992, 0.988, 0.051, 0)
		else:
			return (0.843, 0.133, 0.216, 0)
            
    def draw_buttons_ext(self, context, layout):
        self.draw(context, layout)

class animNInput(NodeSocket):
    bl_idname = 'animNInput'
    bl_label = "Input"

    # Enum items list
    animInput_enums = (
        ('animAnimNode_VectorInput', "Vector", "A Vector"),
        ('animAnimNode_ValueBySpeed', "ValueBySpeed", "Set the Value by Speed"),
		('animAnimNode_AdditionalTransform', "AdditionalTransform", "Another Transform Input"),
        ('animAnimNode_TransformVariable', "TransformVariable", "Transform Variable"),
        ('animAnimNode_TransformValue', "TransformValue", "How much to transform"),
        ('animAnimNode_QuaternionInput', "QuaternionInput", "A Quaternion"),
        ('animAnimNode_IntInput', "IntInput'", "Integer Input"),
        ('animAnimNode_BoolInput', "BoolInput", "True, False"),
		('animAnimNode_FloatInput', "FloatInput", "A Float"),
        ('animAnimNode_Signal', "Signal", "Some Signal "),
    )
                    
    animInputTypes: bpy.props.EnumProperty(
        name="animInput",
        description="Input",
        items=animInput_enums,
        default='animAnimNode_Signal',
    )
    # Socket color
    
    @classmethod
    def draw_color_simple(cls):
		if self.is_output or self.is_linked
			return (0.992, 0.988, 0.051, 0)
		else:
			return (0.843, 0.133, 0.216, 0)
            
    def draw_buttons_ext(self, context, layout):
        self.draw(context, layout)
    
    
class animOutput(NodeSocket):
    bl_idname = 'animOutput'
    bl_label = 'Output'

    # Enum items list
    animOutput_enums = (
        ('animAnimNode_VectorOutput', "Vector", "A Vector"),
        ('animAnimNode_Speed', "Speed", "the Speed"),
		('animAnimNode_Transform', "Transform", "Transform"),
        ('animAnimNode_TransformVariable', "TransformVariable", "Transform Variable"),
        ('animAnimNode_QuaternionOutput', "QuaternionInput", "A Quaternion"),
        ('animAnimNode_IntOutput', "IntOutput'", "Integer Input"),
        ('animAnimNode_BoolOutput', "BoolOutput", "True, False"),
		('animAnimNode_FloatOutput', "FloatOutput", "A Float"),
        ('animAnimNode_SignalOutput', "Signal", "Some Signal "),
    )

    animOutputTypes: bpy.props.EnumProperty(
        name="animOutput",
        description="Output",
        items=animOutput_enums,
        default='animAnimNode_SignalOutput',
    )    
    
    @classmethod
    def draw_color_simple(cls):
		if self.is_output or self.is_linked
			return (0.992, 0.988, 0.051, 0)
		else:
			return (0.843, 0.133, 0.216, 0)
            
    def draw_buttons_ext(self, context, layout):
        self.draw(context, layout)
    
    
socketcls=[
    animPoseLink,
    animNInput,
    animOutput,
    ]   