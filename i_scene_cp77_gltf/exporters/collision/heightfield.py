import copy
import functools
import os

from mathutils import Matrix, Vector

from ...assetio.atomic import atomic_write_json
from ...assetio.documents import load_json_payload
from ...assetio.json_style import JsonStyle
from ...assetio.physx_heightfield import heightfield_grid
from ...assetio.resources import get_resources_dir
from ...assetio.streaming_sector import node_instance_entry, streaming_sector_document
from ...assetio.transform_values import world_transform_entry
from ...assetio.values import coerce_int, json_array
from ...blender.matrix import object_world_matrix
from ..sector.transforms import transform_values

# The streaming distance of each of the twelve terrain collision entries of the 121 game sectors, which a heightfield
# cooked here, with no entry of its own to copy it from, takes.
TERRAIN_STREAMING_DISTANCE = 443.404999
# A cook scales a tile so that its highest sample is the top of the signed 16-bit range.
_HIGHEST_SAMPLE = 32767
_IMPORTED_KIND = "WORLD_HEIGHTFIELD"
_SCALE_TOLERANCE = 1.0e-4


@functools.cache
def _node_template():
    return load_json_payload(
        os.path.join(get_resources_dir(), "base.worldTerrainCollisionNode.json")
    )


def _source_materials(shape):
    values = json_array(getattr(shape, "heightfield_materials_json", "") or "")
    if values:
        return values
    value = str(
        getattr(shape, "physics_material_source", "")
        or shape.physics_material
        or "Default"
    )
    storage = str(getattr(shape, "physics_material_storage", "string") or "string")
    if storage == "uint64" and not value.isdigit():
        storage = "string"
    return [{"$type": "CName", "$storage": storage, "$value": value}]


def _source_material_indices(shape):
    """The material index of each sample the shape recorded on import"""
    recorded = json_array(getattr(shape, "heightfield_material_indices_json", "") or "")
    indices = [coerce_int(value, -1) for value in recorded]
    return indices if indices and min(indices) >= 0 else [0] * 16


def _geometry_holds_scale(obj):
    """Whether the heightfield cooked into the shapes of obj already has the object's scale in it"""
    return obj.type == "MESH" and obj.physx.source_kind != _IMPORTED_KIND


def _shape_world_matrix(obj, shape):
    """The world matrix of shape, a rigid one"""
    world = object_world_matrix(obj)
    if _geometry_holds_scale(obj):
        undo = Vector(tuple(1.0 / value if value else 1.0 for value in obj.scale))
        world = world @ Matrix.Diagonal(undo).to_4x4()
    if any(abs(value - 1.0) > _SCALE_TOLERANCE for value in world.to_scale()):
        raise ValueError(
            f"{obj.name} is scaled; heightfield collisions cannot be scaled, apply or clear its scale."
        )
    return world @ (
        Matrix.Translation(Vector(shape.local_pos))
        @ shape.local_rot.to_matrix().to_4x4()
    )


def cooked_heightfield_shapes(obj):
    """The cooked heightfield shapes of obj"""
    physx = getattr(obj, "physx", None)
    for shape in physx.shapes if physx is not None else ():
        if shape.shape_type == "HEIGHTFIELD" and shape.is_cooked and shape.cooked_data:
            yield shape


def terrain_collision_node(obj, shape):
    """The worldTerrainCollisionNode of the cooked heightfield shape of obj and its entry's matrix"""
    try:
        rows, columns = heightfield_grid(shape.cooked_data)
    except ValueError as error:
        raise ValueError(f"{obj.name}: {error}; cook it again.") from error
    node = copy.deepcopy(_node_template())
    data = node["Data"]
    data["debugName"]["$value"] = shape.name or obj.name
    data["heightfieldGeometry"]["Bytes"] = shape.cooked_data
    data["heightScale"] = float(shape.heightfield_height_scale)
    data["rowScale"] = float(shape.heightfield_row_scale)
    data["columnScale"] = float(shape.heightfield_column_scale)
    extents = data["extents"]
    extents["X"], extents["Y"], extents["Z"] = (
        float(value) for value in shape.heightfield_extents
    )
    data["materials"] = _source_materials(shape)
    data["materialIndices"] = _source_material_indices(shape)
    data["sourcePrefabHash"] = str(shape.heightfield_source_prefab_hash or "0")

    location, rotation, _scale = _shape_world_matrix(obj, shape).decompose()
    data["actorTransform"] = world_transform_entry(
        location, (rotation.x, rotation.y, rotation.z, rotation.w)
    )
    middle = Vector(
        (
            rows * data["rowScale"] / 2.0,
            _HIGHEST_SAMPLE / 2.0 * data["heightScale"],
            columns * data["columnScale"] / 2.0,
        )
    )
    return node, Matrix.Translation(location + rotation @ middle)


def export_selected_heightfields(context, filepath):
    records = [
        (obj, shape)
        for obj in context.selected_objects
        for shape in cooked_heightfield_shapes(obj)
    ]
    if not records:
        raise ValueError("No selected canonical PhysX HEIGHTFIELD shapes are cooked")

    if not filepath.lower().endswith(".streamingsector.json"):
        filepath += ".streamingsector.json"
    nodes, entries = [], []
    for index, (obj, shape) in enumerate(records):
        node, matrix = terrain_collision_node(obj, shape)
        nodes.append(node)
        entries.append(
            node_instance_entry(
                index,
                transform_values(matrix),
                streaming_distance=TERRAIN_STREAMING_DISTANCE,
            )
        )
    sector = streaming_sector_document(
        nodes,
        entries,
        category="Exterior",
        archive_file_name=os.path.basename(filepath),
    )
    atomic_write_json(filepath, sector, style=JsonStyle())
    return len(records), filepath
