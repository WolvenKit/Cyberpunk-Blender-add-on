		
class animAnimNode_Float(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Float'
    bl_label = "Float"

    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
   
   def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
        # "var firstValue": "Float;",
        # "var secondValue": "Float;",
        # "var trueValue": "Float;",
        # "var falseValue": "Float;",
        # "var operation": "animEAnimGraphCompareFunc;",
        # "var firstInputLink": "animFloatLink;",
        # "var secondInputLink": "animFloatLink;",
        # "var trueInputLink": "animFloatLink;",
        # "var falseInputLink": "animFloatLink;",
        # "var id": "Uint32;"        
		# "var min": "Float;",
        # "var max": "Float;",
        # "var inputNode": "animFloatLink;",