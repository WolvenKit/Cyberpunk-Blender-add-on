import json

import bpy

try:
    from ...core.log import get_logger
except ImportError:
    import logging

    def get_logger(name):
        return logging.getLogger(f"i_scene_cp77_gltf.user_scripts.{name}")


_LOG = get_logger(__name__)


json_file_path = "m://lattice_setup.json"  # Replace with the actual file path
try:
    with open(json_file_path, "r") as file:
        data = json.load(file)
except FileNotFoundError:
    _LOG.warning("JSON file not found at: %s", json_file_path, exc_info=True)
    data = None

if data:
    control_points = data.get("deformed_control_points", [])

    bpy.ops.object.add(type="LATTICE", enter_editmode=False, location=(0, 0, 0))
    new_lattice = bpy.context.object
    new_lattice.name = data.get("lattice_object_name", "NewLattice")
    lattice = new_lattice.data

    lattice.points_u = 31
    lattice.points_v = 31
    lattice.points_w = 31
    new_lattice.location[0] = data["lattice_object_location"][0]
    new_lattice.location[1] = data["lattice_object_location"][1]
    new_lattice.location[2] = data["lattice_object_location"][2]

    new_lattice.rotation_euler = (
        data["lattice_object_rotation"][0],
        data["lattice_object_rotation"][1],
        data["lattice_object_rotation"][2],
    )

    new_lattice.scale[0] = data["lattice_object_scale"][0]
    new_lattice.scale[1] = data["lattice_object_scale"][1]
    new_lattice.scale[2] = data["lattice_object_scale"][2]

    lattice.interpolation_type_u = data.get("lattice_interpolation_u", "KEY_BSPLINE")
    lattice.interpolation_type_v = data.get("lattice_interpolation_v", "KEY_BSPLINE")
    lattice.interpolation_type_w = data.get("lattice_interpolation_w", "KEY_BSPLINE")

    lattice_points = lattice.points
    flat_lattice_points = [
        lattice_points[
            w + v * lattice.points_u + u * lattice.points_u * lattice.points_v
        ]
        for u in range(lattice.points_u)
        for v in range(lattice.points_v)
        for w in range(lattice.points_w)
    ]

    for control_point, lattice_point in zip(control_points, flat_lattice_points):
        lattice_point.co_deform = control_point
