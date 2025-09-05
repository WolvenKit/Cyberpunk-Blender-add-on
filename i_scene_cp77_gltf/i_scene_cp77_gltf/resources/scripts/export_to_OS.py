#
#     ____  __      _           __  _____                                         ____        __              __ 
#    / __ \/ /_    (_)__  _____/ /_/ ___/____  ____ __      ______  ___  _____   / __ \__  __/ /_____  __  __/ /_
#   / / / / __ \  / / _ \/ ___/ __/\__ \/ __ \/ __ `/ | /| / / __ \/ _ \/ ___/  / / / / / / / __/ __ \/ / / / __/
#  / /_/ / /_/ / / /  __/ /__/ /_ ___/ / /_/ / /_/ /| |/ |/ / / / /  __/ /     / /_/ / /_/ / /_/ /_/ / /_/ / /_  
#  \____/_.___/_/ /\___/\___/\__//____/ .___/\__,_/ |__/|__/_/ /_/\___/_/      \____/\__,_/\__/ .___/\__,_/\__/  
#            /___/                   /_/                                                     /_/                 #
#
# Script to generate Object Spawner* jsons from the current selection *(aka Entity Spawner, World Editing Toolkit, Wheezekit, Buildy McBuildface)
# Written by Simarilius, OS by KeanuWheeze
# Initial version 15/8/24, updated 14/3/25
# v0.3
#
# INSTRUCTIONS:
# Import some sectors
# Select some stuff
# set the groupname and project folder variables
# Run the script, it saves a json with the OS group in the top level project folder
# Copy it to Cyberpunk 2077\bin\x64\plugins\cyber_engine_tweaks\mods\entSpawner\data\objects
# Spawn it and enjoy/modify
# when your happy with it use the wscript to import to wkit and convert to axl mod
#
# Comments/Suggestions welcome, feel free to ping me on the wkit discord. (use worldediting or blenderaddon channels)

GroupName='aldecados_workshop_tent'
ProjectFolder = 'C:\\CPMod\\OS_export'

# Can try autogenerate collisions, options are NONE, ALL, STRUCT (trys to just do walls/floors/ceilings)
# Any objects with OS_Coll or physicsCollider in the name will get treated as collisions regardless of this
# first if for manual coll additions, second is the naming from the plugin collision generator thing
GENERATE_COLLISIONS='NONE'

import bpy
import os
import json
from math import pi,radians,degrees
D=bpy.data
C=bpy.context



def set_pos(obj):
    #print(inst)
    position={}
    position['w'] = float("{:.9g}".format(0))
    position['x']= float("{:.9g}".format(obj.location[0]))
    position['y'] = float("{:.9g}".format(obj.location[1]))
    position['z'] = float("{:.9g}".format(obj.location[2]))
    return position

def set_rot(obj):
    rotation={}   
    obj.rotation_mode='XYZ'
    rotation['pitch'] = float("{:.9g}".format(degrees(obj.rotation_euler[0] )))
    rotation['roll'] = float("{:.9g}".format(degrees(obj.rotation_euler[1] )))
    rotation['yaw'] = float("{:.9g}".format(degrees(obj.rotation_euler[2] )))
    return rotation

def set_scale(obj):
    scale={}
    scale['x'] = float("{:.9g}".format(obj.scale[0] ))
    scale['y'] = float("{:.9g}".format(obj.scale[1] ))
    scale['z'] = float("{:.9g}".format(obj.scale[2] ))
    return scale

def save_selected():
    selected=[]
    for obj in bpy.context.selected_objects:
        selected.append(obj)
    return selected

def retrieve_selected(list):
    for obj in list:
        try:
            obj.select_set(True)
        except:
            print('invalid')

def find_debugName(obj):
    debugName=None
    if 'debugName' in obj.keys():
        return obj['debugName']    
    if 'debugName' in obj.users_collection[0].keys():
        debugName=obj.users_collection[0]['debugName']
    else:
        if coll_parents.get(obj.users_collection[0].name)!="Scene Collection" and 'debugName' in D.collections[coll_parents.get(obj.users_collection[0].name)]:
            debugName=D.collections[coll_parents.get(obj.users_collection[0].name)]['debugName']
        else:
            if coll_parents.get(coll_parents.get(obj.users_collection[0].name.name)) and 'debugName' in D.collections[coll_parents.get(coll_parents.get(obj.users_collection[0].name.name))]:
                debugName=D.collections[coll_parents.get(coll_parents.get(obj.users_collection[0].name.name))]['debugName']
    return debugName

