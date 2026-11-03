from __future__ import annotations


def submit_triangle_collision(bridge, cloth_handle, vertices, indices, pose=None):
    collision_pose = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0] if pose is None else list(pose)
    if len(collision_pose) != 7:
        raise ValueError("triangle collision pose must contain exactly 7 values")
    bridge.nvcloth_set_triangles(
        int(cloth_handle),
        list(vertices),
        list(indices),
        collision_pose,
    )
