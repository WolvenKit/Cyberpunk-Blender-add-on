<<<<<<< Updated upstream
from datetime import datetime

from ..common.atomic import atomic_write_json


def cp77_materialinstance_export(self, context, filepath):
    active_object = context.active_object
    active_material = active_object.active_material
=======
from ...assetio.atomic import atomic_write_json
from ...assetio.headers import cr2w_header
from ...assetio.values import cname_entry, resource_path_entry
from ...blender.operator_results import OperationResult


def cp77_materialinstance_export(context, filepath):
    """Write the active multilayered material as a WolvenKit material instance"""
    active_object = context.active_object
    active_material = (
        getattr(active_object, "active_material", None)
        if active_object is not None
        else None
    )
    if active_material is None:
        return OperationResult.cancelled("Select an object with an active material.")
    missing = [
        key
        for key in ("MultilayerMask", "MLSetup", "GlobalNormal")
        if key not in active_material
    ]
    if missing:
        return OperationResult.cancelled(
            f"{active_material.name} has no {', '.join(missing)}; only multilayered materials can be exported."
        )
>>>>>>> Stashed changes

    mlmask = active_material["MultilayerMask"]
    mlsetup = active_material["MLSetup"]
    gnormal = active_material["GlobalNormal"]
<<<<<<< Updated upstream

    data = {
        "Header": {
            "WolvenKitVersion": "8.17.2",
            "WKitJsonVersion": "0.0.9",
            "GameVersion": 2310,
            "ExportedDateTime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "DataType": "CR2W",
            "ArchiveFileName": ""
            },
=======
    if not mlsetup:
        return OperationResult.cancelled(
            f"{active_material.name} has no MLSETUP of its own yet; export its MLSETUP first."
        )

    data = {
        "Header": cr2w_header(filepath),
>>>>>>> Stashed changes
        "Data": {
            "Version": 195,
            "BuildVersion": 0,
            "RootChunk": {
                "$type": "CMaterialInstance",
<<<<<<< Updated upstream
                "audioTag": {
                    "$type": "CName",
                    "$storage": "string",
                    "$value": "None"
                    },
                "baseMaterial": {
                    "DepotPath": {
                        "$type": "ResourcePath",
                        "$storage": "string",
                        "$value": "engine\\materials\\multilayered.mt"
                        },
                    "Flags": "Default"
                    },
=======
                "audioTag": cname_entry("None"),
                "baseMaterial": resource_path_entry(
                    "engine\\materials\\multilayered.mt"
                ),
>>>>>>> Stashed changes
                "cookingPlatform": "PLATFORM_PC",
                "enableMask": 0,
                "metadata": None,
                "resourceVersion": 4,
                "values": [
                    {
                        "$type": "rRef:Multilayer_Mask",
<<<<<<< Updated upstream
                        "MultilayerMask": {
                            "DepotPath": {
                                "$type": "ResourcePath",
                                "$storage": "string",
                                "$value": mlmask
                                },
                            "Flags": "Default"
                            }
                        },
                    {
                        "$type": "rRef:Multilayer_Setup",
                        "MultilayerSetup": {
                            "DepotPath": {
                                "$type": "ResourcePath",
                                "$storage": "string",
                                "$value": mlsetup
                                },
                            "Flags": "Default"
                            }
                        },
                    {
                        "$type": "rRef:ITexture",
                        "GlobalNormal": {
                            "DepotPath": {
                                "$type": "ResourcePath",
                                "$storage": "string",
                                "$value": gnormal
                                },
                            "Flags": "Default"
                            }
                        }
                    ]
                },
            "EmbeddedFiles": []
            }
        }

    try:
        atomic_write_json(filepath, data, indent=2)

        success_message = "Exported Material from " + active_material.name + " on " + active_object.name
        self.report({'INFO'}, success_message)

        # LLM generated this - looks good maybe could use elsewhere
        # context.window_manager.popup_menu(
        #     lambda self, ctx: self.layout.label(text=f"Saved to {os.path.basename(filepath)}"), 
        #     title="Export Successful", 
        #     icon='CHECKMARK'
        # )
        return {'FINISHED'}

    except Exception as e:
        print(f"Failed to write file: {e}")
        self.report({'ERROR'}, f"Failed to write material: {e}")
        return {'CANCELLED'}
=======
                        "MultilayerMask": resource_path_entry(mlmask),
                    },
                    {
                        "$type": "rRef:Multilayer_Setup",
                        "MultilayerSetup": resource_path_entry(mlsetup),
                    },
                    {
                        "$type": "rRef:ITexture",
                        "GlobalNormal": resource_path_entry(gnormal),
                    },
                ],
            },
            "EmbeddedFiles": [],
        },
    }

    atomic_write_json(filepath, data, indent=2)
    return OperationResult.finished(
        f"Exported material {active_material.name} on {active_object.name}."
    )
>>>>>>> Stashed changes
