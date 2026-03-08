"""
cp77_facial/pose_preview.py
============================
Stage 3 — Single-pose preview for the CP77 facial rig.

Applies one main pose at full weight (1.0) directly to Blender pose bones,
including all corrective poses that are exclusively driven by this pose.
Supports all three parts: face, eyes, tongue.

Architecture
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import bpy
from bpy.props import EnumProperty, IntProperty
from bpy.types import Operator
from mathutils import Quaternion, Vector

from . import rig_binding


# Module-level snapshot store
# { armature_name: { bone_name: (Quaternion, Vector, str) } }
_snapshots: Dict[str, Dict[str, Tuple]] = {}


# Numpy helpers (no Blender API)

def _xyzw_to_blender_quat(xyzw: np.ndarray) -> Quaternion:
    """Convert numpy [x, y, z, w] to Blender Quaternion(w, x, y, z)."""
    return Quaternion((float(xyzw[3]), float(xyzw[0]), float(xyzw[1]), float(xyzw[2])))


def _build_bone_deltas(
    pose_arrays,
    ib_index: int,
) -> Dict[int, Tuple[Quaternion, Vector]]:
    """
    Extract (delta_quat, delta_trans) for every bone touched by inbetween
    pose `ib_index`.

    Returns {bone_idx: (Quaternion, Vector)}.
    """
    start = int(pose_arrays.row_ptr[ib_index])
    end   = int(pose_arrays.row_ptr[ib_index + 1])

    result: Dict[int, Tuple[Quaternion, Vector]] = {}
    for k in range(start, end):
        bone_idx = int(pose_arrays.pose_bones[k])
        dq = _xyzw_to_blender_quat(pose_arrays.pose_quats[k])
        dt = Vector((
            float(pose_arrays.pose_trans[k, 0]),
            float(pose_arrays.pose_trans[k, 1]),
            float(pose_arrays.pose_trans[k, 2]),
        ))
        result[bone_idx] = (dq, dt)
    return result


def _apply_corrective_deltas(
    pose_arrays,
    corrective_index: int,
    deltas: Dict[int, Tuple[Quaternion, Vector]],
) -> None:
    """
    Additively stack transforms from corrective pose `corrective_index` onto
    the deltas dict in-place (rotation: multiply, translation: add).
    """
    start = int(pose_arrays.row_ptr[corrective_index])
    end   = int(pose_arrays.row_ptr[corrective_index + 1])

    for k in range(start, end):
        bone_idx = int(pose_arrays.pose_bones[k])
        dq = _xyzw_to_blender_quat(pose_arrays.pose_quats[k])
        dt = Vector((
            float(pose_arrays.pose_trans[k, 0]),
            float(pose_arrays.pose_trans[k, 1]),
            float(pose_arrays.pose_trans[k, 2]),
        ))
        if bone_idx in deltas:
            eq, et = deltas[bone_idx]
            deltas[bone_idx] = (eq @ dq, et + dt)
        else:
            deltas[bone_idx] = (dq, dt)


def _find_gce_solo_correctives(part, target_track: int) -> List[int]:
    """
    Return indices of GCE correctives whose ONLY dependency is target_track.
    """
    results = []
    for c in range(part.num_correctives):
        s = int(part.gcorr_row_ptr[c])
        e = int(part.gcorr_row_ptr[c + 1])
        if (e - s) == 1 and int(part.gcorr_tracks[s]) == target_track:
            results.append(c)
    return results


def _find_ice_correctives(part, target_ib: int) -> List[int]:
    """
    Return indices of ICE correctives whose track ref equals target_ib
    (the inbetween-expanded pose index at threshold 1.0).
    """
    results = []
    for c in range(part.num_correctives):
        s = int(part.icorr_row_ptr[c])
        e = int(part.icorr_row_ptr[c + 1])
        for i in range(s, e):
            if int(part.icorr_tracks[i]) == target_ib:
                results.append(c)
                break
    return results


# Snapshot helpers (Blender API)

def _snapshot_pose(
    obj: bpy.types.Object,
    bone_names: List[str],
) -> Dict[str, Tuple]:
    """Save rotation_quaternion, location, and rotation_mode for each bone."""
    snapshot = {}
    pb = obj.pose.bones
    for name in bone_names:
        if name in pb:
            pbone = pb[name]
            prev_mode = pbone.rotation_mode
            pbone.rotation_mode = "QUATERNION"
            snapshot[name] = (
                pbone.rotation_quaternion.copy(),
                pbone.location.copy(),
                prev_mode,
            )
    return snapshot


def _restore_pose(obj: bpy.types.Object, snapshot: Dict[str, Tuple]) -> None:
    """Restore pose bone state from a _snapshot_pose result."""
    pb = obj.pose.bones
    for name, (rot, loc, mode) in snapshot.items():
        if name in pb:
            pbone = pb[name]
            pbone.rotation_mode = "QUATERNION"
            pbone.rotation_quaternion = rot
            pbone.location = loc
            pbone.rotation_mode = mode


def _reset_bones_to_rest(obj: bpy.types.Object, bone_names: List[str]) -> None:
    """Reset named pose bones to rest (identity rotation, zero location)."""
    pb       = obj.pose.bones
    identity = Quaternion()
    zero     = Vector()
    for name in bone_names:
        if name in pb:
            pbone = pb[name]
            pbone.rotation_mode = "QUATERNION"
            pbone.rotation_quaternion = identity
            pbone.location = zero


# Core preview / clear

def preview_apply_pose(
    obj: bpy.types.Object,
    cache: rig_binding.BindingCache,
    part_name: str,
    pose_index: int,
) -> Tuple[bool, str]:
    """
    Apply main pose `pose_index` of `part_name` at full weight (1.0),
    including all solo correctives, to the armature's pose bones.

    Saves the current pose before applying so preview_clear() can restore it.

    Returns (success, message).
    """
    # Resolve part
    part = _get_part(cache.setup, part_name)
    if part is None:
        return False, f"Unknown part '{part_name}'"

    if pose_index < 0 or pose_index >= part.num_main_poses:
        return False, (
            f"Pose index {pose_index} out of range "
            f"[0, {part.num_main_poses - 1}] for part '{part_name}'"
        )

    # Save snapshot (only if not already previewing — preserves original pose)
    if obj.name not in _snapshots:
        _snapshots[obj.name] = _snapshot_pose(obj, cache.used_bone_names)

    # Reset only the bones this part touches
    part_bone_names = _part_bone_names(part, cache)
    _reset_bones_to_rest(obj, part_bone_names)

    # Compute target inbetween index (last inbetween = threshold 1.0)
    target_track = int(part.main_tracks[pose_index])
    target_ib    = int(part.ib_row_ptr[pose_index + 1]) - 1

    # Build delta buffer from the main pose only (no correctives in preview)
    deltas = _build_bone_deltas(part.main_poses, target_ib)

    # Write back to pose bones
    pb          = obj.pose.bones
    bone_names  = cache.rig.bone_names
    written     = 0
    skipped     = 0

    for bone_idx, (dq, dt) in deltas.items():
        if bone_idx >= cache.rig.num_bones:
            skipped += 1
            continue
        name = str(bone_names[bone_idx])
        if name not in pb:
            skipped += 1
            continue
        pbone = pb[name]
        pbone.rotation_mode = "QUATERNION"
        # From rest (identity @ delta = delta), so we assign directly
        pbone.rotation_quaternion = dq
        pbone.location = dt
        written += 1

    # Update scene state
    scene_props = getattr(bpy.context.scene, "cp77_facial", None)
    if scene_props is not None:
        scene_props.preview_active     = True
        scene_props.preview_part       = part_name
        scene_props.preview_pose_index = pose_index

    _tag_redraw()

    track_name = str(cache.rig.track_names[target_track])
    msg = (
        f"Preview: {part_name}[{pose_index}] '{track_name}' — "
        f"{written} bone(s)"
        + (f", {skipped} bone(s) skipped" if skipped else "")
    )
    return True, msg


def preview_clear(
    obj: bpy.types.Object,
    cache: rig_binding.BindingCache,
) -> Tuple[bool, str]:
    """
    Restore the pose saved before the last preview_apply_pose call.
    Falls back to resetting all used bones to rest if no snapshot exists.
    """
    snap = _snapshots.pop(obj.name, None)

    if snap is not None:
        _restore_pose(obj, snap)
        msg = "Preview cleared — pose restored"
    else:
        _reset_bones_to_rest(obj, cache.used_bone_names)
        msg = "Preview cleared — bones reset to rest (no snapshot)"

    scene_props = getattr(bpy.context.scene, "cp77_facial", None)
    if scene_props is not None:
        scene_props.preview_active = False

    _tag_redraw()
    return True, msg


# Internal helpers

def _get_part(setup, part_name: str):
    return {"face": setup.face, "eyes": setup.eyes, "tongue": setup.tongue}.get(part_name)


def _part_bone_names(part, cache: rig_binding.BindingCache) -> List[str]:
    """Collect names of all bones referenced by this part's pose arrays."""
    indices: set = set()
    for arr in (part.main_poses, part.corrective_poses):
        if arr.num_poses > 0:
            indices.update(arr.pose_bones.tolist())
    bone_names = cache.rig.bone_names
    return [str(bone_names[i]) for i in sorted(indices) if i < cache.rig.num_bones]


