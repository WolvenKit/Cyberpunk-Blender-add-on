COLLIDER_TEMPLATES = {
    "Mesh" : {
        "HandleId": "",
        "Data": {
            "$type": "physicsColliderMesh",
            "compiledGeometryBuffer": {
                "BufferId": "",
                "Flags": 4063232,
                "Bytes": ""
            },
            "faceMaterials": [],
            "filterData": {},
            "isImported": 0,
            "isQueryShapeOnly": 0,
            "localToBody": {
                "$type": "Transform",
                "orientation": {
                    "$type": "Quaternion",
                    "i": 0,
                    "j": 0,
                    "k": 0,
                    "r": 0
                },
                "position": {
                    "$type": "Vector4",
                    "W": 0,
                    "X": 0,
                    "Y": 0,
                    "Z": 0
                }
            },
            "material": {
                "$type": "CName",
                "$storage": "string",
                "$value": ""
            },
            "materialApperanceOverrides": [],
            "tag": {
                "$type": "CName",
                "$storage": "string",
                "$value": "None"
            },
            "unk1": 0,
            "unk2": [],
            "volumeModifier": 1
        }
    },
    "Box": {
        "HandleId": "",
        "Data": {
            "$type": "physicsColliderBox",
            "filterData": {},
            "halfExtents": {
                "$type": "Vector3",
                "X": 0,
                "Y": 0,
                "Z": 0
            },
            "isImported": 0,
            "isObstacle": 0,
            "isQueryShapeOnly": 0,
            "localToBody": {
                "$type": "Transform",
                "orientation": {
                    "$type": "Quaternion",
                    "i": 0,
                    "j": 0,
                    "k": 0,
                    "r": 0
                },
                "position": {
                    "$type": "Vector4",
                    "W": 0,
                    "X": 0,
                    "Y": 0,
                    "Z": 0
                }
            },
            "material": {
                "$type": "CName",
                "$storage": "string",
                "$value": ""
            },
            "materialApperanceOverrides": [],
            "tag": {
                "$type": "CName",
                "$storage": "string",
                "$value": "None"
            },
            "volumeModifier": 1
        }
    },
    "Capsule": {
        "HandleId": "",
        "Data": {
            "$type": "physicsColliderCapsule",
            "filterData": {},
            "height": 0,
            "isImported": 0,
            "isQueryShapeOnly": 0,
            "localToBody": {
                "$type": "Transform",
                "orientation": {
                    "$type": "Quaternion",
                    "i": 0,
                    "j": 0,
                    "k": 0,
                    "r": 0
                },
                "position": {
                    "$type": "Vector4",
                    "W": 0,
                    "X": 0,
                    "Y": 0,
                    "Z": 0
                }
            },
            "material": {
                "$type": "CName",
                "$storage": "string",
                "$value": ""
            },
            "materialApperanceOverrides": [],
            "radius": 0,
            "tag": {
                "$type": "CName",
                "$storage": "string",
                "$value": "None"
            },
            "volumeModifier": 0.200000003
        }
    },
    "Sphere": {
        "HandleId": "0",
        "Data": {
            "$type": "physicsColliderSphere",
            "filterData": {},
            "isImported": 0,
            "isQueryShapeOnly": 0,
            "localToBody": {
                "$type": "Transform",
                "orientation": {
                    "$type": "Quaternion",
                    "i": 0,
                    "j": 0,
                    "k": 0,
                    "r": 0
                },
                "position": {
                    "$type": "Vector4",
                    "W": 0,
                    "X": 0,
                    "Y": 0,
                    "Z": 0
                }
            },
            "material": {
                "$type": "CName",
                "$storage": "string",
                "$value": ""
            },
            "materialApperanceOverrides": [],
            "radius": 0,
            "tag": {
                "$type": "CName",
                "$storage": "string",
                "$value": "None"
            },
            "volumeModifier": 1
        }
    }
}

FILTER_DATA_TEMPLATES = {
    "World Static": {
        "HandleId": "",
        "Data": {
            "$type": "physicsFilterData",
            "customFilterData": None,
            "preset": {
                "$type": "CName",
                "$storage": "string",
                "$value": "World Static"
            },
            "queryFilter": {
                "$type": "physicsQueryFilter",
                "mask1": "0",
                "mask2": "71942148"
            },
            "simulationFilter": {
                "$type": "physicsSimulationFilter",
                "mask1": "376836",
                "mask2": "5070"
            }
        }
    },
    "Complex Environment Collision": {
        "HandleId": "",
        "Data": {
            "$type": "physicsFilterData",
            "customFilterData": None,
            "preset": {
                "$type": "CName",
                "$storage": "string",
                "$value": "Complex Environment Collision"
            },
            "queryFilter": {
                "$type": "physicsQueryFilter",
                "mask1": "0",
                "mask2": "4718592"
            },
            "simulationFilter": {
                "$type": "physicsSimulationFilter",
                "mask1": "0",
                "mask2": "0"
            }
        }
    },
    "Simple Environment Collision": {
        "HandleId": "",
        "Data": {
            "$type": "physicsFilterData",
            "customFilterData": None,
            "preset": {
                "$type": "CName",
                "$storage": "string",
                "$value": "Simple Environment Collision"
            },
            "queryFilter": {
                "$type": "physicsQueryFilter",
                "mask1": "0",
                "mask2": "67485700"
            },
            "simulationFilter": {
                "$type": "physicsSimulationFilter",
                "mask1": "376836",
                "mask2": "7752"
            }
        }
    }
}