class animAnimNode_Convert(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Convert'
    bl_label = "Convert"
    
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
   
   def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
