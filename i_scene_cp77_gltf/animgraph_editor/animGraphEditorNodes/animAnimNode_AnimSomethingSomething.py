class animAnimNode_Event(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Event'
    bl_label = "Event"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
