import sys
import bpy
import bpy.utils.previews
from bpy.types import (Operator, OperatorFileListElement, Panel)
from bpy.props import (StringProperty, BoolProperty, CollectionProperty)
from ..main.bartmoss_functions import *
from ..cyber_props import cp77riglist
from ..icons.cp77_icons import get_icon
from ..main.common import get_classes
from ..importers.import_with_materials import CP77GLBimport
from .animtools import *
from .generate_rigs import create_rigify_rig

def CP77AnimsList(self, context):
    for action in bpy.data.actions:
        if action.library:
            continue
        yield action


### Draw a panel to store anims functions
class CP77_PT_AnimsPanel(Panel):
    bl_idname = "CP77_PT_animspanel"
    bl_label = "Animation Tools"
    bl_category = "CP77 Modding"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {'DEFAULT_CLOSED'}

    name: StringProperty(options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
        if cp77_addon_prefs.context_only:
            return context.active_object and context.active_object.type == 'ARMATURE'
        else:
            return context

## make sure the context is unrestricted as possible, ensure there's an armature selected
    def draw(self, context):
        layout = self.layout

        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences

        if not cp77_addon_prefs.show_animtools:
            return
        props = context.scene.cp77_panel_props
        box = layout.box()
        box.label(text='Rigs', icon_value=get_icon("WKIT"))
        row = box.row(align=True)
        row.operator('cp77.rig_loader', text="Load Bundled Rig")
        obj = context.active_object

        if obj is None or obj.type != 'ARMATURE':
            return

        col = box.column()
        if 'deformBonesHidden' in obj:
            col.operator('bone_unhider.cp77',text='Unhide Deform Bones')
        else:
            col.operator('bone_hider.cp77',text='Hide Deform Bones')
        col.operator('reset_armature.cp77')
        col.operator('delete_unused_bones.cp77', text='Delete unused bones')
        col.operator('cp77.anim_namer')
        available_anims = list(CP77AnimsList(context,obj))
        active_action = obj.animation_data.action if obj.animation_data else None
        if not available_anims:
            box = layout.box()
            row = box.row(align=True)
            row.label(text='Animsets', icon_value=get_icon("WKIT"))
            row.operator('cp77.new_action',icon='ADD', text="")
            row = box.row(align=True)
            row.menu('RENDER_MT_framerate_presets')
            row = box.row(align=True)
            row.prop(context.scene.render, "fps")
            row.prop(context.scene.render, "fps_base")
            row = box.row(align=True)
            row.operator('insert_keyframe.cp77')
            return


        box = layout.box()
        for action in available_anims:
            action.use_fake_user:True
            selected = action == active_action
            if selected:
                row = box.row(align=True)
                row.alignment='CENTER'
                row.operator("screen.frame_jump", text="", icon='REW').end = False
                row.operator("screen.keyframe_jump", text="", icon='PREV_KEYFRAME').next = False
                row.operator("screen.animation_play", text="", icon='PLAY_REVERSE').reverse = True
                row.operator("screen.animation_play", text="", icon='PLAY')
                row.operator("screen.keyframe_jump", text="", icon='NEXT_KEYFRAME').next = True
                row.operator("screen.frame_jump", text="", icon='FF').end = True
                row = box.row(align=True)
                row.prop(active_action, 'use_frame_range', text="Set Playback Range",toggle=1)
                if active_action.use_frame_range:
                    row = box.row(align=True)
                    row.prop(bpy.context.scene, 'frame_start', text="")
                    row.prop(bpy.context.scene, 'frame_end', text="")

        box = layout.box()
        row = box.row(align=True)
        row.label(text='Animsets', icon_value=get_icon('WKIT'))
        row.operator('cp77.new_action',icon='ADD', text="")
        row = box.row(align=True)
        row.menu('RENDER_MT_framerate_presets')
        row = box.row(align=True)
        row.prop(context.scene.render, "fps")
        row.prop(context.scene.render, "fps_base")
        row = box.row(align=True)
        row.operator('insert_keyframe.cp77')
        # if available_anims:
        col = box.column(align=True)
        for action in available_anims:
            action.use_fake_user:True
            selected = action == active_action
            row = col.row(align=True)
            sub = row.column(align=True)
            sub.ui_units_x = 1.0
            if selected and context.screen.is_animation_playing:
                op = sub.operator('screen.animation_cancel', icon='PAUSE', text=action.name, emboss=True)
                op.restore_frame = False
                if active_action.use_frame_range:
                    row.prop(active_action, 'use_cyclic', icon='CON_FOLLOWPATH', text="")
            else:
                icon = 'PLAY' if selected else 'TRIA_RIGHT'
                op = sub.operator('cp77.set_animset', icon=icon, text="", emboss=True)
                op.name = action.name
                op.play = True
                op = row.operator('cp77.set_animset', text=action.name)
                op.name = action.name
                op.play = False
                row.operator('cp77.delete_anims', icon='X', text="").name = action.name


### allow deleting animations from the animset panel, regardless of editor context
class CP77AnimsDelete(Operator):
    bl_idname = 'cp77.delete_anims'
    bl_label = "Delete action"
    bl_options = {'INTERNAL', 'UNDO'}
    bl_description = "Delete this action"

    name: StringProperty()

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.animation_data

    def execute(self, context):
        delete_anim(self, context)
        return{'FINISHED'}


# this class is where most of the function is so far - play/pause
# Todo: fix renaming actions from here
class CP77Animset(Operator):
    bl_idname = 'cp77.set_animset'
    bl_label = "Available Animsets"
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

        # Always save it, just in case
        action.use_fake_user = True

        if self.new_name:
            # Rename
            action.name = self.new_name
        elif not self.play and obj.animation_data.action == action:
            # Action was already active, stop editing
            obj.animation_data.action = None
        else:
            reset_armature(self,context)
            obj.animation_data.action = action

            if self.play:
                context.scene.frame_current = int(action.curve_frame_range[0])
                bpy.ops.screen.animation_cancel(restore_frame=False)
                play_anim(self,context,action.name)

        return {'FINISHED'}

    def invoke(self, context, event):
        if event.ctrl:
            return context.window_manager.invoke_props_dialog(self)
        else:
            self.new_name = ""
            return self.execute(context)


class CP77BoneHider(Operator):
    bl_idname = "bone_hider.cp77"
    bl_parent_id = "CP77_PT_animspanel"
    bl_options = {'REGISTER', 'UNDO'}
    bl_label = "Toggle Deform Bone Visibilty"
    bl_description = "Hide deform bones in the selected armature"

    def execute(self, context):
        hide_extra_bones(self, context)
        return{'FINISHED'}


class CP77BoneUnhider(Operator):
    bl_idname = "bone_unhider.cp77"
    bl_parent_id = "CP77_PT_animspanel"
    bl_options = {'REGISTER', 'UNDO'}
    bl_label = "Toggle Deform Bone Visibilty"
    bl_description = "Unhide deform bones in the selected armature"

    def execute(self, context):
        unhide_extra_bones(self, context)
        return{'FINISHED'}


# inserts a keyframe on the current frame
class CP77Keyframe(Operator):
    bl_idname = "insert_keyframe.cp77"
    bl_parent_id = "CP77_PT_animspanel"
    bl_label = "Keyframe Pose"
    bl_description = "Insert a Keyframe"

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
    bl_description = "Clear all transforms on current selected armature"

    def execute(self, context):
        reset_armature(self, context)
        return {"FINISHED"}

class CP77DeleteUnusedBones(Operator):
    bl_idname = "delete_unused_bones.cp77"
    bl_parent_id = "CP77_PT_animspanel"
    bl_label = "Delete unused bones"
    bl_description = "Delete all bones that aren't used by meshes parented to the armature"

    def execute(self, context):
        delete_unused_bones(self, context)
        return {"FINISHED"}


class CP77NewAction(Operator):

    bl_idname = 'cp77.new_action'
    bl_label = "Add Action"
    bl_options = {'INTERNAL', 'UNDO'}
    bl_description = "Add a new action to the list"

    name: StringProperty(default="New action")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        obj = context.active_object


    def invoke(self, context, event):
        obj = context.active_object
        if not obj.animation_data:
            obj.animation_data_create()
        new_action = bpy.data.actions.new(self.name)
        new_action.use_fake_user = True
        reset_armature(obj, context)
        obj.animation_data.action = new_action
        return {'FINISHED'}


class CP77RigLoader(Operator):
    bl_idname = "cp77.rig_loader"
    bl_label = "Load Deform Rig from Resources"
    bl_description = "Load Cyberpunk 2077 deform rigs from plugin resources"

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
        rig_files, rig_names = cp77riglist(self,context)

        if selected_rig_name in rig_names:
            # Find the corresponding .glb file and load it
            selected_rig = rig_files[rig_names.index(selected_rig_name)]
            self.filepath = selected_rig
            CP77GLBimport(self, exclude_unused_mats=True, image_format='PNG', with_materials=False,
                          filepath=selected_rig, hide_armatures=False, import_garmentsupport=False, files=[], directory='', appearances="ALL", remap_depot=False, scripting=True)
            if props.fbx_rot:
                rotate_quat_180(self,context)
            if self.rigify_it:
                create_rigify_rig(self,context)
        return {'FINISHED'}

    def draw(self,context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        box = layout.box()
        row = box.row(align=True)
        row.label(text="Select rig to load: ")
        row.prop(props, 'body_list', text="",)
        col = box.column()
        col.prop(self, 'rigify_it', text="Generate Rigify Control Rig")
        col.prop(props, 'fbx_rot', text="Load Rig in FBX Orientation")


class CP77AnimNamer(Operator):
    bl_idname = "cp77.anim_namer"
    bl_label = "Fix Action Names"
    bl_options = {'INTERNAL', 'UNDO'}
    bl_description = "replace spaces and capital letters in animation names with underscores and lower case letters"

    def execute(self, context):
        for a in CP77AnimsList(self,context): a.name = a.name.replace(" ", "_").lower()
        return {'FINISHED'}


operators, other_classes = get_classes(sys.modules[__name__])


def register_animtools():
    for cls in operators:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
    for cls in other_classes:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)


def unregister_animtools():
    for cls in reversed(other_classes):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
    for cls in reversed(operators):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)