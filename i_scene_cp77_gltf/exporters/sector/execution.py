# Script to export CP2077 streaming sectors from Blender
# Just does changes to existing bits so far
# By Simarilius Jan 2023
# last updated 17/4/24
# latest version in the plugin from https://github.com/WolvenKit/Cyberpunk-Blender-add-on
#
#  __       __   ___  __   __  .  . .  . .   .       __   ___  __  ___  __   __      ___  __  . ___ . .  .  __
# /  ` \ / |__) |__  |__) |__) |  | |\ | |__/       /__` |__  /  `  |  /  \ |__)    |__  |  \ |  |  | |\ | / _`
# \__,  |  |__) |___ |  \ |    \__/ | \| |  \       .__/ |___ \__,  |  \__/ |  \    |___ |__/ |  |  | | \| \__/
#
# Havent written a tutorial for this yet so thought I should add some instructions
# 1) Import the sector you want to edit using the Cyberpunk blender plugin (link above).
# 2) You can move the existing objects around and this will be exported
# 3) If you delete the mesh from a collector but leave the collector, the script will delete it with archivexl the file to do this is written to \source\resources
# 4) to add new stuff create a new collector with the sector name with _new on the end ie interior_1_1_0_1.streamingsector_new and then copy any objects you want into it.
#    You need to copy the collector and the meshes for the nodes you want to copy, not just the meshes, the tags that make it work are on the collectors.
# 5) If its stuff already in the sector it will create nodeData nodes to instance it, if its from another imported sector it will copy the main node too
#    Its assuming it can find the json for the sector its copying from in the project, dont be clever merging blends or whatever.
# 6) not all nodetypes are supported yet, have a look at the case statements to see which are
#
# Ask in world-editing on the discord (https://discord.gg/redmodding) if you have any trouble

# TODO
# - Fix the entities - done
# - Add collisions - can delete
# - sort out instanced bits

import copy
import glob
import json
import os

import bpy

from mathutils import Matrix

from ...paths import get_resources_dir
from ..common.atomic import atomic_write_many
from .buffers import (
    HandleAllocator,
    SectorSceneIndex,
    SharedTransformBufferRegistry,
    remap_owned_handles,
)
from .repository import SectorSourceRepository
from .serializers.archive_xl import build_archive_xl, serialize_archive_xl
from .transforms import get_rot, set_pos, set_rot, set_scale


def are_matrices_equal(mat1, mat2, tolerance=0.01):
    if len(mat1) != len(mat2):
        return False

    for i in range(len(mat1)):
        for j in range(len(mat1[i])):
            if abs(mat1[i][j] - mat2[i][j]) > tolerance:
                return False

    return True


C = bpy.context




# function to recursively count nested collections
def countChildNodes(collection):
    if 'expectedNodes' in collection:
        numChildNodes = collection['expectedNodes']
        return numChildNodes




def checkexists(meshname, Masters):
    groupname = os.path.splitext(os.path.split(meshname)[-1])[0]
    if groupname in Masters.children.keys() and len(Masters.children[groupname].objects) > 0:
        return True
    else:
        return False


