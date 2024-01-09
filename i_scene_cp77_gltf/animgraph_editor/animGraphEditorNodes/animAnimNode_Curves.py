		
class animAnimNode_Curves(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Curves'
    bl_label = "Curves"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
