import bpy
import json
import re
from ..importers.read_rig import *
from ..main.bartmoss_functions import safe_mode_switch, store_current_context, restore_previous_context
# Standard animation bones for CP77
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

def delete_unused_bones(self, context):
    """
    Deletes bones from the selected armature that do not have corresponding vertex groups
    in any of its child mesh objects.
    
    Args:
        self: Operator instance
        context: Blender context
        
    Returns:
        {'FINISHED'} or {'CANCELLED'}
    """
    obj = context.active_object
    if not obj or obj.type != 'ARMATURE':
        self.report({'ERROR'}, "Active object must be an armature.")
        return {'CANCELLED'}

    # Collect all vertex group names from all child meshes
    all_vertex_groups = set()
    for child in obj.children:
        if child.type == 'MESH':
            all_vertex_groups.update(vg.name for vg in child.vertex_groups)
    
    if not all_vertex_groups:
        self.report({'WARNING'}, "No vertex groups found in mesh children.")
        return {'CANCELLED'}

    original_mode = obj.mode
    
    # Safely switch to edit mode
    try:
        if obj and obj.name in bpy.data.objects and original_mode != 'EDIT':
            safe_mode_switch('EDIT')
    except Exception as e:
        self.report({'ERROR'}, f"Failed to switch to edit mode: {e}")
        return {'CANCELLED'}

    try:
        edit_bones = obj.data.edit_bones
        
        # Build a list of bones to remove
        bones_to_remove = []
        for bone in edit_bones:
            # Strip Blender's automatic .001, .002 suffixes
            base_name = re.sub(r'\.\d+$', '', bone.name)
            
            # Keep bone if either its name or base name has a vertex group
            if bone.name not in all_vertex_groups and base_name not in all_vertex_groups:
                bones_to_remove.append(bone)
        
        # Remove bones
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
        # Always restore the original mode
        try:
            if obj and obj.name in bpy.data.objects and obj.mode != original_mode:
                safe_mode_switch(original_mode)
        except Exception as e:
            print(f"Warning: Could not restore original mode: {e}")

    self.report({'INFO'}, f"Removed {len(bones_to_remove)} unused bones.")
    return {'FINISHED'}

def reset_armature(self, context):
    """
    Resets all pose bones of the selected armature to their rest position.
    
    Args:
        self: Operator instance
        context: Blender context
        
    Returns:
        {'FINISHED'} or {'CANCELLED'}
    """
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
    """Create custom properties for all tracks on armature
    
    Args:
        armature_obj: Blender armature object
        rig: RigSkeleton with track_names and reference_tracks
        apply_defaults: If True, set values to reference_tracks defaults
    """
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
        
        # Get default value
        default_value = 0.0
        if defaults is not None and i < len(defaults):
            default_value = float(defaults[i])
        
        # Create property if it doesn't exist
        if track_name not in armature_obj:
            armature_obj[track_name] = default_value if apply_defaults else 0.0
            
            # Set UI metadata
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
            # Property exists, just update value
            armature_obj[track_name] = default_value

