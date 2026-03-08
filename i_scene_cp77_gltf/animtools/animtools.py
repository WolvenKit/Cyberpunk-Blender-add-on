import bpy
import json
import re
from ..importers.read_rig import *
from ..main.bartmoss_functions import safe_mode_switch, store_current_context, restore_previous_context

animBones = [
    "Hips", "Spine", "Spine1", "Spine2", "Spine3",
    "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand", "WeaponLeft",
    "LeftInHandThumb", "LeftHandThumb1", "LeftHandThumb2",
    "LeftInHandIndex", "LeftHandIndex1", "LeftHandIndex2", "LeftHandIndex3",
    "LeftInHandMiddle", "LeftHandMiddle1", "LeftHandMiddle2", "LeftHandMiddle3",
    "LeftInHandRing", "LeftHandRing1", "LeftHandRing2", "LeftHandRing3",
    "LeftInHandPinky", "LeftHandPinky1", "LeftHandPinky2", "LeftHandPinky3",
    "RightShoulder", "RightArm", "RightForeArm", "RightHand", "WeaponRight",
    "RightInHandThumb", "RightHandThumb1", "RightHandThumb2",
    "RightInHandIndex", "RightHandIndex1", "RightHandIndex2", "RightHandIndex3",
    "RightInHandMiddle", "RightHandMiddle1", "RightHandMiddle2", "RightHandMiddle3",
    "RightInHandRing", "RightHandRing1", "RightHandRing2", "RightHandRing3",
    "RightInHandPinky", "RightHandPinky1", "RightHandPinky2", "RightHandPinky3",
    "Neck", "Neck1", "Head", "LeftEye", "RightEye",
    "LeftUpLeg", "LeftLeg", "LeftFoot", "LeftHeel", "LeftToeBase",
    "RightUpLeg", "RightLeg", "RightFoot", "RightHeel", "RightToeBase"
]

def CP77AnimsList(self, context):
    for action in bpy.data.actions:
        if action.library:
            continue
        yield action

def _assign_action(adt, action):
    adt.action = action

    if not hasattr(adt, 'action_slot'):
        return

    suitable = getattr(adt, 'action_suitable_slots', ())
    if suitable:
        adt.action_slot = suitable[0]
        return

    slots = getattr(action, 'slots', None)
    if slots is not None:
        try:
            slot = slots.new(id_type='OBJECT')
            adt.action_slot = slot
        except Exception as e:
            print(f"[CP77] Could not create action slot: {e}")

def delete_unused_bones(self, context):
    obj = context.active_object
    if not obj or obj.type != 'ARMATURE':
        self.report({'ERROR'}, "Active object must be an armature.")
        return {'CANCELLED'}

    all_vertex_groups = set()
    for child in obj.children:
        if child.type == 'MESH':
            all_vertex_groups.update(vg.name for vg in child.vertex_groups)

    if not all_vertex_groups:
        self.report({'WARNING'}, "No vertex groups found in mesh children.")
        return {'CANCELLED'}

    original_mode = obj.mode

    try:
        if obj and obj.name in bpy.data.objects and original_mode != 'EDIT':
            safe_mode_switch('EDIT')
    except Exception as e:
        self.report({'ERROR'}, f"Failed to switch to edit mode: {e}")
        return {'CANCELLED'}

    try:
        edit_bones = obj.data.edit_bones
        bones_to_remove = []
        for bone in edit_bones:
            base_name = re.sub(r'\.\d+$', '', bone.name)
            if bone.name not in all_vertex_groups and base_name not in all_vertex_groups:
                bones_to_remove.append(bone)

        try:
            cp77_addon_prefs = context.preferences.addons['i_scene_cp77_gltf'].preferences
            verbose = not cp77_addon_prefs.non_verbose
        except (KeyError, AttributeError):
            verbose = True

        for bone in bones_to_remove:
            if verbose:
                print(f"Deleting unused bone: {bone.name}")
            edit_bones.remove(bone)

    except Exception as e:
        self.report({'ERROR'}, f"Error during bone deletion: {e}")
        return {'CANCELLED'}

    finally:
        try:
            if obj and obj.name in bpy.data.objects and obj.mode != original_mode:
                safe_mode_switch(original_mode)
        except Exception as e:
            print(f"Warning: Could not restore original mode: {e}")

    self.report({'INFO'}, f"Removed {len(bones_to_remove)} unused bones.")
    return {'FINISHED'}

def reset_armature(self, context):
    obj = context.active_object
    if not obj or obj.type != 'ARMATURE':
        self.report({'ERROR'}, "Active object must be an armature.")
        return {'CANCELLED'}

    reset_count = 0
    for pose_bone in obj.pose.bones:
        pose_bone.matrix_basis.identity()
        reset_count += 1

    return {'FINISHED'}

