
class animAnimNode_MathExpression(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_MathExpression'
    bl_label = "MathExpression"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
        # "var expressionData": "animMathExpressionNodeData;",
        # "var outputFloatTrack": "animNamedTrackIndex;",
        # "var inputLink": "animPoseLink;",
        # "var id": "Uint32;"