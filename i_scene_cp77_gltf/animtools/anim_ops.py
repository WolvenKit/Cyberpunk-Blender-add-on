from __future__ import annotations
import traceback
import bpy
from bpy.types import Operator, OperatorFileListElement
from bpy.props import StringProperty, BoolProperty, IntProperty, CollectionProperty
from ..main.bartmoss_functions import *
from ..cyber_props import cp77riglist
from ..icons.cp77_icons import get_icon
from ..importers.import_with_materials import CP77GLBimport
from .animtools import *
from .animtools import _assign_action
from .generate_rigs import cp77_to_rigify
from .draw import _draw_callback

_handle  = None
_running = False

class CP77_OT_ToggleSIMD(Operator):
    bl_idname = "cp77.toggle_simd"
    bl_label = "Toggle SIMD Encoding"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty(options={'HIDDEN'})

    def execute(self, context):
        action = bpy.data.actions.get(self.name)
        if action is None:
            self.report({'WARNING'}, f"Action '{self.name}' not found")
            return {'CANCELLED'}
        if "optimizationHints" not in action:
            action["optimizationHints"] = {"preferSIMD": False, "maxRotationCompression": 0}
        hints = action["optimizationHints"]
        current = hints.get("preferSIMD", False) if hasattr(hints, 'get') else hints["preferSIMD"]
        new_val = not bool(current)
        action["optimizationHints"] = {
            "preferSIMD": new_val,
            "maxRotationCompression": hints.get("maxRotationCompression", 0) if hasattr(hints, 'get') else hints["maxRotationCompression"]
        }
        label = "SIMD" if new_val else "Compressed"
        self.report({'INFO'}, f"'{self.name}' encoding set to {label}")
        return {'FINISHED'}

class BHLS_OT_Start(Operator):
    bl_idname = "view3d.bhls_start"
    bl_label = "Start Bone Lines"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == 'ARMATURE'

    def execute(self, context):
        global _handle, _running
        if _running:
            self.report({'INFO'}, "Already running")
            return {'CANCELLED'}

        arm_obj = context.object

        _handle = bpy.types.SpaceView3D.draw_handler_add(
                _draw_callback, (arm_obj.name,), 'WINDOW', 'POST_VIEW'
                )
        _running = True
        self.report({'INFO'}, f"Drawing lines for: {arm_obj.name}")

        context.area.tag_redraw()
        return {'FINISHED'}

class BHLS_OT_Stop(Operator):
    bl_idname = "view3d.bhls_stop"
    bl_label = "Stop Bone Lines"
    bl_options = {'REGISTER'}

    def execute(self, context):
        global _handle, _running
        if _handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(_handle, 'WINDOW')
            _handle = None

        _running = False
        self.report({'INFO'}, "Bone Lines stopped")

        if context.area:
            context.area.tag_redraw()

        return {'FINISHED'}

class CP77AnimsDelete(Operator):
    bl_idname = 'cp77.delete_anims'
    bl_label = 'Delete action'
    bl_options = {'INTERNAL', 'UNDO'}
    bl_description = "Delete this action"

    name: StringProperty()

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.animation_data

    def execute(self, context):
        delete_anim(self, context)
        return {'FINISHED'}

class LoadAPose(Operator):
    bl_idname = 'cp77.load_apose'
    bl_label = 'Load A-Pose'

    def execute(self, context):
        try:
            arm_obj = context.object
            if not arm_obj or arm_obj.type != 'ARMATURE':
                self.report({'ERROR'}, "Select an armature object.")
                return {'CANCELLED'}

            arm_data = arm_obj.data
            arm_data["T-Pose"] = False

            load_apose(self, arm_obj)

            return {'FINISHED'}

        except Exception as e:
            print(traceback.format_exc())
            self.report({'ERROR'}, f"Failed: {e}")
            return {'CANCELLED'}

class LoadTPose(Operator):
    bl_idname = "cp77.load_tpose"
    bl_label = "Load T-Pose"

    def execute(self, context):
        arm_obj = context.object
        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, "This isnt' an armature, can't load T-Pose")
            return {'CANCELLED'}
        try:
            load_tpose(self, arm_obj)
            return {'FINISHED'}

        except Exception as e:
            print(traceback.format_exc())
            self.report({'ERROR'}, f"Failed: {e}")
            return {'CANCELLED'}

