from __future__ import annotations

import math

import numpy as np

<<<<<<< Updated upstream
=======
IDENTITY_XYZW = (0.0, 0.0, 0.0, 1.0)

>>>>>>> Stashed changes

def identity_xyzw(count: int, dtype=np.float32) -> np.ndarray:
    result = np.zeros((int(count), 4), dtype=dtype)
    result[:, 3] = 1.0
    return result


def identity_wxyz(count: int, dtype=np.float32) -> np.ndarray:
    result = np.zeros((int(count), 4), dtype=dtype)
    result[:, 0] = 1.0
    return result


<<<<<<< Updated upstream
def multiply_xyzw(left, right) -> np.ndarray:
    left = np.asarray(left)
    right = np.asarray(right)
    lx, ly, lz, lw = np.moveaxis(left, -1, 0)
    rx, ry, rz, rw = np.moveaxis(right, -1, 0)
    return np.stack((
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
        lw * rw - lx * rx - ly * ry - lz * rz,
    ), axis=-1)
=======
def normalize_scalar_xyzw(
    value, epsilon: float = 1e-15
) -> tuple[float, float, float, float]:
    x, y, z, w = (float(component) for component in value)
    length_sq = x * x + y * y + z * z + w * w
    if length_sq <= float(epsilon) * float(epsilon):
        return (0.0, 0.0, 0.0, 1.0)
    inv = 1.0 / math.sqrt(length_sq)
    return (x * inv, y * inv, z * inv, w * inv)


def normalized_single_xyzw(
    value, epsilon: float = 1e-15
) -> tuple[float, float, float, float]:
    """One quaternion normalized with the same arithmetic as normalize_xyzw (bit-identical, no arrays)"""
    x, y, z, w = (float(component) for component in value[:4])
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    if norm <= epsilon:
        return (0.0, 0.0, 0.0, 1.0)
    return (x / norm, y / norm, z / norm, w / norm)


def multiply_unit_scalar_xyzw(left, right) -> tuple[float, float, float, float]:
    lx, ly, lz, lw = normalize_scalar_xyzw(left)
    rx, ry, rz, rw = normalize_scalar_xyzw(right)
    return normalize_scalar_xyzw(
        (
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
            lw * rw - lx * rx - ly * ry - lz * rz,
        )
    )


def rotate_vector_scalar_xyzw(rotation, vector) -> tuple[float, float, float]:
    x, y, z, w = normalize_scalar_xyzw(rotation)
    vx, vy, vz = (float(component) for component in vector)
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    )


def multiply_scalar_xyzw(left, right) -> tuple[float, float, float, float]:
    """Hamilton product of unit quaternions, renormalized"""
    lx, ly, lz, lw = left
    rx, ry, rz, rw = right
    x = lw * rx + lx * rw + ly * rz - lz * ry
    y = lw * ry - lx * rz + ly * rw + lz * rx
    z = lw * rz + lx * ry - ly * rx + lz * rw
    w = lw * rw - lx * rx - ly * ry - lz * rz
    length_sq = x * x + y * y + z * z + w * w
    if length_sq <= 1e-30:
        return (0.0, 0.0, 0.0, 1.0)
    inv = 1.0 / np.sqrt(length_sq)
    return (x * inv, y * inv, z * inv, w * inv)


def rotate_vector_unit_scalar_xyzw(rotation, vector) -> tuple[float, float, float]:
    """Rotate a vector by a quaternion the caller guarantees is unit length"""
    x, y, z, w = rotation
    vx, vy, vz = vector
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return (
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    )


def slerp_scalar_xyzw(left, right, weight: float) -> tuple[float, float, float, float]:
    left = normalize_scalar_xyzw(left)
    right = normalize_scalar_xyzw(right)
    weight = float(weight)
    dot = sum(a * b for a, b in zip(left, right))
    if dot < 0.0:
        right = tuple(-component for component in right)
        dot = -dot
    dot = max(-1.0, min(1.0, dot))
    if dot > 0.9995:
        return normalize_scalar_xyzw(
            tuple((1.0 - weight) * a + weight * b for a, b in zip(left, right))
        )
    theta = math.acos(dot)
    sin_theta = math.sin(theta)
    if abs(sin_theta) <= 1e-10:
        return left
    first = math.sin((1.0 - weight) * theta) / sin_theta
    second = math.sin(weight * theta) / sin_theta
    return normalize_scalar_xyzw(
        tuple(first * a + second * b for a, b in zip(left, right))
    )


