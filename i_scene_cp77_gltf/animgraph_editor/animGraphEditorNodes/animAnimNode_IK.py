class animAnimNode_IK(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_IK'
    bl_label = "IK"

    def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
        # "var ikChain": "CName;",
        # "var targetBone": "animTransformIndex;",
        # "var positionOffset": "Vector3;",
        # "var rotationOffset": "Quaternion;",
        # "var poleVector": "animPoleVectorDetails;",
        # "var weightPosition": "Float;",
        # "var weightRotation": "Float;",
        # "var blendTimeIn": "Float;",
        # "var blendTimeOut": "Float;",
        # "var priority": "Int32;",
        # "var inputLink": "animPoseLink;",
        # "var id": "Uint32;"