import sys
import re
import numpy as np
import bpy
from bpy.utils import register_class, unregister_class
import bpy.utils.previews
from bpy.types import (Operator, OperatorFileListElement, PropertyGroup, Panel)
from bpy.props import (StringProperty, BoolProperty, IntProperty, CollectionProperty, FloatProperty)
from typing import Optional, Tuple
import mathutils
from ..main.bartmoss_functions import *
from ..cyber_props import cp77riglist
from ..icons.cp77_icons import get_icon
from ..main.common import get_classes
from ..importers.import_with_materials import CP77GLBimport
from .animtools import *
from .bartmoss_math import *
from .generate_rigs import cp77_to_rigify
from .facial import load_wkit_facialsetup, load_wkit_rig_skeleton, RigSkeleton, FacialSetup
from .tracksolvers import solve_tracks_face, build_tracks_from_armature
#from .jali_integration import *
from .draw import (_handle, _running, _draw_callback)
from . import root_motion

def CP77AnimsList(self, context):
    for action in bpy.data.actions:
        if action.library:
            continue
        yield action

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
        box.label(text='Rig Tools', icon_value=get_icon("WKIT"))
        col = box.column()
        col.operator('cp77.rig_loader', text="Load Bundled Rig")
        obj = context.active_object

        if obj is None or obj.type != 'ARMATURE':
            return
        col.operator('rigify_generator.cp77', text='Generate Rigify Rig')
        if 'deformBonesHidden' in obj:
            col.operator('bone_unhider.cp77',text='Unhide Deform Bones')
        else:
            col.operator('bone_hider.cp77',text='Hide Deform Bones')
        if _running:
            col.operator(BHLS_OT_Stop.bl_idname, text="Stop Drawing Bone Lines", icon='PAUSE')
        else:
            col.operator(BHLS_OT_Start.bl_idname, text="Draw Bone Lines", icon='PLAY')

        row = col.row()
        row.label(text="Posing")   
        col.operator('reset_armature.cp77')
        if 'T-Pose' in obj.data:
            if obj.data['T-Pose'] is True:
                col.operator('cp77.load_apose')
            else:
                col.operator('cp77.load_tpose')
        row = col.row()
        row.label(text="Cleanup")
        col.operator('delete_unused_bones.cp77', text='Delete unused bones')
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
        col =box.column()
        row = col.row(align=True)
        row.label(text='Animsets', icon_value=get_icon('WKIT'))
        row.operator('cp77.new_action',icon='ADD', text="")
        col.menu('RENDER_MT_framerate_presets')
        row = col.row(align=True)
        row.prop(context.scene.render, "fps")
        row.prop(context.scene.render, "fps_base")
        col.operator('cp77.anim_namer')
        col.operator('insert_keyframe.cp77')
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
        
        # Add draw handler 
        _handle = bpy.types.SpaceView3D.draw_handler_add(
            _draw_callback, (arm_obj.name,), 'WINDOW', 'POST_VIEW'
        )
        _running = True
        self.report({'INFO'}, f"Drawing lines for: {arm_obj.name}")
        
        # Force a redraw so lines appear immediately
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
        
        # Force redraw to clear lines immediately
        if context.area:
            context.area.tag_redraw()
            
        return {'FINISHED'}

### allow deleting animations from the animset panel, regardless of editor context
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
        return{'FINISHED'}

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

            # First always load single base A-pose
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
            return{'CANCELLED'}

# this class is where most of the function is so far - play/pause
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

class CP77ToRigify(Operator):
    bl_idname = "rigify_generator.cp77"
    bl_parent_id = "CP77_PT_animspanel"
    bl_options = {'REGISTER', 'UNDO'}
    bl_label = "Generate Rigify"
    bl_description = "Generate a Rigify Control Rig for the selected Cyberpunk 2077 Armature"

    def execute(self, context):
        cp77_to_rigify()
        return{'FINISHED'}

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
            CP77GLBimport(self, exclude_unused_mats=True, image_format='PNG',
                          filepath=selected_rig, hide_armatures=False, import_garmentsupport=False, files=[], directory='', appearances="ALL", remap_depot=False, scripting=True)
            if props.fbx_rot:
                rotate_quat_180(self,context)
            if self.rigify_it:
                cp77_to_rigify()
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

_CACHE = {
    "rig": None,
    "setup": None,
    "rig_path": "",
    "setup_path": "",
    "last_load_time": 0
}

def _set_cache(rig: Optional[RigSkeleton], setup: Optional[FacialSetup], rig_path: str, setup_path: str):
    """Update cache with loaded data"""
    import time
    _CACHE["rig"] = rig
    _CACHE["setup"] = setup
    _CACHE["rig_path"] = rig_path
    _CACHE["setup_path"] = setup_path
    _CACHE["last_load_time"] = time.time()

