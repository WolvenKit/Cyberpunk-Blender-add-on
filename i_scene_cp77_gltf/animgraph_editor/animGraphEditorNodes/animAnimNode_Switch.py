class animAnimNode_Switch(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Switch'
    bl_label = "Switch"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")				
        # "var numInputs": "Uint32;",
        # "var blendTime": "Float;",
        # "var timeWarpingEnabled": "Bool;",
        # "var weightNode": "animFloatLink;",
        # "var pushDataByTag": "CName;",
        # "var canRequestInertialization": "Bool;",
        # "var id": "Uint32;"