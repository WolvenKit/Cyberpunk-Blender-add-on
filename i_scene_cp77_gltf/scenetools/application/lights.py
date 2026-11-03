from __future__ import annotations

import os

import bpy
from bpy.app.handlers import persistent

from ...assetio.documents import DocumentLoadError, DocumentSession
from ...assetio.values import coerce_int
from ...blender.transactions import restore_id_property, snapshot_id_property
from ...core.log import debug_exception, get_logger
from ...core.notifications import show_message
from ...entity.domain.lights import (
    LightGroup,
    VehicleLightGroup,
    edited_light_data,
    static_light_flicker_seed,
    static_light_settings,
)
from ...exporters.sector.repository import SectorSourceRepository
from ...importers.common.light_channel_semantics import decode_light_channel
from ...importers.common.light_channels import relink_light
from ..blender.lights import light_up, rebuild_static_light, show_lights, switch_zones
from ..blender.vehicle_lights import light_vehicles
from ..runtime.lights import (
    CHANNEL_FILTER_BITS,
    SECTOR_LIGHT_NODE,
    LightPreview,
    act_on_lights,
    active_sector_light,
    clear_light_index,
    light_sector,
)

_LOG = get_logger(__name__)
_DEFAULTS = static_light_settings({})
# The light nodes of each source sector file read for an edit, by path: (file stamp, Data by node index).
_SOURCES = {}
# The source files an edit could not read, which the author was told of.
_UNREADABLE = set()


@persistent
def clear_light_sources(_unused=None):
    _SOURCES.clear()
    _UNREADABLE.clear()


def visible_property(group) -> str:
    """The scene setting that holds a group's eye"""
    return f"lights_{LightGroup(group).value.lower()}_visible"


def brightness_property(group) -> str:
    """The scene setting that holds a group's preview brightness"""
    return f"lights_{LightGroup(group).value.lower()}_brightness"


def vehicle_switch_property(group) -> str:
    """The scene setting that holds a vehicle light group's switch"""
    return f"lights_vehicle_{VehicleLightGroup(group).value.lower()}_on"


def light_preview(settings) -> LightPreview:
    """What the scene's Lights rows are set to show"""
    return LightPreview(
        shown=frozenset(
            group for group in LightGroup if getattr(settings, visible_property(group))
        ),
        brightness={
            group: getattr(settings, brightness_property(group)) for group in LightGroup
        },
        channel=CHANNEL_FILTER_BITS.get(settings.lights_channel_filter, 0),
        devices_on=settings.lights_devices_on,
        vehicles_on=frozenset(
            group
            for group in VehicleLightGroup
            if getattr(settings, vehicle_switch_property(group))
        ),
    )


def show_group(settings, group):
    """Show or hide one group's lights as its eye and the Light Channel say"""
    preview = light_preview(settings)
    act_on_lights(lambda index: show_lights(index.members(group), preview))


def show_channel(settings):
    """Show every group's lights on the Light Channel as their eyes say, and hide the rest"""
    preview = light_preview(settings)
    act_on_lights(lambda index: show_lights(index.every_member(), preview))


def brighten_group(settings, group):
    """Give one group's lights its preview brightness"""
    preview = light_preview(settings)
    act_on_lights(lambda index: light_up(index.members(group), preview))


def _switch_devices(index, preview):
    light_up(index.starting_off, preview)
    switch_zones(index.zones, preview.devices_on)


def switch_devices(settings):
    """Switch the lights and light zones that start off, waiting for their device, on or off"""
    preview = light_preview(settings)
    act_on_lights(lambda index: _switch_devices(index, preview))


def switch_vehicles(settings):
    """Switch the vehicles' lights and light zones as the vehicle group switches say"""
    preview = light_preview(settings)
    act_on_lights(
        lambda index: light_vehicles(
            index.vehicle_lights, index.vehicle_zones, preview.vehicles_on
        )
    )


def lights_before_import(scene):
    """What the file holds before an import, for preview_imported_lights"""
    settings = getattr(scene, "cp77_scene_tools", None)
    if settings is None or light_preview(settings).at_rest:
        return None
    return frozenset(obj.session_uid for obj in bpy.data.objects)


def _preview_imported(index, before, preview):
    members = tuple(
        member
        for member in index.every_member()
        if member.obj.session_uid not in before
    )
    show_lights(members, preview)
    light_up(members, preview)
    if preview.devices_on:
        # Zones start dark, as the switch's off leaves them.
        switch_zones(
            tuple(
                (zone, tuple(obj for obj in objects if obj.session_uid not in before))
                for zone, objects in index.zones
            ),
            True,
        )
    if preview.vehicles_on:
        # Vehicles start dark, as the switches' off leaves them.
        light_vehicles(
            tuple(
                light
                for light in index.vehicle_lights
                if light.samples[0].session_uid not in before
            ),
            tuple(
                (
                    zone,
                    types,
                    tuple(obj for obj in objects if obj.session_uid not in before),
                )
                for zone, types, objects in index.vehicle_zones
            ),
            preview.vehicles_on,
        )


