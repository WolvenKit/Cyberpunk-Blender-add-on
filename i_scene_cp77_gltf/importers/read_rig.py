import time
import traceback
import bpy
import json
import math
import time
from mathutils import Vector, Quaternion, Matrix
from ..main.common import loc, show_message
from ..jsontool import JSONTool
from ..cyber_props import CP77animBones
from ..main.datashards import RigData
from ..main.bartmoss_functions import *

def read_rig(filepath):
    """  
    uses jsontool to read the data from a .rig.json and then populates a data class with it - this makes it much easier and more accessible to access later
    """
    # TODO This needs to be moved into jsontool or maybe just live in datashards/some other module I haven't dreamed of yet
    # It broke sector export and I didn't want to keep messing with it today so I put it here for now    
    
    data = JSONTool.jsonload(filepath)
    base_name = os.path.basename(filepath)

    rig_name = base_name.replace(".rig.json", "")
    root = data.get("Data", {}).get("RootChunk", {})

    # Extract raw bone names and handle missing values 
    bone_names_raw = root.get("boneNames", [])
    bone_names = [
        entry.get("$value", "")
        for entry in bone_names_raw
        if isinstance(entry, dict) and "$value" in entry
    ]
                
    # Instantiate the RigData object with data from the JSON file.
    
    rig_data = RigData(
        rig_name=rig_name,
        disable_connect=rig_name.startswith("v_"),
        apose_ms=root.get("aPoseMS", []),
        apose_ls=root.get("aPoseLS", []),
        bone_transforms=root.get("boneTransforms", []),
        bone_parents=root.get("boneParentIndexes", []),
        bone_names=bone_names,
        parts=root.get("parts", []),
        track_names=root.get("trackNames", []),
        reference_tracks=root.get("referenceTracks", []),
        cooking_platform=root.get("cookingPlatform", ""),
        distance_category_to_lod_map=root.get("distanceCategoryToLodMap", []),
        ik_setups=root.get("ikSetups", []),
        level_of_detail_start_indices=root.get("levelOfDetailStartIndices", []),
        ragdoll_desc=root.get("ragdollDesc", []),
        ragdoll_names=root.get("ragdollNames", [])
    )

    return rig_data

def create_aposels_empties(obj, bone_names, bone_parents, bone_transforms, collection_name="aPoseLS_Debug"):
    """creates local space empties using the LS data from a rig JSON
    each empty's translation and rotation are applied in the space of their parent bone"""
    collection = bpy.data.collections.get(collection_name)
    if collection is None:
        collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(collection)

    empty_objects = {}

    for i, bonename in enumerate(bone_names):
        empty = bpy.data.objects.new(name=f"{collection_name}_{bonename}", object_data=None)
        empty.empty_display_size = 0.05
        empty.empty_display_type = 'ARROWS'
        empty.rotation_mode = 'QUATERNION'
        collection.objects.link(empty)
        empty_objects[i] = empty

    # parent empties
    for i, parent_index in enumerate(bone_parents):
        if parent_index != -1:
            child = empty_objects[i]
            parent = empty_objects.get(parent_index)
            if parent:
                child.parent = parent
                child.matrix_parent_inverse = parent.matrix_world.inverted()

    # apply local-space transforms
    for i, transform in enumerate(bone_transforms):
        t = transform["Translation"]
        r = transform["Rotation"]
        empty = empty_objects[i]
        bone_name = bone_names[i] 
        empty.location = (t["X"], t["Y"], t["Z"])
        empty.rotation_quaternion = Quaternion((
            r["r"],  # W  
            r["i"],  # X
            r["j"],  # Y
            r["k"],  # Z
        ))
        constraint = empty.constraints.new(type='COPY_TRANSFORMS')
        constraint.name = f"CopyTransforms_{bone_name}"
        constraint.target = obj
        constraint.subtarget = bone_name
        constraint.owner_space = 'WORLD'
        constraint.target_space = 'WORLD'
        empty['Owner'] = f"{obj.name} {bone_name}"
        empty['Space: '] = f"{collection_name}"
        empty["raw_translation"] = [t["X"], t["Y"], t["Z"]]
        empty["raw_rotation"] = [r["r"], r["i"], r["j"], r["k"]]
        empty["raw_translation"] = [t["X"], t["Y"], t["Z"]]
        empty["raw_rotation"] = [r["r"], r["i"], r["j"], r["k"]]

