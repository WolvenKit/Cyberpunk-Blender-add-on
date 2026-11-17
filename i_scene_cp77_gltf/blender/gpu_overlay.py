import functools
from contextlib import contextmanager

import gpu


@functools.cache
def uniform_color_shader():
    return gpu.shader.from_builtin("UNIFORM_COLOR")


@contextmanager
def line_drawing(width=1.0, depth_test="NONE"):
    blend = gpu.state.blend_get()
    depth = gpu.state.depth_test_get()
    previous_width = gpu.state.line_width_get()
    gpu.state.blend_set("ALPHA")
    gpu.state.depth_test_set(depth_test)
    gpu.state.line_width_set(width)
    try:
        yield
    finally:
        gpu.state.line_width_set(previous_width)
        gpu.state.depth_test_set(depth)
        gpu.state.blend_set(blend)
