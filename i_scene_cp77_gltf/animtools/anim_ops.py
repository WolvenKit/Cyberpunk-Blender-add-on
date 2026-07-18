from __future__ import annotations

import traceback

from bpy.props import BoolProperty, CollectionProperty, EnumProperty, IntProperty, StringProperty
from bpy.types import Operator, OperatorFileListElement

from .animtools import *
from .animtools import _assign_action, animBones
from .draw import _draw_callback
from .generate_rigs import DIRECTION_FORWARD, DIRECTION_REVERSE, cp77_to_rigify, find_pair, get_constraint_direction, \
    set_constraint_direction
from ..cyber_props import cp77riglist
from ..importers.import_with_materials import CP77GLBimport

_handle = None
_running = False


def _set_pose_bone_select(pose_bone, selected: bool) -> bool:
    """Toggle pose-bone selection across Blender 5.0 and 5.1+.
 
    Pre-5.1 the selection flag lives on the data `Bone` (`pose_bone.bone.select`).
    From 5.1 onward `Bone.select` is gone and selection lives on `PoseBone`
    directly. Returns True if either path succeeded.
    """
    try:
        pose_bone.select = selected
        return True
    except (AttributeError, TypeError):
        pass
    try:
        pose_bone.bone.select = selected
        return True
    except (AttributeError, TypeError):
        return False


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
            "maxRotationCompression": hints.get("maxRotationCompression", 0) if hasattr(hints, 'get') else hints[
                "maxRotationCompression"]
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

            result = load_apose(self, arm_obj)
            return result if result is not None else {'FINISHED'}

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
            result = load_tpose(self, arm_obj)
            return result if result is not None else {'FINISHED'}

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
        return context.active_object is not None and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.active_object
        if obj.animation_data is None:
            obj.animation_data_create()
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


class CP77_OT_ToggleConstraintDirection(Operator):
    """Reverse which rig drives which: Rigify ↔ source"""
    bl_idname = 'cp77.toggle_constraint_direction'
    bl_label = 'Toggle Rigify Constraint Direction'
    bl_options = {'REGISTER', 'UNDO'}

    source_name: StringProperty(options={'HIDDEN'})
    rigify_name: StringProperty(options={'HIDDEN'})

    def execute(self, context):
        source = bpy.data.objects.get(self.source_name)
        rig = bpy.data.objects.get(self.rigify_name)
        if not source or not rig:
            source, rig = find_pair(context.active_object)
        if not source or not rig:
            self.report({'ERROR'}, 'Source/Rigify pair not found')
            return {'CANCELLED'}

        current = get_constraint_direction(source)
        target = (DIRECTION_REVERSE if current == DIRECTION_FORWARD
                  else DIRECTION_FORWARD)
        ok, msg = set_constraint_direction(source, rig, target)
        self.report({'INFO'} if ok else {'ERROR'}, msg)
        return {'FINISHED'} if ok else {'CANCELLED'}


class CP77_OT_ActivateLinkedRig(Operator):
    """Make the named armature the active object"""
    bl_idname = 'cp77.activate_linked_rig'
    bl_label = 'Activate Linked Rig'
    bl_options = {'REGISTER', 'UNDO'}

    target_name: StringProperty(options={'HIDDEN'})

    def execute(self, context):
        target = bpy.data.objects.get(self.target_name)
        if target is None:
            self.report({'ERROR'}, f"Object '{self.target_name}' not found")
            return {'CANCELLED'}

        was_hidden = target.hide_get()
        if was_hidden:
            target.hide_set(False)

        if context.mode != 'OBJECT':
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
            except Exception:
                pass

        for o in context.selected_objects:
            o.select_set(False)
        target.select_set(True)
        context.view_layer.objects.active = target
        return {'FINISHED'}


