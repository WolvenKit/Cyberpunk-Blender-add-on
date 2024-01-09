class animAnimNode_blend(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_blend'
    bl_label = "Blend"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
