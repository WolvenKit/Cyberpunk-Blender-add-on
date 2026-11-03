import bmesh
from mathutils import Vector


def is_mesh(value):
    return value is not None and getattr(value, "type", None) == "MESH"


def uv_by_bounds(objects):
    mesh_objects = [obj for obj in objects if is_mesh(obj)]
    if not mesh_objects:
        return 0

    minimum = Vector((float("inf"), float("inf"), float("inf")))
    maximum = Vector((float("-inf"), float("-inf"), float("-inf")))
    for obj in mesh_objects:
        matrix = obj.matrix_world
        for vertex in obj.data.vertices:
            position = matrix @ vertex.co
            for axis in range(3):
                minimum[axis] = min(minimum[axis], position[axis])
                maximum[axis] = max(maximum[axis], position[axis])

    extent_x = maximum.x - minimum.x
    extent_y = maximum.y - minimum.y
    if abs(extent_x) <= 1e-12 or abs(extent_y) <= 1e-12:
        return 0

    updated = 0
    for obj in mesh_objects:
        mesh = obj.data
        if mesh.uv_layers:
            continue
        bm = bmesh.new()
        try:
            bm.from_mesh(mesh)
            uv_layer = bm.loops.layers.uv.verify()
            for face in bm.faces:
                for loop in face.loops:
                    uv = loop[uv_layer].uv
                    uv.x = (loop.vert.co.x - minimum.x) / extent_x
                    uv.y = (loop.vert.co.y - minimum.y) / extent_y
            bm.to_mesh(mesh)
            mesh.update()
            updated += 1
        finally:
            bm.free()
    return updated