def preview_imported_lights(scene, before):
    """Give the lights and light zones a committed import brought the scene's Lights preview"""
    if before is None:
        return
    try:
        clear_light_index()
        preview = light_preview(scene.cp77_scene_tools)
        act_on_lights(lambda index: _preview_imported(index, before, preview))
    except Exception:
        # The import stands; its lights only miss the preview.
        debug_exception(_LOG, "The imported lights did not take the Lights preview")


def _preview_light(index, light, preview):
    samples = index.samples(light)
    show_lights(samples, preview)
    light_up(samples, preview)


def first_unreadable(path) -> bool:
    """Whether path is a source file no edit failed to read before"""
    if path in _UNREADABLE:
        return False
    _UNREADABLE.add(path)
    return True


def _tell_unreadable(path, message):
    if first_unreadable(path):
        show_message(message, severity="WARNING", logger=_LOG)


def light_node_data(sector, node_index):
    """The Data of light node node_index in the imported sector's source file"""
    path = sector["cp77_sector_path"]
    stat = os.stat(path)
    stamp = (stat.st_mtime_ns, stat.st_size)
    key = os.path.normcase(os.path.realpath(path))
    cached = _SOURCES.get(key)
    if cached is None or cached[0] != stamp:
        with DocumentSession() as documents:
            source = SectorSourceRepository(documents).parsed(path)
        cached = _SOURCES[key] = (
            stamp,
            {
                node.index: node.data
                for node in source.nodes
                if node.node_type == SECTOR_LIGHT_NODE
            },
        )
    return cached[1].get(node_index)


def _node_data(sector, node_index, light):
    """The node Data a sector light was imported from, or None"""
    path = sector["cp77_sector_path"]
    try:
        data = light_node_data(sector, node_index)
    # A missing file, one that is no JSON or no sector document, one in another layout (SectorLayoutError is a
    # ValueError), or a document too damaged for the parser.
    except (OSError, DocumentLoadError, LookupError, TypeError, ValueError) as error:
        debug_exception(_LOG, "%s could not be read for %s", path, light.name)
        _tell_unreadable(
            path,
            f"{light.name} keeps its edit, but its Blender light is not rebuilt: {path} cannot be "
            f"read ({error}). Export the sector again and import it again.",
        )
        return None
    if data is None:
        _tell_unreadable(
            path,
            f"{light.name} keeps its edit, but its Blender light is not rebuilt: {path} has no "
            f"light node {node_index}. Import the sector again.",
        )
    return data


def _node_channel(data, text):
    """text, or the node's own text when it names the node's flags"""
    own = static_light_settings(data)["lightChannel"]
    return (
        own if decode_light_channel(own)[0] == decode_light_channel(text)[0] else text
    )


def selected_light_setting(context, key):
    """The game setting key of the selected sector light"""
    light = active_sector_light(context)
    value = light.get(key, _DEFAULTS[key]) if light is not None else _DEFAULTS[key]
    return tuple(value) if key == "color" else value


def edit_selected_light(context, settings, key, value):
    """Give the selected sector light the game setting key and rebuild its Blender light"""
    light = active_sector_light(context)
    sector = light_sector(context.scene, light) if light is not None else None
    if sector is None:
        return
    node_index = coerce_int(light.get("nodeIndex"), -1)
    data = _node_data(sector, node_index, light)
    if key == "lightChannel" and data is not None:
        value = _node_channel(data, value)
    stored = snapshot_id_property(light, key)
    light[key] = list(value) if isinstance(value, tuple) else value
    try:
        if data is not None:
            samples = act_on_lights(
                lambda index: tuple(member.obj for member in index.samples(light))
            ) or (light,)
            seed = static_light_flicker_seed(
                light.get("cp77_sector_name"),
                node_index,
                light.get("cp77_instance_idx"),
            )
            rebuild_static_light(
                samples, edited_light_data(data, light), seed, context.scene
            )
    except Exception as error:
        # The edit is not kept, so the export writes what the Blender light shows.
        debug_exception(_LOG, "%s could not be rebuilt for %s", light.name, key)
        restore_id_property(light, key, stored)
        show_message(
            f"{light.name}: {key} was not changed, because its Blender light could not be rebuilt "
            f"({error}).",
            severity="WARNING",
            logger=_LOG,
        )
    finally:
        if key == "lightChannel":
            clear_light_index()
            scope = context.scene.collection
            if scope.get("cp77_sector_light_channel_scope"):
                relink_light(light, scope)
        preview = light_preview(settings)
        act_on_lights(lambda index: _preview_light(index, light, preview))
