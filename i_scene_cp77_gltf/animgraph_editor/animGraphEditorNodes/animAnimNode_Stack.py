class animAnimNode_Stack(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Stack'
    bl_label = "Stack"
    
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
   
   def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")