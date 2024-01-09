class animAnimNode_Workspots(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_Workspots'
    bl_label = "Workspot"
    
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
   
   def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
        # "var animLoopEventName": "CName;",
        # "var isCoverHubHack": "Bool;",
        # "var eventFilterType": "animEventFilterType;",
        # "var mainEmotionalState": "CName;",
        # "var emotionalExpression": "CName;",
        # "var facialKeyWeight": "Float;",
        # "var facialIdleMaleAnimation": "CName;",
        # "var facialIdleKey_MaleAnimation": "CName;",
        # "var facialIdleFemaleAnimation": "CName;",
        # "var facialIdleKey_FemaleAnimation": "CName;",
        # "var id": "Uint32;"