class animAnimNode_animSomethingSomething(animgraphEditorNode, Node):
    bl_idname = 'animAnimNode_animSomethingSomething'
    bl_label = "animSomethingSomething"
    
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'CP77AnimGraphTree'
   
   def init(self, context):
		self.inputs.new('node', "In")
        self.outputs.new('node', "Out")
		
        # "var animDataBase": "animAnimDatabaseCollectionEntry;",
        # "var durationLink": "animFloatLink;",
        # "var phase": "CName;",
        # "var animation": "CName;",
        # "var applyMotion": "Bool;",
        # "var isLooped": "Bool;",
        # "var resume": "Bool;",
        # "var collectEvents": "Bool;",
        # "var fireAnimLoopEvent": "Bool;",
        # "var animLoopEventName": "CName;",
        # "var clipFront": "Float;",
        # "var clipEnd": "Float;",
        # "var clipFrontByEvent": "CName;",
        # "var clipEndByEvent": "CName;",
        # "var pushDataByTag": "CName;",
        # "var popDataByTag": "CName;",
        # "var pushSafeCutTag": "CName;",
        # "var convertToAdditive": "Bool;",
        # "var applyInertializationOnAnimSetSwap": "Bool;",
        # "var id": "Uint32;"