def create_track_properties(armature_obj, rig, apply_defaults: bool = True):
    if not armature_obj or armature_obj.type != 'ARMATURE':
        return

    track_names = [
        str(n) if not isinstance(n, dict) else n.get('$value', '')
        for n in rig.track_names
    ]

    defaults = rig.reference_tracks if hasattr(rig, 'reference_tracks') else None

    for i, track_name in enumerate(track_names):
        if not track_name:
            continue

        default_value = 0.0
        if defaults is not None and i < len(defaults):
            default_value = float(defaults[i])

        if track_name not in armature_obj:
            armature_obj[track_name] = default_value if apply_defaults else 0.0
            try:
                ui = armature_obj.id_properties_ui(track_name)
                ui.update(
                        description=f"Facial track {i}: {track_name}",
                        default=default_value,
                        min=0.0,
                        max=1.0,
                        soft_min=0.0,
                        soft_max=1.0,
                        subtype='FACTOR'
                        )
            except Exception as e:
                print(f"Warning: Could not set UI for {track_name}: {e}")
        elif apply_defaults:
            armature_obj[track_name] = default_value

def cp77_keyframe(self, context, frameall=False):
    current_context = bpy.context.mode
    armature = context.active_object

    if not armature or armature.type != 'ARMATURE':
        self.report({'ERROR'}, "Active object must be an armature.")
        return {'CANCELLED'}

    if current_context != 'POSE':
        try:
            bpy.ops.object.mode_set(mode='POSE')
        except Exception as e:
            self.report({'ERROR'}, f"Failed to switch to pose mode: {e}")
            return {'CANCELLED'}

    try:
        if not frameall:
            bpy.ops.anim.keyframe_insert_by_name(type="WholeCharacterSelected")
            self.report({'INFO'}, "Keyframe inserted at current frame.")
            return {'FINISHED'}
        else:
            if not armature.animation_data or not armature.animation_data.action:
                self.report({'ERROR'}, "Armature has no animation data or action.")
                return {'CANCELLED'}

            action = armature.animation_data.action
            frame_start = int(action.frame_range[0])
            frame_end = int(action.frame_range[1])
            step = getattr(context.scene, 'cp77_keyframe_step', 1)
            original_frame = context.scene.frame_current

            keyframe_count = 0
            for frame in range(frame_start, frame_end + 1, step):
                context.scene.frame_set(frame)
                bpy.ops.anim.keyframe_insert_by_name(type="WholeCharacterSelected")
                keyframe_count += 1

            context.scene.frame_set(original_frame)
            self.report({'INFO'}, f"Inserted keyframes at {keyframe_count} frames.")
            return {'FINISHED'}

    except Exception as e:
        self.report({'ERROR'}, f"Keyframe insertion failed: {e}")
        return {'CANCELLED'}

    finally:
        if bpy.context.mode != current_context:
            try:
                bpy.ops.object.mode_set(mode=current_context)
            except Exception:
                pass

def remap_action_to_armature(source_action, armature_obj):
    new_action = source_action.copy()
    new_action.name = source_action.name + "_REMAPPED_" + armature_obj.name

    bone_prefix = 'pose.bones["'
    bone_prefix_alt = "pose.bones['"

    for fcurve in new_action.fcurves:
        dp = fcurve.data_path
        if dp.startswith(bone_prefix) or dp.startswith(bone_prefix_alt):
            try:
                bone_name = dp.split('"')[1] if '"' in dp else dp.split("'")[1]
            except:
                continue

            if bone_name not in armature_obj.pose.bones:
                continue

            suffix = dp.split(']')[1]
            new_data_path = f'pose.bones["{bone_name}"]{suffix}'
            fcurve.data_path = new_data_path
        elif dp.startswith('["') or dp.startswith("[\'"):
            pass
        else:
            pass
    return new_action

def play_anim(self, context, anim_name: str):
    obj = context.active_object
    if obj is None or obj.type != 'ARMATURE':
        self.report({'ERROR'}, "Active object must be an armature.")
        return {'CANCELLED'}

    action = bpy.data.actions.get(anim_name)
    if action is None:
        self.report({'ERROR'}, f"Action '{anim_name}' not found.")
        return {'CANCELLED'}

    if obj.animation_data is None:
        obj.animation_data_create()

    _assign_action(obj.animation_data, action)

    context.view_layer.objects.active = obj

    scene = context.scene
    start, end = int(action.frame_range[0]), int(action.frame_range[1])
    if end <= start:
        end = start + 1
    scene.frame_start = start
    scene.frame_end   = end
    if not (start <= scene.frame_current <= end):
        scene.frame_current = start

    screen = context.screen
    if screen and screen.is_animation_playing:
        bpy.ops.screen.animation_cancel(restore_frame=False)

    wm = context.window_manager
    override_kwargs = None
    _ANIM_AREA_TYPES = {'VIEW_3D', 'TIMELINE', 'DOPESHEET_EDITOR',
                        'GRAPH_EDITOR', 'NLA_EDITOR'}

    for window in wm.windows:
        scr = window.screen
        for area in scr.areas:
            if area.type not in _ANIM_AREA_TYPES:
                continue
            for region in area.regions:
                if region.type == 'WINDOW':
                    override_kwargs = {
                        'window':     window,
                        'screen':     scr,
                        'area':       area,
                        'region':     region,
                        'scene':      context.scene,
                        'view_layer': context.view_layer,
                    }
                    break
            if override_kwargs:
                break
        if override_kwargs:
            break

    if override_kwargs is not None:
        with context.temp_override(**override_kwargs):
            bpy.ops.screen.animation_play()
    else:
        bpy.ops.screen.animation_play()

    return {'FINISHED'}