def cp77_keyframe(self, context, frameall=False):
    """
    Insert keyframes for the armature, either at current frame or for entire animation.
    
    Args:
        self: Operator instance
        context: Blender context
        frameall: If True, keyframe entire animation range
        
    Returns:
        {'FINISHED'} or {'CANCELLED'}
    """
    current_context = bpy.context.mode
    armature = context.active_object
    
    if not armature or armature.type != 'ARMATURE':
        self.report({'ERROR'}, "Active object must be an armature.")
        return {'CANCELLED'}

    # Switch to pose mode if needed
    if current_context != 'POSE':
        try:
            bpy.ops.object.mode_set(mode='POSE')
        except Exception as e:
            self.report({'ERROR'}, f"Failed to switch to pose mode: {e}")
            return {'CANCELLED'}

    try:
        if not frameall:
            # Insert keyframe at current frame only
            bpy.ops.anim.keyframe_insert_by_name(type="WholeCharacterSelected")
            self.report({'INFO'}, "Keyframe inserted at current frame.")
            return {'FINISHED'}
        else:
            # Insert keyframes for entire animation
            if not armature.animation_data or not armature.animation_data.action:
                self.report({'ERROR'}, "Armature has no animation data or action.")
                return {'CANCELLED'}
            
            action = armature.animation_data.action
            frame_start = int(action.frame_range[0])
            frame_end = int(action.frame_range[1])
            
            # Get step size from scene properties if available
            step = getattr(context.scene, 'cp77_keyframe_step', 1)
            
            # Store current frame
            original_frame = context.scene.frame_current
            
            # Insert keyframes
            keyframe_count = 0
            for frame in range(frame_start, frame_end + 1, step):
                context.scene.frame_set(frame)
                bpy.ops.anim.keyframe_insert_by_name(type="WholeCharacterSelected")
                keyframe_count += 1
            
            # Restore original frame
            context.scene.frame_set(original_frame)
            
            self.report({'INFO'}, f"Inserted keyframes at {keyframe_count} frames.")
            return {'FINISHED'}
    
    except Exception as e:
        self.report({'ERROR'}, f"Keyframe insertion failed: {e}")
        return {'CANCELLED'}
    
    finally:
        # Restore original mode
        if bpy.context.mode != current_context:
            try:
                bpy.ops.object.mode_set(mode=current_context)
            except Exception:
                pass

def remap_action_to_armature(source_action, armature_obj):
    """
    Creates a duplicate of `source_action` with all F-curves remapped so they
    target `armature_obj` instead of the original armature the animation came from.
    """

    # Duplicate the action so we don’t overwrite the original
    new_action = source_action.copy()
    new_action.name = source_action.name + "_REMAPPED_" + armature_obj.name

    # Common prefixes for bone animation
    bone_prefix = 'pose.bones["'
    bone_prefix_alt = "pose.bones['"

    for fcurve in new_action.fcurves:
        dp = fcurve.data_path

        # Remap pose.bones["BoneName"] paths
        if dp.startswith(bone_prefix) or dp.startswith(bone_prefix_alt):
            # Extract the bone name from the data path
            try:
                bone_name = dp.split('"')[1] if '"' in dp else dp.split("'")[1]
            except:
                continue

            if bone_name not in armature_obj.pose.bones:
                # Bone doesn't exist on new armature → skip
                continue

            # Rebuild the RNA path for the new armature
            # e.g. pose.bones["Head"].rotation_quaternion
            suffix = dp.split(']')[1]  # .rotation_quaternion etc.
            new_data_path = f'pose.bones["{bone_name}"]{suffix}'
            fcurve.data_path = new_data_path

        # Remap ID custom props (rare)
        elif dp.startswith('["') or dp.startswith("[\'"):
            # Keep as-is; these follow the object, not the armature
            pass

        # Object-level transforms should remain unchanged
        else:
            # Example: 'location', 'rotation_euler', etc.
            pass

    return new_action

