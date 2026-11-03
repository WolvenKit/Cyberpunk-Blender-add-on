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

    mlmask = active_material["MultilayerMask"]
    mlsetup = active_material["MLSetup"]
    gnormal = active_material["GlobalNormal"]
    if not mlsetup:
        return OperationResult.cancelled(
            f"{active_material.name} has no MLSETUP of its own yet; export its MLSETUP first."
        )

    data = {
        "Header": cr2w_header(filepath),
        "Data": {
            "Version": 195,
            "BuildVersion": 0,
            "RootChunk": {
                "$type": "CMaterialInstance",
                "audioTag": cname_entry("None"),
                "baseMaterial": resource_path_entry(
                    "engine\\materials\\multilayered.mt"
                ),
                "cookingPlatform": "PLATFORM_PC",
                "enableMask": 0,
                "metadata": None,
                "resourceVersion": 4,
                "values": [
                    {
                        "$type": "rRef:Multilayer_Mask",
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
