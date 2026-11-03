from __future__ import annotations

from ...blender.operator_results import OperationResult
from ...blender.transactions import transactional
from ..blender.vehicle_lights import rebuild_channels
from ..runtime.vehicle_lights import vehicle_light_collections


@transactional("Light channel refresh")
def refresh_light_channels(context) -> OperationResult:
    """Re-evaluate every vehicle's light-channel volumes and rebuild its light links"""
    vehicles = vehicle_light_collections()
    if not vehicles:
        return OperationResult.cancelled(
            "No imported vehicle has lights.", level="WARNING"
        )
    linked = lights = volumes = 0
    for collection in vehicles:
        summary = rebuild_channels(collection, context.view_layer)
        linked, lights, volumes = (
            linked + summary["linked"],
            lights + summary["lights"],
            volumes + summary["volumes"],
        )
    return OperationResult.finished(
        f"{linked} of {lights} vehicle lights linked across {volumes} light-channel volumes."
    )