def shortest_rotation_scalar_xyzw(
    source, target, fallback_axis=None
) -> tuple[float, float, float, float]:
    sx, sy, sz = (float(component) for component in source)
    tx, ty, tz = (float(component) for component in target)
    sl = math.sqrt(sx * sx + sy * sy + sz * sz)
    tl = math.sqrt(tx * tx + ty * ty + tz * tz)
    if sl <= 1e-12 or tl <= 1e-12:
        return (0.0, 0.0, 0.0, 1.0)
    sx, sy, sz = sx / sl, sy / sl, sz / sl
    tx, ty, tz = tx / tl, ty / tl, tz / tl
    dot = max(-1.0, min(1.0, sx * tx + sy * ty + sz * tz))
    if dot >= 1.0 - 1e-10:
        return (0.0, 0.0, 0.0, 1.0)
    if dot <= -1.0 + 1e-10:
        if fallback_axis is None:
            bx, by, bz = (1.0, 0.0, 0.0)
            if abs(sx) > 0.9:
                bx, by, bz = (0.0, 1.0, 0.0)
            ax, ay, az = sy * bz - sz * by, sz * bx - sx * bz, sx * by - sy * bx
        else:
            fx, fy, fz = (float(component) for component in fallback_axis)
            projection = fx * sx + fy * sy + fz * sz
            ax, ay, az = (
                fx - sx * projection,
                fy - sy * projection,
                fz - sz * projection,
            )
            length = math.sqrt(ax * ax + ay * ay + az * az)
            if length <= 1e-12:
                bx, by, bz = (1.0, 0.0, 0.0)
                if abs(sx) > 0.9:
                    bx, by, bz = (0.0, 1.0, 0.0)
                ax, ay, az = sy * bz - sz * by, sz * bx - sx * bz, sx * by - sy * bx
        length = max(math.sqrt(ax * ax + ay * ay + az * az), 1e-15)
        return (ax / length, ay / length, az / length, 0.0)
    ax, ay, az = sy * tz - sz * ty, sz * tx - sx * tz, sx * ty - sy * tx
    return normalize_scalar_xyzw((ax, ay, az, 1.0 + dot))


def axis_angle_scalar_xyzw(axis, angle: float) -> tuple[float, float, float, float]:
    x, y, z = (float(component) for component in axis)
    length = max(math.sqrt(x * x + y * y + z * z), 1e-15)
    half = 0.5 * float(angle)
    sine = math.sin(half) / length
    return normalize_scalar_xyzw((x * sine, y * sine, z * sine, math.cos(half)))


def multiply_xyzw(left, right) -> np.ndarray:
    left, right = np.broadcast_arrays(np.asarray(left), np.asarray(right))
    result = np.empty(left.shape, dtype=np.result_type(left.dtype, right.dtype))
    multiply_xyzw_into(left, right, result)
    return result
>>>>>>> Stashed changes


def multiply_wxyz(left, right) -> np.ndarray:
    left = np.asarray(left)
    right = np.asarray(right)
    lw, lx, ly, lz = np.moveaxis(left, -1, 0)
    rw, rx, ry, rz = np.moveaxis(right, -1, 0)
<<<<<<< Updated upstream
    return np.stack((
        lw * rw - lx * rx - ly * ry - lz * rz,
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
    ), axis=-1)


def normalize_xyzw(values, epsilon: float = 1e-15) -> np.ndarray:
    result = np.asarray(values).copy()
=======
    return np.stack(
        (
            lw * rw - lx * rx - ly * ry - lz * rz,
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
        ),
        axis=-1,
    )


def product_matrix_wxyz(left, right) -> np.ndarray:
    """The 4x4 matrix taking a quaternion q to left * q * right"""
    lw, lx, ly, lz = (float(value) for value in left)
    rw, rx, ry, rz = (float(value) for value in right)
    by_left = np.array(
        ((lw, -lx, -ly, -lz), (lx, lw, -lz, ly), (ly, lz, lw, -lx), (lz, -ly, lx, lw))
    )
    by_right = np.array(
        ((rw, -rx, -ry, -rz), (rx, rw, rz, -ry), (ry, -rz, rw, rx), (rz, ry, -rx, rw))
    )
    return by_right @ by_left


