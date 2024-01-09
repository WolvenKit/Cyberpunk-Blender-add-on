class animAnimNode_Locoomotion(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Locoomotion'
    bl_label = "Locoomotion"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
