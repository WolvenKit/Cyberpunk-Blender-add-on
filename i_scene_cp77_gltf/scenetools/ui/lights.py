from __future__ import annotations

from ...entity.domain.lights import LightGroup
from ..application.lights import brightness_property, visible_property
from ..runtime.lights import (
    active_sector_light,
    holds_lights,
    light_index,
    light_sector,
)
from ..runtime.vehicle_lights import vehicle_light_collections
from .vehicle_lights import draw_vehicles

_GROUP_LABELS = {
    LightGroup.WORLD: "Light the world",
    LightGroup.CHARACTERS: "Characters only",
    LightGroup.FOG_GI: "Fog and GI only",
    LightGroup.REFLECTIONS: "Reflections only",
    LightGroup.DEVICES: "Device lights",
}
_SELECTED_LIGHT = (
    "light_intensity",
    "light_ev",
    "light_color",
    "light_temperature",
    "light_radius",
    "light_inner_angle",
    "light_outer_angle",
)
_SELECTED_LIGHT_AFTER_CHANNEL = (
    "light_local_shadows",
    "light_flicker_strength",
    "light_flicker_period",
)


def _draw_groups(layout, settings, index):
    """A row per group that holds lights"""
    column = layout.column(align=True)
    for group in index.groups:
        row = column.row(align=True)
        visible = visible_property(group)
        row.prop(
            settings,
            visible,
            text="",
            icon="HIDE_OFF" if getattr(settings, visible) else "HIDE_ON",
            emboss=False,
        )
        row.prop(
            settings, brightness_property(group), text=_GROUP_LABELS[group], slider=True
        )
        if group is LightGroup.DEVICES:
            row.prop(settings, "lights_devices_on", toggle=True)
    if index.switched and LightGroup.DEVICES not in index.groups:
        row = column.row(align=True)
        row.label(text=_GROUP_LABELS[LightGroup.DEVICES])
        row.prop(settings, "lights_devices_on", toggle=True)


def _draw_selected_light(layout, settings):
    column = layout.column()
    for name in _SELECTED_LIGHT:
        column.prop(settings, name)
    column.label(text="Light Channel")
    column.grid_flow(row_major=True, columns=4, even_columns=True, align=True).prop(
        settings, "light_channel", expand=True
    )
    for name in _SELECTED_LIGHT_AFTER_CHANNEL:
        column.prop(settings, name)


def draw_lights(layout, context):
    """The Lights section"""
    vehicles = vehicle_light_collections()
    if not vehicles and not holds_lights():
        return
    header, body = layout.panel("cp77_scene_lights", default_closed=True)
    header.label(text="Lights")
    if not body:
        return
    index = light_index()
    settings = context.scene.cp77_scene_tools
    if index:
        _draw_groups(body, settings, index)
    if index.groups:
        body.prop(settings, "lights_channel_filter")
    if vehicles:
        header, panel = body.panel("cp77_scene_lights_vehicles", default_closed=False)
        header.label(text="Vehicles")
        if panel:
            draw_vehicles(panel, settings, index.vehicle_groups)
    light = active_sector_light(context)
    if light is not None and light_sector(context.scene, light) is not None:
        header, panel = body.panel("cp77_scene_selected_light", default_closed=False)
        header.label(text="Selected Light")
        if panel:
            _draw_selected_light(panel, settings)
