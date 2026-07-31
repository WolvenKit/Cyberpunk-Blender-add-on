from bpy.props import EnumProperty
from bpy.types import Operator

from ...blender.animation_context import active_action
from ..services import events


def _finish(operator, result):
    if result.message:
        operator.report({result.level}, result.message)
    return result.blender_status


class CP77_OT_AnimEventAdd(Operator):
    bl_idname = "cp77.anim_event_add"
    bl_label = "Add Animation Event"
    bl_description = "Add a new animation event at the current frame"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return _finish(self, events.add_event(active_action(context), context.scene.frame_current))


class CP77_OT_AnimEventRemove(Operator):
    bl_idname = "cp77.anim_event_remove"
    bl_label = "Remove Animation Event"
    bl_description = "Remove the selected animation event"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return _finish(self, events.remove_event(active_action(context)))


class CP77_OT_AnimEventGoto(Operator):
    bl_idname = "cp77.anim_event_goto"
    bl_label = "Go To Event"
    bl_description = "Jump playhead to the selected event's start frame"
    bl_options = {"REGISTER"}

    def execute(self, context):
        return _finish(self, events.goto_event(active_action(context), context.scene))


class CP77_OT_AnimEventMove(Operator):
    bl_idname = "cp77.anim_event_move"
    bl_label = "Move Animation Event"
    bl_description = "Reorder event in the list"
    bl_options = {"REGISTER", "UNDO"}

    direction: EnumProperty(items=[("UP", "Up", ""), ("DOWN", "Down", "")], default="UP")

    def execute(self, context):
        return _finish(self, events.move_event(active_action(context), self.direction))


class CP77_OT_AnimEventSyncMarkers(Operator):
    bl_idname = "cp77.anim_event_sync_markers"
    bl_label = "Sync Markers from Events"
    bl_description = "Overwrite pose markers from the event list"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return _finish(self, events.sync_markers(active_action(context)))


class CP77_OT_AnimEventFromMarkers(Operator):
    bl_idname = "cp77.anim_event_from_markers"
    bl_label = "Events from Markers"
    bl_description = "Create new events from existing pose markers (additive)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return _finish(self, events.add_events_from_markers(active_action(context)))


class CP77_OT_AnimEventAddSwitch(Operator):
    bl_idname = "cp77.anim_event_add_switch"
    bl_label = "Add Switch"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return _finish(self, events.add_switch(active_action(context)))


class CP77_OT_AnimEventRemoveSwitch(Operator):
    bl_idname = "cp77.anim_event_remove_switch"
    bl_label = "Remove Switch"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return _finish(self, events.remove_switch(active_action(context)))


class CP77_OT_AnimEventAddParam(Operator):
    bl_idname = "cp77.anim_event_add_param"
    bl_label = "Add Parameter"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return _finish(self, events.add_param(active_action(context)))


class CP77_OT_AnimEventRemoveParam(Operator):
    bl_idname = "cp77.anim_event_remove_param"
    bl_label = "Remove Parameter"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return _finish(self, events.remove_param(active_action(context)))


class CP77_OT_AnimEventAddWorkspotAction(Operator):
    bl_idname = "cp77.anim_event_add_workspot_action"
    bl_label = "Add Workspot Action"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return _finish(self, events.add_workspot_action(active_action(context)))


class CP77_OT_AnimEventRemoveWorkspotAction(Operator):
    bl_idname = "cp77.anim_event_remove_workspot_action"
    bl_label = "Remove Workspot Action"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return _finish(self, events.remove_workspot_action(active_action(context)))
