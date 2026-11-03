import bpy

from ...blender.workspace import is_animation_workspace
from ...core.addon_identity import get_addon_preferences
from ...physics.model.bridge import PhysXCapabilityState
from ...physics.runtime.bridge import capability_status
from .actors import draw_actors
from .dangles import draw_dangles
from .simulation import draw_simulation
from .vehicle import draw_vehicle
from .world import draw_world


class CP77_PT_PhysicsTools(bpy.types.Panel):
    bl_label = "Physics Tools"
    bl_idname = "CP77_PT_physics"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CP77 Modding"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        if is_animation_workspace(context):
            return False
        preferences = get_addon_preferences(context)
        if not preferences.context_only:
            return True

        physics = getattr(context.scene, "physx", None)
        vehicle = getattr(context.scene, "physx_vehicle", None)
        if physics and physics.ui_tab == "VEHICLE":
            if vehicle and vehicle.enabled:
                return True
            active = context.active_object
            if active is not None and active.type == "ARMATURE":
                return True

        active = context.active_object
        return active is not None and active.type in {"MESH", "ARMATURE"}

    def draw(self, context):
        layout = self.layout
        preferences = get_addon_preferences(context)
        if not preferences.show_modtools or not preferences.show_physicstools:
            return

        physics = context.scene.physx
        row = layout.row(align=True)
        row.prop(physics, "viz_enabled", text="Draw Colliders")
        row.prop(physics, "ui_tab", expand=True)

        if physics.ui_tab == "DANGLES":
            draw_dangles(layout, context, physics)
            return

        capability = capability_status()
        if capability.state is PhysXCapabilityState.UNAVAILABLE:
            box = layout.box()
            box.label(text="PhysX bridge unavailable", icon="ERROR")
            box.label(text=capability.reason)
            return

        if physics.ui_tab == "VEHICLE":
            draw_vehicle(layout, context)
            return
        if not physics.is_initialized:
            layout.operator("physx.init_scene", icon="PLAY", text="Initialize PhysX")
            return

        if physics.ui_tab == "WORLD":
            draw_world(layout, physics)
        elif physics.ui_tab == "ACTORS":
            draw_actors(layout, physics)
        elif physics.ui_tab == "SIM":
            draw_simulation(layout, physics)
