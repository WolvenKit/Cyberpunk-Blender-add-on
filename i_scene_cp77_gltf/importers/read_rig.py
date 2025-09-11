from __future__ import annotations

import os
import time
import json
from typing import Any

import bpy
import numpy as np
from mathutils import Vector, Quaternion, Matrix

from ..main.common import loc, show_message
from ..jsontool import JSONTool
from ..cyber_props import CP77animBones
from ..main.datashards import RigData
from ..main.bartmoss_functions import *


def _to_list_of_strings(seq) -> list[str]:
    if not isinstance(seq, (list, tuple)):
        return []
    out = []
    for v in seq:
        if isinstance(v, dict) and "$value" in v:
            out.append(str(v.get("$value", "")))
        elif isinstance(v, str):
            out.append(v)
    return out


def _extract_trs(trs: list[dict], n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    q = np.zeros((n, 4), dtype=np.float32)  # (x,y,z,w)
    t = np.zeros((n, 3), dtype=np.float32)
    s = np.ones((n, 3), dtype=np.float32)
    for i in range(min(n, len(trs))):
        tr = trs[i] or {}
        r = tr.get("Rotation", {})
        # store (x,y,z,w) for mathutils consistency
        q[i] = [float(r.get("i", 0.0)), float(r.get("j", 0.0)), float(r.get("k", 0.0)), float(r.get("r", 1.0))]
        tt = tr.get("Translation", {})
        t[i] = [float(tt.get("X", 0.0)), float(tt.get("Y", 0.0)), float(tt.get("Z", 0.0))]
        sc = tr.get("Scale", {})
        s[i] = [float(sc.get("X", 1.0)), float(sc.get("Y", 1.0)), float(sc.get("Z", 1.0))]
    # normalize quats
    nrm = np.linalg.norm(q, axis=-1, keepdims=True)
    nrm[nrm == 0] = 1.0
    q /= nrm
    return q, t, s


def trs_dicts_to_arrays(trs_list: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert list of TRS dicts to numpy arrays.
    Returns (q_wxyz [N,4], t [N,3], s [N,3]).
    Quaternion order is (w,x,y,z) for the math below.
    """
    n = len(trs_list)
    q = np.zeros((n, 4), dtype=np.float32)
    t = np.zeros((n, 3), dtype=np.float32)
    s = np.ones((n, 3), dtype=np.float32)
    for i, tr in enumerate(trs_list):
        if not tr:
            continue
        r = tr.get("Rotation", {})
        # (w, x, y, z)
        q[i, 0] = float(r.get("r", 1.0))
        q[i, 1] = float(r.get("i", 0.0))
        q[i, 2] = float(r.get("j", 0.0))
        q[i, 3] = float(r.get("k", 0.0))
        tt = tr.get("Translation", {})
        t[i, 0] = float(tt.get("X", 0.0))
        t[i, 1] = float(tt.get("Y", 0.0))
        t[i, 2] = float(tt.get("Z", 0.0))
        sc = tr.get("Scale", {})
        s[i, 0] = float(sc.get("X", 1.0))
        s[i, 1] = float(sc.get("Y", 1.0))
        s[i, 2] = float(sc.get("Z", 1.0))
    # normalize quats
    nrm = np.linalg.norm(q, axis=-1, keepdims=True)
    nrm[nrm == 0] = 1.0
    q /= nrm
    return q, t, s


def trs_to_matrices_np(q_wxyz: np.ndarray, t: np.ndarray, s: np.ndarray) -> np.ndarray:
    """Batch convert TRS numpy arrays to homogenous 4x4 matrices.
    q_wxyz: [N,4] with (w,x,y,z)
    t: [N,3]
    s: [N,3]
    Returns: mats [N,4,4] row-major
    """
    w, x, y, z = q_wxyz[:, 0], q_wxyz[:, 1], q_wxyz[:, 2], q_wxyz[:, 3]
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z

    r00 = 1 - 2 * (yy + zz)
    r01 = 2 * (xy - wz)
    r02 = 2 * (xz + wy)
    r10 = 2 * (xy + wz)
    r11 = 1 - 2 * (xx + zz)
    r12 = 2 * (yz - wx)
    r20 = 2 * (xz - wy)
    r21 = 2 * (yz + wx)
    r22 = 1 - 2 * (xx + yy)

    # scale axes
    r00 *= s[:, 0]; r10 *= s[:, 0]; r20 *= s[:, 0]
    r01 *= s[:, 1]; r11 *= s[:, 1]; r21 *= s[:, 1]
    r02 *= s[:, 2]; r12 *= s[:, 2]; r22 *= s[:, 2]

    n = q_wxyz.shape[0]
    mats = np.zeros((n, 4, 4), dtype=np.float32)
    mats[:, 0, 0] = r00; mats[:, 0, 1] = r01; mats[:, 0, 2] = r02; mats[:, 0, 3] = t[:, 0]
    mats[:, 1, 0] = r10; mats[:, 1, 1] = r11; mats[:, 1, 2] = r12; mats[:, 1, 3] = t[:, 1]
    mats[:, 2, 0] = r20; mats[:, 2, 1] = r21; mats[:, 2, 2] = r22; mats[:, 2, 3] = t[:, 2]
    mats[:, 3, 3] = 1.0
    return mats


def read_rig(filepath: str) -> RigData:
    """Read .rig.json and return RigData (numpy-backed)."""
    data = JSONTool.jsonload(filepath)
    base_name = os.path.basename(filepath)
    rig_name = base_name.replace(".rig.json", "")

    root = data.get("Data", {}).get("RootChunk", {})
    bone_names = _to_list_of_strings(root.get("boneNames", []))
    parent_indices = np.asarray(root.get("boneParentIndexes", []), dtype=np.int16).reshape(-1)
    track_names = _to_list_of_strings(root.get("trackNames", []))

    trs = root.get("boneTransforms", [])
    q, t, s = _extract_trs(trs, len(bone_names))

    return RigData(
        num_bones=len(bone_names),
        parent_indices=parent_indices,
        bone_names=bone_names,
        track_names=track_names,
        ls_q=q,
        ls_t=t,
        ls_s=s,
        rig_name=rig_name,
        disable_connect=rig_name.startswith("v_"),
        apose_ms=root.get("aPoseMS", []),
        apose_ls=root.get("aPoseLS", []),
        bone_transforms=trs,
        parts=root.get("parts", []),
        rig_extra_tracks=root.get("rigExtraTracks", []),
        reference_tracks=root.get("referenceTracks", []),
        cooking_platform=root.get("cookingPlatform", ""),
        distance_category_to_lod_map=root.get("distanceCategoryToLodMap", []),
        ik_setups=root.get("ikSetups", []),
        level_of_detail_start_indices=root.get("levelOfDetailStartIndices", []),
        ragdoll_desc=root.get("ragdollDesc", []),
        ragdoll_names=root.get("ragdollNames", []),
    )


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

def create_aposels_empties(obj, bone_names, parent_indices, bone_transforms, collection_name="aPoseLS_Debug"):
    collection = bpy.data.collections.get(collection_name) or bpy.data.collections.new(collection_name)
    if collection.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(collection)

    empties = {}
    for i, name in enumerate(bone_names):
        empty = bpy.data.objects.new(name=f"{collection_name}_{name}", object_data=None)
        empty.empty_display_size = 0.05
        empty.empty_display_type = 'ARROWS'
        empty.rotation_mode = 'QUATERNION'
        collection.objects.link(empty)
        empties[i] = empty

    parents = np.asarray(parent_indices, dtype=np.int32)
    for i, p in enumerate(parents):
        if p != -1 and p in empties:
            child = empties[i]
            parent = empties[p]
            child.parent = parent
            child.matrix_parent_inverse = parent.matrix_world.inverted()

    for i, trs in enumerate(bone_transforms):
        t = trs["Translation"]
        r = trs["Rotation"]
        s = trs["Scale"]
        empty = empties[i]
        bone_name = bone_names[i]
        empty.location = (t["X"], t["Y"], t["Z"])
        empty.rotation_quaternion = Quaternion((r["r"], r["i"], r["j"], r["k"]))
        empty.scale = (s["X"], s["Y"], s["Z"])
        c = empty.constraints.new(type='COPY_TRANSFORMS')
        c.name = f"CopyTransforms_{bone_name}"
        c.target = obj
        c.subtarget = bone_name
        c.owner_space = 'WORLD'
        c.target_space = 'WORLD'
        empty['Owner'] = f"{obj.name} {bone_name}"
        empty['Space: '] = f"{collection_name}"
        empty["raw_translation"] = [t["X"], t["Y"], t["Z"]]
        empty["raw_rotation"] = [r["r"], r["i"], r["j"], r["k"]]
        empty["raw_scale"] = [s["X"], s["Y"], s["Z"]]

def create_aposems_empties(obj, bone_names, parent_indices, bone_transforms, collection_name="aPoseMS_Debug"):
    collection = bpy.data.collections.get(collection_name) or bpy.data.collections.new(collection_name)
    if collection.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(collection)

    empties = {}
    for i, name in enumerate(bone_names):
        empty = bpy.data.objects.new(name=f"aPoseMS_{name}_Debug", object_data=None)
        empty.empty_display_size = 0.05
        empty.empty_display_type = 'ARROWS'
        empty.rotation_mode = 'QUATERNION'
        collection.objects.link(empty)
        empties[i] = empty

    for i, tr in enumerate(bone_transforms):
        t = tr["Translation"]
        r = tr["Rotation"]
        s = trs["Scale"]
        empty = empties[i]
        bone_name = bone_names[i]
        empty.location = (t["X"], t["Y"], t["Z"])
        empty.rotation_quaternion = Quaternion((r["r"], r["i"], r["j"], r["k"]))
        empty.scale = (s["X"], s["Y"], s["Z"])
        c = empty.constraints.new(type='COPY_TRANSFORMS')
        c.name = f"CopyTransforms_{bone_name}"
        c.target = obj
        c.subtarget = bone_name
        c.owner_space = 'WORLD'
        c.target_space = 'WORLD'
        empty['Owner'] = f"{obj.name} {bone_name}"
        empty['Space: '] = f"{collection_name}"
        empty["raw_translation"] = [t["X"], t["Y"], t["Z"]]
        empty["raw_rotation"] = [r["r"], r["i"], r["j"], r["k"]]
        empty["raw_scale"] = [s["X"], s["Y"], s["Z"]]

def scale_matrix(s: Vector | tuple | list) -> Matrix:
    m = Matrix.Identity(4)
    m[0][0], m[1][1], m[2][2] = s
    return m


def compute_global_transform(index: int, transforms: list[dict], parents: np.ndarray, cache: dict[int, Matrix]) -> Matrix:
    if index in cache:
        return cache[index]

    t3 = transforms[index]["Translation"]
    r4 = transforms[index]["Rotation"]
    s3 = transforms[index].get("Scale", {"X": 1.0, "Y": 1.0, "Z": 1.0})

    T = Vector((t3["X"], t3["Y"], t3["Z"]))
    Q = Quaternion((r4["r"], r4["i"], r4["j"], r4["k"]))
    S = Vector((s3["X"], s3["Y"], s3["Z"]))

    local_mat = Matrix.Translation(T) @ Q.to_matrix().to_4x4() @ scale_matrix(S)
    p = int(parents[index]) if index < len(parents) else -1
    if p == -1:
        cache[index] = local_mat
    else:
        parent_mat = compute_global_transform(p, transforms, parents, cache)
        cache[index] = parent_mat @ local_mat
    return cache[index]


def build_apose_matrices(apose_ms, apose_ls, bone_names: list[str], parent_indices: np.ndarray):
    if apose_ms:
        # Fast path: model-space TRS can be converted in batch with numpy
        q_wxyz, t, s = trs_dicts_to_arrays(apose_ms)
        mats_np = trs_to_matrices_np(q_wxyz, t, s)
        return [Matrix(m) for m in mats_np]
    elif apose_ls:
        # Local-space: need hierarchy; keep existing cached recursion
        cache: dict[int, Matrix] = {}
        for i in range(len(bone_names)):
            compute_global_transform(i, apose_ls, parent_indices, cache)
        return [cache[i] for i in range(len(bone_names))]
    return None


def is_identity_transform(transform: dict) -> bool:
    t = transform["Translation"]; r = transform["Rotation"]; s = transform["Scale"]
    return (
        abs(t["X"]) < 1e-6 and abs(t["Y"]) < 1e-6 and abs(t["Z"]) < 1e-6 and
        abs(r["r"]) < 1e-6 and abs(r["i"]) < 1e-6 and abs(r["j"]) < 1e-6 and abs(r["k"] - 1) < 1e-6 and
        abs(s["X"] - 1) < 1e-6 and abs(s["Y"] - 1) < 1e-6 and abs(s["Z"] - 1) < 1e-6
    )


def apply_bone_from_matrix(bone_index: int, mat: Matrix, edit_bones: dict[int, bpy.types.EditBone], parent_indices: np.ndarray, global_transforms: dict[int, Matrix], default_length: float = 0.01):
    safe_mode_switch('EDIT')
    head = mat.to_translation()

    pi = np.asarray(parent_indices, dtype=np.int32)
    child_indices = np.where(pi == bone_index)[0].tolist()

    if child_indices:
        avg = Vector()
        for ci in child_indices:
            avg += global_transforms[ci].to_translation()
        avg /= len(child_indices)
        direction = avg - head
        if direction.length < 1e-6:
            y_axis = (mat.to_3x3() @ Vector((0, 1, 0))).normalized()
            direction = y_axis * default_length
        else:
            direction = direction.normalized() * max(direction.length, default_length)
        tail = head + direction
    else:
        y_axis = (mat.to_3x3() @ Vector((0, 1, 0))).normalized()
        tail = head + y_axis * default_length

    if (tail - head).length < 1e-6:
        tail = head + Vector((0, default_length, 0))

    eb = edit_bones[bone_index]
    eb.head = head
    eb.tail = tail
    x_axis = mat.to_3x3() @ Vector((1, 0, 0))
    eb.align_roll(x_axis)


def create_armature_from_data(filepath: str, bind_pose: str, create_debug: bool = False):
    start_time = time.time()

    rig_data = read_rig(filepath)
    if not rig_data:
        show_message(f"Failed to load rig data from {filepath} ERROR")
        return None

    print(f'Beginning Import of: {rig_data.rig_name} from: {filepath} Bind Pose: {bind_pose}')
    context = bpy.context
    safe_mode_switch('OBJECT')
    bpy.ops.object.add(type='ARMATURE', enter_editmode=True, location=(0, 0, 0))
    arm_obj = context.object
    arm_data = arm_obj.data
    arm_obj.name = rig_data.rig_name
    arm_data.name = f"{rig_data.rig_name}_Data"
    arm_data['source_rig_file'] = filepath
    arm_data['boneNames'] = rig_data.bone_names
    arm_data['boneParentIndexes'] = rig_data.parent_indices.tolist()
    arm_data['rig_extra_tracks'] = rig_data.rig_extra_tracks

    edit_bones = arm_data.edit_bones
    bone_index_map: dict[int, bpy.types.EditBone] = {}

    for i, name in enumerate(rig_data.bone_names):
        b = edit_bones.new(name)
        b.head = Vector((0, 0, 0))
        b.tail = Vector((0, 0.05, 0))
        bone_index_map[i] = b

    for i, parent_idx in enumerate(rig_data.parent_indices.tolist()):
        child_bone = bone_index_map[i]
        if parent_idx != -1:
            parent_bone = bone_index_map[parent_idx]
            child_bone.parent = parent_bone
            special = child_bone.name.endswith(("GRP", "IK", "JNT", "Trajectory", "reference_joint", "Hips"))
            if not rig_data.disable_connect and not special:
                child_bone.use_connect = False

    global_transforms: dict[int, Matrix] = {}
    for i in range(len(rig_data.bone_names)):
        mat = compute_global_transform(i, rig_data.bone_transforms, rig_data.parent_indices, global_transforms)
        global_transforms[i] = mat

    for i, tr in enumerate(rig_data.bone_transforms):
        if is_identity_transform(tr):
            continue
        apply_bone_from_matrix(i, global_transforms[i], bone_index_map, rig_data.parent_indices, global_transforms)

    arm_data['T-Pose'] = True

    if bind_pose == 'A-Pose':
        if not rig_data.apose_ls and not rig_data.apose_ms:
            print(f"No A-Pose found in {rig_data.rig_name}.json at {filepath}, falling back to T-Pose")
        mats = build_apose_matrices(rig_data.apose_ms, rig_data.apose_ls, rig_data.bone_names, rig_data.parent_indices)
        if mats is not None:
            for i, m in enumerate(mats):
                apply_bone_from_matrix(i, m, bone_index_map, rig_data.parent_indices, global_transforms)
            arm_data['T-Pose'] = False
        else:
            print(f"No A-Pose found in {rig_data.rig_name}.json at {filepath}, falling back to T-Pose")

    shape = create_bone_shape()
    assign_part_groups(arm_obj, rig_data.parts)
    assign_bone_shapes(arm_obj, rig_data.disable_connect, shape)
    assign_reference_tracks(arm_obj, rig_data.track_names, rig_data.reference_tracks)

    if create_debug:
        create_debug_empties(arm_obj, rig_data.bone_names, rig_data.parent_indices, rig_data.bone_transforms, rig_data.apose_ls, rig_data.apose_ms, bind_pose)

    safe_mode_switch('OBJECT')
    print(f"Successfully imported {rig_data.rig_name} in {time.time() - start_time:.2f} seconds.")
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

        if name in {"Root", "Hips,","Trajectory"}:
            pb.custom_shape = shape
            pb.custom_shape_scale_xyz = Vector((0.075, 0.075, 0.075))
            pb.use_custom_shape_bone_size = False
        elif name in {"WeaponLeft", "WeaponRight"}:
            pb.custom_shape = shape
            pb.custom_shape_scale_xyz = Vector((0.0125, 0.0125, 0.0125))
            pb.use_custom_shape_bone_size = False
            edit_bone = arm.data.edit_bones.get(name)
            if edit_bone:
                edit_bone.use_connect = False
        else:
            use_shape = (disable_connect or name.endswith("JNT") or name.endswith("GRP") or name.endswith("IK"))
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
        return

    arm_data = arm_obj.data

    arm_obj.hide_set(False)
    arm_obj.hide_viewport = False
    arm_obj.hide_render = False
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj

    current_mode = get_safe_mode()
    safe_mode_switch("EDIT")

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

    target_layer = arm_data.edit_bones

    for part in parts:
        if not isinstance(part, dict):
            continue

        part_name = part.get("name", {}).get("$value")
        if not isinstance(part_name, str):
            continue

        collection = arm_data.collections.get(part_name) or arm_data.collections.new(name=part_name)

        for bone_entry in part.get("singleBones", []):
            bone_name = bone_entry.get("$value") if isinstance(bone_entry, dict) else None
            if isinstance(bone_name, str):
                bone = arm_data.bones.get(bone_name)
                if bone:
                    collection.assign(bone)

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

        bones_with_rot_ms = [entry.get("$value") for entry in part.get("bonesWithRotationInModelSpace", []) if isinstance(entry, dict) and "$value" in entry]
        mask_entries = {str(entry["index"]): entry["weight"] for entry in part.get("mask", []) if isinstance(entry, dict) and "index" in entry and "weight" in entry}
        mask_rot_ms = part.get("maskRotMS", [])

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
    if not track_names:
        return
    names: list[str] = []
    for t in track_names:
        if isinstance(t, str):
            names.append(t)
        elif isinstance(t, dict) and "$value" in t:
            names.append(str(t["$value"]))
    for i, name in enumerate(names):
        if i < len(reference_tracks):
            arm_obj[name] = reference_tracks[i]
