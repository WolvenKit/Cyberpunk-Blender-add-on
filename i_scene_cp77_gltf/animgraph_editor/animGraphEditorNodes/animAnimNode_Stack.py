class animAnimNode_Stack(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Stack'
    bl_label = "Stack"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