class CP77_OT_BakeFacialAnimation(Operator):
    """Bake facial animation over frame range
    
    Reads track values from armature custom properties on each frame,
    solves the facial system, and inserts bone keyframes.
    """
    bl_idname = "cp77.bake_facial_animation"
    bl_label = "Bake Facial Animation"
    bl_options = {'REGISTER', 'UNDO'}
    
    frame_start: bpy.props.IntProperty(
        name="Start Frame",
        description="First frame to bake",
        default=1,
        min=0
    )
    frame_end: bpy.props.IntProperty(
        name="End Frame",
        description="Last frame to bake",
        default=250,
        min=0
    )
    keyframe_step: bpy.props.IntProperty(
        name="Keyframe Step",
        description="Insert keyframes every N frames (1 = every frame)",
        default=1,
        min=1,
        max=10
    )
    
    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'
    
    def _ensure_loaded(self, context) -> Tuple[Optional[RigSkeleton], Optional[FacialSetup]]:
        """Load rig and setup from cache or file"""
        from . import _CACHE
        
        if _CACHE.get("rig") is not None and _CACHE.get("setup") is not None:
            return _CACHE["rig"], _CACHE["setup"]
        
        props = context.scene.cp77_facial
        if props.rig_json and props.facial_json:
            try:
                rig = load_wkit_rig_skeleton(props.rig_json)
                setup = load_wkit_facialsetup(props.facial_json, rig)
                _CACHE["rig"] = rig
                _CACHE["setup"] = setup
                return rig, setup
            except Exception as e:
                print(f"Failed to load rig/setup: {e}")
                return None, None
        return None, None

    @staticmethod
    def _additive_local_pose(
        base_q: np.ndarray, base_t: np.ndarray, base_s: np.ndarray,
        add_q: np.ndarray, add_t: np.ndarray, add_s: np.ndarray,
        weight: float
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Apply additive pose with weight (vectorized for all bones)
        """
        ident = np.zeros_like(add_q)
        ident[..., 3] = 1.0
        
        w = float(np.clip(weight, 0.0, 1.0))
        
        if w <= 1e-6:
            return base_q, base_t, base_s
        
        # Create weight array for broadcasting
        tw = np.full((base_q.shape[0], 1), w, dtype=base_q.dtype)
        
        # Quaternion: slerp from identity to additive, then multiply
        dq = quat_slerp(ident, add_q, tw)
        out_q = quat_multiply(base_q, dq)
        
        # Translation: weighted addition
        out_t = base_t + add_t * tw
        
        # Scale: weighted blend (not used but kept for completeness)
        out_s = base_s * (1.0 + (add_s - 1.0) * tw)
        
        return quat_normalize(out_q), out_t, out_s
    
    @staticmethod
    def _local_deltas(
        ref_q: np.ndarray, ref_t: np.ndarray, ref_s: np.ndarray,
        q: np.ndarray, t: np.ndarray, s: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute deltas from reference pose"""
        # Quaternion delta: q_delta = q_ref^-1 * q
        rx, ry, rz, rw = np.moveaxis(ref_q, -1, 0)
        inv_ref = np.stack([-rx, -ry, -rz, rw], axis=-1)
        
        ax, ay, az, aw = np.moveaxis(inv_ref, -1, 0)
        bx, by, bz, bw = np.moveaxis(q, -1, 0)
        dq = np.stack([
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz,
        ], axis=-1)
        dq = quat_normalize(dq)
        
        # Translation delta: simple subtraction
        dt = t - ref_t
        
        # Scale delta: division (avoid divide by zero)
        ds = s / np.where(ref_s == 0.0, 1.0, ref_s)
        
        return dq, dt, ds
    
    
    def _apply_solved_pose(
        self,
        context,
        rig: RigSkeleton,
        setup: FacialSetup,
        obj,
        frame: int
    ) -> bool:
        """Solve and apply facial pose for a single frame"""
        # Read track values from armature
        tracks = build_tracks_from_armature(obj, rig)
        
        # Solve facial system
        try:
            result = solve_tracks_face(setup, rig, tracks)
        except Exception as e:
            self.report({'ERROR'}, f'Solver error at frame {frame}: {e}')
            return False
        
        inbtw = np.asarray(result.get('inbetween_weights', np.zeros((0,), dtype=np.float32)))
        corr = np.asarray(result.get('corrective_weights', np.zeros((0,), dtype=np.float32)))
        
        # Start from reference pose
        q_ls = rig.ls_q.copy()
        t_ls = rig.ls_t.copy()
        s_ls = rig.ls_s.copy()
        
        # Apply main in-betweens
        Pm_bank = getattr(setup.face_main_bank, 'q', np.zeros((0,))).shape[0]
        Pm_apply = int(min(Pm_bank, inbtw.shape[0]))
        eps = 1e-6
        
        for pi in range(Pm_apply):
            w = float(inbtw[pi])
            if w > eps:
                q_ls, t_ls, s_ls = self._additive_local_pose(
                    q_ls, t_ls, s_ls,
                    setup.face_main_bank.q[pi],
                    setup.face_main_bank.t[pi],
                    setup.face_main_bank.s[pi],
                    w
                )
        
        # Apply correctives
        Pc_bank = getattr(setup.face_corrective_bank, 'q', np.zeros((0,))).shape[0]
        Pc_apply = int(min(Pc_bank, corr.shape[0]))
        
        for ci in range(Pc_apply):
            w = float(corr[ci])
            if w > eps:
                q_ls, t_ls, s_ls = self._additive_local_pose(
                    q_ls, t_ls, s_ls,
                    setup.face_corrective_bank.q[ci],
                    setup.face_corrective_bank.t[ci],
                    setup.face_corrective_bank.s[ci],
                    w
                )
        
        # Convert to deltas and swap coordinate system
        dq, dt, ds = self._local_deltas(rig.ls_q, rig.ls_t, rig.ls_s, q_ls, t_ls, s_ls)
        dt2, dq2 = bartmoss_math.swap_yz_trn_rot(dt, dq)
        
        # Apply to bones
        bones = obj.pose.bones
        for i, name in enumerate(rig.bone_names):
            pb = bones.get(name)
            if pb is None:
                continue
            
            pb.location = mathutils.Vector((
                float(dt2[i, 0]),
                float(dt2[i, 1]),
                float(dt2[i, 2])
            ))
            pb.rotation_mode = 'QUATERNION'
            pb.rotation_quaternion = mathutils.Quaternion((
                float(dq2[i, 3]),  # w
                float(dq2[i, 0]),  # x
                float(dq2[i, 1]),  # y
                float(dq2[i, 2])   # z
            ))
            pb.scale = mathutils.Vector((
                float(ds[i, 0]),
                float(ds[i, 1]),
                float(ds[i, 2])
            ))
        
        return True
    
    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'ARMATURE':
            self.report({'ERROR'}, 'Select an Armature object.')
            return {'CANCELLED'}
        
        # Load rig and setup (cached)
        rig, setup = self._ensure_loaded(context)
        if rig is None or setup is None:
            self.report({'ERROR'}, 'Load rig + facialsetup first.')
            return {'CANCELLED'}
        
        # Ensure pose mode
        if context.object.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')
        
        # Ensure action exists
        if not obj.animation_data:
            obj.animation_data_create()
        if not obj.animation_data.action:
            obj.animation_data.action = bpy.data.actions.new(name="FacialAnimation")
        
        action = obj.animation_data.action
        
        # Validate frame range
        if self.frame_end < self.frame_start:
            self.report({'ERROR'}, 'End frame must be >= start frame.')
            return {'CANCELLED'}
        
        # Bake loop
        frame_count = 0
        for frame in range(self.frame_start, self.frame_end + 1, self.keyframe_step):
            context.scene.frame_set(frame)
            
            # Solve and apply pose
            if not self._apply_solved_pose(context, rig, setup, obj, frame):
                return {'CANCELLED'}
            
            # Insert keyframes for all facial bones
            # Note: Could optimize by only keying changed bones
            for bone in obj.pose.bones:
                bone.keyframe_insert(data_path="location", frame=frame)
                bone.keyframe_insert(data_path="rotation_quaternion", frame=frame)
                bone.keyframe_insert(data_path="scale", frame=frame)
            
            frame_count += 1
        
        obj.update_tag(refresh={'DATA'})
        context.view_layer.update()
        
        self.report({'INFO'}, f'Baked {frame_count} frames ({self.frame_start}-{self.frame_end}).')
        return {'FINISHED'}
    
    def invoke(self, context, event):
        self.frame_start = context.scene.frame_start
        self.frame_end = context.scene.frame_end
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "frame_start")
        layout.prop(self, "frame_end")
        layout.prop(self, "keyframe_step")