def create_aposems_empties(obj, bone_names, bone_parents, bone_transforms, collection_name="aPoseMS_Debug"):
    """
    Creates empties directly from the JSON model-space transforms (no hierarchy).
    Position and rotation are applied as-is from the JSON data.
    """
    collection = bpy.data.collections.get(collection_name)
    if collection is None:
        collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(collection)

    empty_objects = {}

    for i, name in enumerate(bone_names):
        empty = bpy.data.objects.new(name=f"aPoseMS_{name}_Debug", object_data=None)
        empty.empty_display_size = 0.05
        empty.empty_display_type = 'ARROWS'
        empty.rotation_mode = 'QUATERNION'
        collection.objects.link(empty)
        empty_objects[i] = empty


    for i, name in enumerate(bone_names):
        t = bone_transforms[i]["Translation"]
        r = bone_transforms[i]["Rotation"]

    for i, transform in enumerate(bone_transforms):
        t = transform["Translation"]
        r = transform["Rotation"]
        empty = empty_objects[i]
        bone_name = bone_names[i]

        empty.location = (t["X"], t["Y"], t["Z"])
        empty.rotation_quaternion = Quaternion((
            r["r"],  # W
            r["i"],  # X
            r["j"],  # Y
            r["k"],  # Z
        ))
        
        constraint = empty.constraints.new(type='COPY_TRANSFORMS')
        constraint.name = f"CopyTransforms_{bone_name}"
        constraint.target = obj
        constraint.subtarget = bone_name
        constraint.owner_space = 'WORLD'
        constraint.target_space = 'WORLD'
        empty['Owner'] = f"{obj.name} {bone_name}"
        empty['Space: '] = f"{collection_name}"
        empty["raw_translation"] = [t["X"], t["Y"], t["Z"]]
        empty["raw_rotation"] = [r["r"], r["i"], r["j"], r["k"]]

def create_debug_empties(obj, bone_names, bone_parents, bone_transforms, apose_ls, apose_ms, bind_pose):
    """
    Creates empties on an imported rig's joints for local and model space,
    and groups them under a parent collection
    """
    debug_collection_name = f"{obj.name}_transform_debugging"
    debug_collection = bpy.data.collections.get(debug_collection_name)
    if debug_collection is None:
        debug_collection = bpy.data.collections.new(debug_collection_name)
        bpy.context.scene.collection.children.link(debug_collection)
    debug_collection['owner'] = obj
    # Helper to create a child collection and link it to Debugging
    def ensure_debug_subcollection(sub_name, create_fn):
        if sub_name in bpy.data.collections:
            sub_col = bpy.data.collections[sub_name]
        else:
            sub_col = bpy.data.collections.new(sub_name)
            debug_collection.children.link(sub_col)
        create_fn(sub_col)

    if  bind_pose == 'A-Pose':
        if apose_ls is not None:
            ensure_debug_subcollection("aPoseLS", lambda col: create_aposels_empties(
            obj, bone_names, bone_parents, apose_ls, collection_name=col.name
            ))

        if apose_ms is not None:
            ensure_debug_subcollection("aPoseMS", lambda col: create_aposems_empties(
                obj, bone_names, bone_parents, apose_ms, collection_name=col.name
            ))
    else:
        if bone_transforms is not None:
            ensure_debug_subcollection("tPoseLS", lambda col: create_aposels_empties(
               obj, bone_names, bone_parents, bone_transforms, collection_name=col.name
            ))
    
def apply_bone_from_matrix(bone, mat, bone_index, bone_parents, global_transforms, default_length=0.01):
    safe_mode_switch('EDIT')
    head = mat.to_translation()

    # Find all children of this bone
    child_indices = [i for i, parent in enumerate(bone_parents) if parent == bone]
    #print(f"[{bone_index[bone].name}] Head: {head}, Children: {child_indices}")

    if child_indices:
        avg = sum((global_transforms[i].to_translation() for i in child_indices), Vector())
        avg /= len(child_indices)

        direction = avg - head
        #print(f"[{bone_index[bone].name}] Avg child head: {avg}, Direction: {direction}, Length: {direction.length}")

        if direction.length < 1e-6:
            # Fallback to Y axis
            y_axis = (mat.to_3x3() @ Vector((0, 1, 0))).normalized()
            direction = y_axis * default_length
            #print(f"[{bone_index[bone].name}] Direction fallback to local Y axis")
        else:
            direction = direction.normalized() * max(direction.length, default_length)

        tail = head + direction
    else:
        # No children — fallback to local Y
        y_axis = (mat.to_3x3() @ Vector((0, 1, 0))).normalized()
        tail = head + y_axis * default_length
        #print(f"[{bone_index[bone].name}] No children, using local Y for tail")

    # Final fallback: avoid zero-length bone
    if (tail - head).length < 1e-6:
        tail = head + Vector((0, default_length, 0))
        #print(f"[{bone_index[bone].name}] Final fallback applied — forced tail offset")

    bone_index[bone].head = head
    bone_index[bone].tail = tail

    x_axis = mat.to_3x3() @ Vector((1, 0, 0))
    bone_index[bone].align_roll(x_axis)

