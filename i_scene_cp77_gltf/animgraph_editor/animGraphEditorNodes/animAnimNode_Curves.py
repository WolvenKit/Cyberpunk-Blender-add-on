		
class animAnimNode_Curves(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Curves'
    bl_label = "Curves"
    
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
   
   def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