def normalize_xyzw(values, epsilon: float = 1e-15) -> np.ndarray:
    source = np.asarray(values)
    dtype = source.dtype if np.issubdtype(source.dtype, np.floating) else np.float64
    result = np.asarray(values, dtype=dtype).copy()
>>>>>>> Stashed changes
    norms = np.linalg.norm(result, axis=-1, keepdims=True)
    invalid = norms <= epsilon
    np.divide(result, np.where(invalid, 1.0, norms), out=result)
    if np.any(invalid):
        result = np.where(
            invalid,
            np.asarray((0.0, 0.0, 0.0, 1.0), dtype=result.dtype),
            result,
        )
    return result


def normalize_wxyz(values, epsilon: float = 1e-15) -> np.ndarray:
<<<<<<< Updated upstream
    result = np.asarray(values).copy()
=======
    source = np.asarray(values)
    dtype = source.dtype if np.issubdtype(source.dtype, np.floating) else np.float64
    result = np.asarray(values, dtype=dtype).copy()
>>>>>>> Stashed changes
    norms = np.linalg.norm(result, axis=-1, keepdims=True)
    invalid = norms <= epsilon
    np.divide(result, np.where(invalid, 1.0, norms), out=result)
    if np.any(invalid):
        result = np.where(
            invalid,
            np.asarray((1.0, 0.0, 0.0, 0.0), dtype=result.dtype),
            result,
        )
    return result


<<<<<<< Updated upstream
=======
def normalize_wxyz_strict(values, epsilon: float = 1e-12) -> np.ndarray:
    source = np.asarray(values, dtype=np.float64)
    norm = float(np.linalg.norm(source))
    if norm <= float(epsilon):
        raise ValueError("Quaternion magnitude is zero")
    return source / norm


>>>>>>> Stashed changes
def normalize_sequence_xyzw(values) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64).copy()
    lengths = np.linalg.norm(result, axis=-1)
    invalid = lengths <= 1e-15
    if np.any(invalid):
        result[invalid] = (0.0, 0.0, 0.0, 1.0)
        lengths = np.linalg.norm(result, axis=-1)
    result /= lengths[..., None]
    if len(result) > 1:
        dots = np.sum(result[:-1] * result[1:], axis=1)
        flips = np.cumprod(np.where(dots < 0.0, -1.0, 1.0))
        result[1:] *= flips[:, None]
    return result


<<<<<<< Updated upstream
=======
def wxyz_from_xyzw(values) -> np.ndarray:
    return np.asarray(values)[..., (3, 0, 1, 2)]


def xyzw_from_wxyz(values) -> np.ndarray:
    return np.asarray(values)[..., (1, 2, 3, 0)]


def continuous_wxyz(values) -> np.ndarray:
    """Unit wxyz quaternions, each on the hemisphere of the one before it"""
    return wxyz_from_xyzw(normalize_sequence_xyzw(xyzw_from_wxyz(values)))


def aligned_xyzw(reference, value) -> np.ndarray:
    """value on the same hemisphere as reference (negated when their dot product is negative)"""
    q = np.asarray(value, dtype=np.float64)
    return -q if float(np.dot(np.asarray(reference, dtype=np.float64), q)) < 0.0 else q


>>>>>>> Stashed changes
def nlerp_xyzw(left, right, weight) -> np.ndarray:
    left = np.asarray(left)
    right = np.asarray(right)
    dot = np.sum(left * right, axis=-1, keepdims=True)
    aligned = np.where(dot < 0.0, -right, right)
    weight = np.asarray(weight, dtype=left.dtype)
    while weight.ndim < left.ndim:
        weight = weight[..., None]
    blended = left + weight * (aligned - left)
    norms = np.linalg.norm(blended, axis=-1, keepdims=True)
    safe = np.where(norms < 1e-8, 1.0, norms)
    normalized = blended / safe
    return np.where(norms < 1e-8, left, normalized)


