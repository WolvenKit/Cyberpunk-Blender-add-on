import sys
import bpy
import bpy.utils.previews
from bpy.types import (Operator, OperatorFileListElement, PropertyGroup, Panel)
from bpy.props import (StringProperty, BoolProperty, IntProperty, CollectionProperty)
from ..main.bartmoss_functions import *
from ..cyber_props import cp77riglist
from ..icons.cp77_icons import get_icon
from ..main.common import get_classes
from ..importers.import_with_materials import CP77GLBimport
from .animtools import *
from .generate_rigs import create_rigify_rig
from ..importers.read_rig import *
from .facial import *
from .tracksolvers import (
    build_tracks_from_armature,
    solve_tracks_face,  
)
import os
from typing import Dict, List, Tuple, Optional
from .facial import load_wkit_facialsetup, load_wkit_rig_skeleton
from .tracksolvers import solve_tracks_face
from .tracks import export_anim_tracks, import_anim_tracks
from .animtracks import (_ensure_armature, _get_fps, _ensure_custom_prop, _fcurve_for_prop, _keyframe_scalar
)
def CP77AnimsList(self, context):
    for action in bpy.data.actions:
        if action.library:
            continue
        yield action
_state = {"rig": None, "setup": None}
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
        if 'T-Pose' in obj.data:
            if obj.data['T-Pose'] is True:
                col.operator('cp77.load_apose')
            else:
                col.operator('cp77.load_tpose')
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
            self.load_apose(arm_obj)

            # Then load multi-source if any extensions exist
            
            #if "rig_sources" in arm_data and arm_data["rig_sources"]:
            #    self.load_multi_source_apose(arm_obj)
            # todo: reimplement rig merging and decomposing

            return {'FINISHED'}

        except Exception as e:
            print(traceback.format_exc())
            self.report({'ERROR'}, f"Failed: {e}")
            return {'CANCELLED'}

    def load_apose(self, arm_obj):
        arm_data = arm_obj.data
        filepath = arm_data.get('source_rig_file', None)
        bone_names = arm_data.get('boneNames', [])
        bone_parents = arm_data.get('boneParentIndexes', [])
        safe_mode_switch('EDIT')
        edit_bones = arm_data.edit_bones
        if not os.path.exists(filepath):
            self.report({'ERROR'}, f"Invalid path to json source {filepath} not found")
            return

        rig_data = read_rig(filepath)
        apose_ms = rig_data.apose_ms
        apose_ls = rig_data.apose_ls
        

        if apose_ms is None and apose_ls is None:
            self.report({'ERROR'}, f"No A-Pose found in {rig_data.rig_name} json source")
            return
        
        bone_index_map = {}

        for i, name in enumerate(rig_data.bone_names):
            bone = edit_bones.get(name)
            bone_index_map[i] = bone

        pose_matrices = build_apose_matrices(apose_ms, apose_ls, bone_names, bone_parents)
        if not pose_matrices:
            self.report({'ERROR'}, f"Error building A-Pose matrices for {rig_data.rig_name}")
            print
            return

        for i, name in enumerate(rig_data.bone_names):
            mat = pose_matrices[i]
            apply_bone_from_matrix(i, mat, bone_index_map, rig_data.bone_parents, pose_matrices)
        safe_mode_switch("OBJECT")

        self.report({'INFO'}, "A-Pose loaded")

class LoadTPose(Operator):
    bl_idname = "cp77.load_tpose"
    bl_label = "Load T-Pose"

    def execute(self, context):
        arm_obj = context.object
        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, "This isnt' an armature, can't load T-Pose")
            return {'CANCELLED'}
        try:    
            self.load_tpose(arm_obj)
            return {'FINISHED'}
        
        except Exception as e:
            print(traceback.format_exc())
            self.report({'ERROR'}, f"Failed: {e}")
            return{'CANCELLED'}
    
    def load_tpose(self, arm_obj):
        arm_data = arm_obj.data
        filepath = arm_data.get('source_rig_file', None)
        bone_names = arm_data.get('boneNames', [])
        bone_parents = arm_data.get('boneParentIndexes', [])
        safe_mode_switch('EDIT')
        edit_bones = arm_data.edit_bones


        # Make sure the path exists
        if not os.path.exists(filepath):
            self.report({'ERROR'}, f"Invalid path to json source {filepath} not found")
            return
        #Load Fresh Data
        rig_data = read_rig(filepath)

        bone_index_map = {}

        for i, name in enumerate(rig_data.bone_names):
            bone = edit_bones.get(name)
            bone_index_map[i] = bone
            print(f'index{i} = {bone.name} = {bone}')
        
        global_transforms = {}
        for i in range(len(rig_data.bone_names)):
            mat_red = compute_global_transform(i, rig_data.bone_transforms, rig_data.bone_parents, global_transforms)

            global_transforms[i] = mat_red

        for i in range(len(rig_data.bone_transforms)):
            transform_data = rig_data.bone_transforms[i]
            if is_identity_transform(transform_data):
                continue  # leave stub alone
            apply_bone_from_matrix(i, global_transforms[i], bone_index_map, rig_data.bone_parents, global_transforms)
            arm_data['T-Pose'] = True
        safe_mode_switch('OBJECT')
        
        self.report({'INFO'}, "A-Pose loaded")
        return

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


