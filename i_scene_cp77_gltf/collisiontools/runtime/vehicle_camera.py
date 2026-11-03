from __future__ import annotations

import math
from dataclasses import dataclass

from mathutils import Vector

from ...bartmoss.chase_camera import (
    ChaseCameraPreset,
    reset_chase_camera,
    step_chase_camera,
)
from ...blender.context import view3d_areas
from ...blender.identity import rna_identity
from ...blender.physics.vehicle_geometry import vehicle_frame_world, vehicle_root
from ...core.log import get_logger
from ...physics.domain.vehicle.camera import default_tpp_camera, tpp_camera_preset
from ...physics.model.vehicle.camera import TPP_CAMERA_SMOOTH_TIME
from ..blender.vehicle_validation import resolved_game_config

_LOG = get_logger(__name__)

# Blender's perspective viewport fits a 72 mm sensor to the wider side of the region.
_VIEWPORT_HALF_SENSOR = 36.0


@dataclass(slots=True)
class _ViewLock:
    area_pointer: int
    saved: tuple | None
    camera: object = None


_LOCKS = {}


def _largest_view_area():
    return max(view3d_areas(), key=lambda area: area.width * area.height, default=None)


def _locked_area(lock):
    for area in view3d_areas():
        if area.as_pointer() == lock.area_pointer:
            return area
    return None


def _save_view(area):
    space = area.spaces.active
    view = space.region_3d
    return (
        view.view_location.copy(),
        view.view_rotation.copy(),
        float(view.view_distance),
        view.view_perspective,
        float(space.lens),
    )


def _restore_view(area, saved):
    space = area.spaces.active
    view = space.region_3d
    location, rotation, distance, perspective, lens = saved
    view.view_location = location
    view.view_rotation = rotation
    view.view_distance = distance
    view.view_perspective = perspective
    space.lens = lens
    area.tag_redraw()


def _camera_setup(vehicle):
    try:
        camera = resolved_game_config(vehicle).get("tpp_camera")
    except ValueError:
        camera = None
    return (
        camera
        if isinstance(camera, dict) and camera.get("presets")
        else default_tpp_camera()
    )


def _preset(vehicle, camera):
    preset = tpp_camera_preset(
        camera, vehicle.game_camera_height, vehicle.game_camera_distance
    )
    return ChaseCameraPreset(
        tuple(preset["look_at_offset"]),
        float(preset["pitch"]),
        float(preset["boom_length"]),
    )


def _vehicle_pose(vehicle):
    frame = vehicle_frame_world(vehicle)
    forward = frame.to_3x3() @ Vector((0.0, 1.0, 0.0))
    return tuple(frame.translation), tuple(forward)


def _lens(space, area, vertical_fov):
    region = next((region for region in area.regions if region.type == "WINDOW"), None)
    aspect = (
        (region.width / region.height)
        if region is not None and region.height > 0
        else 16.0 / 9.0
    )
    half = math.tan(math.radians(vertical_fov) * 0.5)
    space.lens = _VIEWPORT_HALF_SENSOR / (half * max(aspect, 1.0))


def _apply(area, camera_state, vertical_fov):
    space = area.spaces.active
    view = space.region_3d
    position = Vector(camera_state.position)
    look_at = Vector(camera_state.look_at)
    offset = position - look_at
    distance = max(offset.length, 1.0e-3)
    view.view_perspective = "PERSP"
    view.view_location = look_at
    view.view_distance = distance
    view.view_rotation = (-offset).to_track_quat("-Z", "Y")
    _lens(space, area, vertical_fov)
    area.tag_redraw()


def vehicle_camera_active(scene):
    return rna_identity(scene) in _LOCKS


def snap_vehicle_camera(scene):
    """Places the camera behind the vehicle at its preset, with no smoothing"""
    lock = _LOCKS.get(rna_identity(scene))
    vehicle = getattr(scene, "physx_vehicle", None)
    if lock is None or vehicle is None or vehicle_root(vehicle) is None:
        return
    area = _locked_area(lock)
    if area is None:
        return
    camera = _camera_setup(vehicle)
    position, forward = _vehicle_pose(vehicle)
    lock.camera = reset_chase_camera(
        _preset(vehicle, camera),
        position,
        forward,
        tuple(vehicle.linear_velocity),
        bool(vehicle.vehicle_in_air),
    )
    _apply(area, lock.camera, camera["params"]["fov"])


def start_vehicle_camera(scene):
    """Locks the largest 3D viewport to the vehicle"""
    if vehicle_camera_active(scene):
        snap_vehicle_camera(scene)
        return True
    vehicle = getattr(scene, "physx_vehicle", None)
    area = _largest_view_area()
    if vehicle is None or area is None or vehicle_root(vehicle) is None:
        return False
    _LOCKS[rna_identity(scene)] = _ViewLock(area.as_pointer(), _save_view(area))
    snap_vehicle_camera(scene)
    return True


def stop_vehicle_camera(scene=None, *, restore=True):
    """Releases the viewport lock of a scene, or of every scene, restoring the saved view"""
    if scene is None:
        locks = list(_LOCKS.values())
        _LOCKS.clear()
    else:
        lock = _LOCKS.pop(rna_identity(scene), None)
        locks = [lock] if lock is not None else []
    if not restore:
        return
    for lock in locks:
        area = _locked_area(lock)
        if area is not None and lock.saved is not None:
            try:
                _restore_view(area, lock.saved)
            except (AttributeError, ReferenceError) as error:
                _LOG.debug("Game Camera view restore skipped: %s", error)


def update_vehicle_camera(scene, dt):
    """Advances the locked camera by dt seconds of simulated time"""
    lock = _LOCKS.get(rna_identity(scene))
    vehicle = getattr(scene, "physx_vehicle", None)
    if lock is None or vehicle is None or vehicle_root(vehicle) is None:
        return
    area = _locked_area(lock)
    if area is None:
        _LOCKS.pop(rna_identity(scene), None)
        return
    if lock.camera is None:
        snap_vehicle_camera(scene)
        return
    camera = _camera_setup(vehicle)
    position, forward = _vehicle_pose(vehicle)
    step_chase_camera(
        lock.camera,
        _preset(vehicle, camera),
        camera["params"],
        position,
        forward,
        tuple(vehicle.linear_velocity),
        tuple(vehicle.angular_velocity),
        float(dt),
        in_air=bool(vehicle.vehicle_in_air),
        smooth_time=TPP_CAMERA_SMOOTH_TIME,
    )
    _apply(area, lock.camera, camera["params"]["fov"])