class CP77_OT_ResetTracksToDefaults(Operator):
    """Reset all facial track custom properties to reference defaults"""
    bl_idname = "cp77.reset_tracks_defaults"
    bl_label = "Reset Tracks to Defaults"
    bl_description = "Reset all facial animation track values to their reference defaults from rig JSON"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'
    
    def execute(self, context):
        obj = context.active_object
        

        rig = _CACHE.get("rig")
        
        if not rig:
            self.report({'ERROR'}, "No rig loaded. Import facial setup first.")
            return {'CANCELLED'}
        
        if not hasattr(rig, 'reference_tracks'):
            self.report({'ERROR'}, "Rig has no reference_tracks data")
            return {'CANCELLED'}
        
        # Apply defaults
        try:
            create_track_properties(obj, rig, apply_defaults=True)
            self.report({'INFO'}, f"Reset {len(rig.track_names)} tracks to defaults")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to reset tracks: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

class CP77_OT_CreateTrackProperties(Operator):
    """Create all facial track custom properties with defaults"""
    bl_idname = "cp77.create_track_properties"
    bl_label = "Create Track Properties"
    bl_description = "Create all facial animation track custom properties on the armature"
    bl_options = {'REGISTER', 'UNDO'}
    
    apply_defaults: BoolProperty(
        name="Apply Default Values",
        description="Set properties to their reference defaults from rig JSON",
        default=True
    )
    
    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'
    
    def execute(self, context):
        obj = context.active_object
        
        # Get rig from cache
        from . import _state
        rig = _state.get("rig")
        
        if not rig:
            self.report({'ERROR'}, "No rig loaded. Import facial setup first.")
            return {'CANCELLED'}
        
        try:
            create_track_properties(obj, rig, apply_defaults=self.apply_defaults)
            
            if self.apply_defaults:
                self.report({'INFO'}, f"Created {len(rig.track_names)} track properties with defaults")
            else:
                self.report({'INFO'}, f"Created {len(rig.track_names)} track properties (zero values)")
            
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to create properties: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "apply_defaults")

class CP77_OT_ZeroAllTracks(Operator):
    """Set all facial track values to zero"""
    bl_idname = "cp77.zero_all_tracks"
    bl_label = "Zero All Tracks"
    bl_description = "Set all facial animation track custom properties to 0.0"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'
    
    def execute(self, context):
        obj = context.active_object
        
        # Get rig from cache
        from . import _state
        rig = _state.get("rig")
        
        if not rig:
            self.report({'WARNING'}, "No rig loaded - will zero all existing track properties")
        
        # Zero all track properties
        count = 0
        for key in obj.keys():
            # Skip Blender internal properties
            if key.startswith('_'):
                continue
            
            # Check if it's a track property (numeric)
            try:
                if isinstance(obj[key], (int, float)):
                    obj[key] = 0.0
                    count += 1
            except:
                pass
        
        self.report({'INFO'}, f"Set {count} track properties to zero")
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

