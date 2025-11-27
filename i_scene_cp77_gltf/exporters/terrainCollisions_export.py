import bpy
import random

from mathutils import Quaternion

from ..main.common import *
from ..cyber_props import *
from .physxHeightfieldWriter import PhysXWriter

resources_dir = get_resources_dir()

def getBaseSector():
    with open(os.path.join(get_resources_dir(), 'empty.streamingsector.json'), 'r') as f:
        return json.load(f)

def getBaseNodeData():
    with open(os.path.join(get_resources_dir(), 'base.nodeData.json'), 'r') as f:
        return json.load(f)

def getBaseNode():
    with open(os.path.join(get_resources_dir(), 'base.worldTerrainCollisionNode.json'), 'r') as f:
        return json.load(f)

def generate_terrain_collision(obj, node):

    rows = 72
    columns = 72

    hf = {
        "rows": rows,
        "columns": columns,
        "row_limit": rows - 2.0,
        "col_limit": columns - 2.0,
        "nb_columns": columns,
        "thickness": -1.0,
        "convex_edge_threshold": 0.0,
        "flags": 1,
        "format": 1,
        "min_max_bounds": {
            "min": {"x": 0.0, "y": 0.0, "z": 0.0},
            "max": {"x": rows - 1, "y": 32767.0, "z": columns - 1},
        },
        "sample_stride": 4,
        "nb_samples": rows * columns,
        "min_height": 0.0,
        "max_height": 32767.0,
        "samples": [],
    }

    bm = bmesh.new()
    bm.from_mesh(obj.data)

    verts = [v.co for v in bm.verts]

    if len(verts) == 0:
        show_message(f"Error: Mesh {obj.name} has no vertices")
        bm.free()
        return None, None

    min_x = min(v.x for v in verts)
    max_x = max(v.x for v in verts)
    min_y = min(v.y for v in verts)
    max_y = max(v.y for v in verts)
    min_z = min(v.z for v in verts)
    max_z = max(v.z for v in verts)

    for r in range(rows):
        for c in range(columns):
            u = r / rows
            v = c / columns

            world_x = min_x + u * (max_x - min_x)
            world_y = min_y + v * (max_y - min_y)

            ray_origin = Vector((world_x, world_y, max_z + 1.0))
            ray_direction = Vector((0, 0, -1))

            result, location, normal, index = obj.ray_cast(ray_origin, ray_direction)

            if result:
                # Normalize height to 0-1 range
                height = (location.z - min_z) / (max_z - min_z) if max_z != min_z else 0.5
                hf["samples"].append(
                    {
                        "height": height * 32767,
                        "material_index_0": 0,
                        "material_index_1": 0,
                    }
                )
            else:
                # will need to double check if this is the correct index for holes
                hf["samples"].append(
                    {
                        "height": 0,
                        "material_index_0": 65535,
                        "material_index_1": 65535,
                    }
                )

    bm.free()

    node["Data"]["heightfieldGeometry"]["Bytes"] =  PhysXWriter.write(hf)
    return None


def set_transforms(obj, nodeData, node):
    bm = bmesh.new()
    bm.from_mesh(obj.data)

    verts = [v.co for v in bm.verts]

    if len(verts) == 0:
        show_message(f"Error: Mesh {obj.name} has no vertices")
        bm.free()
        return None, None

    local_min_x = min(v.x for v in verts)
    local_min_y = min(v.y for v in verts)
    local_min_z = min(v.z for v in verts)

    bm.transform(obj.matrix_world)

    world_min_z = min(v.z for v in verts)
    world_max_z = max(v.z for v in verts)

    node["Data"]["heightScale"] = (world_max_z - world_min_z) / 32767.0

    # Calculate the world position of the local bottom-left corner
    local_origin = Vector((local_min_x, local_min_y, local_min_z))
    world_origin = obj.matrix_world @ local_origin

    nodeData["Position"]["X"] = world_origin.x
    nodeData["Position"]["Y"] = world_origin.y
    nodeData["Position"]["Z"] = world_origin.z
    nodeData["Position"]["W"] = 1

    nodeData["Bounds"]["Max"]["X"] = world_origin.x
    nodeData["Bounds"]["Max"]["Y"] = world_origin.y
    nodeData["Bounds"]["Max"]["Z"] = world_origin.z
    nodeData["Bounds"]["Max"]["W"] = 1

    nodeData["Bounds"]["Min"]["X"] = world_origin.x
    nodeData["Bounds"]["Min"]["Y"] = world_origin.y
    nodeData["Bounds"]["Min"]["Z"] = world_origin.z
    nodeData["Bounds"]["Min"]["W"] = 1

    node["Data"]["actorTransform"]["Position"]["x"]["Bits"] = world_origin.x * 131072
    node["Data"]["actorTransform"]["Position"]["y"]["Bits"] = world_origin.y * 131072
    node["Data"]["actorTransform"]["Position"]["z"]["Bits"] = world_origin.z * 131072

    # the base rotation of the terrain collision is 90 90 0
    rot = obj.matrix_world.to_quaternion() @ Quaternion((0.5, 0.5, 0.5, 0.5))
    node["Data"]["actorTransform"]["Orientation"]["i"] = rot.x
    node["Data"]["actorTransform"]["Orientation"]["j"] = rot.y
    node["Data"]["actorTransform"]["Orientation"]["k"] = rot.z
    node["Data"]["actorTransform"]["Orientation"]["r"] = rot.w

    return None

def generate_sector_node(obj):
    nodeData = getBaseNodeData()
    node = getBaseNode()
    nodeData["Id"] = random.randint(0, 65535)
    node["Data"]["debugName"]["$value"] = obj.name

    generate_terrain_collision(obj, node)
    set_transforms(obj, nodeData, node)

    return nodeData, node

def export_selected_terrain(filePath):
    ctx = bpy.context

    print(filePath)
    print(len(ctx.selected_objects))

    sector = getBaseSector()
    i = 0
    for obj in ctx.selected_objects:
        if obj.type != 'MESH': continue
        nodeData, node = generate_sector_node(obj)
        if not nodeData or not node: continue
        nodeData['NodeIndex'] = i
        sector['Data']['RootChunk']['nodeData']['Data'] += [nodeData]
        sector['Data']['RootChunk']['nodes'] += [node]

        i += 1
    if not filePath.endswith('.streamingsector.json'):
        filePath += '.streamingsector.json'

    with open(filePath, 'w') as f:
        json.dump(sector, f, indent=4)

    show_message(f"{len(sector['Data']['RootChunk']['nodes'])} Terrain Collisions exported to: {filePath}")
