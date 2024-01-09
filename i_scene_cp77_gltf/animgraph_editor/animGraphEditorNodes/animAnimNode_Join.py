class animAnimNode_Join(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Join'
    bl_label = "Join"
    
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
   
   def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")