class CP77_OT_ClearFacialAnimation(Operator):
    """Clear all facial animation keyframes"""
    bl_idname = "cp77.clear_facial_animation"
    bl_label = "Clear Facial Animation"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return (context.active_object and 
                context.active_object.type == 'ARMATURE' and
                context.active_object.animation_data and
                context.active_object.animation_data.action)
    
    def execute(self, context):
        obj = context.active_object
        action = obj.animation_data.action
        
        if not action:
            self.report({'INFO'}, 'No action to clear.')
            return {'CANCELLED'}
        
        # Remove all F-curves
        fcurves_to_remove = list(action.fcurves)
        for fc in fcurves_to_remove:
            action.fcurves.remove(fc)
        
        self.report({'INFO'}, f'Cleared {len(fcurves_to_remove)} F-curves.')
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

class CP77_FacialProps(PropertyGroup):
    rig_json: StringProperty(
        name="Rig JSON", 
        subtype='FILE_PATH',
        description="Path to *_skeleton_rig.json file"
    )
    facial_json: StringProperty(
        name="FacialSetup JSON", 
        subtype='FILE_PATH',
        description="Path to *_facialsetup.json file"
    )
    main_pose: IntProperty(
        name="Main Pose", 
        default=1, 
        min=1,
        max=133,  
        step=1,
        description="Select main pose to preview (1-133)"
    )
    preview_weight: FloatProperty(
        name="Weight",
        default=1.0,
        min=0.0,
        max=2.0,
        description="Pose weight for preview"
    )

class CP77_OT_LoadFacial(Operator):
    bl_idname = "cp77.load_facial"
    bl_label = "Load Rig + FacialSetup"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.cp77_facial
        
        # Validate paths
        if not props.rig_json:
            self.report({'ERROR'}, "Please select a rig JSON file")
            return {'CANCELLED'}
        if not props.facial_json:
            self.report({'ERROR'}, "Please select a facial setup JSON file")
            return {'CANCELLED'}
        
        try:
            # Load with error handling
            rig = load_wkit_rig_skeleton(props.rig_json)
            setup = load_wkit_facialsetup(props.facial_json, rig)
            
            # Cache loaded data
            _set_cache(rig, setup, props.rig_json, props.facial_json)
            
            # Report success with stats
            nb = rig.num_bones
            mp = setup.face_main_bank.q.shape[0]
            cp = setup.face_corrective_bank.q.shape[0]
            
            self.report({'INFO'}, 
                f"Loaded: {nb} bones, {mp} main poses, {cp} correctives")
            return {'FINISHED'}
            
        except FileNotFoundError as e:
            self.report({'ERROR'}, f"File not found: {e}")
            return {'CANCELLED'}
        except ValueError as e:
            self.report({'ERROR'}, f"Invalid data: {e}")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, f"Load failed: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

