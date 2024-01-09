class animAnimNode_fpp(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_fpp'
    bl_label = "fpp"
    
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
   
   def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")