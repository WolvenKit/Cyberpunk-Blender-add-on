class animAnimNode_Switch(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Switch'
    bl_label = "Switch"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")				