class CP77_OT_ApplyMainPose(Operator):
    bl_idname = "cp77.apply_main_pose"
    bl_label = "Apply (Full Solver)"
    bl_options = {'REGISTER', 'UNDO'}

    def _ensure_loaded(self, context) -> bool:
        if _CACHE["rig"] is not None and _CACHE["setup"] is not None:
            return True
        props = context.scene.cp77_facial
        if props.rig_json and props.facial_json:
            try:
                rig = load_wkit_rig_skeleton(props.rig_json)
                setup = load_wkit_facialsetup(props.facial_json, rig)
                _set_cache(rig, setup, props.rig_json, props.facial_json)
                return True
            except Exception:
                return False
        return False

    @staticmethod
    def _additive_local_pose_only(base_q: np.ndarray, base_t: np.ndarray, base_s: np.ndarray,
                                  add_q: np.ndarray, add_t: np.ndarray, add_s: np.ndarray,
                                  weight: float, mask_indices: Optional[list] = None):
        """Apply additive LS deltas with optional sparse bone mask."""
        ident = np.zeros_like(add_q); ident[..., 3] = 1.0
        w = float(np.clip(weight, 0.0, 1.0))
        if w <= 1e-6:
            return base_q, base_t, base_s
        if mask_indices is None or len(mask_indices) == 0:
            tw = np.full((base_q.shape[0], 1), w, dtype=base_q.dtype)
            dq = quat_slerp(ident, add_q, tw)
            out_q = quat_multiply(base_q, dq)
            out_t = base_t + add_t * tw
            out_s = base_s * (1.0 + (add_s - 1.0) * tw)
            return quat_normalize(out_q), out_t, out_s
        # sparse path
        out_q = base_q.copy(); out_t = base_t.copy(); out_s = base_s.copy()
        for i in mask_indices:
            if i < 0 or i >= base_q.shape[0]:
                continue
            dq = quat_slerp(ident[i:i+1], add_q[i:i+1], np.array([[w]], dtype=base_q.dtype))
            out_q[i] = quat_multiply(base_q[i:i+1], dq)[0]
            out_t[i] = base_t[i] + add_t[i] * w
            out_s[i] = base_s[i] * (1.0 + (add_s[i] - 1.0) * w)
        return quat_normalize(out_q), out_t, out_s

    @staticmethod
    def _pose_mask_from_bank_pose(bank, idx: int) -> Optional[list]:
        """Build sparse bone list that actually changes in this pose
        
        Returns None if all bones change, or list of bone indices if sparse.
        Threshold: only include bones with >1e-6 change in any component.
        """
        q = bank.q[idx]
        t = bank.t[idx]
        s = bank.s[idx]
        
        # Identity values
        qi = np.zeros_like(q)
        qi[..., 3] = 1.0
        
        # Check for changes
        q_changed = (np.abs(q - qi).max(axis=-1) > 1e-6)
        t_changed = (np.abs(t).max(axis=-1) > 1e-9)
        s_changed = (np.abs(s - 1.0).max(axis=-1) > 1.0e-6)
        
        changed = q_changed | t_changed | s_changed
        ids = np.where(changed)[0]
        
        # Return None if too many bones (dense apply is faster)
        # Return sparse list if < 50% of bones changed
        if ids.size == 0:
            return []
        elif ids.size > len(q) * 0.5:
            return None
        else:
            return ids.tolist()

    @staticmethod
    def _local_deltas(ref_q: np.ndarray, ref_t: np.ndarray, ref_s: np.ndarray,
                      q: np.ndarray, t: np.ndarray, s: np.ndarray):
        rx, ry, rz, rw = np.moveaxis(ref_q, -1, 0)
        inv_ref = np.stack([-rx, -ry, -rz, rw], axis=-1)
        ax, ay, az, aw = np.moveaxis(inv_ref, -1, 0)
        bx, by, bz, bw = np.moveaxis(q, -1, 0)
        dq = np.stack([
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz,
        ], axis=-1)
        dq = quat_normalize(dq)
        dt = t - ref_t
        ds = s / np.where(ref_s == 0.0, 1.0, ref_s)
        return dq, dt, ds

    def execute(self, context):
        if not self._ensure_loaded(context):
            self.report({'ERROR'}, "Load rig + facialsetup first.")
            return {'CANCELLED'}
        rig = _CACHE["rig"]; setup = _CACHE["setup"]

        obj = context.active_object
        if obj is None or obj.type != 'ARMATURE':
            self.report({'ERROR'}, 'Select an Armature object.')
            return {'CANCELLED'}

        # Build tracks from armature custom properties (names from rig.track_names)
        tracks = build_tracks_from_armature(obj, rig)

        # Optional convenience: force controller of selected main pose to >= 1.0
        p = int(max(0, context.scene.cp77_facial.main_pose))
        try:
            ctrl_trk = int(setup.face_meta.mainposes_track[p])
            if 0 <= ctrl_trk < tracks.shape[0]:
                tracks[ctrl_trk] = max(1.0, float(tracks[ctrl_trk]))
        except Exception:
            pass

        try:
            res = solve_tracks_face(setup, rig, tracks)
        except Exception as e:
            self.report({'ERROR'}, f'Solver error: {e}')
            return {'CANCELLED'}

        inbtw = np.asarray(res.get('inbetween_weights', np.zeros((0,), dtype=np.float32)))
        corr  = np.asarray(res.get('corrective_weights', np.zeros((0,), dtype=np.float32)))

        # Start from reference LS; apply in-between & corrective banks additively
        q_ls = rig.ls_q.copy(); t_ls = rig.ls_t.copy(); s_ls = rig.ls_s.copy()

        # Apply main in-betweens
        Pm_bank = getattr(setup.face_main_bank, 'q', np.zeros((0,))).shape[0]
        Pm_apply = int(min(Pm_bank, inbtw.shape[0]))
        eps = 1e-6
        for pi in range(Pm_apply):
            w = float(inbtw[pi])
            if w <= eps:
                continue
            mask_ids = self._pose_mask_from_bank_pose(setup.face_main_bank, pi)
            q_ls, t_ls, s_ls = self._additive_local_pose_only(q_ls, t_ls, s_ls,
                                                              setup.face_main_bank.q[pi],
                                                              setup.face_main_bank.t[pi],
                                                              setup.face_main_bank.s[pi],
                                                              w, mask_ids)

        # Apply correctives
        Pc_bank = getattr(setup.face_corrective_bank, 'q', np.zeros((0,))).shape[0]
        Pc_apply = int(min(Pc_bank, corr.shape[0]))
        for ci in range(Pc_apply):
            w = float(corr[ci])
            if w <= eps:
                continue
            mask_ids = self._pose_mask_from_bank_pose(setup.face_corrective_bank, ci)
            q_ls, t_ls, s_ls = self._additive_local_pose_only(q_ls, t_ls, s_ls,
                                                              setup.face_corrective_bank.q[ci],
                                                              setup.face_corrective_bank.t[ci],
                                                              setup.face_corrective_bank.s[ci],
                                                              w, mask_ids)

        # Convert LS to deltas against reference
        dq, dt, ds = self._local_deltas(rig.ls_q, rig.ls_t, rig.ls_s, q_ls, t_ls, s_ls)
        # Map JSON space → Blender space (translation & rotation)
        dt2, dq2 = bartmoss_math.swap_yz_trn_rot(dt, dq)

        if context.object.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')
        bones = obj.pose.bones
        for i, name in enumerate(rig.bone_names):
            pb = bones.get(name)
            if pb is None:
                continue
            pb.location = mathutils.Vector((float(dt2[i, 0]), float(dt2[i, 1]), float(dt2[i, 2])))
            pb.rotation_mode = 'QUATERNION'
            pb.rotation_quaternion = mathutils.Quaternion((float(dq2[i, 3]), float(dq2[i, 0]), float(dq2[i, 1]), float(dq2[i, 2])))
            pb.scale = mathutils.Vector((float(ds[i, 0]), float(ds[i, 1]), float(ds[i, 2])))
        obj.update_tag(refresh={'DATA'}); context.view_layer.update()

        self.report({'INFO'}, 'Applied facial pose.')
        return {'FINISHED'}