def createNodeData(t, col, nodeIndex, obj, ID):
    print(ID)
    t.append(
            {'Id': ID, 'Uk10': 1088, 'Uk11': 256, 'Uk12': 0, 'UkFloat1': 60.47757,
             'UkHash1': {"$type": "NodeRef", "$storage": "uint64", "$value": "0"},
             'QuestPrefabRefHash': {"$type": "NodeRef", "$storage": "uint64", "$value": "0"},
             'MaxStreamingDistance': 3.4028235e+38}
            )
    new = t[len(t) - 1]
    new['NodeIndex'] = nodeIndex
    new['Position'] = {'$type': 'Vector4', 'W': 0, 'X': float("{:.9g}".format(obj.location[0])),
                       'Y': float("{:.9g}".format(obj.location[1])), 'Z': float("{:.9g}".format(obj.location[2]))}
    new['Orientation'] = {'$type': 'Quaternion', 'r': float("{:.9g}".format(obj.rotation_quaternion[0])),
                          'i': float("{:.9g}".format(obj.rotation_quaternion[1])),
                          'j': float("{:.9g}".format(obj.rotation_quaternion[2])),
                          'k': float("{:.9g}".format(obj.rotation_quaternion[3]))}
    new['Scale'] = {'$type': 'Vector3', 'X': float("{:.9g}".format(obj.scale[0])),
                    'Y': float("{:.9g}".format(obj.scale[1])), 'Z': float("{:.9g}".format(obj.scale[2]))}
    new['Pivot'] = {'$type': 'Vector3', 'X': 0, 'Y': 0, 'Z': 0}
    new['Bounds'] = {'$type': 'Box'}
    new['Bounds']['Max'] = {'$type': 'Vector4', 'X': float("{:.9g}".format(obj.location[0])),
                            'Y': float("{:.9g}".format(obj.location[1])), 'Z': float("{:.9g}".format(obj.location[2]))}
    new['Bounds']['Min'] = {'$type': 'Vector4', 'X': float("{:.9g}".format(obj.location[0])),
                            'Y': float("{:.9g}".format(obj.location[1])), 'Z': float("{:.9g}".format(obj.location[2]))}


def create_static_from_WIMN(node, template_nodes, handle_allocator):
    new_ni = len(template_nodes)
    WSMN = {
        "Data": {
            "$type": "worldStaticMeshNode",
            "castLocalShadows": "Always",
            "castRayTracedGlobalShadows": "Always",
            "castRayTracedLocalShadows": "Always",
            "castShadows": "Always",
            "debugName": {
                "$type": "CName",
                "$storage": "string",
                "$value": node['Data']['debugName']['$value']
                },
            "isHostOnly": node['Data']['isHostOnly'],
            "isVisibleInGame": node['Data']['isVisibleInGame'],
            "mesh": {
                "DepotPath": {
                    "$type": "ResourcePath",
                    "$storage": "string",
                    "$value": node['Data']['mesh']['DepotPath']['$value']
                    },
                "Flags": "Soft"
                },
            "meshAppearance": {
                "$type": "CName",
                "$storage": "string",
                "$value": node['Data']['meshAppearance']['$value']
                },
            "occluderAutohideDistanceScale": node['Data']['occluderAutohideDistanceScale'],
            "occluderType": node['Data']['occluderType'],
            "proxyScale": node['Data']['proxyScale'],

            "sourcePrefabHash": node['Data']['sourcePrefabHash'],
            "tag": node['Data']['tag'],
            "tagExt": node['Data']['tagExt'],
            "version": node['Data']['version'],

            }
        }
    WSMN["HandleId"] = handle_allocator.allocate()
    template_nodes.append(WSMN)


