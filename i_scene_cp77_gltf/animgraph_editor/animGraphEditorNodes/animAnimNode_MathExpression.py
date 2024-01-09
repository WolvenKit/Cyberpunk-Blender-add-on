
class animAnimNode_MathExpression(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_MathExpression'
    bl_label = "MathExpression"
    
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
   
   def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
        # "var expressionData": "animMathExpressionNodeData;",
        # "var outputFloatTrack": "animNamedTrackIndex;",
        # "var inputLink": "animPoseLink;",
        # "var id": "Uint32;"