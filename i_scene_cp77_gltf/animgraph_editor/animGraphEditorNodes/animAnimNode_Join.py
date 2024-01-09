class animAnimNode_Join(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Join'
    bl_label = "Join"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
class animAnimNode_Latch(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Latch'
    bl_label = "Latch"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
        
class animAnimNode_Convert(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Convert'
    bl_label = "Convert"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
class animAnimNode_Event(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Event'
    bl_label = "Event"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
class animAnimNode_animsomethingsomething(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_animsomethingsomething'
    bl_label = "animsomethingsomething"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
class animAnimNode_Workspots(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Workspots'
    bl_label = "Workspot"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
class animAnimNode_statemachine(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_statemachine'
    bl_label = "statemachine"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
class animAnimNode_fpp(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_fpp'
    bl_label = "fpp"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
class animAnimNode_Curves(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Curves'
    bl_label = "Curves"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
class animAnimNode_Interpolation(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Interpolation'
    bl_label = "Interpolation"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
class animAnimNode_Transform(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Transform'
    bl_label = "Transform"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
class animAnimNode_Bone(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Bone'
    bl_label = "Bone"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
class animAnimNode_Locoomotion(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Locoomotion'
    bl_label = "Locoomotion"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")

class animAnimNode_MathExpression(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_MathExpression'
    bl_label = "MathExpression"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
class animAnimNode_Track(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Track'
    bl_label = "Track"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
class animAnimNode_SetDrivenKey(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_SetDrivenKey'
    bl_label = "SetDrivenKey"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
class animAnimNode_Float(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Float'
    bl_label = "Float"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")	
		
class animAnimNode_Stack(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Stack'
    bl_label = "Stack"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
class animAnimNode_IK(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_IK'
    bl_label = "IK"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
class animAnimNode_Switch(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Switch'
    bl_label = "Switch"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")				

class animAnimNode_Sync(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Sync'
    bl_label = "Sync"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")				
					   
class animNodeCategories(NodeCategory):
    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == 'animgraphEditorNode'