def _tag_redraw() -> None:
    """Request a viewport redraw on all VIEW_3D areas."""
    if bpy.context.screen is None:
        return
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            area.tag_redraw()


def get_pose_track_name(cache: rig_binding.BindingCache, part_name: str, pose_index: int) -> str:
    """Return the rig track name for a given part + pose index, or empty string."""
    part = _get_part(cache.setup, part_name)
    if part is None or pose_index < 0 or pose_index >= part.num_main_poses:
        return ""
    track_idx = int(part.main_tracks[pose_index])
    if track_idx < cache.rig.num_tracks:
        return str(cache.rig.track_names[track_idx])
    return ""


def get_corrective_count(
    cache: rig_binding.BindingCache,
    part_name: str,
    pose_index: int,
) -> Tuple[int, int]:
    """Return (num_gce_solo, num_ice_solo) without running the preview."""
    part = _get_part(cache.setup, part_name)
    if part is None or pose_index < 0 or pose_index >= part.num_main_poses:
        return 0, 0
    target_track = int(part.main_tracks[pose_index])
    target_ib    = int(part.ib_row_ptr[pose_index + 1]) - 1
    return (
        len(_find_gce_solo_correctives(part, target_track)),
        len(_find_ice_correctives(part, target_ib)),
    )


# Operators

