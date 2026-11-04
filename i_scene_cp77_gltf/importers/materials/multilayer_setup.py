import os

import bpy
from bpy_extras.io_utils import ImportHelper

from ...assetio.catalog import ResourceKind
from ...assetio.repository import ResourceLoadError
from ...blender.transactions import track_created_datablock
from ...core.log import get_logger
from ...core.notifications import import_operation, report
from ...material_types.multilayered import Multilayered
from ...materials.resources import load_material_document

_LOG = get_logger(__name__)


class CP77ImportMLSetup(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.mlsetup"
    bl_label = "Import MLSetup and Create Plane"
    filename_ext = ".json"

    filter_glob: bpy.props.StringProperty(
        default="*.mlsetup.json",
        options={"HIDDEN"},
    )

    @import_operation
    def execute(self, context):
        filepath = self.filepath
        try:
            mlsetup_document = load_material_document(
                filepath, expected_kind=ResourceKind.MLSETUP, required=True
            )
        except ResourceLoadError as error:
            report(
                self,
                "ERROR",
                f"MLSetup document could not be loaded: {error}",
                logger=_LOG,
                error=error,
            )
            return {"CANCELLED"}
        base_path = os.path.dirname(filepath)
        multilayered = Multilayered(base_path, "PNG", base_path)
        mat_name = os.path.splitext(os.path.basename(filepath))[0]
        mat = track_created_datablock(
            "materials",
            bpy.data.materials.new(mat_name),
        )
        mat.use_nodes = True
        multilayered.create(mlsetup_document.payload["Data"], mat)

        try:
            result = bpy.ops.mesh.primitive_plane_add(size=2)
        except RuntimeError as error:
            report(
                self,
                "ERROR",
                f"Could not create the MLSetup preview plane: {error}",
                logger=_LOG,
                error=error,
            )
            return {"CANCELLED"}
        plane = context.active_object
        if "FINISHED" not in result or plane is None or plane.type != "MESH":
            report(
                self,
                "ERROR",
                "Blender did not create a valid MLSetup preview mesh.",
                logger=_LOG,
            )
            return {"CANCELLED"}
        plane = track_created_datablock("objects", plane)
        track_created_datablock("meshes", plane.data)
        if plane.data.materials:
            plane.data.materials[0] = mat
        else:
            plane.data.materials.append(mat)
        if not plane.data.uv_layers:
            plane.data.uv_layers.new(name="UVMap")
        uv_layer = plane.data.uv_layers.active.data
        uv_coords = ((0, 0), (1, 0), (1, 1), (0, 1))
        for loop in plane.data.loops:
            uv_layer[loop.index].uv = uv_coords[loop.index % 4]
        return {"FINISHED"}
