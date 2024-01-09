class animAnimNode_Sync(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Sync'
    bl_label = "Sync"
    
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
   
   def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")