class animAnimNode_Workspots(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Workspots'
    bl_label = "Workspot"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
