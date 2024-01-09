
		
class animAnimNode_SetDrivenKey(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_SetDrivenKey'
    bl_label = "SetDrivenKey"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
