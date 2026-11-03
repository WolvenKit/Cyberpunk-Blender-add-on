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