_CACHE = {"rig": None, "setup": None, "rig_path": "", "setup_path": ""}


def _set_cache(rig, setup, rig_path: str, setup_path: str):
    _CACHE["rig"] = rig
    _CACHE["setup"] = setup
    _CACHE["rig_path"] = rig_path
    _CACHE["setup_path"] = setup_path


class CP77_FacialProps(PropertyGroup):
    rig_json: StringProperty(name="Rig JSON", subtype='FILE_PATH')  
    facial_json: StringProperty(name="FacialSetup JSON", subtype='FILE_PATH')  
    main_pose: IntProperty(name="Main Pose", default=1, min=1,max=133, step=1)  

class CP77_OT_LoadFacial(Operator):
    bl_idname = "cp77.load_facial"
    bl_label = "Load Rig + FacialSetup"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.cp77_facial
        try:
            rig = load_wkit_rig_skeleton(props.rig_json or "")
            setup = load_wkit_facialsetup(props.facial_json or "", rig)
        except Exception as e:
            self.report({'ERROR'}, f"Load failed: {e}")
            return {'CANCELLED'}
        _set_cache(rig, setup, props.rig_json or "", props.facial_json or "")
        try:
            nb = int(getattr(rig, 'num_bones', 0)); mp = int(setup.face_main_bank.q.shape[0])
        except Exception:
            nb, mp = 0, 0
        self.report({'INFO'}, f"Loaded bones={nb}, mainPoses={mp}")
        return {'FINISHED'}


