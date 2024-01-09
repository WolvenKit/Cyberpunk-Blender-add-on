class animAnimNode_Track(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Track'
    bl_label = "Track"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")