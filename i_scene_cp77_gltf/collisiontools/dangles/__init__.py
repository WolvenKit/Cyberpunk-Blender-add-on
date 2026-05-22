bl_info = {
    "name": "Dangle Physics Editor",
    "author": "",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "location": "3D View > N-Panel > Dangle",
    "description": "authoring and simulation of dangle physics chains.",
    "category": "Animation",
}

if "bpy" in locals():
    import importlib
    importlib.reload(props)
    importlib.reload(draw)
    importlib.reload(io)
    importlib.reload(ops)
    importlib.reload(ui)
    from .sim import collision, constraints, core, solvers
    importlib.reload(collision)
    importlib.reload(constraints)
    importlib.reload(core)
    importlib.reload(solvers)
else:
    from . import props
    from .sim import collision, constraints, core, solvers
    from . import draw
    from . import ops
    from . import ui

def register():
    props.register()
    ui.register()
    ops.register()
    draw.register_global_handler()

def unregister():
    draw.unregister_all()
    ops.unregister()
    ui.unregister()
    props.unregister()