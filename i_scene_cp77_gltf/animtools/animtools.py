import re

from .compat import (
    assign_action_with_slot,
    configure_float_idproperty,
    get_action_fcurves,
    )
from ..importers.read_rig import *
from ..importers.read_rig import _model_space_matrices_cached
from ..main.animation_bones import ANIMATION_BONES, ANIMATION_BONE_SET
from ..main.bartmoss_functions import restore_previous_context, safe_mode_switch, store_current_context

animBones = list(ANIMATION_BONES)

def CP77AnimsList(self, context):
    for action in bpy.data.actions:
        if action.library:
            continue
        yield action

def _assign_action(adt, action):
    owner = getattr(adt, "id_data", None)
    if owner is None:
        adt.action = action
        return adt
    return assign_action_with_slot(owner, action)


def reset_armature(self, context):
    obj = context.active_object
    if not obj or obj.type != 'ARMATURE':
        self.report({'ERROR'}, "Active object must be an armature.")
        return {'CANCELLED'}

    for pose_bone in obj.pose.bones:
        pose_bone.matrix_basis.identity()

    return {'FINISHED'}

def create_track_properties(armature_obj, rig, apply_defaults: bool = True):
    """Ensure canonical track properties without replacing facial UI metadata."""
    if not armature_obj or armature_obj.type != "ARMATURE":
        return
    defaults = getattr(rig, "reference_tracks", ())
    for index, raw_name in enumerate(rig.track_names):
        track_name = raw_name.get("$value", "") if isinstance(raw_name, dict) else str(raw_name)
        if not track_name:
            continue
        default_value = float(defaults[index]) if index < len(defaults) else 0.0
        current = armature_obj.get(track_name)
        value = default_value if apply_defaults or current is None else float(current)
        configure_float_idproperty(
            armature_obj,
            track_name,
            value,
            default=default_value,
            minimum=0.0,
            maximum=1.0,
            soft_minimum=0.0,
            soft_maximum=1.0,
            description=f"Facial track {index}: {track_name}",
            subtype="FACTOR",
            overwrite_ui=False,
        )

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
            safe_mode_switch(current_context)

def remap_action_to_armature(source_action, armature_obj):
    new_action = source_action.copy()
    new_action.name = f"{source_action.name}_REMAPPED_{armature_obj.name}"
    pattern = re.compile(r'^pose\.bones\[(["\'])(.*?)\1\](.*)$')
    for fcurve in get_action_fcurves(new_action, armature_obj) or ():
        match = pattern.match(fcurve.data_path)
        if match is None:
            continue
        bone_name = match.group(2)
        if bone_name not in armature_obj.pose.bones:
            continue
        fcurve.data_path = f'pose.bones["{bone_name}"]{match.group(3)}'
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

def _load_bind_pose(self, arm_obj, *, use_tpose: bool):
    arm_data = arm_obj.data
    filepath = arm_data.get("source_rig_file", "")
    if not filepath or ";" in filepath or not os.path.isfile(filepath):
        self.report({"ERROR"}, f"Invalid single-rig JSON source: {filepath}")
        return {"CANCELLED"}

    rig_data = read_rig(filepath)
    matrices = (
        list(_model_space_matrices_cached(rig_data.bone_transforms, rig_data.parent_indices))
        if use_tpose
        else build_apose_matrices(
            rig_data.apose_ms,
            rig_data.apose_ls,
            rig_data.bone_names,
            rig_data.parent_indices,
        )
    )
    if not matrices:
        pose_name = "T-Pose" if use_tpose else "A-Pose"
        self.report({"ERROR"}, f"No complete {pose_name} found in {rig_data.rig_name}")
        return {"CANCELLED"}

    store_current_context()
    try:
        safe_mode_switch("EDIT")
        edit_bones = arm_data.edit_bones
        bone_index_map = {index: edit_bones.get(name) for index, name in enumerate(rig_data.bone_names)}
        missing = [rig_data.bone_names[index] for index, bone in bone_index_map.items() if bone is None]
        if missing:
            self.report({"ERROR"}, f"Armature is missing {len(missing)} rig bones")
            return {"CANCELLED"}
        for index, matrix in enumerate(matrices):
            apply_bone_from_matrix(
                index, matrix, bone_index_map, rig_data.parent_indices, matrices
            )
        arm_data["T-Pose"] = use_tpose
    finally:
        restore_previous_context()

    for pose_bone in arm_obj.pose.bones:
        pose_bone.matrix_basis.identity()
    self.report({"INFO"}, "T-Pose loaded" if use_tpose else "A-Pose loaded")
    return {"FINISHED"}


def load_apose(self, arm_obj):
    return _load_bind_pose(self, arm_obj, use_tpose=False)


def load_tpose(self, arm_obj):
    return _load_bind_pose(self, arm_obj, use_tpose=True)

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
        if b.name not in ANIMATION_BONE_SET
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
    return list(ANIMATION_BONES)

def is_animation_bone(bone_name):
    return bone_name in ANIMATION_BONE_SET

def validate_armature(obj):
    if not obj or obj.type != 'ARMATURE':
        return False
    if not obj.data or not obj.data.bones:
        return False
    return True