def load_apose(self, arm_obj):
    arm_data = arm_obj.data
    filepath = arm_data.get('source_rig_file', None)
    bone_names = arm_data.get('boneNames', [])
    bone_parents = arm_data.get('boneParentIndexes', [])
    store_current_context()
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
        return
    for i, name in enumerate(rig_data.bone_names):
        mat = pose_matrices[i]
        apply_bone_from_matrix(i, mat, bone_index_map, rig_data.parent_indices, pose_matrices)
    restore_previous_context()
    self.report({'INFO'}, "A-Pose loaded")

def load_tpose(self, arm_obj):
    arm_data = arm_obj.data
    filepath = arm_data.get('source_rig_file', None)
    store_current_context()
    safe_mode_switch('EDIT')
    edit_bones = arm_data.edit_bones
    if not os.path.exists(filepath):
        self.report({'ERROR'}, f"Invalid path to json source {filepath} not found")
        return
    rig_data = read_rig(filepath)
    bone_index_map = {}
    for i, name in enumerate(rig_data.bone_names):
        bone = edit_bones.get(name)
        bone_index_map[i] = bone

    global_transforms = {}
    for i in range(len(rig_data.bone_names)):
        mat_red = compute_global_transform(i, rig_data.bone_transforms, rig_data.parent_indices, global_transforms)
        global_transforms[i] = mat_red
    for i in range(len(rig_data.bone_transforms)):
        transform_data = rig_data.bone_transforms[i]
        if is_identity_transform(transform_data):
            continue
        apply_bone_from_matrix(i, global_transforms[i], bone_index_map, rig_data.parent_indices, global_transforms)
        arm_data['T-Pose'] = True
    restore_previous_context()

    self.report({'INFO'}, "T-Pose loaded")
    return

def delete_anim(self, context):
    if not hasattr(self, 'name'):
        return {'CANCELLED'}

    action = bpy.data.actions.get(self.name, None)
    if not action:
        return {'CANCELLED'}

    try:
        bpy.data.actions.remove(action)
        return {'FINISHED'}
    except Exception:
        return {'CANCELLED'}

def _set_bone_visibility(armature_object, hide_state, bone_filter=None):
    if not armature_object:
        return

    armature_data = armature_object.data

    for bone in armature_object.pose.bones:
        if bone_filter is None or bone.name in bone_filter:
            bone.hide = hide_state
    for bone in armature_data.bones:
        if bone_filter is None or bone.name in bone_filter:
            bone.hide = hide_state

def hide_extra_bones(self, context):
    selected_object = context.active_object

    if not selected_object or selected_object.type != 'ARMATURE':
        print("Select an armature object.")
        return

    bones_to_hide = [
        b.name for b in selected_object.pose.bones
        if b.name not in animBones
        ]

    _set_bone_visibility(selected_object, True, bones_to_hide)
    selected_object.update_tag()
    selected_object['deformBonesHidden'] = True

    if hasattr(self, 'report'):
        self.report({'INFO'}, f"Hidden {len(bones_to_hide)} extra bones")
    else:
        print(f"Hidden {len(bones_to_hide)} extra bones")

def unhide_extra_bones(self, context):
    selected_object = context.active_object

    if not selected_object or selected_object.type != 'ARMATURE':
        print("Select an armature object.")
        return

    _set_bone_visibility(selected_object, False, None)
    selected_object.update_tag()

    try:
        bpy.ops.wm.properties_remove(data_path="object", property_name="deformBonesHidden")
    except Exception:
        if 'deformBonesHidden' in selected_object:
            del selected_object['deformBonesHidden']

    print("Unhidden all bones")

def get_animation_bones():
    return animBones.copy()

def is_animation_bone(bone_name):
    return bone_name in animBones

def validate_armature(obj):
    if not obj or obj.type != 'ARMATURE':
        return False
    if not obj.data or not obj.data.bones:
        return False
    return True