def compute_global_transform(index, transforms, parents, global_transforms):
    if index in global_transforms:
        return global_transforms[index]

    local_translation = Vector((
        transforms[index]["Translation"]["X"],
        transforms[index]["Translation"]["Y"],
        transforms[index]["Translation"]["Z"]
    ))        
    local_rotation = Quaternion((
        transforms[index]["Rotation"]["r"],        
        transforms[index]["Rotation"]["i"],
        transforms[index]["Rotation"]["j"],
        transforms[index]["Rotation"]["k"]
    ))
    local_scale = Vector((
        transforms[index]["Scale"]["X"],
        transforms[index]["Scale"]["Y"],
        transforms[index]["Scale"]["Z"]
    ))

    local_mat = Matrix.Translation(local_translation) @ local_rotation.to_matrix().to_4x4()
    local_mat = local_mat @ scale_matrix(local_scale)

    if parents[index] == -1:
        global_transforms[index] = local_mat
    else:
        parent_mat = compute_global_transform(parents[index], transforms, parents, global_transforms)
        global_transforms[index] = parent_mat @ local_mat

    return global_transforms[index]

def scale_matrix(s):
    m = Matrix.Identity(4)
    m[0][0], m[1][1], m[2][2] = s
    return m

def build_apose_matrices(apose_ms, apose_ls, bone_names, bone_parents):
    if apose_ms:
        def build_matrix(pose):
            T = Vector([pose["Translation"]["X"], pose["Translation"]["Y"], pose["Translation"]["Z"]])
            Q = Quaternion([pose["Rotation"]["r"], pose["Rotation"]["i"], pose["Rotation"]["j"], pose["Rotation"]["k"]])
            S = Vector([pose["Scale"]["X"], pose["Scale"]["Y"], pose["Scale"]["Z"]])
            return Matrix.Translation(T) @ Q.to_matrix().to_4x4() @ scale_matrix(S)
        return [build_matrix(p) for p in apose_ms]
    elif apose_ls:
        global_poses = {}
        for i in range(len(bone_names)):
            global_poses[i] = compute_global_transform(i, apose_ls, bone_parents, global_poses)
        return [global_poses[i] for i in range(len(bone_names))]
    return None

def is_identity_transform(transform):
    t = transform["Translation"]
    r = transform["Rotation"]
    s = transform["Scale"]
    return (
        abs(t["X"]) < 1e-6 and abs(t["Y"]) < 1e-6 and abs(t["Z"]) < 1e-6 and
        abs(r["r"]) < 1e-6 and abs(r["i"]) < 1e-6 and abs(r["j"]) < 1e-6 and abs(r["k"] - 1) < 1e-6 and
        abs(s["X"] - 1) < 1e-6 and abs(s["Y"] - 1) < 1e-6 and abs(s["Z"] - 1) < 1e-6
    )

