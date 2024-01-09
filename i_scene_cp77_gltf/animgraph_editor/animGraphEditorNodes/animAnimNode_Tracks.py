class animAnimNode_Track(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Track'
    bl_label = "Track"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
        
                # "var min": "Float;",
        # "var max": "Float;",
        # "var oldMin": "Float;",
        # "var oldMax": "Float;",
        # "var minLink": "animFloatLink;",
        # "var maxLink": "animFloatLink;",
        # "var oldMinLink": "animFloatLink;",
        # "var oldMaxLink": "animFloatLink;",
        # "var track": "animNamedTrackIndex;",
        # "var debug": "Bool;",
        # "var inputLink": "animPoseLink;",
        # "var id": "Uint32;"