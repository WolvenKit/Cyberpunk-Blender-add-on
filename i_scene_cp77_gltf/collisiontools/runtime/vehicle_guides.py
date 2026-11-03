from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

import blf
import bpy
import gpu
from bpy_extras.view3d_utils import location_3d_to_region_2d
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Quaternion, Vector

from ...bartmoss.vehicle import (
    box_inertia,
    equivalent_inertia_box,
    radii_of_gyration,
    static_wheel_loads,
)
from ...bartmoss.wireframes import box_wireframe, coil_wireframe, ring_wireframe
from ...blender.context import tag_view3d_redraw
from ...blender.physics.vehicle_geometry import vehicle_actor_world
from ...core.log import get_logger, log_once
from ..blender.vehicle_authoring_state import scene_gravity_magnitude
from ..blender.vehicle_config import vehicle_live_dynamics_config
from .vehicle_preview import _runtime

_LOG = get_logger(__name__)

SPRING_COLOR = (1.0, 0.72, 0.18, 1.0)
SPRING_LIMIT_COLOR = (1.0, 0.25, 0.2, 1.0)
TRAVEL_COLOR = (0.85, 0.85, 0.85, 0.9)
MASS_COLOR = (1.0, 0.35, 0.9, 1.0)
SUPPORT_COLOR = (1.0, 0.35, 0.9, 0.45)
AXIS_COLORS = ((1.0, 0.3, 0.3, 1.0), (0.35, 1.0, 0.4, 1.0), (0.35, 0.6, 1.0, 1.0))
INERTIA_BOX_COLOR = (0.7, 0.7, 0.75, 0.55)
LABEL_SIZE = 12
_CONFIG_LIFETIME = 0.2

_view_handle = None
_pixel_handle = None
_shader = None
_config_cache = {}


@dataclass(slots=True)
class GuideLayer:
    color: tuple
    vertices: list = field(default_factory=list)
    lines: list = field(default_factory=list)

    def add(self, local_vertices, local_lines, matrix):
        offset = len(self.vertices)
        self.vertices.extend(matrix @ Vector(vertex) for vertex in local_vertices)
        self.lines.extend((a + offset, b + offset) for a, b in local_lines)


def _guide_config(scene, vehicle):
    """The live vehicle values, recomputed at most every _CONFIG_LIFETIME seconds per scene"""
    key = scene.as_pointer()
    now = perf_counter()
    cached = _config_cache.get(key)
    if cached is not None and now - cached[0] < _CONFIG_LIFETIME:
        return cached[1]
    config = vehicle_live_dynamics_config(vehicle)
    _config_cache[key] = (now, config)
    return config


def _wheel_compressions(vehicle, state, config, strengths, lengths):
    """Current compression per wheel"""
    count = len(lengths)
    if vehicle.preview_built and state is not None and state.last_stats:
        return [
            float(value) for value in tuple(vehicle.wheel_compression)[:count]
        ], False
    gravity = max(scene_gravity_magnitude(vehicle.id_data), 1.0e-6)
    loads = static_wheel_loads(
        float(config.get("chassis_mass", vehicle.chassis_mass)) * gravity,
        config["wheel_target_centers"],
        config["chassis_cm_offset"],
    )
    return [
        min(max(load / strength if strength > 1.0e-6 else length, 0.0), length)
        for load, strength, length in zip(loads, strengths, lengths)
    ], True


def _mass_properties(vehicle, state, config):
    """(mass, principal moments, principal frame in the actor frame, source label)"""
    stats = state.last_stats if state is not None and vehicle.preview_built else None
    if stats and stats.get("chassis_inertia") and stats.get("chassis_mass_pose"):
        pose = stats["chassis_mass_pose"]
        frame = (
            Matrix.Translation(Vector(pose[:3]))
            @ Quaternion((pose[6], pose[3], pose[4], pose[5]))
            .normalized()
            .to_matrix()
            .to_4x4()
        )
        return (
            float(stats["chassis_mass"]),
            tuple(float(v) for v in stats["chassis_inertia"]),
            frame,
            "preview",
        )
    mass = float(config.get("chassis_mass", vehicle.chassis_mass))
    com = Vector(config["chassis_cm_offset"])
    if config.get("chassis_inertia"):
        return (
            mass,
            tuple(float(v) for v in config["chassis_inertia"]),
            Matrix.Translation(com),
            "authored",
        )
    half_extents = tuple(0.5 * float(value) for value in vehicle.chassis_dims)
    return (
        mass,
        box_inertia(mass, half_extents, tuple(-com)),
        Matrix.Translation(com),
        "collider box",
    )


