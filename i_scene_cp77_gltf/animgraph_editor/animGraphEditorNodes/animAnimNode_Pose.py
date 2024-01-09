class animAnimNode_Pose(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Pose'
    bl_label = "Pose"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
