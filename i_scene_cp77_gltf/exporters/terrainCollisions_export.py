import json
import glob
import os
from operator import indexOf

import bpy
import copy
from ..main.common import *
from mathutils import Vector, Matrix, Quaternion
from os.path import join
from ..cyber_props import *
import random

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

def generate_terrain_collisions(obj):
    nodeData = getBaseNodeData()
    node = getBaseNode()

    nodeData['Id'] = random.randint(0, 65535)

    return nodeData, node

def export_selected_terrain(filePath):
    ctx = bpy.context

    print(filePath)
    print(len(ctx.selected_objects))

    sector = getBaseSector()
    i = 0
    for obj in ctx.selected_objects:
        if obj.type != 'MESH': continue
        print(obj.name)
        nodeData, node = generate_terrain_collisions(obj)
        nodeData['NodeIndex'] = i
        sector['Data']['RootChunk']['nodeData']['Data'] += [nodeData]
        sector['Data']['RootChunk']['nodes'] += [node]

        i += 1

    with open(filePath, 'w') as f:
        json.dump(sector, f, indent=4)

    show_message(f"{len(sector['Data']['RootChunk']['nodes'])} Terrain Collisions exported to: {filePath}")