class CP77_OT_BakeRigifyToSource(Operator):
    """Bake Rigify-driven motion to keyframes on the CP77 source rig
 
    Reads constraint-evaluated transforms from the source bones over the chosen
    frame range and writes them as an action ready for in-game export. Only
    the animation-bone subset is baked. Forward constraints are left in place;
    mute or remove them later to play the baked action standalone.
    """
    bl_idname = 'cp77.bake_rigify_to_source'
    bl_label = 'Bake Rigify to Cyberpunk'
    bl_options = {'REGISTER', 'UNDO'}

    action_name: StringProperty(
            name='Action Name',
            description="Name of the new action. Defaults to '<rigify action>_baked'",
            default='',
            )
    overwrite: BoolProperty(
            name='Overwrite Existing',
            description='Replace the target action if it already exists',
            default=False,
            )
    frame_range_source: EnumProperty(
            name='Frame Range',
            items=[
                ('SCENE', 'Scene Range', "Use scene.frame_start / scene.frame_end"),
                ('ACTION', 'Action Range', "Use the Rigify action's own frame_range"),
                ('MANUAL', 'Manual', 'Specify start and end frames'),
                ],
            default='SCENE',
            )
    frame_start: IntProperty(name='Start', default=1, min=0)
    frame_end: IntProperty(name='End', default=250, min=0)
    step: IntProperty(
            name='Step',
            description='Frame step (1 = every frame)',
            default=1, min=1, max=10,
            )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None or obj.type != 'ARMATURE':
            return False
        source, rig = find_pair(obj)
        if not source or not rig:
            return False
        return (rig.animation_data is not None
                and rig.animation_data.action is not None)

    def invoke(self, context, event):
        source, rig = find_pair(context.active_object)
        if rig is None or rig.animation_data is None or rig.animation_data.action is None:
            self.report({'ERROR'}, 'Rigify rig has no action to bake')
            return {'CANCELLED'}

        rig_action = rig.animation_data.action
        self.action_name = f"{rig_action.name}_baked"

        fr = rig_action.frame_range
        self.frame_start = int(fr[0])
        self.frame_end = int(fr[1])

        if get_constraint_direction(source) != DIRECTION_FORWARD:
            self.report(
                    {'WARNING'},
                    "Constraints are in REVERSE direction — source already follows itself. "
                    "Switch to FORWARD before baking for meaningful results.",
                    )

        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True

        source, rig = find_pair(context.active_object)
        if rig is not None and rig.animation_data and rig.animation_data.action:
            col = layout.column(align=True)
            col.enabled = False
            col.label(
                text=f"From: {rig.name} → {rig.animation_data.action.name}",
                icon='ARMATURE_DATA'
                )
            col.label(text=f"Onto: {source.name}", icon='OUTLINER_OB_ARMATURE')
            layout.separator()

        layout.prop(self, 'action_name')
        layout.prop(self, 'overwrite')
        layout.separator()
        layout.prop(self, 'frame_range_source')
        if self.frame_range_source == 'MANUAL':
            row = layout.row(align=True)
            row.prop(self, 'frame_start')
            row.prop(self, 'frame_end')
        layout.prop(self, 'step')

        layout.separator()
        info = layout.column(align=True)
        info.scale_y = 0.85
        info.label(text='Animation-bone subset only (animBones).', icon='INFO')
        info.label(
            text='Forward constraints are preserved — mute them later',
            icon='INFO'
            )
        info.label(text='to play the baked action standalone.')

    def execute(self, context):
        source, rig = find_pair(context.active_object)
        if not source or not rig:
            self.report({'ERROR'}, 'No Rigify pair found for active object')
            return {'CANCELLED'}
        if not (rig.animation_data and rig.animation_data.action):
            self.report({'ERROR'}, 'Rigify rig has no action to bake')
            return {'CANCELLED'}

        if self.frame_range_source == 'SCENE':
            start, end = context.scene.frame_start, context.scene.frame_end
        elif self.frame_range_source == 'ACTION':
            fr = rig.animation_data.action.frame_range
            start, end = int(fr[0]), int(fr[1])
        else:
            start, end = self.frame_start, self.frame_end

        if end < start:
            self.report({'ERROR'}, f"Invalid frame range: {start} → {end}")
            return {'CANCELLED'}

        action_name = self.action_name.strip() or f"{rig.animation_data.action.name}_baked"
        existing = bpy.data.actions.get(action_name)
        if existing is not None and not self.overwrite:
            self.report(
                    {'ERROR'},
                    f"Action '{action_name}' already exists — enable Overwrite to replace"
                    )
            return {'CANCELLED'}
        if existing is not None and self.overwrite:
            bpy.data.actions.remove(existing)

        target_action = bpy.data.actions.new(action_name)
        target_action.use_fake_user = True

        store_current_context()
        try:
            if context.mode != 'OBJECT':
                try:
                    bpy.ops.object.mode_set(mode='OBJECT')
                except Exception:
                    pass

            for o in context.selected_objects:
                o.select_set(False)
            if source.hide_get():
                source.hide_set(False)
            source.select_set(True)
            context.view_layer.objects.active = source

            bpy.ops.object.mode_set(mode='POSE')

            if not source.animation_data:
                source.animation_data_create()
            _assign_action(source.animation_data, target_action)

            present_anim_bones = set()
            for pb in source.pose.bones:
                is_anim = pb.name in animBones
                _set_pose_bone_select(pb, is_anim)
                if is_anim:
                    present_anim_bones.add(pb.name)

            if not present_anim_bones:
                self.report({'ERROR'}, 'No animation bones present on source rig')
                return {'CANCELLED'}

            bpy.ops.nla.bake(
                    frame_start=start,
                    frame_end=end,
                    step=self.step,
                    only_selected=True,
                    visual_keying=True,
                    clear_constraints=False,
                    clear_parents=False,
                    use_current_action=True,
                    bake_types={'POSE'},
                    )
        except Exception as e:
            traceback.print_exc()
            self.report({'ERROR'}, f"Bake failed: {e}")
            return {'CANCELLED'}
        finally:
            restore_previous_context()

        self.report(
                {'INFO'},
                f"Baked '{target_action.name}' "
                f"({start}→{end}, step {self.step}, {len(present_anim_bones)} bones). "
                f"Mute the constraints on source bones to play it standalone."
                )
        return {'FINISHED'}


class CP77NewAction(Operator):
    bl_idname = 'cp77.new_action'
    bl_label = "Add Action"
    bl_options = {'INTERNAL', 'UNDO'}

    name: StringProperty(default="New action")

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.active_object
        if not obj.animation_data:
            obj.animation_data_create()
        new_action = bpy.data.actions.new(self.name)
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
                    with_materials=False,
                    exclude_unused_mats=True,
                    image_format='PNG',
                    filepath=selected_rig,
                    hide_armatures=False,
                    import_garmentsupport=False,
                    files=[],
                    directory='',
                    appearances=['ALL'],
                    remap_depot=False,
                    scripting=True,
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