class FACIAL_OT_PreviewPose(Operator):
    """Preview a single main pose at full weight on the active armature"""
    bl_idname  = "cp77_facial.preview_pose"
    bl_label   = "Preview Pose"
    bl_options = {"REGISTER", "UNDO"}

    part: EnumProperty(
        name  = "Part",
        items = [
            ("face",   "Face",   "Face main poses (121)"),
            ("eyes",   "Eyes",   "Eye main poses (12)"),
            ("tongue", "Tongue", "Tongue main poses (18)"),
        ],
        default = "face",
    )  # type: ignore

    pose_index: IntProperty(
        name    = "Pose Index",
        default = 0,
        min     = 0,
        max     = 255,
    )  # type: ignore

    @classmethod
    def poll(cls, context):
        obj = context.object
        return (
            obj is not None
            and obj.type == "ARMATURE"
            and rig_binding.is_bound(obj)
            and rig_binding.get_cache(obj.name) is not None
        )

    def invoke(self, context, event):
        scene_props = getattr(context.scene, "cp77_facial", None)
        if scene_props is not None:
            self.part       = scene_props.preview_part
            self.pose_index = scene_props.preview_pose_index

        cache = rig_binding.get_cache(context.object.name)
        if cache is not None:
            part = _get_part(cache.setup, self.part)
            if part is not None:
                self.pose_index = max(0, min(self.pose_index, part.num_main_poses - 1))

        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        cache = rig_binding.get_cache(context.object.name)

        layout.prop(self, "part")
        layout.prop(self, "pose_index")

        if cache is not None:
            track_name = get_pose_track_name(cache, self.part, self.pose_index)
            if track_name:
                col = layout.column(align=True)
                col.enabled = False
                col.label(text=f"Track:  {track_name}", icon="ACTION")

        # Solver conflict warning
        scene_props = getattr(context.scene, "cp77_facial", None)
        if scene_props is not None and getattr(scene_props, "solver_active", False):
            layout.separator()
            layout.label(
                text="Solver active — preview will be overwritten on next frame",
                icon="ERROR",
            )

    def execute(self, context):
        obj   = context.object
        cache = rig_binding.get_cache(obj.name)
        if cache is None:
            self.report({"ERROR"}, "No binding cache — please rebind first")
            return {"CANCELLED"}

        ok, msg = preview_apply_pose(obj, cache, self.part, self.pose_index)
        self.report({"INFO"} if ok else {"ERROR"}, msg)
        return {"FINISHED"} if ok else {"CANCELLED"}



