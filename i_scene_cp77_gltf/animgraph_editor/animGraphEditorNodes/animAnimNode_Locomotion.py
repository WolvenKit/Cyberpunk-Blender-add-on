class animAnimNode_Locoomotion(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Locoomotion'
    bl_label = "Locoomotion"
    
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
   
   def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
        # "var targetPosition": "animVectorLink;",
        # "var targetDirection": "animVectorLink;",
        # "var initialForwardVector": "Vector4;",
        # "var blendSpeedPos": "Float;",
        # "var blendSpeedPosMin": "Float;",
        # "var blendSpeedRot": "Float;",
        # "var maxDistance": "Float;",
        # "var inputLink": "animPoseLink;",
        # "var id": "Uint32;"