def find_nodeType(obj):
    nodeType=None
    if 'nodeType' in obj.keys():
        return obj['nodeType']    
    if obj.users_collection[0].name!="Scene Collection" and 'nodeType' in obj.users_collection[0].keys():
        nodeType=obj.users_collection[0]['nodeType']
        obj['appearanceName']=obj.users_collection[0]['appearanceName']
    elif coll_parents.get(obj.users_collection[0].name)!="Scene Collection" and 'nodeType' in D.collections[coll_parents.get(obj.users_collection[0].name)]:
        nodeType=D.collections[coll_parents.get(obj.users_collection[0].name)]['nodeType']
        obj['appearanceName']=D.collections[coll_parents.get(obj.users_collection[0].name)]['appearanceName']

    return nodeType

def traverse_tree(t):
    yield t
    for child in t.children:
        yield from traverse_tree(child)

def parent_lookup(coll):
    parent_lookup = {}
    for coll in traverse_tree(coll):
        for c in coll.children.keys():
            parent_lookup.setdefault(c, coll.name)
    return parent_lookup

def new_group(groupname):
    return {"rot": {"pitch": 0,"yaw": 0,"roll": 0}, "pos": { "x": 0,"y": 0, "w": 0, "z": 0 },"childs":[],"name": groupname,"isUsingSpawnables": True, "headerOpen": True,"loadRange": 1000, "autoLoad": False, "type": "group"}

def new_object(OStype,name, pos, rot,spawnData):
    obj=new_group(name)
    obj['type']='object'
    obj['name']=name
    obj['spawnableHeaderOpen']=False
    obj['spawnable']= {
                        "modulePath": OStype[0],
                        "rotationRelative": False,
                        "position": pos,
                        "spawnData": spawnData,
                        "app": "",
                        "dataType": OStype[1],
                        "rotation": rot
                    }
    return obj

def new_collision(group, obj, name):
    colltarget = group['childs'][mesh_colls]['childs']
    obj.rotation_mode='XYZ'
    rot=set_rot(obj)
    pos=set_pos(obj)
    scale=set_scale(obj)
    extents={'x':obj.dimensions[0]/2,'y':obj.dimensions[1]/2,'z':obj.dimensions[2]/2}
    collpos={'x':pos['x'],'y':pos['y'],'z':pos['z']}
    colltarget.append({
        "spawnableHeaderOpen": False,
        "type": "object",
        "name": obj.name,
        "autoLoad": False,
        "loadRange": 1000,
        "spawnable": {
            "modulePath": "collision/collider",
            "rotationRelative": False,
            "previewed": True,
            "radius": 1, # radius for sphere and capsule
            "material": 31,
            "position": collpos,
            "height": 1, # capsule length
            "spawnData": "base\\spawner\\empty_entity.ent",
            "extents": extents,
            "preset": 33,
            "rotation": rot,
            "app": "",
            "dataType": "Collision Shape",
            "shape": 0 # 0=box, 1=capsue, 2=sphere from entspawner code
        },
        "headerOpen": False
    })




coll_scene = C.scene.collection
coll_parents = parent_lookup(coll_scene)


exported=[]
group=new_group(GroupName)
group['childs'].append(new_group('walls'))
walls=0
group['childs'].append(new_group('floors'))
floors=1
group['childs'].append(new_group('ceilings'))
ceilings=2
group['childs'].append(new_group('Decals'))
decals=3
group['childs'].append(new_group('Entities'))
entities=4
group['childs'].append(new_group('Meshes'))
meshes=5
group['childs'].append(new_group('Sounds'))
sounds=6
group['childs'].append(new_group('Effects_and_Particles'))
effects=7
group['childs'].append(new_group('Struct_Collisions'))
struct_colls=8
group['childs'].append(new_group('mesh_collisions'))
mesh_colls=9

