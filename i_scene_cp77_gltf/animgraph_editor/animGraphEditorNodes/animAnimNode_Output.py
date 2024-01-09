class animAnimNode_Output(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Output'
    bl_label = "Output"

    def init(self, context):
        self.inputs.new('node', "In")