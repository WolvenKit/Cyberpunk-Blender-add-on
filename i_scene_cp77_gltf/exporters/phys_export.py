import json
import os 
import bpy
from mathutils import Vector, Euler, Quaternion
from ..main.common import show_message

def export_colliders_to_phys(collections, filepath):
    # Initialize a list to store collider information
    colliders = []
    print(collections)
    # Initialize an index counter
    index = 1
    for collection in collections:
        # Iterate over objects in the collection
        for obj in collection.objects:
            if 'collisionShape' in obj:
                collider_info = {
                    "HandleId": str(index),
                    "Data": {
                        "$type": obj['collisionShape'],
                        "filterData": None,
                        "isImported": 0,
                        "isQueryShapeOnly": 0,
                        "localToBody": {
                            "$type": "Transform",
                            "orientation": {
                                "$type": "Quaternion",
                                "i": obj.rotation_quaternion.z,
                                "j": obj.rotation_quaternion.x,
                                "k": obj.rotation_quaternion.y,
                                "r": obj.rotation_quaternion.w
                            },
                            "position": {
                                "$type": "Vector4",
                                "W": 0,
                                "X": obj.location.x,
                                "Y": obj.location.y,
                                "Z": obj.location.z
                            }
                        },
                        "material": {
                            "$type": "CName",
                            "$storage": "string",
                            "$value": obj.get('physics_material', 'None')
                        },
                        "materialApperanceOverrides": [],
                        "tag": {
                            "$type": "CName",
                            "$storage": "string",
                            "$value": "None"
                        },
                        "volumeModifier": 1
                    }
                }
                
                # Add collider-specific data
                if obj['collisionShape'] == "physicsColliderConvex":
                    mesh = obj.data
                    vertices = []
                    # Iterate over each vertex and store its position
                    for vertex in mesh.vertices:
                        position = {
                            "$type": "Vector3",
                            "X": vertex.co.x,
                            "Y": vertex.co.y,
                            "Z": vertex.co.z
                            }
                        vertices.append(position)
                    # Add vertices data
                    collider_info["Data"]["vertices"] = vertices
                    
                elif obj['collisionShape'] == "physicsColliderBox":
                    # Add halfExtents data
                    collider_info["Data"]["halfExtents"] = {
                        "$type": "Vector3",
                        "X": obj.dimensions.x / 2,
                        "Y": obj.dimensions.y / 2,
                        "Z": obj.dimensions.z / 2
                    }
                
                elif obj['collisionShape'] == "physicsColliderCapsule":
                    collider_info['Data']['radius'] = obj.dimensions.x / 2 
                    collider_info['Data']['height'] = obj.dimensions.z
               
                elif obj['collisionShape'] == "physicsColliderSphere":
                    collider_info['Data']['radius'] = obj.dimensions.x / 2  
                
                # Append collider info to list
                colliders.append(collider_info)
                index += 1

    # Create the JSON data structure
    data = {
        "Header": {
            "WolvenKitVersion": "8.13.0-nightly.2024-04-10",
            "WKitJsonVersion": "0.0.8",
            "GameVersion": 2120,
            "ExportedDateTime": "2024-04-11T03:57:18.3818438Z",
            "DataType": "CR2W",
            "ArchiveFileName": filepath
        },
        "Data": {
            "Version": 195,
            "BuildVersion": 0,
            "RootChunk": {
                "$type": "physicsSystemResource",
                "bodies": [
                    {
                      "HandleId": "0",
                      "Data": {
                        "$type": "physicsSystemBody",
                        "collisionShapes": colliders,
                        "isQueryBodyOnly": 0,
                        "localToModel": {
                            "$type": "Transform",
                            "orientation": {"$type": "Quaternion", "i": 0, "j": 0, "k": 0, "r": 1},
                            "position": {"$type": "Vector4", "W": 0, "X": 0, "Y": 0, "Z": 0}
                        },
                        "mappedBoneName": {"$type": "CName", "$storage": "string", "$value": "None"},
                        "mappedBoneToBody": {
                            "$type": "Transform",
                            "orientation": {"$type": "Quaternion", "i": 0, "j": 0, "k": 0, "r": 1},
                            "position": {"$type": "Vector4", "W": 0, "X": 0, "Y": 0, "Z": 0}
                        },
                        "name": {"$type": "CName", "$storage": "string", "$value": "Actor"},
                        "params": {
                            "$type": "physicsSystemBodyParams",
                            "angularDamping": 0,
                            "comOffset": {
                                "$type": "Transform",
                                "orientation": {"$type": "Quaternion", "i": 0, "j": 0, "k": 0, "r": 1},
                                "position": {"$type": "Vector4", "W": 0, "X": 0, "Y": 0, "Z": 0}
                            },
                            "inertia": {"$type": "Vector3", "X": 0, "Y": 0, "Z": 0},
                            "linearDamping": 0,
                            "mass": 0,
                            "maxAngularVelocity": -1,
                            "maxContactImpulse": -1,
                            "maxDepenetrationVelocity": -1,
                            "simulationType": "Static",
                            "solverIterationsCountPosition": 4,
                            "solverIterationsCountVelocity": 1
                }
          }
        }
      ],
      "cookingPlatform": "PLATFORM_PC",
      "joints": []
    },
    "EmbeddedFiles": []
  }
}
    message = f"Collider information exported to: {filepath}"
    # Write the data to a JSON file
    with open(filepath, 'w') as json_file:
        json.dump(data, json_file, indent=4)
    show_message(message)