class CP77_OT_PreviewFacialPose(Operator):
    """Preview facial poses in real-time for testing and verification"""
    bl_idname = "cp77.preview_facial_pose"
    bl_label = "Preview Facial Pose"
    bl_description = "Apply a test facial pose to verify rig setup"
    bl_options = {'REGISTER', 'UNDO'}
    
    # Predefined test poses
    pose_type: bpy.props.EnumProperty(
        name="Pose Type",
        items=[
            ('NEUTRAL', "Neutral", "Relaxed neutral face"),
            ('AA', "AA - 'father'", "Open jaw, neutral lips"),
            ('IY', "IY - 'beet'", "Slight jaw, wide lips"),
            ('UW', "UW - 'boot'", "Slight jaw, puckered lips"),
            ('M', "M - 'mom'", "Closed jaw, lip closure"),
            ('F', "F - 'fun'", "Slight jaw, lip-teeth"),
            ('S', "S - 'sun'", "Narrow jaw, stretched"),
            ('TH', "TH - 'think'", "Slight jaw, tongue forward"),
            ('SMILE', "Smile", "Wide lips, raised corners"),
            ('POUT', "Pout", "Puckered lips"),
            ('JAW_OPEN', "Jaw Open", "Max jaw opening"),
            ('CUSTOM', "Custom JALI", "Manual JA/LI control"),
        ],
        default='NEUTRAL'
    )
    
    custom_jaw: bpy.props.FloatProperty(
        name="Jaw (JA)",
        default=0.5,
        min=0.0,
        max=1.0,
        description="Jaw opening (0 = closed, 1 = max open)"
    )
    
    custom_lip: bpy.props.FloatProperty(
        name="Lip (LI)",
        default=0.0,
        min=-1.0,
        max=1.0,
        description="Lip shaping (-1 = pucker, 0 = neutral, 1 = wide)"
    )
    
    intensity: bpy.props.FloatProperty(
        name="Intensity",
        default=1.0,
        min=0.0,
        max=2.0,
        description="Pose intensity multiplier"
    )
    
    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE'
    
    def execute(self, context):
        obj = context.active_object
        
        from . import _CACHE
        rig = _CACHE.get("rig")
        setup = _CACHE.get("setup")
        
        if not rig or not setup:
            self.report({'ERROR'}, 'Load rig + facialsetup first.')
            return {'CANCELLED'}
        
        ja, li = self._get_jali_params()
        ja *= self.intensity
        li *= self.intensity
        
        from .jali_bridge import JALIToCp77Bridge
        bridge = JALIToCp77Bridge()
        
        track_names = [str(n) if not isinstance(n, dict) else n.get('$value', '') 
                      for n in rig.track_names]
        
        ja_curve = np.array([ja], dtype=np.float32)
        li_curve = np.array([li], dtype=np.float32)
        
        tracks = bridge.jali_to_tracks(ja_curve, li_curve, track_names)
        
        for i, name in enumerate(track_names):
            if not name:
                continue
            
            value = float(tracks[0, i])
            if name not in obj:
                obj[name] = value
                if hasattr(obj, 'id_properties_ui'):
                    ui = obj.id_properties_ui(name)
                    ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0)
            else:
                obj[name] = value
        
        if context.object.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')
        
        result = self._apply_solved_pose(context, rig, setup, obj, tracks[0, :])
        
        if result:
            self.report({'INFO'}, f'Applied {self.pose_type} pose (JA={ja:.2f}, LI={li:.2f})')
        
        return {'FINISHED'}
    
    def _get_jali_params(self) -> Tuple[float, float]:
        from .jali_core import ARPABET_JALI_MAP
        
        if self.pose_type == 'CUSTOM':
            return self.custom_jaw, self.custom_lip
        
        pose_map = {
            'NEUTRAL': (0.3, 0.0),
            'AA': (1.0, 0.0),
            'IY': (0.15, 0.9),
            'UW': (0.2, -0.95),
            'M': (0.0, 0.0),
            'F': (0.1, 0.1),
            'S': (0.05, 0.4),
            'TH': (0.15, 0.0),
            'SMILE': (0.3, 0.8),
            'POUT': (0.2, -0.9),
            'JAW_OPEN': (1.0, 0.0),
        }
        
        if self.pose_type in ARPABET_JALI_MAP:
            jali = ARPABET_JALI_MAP[self.pose_type]
            return jali.jaw, jali.lip
        
        return pose_map.get(self.pose_type, (0.3, 0.0))
    
    def _apply_solved_pose(self, context, rig, setup, obj, tracks_in: np.ndarray) -> bool:
        from .tracksolvers import solve_tracks_face
        
        try:
            result = solve_tracks_face(setup, rig, tracks_in)
        except Exception as e:
            self.report({'ERROR'}, f'Solver error: {e}')
            return False
        
        inbtw = np.asarray(result.get('inbetween_weights', np.zeros((0,), dtype=np.float32)))
        corr = np.asarray(result.get('corrective_weights', np.zeros((0,), dtype=np.float32)))
        
        q_ls = rig.ls_q.copy()
        t_ls = rig.ls_t.copy()
        s_ls = rig.ls_s.copy()
        
        Pm_bank = getattr(setup.face_main_bank, 'q', np.zeros((0,))).shape[0]
        Pm_apply = int(min(Pm_bank, inbtw.shape[0]))
        eps = 1e-6
        
        for pi in range(Pm_apply):
            w = float(inbtw[pi])
            if w > eps:
                q_ls, t_ls, s_ls = CP77_OT_BakeFacialAnimation._additive_local_pose(
                    q_ls, t_ls, s_ls,
                    setup.face_main_bank.q[pi],
                    setup.face_main_bank.t[pi],
                    setup.face_main_bank.s[pi],
                    w
                )
        
        Pc_bank = getattr(setup.face_corrective_bank, 'q', np.zeros((0,))).shape[0]
        Pc_apply = int(min(Pc_bank, corr.shape[0]))
        
        for ci in range(Pc_apply):
            w = float(corr[ci])
            if w > eps:
                q_ls, t_ls, s_ls = CP77_OT_BakeFacialAnimation._additive_local_pose(
                    q_ls, t_ls, s_ls,
                    setup.face_corrective_bank.q[ci],
                    setup.face_corrective_bank.t[ci],
                    setup.face_corrective_bank.s[ci],
                    w
                )
        
        dq, dt, ds = CP77_OT_BakeFacialAnimation._local_deltas(rig.ls_q, rig.ls_t, rig.ls_s, q_ls, t_ls, s_ls)
        dt2, dq2 = bartmoss_math.swap_yz_trn_rot(dt, dq)
        
        import mathutils
        bones = obj.pose.bones
        for i, name in enumerate(rig.bone_names):
            pb = bones.get(name)
            if pb is None:
                continue
            
            pb.location = mathutils.Vector((float(dt2[i, 0]), float(dt2[i, 1]), float(dt2[i, 2])))
            pb.rotation_mode = 'QUATERNION'
            pb.rotation_quaternion = mathutils.Quaternion((
                float(dq2[i, 3]), float(dq2[i, 0]), float(dq2[i, 1]), float(dq2[i, 2])
            ))
            pb.scale = mathutils.Vector((float(ds[i, 0]), float(ds[i, 1]), float(ds[i, 2])))
        
        context.view_layer.update()
        return True
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=350)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "pose_type", text="")
        
        if self.pose_type == 'CUSTOM':
            box = layout.box()
            box.label(text="JALI Parameters:", icon='SETTINGS')
            box.prop(self, "custom_jaw", slider=True)
            box.prop(self, "custom_lip", slider=True)
        
        layout.separator()
        layout.prop(self, "intensity", slider=True)

