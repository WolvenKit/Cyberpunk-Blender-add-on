from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
)
from bpy.types import PropertyGroup

from ...bartmoss.celestial import DAY_HOURS, wrap_hour
from ...entity.domain.lights import LightGroup, VehicleLightGroup
from ...importers.common.light_channel_semantics import (
    LC_AUTOMATED,
    LC_CHANNEL1,
    LC_CHANNEL_WORLD,
    LC_CHARACTER,
    LC_PLAYER,
    LC_SUPPORTED_MASK,
    decode_light_channel,
    light_channel_text,
)
from ..application.execution import refresh_environment
from ..application.lights import (
    brighten_group,
    edit_selected_light,
    selected_light_setting,
    show_channel,
    show_group,
    switch_devices,
    switch_vehicles,
    vehicle_switch_property,
)
from ..application.options import SEASON_ITEMS, WEATHER_ITEMS, RefreshScope
from ..runtime.ownership import scene_has_owned_runtime

# Whom or what each group's lights light, for the rows' tooltips.
_GROUP_RULES = {
    LightGroup.WORLD: "light the world",
    LightGroup.CHARACTERS: "light only characters (lightChannel LC_Character)",
    LightGroup.FOG_GI: "light only fog and global illumination (sceneDiffuse and sceneSpecularScale 0)",
    LightGroup.REFLECTIONS: "light only reflections (sceneDiffuse 0)",
    LightGroup.DEVICES: "their device switches on (entity lights with turnOnByDefault 0)",
}
# The vehicle lights each vehicle switch row switches, for the rows' tooltips.
_VEHICLE_RULES = {
    VehicleLightGroup.HEAD: "with lightType Head or Default",
    VehicleLightGroup.HIGH_BEAM: "with lightType Head or Default, the lights reaching, spreading and aiming as their "
    "high beam (highBeamRadiusMultiplier, highBeamConeMultiplier, highBeamPitchAngle)",
    VehicleLightGroup.BRAKE: "with lightType Brake or Default",
    VehicleLightGroup.LEFT_BLINKER: "with lightType LeftBlinker, Blinkers or Default",
    VehicleLightGroup.RIGHT_BLINKER: "with lightType RightBlinker, Blinkers or Default",
    VehicleLightGroup.REVERSE: "with lightType Reverse",
    VehicleLightGroup.INTERIOR: "with lightType Interior or Default",
    VehicleLightGroup.UTILITY: "with lightType Utility",
}
_CHANNEL_FILTERS = (
    ("ALL", "All", "Every light"),
    (
        "WORLD",
        "World",
        "The lights on the world channel (LC_ChannelWorld), and the lights on no channel",
    ),
    ("CHARACTER", "Character", "The lights on the character channel (LC_Character)"),
    *(
        (
            f"CHANNEL_{number}",
            f"Channel {number}",
            f"The lights on channel {number} (LC_Channel{number})",
        )
        for number in range(1, 9)
    ),
)
# The flags of the game's light channel bitfield (rendLightChannel).
_CHANNEL_FLAGS = (
    *(
        (
            f"LC_Channel{number}",
            f"Channel {number}",
            f"LC_Channel{number}",
            LC_CHANNEL1 << (number - 1),
        )
        for number in range(1, 9)
    ),
    ("LC_ChannelWorld", "World", "LC_ChannelWorld", LC_CHANNEL_WORLD),
    ("LC_Character", "Character", "LC_Character", LC_CHARACTER),
    ("LC_Player", "Player", "LC_Player", LC_PLAYER),
    ("LC_Automated", "Automated", "LC_Automated", LC_AUTOMATED),
)


def _time_get(self):
    return float(self.get("_time_of_day", 12.0))


def _time_set(self, value):
    self["_time_of_day"] = wrap_hour(value)


def _refresh_scoped(context, scope):
    scene = getattr(context, "scene", None)
    if scene is None or not hasattr(scene, "cp77_scene_tools"):
        return
    settings = scene.cp77_scene_tools
    if not settings.live_update or not scene_has_owned_runtime(scene):
        return
    refresh_environment(scene, settings, scope)


def _refresh_full(self, context):
    _refresh_scoped(context, RefreshScope.FULL)


def _refresh_exposure(self, context):
    _refresh_scoped(context, RefreshScope.EXPOSURE)


def _refresh_weather_preview(self, context):
    _refresh_scoped(context, RefreshScope.WEATHER_PREVIEW)


def _refresh_cloud_preview(self, context):
    _refresh_scoped(context, RefreshScope.CLOUD_PREVIEW)


def _refresh_fog_preview(self, context):
    _refresh_scoped(context, RefreshScope.FOG_PREVIEW)


def _group_visible(group):
    """The eye of a group's row"""

    def update(self, _context):
        show_group(self, group)

    return BoolProperty(
        name="Show",
        description=f"Show the lights that {_GROUP_RULES[group]} in the viewport and in renders; a preview, never "
        "exported",
        default=True,
        update=update,
    )


