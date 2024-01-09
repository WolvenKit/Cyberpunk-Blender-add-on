class animAnimNode_Latch(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Latch'
    bl_label = "Latch"
    
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
   
   def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")