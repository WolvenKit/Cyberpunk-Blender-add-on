class animAnimNode_Base(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Base'
    bl_label = "Root"
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
		
    def init(self, context):
        self.outputs.new('node', "Out")