def _group_brightness(group):
    """The preview brightness of a group's row"""

    def update(self, _context):
        brighten_group(self, group)

    return FloatProperty(
        name="Brightness",
        description=f"How bright the lights that {_GROUP_RULES[group]} look in Blender; their game settings and the "
        "export are left alone",
        default=1.0,
        min=0.0,
        soft_max=4.0,
        update=update,
    )


def _switch_devices(self, _context):
    switch_devices(self)


def _switch_vehicles(self, _context):
    switch_vehicles(self)


def _vehicle_switch(group):
    """The switch of a vehicle light group's row"""
    return BoolProperty(
        name="On",
        description=f"Switch on the vehicle lights and light zones {_VEHICLE_RULES[group]}; a preview, never exported",
        default=False,
        update=_switch_vehicles,
    )


def _vehicles_on_get(self):
    return any(
        getattr(self, vehicle_switch_property(group)) for group in VehicleLightGroup
    )


def _vehicles_on_set(self, value):
    # Every group's switch is set as it is stored, so the vehicles are switched once.
    for group in VehicleLightGroup:
        self[vehicle_switch_property(group)] = bool(value)
    switch_vehicles(self)


def _show_channel(self, _context):
    show_channel(self)


def _light_float(key, name, description, **limits):
    """A setting of the selected sector light"""

    def get(_self):
        return float(selected_light_setting(bpy.context, key))

    def put(self, value):
        edit_selected_light(bpy.context, self, key, float(value))

    return FloatProperty(
        name=name, description=description, get=get, set=put, options=set(), **limits
    )


def _light_color_get(_self):
    return tuple(
        channel / 255.0 for channel in selected_light_setting(bpy.context, "color")[:3]
    )


def _light_color_set(self, value):
    alpha = selected_light_setting(bpy.context, "color")[3:4] or (255,)
    edit_selected_light(
        bpy.context,
        self,
        "color",
        (*(round(channel * 255.0) for channel in value), *alpha),
    )


def _light_channel_get(_self):
    return (
        decode_light_channel(selected_light_setting(bpy.context, "lightChannel"))[0]
        & LC_SUPPORTED_MASK
    )


def _light_channel_set(self, value):
    # The same flags keep the text the light has, which may spell them differently.
    if value != _light_channel_get(self):
        edit_selected_light(
            bpy.context, self, "lightChannel", light_channel_text(value)
        )


def _light_shadows_get(_self):
    return bool(selected_light_setting(bpy.context, "enableLocalShadows"))


def _light_shadows_set(self, value):
    edit_selected_light(bpy.context, self, "enableLocalShadows", bool(value))


