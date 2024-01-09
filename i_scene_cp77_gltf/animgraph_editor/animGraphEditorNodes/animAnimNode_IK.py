class animAnimNode_IK(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_IK'
    bl_label = "IK"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