class CP77_OT_GenerateJALILipSync(Operator):
    """Generate JALI-based lipsync animation for CP77 facial system"""
    bl_idname = "cp77.generate_jali_lipsync"
    bl_label = "Generate JALI Lipsync"
    bl_description = "Analyze audio and generate procedural facial animation using JALI"
    bl_options = {'REGISTER', 'UNDO'}
    
    audio_path: bpy.props.StringProperty(
        name="Audio File",
        subtype='FILE_PATH',
        description="Audio file to analyze (.wav, .mp3, .ogg)"
    )
    
    transcript: bpy.props.StringProperty(
        name="Transcript (Optional)",
        description="Text transcript for better accuracy"
    )
    
    use_transcript: bpy.props.BoolProperty(
        name="Use Transcript",
        default=False,
        description="Use transcript for forced alignment (more accurate)"
    )
    
    jaw_multiplier: bpy.props.FloatProperty(
        name="Jaw Multiplier",
        default=1.0,
        min=0.0,
        max=2.0,
        description="Scale jaw opening (1.0 = normal, 2.0 = exaggerated)"
    )
    
    lip_multiplier: bpy.props.FloatProperty(
        name="Lip Multiplier",
        default=1.0,
        min=0.0,
        max=2.0,
        description="Scale lip shaping (1.0 = normal, 2.0 = exaggerated)"
    )
    
    @classmethod
    def poll(cls, context):
        return (context.active_object and 
                context.active_object.type == 'ARMATURE')
    
    def execute(self, context):
        if not PARSELMOUTH_AVAILABLE:
            self.report({'ERROR'}, "Install parselmouth: pip install praat-parselmouth")
            return {'CANCELLED'}
        
        audio_path = bpy.path.abspath(self.audio_path)
        if not audio_path or not Path(audio_path).exists():
            self.report({'ERROR'}, f"Audio file not found: {audio_path}")
            return {'CANCELLED'}
        
        # Load rig/setup from cache
        from . import _CACHE
        rig = _CACHE.get("rig")
        setup = _CACHE.get("setup")
        
        if not rig or not setup:
            self.report({'ERROR'}, "Load facial rig + setup first (Import Facial Setup)")
            return {'CANCELLED'}
        
        try:
            # Detect phonemes
            self.report({'INFO'}, "Detecting phonemes from audio...")
            
            if self.use_transcript and self.transcript.strip():
                aligner = TranscriptAligner(audio_path, self.transcript)
                phoneme_events = aligner.align_phonemes()
                self.report({'INFO'}, f"Aligned {len(phoneme_events)} phonemes with transcript")
            else:
                detector = SimplePhonemeDetector(audio_path)
                phoneme_events = detector.detect_phonemes()
                self.report({'INFO'}, f"Detected {len(phoneme_events)} phonemes (acoustic-only)")
            
            if not phoneme_events:
                self.report({'WARNING'}, "No phonemes detected")
                return {'CANCELLED'}
            
            # Generate animation
            self.report({'INFO'}, "Generating JALI animation...")
            
            from .jali_bridge import JALIAnimationPipeline
            
            pipeline = JALIAnimationPipeline(
                rig=rig,
                setup=setup,
                fps=context.scene.render.fps
            )
            
            tracks, inbetweens, correctives = pipeline.generate_animation(
                phoneme_events,
                audio_path=audio_path
            )
            
            # Apply multipliers
            if self.jaw_multiplier != 1.0 or self.lip_multiplier != 1.0:
                self.report({'INFO'}, f"Applying multipliers (Jaw: {self.jaw_multiplier:.2f}, Lip: {self.lip_multiplier:.2f})")
                
                # Get track indices for jaw/lip controls
                track_names = [str(n) if not isinstance(n, dict) else n.get('$value', '') 
                              for n in rig.track_names]
                
                for i, name in enumerate(track_names):
                    if 'jaw' in name.lower():
                        tracks[:, i] *= self.jaw_multiplier
                    elif 'lips' in name.lower() or 'mouth' in name.lower():
                        tracks[:, i] *= self.lip_multiplier
            
            # Apply to armature
            self.report({'INFO'}, "Applying animation to armature...")
            pipeline.apply_to_armature(
                context.active_object,
                tracks,
                start_frame=context.scene.frame_start
            )
            
            # Update timeline
            duration = phoneme_events[-1].end + 0.5
            context.scene.frame_end = int(duration * context.scene.render.fps) + 10
            
            self.report({'INFO'}, f"✓ Lipsync complete! ({duration:.2f}s, {len(phoneme_events)} phonemes)")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)
    
    def draw(self, context):
        layout = self.layout
        
        layout.label(text="Audio Input:", icon='SPEAKER')
        layout.prop(self, "audio_path", text="")
        
        layout.separator()
        layout.prop(self, "use_transcript")
        
        if self.use_transcript:
            box = layout.box()
            box.label(text="Transcript:", icon='TEXT')
            box.prop(self, "transcript", text="")
        
        layout.separator()
        layout.label(text="JALI Parameters:", icon='SETTINGS')
        
        col = layout.column(align=True)
        col.prop(self, "jaw_multiplier", slider=True)
        col.prop(self, "lip_multiplier", slider=True)