objs=bpy.context.selected_objects
for obj in objs:
    nodeType=find_nodeType(obj)
    
    match nodeType:
    # check for decals
        case 'worldStaticDecalNode':
            pos=set_pos(obj)
            rot=set_rot(obj)


            if 'horizontalFlip' in obj.keys():
                horizontalFlip=bool(obj['horizontalFlip'])
            else:
                horizontalFlip=False
            if 'verticalFlip' in obj.keys():
                verticalFlip=bool(obj['verticalFlip'])
            else:
                verticalFlip=False
            
            group['childs'][decals]['childs'].append({
            "spawnableHeaderOpen": False,
            "type": "object",
            "name": obj.name,
            "autoLoad": False,
            "loadRange": 1000,
            "spawnable": {"modulePath": "visual/decal",
            "rotationRelative": False,
            "alpha": 1,
            "horizontalFlip": horizontalFlip,
            "verticalFlip": verticalFlip,
            "position": set_pos(obj),
            "spawnData": obj['decal'],
            "scaleLocked": True,
            "autoHideDistance": 150,
            "scale": set_scale(obj),
            "app":obj['appearanceName'],
            "dataType": "Decals",
            "rotation": rot},
            "headerOpen": False})           
    # check for entities
        case 'worldEntityNode':
            if 'nodeType' in obj.keys():
                ent=obj    
            elif 'nodeType' in obj.users_collection[0].keys():
                ent=obj.users_collection[0]
            elif 'nodeType' in D.collections[coll_parents.get(obj.users_collection[0].name)]:
                ent=D.collections[coll_parents.get(obj.users_collection[0].name)]
            elif 'nodeType' in D.collections[coll_parents.get(coll_parents.get(obj.users_collection[0].name.name))]:
                ent=D.collections[coll_parents.get(coll_parents.get(obj.users_collection[0].name.name))]
            if ent.name not in exported:            
                rot={'pitch': float("{:.9g}".format(degrees(ent['ent_rot'][0]))),'roll': float("{:.9g}".format(degrees(ent['ent_rot'][1]))),'yaw': float("{:.9g}".format(degrees(ent['ent_rot'][2])))}
                pos={'x': float("{:.9g}".format(ent['ent_pos'][0])),'y': float("{:.9g}".format(ent['ent_pos'][1])),'z': float("{:.9g}".format(ent['ent_pos'][2])),'w': float("{:.9g}".format(0))}
                
                group['childs'][entities]['childs'].append({"spawnableHeaderOpen": False,
                    "type": "object",
                    "name": ent.name,
                    "autoLoad": False,
                    "loadRange": 1000,
                    "spawnable": {"modulePath": "entity/entityTemplate",
                    "rotationRelative": False,
                    "position": pos,
                    "instanceData": [],
                    "spawnData": ent['entityTemplate'],
                    "instanceDataChanges": [],
                    "app": ent['appearanceName'],
                    "dataType": "Entity Template",                    
                    "rotation": rot
                    },
                    "headerOpen": False
                    })
                exported.append(ent.name)
        case "worldPopulationSpawnerNode":
            rot=set_rot(obj)
            group['childs'][entities]['childs'].append({
                    "spawnableHeaderOpen": False,
                    "type": "object",
                    "name": "Entity Record",
                    "autoLoad": False,
                    "loadRange": 1000,
                    "spawnable": {
                        "modulePath": "entity/entityRecord",
                        "rotationRelative": False,
                        "position": set_pos(obj),
                        "instanceData": [],
                        "spawnData": obj['objectRecordId'],
                        "instanceDataChanges": [],
                        "app": obj['appearanceName'],
                        "dataType": "Entity Record",
                        "rotation": rot
                    },
                    "headerOpen": False
                })
            pass

        case "worldStaticLightNode":
            rot=set_rot(obj)
            OSobj= {
            "spawnableHeaderOpen": False,
            "type": "object",
            "name": "Light",
            "autoLoad": False,
            "loadRange": 1000,
            "spawnable": {
                "modulePath": "light/light",
                "intensity": obj.data.energy,
                "radius": 15,
                "spawnData": "base\\spawner\\empty_entity.ent",
                "capsuleLength": 1,
                "autoHideDistance": 45,
                "flickerStrength": obj['flicker']['flickerStrength'],
                "flickerPeriod": obj['flicker']['flickerPeriod'],
                "dataType": "Static Light",
                "rotationRelative": False,
                "innerAngle": 20,
                "outerAngle": 60,
                "color": [
                    obj.data.color[0],
                    obj.data.color[1],
                    obj.data.color[2]
                ],
                "position": set_pos(obj),
                "scaleVolFog": 0,
                "temperature": -1,
                "lightType": 0,
                "app": "",
                "flickerOffset": 0,
                "rotation": rot
            },
            "headerOpen": False
            }
            if 'capsuleLength' in obj.keys():
                OSobj['capsuleLength']=obj['capsuleLength']
            if 'radius' in obj.keys():
                OSobj['radius']=obj['radius']
            group['childs'][entities]['childs'].append(OSobj)

            pass
        
        case "worldEffectNode":
            rot=set_rot(obj)
            group['childs'][effects]['childs'].append({
            "spawnableHeaderOpen": False,
            "type": "object",
            "name": "Effect",
            "autoLoad": False,
            "loadRange": 1000,
            "spawnable": {
                "modulePath": "visual/effect",
                "spawnData": obj['effect'],
                "rotationRelative": False,
                "dataType": "Effects",
                "app": "",
                "rotation": rot,
                "position": set_pos(obj)
            },
            "headerOpen": False
        })
            pass
        case "worldStaticParticleNode":
            rot=set_rot(obj)
            group['childs'][effects]['childs'].append({
            "spawnableHeaderOpen": False,
            "type": "object",
            "name": "Particle",
            "autoLoad": False,
            "loadRange": 1000,
            "spawnable": {
                "modulePath": "visual/particle",
                "emissionRate": 1,
                "respawnOnMove": False,
                "position": set_pos(obj),
                "spawnData": obj['particleSystem'],
                "rotation": rot,
                "app": "",
                "dataType": "Particles",
                "rotationRelative": False
            },
            "headerOpen": False
            })
            pass
        case "worldStaticSoundEmitterNode":
            group['childs'][sounds]['childs'].append({
            "spawnableHeaderOpen": False,
            "type": "object",
            "name": "Sound",
            "autoLoad": False,
            "loadRange": 1000,
            "spawnable": {
                "modulePath": "visual/audio",
                "spawnData": obj['eventName'],
                "radius": 5,
                "rotationRelative": False,
                "dataType": "Sounds",
                "app": "",
                "rotation": set_rot(obj),
                "position": set_pos(obj)
            },
            "headerOpen": False
        })
            pass
        
        case  "worldRotatingMeshNode":
            OS_obj=new_object("mesh/rotatingMesh",obj.name,set_pos(obj),set_rot(obj),obj.users_collection[0]['mesh'])
            OS_obj['axis']=obj.users_collection[0]['rot_axis']
            OS_obj["reverse"]='reverseDirection'
            OS_obj["duration"]='fullRotationTime'
                        
        case  "worldCollisionNode":
            new_collision(group, obj,obj.name)
            pass
        case "worldClothMeshNode":
            obj.rotation_mode='XYZ'
            rot=set_rot(obj)
            pos=set_pos(obj)
            scale=set_scale(obj)
            group['childs'][meshes]['childs'].append({
            "spawnableHeaderOpen": False,
            "type": "object",
            "name": "Cloth Mesh",
            "autoLoad": False,
            "loadRange": 1000,
            "spawnable": {
                "modulePath": "mesh/clothMesh",
                "rotationRelative": False,
                "scale": scale,
                "rotation": rot,
                "spawnData": obj.users_collection[0]['mesh'],
                "affectedByWind": True,
                "scaleLocked": False,
                "position": pos,
                "app": obj['appearanceName'],
                "dataType": "Cloth Mesh",
                "collisionType": 4
            },
            "headerOpen": False
        })
            pass
    # none of the above then see if it has a mesh and treat it as a static
        case _:
            if obj.users_collection[0].name not in exported and 'mesh' in obj.users_collection[0].keys() :
                target=group['childs'][meshes]['childs']
                colltarget = group['childs'][mesh_colls]['childs']
                
                mesh=obj.users_collection[0]['mesh']
                name=os.path.basename(mesh).split('.')[0]
                if 'wall' in name and 'decal' not in name:
                    target = group['childs'][walls]['childs']
                    colltarget = group['childs'][struct_colls]['childs']
                elif 'floor' in name:
                    target = group['childs'][floors]['childs']
                    colltarget = group['childs'][struct_colls]['childs']
                elif 'ceil' in name:
                    target = group['childs'][ceilings]['childs']
                    colltarget = group['childs'][struct_colls]['childs']
                obj.rotation_mode='XYZ'
                rot=set_rot(obj)
                print(rot)
                pos=set_pos(obj)
                scale=set_scale(obj)
                target.append({"spawnable":{
                    "dataType":"Static Mesh",
                    "rotation":rot,
                    "scale":scale,
                    "rotationRelative":False,
                    "app":obj.users_collection[0]['appearanceName'],
                    "scaleLocked":True,
                    "modulePath":"mesh/mesh",
                    "position":pos,
                    "spawnData":mesh},
                    "headerOpen":False,
                    "spawnableHeaderOpen":False,
                    "autoLoad":False,
                    "loadRange":1000,
                    "type":"object",
                    "name":name})
                
                exported.append(obj.users_collection[0].name)
                if GENERATE_COLLISIONS=='ALL' or (GENERATE_COLLISIONS=='STRUCT' and ('wall' in name and 'decal' not in name and 'door' not in name or 'floor' in name or 'ceil' in name)):

                   new_collision(group, obj, name+"_ColliderBox")
            
            elif 'OS_Coll' in obj.name or 'physicsCollider' in obj.name:
                new_collision(group, obj,obj.name)

sectpathout = os.path.join(ProjectFolder,GroupName+'.json')

with open(sectpathout, 'w') as outfile:
    json.dump(group, outfile,indent=2)