class CP77Animset(Operator):
    bl_idname = 'cp77.set_animset'
    bl_label = "Animsets"
    bl_options = {'INTERNAL', 'UNDO'}

    name: StringProperty(options={'HIDDEN'})
    new_name: StringProperty(name="New name", default="")
    play: BoolProperty(options={'HIDDEN'}, default=False)

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.animation_data

    def execute(self, context):
        obj = context.active_object
        if not self.name:
            obj.animation_data.action = None
            return {'FINISHED'}

        action = bpy.data.actions.get(self.name, None)
        if not action:
            return {'CANCELLED'}

        action.use_fake_user = True

        if self.new_name:
            action.name = self.new_name
        elif not self.play and obj.animation_data.action == action:
            obj.animation_data.action = None
        else:
            reset_armature(self, context)
            if not obj.animation_data:
                obj.animation_data_create()
            if self.play:
                play_anim(self, context, action.name)
            else:
                _assign_action(obj.animation_data, action)

        return {'FINISHED'}

    def invoke(self, context, event):
        if event.ctrl:
            self.new_name = self.name
            return context.window_manager.invoke_props_dialog(self)
        else:
            self.new_name = ""
            return self.execute(context)

class CP77ToRigify(Operator):
    bl_idname = "rigify_generator.cp77"
    bl_parent_id = "CP77_PT_animspanel"
    bl_options = {'REGISTER', 'UNDO'}
    bl_label = "Generate Rigify"

    def execute(self, context):
        cp77_to_rigify()
        return {'FINISHED'}

class CP77BoneHider(Operator):
    bl_idname = "bone_hider.cp77"
    bl_parent_id = "CP77_PT_animspanel"
    bl_options = {'REGISTER', 'UNDO'}
    bl_label = "Toggle Deform Bone Visibilty"

    def execute(self, context):
        hide_extra_bones(self, context)
        return {'FINISHED'}

class CP77BoneUnhider(Operator):
    bl_idname = "bone_unhider.cp77"
    bl_parent_id = "CP77_PT_animspanel"
    bl_options = {'REGISTER', 'UNDO'}
    bl_label = "Toggle Deform Bone Visibilty"

    def execute(self, context):
        unhide_extra_bones(self, context)
        return {'FINISHED'}

class CP77Keyframe(Operator):
    bl_idname = "insert_keyframe.cp77"
    bl_parent_id = "CP77_PT_animspanel"
    bl_label = "Keyframe Pose"

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        props = context.scene.cp77_panel_props
        cp77_keyframe(props, context, props.frameall)
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.cp77_panel_props
        row = layout.row(align=True)
        row.label(text="Insert a keyframe for every bone at every from of the animation")
        row = layout.row(align=True)
        row.prop(props, "frameall", text="")

class CP77ResetArmature(Operator):
    bl_idname = "reset_armature.cp77"
    bl_parent_id = "CP77_PT_animspanel"
    bl_label = "Reset Armature Position"

    def execute(self, context):
        reset_armature(self, context)
        return {"FINISHED"}


class CP77NewAction(Operator):
    bl_idname = 'cp77.new_action'
    bl_label = "Add Action"
    bl_options = {'INTERNAL', 'UNDO'}

    name: StringProperty(default="New action")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        obj = context.active_object
        if not obj.animation_data:
            obj.animation_data_create()
        new_action               = bpy.data.actions.new(self.name)
        new_action.use_fake_user = True
        reset_armature(self, context)
        _assign_action(obj.animation_data, new_action)
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

class CP77RigLoader(Operator):
    bl_idname = "cp77.rig_loader"
    bl_label = "Load Deform Rig from Resources"

    files: CollectionProperty(type=OperatorFileListElement)
    appearances: StringProperty(name="Appearances", default="")
    directory: StringProperty(name="Directory", default="")
    filepath: StringProperty(name="Filepath", default="")
    rigify_it: BoolProperty(name='Apply Rigify Rig', default=False)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        props = context.scene.cp77_panel_props
        selected_rig_name = props.body_list
        rig_files, rig_names = cp77riglist(self, context)

        if selected_rig_name in rig_names:
            selected_rig = rig_files[rig_names.index(selected_rig_name)]
            self.filepath = selected_rig
            CP77GLBimport(
                self, exclude_unused_mats=True, image_format='PNG',
                filepath=selected_rig, hide_armatures=False, import_garmentsupport=False, files=[], directory='',
                appearances="ALL", remap_depot=False, scripting=True
                )
            if props.fbx_rot:
                rotate_quat_180(self, context)
            if self.rigify_it:
                cp77_to_rigify()
        return {'FINISHED'}

    def draw(self, context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        box = layout.box()
        row = box.row(align=True)
        row.label(text="Select rig to load: ")
        row.prop(props, 'body_list', text="", )
        col = box.column()
        col.prop(self, 'rigify_it', text="Generate Rigify Control Rig")
        col.prop(props, 'fbx_rot', text="Load Rig in FBX Orientation")

class CP77AnimNamer(Operator):
    bl_idname = "cp77.anim_namer"
    bl_label = "Fix Action Names"
    bl_options = {'INTERNAL', 'UNDO'}

    def execute(self, context):
        for a in CP77AnimsList(self, context): a.name = a.name.replace(" ", "_").lower()
        return {'FINISHED'}