def slerp_xyzw(left, right, weight) -> np.ndarray:
<<<<<<< Updated upstream
    left = np.asarray(left)
    right = np.asarray(right)
    weight = np.asarray(weight, dtype=np.result_type(left.dtype, right.dtype, np.float32))
=======
    left = normalize_xyzw(left)
    right = normalize_xyzw(right)
    weight = np.asarray(
        weight, dtype=np.result_type(left.dtype, right.dtype, np.float32)
    )
>>>>>>> Stashed changes
    while weight.ndim < left.ndim:
        weight = weight[..., None]
    dot = np.sum(left * right, axis=-1, keepdims=True)
    aligned = np.where(dot < 0.0, -right, right)
    dot = np.abs(dot)
    theta = np.arccos(np.clip(dot, -1.0, 1.0))
    sin_theta = np.sin(theta)
    close = dot > 0.9995
    safe_sin = np.where(sin_theta < 1e-10, 1.0, sin_theta)
    first = np.sin((1.0 - weight) * theta) / safe_sin
    second = np.sin(weight * theta) / safe_sin
    spherical = first * left + second * aligned
    linear = (1.0 - weight) * left + weight * aligned
    linear /= np.linalg.norm(linear, axis=-1, keepdims=True) + 1e-10
<<<<<<< Updated upstream
    return np.where(close, linear, spherical)
=======
    return normalize_xyzw(np.where(close, linear, spherical))


def multiply_unit_xyzw(left, right) -> np.ndarray:
    return normalize_xyzw(multiply_xyzw(normalize_xyzw(left), normalize_xyzw(right)))


def rotate_vector_xyzw(rotation, vector) -> np.ndarray:
    quaternion = normalize_xyzw(np.asarray(rotation, dtype=np.float64))
    xyz = quaternion[..., :3]
    value = np.asarray(vector, dtype=np.float64)
    uv = np.cross(xyz, value)
    uuv = np.cross(xyz, uv)
    return value + 2.0 * (quaternion[..., 3, None] * uv + uuv)


def inverse_rotate_vector_xyzw(rotation, vector) -> np.ndarray:
    """One vector rotated by the inverse of one xyzw rotation"""
    x, y, z, w = (float(value) for value in rotation[:4])
    length = float(np.linalg.norm((x, y, z, w)))
    if length <= 1e-15:
        return np.asarray(vector, dtype=np.float64)
    qvec = np.asarray((-x / length, -y / length, -z / length), dtype=np.float64)
    scalar = w / length
    value = np.asarray(vector, dtype=np.float64)
    uv = np.cross(qvec, value)
    uuv = np.cross(qvec, uv)
    return value + 2.0 * (scalar * uv + uuv)


def shortest_rotation_xyzw(source, target, fallback_axis=None) -> np.ndarray:
    source = np.asarray(source, dtype=np.float64).copy()
    target = np.asarray(target, dtype=np.float64).copy()
    source_length = float(np.linalg.norm(source))
    target_length = float(np.linalg.norm(target))
    if source_length <= 1e-12 or target_length <= 1e-12:
        return np.asarray((0.0, 0.0, 0.0, 1.0), dtype=np.float64)
    source /= source_length
    target /= target_length
    dot = float(np.clip(np.dot(source, target), -1.0, 1.0))
    if dot >= 1.0 - 1e-10:
        return np.asarray((0.0, 0.0, 0.0, 1.0), dtype=np.float64)
    if dot <= -1.0 + 1e-10:
        if fallback_axis is None:
            basis = np.asarray((1.0, 0.0, 0.0), dtype=np.float64)
            if abs(float(np.dot(source, basis))) > 0.9:
                basis = np.asarray((0.0, 1.0, 0.0), dtype=np.float64)
            axis = np.cross(source, basis)
            length = float(np.linalg.norm(axis))
        else:
            axis = np.asarray(fallback_axis, dtype=np.float64).copy()
            axis -= source * float(np.dot(axis, source))
            length = float(np.linalg.norm(axis))
            if length <= 1e-12:
                basis = np.asarray((1.0, 0.0, 0.0), dtype=np.float64)
                if abs(float(np.dot(source, basis))) > 0.9:
                    basis = np.asarray((0.0, 1.0, 0.0), dtype=np.float64)
                axis = np.cross(source, basis)
                length = float(np.linalg.norm(axis))
        axis /= max(length, 1e-15)
        return np.asarray((axis[0], axis[1], axis[2], 0.0), dtype=np.float64)
    axis = np.cross(source, target)
    return normalize_xyzw(
        np.asarray((axis[0], axis[1], axis[2], 1.0 + dot), dtype=np.float64)
    )


