import bpy
import ctypes
import os

from . import io_phys, physx_ops, physx_props, physx_ui, physx_utils, viz


def get_physx_dir():
    current_dir = os.path.dirname(os.path.realpath(__file__))
    return os.path.join(current_dir, "physx")


if hasattr(os, "add_dll_directory"):
    os.add_dll_directory(get_physx_dir())


def load_physx_lib(name):
    path = os.path.join(get_physx_dir(), name)
    if not os.path.exists(path):
        return
    try:
        ctypes.CDLL(path)
    except OSError:
        print(f"Failed to load {name} from {path}")
        print("physx will not work")


load_physx_lib("PxFoundation_x64.dll")
load_physx_lib("PhysX3Common_x64.dll")
load_physx_lib("PhysX3_x64.dll")
load_physx_lib("PhysX3Cooking_x64.dll")
load_physx_lib("NvCloth_x64.dll")


classes = (
    physx_props.PhysXShapeItem,
    physx_props.PhysXActorItem,
    physx_props.PhysXObjectProperties,
    physx_props.PhysXSceneProperties,
    physx_ops.PHYSX_OT_init_scene,
    physx_ops.PHYSX_OT_validate_scene,
    physx_ops.PHYSX_OT_sim_step,
    physx_ops.PHYSX_OT_stop_sim,
    physx_ops.PHYSX_OT_apply_force,
    physx_ops.PHYSX_OT_update_gravity,
    physx_ops.PHYSX_OT_run_steps,
    physx_ops.PHYSX_OT_shape_action,
    physx_ops.PHYSX_OT_list_action,
    physx_ops.PHYSX_OT_fit_bounds_shape,
    physx_ops.PHYSX_OT_cook_mesh,
    physx_ops.PHYSX_OT_calc_dynamics,
    physx_ops.PHYSX_OT_build_scene,
    physx_ops.PHYSX_OT_reset_session,
    io_phys.PHYSX_OT_save_cooked,
    io_phys.PHYSX_OT_load_cooked,
    io_phys.PHYSX_OT_export_phys,
    io_phys.PHYSX_OT_import_phys,
    io_phys.PHYSX_OT_confirm_import,
    io_phys.PHYSX_OT_export_scene,
    io_phys.PHYSX_OT_import_scene,
    physx_ui.PHYSX_UL_actor_list,
    physx_ui.PHYSX_UL_shape_list,
    physx_ui.PhysXToolsGizmoGroup,
)


@bpy.app.handlers.persistent
def depsgraph_update_handler(scene, depsgraph):
    viz.invalidate_visualization_cache()


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Object.physx = bpy.props.PointerProperty(
        type=physx_props.PhysXObjectProperties
    )
    bpy.types.Scene.physx = bpy.props.PointerProperty(
        type=physx_props.PhysXSceneProperties
    )

    viz.register_viz()
    handlers = bpy.app.handlers.depsgraph_update_post
    if depsgraph_update_handler not in handlers:
        handlers.append(depsgraph_update_handler)


def unregister():
    viz.unregister_viz()

    handlers = bpy.app.handlers.depsgraph_update_post
    if depsgraph_update_handler in handlers:
        handlers.remove(depsgraph_update_handler)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Object.physx
    del bpy.types.Scene.physx


if __name__ == "__main__":
    register()
