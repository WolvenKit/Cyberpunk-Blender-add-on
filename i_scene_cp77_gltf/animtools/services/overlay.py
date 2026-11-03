import bpy
import gpu
from gpu_extras.batch import batch_for_shader

_handle = None
LINE_COLOR = (1.0, 0.0, 0.0, 1.0)
LINE_WIDTH = 2.0


def draw_bone_lines(arm_obj_name):
    arm_obj = bpy.data.objects.get(arm_obj_name)
    if not arm_obj:
        return

    coords = collect_lines_world(arm_obj)
    if not coords:
        return

    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, "LINES", {"pos": coords})

    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(LINE_WIDTH)

    shader.bind()
    shader.uniform_float("color", LINE_COLOR)
    batch.draw(shader)

    gpu.state.blend_set('NONE')


def collect_lines_world(arm_obj) -> list:
    coords = []
    if not arm_obj or arm_obj.type != 'ARMATURE':
        return coords

    depsgraph = bpy.context.evaluated_depsgraph_get()
    arm_eval = arm_obj.evaluated_get(depsgraph)
    mw = arm_eval.matrix_world

    for pb in arm_eval.pose.bones:
        if pb.hide:
            continue

        if pb.parent is None:
            continue

        head = mw @ pb.head
        phead = mw @ pb.parent.head
        coords.extend((head, phead))

    return coords


def is_running() -> bool:
    return _handle is not None


def start(armature) -> bool:
    global _handle
    if _handle is not None:
        return False
    _handle = bpy.types.SpaceView3D.draw_handler_add(
        draw_bone_lines, (armature.name,), "WINDOW", "POST_VIEW"
    )
    return True


def stop() -> bool:
    global _handle
    if _handle is None:
        return False
    try:
        bpy.types.SpaceView3D.draw_handler_remove(_handle, "WINDOW")
    finally:
        _handle = None
    return True
