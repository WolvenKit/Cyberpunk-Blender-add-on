from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VehicleArchetype:
    key: str
    kind: str
    record_id: str
    label: str


ARCHETYPES = {
    item.key: item
    for item in (
        VehicleArchetype(
            "CAR_STANDARD", "CAR", "Vehicle.v_standard2_archer_hella", "Standard Car"
        ),
        VehicleArchetype(
            "CAR_SPORT", "CAR", "Vehicle.v_sport1_quadra_turbo", "Sport Car"
        ),
        VehicleArchetype(
            "CAR_OFFROAD", "CAR", "Vehicle.v_sport2_quadra_type66_nomad", "Off-road Car"
        ),
        VehicleArchetype(
            "BIKE_KUSANAGI", "BIKE", "Vehicle.v_sportbike1_yaiba_kusanagi", "Sport Bike"
        ),
        VehicleArchetype("BIKE_ARCH", "BIKE", "Vehicle.v_sportbike2_arch", "Road Bike"),
        VehicleArchetype(
            "BIKE_APOLLO",
            "BIKE",
            "Vehicle.v_sportbike3_brennan_apollo",
            "Off-road Bike",
        ),
    )
}


def archetype(key):
    try:
        return ARCHETYPES[str(key)]
    except KeyError as error:
        raise ValueError(f"Unknown vehicle archetype: {key}") from error
