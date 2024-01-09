
class animAnimNode_Constraint(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Constraint'
    bl_label = "Constraint"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")