def axis_angle_xyzw(axis, angle: float) -> np.ndarray:
    vector = np.asarray(axis, dtype=np.float64).copy()
    vector /= max(float(np.linalg.norm(vector)), 1e-15)
    half = 0.5 * float(angle)
    sine = math.sin(half)
    return normalize_xyzw(
        np.asarray(
            (
                vector[0] * sine,
                vector[1] * sine,
                vector[2] * sine,
                math.cos(half),
            ),
            dtype=np.float64,
        )
    )


def euler_xyz_from_xyzw(rotation) -> tuple[float, float, float]:
    x, y, z, w = normalize_xyzw(np.asarray(rotation, dtype=np.float64))
    sin_x = 2.0 * (w * x + y * z)
    cos_x = 1.0 - 2.0 * (x * x + y * y)
    pitch = math.atan2(sin_x, cos_x)
    sin_y = 2.0 * (w * y - z * x)
    roll = math.asin(float(np.clip(sin_y, -1.0, 1.0)))
    sin_z = 2.0 * (w * z + x * y)
    cos_z = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(sin_z, cos_z)
    return pitch, roll, yaw


def xyzw_from_euler_xyz(pitch: float, roll: float, yaw: float) -> np.ndarray:
    half_x = 0.5 * float(pitch)
    half_y = 0.5 * float(roll)
    half_z = 0.5 * float(yaw)
    sx, cx = math.sin(half_x), math.cos(half_x)
    sy, cy = math.sin(half_y), math.cos(half_y)
    sz, cz = math.sin(half_z), math.cos(half_z)
    return normalize_xyzw(
        np.asarray(
            (
                sx * cy * cz - cx * sy * sz,
                cx * sy * cz + sx * cy * sz,
                cx * cy * sz - sx * sy * cz,
                cx * cy * cz + sx * sy * sz,
            ),
            dtype=np.float64,
        )
    )
>>>>>>> Stashed changes


def matrix_from_xyzw(value) -> np.ndarray:
    x, y, z, w = (float(component) for component in value)
    length = math.sqrt(x * x + y * y + z * z + w * w)
    if length <= 1e-15:
        x = y = z = 0.0
        w = 1.0
    else:
        x /= length
        y /= length
        z /= length
        w /= length
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
<<<<<<< Updated upstream
    return np.array((
        (1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy), 0.0),
        (2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx), 0.0),
        (2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy), 0.0),
        (0.0, 0.0, 0.0, 1.0),
    ), dtype=np.float64)
=======
    return np.array(
        (
            (1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy), 0.0),
            (2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx), 0.0),
            (2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy), 0.0),
            (0.0, 0.0, 0.0, 1.0),
        ),
        dtype=np.float64,
    )
>>>>>>> Stashed changes


def wxyz_from_matrices(matrices) -> np.ndarray:
    matrices = np.asarray(matrices, dtype=np.float64)
    original_shape = matrices.shape[:-2]
    values = matrices.reshape(-1, 3, 3)
    result = np.empty((len(values), 4), dtype=np.float64)
    trace = values[:, 0, 0] + values[:, 1, 1] + values[:, 2, 2]
    positive = trace > 0.0
    if np.any(positive):
        root = np.sqrt(np.maximum(trace[positive] + 1.0, 0.0)) * 2.0
        root = np.maximum(root, 1e-15)
        result[positive, 0] = 0.25 * root
        result[positive, 1] = (values[positive, 2, 1] - values[positive, 1, 2]) / root
        result[positive, 2] = (values[positive, 0, 2] - values[positive, 2, 0]) / root
        result[positive, 3] = (values[positive, 1, 0] - values[positive, 0, 1]) / root
    remaining = ~positive
    diagonal = np.stack((values[:, 0, 0], values[:, 1, 1], values[:, 2, 2]), axis=1)
    dominant = np.argmax(diagonal, axis=1)
    for axis in range(3):
        mask = remaining & (dominant == axis)
        if not np.any(mask):
            continue
        matrix = values[mask]
        if axis == 0:
