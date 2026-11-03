import bpy
import gpu
from gpu_extras.batch import batch_for_shader

from ...blender.context import tag_view3d_redraw

_handle = None
_armature_name = ""
_shader = None
_batch = None
_dirty = True
LINE_COLOR = (1.0, 0.0, 0.0, 1.0)
LINE_WIDTH = 2.0


def _mark_dirty() -> None:
    # The batch is shared by every 3D view, so each one is redrawn, not only the one being edited.
    global _dirty
    _dirty = True
    tag_view3d_redraw()


def invalidate(depsgraph) -> None:
    """Mark the cached line batch stale when the drawn armature or its data changed"""
    if not _armature_name:
        return
    armature = bpy.data.objects.get(_armature_name)
    if armature is None or depsgraph is None:
        _mark_dirty()
        return
    for update in depsgraph.updates:
        updated = getattr(update.id, "original", update.id)
        if updated == armature or updated == armature.data:
            _mark_dirty()
            return


def invalidate_frame() -> None:
    """Mark the batch stale on a frame change, which re-evaluates the pose without a depsgraph update event"""
    if _armature_name:
        _mark_dirty()


def _ensure_batch(armature):
    global _shader, _batch, _dirty
    if not _dirty and _batch is not None:
        return _shader, _batch
    coords = collect_lines_world(armature)
    if not coords:
        _batch = None
        _dirty = False
        return None, None
    if _shader is None:
        _shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    _batch = batch_for_shader(_shader, "LINES", {"pos": coords})
    _dirty = False
    return _shader, _batch


def draw_bone_lines(arm_obj_name):
    arm_obj = bpy.data.objects.get(arm_obj_name)
    if not arm_obj:
        return
    shader, batch = _ensure_batch(arm_obj)
    if shader is None or batch is None:
        return
    try:
        gpu.state.blend_set("ALPHA")
        gpu.state.line_width_set(LINE_WIDTH)
        shader.bind()
        shader.uniform_float("color", LINE_COLOR)
        batch.draw(shader)
    finally:
        gpu.state.line_width_set(1.0)
        gpu.state.depth_test_set("NONE")
        gpu.state.blend_set("NONE")


def collect_lines_world(arm_obj) -> list:
    coords = []
    if not arm_obj or arm_obj.type != "ARMATURE":
        return coords
    depsgraph = bpy.context.evaluated_depsgraph_get()
    arm_eval = arm_obj.evaluated_get(depsgraph)
    mw = arm_eval.matrix_world
    for pose_bone in arm_eval.pose.bones:
        if pose_bone.hide or pose_bone.parent is None:
            continue
        coords.extend((mw @ pose_bone.head, mw @ pose_bone.parent.head))
    return coords


def is_running() -> bool:
    return _handle is not None


def start(armature) -> bool:
    global _handle, _armature_name, _dirty
    if _handle is not None:
        return False
    _armature_name = armature.name
    _dirty = True
    _handle = bpy.types.SpaceView3D.draw_handler_add(
        draw_bone_lines, (_armature_name,), "WINDOW", "POST_VIEW"
    )
    tag_view3d_redraw()
    return True


def stop() -> bool:
    global _handle, _armature_name, _shader, _batch, _dirty
    if _handle is None:
        return False
    try:
        bpy.types.SpaceView3D.draw_handler_remove(_handle, "WINDOW")
    finally:
        _handle = None
        _armature_name = ""
        _shader = None
        _batch = None
        _dirty = True
        tag_view3d_redraw()
    return True