def create_armature_from_data(filepath, bind_pose, create_debug=False):
    print(f"bind pose = {bind_pose}")
    start_time = time.time()

    rig_data = None
    arm_obj = None

    rig_data = read_rig(filepath)
    if not rig_data:
        show_message(f"Failed to load rig data from {filepath} ERROR")
        return None
    else:
        print(f'Beginning Import of: {rig_data.rig_name} from: {filepath} Bind Pose set to: {bind_pose}')
        context = bpy.context
        safe_mode_switch('OBJECT')
        bpy.ops.object.add(type='ARMATURE', enter_editmode=True, location=(0, 0, 0))
        arm_obj = context.object
        arm_data = arm_obj.data
        arm_obj.name = rig_data.rig_name
        arm_data.name = f"{rig_data.rig_name}_Data"
        arm_data['source_rig_file'] = filepath
        arm_data['boneNames'] = rig_data.bone_names
        arm_data['boneParentIndexes'] = rig_data.bone_parents

        edit_bones = arm_data.edit_bones
        bone_index_map = {}

        # Create all bones as stubs
        for i, name in enumerate(rig_data.bone_names):
            bone = edit_bones.new(name)
            bone.head = Vector((0, 0, 0))
            bone.tail = Vector((0, 0.05, 0))
            bone_index_map[i] = bone

        #  Apply parenting + connections
        for i, parent_idx in enumerate(rig_data.bone_parents):
            child_bone = bone_index_map[i]
            if parent_idx != -1:
                parent_bone = bone_index_map[parent_idx]
                child_bone.parent = parent_bone

                is_special_bone = child_bone.name.endswith(("GRP", "IK", "JNT", "Trajectory", "reference_joint", "Hips"))
                if not rig_data.disable_connect and not is_special_bone:
                    child_bone.use_connect = False

        # Apply bind pose (T-Pose)
        global_transforms = {}
        for i in range(len(rig_data.bone_names)):
            mat_red = compute_global_transform(i, rig_data.bone_transforms, rig_data.bone_parents, global_transforms)

            global_transforms[i] = mat_red

        for i in range(len(rig_data.bone_transforms)):
            transform_data = rig_data.bone_transforms[i]
            if is_identity_transform(transform_data):
                continue  # leave Root alone 
            apply_bone_from_matrix(i, global_transforms[i], bone_index_map, rig_data.bone_parents, global_transforms)

        arm_data['T-Pose'] = True
        if bind_pose == 'A-Pose':
            # Apply A-pose if present (apply after bind pose)
            pose_matrices = build_apose_matrices(rig_data.apose_ms, rig_data.apose_ls, rig_data.bone_names, rig_data.bone_parents)
            if pose_matrices is not None:
                for i in range(len(rig_data.bone_names)): 
                    #bone = bone_index_map[i]
                    mat = pose_matrices[i]
                    apply_bone_from_matrix(i, mat, bone_index_map, rig_data.bone_parents, pose_matrices)
                arm_data['T-Pose'] = False
            else:
                print(f"No A-Pose found in {rig_data.rig_name}.json at {filepath}")

        shape = create_bone_shape()
        assign_part_groups(arm_obj, rig_data.parts)
        assign_bone_shapes(arm_obj, rig_data.disable_connect, shape)
        assign_reference_tracks(arm_obj, rig_data.track_names, rig_data.reference_tracks)
        if create_debug == True:
            create_debug_empties(arm_obj, rig_data.bone_names, rig_data.bone_parents, rig_data.bone_transforms, rig_data.apose_ls, rig_data.apose_ms, bind_pose)
        safe_mode_switch('OBJECT')
        end_time = time.time()
        duration = end_time - start_time
        print(f"Successfully imported {rig_data.rig_name} in {duration:.2f} seconds.")
        return arm_obj

def create_bone_shape():
    shape = bpy.data.objects.get("BoneCustomShape")
    if shape is None:
        current_mode = get_safe_mode()
        if current_mode != 'OBJECT':
            safe_mode_switch("OBJECT")
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.mesh.primitive_ico_sphere_add(radius=1.0, enter_editmode=False)
        shape = bpy.context.active_object
        shape.name = "BoneCustomShape"
        bpy.ops.object.shade_smooth()

    # Make sure it's linked to the view layer
    if shape.name not in bpy.context.view_layer.objects:
        bpy.context.collection.objects.link(shape)

    shape.hide_viewport = True
    shape.hide_render = True
    try:
        shape.hide_set(True)
    except RuntimeError as e:
        print(f"[create_bone_shape] Warning: Could not hide object: {e}")

    shape.select_set(False)
    return shape

