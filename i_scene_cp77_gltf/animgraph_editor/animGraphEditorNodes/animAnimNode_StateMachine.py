class animAnimNode_statemachine(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_statemachine'
    bl_label = "statemachine"
    
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
   
   def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")