def play_anim(self, context, anim_name: str):
    """Play the named Action on the currently active armature.

    This version is written for Blender 4.5/5.0 and takes Slotted Actions
    into account by assigning an appropriate action slot on the armature's
    AnimData before starting playback.
    """
    obj = context.active_object

    # Require an active armature.
    if obj is None or obj.type != 'ARMATURE':
        self.report({'ERROR'}, "Active object must be an armature.")
        return {'CANCELLED'}

    # Look up the action by name.
    action = bpy.data.actions.get(anim_name)
    if action is None:
        self.report({'ERROR'}, f"Action '{anim_name}' not found.")
        return {'CANCELLED'}

    # Ensure the armature has animation data.
    if obj.animation_data is None:
        obj.animation_data_create()
    adt = obj.animation_data

    # If this action wasn't authored for this armature instance, duplicate and
    # remap it so that all F-Curves target this armature.
    if adt.action is not action:
        try:
            action = remap_action_to_armature(action, obj)
        except Exception as ex:
            print(f"[CP77 AnimTools] remap_action_to_armature failed: {ex}")
            # Fall back to using the original action.
        adt.action = action
    else:
        adt.action = action

    # --- Slotted Actions support (Blender 4.4+).
    # In 4.4+ each Action can have multiple slots. AnimData.action_slot
    # chooses which slot of the Action is used for this data-block.
    # For older Blender versions these attributes simply do not exist.
    try:
        if hasattr(adt, "action_suitable_slots") and hasattr(adt, "action_slot"):
            slot_identifier = None
            obj_name = obj.name
            ob_name = f"{obj_name}"

            # 1) First try to derive the handle directly from the Action's slots
            #    using the same naming convention you mentioned:
            #    bpy.data.actions[...].slots["OBArmature"].name_display
            action_slots = getattr(action, "slots", None)
            if action_slots is not None:
                try:
                    # Most collections expose get(name); otherwise fall back to a manual scan.
                    if hasattr(action_slots, "get"):
                        slot = action_slots.get(ob_name)
                    else:
                        slot = None
                        for s in action_slots:
                            if getattr(s, "name", None) == ob_name:
                                slot = s
                                break
                    if slot is not None:
                        slot_identifier = (
                            getattr(slot, "handle", None)
                            or getattr(slot, "identifier", None)
                            or getattr(slot, "name", None)
                        )
                except Exception as ex_slots:
                    print(f"[CP77 AnimTools] Failed to resolve slot from Action.slots: {ex_slots}")

            # 2) If that didn't yield anything, fall back to the generic
            #    AnimData.action_suitable_slots API recommended in the 4.4+
            #    upgrade notes.
            if slot_identifier is None:
                slots = adt.action_suitable_slots
                if slots:
                    # Prefer a slot whose display/name references this armature.
                    for candidate in slots:
                        name = getattr(candidate, "name", None)
                        name_display = getattr(candidate, "name_display", None)
                        handle = getattr(candidate, "handle", None)
                        ident = getattr(candidate, "identifier", None)

                        if name in {obj_name, ob_name} or name_display in {obj_name, ob_name}:
                            slot_identifier = handle or ident or name or name_display or candidate
                            break

                    # If nothing matched by name, just use the first suitable slot.
                    if slot_identifier is None:
                        first = slots[0]
                        slot_identifier = (
                            getattr(first, "handle", None)
                            or getattr(first, "identifier", None)
                            or getattr(first, "name", None)
                            or getattr(first, "name_display", None)
                            or first
                        )

            # Finally assign the slot identifier back onto the AnimData.
            if slot_identifier is not None:
                adt.action_slot = slot_identifier
    except Exception as ex:
        # Failing to assign a slot should not hard-crash playback; it will just
        # behave like pre-4.4 where the first slot is used implicitly.
        print(f"[CP77 AnimTools] Failed to assign action slot for '{obj.name}': {ex}")

    # Make sure this armature is the active one in the view layer.
    view_layer = context.view_layer
    view_layer.objects.active = obj

    # Sync scene frame range to the action (using the action's frame_range).
    scene = context.scene
    start, end = action.frame_range
    start = int(start)
    end = int(end)

    if end <= start:
        end = start + 1

    scene.frame_start = start
    scene.frame_end = end
    if scene.frame_current < start or scene.frame_current > end:
        scene.frame_current = start

    # Stop playback if it's already running, otherwise animation_play will just toggle.
    screen = context.screen
    if screen and screen.is_animation_playing:
        # Blender 4.5+ API: restore_frame arg is still present.
        bpy.ops.screen.animation_cancel(restore_frame=False)

    # Build a temp override so animation_play runs in a sensible area.
    wm = context.window_manager
    override_kwargs = None

    for window in wm.windows:
        scr = window.screen
        for area in scr.areas:
            if area.type in {'TIMELINE', 'DOPESHEET_EDITOR', 'GRAPH_EDITOR', 'NLA_EDITOR', 'VIEW_3D'}:
                region = None
                for region_candidate in area.regions:
                    if region_candidate.type == 'WINDOW':
                        region = region_candidate
                        break
                if region is not None:
                    override_kwargs = dict(
                        window=window,
                        screen=scr,
                        area=area,
                        region=region,
                        scene=scr.scene if hasattr(scr, "scene") else scene,
                        view_layer=window.view_layer if hasattr(window, "view_layer") else context.view_layer,
                    )
                    break
        if override_kwargs:
            break

    # Use the modern temp_override API (Blender 3.2+, standard in 4.5/5.0).
    if hasattr(context, "temp_override") and override_kwargs is not None:
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
        print
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
        mat_red = compute_global_transform(i, rig_data.bone_transforms, rig_data.parent_indices, global_transforms)
        global_transforms[i] = mat_red
    for i in range(len(rig_data.bone_transforms)):
        transform_data = rig_data.bone_transforms[i]
        if is_identity_transform(transform_data):
            continue  # leave stub alone
        apply_bone_from_matrix(i, global_transforms[i], bone_index_map, rig_data.parent_indices, global_transforms)
        arm_data['T-Pose'] = True
    restore_previous_context()
    
    self.report({'INFO'}, "A-Pose loaded")
    return

