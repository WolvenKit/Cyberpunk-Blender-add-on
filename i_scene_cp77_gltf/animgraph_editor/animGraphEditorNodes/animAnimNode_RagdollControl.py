class animAnimNode_RagdollControl(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_RagdollControl'
    bl_label = "RagdollControl"
    
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
   
   def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		# "var blendInDuration": "Float;",
        # "var blendOutDuration": "Float;",
        # "var inputPoseNode": "animPoseLink;",
        # "var id": "Uint32;"