def export_sectors(filename, use_yaml):
    # Set this to your project directory
    # filename= '/Volumes/Ruby/archivexlconvert/archivexlconvert.cdproj'
    # project = '/Volumes/Ruby/archivexlconvert/'
    project = os.path.dirname(filename)
    if not os.path.exists(project):
        raise FileNotFoundError(f"Project path does not exist: {project}")
    projpath = os.path.join(project, 'source', 'raw')
    print('exporting sectors from ', projpath)
    # its currently set to output the modified jsons to an output folder in the project dir (create one before running)
    # you can change this to a path if you prefer
    xloutpath = os.path.join(project, 'source', 'resources')
    escaped_path = glob.escape(projpath)
    jsons = glob.glob(os.path.join(escaped_path, "**", "*.streamingsector.json"), recursive=True)

    projpath = os.path.join(project, 'source', 'raw', 'base')
    if len(jsons) < 1:
        raise FileNotFoundError(
            f"No source streaming sector JSON files found below {project}"
        )

    Masters = bpy.data.collections.get("MasterInstances")

    # Open the blank template streaming sector
    resourcepath = get_resources_dir()
    with open(os.path.join(resourcepath, 'empty.streamingsector.json'), 'r') as f:
        template_json = json.load(f)

    template_nodes = template_json["Data"]["RootChunk"]["nodes"]
    template_nodeData = template_json['Data']['RootChunk']['nodeData']['Data']
    template_handle_allocator = HandleAllocator(template_json)
    template_transform_buffers = SharedTransformBufferRegistry(
        template_nodes,
        allocator=template_handle_allocator,
    )
    ID = max(
        (int(item.get("Id", 0)) for item in template_nodeData),
        default=665,
    ) + 1

    # If anythings tagged from last time you exported, clear it
    for col in bpy.data.collections:
        col['exported'] = False

    for obj in bpy.data.objects:
        if 'exported' in obj.keys():
            obj['exported'] = False
    coll_scene = bpy.context.scene.collection
    impacts = None
    impact_mats = []
    source_repository = SectorSourceRepository()
    # .  .  __ .    .. .  .  __      __  ___ .  .  ___  ___
    # |\/| /  \ \  / | |\ | / _`    /__`  |  |  | |__  |__
    # |  | \__/  \/  | | \| \__/    .__/  |  \__/ |    |
    #
    deletions = {}
    deletions['Decals'] = {}
    deletions['Collisions'] = {}
    expectedNodes = {}
    for filepath in jsons:
        projectjson = os.path.join(projpath, os.path.splitext(os.path.basename(filename))[0] + '.streamingsector.json')
        print(projectjson)
        print(filepath)
        if os.path.normcase(os.path.realpath(filepath)) == os.path.normcase(
            os.path.realpath(projectjson)
        ):
            continue
        j = copy.deepcopy(source_repository.load(filepath))
        nodes = j["Data"]["RootChunk"]["nodes"]
        t = j['Data']['RootChunk']['nodeData']['Data']
        # add nodeDataIndex props to all the nodes in t
        node_data_by_node = {}
        for index, obj in enumerate(t):
            obj['nodeDataIndex'] = index
            node_data_by_node.setdefault(int(obj['NodeIndex']), []).append(
                (obj, index)
            )

        sectorName = os.path.basename(filepath)[:-5]
        deletions[sectorName] = []
        deletions['Decals'][sectorName] = []
        deletions['Collisions'][sectorName] = {}
        if sectorName not in bpy.data.collections.keys():
            continue
        print('Updating sector ', sectorName)
        Sector_coll = bpy.data.collections.get(sectorName)
        scene_index = SectorSceneIndex(Sector_coll)
        expectedNodes[sectorName] = countChildNodes(Sector_coll)
        if 'filepath' not in Sector_coll.keys():
            Sector_coll['filepath'] = filepath
        # print(filepath)
        # print(len(nodes))
        Sector_additions_coll = bpy.data.collections.get(sectorName + '_new')
        sector_Collisions = sectorName + '_colls'
        wIMNs = 0
        for i, e in enumerate(nodes):
            data = e['Data']
            type = data['$type']
            match type:
                case 'worldInstancedMeshNode':
                    wIMNs += 1
                    # print(wIMNs)
                    meshname = data['mesh']['DepotPath']['$value'].replace('\\', os.sep)
                    # if 'chopstick' in meshname:
                    #    print('worldInstancedMeshNode - ',meshname)
                    if not checkexists(meshname, Masters):
                        print(meshname, ' not found in masters')
                        continue

                    instances = node_data_by_node.get(i, ())
                    for Nidx, (inst, instNDidx) in enumerate(instances):
                        num = data['worldTransformsBuffer']['numElements']
                        start = data['worldTransformsBuffer']['startIndex']
                        if (meshname != 0):
                            for idx in range(start, start + num):
                                # find the top level instance collector
                                obj_col = scene_index.collection(i, idx)
                                if obj_col:
                                    # elements are in collectors inside the top one, not just objects
                                    if len(obj_col.children) > 0 and len(obj_col.children[0].objects) > 0:
                                        obj = obj_col.children[0].objects[0]
                                        # Check for Position and if changed delete the original and add to the new sector
                                        if obj.matrix_world != Matrix(obj_col['matrix']):
                                            deletions[sectorName].append(obj_col)
                                            # working with instancedmesh nodes is a pain in the ass, so convert to static

                                            create_static_from_WIMN(
                                                e,
                                                template_nodes,
                                                template_handle_allocator,
                                            )
                                            new_ni = len(template_nodes) - 1
                                            for child in obj_col.children:
                                                if len(child.objects) > 0:
                                                    # might need to convert instanced to static here, not sure what the best approach is.
                                                    createNodeData(
                                                        template_nodeData, child, new_ni, child.objects[0], ID
                                                        )
                                                    ID += 1
                                    else:
                                        # empty collector, so just delete
                                        if obj_col:
                                            deletions[sectorName].append(obj_col)

                case 'worldStaticDecalNode':
                    # print('worldStaticDecalNode')
                    instances = node_data_by_node.get(i, ())
                    for idx, (inst, instNid) in enumerate(instances):
                        obj = scene_index.decal(i, idx)
                        if obj:
                            # Check for Position and if changed delete the original and add to the new sector
                            if obj.matrix_world != Matrix(obj['matrix']):
                                deletions['Decals'][sectorName].append(
                                        {'nodeIndex': instNid, 'NodeComment': obj.name, 'NodeType': obj['nodeType']}
                                        )
                                new_ni = len(template_nodes)
                                template_nodes.append(copy.deepcopy(nodes[obj['nodeIndex']]))
                                createNodeData(template_nodeData, Sector_coll, new_ni, obj, ID)
                                ID += 1
                        else:
                            deletions['Decals'][sectorName].append(
                                    {'nodeIndex': instNid,
                                     'NodeComment': 'DELETED Decal nid:' + str(inst['NodeIndex']) + ' ndid:' + str(
                                         instNid
                                         ), 'NodeType': 'worldStaticDecalNode'}
                                    )

                case 'worldStaticMeshNode' | 'worldBuildingProxyMeshNode' | 'worldGenericProxyMeshNode' | 'worldTerrainProxyMeshNode':
                    if isinstance(e, dict) and 'mesh' in data.keys():
                        meshname = data['mesh']['DepotPath']['$value'].replace('\\', os.sep)
                        # print('Mesh name is - ',meshname, e['HandleId'])
                        if (meshname != 0):
                            instances = [
                                entry for entry, _ in node_data_by_node.get(i, ())
                            ]
                            for idx, inst in enumerate(instances):
                                obj_col = scene_index.collection(i, idx)
                                # print(obj_col)
                                if obj_col:
                                    if len(obj_col.objects) > 0:
                                        obj = obj_col.objects[0]
                                        # Check for Position and if changed delete the original and add to the new sector
                                        if obj.matrix_world != Matrix(obj_col['matrix']):
                                            deletions[sectorName].append(obj_col)
                                            new_ni = len(template_nodes)
                                            template_nodes.append(copy.deepcopy(nodes[obj_col['nodeIndex']]))

                                            createNodeData(template_nodeData, obj_col, new_ni, obj, ID)
                                            ID += 1
                                    else:
                                        if obj_col:
                                            deletions[sectorName].append(obj_col)

                case 'worldEntityNode':
                    if isinstance(e, dict) and 'entityTemplate' in data.keys():
                        entname = data['entityTemplate']['DepotPath']['$value'].replace('\\', os.sep)

                        if (entname != 0):
                            instances = [
                                entry for entry, _ in node_data_by_node.get(i, ())
                            ]
                            for idx, inst in enumerate(instances):
                                obj_col = scene_index.collection(i, idx)
                                # print(obj_col)
                                # THIS WAS WRONG, the entity meshes are in child collectors not objects so children>0 and children.objects>0
                                if obj_col and len(obj_col.children) > 0:
                                    if len(obj_col.children[0].objects) > 0:
                                        obj = obj_col.children[0].objects[0]
                                        # Check for Position and if changed delete the original and add to the new sector
                                        if obj.matrix_world != Matrix(obj_col['matrix']):
                                            deletions[sectorName].append(obj_col)
                                            new_ni = len(template_nodes)
                                            template_nodes.append(copy.deepcopy(nodes[obj_col['nodeIndex']]))

                                            createNodeData(template_nodeData, obj_col, new_ni, obj, ID)
                                            ID += 1

                                else:
                                    if obj_col:
                                        deletions[sectorName].append(obj_col)

                case 'worldInstancedDestructibleMeshNode':
                    # print('worldInstancedDestructibleMeshNode',i)
                    if isinstance(e, dict) and 'mesh' in data.keys():
                        meshname = data['mesh']['DepotPath']['$value'].replace('\\', os.sep)
                        num = data['cookedInstanceTransforms']['numElements']
                        start = data['cookedInstanceTransforms']['startIndex']
                        instances = [
                            entry for entry, _ in node_data_by_node.get(i, ())
                        ]
                        # need to go through the instances (tlidx - top level index) and then the elements (just idx)
                        new_WIDM_static = None
                        for tlidx, inst in enumerate(instances):
                            for idx in range(start, start + num):

                                obj_col = scene_index.world_instance(i, tlidx, idx)

                                if obj_col:
                                    # elements are in collectors inside the top one, not just objects
                                    if len(obj_col.children) > 0 and len(obj_col.children[0].objects) > 0:
                                        obj = obj_col.children[0].objects[0]
                                        # Check for Position and if changed delete the original and add to the new sector
                                        if obj.matrix_world != Matrix(obj_col['matrix']):
                                            deletions[sectorName].append(obj_col)
                                            # working with instancedmesh nodes is a pain in the ass, so convert to static
                                            if new_WIDM_static == None:
                                                create_static_from_WIMN(e, template_nodes, new_HID)
                                                new_ni = len(template_nodes) - 1
                                                new_WIDM_static = new_ni

                                            for child in obj_col.children:
                                                if len(child.objects) > 0:
                                                    # might need to convert instanced to static here, not sure what the best approach is.
                                                    createNodeData(
                                                        template_nodeData, child, new_WIDM_static, child.objects[0], ID
                                                        )
                                                    ID += 1
                                    else:
                                        # empty collector, so just delete
                                        if obj_col:
                                            deletions[sectorName].append(obj_col)

                case 'worldCollisionNode':
                    # need to process the sector_coll sectors and look for deleted collision bodies - this is almost identical to import, refactor them to have it in one place
                    if sector_Collisions in coll_scene.children.keys():

                        sector_Collisions_coll = bpy.data.collections.get(sector_Collisions)
                        collision_instances = node_data_by_node.get(i, ())
                        if not collision_instances:
                            raise ValueError(
                                f"{sectorName}: collision node {i} has no nodeData"
                            )
                        inst = collision_instances[0][0]
                        print('collisions Node ', inst['nodeDataIndex'])
                        Actors = e['Data']['compiledData']['Data']['Actors']
                        expectedNodes[sectorName + '_NI_' + str(inst['nodeDataIndex'])] = len(Actors)
                        for idx, act in enumerate(Actors):
                            x = act['Position']['x']['Bits'] / 131072
                            y = act['Position']['y']['Bits'] / 131072
                            z = act['Position']['z']['Bits'] / 131072
                            arot = get_rot(act)
                            for s, shape in enumerate(act['Shapes']):
                                collname = 'NodeDataIndex_' + str(inst['nodeDataIndex']) + '_Actor_' + str(
                                    idx
                                    ) + '_Shape_' + str(s)
                                if collname in sector_Collisions_coll.objects:
                                    print('found ', collname)
                                    crash = sector_Collisions_coll.objects[collname]
                                    if Matrix(crash['matrix']).to_translation() != crash.matrix_world.to_translation():
                                        # how the f do we deal with this???
                                        # delete the actor with archivexl, then recreate it with the new position
                                        # so we need a collisions node, then we need to add the actor
                                        # if we already added one to the export sector it should be ref'd by impacts, if not copy this one and ref it from impacts
                                        # Code below is working, but the collisions arent, I'm clearly missing something.
                                        if impacts == None:
                                            # add the actor to the archivexl deletion list
                                            if inst['nodeDataIndex'] in deletions['Collisions'][sectorName].keys():
                                                deletions['Collisions'][sectorName][inst['nodeDataIndex']].append(
                                                    str(idx)
                                                    )
                                            else:
                                                deletions['Collisions'][sectorName][inst['nodeDataIndex']] = [str(idx)]

                                            # nodeindex is the len of template nodes
                                            new_ni = len(template_nodes)
                                            # copy the collision node
                                            template_nodes.append(copy.deepcopy(nodes[i]))
                                            createNodeData(template_nodeData, nodes[i], new_ni, crash, ID)
                                            ID += 1
                                            impacts = template_nodes[len(template_nodes) - 1]
                                            impacts['Data']['compiledData']['Data']['Actors'] = []
                                            # need to update the position data

                                        # Add the current actor to the actors
                                        impacts['Data']['compiledData']['Data']['Actors'].append(
                                            copy.deepcopy(Actors[idx])
                                            )
                                        # update its position
                                        ddyer = impacts['Data']['compiledData']['Data']['Actors'][
                                            len(impacts['Data']['compiledData']['Data']['Actors']) - 1]
                                        actloc = ((crash.location[0] - ddyer['Shapes'][s]['Position']['X']) * 131072,
                                                  (crash.location[1] - ddyer['Shapes'][s]['Position']['Y']) * 131072,
                                                  (crash.location[2] - ddyer['Shapes'][s]['Position']['Z']) * 131072)
                                        ddyer['Shapes'][s]['Position'] = {"$type": "Vector3",
                                                                          "X": {"$type": "FixedPoint",
                                                                                "Bits": int(actloc[0])},
                                                                          "y": {"$type": "FixedPoint",
                                                                                "Bits": int(actloc[1])},
                                                                          "z": {"$type": "FixedPoint",
                                                                                "Bits": int(actloc[2])}}
                                        ddyer['Orientation'] = {'$type': 'Quaternion', 'r': float(
                                            "{:.9g}".format(crash.rotation_quaternion[0])
                                            ), 'i': float("{:.9g}".format(crash.rotation_quaternion[1])), 'j': float(
                                            "{:.9g}".format(crash.rotation_quaternion[2])
                                            ), 'k': float("{:.9g}".format(crash.rotation_quaternion[3]))}
                                        ddyer['Scale'] = {'$type': 'Vector3',
                                                          'X': float("{:.9g}".format(crash.scale[0])),
                                                          'Y': float("{:.9g}".format(crash.scale[1])),
                                                          'Z': float("{:.9g}".format(crash.scale[2]))}
                                        if 'Size' in ddyer['Shapes'][s].keys():
                                            ddyer['Shapes'][s]['Size'] = {"$type": "Vector3",
                                                                          "X": crash.dimensions[0] / 2,
                                                                          "Y": crash.dimensions[1] / 2,
                                                                          "Z": crash.dimensions[2] / 2}
                                        # update the numActors property
                                        impacts['Data']['numActors'] = len(
                                                impacts['Data']['compiledData']['Data']['Actors']
                                                )

                                        for mat in shape['Materials']:
                                            if mat['$value'] not in impact_mats:
                                                impact_mats.append(mat['$value'])
                                        impacts['Data']['numMaterials'] = len(impact_mats)


                                else:
                                    if shape['ShapeType'] == 'Box' or shape['ShapeType'] == 'Capsule':
                                        if inst['nodeDataIndex'] in deletions['Collisions'][sectorName].keys():
                                            deletions['Collisions'][sectorName][inst['nodeDataIndex']].append(str(idx))
                                        else:
                                            deletions['Collisions'][sectorName][inst['nodeDataIndex']] = [str(idx)]

        print(wIMNs)

        #       __   __          __      __  ___       ___  ___
        #  /\  |  \ |  \ | |\ | / _`    /__`  |  |  | |__  |__
        # /~~\ |__/ |__/ | | \| \__>    .__/  |  \__/ |    |
        #
        instances_to_copy = []
        destructibles_to_copy = []
        if Sector_additions_coll:
            for col in Sector_additions_coll.children:
                if (
                    'nodeIndex' not in col.keys()
                    or not col.objects
                    or col.get('sectorName') not in bpy.data.collections.keys()
                ):
                    continue
                source_sector = col['sectorName']
                source_collection = bpy.data.collections.get(source_sector)
                source_document = source_repository.load(
                    source_collection['filepath']
                )
                source_nodes = source_document["Data"]["RootChunk"]["nodes"]
                node_index = int(col['nodeIndex'])
                node_type = col['nodeType']
                if node_type == 'worldInstancedMeshNode':
                    key = [node_index, source_sector]
                    if key not in instances_to_copy:
                        instances_to_copy.append(key)
                    continue
                if node_type == 'worldInstancedDestructibleMeshNode':
                    key = [node_index, source_sector]
                    if key not in destructibles_to_copy:
                        destructibles_to_copy.append(key)
                    continue
                if node_type not in {
                    'worldStaticMeshNode',
                    'worldStaticDecalNode',
                    'worldBuildingProxyMeshNode',
                    'worldGenericProxyMeshNode',
                    'worldTerrainProxyMeshNode',
                    'worldEntityNode',
                }:
                    continue
                if node_index < 0 or node_index >= len(source_nodes):
                    raise ValueError(
                        f"{source_sector}: invalid source node {node_index}"
                    )
                new_node = copy.deepcopy(source_nodes[node_index])
                remap_owned_handles(new_node, template_handle_allocator)
                template_nodes.append(new_node)
                createNodeData(
                    template_nodeData,
                    col,
                    len(template_nodes) - 1,
                    col.objects[0],
                    ID,
                )
                ID += 1

        print(instances_to_copy)
        print(destructibles_to_copy)

        for node in instances_to_copy:
            ni = node[0]
            source_sector = node[1]
            source_sect_coll = bpy.data.collections.get(source_sector)
            source_sect_json_path = source_sect_coll['filepath']
            source_sect_json = source_repository.load(source_sect_json_path)
            source_nodes = source_sect_json["Data"]["RootChunk"]["nodes"]
            template_nodes.append(copy.deepcopy(source_nodes[ni]))
            new_Index = len(template_nodes) - 1
            new_node = template_nodes[new_Index]
            remap_owned_handles(new_node, template_handle_allocator)
            instances = source_repository.node_data(
                source_sect_json_path,
                ni,
            )
            if not instances:
                raise ValueError(
                    f"{source_sector}: node {ni} has no nodeData entry"
                )
            inst = instances[0]
            template_nodeData.append(copy.deepcopy(inst))
            new_nd_node = template_nodeData[-1]
            new_nd_node['NodeIndex'] = new_Index
            new_nd_node['Id'] = ID
            ID += 1
            copied_transforms = []
            for col in Sector_additions_coll.children:
                if (
                    col.get('nodeIndex') != ni
                    or col.get('sectorName') != source_sector
                    or not col.objects
                ):
                    continue
                obj = col.objects[0]
                trans = {"$type": "worldNodeTransform",
                         "rotation": {"$type": "Quaternion", "i": 0.0, "j": 0.0, "k": 0.0, "r": 1.0},
                         "translation": {"$type": "Vector3", "X": 0.0, "Y": 0.0, "Z": 0.0},
                         'scale': {'$type': 'Vector3', 'X': 1.0, 'Y': 1.0, 'Z': 1.0}}
                set_pos(trans, obj)
                set_rot(trans, obj)
                set_scale(trans, obj)
                copied_transforms.append(trans)
            if not copied_transforms:
                raise ValueError(
                    f"{source_sector}: copied node {ni} has no instances"
                )
            template_transform_buffers.attach_slice(
                "worldTransformsBuffer",
                new_node['Data']['worldTransformsBuffer'],
                copied_transforms,
            )

        for node in destructibles_to_copy:
            ni = node[0]
            source_sector = node[1]
            source_sect_coll = bpy.data.collections.get(source_sector)
            source_sect_json_path = source_sect_coll['filepath']
            source_sect_json = source_repository.load(source_sect_json_path)
            source_nodes = source_sect_json["Data"]["RootChunk"]["nodes"]
            template_nodes.append(copy.deepcopy(source_nodes[ni]))
            new_Index = len(template_nodes) - 1
            new_node = template_nodes[new_Index]
            remap_owned_handles(new_node, template_handle_allocator)
            instances = source_repository.node_data(
                source_sect_json_path,
                ni,
            )
            if not instances:
                raise ValueError(
                    f"{source_sector}: node {ni} has no nodeData entry"
                )
            inst = instances[0]
            template_nodeData.append(copy.deepcopy(inst))
            new_nd_node = template_nodeData[-1]
            new_nd_node['NodeIndex'] = new_Index
            new_nd_node['Id'] = ID
            ID += 1
            new_nd_node['Position']['X'] = 0
            new_nd_node['Position']['Y'] = 0
            new_nd_node['Position']['Z'] = 0
            new_nd_node['Orientation']['r'] = 1
            new_nd_node['Orientation']['i'] = 0
            new_nd_node['Orientation']['j'] = 0
            new_nd_node['Orientation']['k'] = 0
            new_nd_node['Scale']['X'] = 1
            new_nd_node['Scale']['Y'] = 1
            new_nd_node['Scale']['Z'] = 1

            copied_transforms = []
            for col in Sector_additions_coll.children:
                if (
                    col.get('nodeIndex') != ni
                    or col.get('sectorName') != source_sector
                    or not col.objects
                ):
                    continue
                obj = col.objects[0]
                trans = {"$type": "Transform",
                         "orientation": {"$type": "Quaternion", "i": 0.0, "j": 0.0, "k": 0.0, "r": 1.0},
                         "position": {"$type": "Vector4", "W": 0, "X": 0.0, "Y": 0.0, "Z": 0.0}}
                set_pos(trans, obj)
                set_rot(trans, obj)
                set_scale(trans, obj)
                copied_transforms.append(trans)
            if not copied_transforms:
                raise ValueError(
                    f"{source_sector}: copied destructible node {ni} "
                    "has no instances"
                )
            template_transform_buffers.attach_slice(
                "cookedInstanceTransforms",
                new_node['Data']['cookedInstanceTransforms'],
                copied_transforms,
            )

    # Export the modified json
    sectpathout = os.path.join(projpath, os.path.splitext(os.path.basename(filename))[0] + '.streamingsector.json')
    xlpathout = os.path.join(xloutpath, os.path.splitext(os.path.basename(filename))[0] + '.archive.xl')
    archive_xl = build_archive_xl(xlpathout, deletions, expectedNodes)
    atomic_write_many({
        sectpathout: (
            json.dumps(template_json, indent=2, ensure_ascii=False) + "\n"
        ).encode("utf-8"),
        xlpathout: serialize_archive_xl(
            archive_xl,
            use_yaml=use_yaml,
        ).encode("utf-8"),
    })
    print('Finished exporting sectors from ', os.path.splitext(os.path.basename(filename))[0], ' to ', sectpathout)
    return {
        "sector_path": sectpathout,
        "archive_xl_path": xlpathout,
    }