class FACIAL_OT_ClearPreview(Operator):
    """Restore the pose that was active before the last preview"""
    bl_idname  = "cp77_facial.clear_preview"
    bl_label   = "Clear Preview"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        if obj is None or obj.type != "ARMATURE" or not rig_binding.is_bound(obj):
            return False
        scene_props = getattr(context.scene, "cp77_facial", None)
        if scene_props is not None and scene_props.preview_active:
            return True
        return obj.name in _snapshots

    def execute(self, context):
        obj   = context.object
        cache = rig_binding.get_cache(obj.name)
        if cache is None:
            self.report({"ERROR"}, "No binding cache — please rebind first")
            return {"CANCELLED"}

        ok, msg = preview_clear(obj, cache)
        self.report({"INFO"}, msg)
        return {"FINISHED"} if ok else {"CANCELLED"}



class FACIAL_OT_BrowsePoses(Operator):
    """Step through main poses one at a time for the selected part"""
    bl_idname  = "cp77_facial.browse_poses"
    bl_label   = "Browse Poses"
    bl_options = {"REGISTER", "UNDO"}

    direction: IntProperty(name="Direction", default=1, min=-1, max=1)  # type: ignore

    @classmethod
    def poll(cls, context):
        obj = context.object
        return (
            obj is not None
            and obj.type == "ARMATURE"
            and rig_binding.is_bound(obj)
            and rig_binding.get_cache(obj.name) is not None
        )

    def execute(self, context):
        obj         = context.object
        cache       = rig_binding.get_cache(obj.name)
        scene_props = getattr(context.scene, "cp77_facial", None)

        if cache is None or scene_props is None:
            return {"CANCELLED"}

        part = _get_part(cache.setup, scene_props.preview_part)
        if part is None:
            return {"CANCELLED"}

        new_index = (scene_props.preview_pose_index + self.direction) % part.num_main_poses
        scene_props.preview_pose_index = new_index

        ok, msg = preview_apply_pose(obj, cache, scene_props.preview_part, new_index)
        self.report({"INFO"} if ok else {"ERROR"}, msg)
        return {"FINISHED"} if ok else {"CANCELLED"}


# Registration

_CLASSES = (
    FACIAL_OT_PreviewPose,
    FACIAL_OT_ClearPreview,
    FACIAL_OT_BrowsePoses,
)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    _snapshots.clear()
    for cls in reversed(_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
