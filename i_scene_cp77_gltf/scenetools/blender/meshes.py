from __future__ import annotations

import bpy

from ...blender.transactions import track_created_datablock


def cube_mesh(name):
    mesh = track_created_datablock("meshes", bpy.data.meshes.new(name))
    vertices = (
        (-1.0, -1.0, -1.0),
        (1.0, -1.0, -1.0),
        (1.0, 1.0, -1.0),
        (-1.0, 1.0, -1.0),
        (-1.0, -1.0, 1.0),
        (1.0, -1.0, 1.0),
        (1.0, 1.0, 1.0),
        (-1.0, 1.0, 1.0),
    )
    # Faces point out: Cycles takes a ray meeting a face's front as entering the volume.
    faces = (
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (4, 7, 3, 0),
    )
    mesh.from_pydata(vertices, (), faces)
    mesh.update()
    return mesh