class CP77_OT_ApplyMainPose(bpy.types.Operator):
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

    # --- math helpers (local; names stable) ---
    @staticmethod
    def _quat_normalize(q: np.ndarray) -> np.ndarray:
        n = np.linalg.norm(q, axis=-1, keepdims=True); n[n == 0] = 1.0; return q / n

    @staticmethod
    def _quat_mul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        ax, ay, az, aw = np.moveaxis(a, -1, 0); bx, by, bz, bw = np.moveaxis(b, -1, 0)
        x = aw * bx + ax * bw + ay * bz - az * by
        y = aw * by - ax * bz + ay * bw + az * bx
        z = aw * bz + ax * by - ay * bx + az * bw
        w = aw * bw - ax * bx - ay * by - az * bz
        return np.stack([x, y, z, w], axis=-1)

    @staticmethod
    def _slerp(q0: np.ndarray, q1: np.ndarray, t: np.ndarray) -> np.ndarray:
        dot = np.sum(q0 * q1, axis=-1, keepdims=True)
        sign = np.where(dot < 0, -1.0, 1.0)
        q1 = q1 * sign
        dot = np.clip(np.abs(dot), 0.0, 1.0)
        eps = 1e-6
        use_lerp = dot > 1 - eps
        theta = np.arccos(dot)
        sin_theta = np.sin(theta)
        w0 = np.where(use_lerp, 1 - t, np.sin((1 - t) * theta) / np.where(sin_theta == 0, 1, sin_theta))
        w1 = np.where(use_lerp, t, np.sin(t * theta) / np.where(sin_theta == 0, 1, sin_theta))
        out = CP77_OT_ApplyMainPose._quat_normalize(q0 * w0 + q1 * w1)
        return out

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
            dq = CP77_OT_ApplyMainPose._slerp(ident, add_q, tw)
            out_q = CP77_OT_ApplyMainPose._quat_mul(base_q, dq)
            out_t = base_t + add_t * tw
            out_s = base_s * (1.0 + (add_s - 1.0) * tw)
            return CP77_OT_ApplyMainPose._quat_normalize(out_q), out_t, out_s
        # sparse path
        out_q = base_q.copy(); out_t = base_t.copy(); out_s = base_s.copy()
        for i in mask_indices:
            if i < 0 or i >= base_q.shape[0]:
                continue
            dq = CP77_OT_ApplyMainPose._slerp(ident[i:i+1], add_q[i:i+1], np.array([[w]], dtype=base_q.dtype))
            out_q[i] = CP77_OT_ApplyMainPose._quat_mul(base_q[i:i+1], dq)[0]
            out_t[i] = base_t[i] + add_t[i] * w
            out_s[i] = base_s[i] * (1.0 + (add_s[i] - 1.0) * w)
        return CP77_OT_ApplyMainPose._quat_normalize(out_q), out_t, out_s

    @staticmethod
    def _pose_mask_from_bank_pose(bank, idx: int) -> Optional[list]:
        q = bank.q[idx]; t = bank.t[idx]; s = bank.s[idx]
        qi = np.zeros_like(q); qi[..., 3] = 1.0
        changed = (np.abs(q - qi).max(axis=-1) > 1e-6) | (np.abs(t).max(axis=-1) > 1e-9) | (np.abs(s - 1.0).max(axis=-1) > 1.0e-6)
        ids = np.where(changed)[0]
        return ids.tolist() if ids.size else None

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
        dq = CP77_OT_ApplyMainPose._quat_normalize(dq)
        dt = t - ref_t
        ds = s / np.where(ref_s == 0.0, 1.0, ref_s)
        return dq, dt, ds

    @staticmethod
    def _swap_yz_trn_rot(dt: np.ndarray, dq: np.ndarray):
        """Map JSON space → Blender space: (x, y, z) → (x, -z, y) and rotate quats by +90° around X.
        Applies to translations and rotations only (scales unchanged).
        """
        # translation: [x, -z, y]
        dt_sw = np.stack([dt[:, 0], -dt[:, 2], dt[:, 1]], axis=-1)
        # rotation: q' = s * q * s^{-1}, s = rotX(+90°)
        s = np.array([np.sqrt(0.5, dtype=dq.dtype), 0.0, 0.0, np.sqrt(0.5, dtype=dq.dtype)], dtype=dq.dtype)
        s_inv = s.copy(); s_inv[:3] *= -1.0
        s_b = np.broadcast_to(s, dq.shape)
        s_inv_b = np.broadcast_to(s_inv, dq.shape)
        q_tmp = CP77_OT_ApplyMainPose._quat_mul(s_b, dq)
        dq_sw = CP77_OT_ApplyMainPose._quat_mul(q_tmp, s_inv_b)
        return dt_sw, dq_sw

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
        dt2, dq2 = self._swap_yz_trn_rot(dt, dq)

        import mathutils
        if context.object.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')
        bones = obj.pose.bones
        for i, name in enumerate(rig.bone_names):
            pb = bones.get(name)
            if pb is None:
                continue
            pb.location = mathutils.Vector((float(dt[i, 0]), float(dt[i, 1]), float(dt[i, 2])))
            pb.rotation_mode = 'QUATERNION'
            pb.rotation_quaternion = mathutils.Quaternion((float(dq[i, 3]), float(dq[i, 0]), float(dq[i, 1]), float(dq[i, 2])))
            pb.scale = mathutils.Vector((float(ds[i, 0]), float(ds[i, 1]), float(ds[i, 2])))
        obj.update_tag(refresh={'DATA'}); context.view_layer.update()

        self.report({'INFO'}, 'Applied facial pose.')
        return {'FINISHED'}

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
    bl_label = 'Facial Preview (Full Solver)'
    def draw(self, context):
        layout = self.layout
        props = context.scene.cp77_facial
        col = layout.column(align=True)
        col.prop(props, "rig_json")
        col.prop(props, "facial_json")
        row = layout.row(align=True)
        row.operator("cp77.load_facial", icon='FILE_FOLDER')
        layout.separator()
        col = layout.column(align=True)
        col.prop(props, "main_pose")
        row = layout.row(align=True)
        row.operator("cp77.apply_main_pose", icon='PLAY')
        row.operator("cp77.reset_neutral", icon='ARMATURE_DATA')

operators, other_classes = get_classes(sys.modules[__name__])


def register_animtools():
    for cls in operators:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
    for cls in other_classes:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
        bpy.types.Scene.cp77_facial = bpy.props.PointerProperty(type=CP77_FacialProps)  # type: ignore



def unregister_animtools():
    if hasattr(bpy.types.Scene, 'CP77_facial'):
        del bpy.types.Scene.cp77_facial
    for cls in reversed(other_classes):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
    for cls in reversed(operators):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)