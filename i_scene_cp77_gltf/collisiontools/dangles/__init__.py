bl_info = {
    "name": "Dangle Physics Editor",
    "author": "",
    "version": (1, 7, 3),
    "blender": (5, 0, 0),
    "location": "3D View > CP77 Modding > Physics Tools > Dangles",
    "description": "Authoring and preview for REDengine Dyng, Position Projection, Spring, Pendulum, and Drag physics.",
    "category": "Animation",
}

if "bpy" in locals():
    import importlib
    from . import draw, io, ops, props, selection_sync, ui
    importlib.reload(selection_sync)
    importlib.reload(props)
    importlib.reload(draw)
    importlib.reload(io)
    importlib.reload(ops)
    importlib.reload(ui)
    from .sim import spaces, collision, constraints, frame_time, spring, pendulum, core, drag, solvers
    importlib.reload(spaces)
    importlib.reload(collision)
    importlib.reload(constraints)
    importlib.reload(frame_time)
    importlib.reload(drag)
    importlib.reload(spring)
    importlib.reload(pendulum)
    importlib.reload(core)
    importlib.reload(solvers)
else:
    from . import selection_sync
    from . import props
    from .sim import spaces, collision, constraints, frame_time, spring, pendulum, core, drag, solvers
    from . import draw
    from . import ops
    from . import ui

def register():
    props.register()
    ui.register()
    ops.register()
    draw.register_global_handler()
    selection_sync.register()

def unregister():
    selection_sync.unregister()
    draw.unregister_all()
    ops.unregister()
    ui.unregister()
    props.unregister()