class CP77SceneToolsSettings(PropertyGroup):
    time_of_day: FloatProperty(
        name="Time of Day",
        description="Cyclic 24-hour environment time; 24 wraps to 0",
        default=12.0,
        min=0.0,
        max=DAY_HOURS,
        precision=2,
        get=_time_get,
        set=_time_set,
        update=_refresh_full,
    )
    weather: EnumProperty(
        name="Weather",
        description="Environment state layered over the master definition",
        items=WEATHER_ITEMS,
        default=WEATHER_ITEMS[0][0],
        update=_refresh_full,
    )
    override_season: BoolProperty(
        name="Override Season",
        default=False,
        update=_refresh_full,
    )
    season: EnumProperty(
        name="Season",
        items=SEASON_ITEMS,
        default="ETOYS_Summer",
        update=_refresh_full,
    )
    override_latitude: BoolProperty(
        name="Override Latitude",
        default=False,
        update=_refresh_full,
    )
    latitude: FloatProperty(
        name="Latitude",
        default=45.0,
        min=-90.0,
        max=90.0,
        update=_refresh_full,
    )
    preview_exposure: FloatProperty(
        name="Preview Exposure",
        description="Blender-only exposure offset; imported environment values remain unchanged",
        default=0.0,
        soft_min=-8.0,
        soft_max=8.0,
        update=_refresh_exposure,
    )
    create_global_light: BoolProperty(
        name="Global Light",
        default=True,
    )
    create_world: BoolProperty(
        name="Environment World",
        default=True,
    )
    preview_volumetric_clouds: BoolProperty(
        name="Volumetric Clouds",
        description="Preview the evaluated CP77 weather-cloud slab using the bundled weather map and sliced 3D noise atlas",
        default=True,
        update=_refresh_cloud_preview,
    )
    preview_high_clouds: BoolProperty(
        name="Particle High Clouds",
        description="Display the separate bundled cirrus/altocumulus particle-layer preview; this is not the main CP77 weather-cloud system",
        default=False,
        update=_refresh_weather_preview,
    )
    preview_rain: BoolProperty(
        name="Rain",
        description="Display a dense camera-volume rain approximation using bundled rain resources and evaluated weather data",
        default=True,
        update=_refresh_weather_preview,
    )
    preview_volumetric_fog: BoolProperty(
        name="Volumetric Fog",
        description="Preview evaluated global volumetric fog using height-density and anisotropy parameters",
        default=True,
        update=_refresh_fog_preview,
    )
    preview_distant_fog: BoolProperty(
        name="Distant Fog",
        description="Preview the two exponential distant-fog layers as a bounded Blender volume approximation",
        default=True,
        update=_refresh_fog_preview,
    )
    weather_follow_scene_camera: BoolProperty(
        name="Follow Scene Camera",
        description="Keep camera-centered weather preview volumes on the active scene camera; disable for free viewport work and use Center Weather on View",
        default=False,
        update=_refresh_weather_preview,
    )
    live_update: BoolProperty(
        name="Live Update",
        default=True,
    )
    new_sector_index: IntProperty(name="New Sector")
    lights_world_visible: _group_visible(LightGroup.WORLD)
    lights_world_brightness: _group_brightness(LightGroup.WORLD)
    lights_characters_visible: _group_visible(LightGroup.CHARACTERS)
    lights_characters_brightness: _group_brightness(LightGroup.CHARACTERS)
    lights_fog_gi_visible: _group_visible(LightGroup.FOG_GI)
    lights_fog_gi_brightness: _group_brightness(LightGroup.FOG_GI)
    lights_reflections_visible: _group_visible(LightGroup.REFLECTIONS)
    lights_reflections_brightness: _group_brightness(LightGroup.REFLECTIONS)
    lights_devices_visible: _group_visible(LightGroup.DEVICES)
    lights_devices_brightness: _group_brightness(LightGroup.DEVICES)
    lights_devices_on: BoolProperty(
        name="On",
        description="Switch the devices on: their lights that start off (turnOnByDefault 0) and the light zones they "
        "drive; a preview, never exported",
        default=False,
        update=_switch_devices,
    )
    lights_channel_filter: EnumProperty(
        name="Light Channel",
        description="Narrow every row to the lights on this channel (lightChannel)",
        items=_CHANNEL_FILTERS,
        default="ALL",
        update=_show_channel,
    )
    lights_vehicles_on: BoolProperty(
        name="On",
        description="Switch every vehicle light group on or off; on while any is. A preview, never exported",
        get=_vehicles_on_get,
        set=_vehicles_on_set,
        options=set(),
    )
    lights_vehicle_head_on: _vehicle_switch(VehicleLightGroup.HEAD)
    lights_vehicle_high_beam_on: _vehicle_switch(VehicleLightGroup.HIGH_BEAM)
    lights_vehicle_brake_on: _vehicle_switch(VehicleLightGroup.BRAKE)
    lights_vehicle_left_blinker_on: _vehicle_switch(VehicleLightGroup.LEFT_BLINKER)
    lights_vehicle_right_blinker_on: _vehicle_switch(VehicleLightGroup.RIGHT_BLINKER)
    lights_vehicle_reverse_on: _vehicle_switch(VehicleLightGroup.REVERSE)
    lights_vehicle_interior_on: _vehicle_switch(VehicleLightGroup.INTERIOR)
    lights_vehicle_utility_on: _vehicle_switch(VehicleLightGroup.UTILITY)
    light_intensity: _light_float(
        "intensity", "Intensity", "The light's intensity (intensity)", min=0.0
    )
    light_ev: _light_float("EV", "EV", "Exposure value the intensity is raised by (EV)")
    light_color: FloatVectorProperty(
        name="Color",
        description="The light's colour (color)",
        subtype="COLOR_GAMMA",
        size=3,
        min=0.0,
        max=1.0,
        get=_light_color_get,
        set=_light_color_set,
        options=set(),
    )
    light_temperature: _light_float(
        "temperature",
        "Temperature",
        "Colour temperature in kelvin tinting the colour; -1 for none (temperature)",
        min=-1.0,
        soft_max=12000.0,
    )
    light_radius: _light_float(
        "radius", "Radius", "How far the light reaches (radius)", min=0.0
    )
    light_inner_angle: _light_float(
        "innerAngle",
        "Inner Angle",
        "The cone a spot light lights at full strength, in degrees (innerAngle)",
        min=0.0,
        soft_max=180.0,
    )
    light_outer_angle: _light_float(
        "outerAngle",
        "Outer Angle",
        "The cone a spot light lights at all, in degrees (outerAngle)",
        min=0.0,
        soft_max=180.0,
    )
    light_channel: EnumProperty(
        name="Light Channel",
        description="The channels the light lights (lightChannel)",
        items=_CHANNEL_FLAGS,
        options={"ENUM_FLAG"},
        get=_light_channel_get,
        set=_light_channel_set,
    )
    light_local_shadows: BoolProperty(
        name="Local Shadows",
        description="The light casts shadows (enableLocalShadows)",
        get=_light_shadows_get,
        set=_light_shadows_set,
        options=set(),
    )
    light_flicker_strength: _light_float(
        "flickerStrength",
        "Flicker Strength",
        "How far the light dims as it flickers, 0 to 1 (flickerStrength)",
        min=0.0,
        max=1.0,
    )
    light_flicker_period: _light_float(
        "flickerPeriod",
        "Flicker Period",
        "Seconds between the flicker's changes (flickerPeriod)",
        min=0.0,
    )


SCENE_TOOL_PROPERTY_CLASSES = (CP77SceneToolsSettings,)
