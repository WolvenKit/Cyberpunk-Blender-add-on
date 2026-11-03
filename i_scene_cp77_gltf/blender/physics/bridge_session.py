import bpy

from ...physics.runtime.bridge import initialized_bridge


class BlenderBridgeHost:
    @property
    def blender_version(self):
        return bpy.app.version

    def mark_scene_runtime_stale(self, *, initialized=None):
        for scene in getattr(bpy.data, "scenes", ()):
            physx = getattr(scene, "physx", None)
            if physx is None:
                continue
            physx.sim_running = False
            physx.scene_built = False
            physx.active_actor_count = 0
            if initialized is not None:
                physx.is_initialized = bool(initialized)
            for actor in getattr(physx, "actors", ()):
                actor.actor_handle = "0"


BRIDGE_HOST = BlenderBridgeHost()


def require_initialized_bridge(context=None):
    """The initialized bridge"""
    bridge = initialized_bridge()
    if context is not None:
        scene = getattr(context, "scene", None)
        scene_physx = getattr(scene, "physx", None) if scene is not None else None
        if scene_physx is not None:
            scene_physx.is_initialized = True
            gravity = getattr(scene_physx, "gravity", None)
            if gravity is not None and hasattr(bridge, "set_gravity"):
                bridge.set_gravity(gravity[0], gravity[1], gravity[2])
    return bridge
