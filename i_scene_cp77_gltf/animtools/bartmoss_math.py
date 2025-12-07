from __future__ import annotations
import numpy as np
from typing import Union, Any

ArrayLike = Union[np.ndarray, float, int]

def clamp(x: ArrayLike, lo: float, hi: float) -> ArrayLike:
    """Clamp value(s) to range [lo, hi]
    
    Vectorized: works on scalars and arrays.

    Args:
        x: Value or array to clamp
        lo: Lower bound
        hi: Upper bound
    
    Returns:
        Clamped value(s)
    """
    return np.clip(x, lo, hi)

def lerp(t: ArrayLike, a: ArrayLike, b: ArrayLike) -> ArrayLike:
    """Linear interpolation: (1-t)*a + t*b
    
 works on scalars and arrays.
    Args:
        t: Interpolation factor (0=a, 1=b)
        a: Start value
        b: End value
    
    Returns:
        Interpolated value(s)
    """
    return (1.0 - t) * a + t * b

def smoothstep(edge0: float, edge1: float, x: ArrayLike) -> ArrayLike:
    """Hermite smoothstep interpolation
    
    Returns 0 if x <= edge0, 1 if x >= edge1,
    smooth interpolation in between.
    
    Args:
        edge0: Lower edge
        edge1: Upper edge
        x: Value(s) to evaluate
    
    Returns:
        Smoothed value(s) in [0, 1]
    """
    t = clamp((x - edge0) / (edge1 - edge0 + 1e-10), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)

def to_int_array(arr: Any, dtype: np.dtype = np.int16) -> np.ndarray:
    """Convert list/array to NumPy integer array
    
    Args:
        arr: Input list or array-like
        dtype: NumPy integer dtype (default: int16)
    
    Returns:
        NumPy array with specified dtype
    """
    return np.asarray(arr, dtype=dtype)

def to_float_array(arr: Any, dtype: np.dtype = np.float32) -> np.ndarray:
    """Convert list/array to NumPy float array
    
    Args:
        arr: Input list or array-like
        dtype: NumPy float dtype (default: float32)
    
    Returns:
        NumPy array with specified dtype
    """
    return np.asarray(arr, dtype=dtype)

def quat_identity(n: int) -> np.ndarray:
    """Create array of identity quaternions
    
    Format: [x, y, z, w] where w=1 for identity
    
    Args:
        n: Number of quaternions
    
    Returns:
        Array of shape (n, 4) with identity quaternions
    """
    q = np.zeros((n, 4), dtype=np.float32)
    q[:, 3] = 1.0  # w component
    return q

