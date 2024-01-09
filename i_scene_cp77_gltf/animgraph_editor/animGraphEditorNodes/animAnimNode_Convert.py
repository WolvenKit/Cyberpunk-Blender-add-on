class animAnimNode_Convert(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Convert'
    bl_label = "Convert"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
