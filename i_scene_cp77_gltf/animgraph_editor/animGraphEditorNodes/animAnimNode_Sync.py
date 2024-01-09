class animAnimNode_Sync(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Sync'
    bl_label = "Sync"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")				
