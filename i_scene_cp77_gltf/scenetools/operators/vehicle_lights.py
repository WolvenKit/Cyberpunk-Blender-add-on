from __future__ import annotations

from bpy.types import Operator

from ...blender.operator_results import execute_operation
from ..application.vehicle_lights import refresh_light_channels


class CP77_OT_VehicleLightChannelsRefresh(Operator):
    bl_idname = "cp77.vehicle_light_channels_refresh"
    bl_label = "Refresh Light Channels"
    bl_description = "Re-evaluate every vehicle's light-channel volumes and rebuild which objects each light illuminates"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return execute_operation(
            self, "Light channel refresh", refresh_light_channels, context
        )


VEHICLE_LIGHT_OPERATOR_CLASSES = (CP77_OT_VehicleLightChannelsRefresh,)
