		
class animAnimNode_Bone(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Bone'
    bl_label = "Bone"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
