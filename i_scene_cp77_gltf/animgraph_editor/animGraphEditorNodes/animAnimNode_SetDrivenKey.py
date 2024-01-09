
		
class animAnimNode_SetDrivenKey(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_SetDrivenKey'
    bl_label = "SetDrivenKey"
    
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
   
   def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")