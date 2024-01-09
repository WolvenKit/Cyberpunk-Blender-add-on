class animAnimNode_fpp(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_fpp'
    bl_label = "fpp"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
