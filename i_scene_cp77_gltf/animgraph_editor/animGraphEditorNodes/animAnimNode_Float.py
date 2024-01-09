		
class animAnimNode_Float(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Float'
    bl_label = "Float"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")	
		
