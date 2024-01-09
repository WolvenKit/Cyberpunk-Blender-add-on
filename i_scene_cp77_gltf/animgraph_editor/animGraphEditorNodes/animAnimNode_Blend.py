class animAnimNode_blend(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_blend'
    bl_label = "Blend"
    
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
   
   def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
        
        # "var biasValue": "Float;",
		# "var minInputValue": "Float;",
        # "var maxInputValue": "Float;",
		# "var firstInputNode": "animPoseLink;",
        # "var secondInputNode": "animPoseLink;",
        # "var scaleValue": "Float;",
        # "var additiveType": "animEAnimGraphAdditiveType;",
        # "var timeWarpingEnabled": "Bool;",
        # "var blendTracks": "animEBlendTracksMode;",
        # "var inputNode": "animPoseLink;",
        # "var addedInputNode": "animPoseLink;",
        # "var weightNode": "animFloatLink;",
        # "var weightPreviousFrameFloatTrack": "animNamedTrackIndex;",
        # "var weightPreviousFrameFloatTrackDefaultValue": "Float;",
        # "var maskName": "CName;",
        # "var id": "Uint32;"