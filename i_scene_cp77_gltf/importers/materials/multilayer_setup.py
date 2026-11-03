import os

import bpy
from bpy_extras.io_utils import ImportHelper

from ...blender.transactions import track_created_datablock
from ...assetio.catalog import ResourceKind
from ...materials.resources import load_material_document
from ...material_types.multilayered import Multilayered


class CP77ImportMLSetup(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.mlsetup"
    bl_label = "Import MLSetup and Create Plane"
    filename_ext = ".json"

    filter_glob: bpy.props.StringProperty(
        default="*.mlsetup.json",
        options={'HIDDEN'},
    )

    def execute(self, context):
        filepath = self.filepath
        mlsetup_document = load_material_document(
            filepath,
            expected_kind=ResourceKind.MLSETUP,
        )
        if mlsetup_document is None:
            self.report({'ERROR'}, "MLSetup document could not be loaded")
            return {'CANCELLED'}
        base_path = os.path.dirname(filepath)
        multilayered = Multilayered(base_path, 'PNG', base_path)
        mat_name = os.path.splitext(os.path.basename(filepath))[0]
        mat = track_created_datablock(
            "materials",
            bpy.data.materials.new(mat_name),
        )
        mat.use_nodes = True
        multilayered.create(mlsetup_document.payload["Data"], mat)

        bpy.ops.mesh.primitive_plane_add(size=2)
        plane = track_created_datablock("objects", context.active_object)
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
        return {'FINISHED'}


def import_multilayer_setup():
    return bpy.ops.import_scene.mlsetup('INVOKE_DEFAULT')
