from __future__ import annotations

from ...entity.domain.lights import VehicleLightGroup
from ..application.lights import vehicle_switch_property
from ..operators.vehicle_lights import CP77_OT_VehicleLightChannelsRefresh

_GROUP_LABELS = {
    VehicleLightGroup.HEAD: "Headlights",
    VehicleLightGroup.HIGH_BEAM: "High Beam",
    VehicleLightGroup.BRAKE: "Brake",
    VehicleLightGroup.LEFT_BLINKER: "Left Blinker",
    VehicleLightGroup.RIGHT_BLINKER: "Right Blinker",
    VehicleLightGroup.REVERSE: "Reverse",
    VehicleLightGroup.INTERIOR: "Interior",
    VehicleLightGroup.UTILITY: "Utility",
}


def draw_vehicles(layout, settings, groups):
    """The All Vehicle Lights switch and a switch row per vehicle light group"""
    column = layout.column(align=True)
    row = column.row(align=True)
    row.label(text="All Vehicle Lights")
    row.prop(settings, "lights_vehicles_on", toggle=True)
    row.operator(
        CP77_OT_VehicleLightChannelsRefresh.bl_idname, text="", icon="FILE_REFRESH"
    )
    for group in groups:
        row = column.row(align=True)
        row.label(text=_GROUP_LABELS[group])
        row.prop(settings, vehicle_switch_property(group), toggle=True)
