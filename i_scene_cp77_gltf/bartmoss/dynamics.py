from __future__ import annotations

import numpy as np


def damping_force(velocity, damping, mass, acceleration_limit: float = 50.0):
    result = np.asarray(velocity, dtype=np.float64) * -float(damping)
    limit = float(acceleration_limit) * float(mass)
    length = float(np.linalg.norm(result))
    if length > limit and length > 0.0:
        result *= limit / length
    return result


def clamp_damping_vectors(
    velocity,
    factors,
    limit,
    *,
    out,
    norm_buffer,
    safe_buffer,
    clamped_buffer,
    mask_buffer,
):
    np.multiply(velocity, factors[..., None], out=out)
    np.einsum("ij,ij->i", out, out, out=norm_buffer)
    np.sqrt(norm_buffer, out=norm_buffer)
    safe_buffer[:] = norm_buffer
    safe_buffer[norm_buffer < 1e-6] = 1.0
    np.divide(out, safe_buffer[:, None], out=clamped_buffer)
    clamped_buffer *= limit
    np.greater(norm_buffer, limit, out=mask_buffer)
    np.copyto(out, clamped_buffer, where=mask_buffer[:, None])
    return out
<<<<<<< Updated upstream
=======


def quintic_decay(
    error, velocity, duration, time: float, *, clamp_initial_acceleration: bool = False
):
    """Quintic decay from (error, velocity) to rest over duration"""
    x0, v0, t1 = error, velocity, duration
    with np.errstate(divide="ignore", invalid="ignore"):
        t1_2 = t1 * t1
        t1_3, t1_4, t1_5 = t1_2 * t1, t1_2 * t1_2, t1_2 * t1_2 * t1
        a0 = (-8.0 * v0 * t1 - 20.0 * x0) / t1_2
        if clamp_initial_acceleration:
            a0 = np.where(a0 * x0 <= 0.0, 0.0, a0)
        a = -(a0 * t1_2 + 6.0 * v0 * t1 + 12.0 * x0) / (2.0 * t1_5)
        b = (3.0 * a0 * t1_2 + 16.0 * v0 * t1 + 30.0 * x0) / (2.0 * t1_4)
        c = -(3.0 * a0 * t1_2 + 12.0 * v0 * t1 + 20.0 * x0) / (2.0 * t1_3)
        t = float(time)
        return ((((a * t + b) * t + c) * t + 0.5 * a0) * t + v0) * t + x0
>>>>>>> Stashed changes