def _build_guides(context):
    """GuideLayers in world space and (world position, text, color) labels"""
    scene = context.scene
    vehicle = getattr(scene, "physx_vehicle", None)
    if vehicle is None or not vehicle.enabled or not vehicle.show_authoring_guides:
        return (), ()
    if (vehicle.rig if vehicle.source_mode == "RIG" else vehicle.chassis) is None:
        return (), ()
    config = _guide_config(scene, vehicle)
    state = _runtime(scene, create=False)
    actor = vehicle_actor_world(vehicle)
    labels = []

    springs = GuideLayer(SPRING_COLOR)
    limited = GuideLayer(SPRING_LIMIT_COLOR)
    travel = GuideLayer(TRAVEL_COLOR)
    centers = [Vector(center) for center in config["wheel_target_centers"]]
    radii = [float(value) for value in config["wheel_radii"]]
    offsets = [
        float(value)
        for value in config.get("wheel_vertical_offsets") or [0.0] * len(centers)
    ]
    bumps = [float(value) for value in config["suspension_compressions"]]
    droops = [float(value) for value in config["suspension_droops"]]
    lengths = [bump + droop for bump, droop in zip(bumps, droops)]
    strengths = [float(value) for value in config["suspension_spring_strengths"]]
    compressions, estimated = _wheel_compressions(
        vehicle, state, config, strengths, lengths
    )
    hubs = []
    for center, radius, offset, bump, droop, length, compression in zip(
        centers, radii, offsets, bumps, droops, lengths, compressions
    ):
        top = center + Vector((0.0, 0.0, bump - offset))
        hub = center + Vector((0.0, 0.0, compression - droop - offset))
        bottom = center + Vector((0.0, 0.0, -droop - offset))
        hubs.append(hub)
        free = max(length - compression, 0.0)
        near_limit = length > 1.0e-6 and not 0.05 <= compression / length <= 0.95
        coil_vertices, coil_lines = coil_wireframe(
            round(radius * 0.3, 4), round(free, 4)
        )
        (limited if near_limit else springs).add(
            coil_vertices, coil_lines, Matrix.Translation(top)
        )
        tick = radius * 0.45
        for point in (top, bottom):
            travel.add(
                ((0.0, -tick, 0.0), (0.0, tick, 0.0)),
                ((0, 1),),
                Matrix.Translation(point),
            )
        travel.add(
            ((0.0, 0.0, 0.0), tuple(bottom - top)), ((0, 1),), Matrix.Translation(top)
        )
        labels.append(
            (
                actor @ (top + Vector((0.0, 0.0, 0.04))),
                f"spring {length:.3f} m · free {free:.3f} m"
                + (" (static sag)" if estimated else ""),
                SPRING_LIMIT_COLOR if near_limit else SPRING_COLOR,
            )
        )

    mass, inertia, principal, source = _mass_properties(vehicle, state, config)
    com = principal.translation.copy()
    ground = min(hub.z - radius for hub, radius in zip(hubs, radii)) if hubs else com.z
    mass_layer = GuideLayer(MASS_COLOR)
    marker = 0.08
    mass_layer.add(
        (
            (-marker, 0.0, 0.0),
            (marker, 0.0, 0.0),
            (0.0, -marker, 0.0),
            (0.0, marker, 0.0),
            (0.0, 0.0, -marker),
            (0.0, 0.0, marker),
        ),
        ((0, 1), (2, 3), (4, 5)),
        Matrix.Translation(com),
    )
    for axis in range(3):
        mass_layer.add(*ring_wireframe(marker * 0.6, axis, 16), Matrix.Translation(com))
    floor = Vector((com.x, com.y, ground))
    mass_layer.add(
        ((0.0, 0.0, 0.0), tuple(floor - com)), ((0, 1),), Matrix.Translation(com)
    )
    mass_layer.add(
        (
            (-marker, -marker, 0.0),
            (marker, marker, 0.0),
            (-marker, marker, 0.0),
            (marker, -marker, 0.0),
        ),
        ((0, 1), (2, 3)),
        Matrix.Translation(floor),
    )
    support = GuideLayer(SUPPORT_COLOR)
    order = (0, 1, 3, 2) if len(hubs) == 4 else tuple(range(len(hubs)))
    contacts = [(hubs[index].x, hubs[index].y, ground) for index in order]
    support.add(
        contacts,
        tuple((index, (index + 1) % len(contacts)) for index in range(len(contacts))),
        Matrix.Identity(4),
    )
    labels.append(
        (
            actor @ (com + Vector((0.0, 0.0, marker * 1.6))),
            f"CoM · {mass:.0f} kg · {com.z - ground:.2f} m above ground",
            MASS_COLOR,
        )
    )

    rings = [GuideLayer(color) for color in AXIS_COLORS]
    gyration = radii_of_gyration(mass, inertia)
    for axis, (layer, radius) in enumerate(zip(rings, gyration)):
        layer.add(*ring_wireframe(round(radius, 4), axis, 48), principal)
    inertia_box = GuideLayer(INERTIA_BOX_COLOR)
    inertia_box.add(
        *box_wireframe(
            tuple(round(v, 4) for v in equivalent_inertia_box(mass, inertia))
        ),
        principal,
    )
    labels.append(
        (
            actor @ (com + Vector((0.0, 0.0, max(gyration) + 0.08))),
            "inertia ({}): pitch {:.0f} · roll {:.0f} · yaw {:.0f} kg·m²".format(
                source, *inertia
            ),
            (0.9, 0.9, 0.95, 1.0),
        )
    )

    layers = (travel, springs, limited, mass_layer, support, *rings, inertia_box)
    for layer in layers:
        layer.vertices = [actor @ vertex for vertex in layer.vertices]
    return layers, labels


