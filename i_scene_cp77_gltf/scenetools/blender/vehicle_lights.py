from __future__ import annotations

from ...blender.light_preview import BASE_ENERGY_KEY, PREVIEW_AVAILABLE_KEY, set_zone_on
from ...entity.domain.lights import (
    HIGH_BEAM_STRENGTH,
    VEHICLE_GROUP_TYPES,
    VehicleLightGroup,
    high_beam_energy,
    vehicle_light_lit,
)
from ...importers.common.light_channels import rebuild_light_channel_links
from ...importers.common.vehicle_light_preview import (
    apply_high_beam_geometry,
    restore_base_geometry,
    set_light_energy_animation_muted,
)

_HIGH_BEAM = VEHICLE_GROUP_TYPES[VehicleLightGroup.HIGH_BEAM]


def has_vehicle_lights(collection) -> bool:
    return bool(collection.get("cp77_entity_imported", False)) and bool(
        collection.get(PREVIEW_AVAILABLE_KEY, False)
    )


def light_vehicles(lights, zones, on):
    """Light each enabled vehicle light and zone while a group that drives it is on"""
    high_beam = VehicleLightGroup.HIGH_BEAM in on
    for light in lights:
        lit = light.enabled and vehicle_light_lit(light.types, on)
        raised = lit and high_beam and bool(light.types & _HIGH_BEAM)
        for sample in light.samples:
            if raised:
                apply_high_beam_geometry(
                    sample, apply_rotation=sample is light.samples[0]
                )
            elif light.types & _HIGH_BEAM:
                restore_base_geometry(sample)
            energy = float(sample.get(BASE_ENERGY_KEY, 0.0)) if lit else 0.0
            if raised:
                energy = high_beam_energy(energy, sample.get("onStrength", 1.0))
            if sample.data.energy != energy:
                sample.data.energy = energy
            set_light_energy_animation_muted(sample.data, not lit)
    for zone, types, objects in zones:
        raised = high_beam and bool(types & _HIGH_BEAM)
        set_zone_on(
            objects,
            zone,
            vehicle_light_lit(types, on),
            level=HIGH_BEAM_STRENGTH if raised else None,
        )


def rebuild_channels(collection, view_layer) -> dict:
    """Re-evaluate the collection's light-channel volumes and rebuild its light links"""
    view_layer.update()
    return rebuild_light_channel_links(
        collection, record_collections=(collection,), mode="ENTITY"
    )