def quat_multiply(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
    """Quaternion multiplication: q1 * q2
    
    Vectorized for arrays of quaternions.
    Format: [x, y, z, w]
    
    Args:
        q1: First quaternion(s) (..., 4)
        q2: Second quaternion(s) (..., 4)
    
    Returns:
        Product quaternion(s) (..., 4)
    """
    x1, y1, z1, w1 = q1[..., 0], q1[..., 1], q1[..., 2], q1[..., 3]
    x2, y2, z2, w2 = q2[..., 0], q2[..., 1], q2[..., 2], q2[..., 3]
    
    result = np.empty_like(q1)
    result[..., 0] = w1*x2 + x1*w2 + y1*z2 - z1*y2  # x
    result[..., 1] = w1*y2 - x1*z2 + y1*w2 + z1*x2  # y
    result[..., 2] = w1*z2 + x1*y2 - y1*x2 + z1*w2  # z
    result[..., 3] = w1*w2 - x1*x2 - y1*y2 - z1*z2  # w
    
    return result

def quat_slerp(q1: np.ndarray, q2: np.ndarray, t: ArrayLike) -> np.ndarray:
    """Spherical linear interpolation between quaternions

    Args:
        q1: Start quaternion(s) (..., 4)
        q2: End quaternion(s) (..., 4)
        t: Interpolation factor(s) [0, 1]
    
    Returns:
        Interpolated quaternion(s) (..., 4)
    """
    # Ensure t is broadcastable
    t = np.atleast_1d(t).astype(np.float32)
    while t.ndim < q1.ndim:
        t = t[..., np.newaxis]
    
    # Dot product
    dot = np.sum(q1 * q2, axis=-1, keepdims=True)
    
    # If dot < 0, negate one to take shorter path
    q2_adj = np.where(dot < 0, -q2, q2)
    dot = np.abs(dot)
    
    # For nearly identical quaternions, use lerp
    DOT_THRESHOLD = 0.9995
    close_mask = dot > DOT_THRESHOLD
    
    # Compute SLERP
    theta = np.arccos(np.clip(dot, -1.0, 1.0))
    sin_theta = np.sin(theta)
    
    # Avoid division by zero
    sin_theta = np.where(sin_theta < 1e-10, 1.0, sin_theta)
    
    s1 = np.sin((1.0 - t) * theta) / sin_theta
    s2 = np.sin(t * theta) / sin_theta
    
    result = s1 * q1 + s2 * q2_adj
    
    # Use lerp for close quaternions
    lerp_result = (1.0 - t) * q1 + t * q2_adj
    lerp_norm = np.linalg.norm(lerp_result, axis=-1, keepdims=True)
    lerp_result = lerp_result / (lerp_norm + 1e-10)
    
    result = np.where(close_mask, lerp_result, result)
    
    return result

def quat_normalize(q: np.ndarray) -> np.ndarray:
    """Normalize quaternion(s)
    
    Args:
        q: Quaternion(s) (..., 4)
    
    Returns:
        Normalized quaternion(s)
    """
    norm = np.linalg.norm(q, axis=-1, keepdims=True)
    return q / (norm + 1e-10)

def apply_additive_transform(
    base_q: np.ndarray,
    base_t: np.ndarray,
    add_q: np.ndarray,
    add_t: np.ndarray,
    weight: ArrayLike = 1.0
) -> tuple[np.ndarray, np.ndarray]:
    """Apply additive transform to base transform

        base.Translation += additive.Translation * weight
        base.Rotation = slerp(base.Rotation, base.Rotation * additive.Rotation, weight)
    
    Args:
        base_q: Base rotation quaternions (N, 4)
        base_t: Base translations (N, 3)
        add_q: Additive rotation quaternions (N, 4)
        add_t: Additive translations (N, 3)
        weight: Blend weight (scalar or array)
    
    Returns:
        Tuple of (result_q, result_t)
    """
    weight = np.atleast_1d(weight).astype(np.float32)
    while weight.ndim < base_t.ndim:
        weight = weight[..., np.newaxis]
    
    # Translation: base + additive * weight
    result_t = base_t + add_t * weight
    
    # Rotation: slerp(base, base * additive, weight)
    combined_q = quat_multiply(base_q, add_q)
    result_q = quat_slerp(base_q, combined_q, weight.squeeze())
    
    return result_q, result_t

def limit_weight(
    slider: ArrayLike,
    min_val: ArrayLike,
    mid_val: ArrayLike,
    max_val: ArrayLike
) -> ArrayLike:
    """Interpolate weight based on slider position

    - slider == 1.0: returns mid
    - slider < 1.0: interpolates min → mid
    - slider > 1.0: interpolates mid → max
    
    Vectorized for numpy arrays.
    
    Args:
        slider: Control value (0 to 2 range)
        min_val: Minimum weight
        mid_val: Middle weight (at slider=1)
        max_val: Maximum weight
    
    Returns:
        Interpolated weight
    """
    slider = np.asarray(slider)
    min_val = np.asarray(min_val)
    mid_val = np.asarray(mid_val)
    max_val = np.asarray(max_val)
    
    # Case: slider == 1.0
    result = np.where(slider == 1.0, mid_val, 0.0)
    
    # Case: slider < 1.0 (interpolate min → mid)
    below_mask = slider < 1.0
    below_result = min_val + slider * (mid_val - min_val)
    below_result = np.clip(below_result, 
                           np.minimum(min_val, mid_val),
                           np.maximum(min_val, mid_val))
    result = np.where(below_mask, below_result, result)
    
    # Case: slider > 1.0 (interpolate mid → max)
    above_mask = slider > 1.0
    above_result = mid_val + (slider - 1.0) * (max_val - mid_val)
    above_result = np.clip(above_result,
                           np.minimum(mid_val, max_val),
                           np.maximum(mid_val, max_val))
    result = np.where(above_mask, above_result, result)
    
    return result

def scale_identity(n: int) -> np.ndarray:
    """Create array of identity scales (1, 1, 1)
    
    Args:
        n: Number of scale vectors
    
    Returns:
        Array of shape (n, 3) with ones
    """
    return np.ones((n, 3), dtype=np.float32)

def swap_yz_trn_rot(dt: np.ndarray, dq: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Convert Y-up to Z-up coordinate system
    
    Coordinate transform:
    - Translation: (x, y, z) → (x, -z, y)
    - Rotation: Apply +90° X-axis conjugation (q' = s * q * s^-1)
    """
    # Translation: swap Y and Z, negate new Y
    dt_sw = np.stack([dt[:, 0], -dt[:, 2], dt[:, 1]], axis=-1)
    
    # Rotation: Conjugate by +90° X rotation
    # s = (sin(45°), 0, 0, cos(45°)) = (√0.5, 0, 0, √0.5)
    s = np.array([np.sqrt(0.5), 0.0, 0.0, np.sqrt(0.5)], dtype=dq.dtype)
    s_inv = s.copy()
    s_inv[:3] *= -1.0  # Conjugate
    
    # Broadcast to all bones
    s_b = np.broadcast_to(s, dq.shape)
    s_inv_b = np.broadcast_to(s_inv, dq.shape)
    
    # q' = s * q * s^-1
    q_tmp = quat_multiply(s_b, dq)
    dq_sw = quat_multiply(q_tmp, s_inv_b)
    
    return dt_sw, dq_sw


def wrinkle_weight(track_weight: ArrayLike) -> ArrayLike:
    """Calculate wrinkle weight from main track weight
    
    Formula: wrinkle = 1 - (1 - trackWeight)²
    This creates a parabolic response curve.
    
    Args:
        track_weight: Main track weight(s) [0, 1]
    
    Returns:
        Wrinkle weight(s) [0, 1]
    """
    u = 1.0 - track_weight
    return clamp(1.0 - u * u, 0.0, 1.0)

# JALI MOTION CURVE SHAPES

def sin_squared_ease(t: ArrayLike) -> ArrayLike:
    """Sin² easing function
    
    Used for JALI onset/decay curves per paper §4.2.
    
    Args:
        t: Normalized time [0, 1]
    
    Returns:
        Eased value [0, 1]
    """
    return np.sin(0.5 * np.pi * clamp(t, 0.0, 1.0)) ** 2

__all__ = [
    # Basic math
    'clamp', 'lerp', 'smoothstep',
    
    # Array conversion
    'to_int_array', 'to_float_array',
    
    # Quaternion operations
    'quat_identity', 'quat_multiply', 'quat_slerp', 'quat_normalize',
    
    # Transform operations
    'apply_additive_transform',
    
    # Weight functions
    'limit_weight', 'wrinkle_weight',
    
    # Identity arrays
    'scale_identity',
    
    # Easing
    'sin_squared_ease',
]