_frame_guides = {}


def _draw_view():
    global _shader
    context = bpy.context
    try:
        layers, labels = _build_guides(context)
    except Exception as error:
        _frame_guides.clear()
        log_once(
            _LOG,
            "WARNING",
            ("vehicle_guides", type(error).__name__),
            "Vehicle authoring guides unavailable: %s",
            error,
            exc_info=True,
        )
        return
    _frame_guides["labels"] = labels
    if not layers:
        return
    if _shader is None:
        _shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    matrix = context.region_data.perspective_matrix
    try:
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("NONE")
        gpu.state.line_width_set(2.0)
        _shader.bind()
        _shader.uniform_float("ModelViewProjectionMatrix", matrix)
        for layer in layers:
            if not layer.lines:
                continue
            batch = batch_for_shader(
                _shader, "LINES", {"pos": layer.vertices}, indices=layer.lines
            )
            _shader.uniform_float("color", layer.color)
            batch.draw(_shader)
    finally:
        gpu.state.line_width_set(1.0)
        gpu.state.blend_set("NONE")


def _draw_labels():
    labels = _frame_guides.get("labels")
    if not labels:
        return
    context = bpy.context
    region = context.region
    view = context.region_data
    font = 0
    blf.size(font, LABEL_SIZE)
    for position, text, color in labels:
        point = location_3d_to_region_2d(region, view, position)
        if point is None:
            continue
        blf.color(font, *color)
        blf.position(font, point.x + 6.0, point.y + 4.0, 0.0)
        blf.draw(font, text)


def tag_guides_redraw():
    _config_cache.clear()
    tag_view3d_redraw()


def register_vehicle_guides():
    global _view_handle, _pixel_handle
    unregister_vehicle_guides()
    _view_handle = bpy.types.SpaceView3D.draw_handler_add(
        _draw_view, (), "WINDOW", "POST_VIEW"
    )
    _pixel_handle = bpy.types.SpaceView3D.draw_handler_add(
        _draw_labels, (), "WINDOW", "POST_PIXEL"
    )


def unregister_vehicle_guides():
    global _view_handle, _pixel_handle, _shader
    for handle in (_view_handle, _pixel_handle):
        if handle is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(handle, "WINDOW")
            except (ReferenceError, RuntimeError, TypeError, ValueError):
                pass
    _view_handle = None
    _pixel_handle = None
    _shader = None
    _config_cache.clear()
    _frame_guides.clear()
