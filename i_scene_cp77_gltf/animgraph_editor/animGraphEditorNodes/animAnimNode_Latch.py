class animAnimNode_Latch(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Latch'
    bl_label = "Latch"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
        
