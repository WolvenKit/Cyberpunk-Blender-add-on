class animAnimNode_Pose(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Pose'
    bl_label = "Pose"
    
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
   
   def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")