class CP77_OT_ResetNeutral(Operator):
    bl_idname = "cp77.reset_neutral"
    bl_label = "Reset to Rest"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'ARMATURE':
            self.report({'ERROR'}, 'Select an Armature object.')
            return {'CANCELLED'}
        if context.object.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')
        for pb in obj.pose.bones:
            pb.matrix_basis.identity()
        obj.update_tag(refresh={'DATA'}); context.view_layer.update()
        return {'FINISHED'}

class CP77_PT_FacialPreview(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'CP77 Modding'
    bl_parent_id = 'CP77_PT_animspanel'
    bl_options = {'DEFAULT_CLOSED'} 
    bl_label = 'Facial Pose Tools'
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.cp77_facial
        
        # File selection
        col = layout.column(align=True)
        col.prop(props, "rig_json")
        col.prop(props, "facial_json")
        row = layout.row(align=True)
        row.operator("cp77.load_facial", icon='FILE_FOLDER')
        
        # Show cache status
        if _CACHE.get("rig") is not None:
            box = layout.box()
            rig = _CACHE["rig"]
            setup = _CACHE["setup"]
            box.label(text=f"Loaded: {rig.num_bones} bones", icon='CHECKMARK')
            box.label(text=f"Main poses: {setup.face_main_bank.q.shape[0]}")
        
        layout.separator()
        
        # Preview controls
        col = layout.column(align=True)
        col.label(text="Preview (Single Frame):", icon='RESTRICT_VIEW_OFF')
        
        row = col.row(align=True)
        row.prop(props, "main_pose", text="Pose")
        
        row = col.row(align=True)
        row.prop(props, "preview_weight", text="Weight", slider=True)
        
        row = col.row(align=True)
        row.operator("cp77.apply_main_pose", text="Apply Pose", icon='PLAY')
        row.operator("cp77.reset_neutral", text="", icon='ARMATURE_DATA')

        row = col.row(align=True)
        row.operator("cp77.reset_tracks_defaults", icon='ARMATURE_DATA')
        
        layout.separator()
        
        # Animation controls
        col = layout.column(align=True)
        col.label(text="Facial Animation:", icon='ANIM')
        row = layout.row(align=True)
        row.operator("cp77.bake_facial_animation", text="Bake Facial Animation", icon='REC')
        row.operator("cp77.clear_facial_animation", text="", icon='X')
        #col.operator("cp77.preview_facial_pose", icon='ANIM')
        #col.operator("cp77.generate_jali_lipsync", icon='ANIM')
operators, other_classes = get_classes(sys.modules[__name__])

operators, other_classes = get_classes(sys.modules[__name__])


def register_animtools():
    """Register all animation tool classes"""
    
    # Register operators
    for cls in operators:
        if not hasattr(bpy.types, cls.__name__):
            try:
                register_class(cls)
            except ValueError:
                pass  # Already registered
    
    # Register other classes (panels, property groups)
    for cls in other_classes:
        if not hasattr(bpy.types, cls.__name__):
            try:
                register_class(cls)
            except ValueError:
                pass  # Already registered
    
    # Register property groups
    bpy.types.Scene.cp77_facial = bpy.props.PointerProperty(type=CP77_FacialProps)
    
    # Register root motion tools
    root_motion.register_rm()

def unregister_animtools():
    """Unregister all animation tool classes"""
    
    global _handle
    
    # Stop bone line drawing if active
    if _handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_handle, 'WINDOW')
        except Exception:
            pass
        _handle = None
    
    # Unregister root motion tools
    root_motion.unregister_rm()
    
    # Unregister property groups
    if hasattr(bpy.types.Scene, 'cp77_facial'):
        del bpy.types.Scene.cp77_facial
    
    # Unregister other classes in reverse order
    for cls in reversed(other_classes):
        try:
            unregister_class(cls)
        except RuntimeError:
            pass  # Not registered
    
    # Unregister operators in reverse order
    for cls in reversed(operators):
        try:
            unregister_class(cls)
        except RuntimeError:
            pass  # Not registered
