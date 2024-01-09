class animAnimNode_Transform(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Transform'
    bl_label = "Transform"
    
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
   
   def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")