def assign_bone_shapes(arm, disable_connect, shape=None):
    anim_bones = CP77animBones()
    if shape is None or not isinstance(shape, bpy.types.Object):
        shape = create_bone_shape()

    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')

    for pb in arm.pose.bones:
        name = pb.name
        pb.custom_shape = None

        #  Use shapes for these ones because it's easier for animating when they're not tiny
        if name in {"Root", "Hips,","Trajectory"}:
            pb.custom_shape = shape
            pb.custom_shape_scale_xyz = Vector((0.05, 0.05, 0.05))
            pb.use_custom_shape_bone_size = False

        elif name in {"WeaponLeft", "WeaponRight"}:
            pb.custom_shape = shape
            pb.custom_shape_scale_xyz = Vector((0.0125, 0.0125, 0.0125))
            pb.use_custom_shape_bone_size = False
            # Make sure use_connect is disabled in Edit mode
            edit_bone = arm.data.edit_bones.get(name)
            if edit_bone:
                edit_bone.use_connect = False

        else:
            use_shape = (
                disable_connect or
                name.endswith("JNT") or
                name.endswith("GRP") or
                name.endswith("IK")
            )
            if use_shape:
                pb.custom_shape = shape
                if disable_connect:
                    pb.custom_shape_scale_xyz = Vector((0.05, 0.05, 0.05))
                    pb.use_custom_shape_bone_size = True
                elif name not in anim_bones:
                    pb.custom_shape_scale_xyz = Vector((0.1, 0.1, 0.1))
                else:
                    pb.custom_shape_scale_xyz = Vector((0.05, 0.05, 0.05))

def assign_part_groups(arm_obj, parts):
    if not parts or not isinstance(parts, list):
        return  # Nothing to do

    arm_data = arm_obj.data

    # Ensure object is visible and selectable
    arm_obj.hide_set(False)
    arm_obj.hide_viewport = False
    arm_obj.hide_render = False
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj

    # Detect current mode so we can restore it later
    current_mode = get_safe_mode()
    safe_mode_switch("EDIT")
    target_layer = arm_data.edit_bones

    def collect_root_bones(tree):
        bones = []
        root_entry = tree.get("rootBone", {}) if isinstance(tree, dict) else {}
        root = root_entry.get("$value") if isinstance(root_entry, dict) else None
        if root:
            bones.append(root)
        for subtree in tree.get("subtreesToChange", []):
            bones.extend(collect_root_bones(subtree))
        return bones

    def get_descendants(bone_name, bone_map):
        descendants = []
        for b in bone_map.values():
            if b.parent and b.parent.name == bone_name:
                descendants.append(b.name)
                descendants.extend(get_descendants(b.name, bone_map))
        return descendants
    

    safe_mode_switch("EDIT")
    target_layer = arm_data.edit_bones


    for part in parts:
        if not isinstance(part, dict):
            continue

        part_name = part.get("name", {}).get("$value")
        if not isinstance(part_name, str):
            continue

        # Create or reuse collection
        if part_name not in arm_data.collections:
            collection = arm_data.collections.new(name=part_name)
        else:
            collection = arm_data.collections[part_name]

        # Handle singleBones
        for bone_entry in part.get("singleBones", []):
            bone_name = bone_entry.get("$value") if isinstance(bone_entry, dict) else None
            if isinstance(bone_name, str):
                bone = arm_data.bones.get(bone_name)
                if bone:
                    collection.assign(bone)

        # Handle treeBones
        for tree in part.get("treeBones", []):
            if not isinstance(tree, dict):
                continue
            root_bones = collect_root_bones(tree)
            for root_name in root_bones:
                if not isinstance(root_name, str):
                    continue
                root_bone = arm_data.bones.get(root_name)
                if root_bone:
                    collection.assign(root_bone)
                for child_name in get_descendants(root_name, arm_data.bones):
                    child_bone = arm_data.bones.get(child_name)
                    if child_bone:
                        collection.assign(child_bone)

        # rig data stored as custom props
        bones_with_rot_ms = [
            entry.get("$value") for entry in part.get("bonesWithRotationInModelSpace", [])
            if isinstance(entry, dict) and "$value" in entry
        ]
        mask_entries = {
            str(entry["index"]): entry["weight"]
            for entry in part.get("mask", [])
            if isinstance(entry, dict) and "index" in entry and "weight" in entry
        }
        mask_rot_ms = part.get("maskRotMS", [])

        # Set armature-level props
        arm_obj["bonesWithRotationInModelSpace"] = bones_with_rot_ms
        arm_obj["mask"] = json.dumps(mask_entries)
        arm_obj["maskRotMS"] = mask_rot_ms
        
        safe_mode_switch("POSE")
        pose_bones = arm_obj.pose.bones

        for bone_name in bones_with_rot_ms:
            if not isinstance(bone_name, str):
                continue
            pb = pose_bones.get(bone_name)
            if pb:
                pb["maskRotMS"] = True
    safe_mode_switch('OBJECT')

def assign_reference_tracks(arm_obj, track_names, reference_tracks):
    for i, track in enumerate(track_names):
        track_name = track.get("$value")
        if track_name and i < len(reference_tracks):
            arm_obj[track_name] = reference_tracks[i]