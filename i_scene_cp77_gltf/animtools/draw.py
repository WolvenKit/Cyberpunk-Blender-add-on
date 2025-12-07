import bpy
import gpu
from gpu_extras.batch import batch_for_shader

_handle = None  # draw handler
_running = False

LINE_COLOR = (1.0, 0.0, 0.0, 1.0) # Red
LINE_WIDTH = 2.0


def _draw_callback(arm_obj_name):
    arm_obj = bpy.data.objects.get(arm_obj_name)
    if not arm_obj:
        return

    coords = _collect_lines_world(arm_obj)
    if not coords:
        return

    # GPU Setup
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, "LINES", {"pos": coords})

    # Draw
    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(LINE_WIDTH)
    
    shader.bind()
    shader.uniform_float("color", LINE_COLOR)
    batch.draw(shader)
    
    gpu.state.blend_set('NONE')

def _collect_lines_world(arm_obj) -> list:
    """Builds line segments: [head, parent_head, head, parent_head...]"""
    coords = []
    if not arm_obj or arm_obj.type != 'ARMATURE':
        return coords


    depsgraph = bpy.context.evaluated_depsgraph_get()
    arm_eval = arm_obj.evaluated_get(depsgraph)
    mw = arm_eval.matrix_world

    for pb in arm_eval.pose.bones:
        if pb.bone.hide:
            continue

        if pb.parent is None:
            continue

        head = mw @ pb.head
        phead = mw @ pb.parent.head
        coords.extend((head, phead))

    return coords
