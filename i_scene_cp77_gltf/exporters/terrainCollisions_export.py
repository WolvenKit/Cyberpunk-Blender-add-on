import bpy
import random

import mathutils
from mathutils import Quaternion

from ..main.common import *
from ..cyber_props import *
from .physxHeightfieldWriter import PhysXWriter

resources_dir = get_resources_dir()
epsilon = 1e-4

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

    bm.transform(obj.matrix_world)

    world_min_z = min(v.z for v in verts)
    world_max_z = max(v.z for v in verts)

    node["Data"]["heightScale"] = (world_max_z - world_min_z) / 32767.0

    # account for outermost rows and columns not being fully generated
    rows = math.ceil(((max_x - min_x) / 2)) + 2
    columns = math.ceil(((max_y - min_y) / 2)) + 2

    hf = {
        "rows": rows,
        "columns": columns,
        "row_limit": rows,
        "col_limit": columns,
        "nb_columns": columns,
        "thickness": -1.0,
        "convex_edge_threshold": 0.0,
        "flags": 1,
        "format": 1,
        "min_max_bounds": {
            "min": {"x": 0.0, "y": 0.0, "z": 0.0},
            "max": {"x": rows, "y": 32767.0, "z": columns},
        },
        "sample_stride": 4,
        "nb_samples": rows * columns,
        "min_height": 0.0,
        "max_height": 32767.0,
        "samples": [],
    }

    quadQuarterStepRow = ((1 / (rows - 2)) * 0.25) * (min_y - max_y)
    quadQuarterStepCol = ((1 / (columns - 2)) * 0.25) * (max_x - min_x)

    for r in range(rows):
        for c in range(columns):
            # sample the center of each quad, but position the outermost row and column outside the UV square
            # and clamp to mesh edge to generate outermost terrain which cannot be fully built due to
            # missing triangles.
            # this avoids needing surrounding terrain tiles while being reasonably accurate
            u = (c - 0.5) / (columns - 2)
            v = (r - 0.5) / (rows - 2)

            preClampU = u
            preClampV = v

            u = min(1.0 - epsilon, max(epsilon, u))
            v = min(1.0 - epsilon, max(epsilon, v))

            heightAvg = 0
            hitT0 = False
            hitT1 = False

            world_x = min_x + u * (max_x - min_x)
            world_y = min_y + v * (max_y - min_y)

            ray_origin = Vector((world_x, world_y, max_z + 1.0))
            ray_direction = Vector((0, 0, -1))

            if (preClampU != u) or (preClampV != v):
                # only sample center for edge quads

                result, location, normal, index = obj.ray_cast(ray_origin, ray_direction)
                if result:
                    heightAvg = location.z
                    hitT0 = True
                    hitT1 = True
                else:
                    heightAvg = 0
                    hitT0 = False
                    hitT1 = False
            else:
                # sample triangle center, and quad center for inner quads
                resultCenter, locationCenter, normalCenter, indexCenter = obj.ray_cast(ray_origin, ray_direction)

                rayT0 = ray_origin.copy()
                rayT0.y += quadQuarterStepRow
                rayT0.x -= quadQuarterStepCol
                resultT0, locationT0, normalT0, indexT0 = obj.ray_cast(rayT0, ray_direction)

                rayT1 = ray_origin.copy()
                rayT1.y -= quadQuarterStepRow
                rayT1.x += quadQuarterStepCol
                resultT1, locationT1, normalT1, indexT1 = obj.ray_cast(rayT1, ray_direction)

                rayS0 = ray_origin.copy()
                rayS0.y -= quadQuarterStepRow
                rayS0.x -= quadQuarterStepCol
                resultS0, locationS0, normalS0, indexS0 = obj.ray_cast(rayS0, ray_direction)

                rayS1 = ray_origin.copy()
                rayS1.y += quadQuarterStepRow
                rayS1.x += quadQuarterStepCol
                resultS1, locationS1, normalS1, indexS1 = obj.ray_cast(rayS0, ray_direction)

                
                hits = 0
                if resultCenter:
                    heightAvg = locationCenter.z
                    hits += 1
                if resultT0:
                    heightAvg += locationT0.z
                    hits += 1
                if resultT1:
                    heightAvg += locationT1.z
                    hits += 1
                if resultS0:
                    heightAvg += locationS0.z
                    hits += 1
                if resultS1:
                    heightAvg += locationS1.z
                    hits += 1   

                if hits > 1:
                    heightAvg /= hits

                """

                hmin = min(locationCenter.z, locationT0.z, locationT1.z, locationS0.z, locationS1.z)
                hmax = max(locationCenter.z, locationT0.z, locationT1.z, locationS0.z, locationS1.z)
                hdiff = hmax - hmin
                heightAvg = hmin + hdiff * 0.8

                """

                hitT0 = resultT0
                hitT1 = resultT1

            # Normalize height to 0-1 range
            height = (heightAvg - min_z) / (max_z - min_z) if max_z != min_z else 0.5
            hf["samples"].append(
                {
                    "height": height * 32767,
                    "material_index_0": 0 if hitT0 else 127,
                    "material_index_1": 0 if hitT1 else 127,
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

    min_x = min(v.x for v in verts)
    max_x = max(v.x for v in verts)
    min_y = min(v.y for v in verts)
    max_y = max(v.y for v in verts)
    min_z = min(v.z for v in verts)
    max_z = max(v.z for v in verts)

    bm.free()

    lenX = max_x - min_x
    lenY = max_y - min_y
    lenZ = max_z - min_z

    node["Data"]["extents"]["X"] = lenX
    node["Data"]["extents"]["Y"] = lenY
    node["Data"]["extents"]["Z"] = lenZ

    nodeData["UkFloat1"] = max(lenX, lenY, lenZ) * 1.5

    # Calculate the world position of the local bottom-left corner
    # adjust for the outermost row and column being outside the terrain mesh
    local_origin = Vector((min_x, min_y, min_z)) - Vector((1, 1, 0))
    world_origin = (obj.matrix_world @ local_origin)

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