def delete_anim(self, context):
    """
    Delete an animation action by name.
    
    Args:
        self: Operator instance (must have 'name' attribute)
        context: Blender context
        
    Returns:
        {'FINISHED'} or {'CANCELLED'}
    """
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
    """
    Helper function to set bone visibility.

    Args:
        armature_object: Armature object (not data!)
        hide_state: Boolean, True to hide, False to show
        bone_filter: List of bone names to affect. If None, it affects all
    """
    if not armature_object:
        return

    armature_data = armature_object.data

    # Handles Pose and object mode visibility
    for bone in armature_object.pose.bones:
        if bone_filter is None or bone.name in bone_filter:
            bone.hide = hide_state
    # Handles edit mode visibility
    for bone in armature_data.bones:
        if bone_filter is None or bone.name in bone_filter:
            bone.hide = hide_state

def hide_extra_bones(context):
    """
    Hide all bones that are not in the animBones list.
    """
    selected_object = context.active_object

    if not selected_object or selected_object.type != 'ARMATURE':
        print("Select an armature object.")
        return

    bones_to_hide = [
        b.name for b in selected_object.pose.bones 
        if b.name not in animBones
    ]

    _set_bone_visibility(selected_object, False, bones_to_hide)

    selected_object.update_tag()

    selected_object['deformBonesHidden'] = True

    print(f"Hidden {len(bones_to_hide)} extra bones")

def unhide_extra_bones(self, context):
    """
    Unhide all bones in the armature.
    """
    selected_object = context.active_object

    if not selected_object or selected_object.type != 'ARMATURE':
        print("Select an armature object.")
        return

    # Pass None to unhide everything
    _set_bone_visibility(selected_object, False, None)

    selected_object.update_tag()

    # Remove the property
    try:
        bpy.ops.wm.properties_remove(data_path="object", property_name="deformBonesHidden")
    except Exception:
        if 'deformBonesHidden' in selected_object:
            del selected_object['deformBonesHidden']

    print("Unhidden all bones")
    
# Utility functions for external use
def get_animation_bones():
    """
    Get the list of standard animation bones.
    
    Returns:
        List of bone names
    """
    return animBones.copy()

def is_animation_bone(bone_name):
    """
    Check if a bone name is in the standard animation bone list.
    
    Args:
        bone_name: Name of the bone to check
        
    Returns:
        Boolean
    """
    return bone_name in animBones

def validate_armature(obj):
    """
    Validate that an object is a usable armature.
    
    Args:
        obj: Blender object to validate
        
    Returns:
        Boolean
    """
    if not obj or obj.type != 'ARMATURE':
        return False
    
    if not obj.data or not obj.data.bones:
        return False
    
    return True
