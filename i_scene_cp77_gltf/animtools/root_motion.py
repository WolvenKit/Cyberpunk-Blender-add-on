from __future__ import annotations

from typing import Dict, List, Tuple

import bpy
from bpy.props import PointerProperty
from bpy.types import Operator, Panel, PoseBone
from mathutils import Vector

from .compat import get_action_fcurves
from ..cyber_props import RootMotionData
from ..main.bartmoss_functions import pose_mtx, valid_armature, world_mtx
from ..main.datashards import BoneTransformCache


def get_frame_range(action) -> Tuple[int, int]:
    f = action.frame_range
    return int(f.x), int(f.y)


def generate_frame_list(scene, start: int, end: int) -> List[int]:
    step = scene.rm_data.step
    frames = list(range(start, end + 1, step))
    if frames[-1] != end:
        frames.append(end)
    return frames


def cache_bone_transforms(context, armature, bone_name: str, frames: List[int]) -> Dict[int, BoneTransformCache]:
    bone = armature.pose.bones.get(bone_name)
    if not bone:
        raise ValueError(f"Bone '{bone_name}' not found")
    cache: Dict[int, BoneTransformCache] = {}
    for f in frames:
        context.scene.frame_set(f)
        cache[f] = BoneTransformCache(
                bone.location.copy(),
                bone.rotation_quaternion.copy(),
                bone.scale.copy(),
                bone.matrix.copy(),
                world_mtx(armature, bone).copy(),
                )
    return cache


def clear_bone_fcurves(action, armature, bone_name: str):
    """Remove all animation curves for one bone from the armature's action slot."""
    fcurves = get_action_fcurves(action, armature)
    if fcurves is None:
        return
    target = f'pose.bones["{bone_name}"]'
    for curve in [curve for curve in fcurves if curve.data_path.startswith(target)]:
        fcurves.remove(curve)


def keyframe_bone(pb: PoseBone, frame: int, include_rot: bool = True):
    pb.keyframe_insert("location", frame=frame)
    if include_rot:
        pb.keyframe_insert("rotation_quaternion", frame=frame)
    pb.keyframe_insert("scale", frame=frame)


class RootMotionOperatorBase(Operator):
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return valid_armature(context) is not None

    def validate(self, context):
        arm = valid_armature(context)
        if not arm:
            self.report({'ERROR'}, "Select an animated armature")
            return None, None, 0, 0
        data = context.scene.rm_data
        if not data.root or data.root not in arm.pose.bones:
            data.root = next(iter(arm.pose.bones)).name
        if not data.hip or data.hip not in arm.pose.bones:
            data.hip = list(arm.pose.bones)[1].name if len(arm.pose.bones) > 1 else data.root
        start, end = get_frame_range(arm.animation_data.action)
        return arm, data, start, end


class CP77HipMotionToRoot(RootMotionOperatorBase):
    """Extract root motion from hip bone animation"""
    bl_idname = "cp77.hip_to_root_motion"
    bl_label = "Extract Root Motion"

    def execute(self, context):
        arm, data, start, end = self.validate(context)
        if not arm:
            return {'CANCELLED'}

        try:
            keyframes = generate_frame_list(context.scene, start, end)
            hip_cache = cache_bone_transforms(context, arm, data.hip, keyframes)

            root = arm.pose.bones[data.root]
            hip = arm.pose.bones[data.hip]

            init_world = hip_cache[start].world_matrix.copy()
            init_vec = (hip.head - hip.tail).copy()
            init_vec.z = 0

            clear_bone_fcurves(arm.animation_data.action, arm, data.hip)

            for f in keyframes:
                context.scene.frame_set(f)
                c = hip_cache[f]
                delta = c.world_matrix.translation - init_world.translation
                if not data.do_vert:
                    delta.z = 0
                armature_delta = arm.matrix_world.to_3x3().inverted_safe() @ delta
                root.location = root.bone.matrix_local.to_3x3().inverted_safe() @ armature_delta
                if not data.no_rot:
                    vec = (hip.head - hip.tail).copy()
                    vec.z = 0
                    root.rotation_quaternion = init_vec.rotation_difference(vec)
                root.scale = Vector((1, 1, 1))
                keyframe_bone(root, f, include_rot=not data.no_rot)

            context.view_layer.update()
            self.report({'INFO'}, f"Root motion extracted ({end - start + 1} frames)")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Root motion failed: {e}")
            import traceback;
            traceback.print_exc()
            return {'CANCELLED'}


class CP77RootToHipMotion(RootMotionOperatorBase):
    """Integrate root motion back into hip bone"""
    bl_idname = "cp77.root_to_hip_motion"
    bl_label = "Integrate Root Motion"

    def execute(self, context):
        arm, data, start, end = self.validate(context)
        if not arm:
            return {'CANCELLED'}
        try:
            keyframes = generate_frame_list(context.scene, start, end)
            hip_cache = cache_bone_transforms(context, arm, data.hip, keyframes)

            clear_bone_fcurves(arm.animation_data.action, arm, data.root)
            clear_bone_fcurves(arm.animation_data.action, arm, data.hip)

            root = arm.pose.bones[data.root]
            hip = arm.pose.bones[data.hip]

            for f in keyframes:
                context.scene.frame_set(f)
                hip.matrix = pose_mtx(arm, hip, hip_cache[f].world_matrix)
                keyframe_bone(hip, f)

            for f in (start, end):
                context.scene.frame_set(f)
                root.location = (0, 0, 0)
                root.rotation_quaternion = (1, 0, 0, 0)
                root.scale = (1, 1, 1)
                keyframe_bone(root, f)

            context.view_layer.update()
            self.report({'INFO'}, f"Motion integrated ({end - start + 1} frames)")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Integration failed: {e}")
            import traceback;
            traceback.print_exc()
            return {'CANCELLED'}


class CP77RemoveRootMotion(RootMotionOperatorBase):
    """Remove root motion for in-place animation"""
    bl_idname = "cp77.remove_root_motion"
    bl_label = "Remove Root Motion"

    def execute(self, context):
        arm = valid_armature(context)
        if not arm:
            self.report({'ERROR'}, "Select an armature")
            return {'CANCELLED'}

        data = context.scene.rm_data
        if data.root not in arm.pose.bones:
            self.report({'ERROR'}, f"Root bone '{data.root}' missing")
            return {'CANCELLED'}

        start, end = get_frame_range(arm.animation_data.action)
        clear_bone_fcurves(arm.animation_data.action, arm, data.root)

        root = arm.pose.bones[data.root]
        for f in (start, end):
            context.scene.frame_set(f)
            root.location = (0, 0, 0)
            root.rotation_quaternion = (1, 0, 0, 0)
            root.scale = (1, 1, 1)
            keyframe_bone(root, f)

        context.view_layer.update()
        self.report({'INFO'}, "Root motion removed (in-place)")
        return {'FINISHED'}


classes = (
    CP77HipMotionToRoot,
    CP77RootToHipMotion,
    CP77RemoveRootMotion,
    )


def register_rm():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.rm_data = PointerProperty(type=RootMotionData)


def unregister_rm():
    if hasattr(bpy.types.Scene, "rm_data"):
        del bpy.types.Scene.rm_data
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
