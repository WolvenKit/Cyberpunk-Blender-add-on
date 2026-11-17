import os

import bpy

from ...assetio.catalog import ResourceKind
from ...assetio.repository import ResourceLoadError
from ...blender.operator_results import OperationResult, require_finished
from ...blender.transactions import (
    snapshot_datablocks,
    track_created_datablock,
    track_created_since,
    transactional,
)
from ...material_types.multilayered import Multilayered
from ...materials.resources import load_material_document

_PLANE_UVS = ((0, 0), (1, 0), (1, 1), (0, 1))


@transactional("MLSetup import")
def import_multilayer_setup(context, filepath) -> OperationResult:
    try:
        document = load_material_document(
            filepath, expected_kind=ResourceKind.MLSETUP, required=True
        )
    except ResourceLoadError as error:
        return OperationResult.cancelled(
            f"MLSetup document could not be loaded: {error}", error=error
        )
    base_path = os.path.dirname(filepath)
    material = track_created_datablock(
        "materials",
        bpy.data.materials.new(os.path.splitext(os.path.basename(filepath))[0]),
    )
    material.use_nodes = True
    Multilayered(base_path, "PNG", base_path).create(document.payload["Data"], material)

    before = snapshot_datablocks()
    result = bpy.ops.mesh.primitive_plane_add(size=2)
    track_created_since(before)
    require_finished(result, "Adding the MLSetup preview plane")
    plane = context.active_object
    if plane is None or plane.type != "MESH":
        return OperationResult.cancelled(
            "Blender did not create a valid MLSetup preview mesh."
        )
    if plane.data.materials:
        plane.data.materials[0] = material
    else:
        plane.data.materials.append(material)
    if not plane.data.uv_layers:
        plane.data.uv_layers.new(name="UVMap")
    uv_layer = plane.data.uv_layers.active.data
    for loop in plane.data.loops:
        uv_layer[loop.index].uv = _PLANE_UVS[loop.index % 4]
    return OperationResult.finished()
