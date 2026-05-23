import bpy
import json
import os
from datetime import datetime

def cp77_materialinstance_export(self,context, filepath):
    active_object = context.active_object
    active_material = active_object.active_material

    mlmask = active_material["MultilayerMask"]
    mlsetup = active_material["MLSetup"]
    gnormal = active_material["GlobalNormal"]

    data = {
        "Header": {
            "WolvenKitVersion": "8.17.2",
            "WKitJsonVersion": "0.0.9",
            "GameVersion": 2310,
            "ExportedDateTime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "DataType": "CR2W",
            "ArchiveFileName": ""
        },
        "Data": {
            "Version": 195,
            "BuildVersion": 0,
            "RootChunk": {
                "$type": "CMaterialInstance",
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
                "cookingPlatform": "PLATFORM_PC",
                "enableMask": 0,
                "metadata": None,
                "resourceVersion": 4,
                "values": [
                    {
                        "$type": "rRef:Multilayer_Mask",
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
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

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
        return {'CANCELLED'}