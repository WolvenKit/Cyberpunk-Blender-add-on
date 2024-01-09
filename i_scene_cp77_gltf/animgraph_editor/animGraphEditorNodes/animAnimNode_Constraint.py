
class animAnimNode_Constraint(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Constraint'
    bl_label = "Constraint"
    
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
   
   def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")

        # "var isSourceTransformResaved": "Bool;",
        # "var sourceTransformIndex": "animTransformIndex;",
        # "var transformIndex": "animTransformIndex;",
        # "var posX": "Bool;",
        # "var posY": "Bool;",
        # "var posZ": "Bool;",
        # "var rotX": "Bool;",
        # "var rotY": "Bool;",
        # "var rotZ": "Bool;",
        # "var scaleX": "Bool;",
        # "var scaleY": "Bool;",
        # "var scaleZ": "Bool;",
        # "var weight": "Float;",
        # "var weightNode": "animFloatLink;",
        # "var inputLink": "animPoseLink;",
        # "var id": "Uint32;"