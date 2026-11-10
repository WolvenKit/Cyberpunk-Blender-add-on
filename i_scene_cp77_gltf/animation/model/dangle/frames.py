from __future__ import annotations

from typing import NamedTuple


class EllipsoidFrame(NamedTuple):
    center: tuple
    rotation: tuple
    inverse: tuple


class ConeFrame(NamedTuple):
    origin: tuple
    initial_axis: tuple | None
    """Unit cone axis; None when the frame's axis is degenerate."""
    orthogonal_axis: tuple | None
    """Unit hinge normal for hinge and half cones; None for plain cones or a degenerate normal."""
    collision_orthogonal: tuple
    """The frame's Z axis as rotated, unnormalized (directed rotational projection)."""


class DyngFrame(NamedTuple):
    ellipsoids: dict
    """Ellipsoid constraint index -> EllipsoidFrame."""
    cones: dict
    """Cone constraint index -> ConeFrame."""
    directed_axes: dict
    """Particle index -> float32 capsule axis in model space (directed collision projection)."""


class SpringFrame(NamedTuple):
    parent_position: tuple
    pull_origin: tuple
    rotation: tuple
    """Constraint ellipsoid rotation."""
    inverse: tuple


class PendulumFrame(NamedTuple):
    parent_position: tuple
    initial_axis: tuple
    orthogonal_axis: tuple
    pull_direction: tuple


class PositionProjectionParams(NamedTuple):
    projection_type: str
    capsule_radius: float
    capsule_height: float


class DyngParams(NamedTuple):
    substep_time: float
    solver_iterations: int


class SpringParams(NamedTuple):
    mass: float
    pull_force: float
    damping: float
    simulation_fps: float
    projection_type: str
    collision_radius: float
    constraint_radius: float
    constraint_scale1: float
    constraint_scale2: float


class PendulumParams(NamedTuple):
    mass: float
    pull_force: float
    damping: float
    simulation_fps: float
    constraint_type: str
    projection_type: str
    collision_radius: float
    collision_height: float
    half_angle: float
    """Half aperture in degrees, clamped to [0, 180]."""
    half_sine: float
    """float32 sine and cosine of half of ``half_angle`` (the rotation limit as a quaternion)."""
    half_cosine: float
