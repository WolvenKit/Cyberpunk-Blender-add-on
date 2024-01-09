class animAnimNode_Interpolation(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Interpolation'
    bl_label = "Interpolation"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