<<<<<<< Updated upstream
            root = np.sqrt(np.maximum(1.0 + matrix[:, 0, 0] - matrix[:, 1, 1] - matrix[:, 2, 2], 0.0)) * 2.0
=======
            root = (
                np.sqrt(
                    np.maximum(
                        1.0 + matrix[:, 0, 0] - matrix[:, 1, 1] - matrix[:, 2, 2], 0.0
                    )
                )
                * 2.0
            )
>>>>>>> Stashed changes
            root = np.maximum(root, 1e-15)
            result[mask, 0] = (matrix[:, 2, 1] - matrix[:, 1, 2]) / root
            result[mask, 1] = 0.25 * root
            result[mask, 2] = (matrix[:, 0, 1] + matrix[:, 1, 0]) / root
            result[mask, 3] = (matrix[:, 0, 2] + matrix[:, 2, 0]) / root
        elif axis == 1:
<<<<<<< Updated upstream
            root = np.sqrt(np.maximum(1.0 + matrix[:, 1, 1] - matrix[:, 0, 0] - matrix[:, 2, 2], 0.0)) * 2.0
=======
            root = (
                np.sqrt(
                    np.maximum(
                        1.0 + matrix[:, 1, 1] - matrix[:, 0, 0] - matrix[:, 2, 2], 0.0
                    )
                )
                * 2.0
            )
>>>>>>> Stashed changes
            root = np.maximum(root, 1e-15)
            result[mask, 0] = (matrix[:, 0, 2] - matrix[:, 2, 0]) / root
            result[mask, 1] = (matrix[:, 0, 1] + matrix[:, 1, 0]) / root
            result[mask, 2] = 0.25 * root
            result[mask, 3] = (matrix[:, 1, 2] + matrix[:, 2, 1]) / root
        else:
<<<<<<< Updated upstream
            root = np.sqrt(np.maximum(1.0 + matrix[:, 2, 2] - matrix[:, 0, 0] - matrix[:, 1, 1], 0.0)) * 2.0
=======
            root = (
                np.sqrt(
                    np.maximum(
                        1.0 + matrix[:, 2, 2] - matrix[:, 0, 0] - matrix[:, 1, 1], 0.0
                    )
                )
                * 2.0
            )
>>>>>>> Stashed changes
            root = np.maximum(root, 1e-15)
            result[mask, 0] = (matrix[:, 1, 0] - matrix[:, 0, 1]) / root
            result[mask, 1] = (matrix[:, 0, 2] + matrix[:, 2, 0]) / root
            result[mask, 2] = (matrix[:, 1, 2] + matrix[:, 2, 1]) / root
            result[mask, 3] = 0.25 * root
    result /= np.maximum(np.linalg.norm(result, axis=1)[:, None], 1e-15)
    return result.reshape(original_shape + (4,))


<<<<<<< Updated upstream
def xyzw_from_matrices(matrices) -> np.ndarray:
    wxyz = wxyz_from_matrices(matrices)
    xyzw = wxyz[..., (1, 2, 3, 0)]
    normalized = normalize_sequence_xyzw(xyzw.reshape(-1, 4))
    return normalized.reshape(xyzw.shape)
=======
def xyzw_from_matrices(matrices, *, continuous=True) -> np.ndarray:
    wxyz = wxyz_from_matrices(matrices)
    xyzw = xyzw_from_wxyz(wxyz)
    if not continuous:
        return xyzw
    normalized = normalize_sequence_xyzw(xyzw.reshape(-1, 4))
    return normalized.reshape(xyzw.shape)


def multiply_xyzw_into(left: np.ndarray, right: np.ndarray, out: np.ndarray) -> None:
    """Multiply XYZW arrays into output, which must not alias either input"""
    lx = left[..., 0]
    ly = left[..., 1]
    lz = left[..., 2]
    lw = left[..., 3]
    rx = right[..., 0]
    ry = right[..., 1]
    rz = right[..., 2]
    rw = right[..., 3]
    out[..., 0] = lw * rx + lx * rw + ly * rz - lz * ry
    out[..., 1] = lw * ry - lx * rz + ly * rw + lz * rx
    out[..., 2] = lw * rz + lx * ry - ly * rx + lz * rw
    out[..., 3] = lw * rw - lx * rx - ly * ry - lz * rz


