class animAnimNode_Output(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Output'
    bl_label = "Output"
    
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
   
   def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")