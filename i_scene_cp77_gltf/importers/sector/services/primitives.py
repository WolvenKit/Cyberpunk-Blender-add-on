from __future__ import annotations
from ....blender.transactions import track_created_datablock

import bpy


_BOX_FACES = (
    (0, 3, 2, 1),
    (4, 5, 6, 7),
    (0, 1, 5, 4),
    (1, 2, 6, 5),
    (2, 3, 7, 6),
    (3, 0, 4, 7),
)


class PrimitiveMeshService:
    def __init__(self, session):
        self.cache = session.caches.primitive_meshes

    @staticmethod
    def _box_vertices(minimum, maximum):
        x0, y0, z0 = (float(value) for value in minimum)
        x1, y1, z1 = (float(value) for value in maximum)
        return (
            (x0, y0, z0),
            (x1, y0, z0),
            (x1, y1, z0),
            (x0, y1, z0),
            (x0, y0, z1),
            (x1, y0, z1),
            (x1, y1, z1),
            (x0, y1, z1),
        )

    def box(self, name, minimum, maximum, *, shared=True):
        minimum = tuple(float(value) for value in minimum)
        maximum = tuple(float(value) for value in maximum)
        key = ("box", minimum, maximum)
        if shared:
            cached = self.cache.get(key)
            if cached is not None:
                return cached

        mesh = track_created_datablock("meshes", bpy.data.meshes.new(name))
        mesh.from_pydata(
            self._box_vertices(minimum, maximum),
            [],
            _BOX_FACES,
        )
        mesh.update()
        if shared:
            self.cache[key] = mesh
        return mesh

    def centered_box(self, name, extents, *, shared=True):
        extents = tuple(float(value) for value in extents)
        return self.box(
            name,
            tuple(-value for value in extents),
            extents,
            shared=shared,
        )

    def unit_box(self, name, half_extent=1.0, *, shared=True):
        extent = float(half_extent)
        return self.centered_box(
            name,
            (extent, extent, extent),
            shared=shared,
        )
