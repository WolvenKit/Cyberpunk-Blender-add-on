from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple, Protocol


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


class DangleFrames(Protocol):
    """Host-side frame evaluation for one DangleSystem"""

    def begin_shapes(self, shapes: Sequence[dict]) -> None:
        """Make each shape's current transform the previous one and take the new one from its bone"""

    def initialize_shapes(self, shapes: Sequence[dict]) -> None:
        """Snap previous, current and posed transforms of each shape to its bone"""

    def pose_shapes(self, shapes: Sequence[dict], progress: float) -> None:
        """Pose each shape between its previous and current transform"""

    def dyng_frame(self, node_index: int, progress: float) -> DyngFrame:
        """Interpolate the node's tracked bones and evaluate its constraint frames"""

    def reset_dyng_interpolation(self, node_index: int) -> None:
        """Make the previous and interpolated frames of the node's particles their current frames"""

    def current_bone_axis(self, particle_index: int):
        """A particle's capsule axis rotated by its current bone (float32)"""

    def spring_frame(self, node_index: int, progress: float) -> SpringFrame:
        """Spring parent frame between the previous and current step"""

    def spring_rest_position(self, node_index: int) -> tuple:
        """Current spring parent position"""

    def pendulum_frame(self, node_index: int, progress: float) -> PendulumFrame:
        """Pendulum constraint frame between the previous and current step"""

    def pendulum_rest_frame(self, node_index: int) -> tuple:
        """(current parent position, unnormalized current constraint axis)"""