def nlerp_xyzw_into(
    current: np.ndarray,
    target: np.ndarray,
    weight: float,
    output: np.ndarray,
    dot: np.ndarray,
    norm: np.ndarray,
    sign: np.ndarray,
    valid: np.ndarray,
    negative: np.ndarray,
    safe_norm: np.ndarray,
) -> None:
    np.einsum("ij,ij->i", current, target, out=dot)
    sign.fill(1.0)
    np.less(dot, 0.0, out=negative)
    np.putmask(sign, negative, -1.0)
    np.multiply(target, sign[:, None], out=output)
    np.subtract(output, current, out=output)
    output *= weight
    output += current
    np.einsum("ij,ij->i", output, output, out=norm)
    np.sqrt(norm, out=norm)
    np.greater_equal(norm, 1e-8, out=valid)
    np.copyto(safe_norm, norm)
    np.logical_not(valid, out=negative)
    np.copyto(safe_norm, 1.0, where=negative)
    output /= safe_norm[:, None]
    np.copyto(output, current, where=negative[:, None])


# Row kernels for (N, 4) quaternion and (N, 3) vector arrays: plain elementwise
# arithmetic, faster than the general helpers above for short rows.


def normalize_rows_xyzw(values: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    safe = np.where(norms <= 1e-30, 1.0, norms)
    result = values / safe
    invalid = norms[:, 0] <= 1e-30
    if np.any(invalid):
        result[invalid] = (0.0, 0.0, 0.0, 1.0)
    return result


def product_rows_xyzw(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    """Row-wise Hamilton product, not renormalized"""
    lx, ly, lz, lw = left.T
    rx, ry, rz, rw = right.T
    result = np.empty_like(left)
    result[:, 0] = lw * rx + lx * rw + ly * rz - lz * ry
    result[:, 1] = lw * ry - lx * rz + ly * rw + lz * rx
    result[:, 2] = lw * rz + lx * ry - ly * rx + lz * rw
    result[:, 3] = lw * rw - lx * rx - ly * ry - lz * rz
    return result


def multiply_rows_xyzw(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    return normalize_rows_xyzw(product_rows_xyzw(left, right))


def cross_rows(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    # Same arithmetic as np.cross without its per-call axis handling, which dominates for short rows.
    out = np.empty_like(b)
    out[:, 0] = a[:, 1] * b[:, 2] - a[:, 2] * b[:, 1]
    out[:, 1] = a[:, 2] * b[:, 0] - a[:, 0] * b[:, 2]
    out[:, 2] = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
    return out


def rotate_rows_xyzw(rotations: np.ndarray, vectors: np.ndarray) -> np.ndarray:
    xyz = rotations[:, :3]
    t = 2.0 * cross_rows(xyz, vectors)
    return vectors + rotations[:, 3:4] * t + cross_rows(xyz, t)


def xyzw_from_axis_sequence(angles_degrees, axes: str) -> np.ndarray:
    """Rotations from per-axis angles in degrees, composed in the listed order"""
    angles = np.radians(np.asarray(angles_degrees, dtype=np.float64))
    axes = axes.upper()
    if angles.shape[-1:] != (len(axes),) or set(axes) - set("XYZ"):
        raise ValueError(
            f"Axis sequence {axes!r} does not match angles of shape {angles.shape}"
        )
    result = np.zeros(angles.shape[:-1] + (4,), dtype=np.float64)
    result[..., 3] = 1.0
    for index, axis in enumerate(axes):
        factor = np.zeros_like(result)
        factor[..., "XYZ".index(axis)] = np.sin(0.5 * angles[..., index])
        factor[..., 3] = np.cos(0.5 * angles[..., index])
        result = multiply_xyzw(result, factor)
    return result


def angle_between_xyzw(left, right) -> np.ndarray:
    """Rotation angle in radians between unit quaternions"""
    dots = np.abs(
        np.sum(
            np.asarray(left, dtype=np.float64) * np.asarray(right, dtype=np.float64),
            axis=-1,
        )
    )
    return 2.0 * np.arccos(np.clip(dots, 0.0, 1.0))
>>>>>>> Stashed changes
