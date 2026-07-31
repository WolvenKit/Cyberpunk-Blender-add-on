from __future__ import annotations

from bpy.types import Operator

from ..services import root_motion


class RootMotionOperatorBase(Operator):
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return root_motion.animated_armature(context) is not None

    def _request(self, context):
        armature, request, start, end = root_motion.default_request(context)
        if armature is None:
            self.report({"ERROR"}, "Select an animated armature")
        return armature, request, start, end

    def _finish(self, result):
        self.report({result.level}, result.message)
        return result.blender_status


class CP77HipMotionToRoot(RootMotionOperatorBase):
    bl_idname = "cp77.hip_to_root_motion"
    bl_label = "Extract Root Motion"

    def execute(self, context):
        armature, request, start, end = self._request(context)
        if armature is None:
            return {"CANCELLED"}
        return self._finish(root_motion.extract_root_motion(context, armature, request, start, end))


class CP77RootToHipMotion(RootMotionOperatorBase):
    bl_idname = "cp77.root_to_hip_motion"
    bl_label = "Integrate Root Motion"

    def execute(self, context):
        armature, request, start, end = self._request(context)
        if armature is None:
            return {"CANCELLED"}
        return self._finish(root_motion.integrate_root_motion(context, armature, request, start, end))


class CP77RemoveRootMotion(RootMotionOperatorBase):
    bl_idname = "cp77.remove_root_motion"
    bl_label = "Remove Root Motion"

    def execute(self, context):
        armature, request, _start, _end = self._request(context)
        if armature is None:
            return {"CANCELLED"}
        return self._finish(root_motion.remove_root_motion(context, armature, request.root_bone))
