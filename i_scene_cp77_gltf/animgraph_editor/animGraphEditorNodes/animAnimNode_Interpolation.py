class animAnimNode_Interpolation(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Interpolation'
    bl_label = "Interpolation"
    
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
   
   def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")