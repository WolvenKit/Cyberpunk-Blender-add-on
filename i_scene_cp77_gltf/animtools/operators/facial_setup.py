import bpy
from bpy.types import Operator

from ...blender.animation_context import active_armature
from ..services.facial import operations, session


def _finish(operator, result):
    if result.message:
        operator.report({result.level}, result.message)
    return result.blender_status


class CP77_OT_LoadFacial(Operator):
    bl_idname = "cp77.load_facial"
    bl_label = "Load Rig + FacialSetup"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.cp77_facial
        return _finish(self, operations.load(context, props.rig_json, props.facial_json))


class CP77_OT_UnbindFacial(Operator):
    bl_idname = "cp77_facial.unbind"
    bl_label = "Unbind Facial Setup"
    bl_options = {"REGISTER", "UNDO"}

    keep_properties: bpy.props.BoolProperty(name="Keep Track Properties", default=False)

    @classmethod
    def poll(cls, context):
        armature = active_armature(context)
        return bool(armature and session.is_bound(armature))

    def execute(self, context):
        return _finish(self, operations.unbind(context, keep_properties=bool(self.keep_properties)))


class CP77_OT_RebuildFacialSession(Operator):
    bl_idname = "cp77_facial.rebuild_cache"
    bl_label = "Rebuild Facial Session"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        armature = active_armature(context)
        return bool(armature and session.is_bound(armature))

    def execute(self, context):
        return _finish(self, operations.rebuild(context))


class CP77_OT_ResetNeutral(Operator):
    bl_idname = "cp77.reset_neutral"
    bl_label = "Reset to Rest"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return _finish(self, operations.reset_neutral(context))


class CP77_OT_ResetTracksToDefaults(Operator):
    bl_idname = "cp77.reset_tracks_defaults"
    bl_label = "Reset Tracks to Defaults"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return active_armature(context) is not None

    def execute(self, context):
        return _finish(self, operations.reset_tracks(context))
