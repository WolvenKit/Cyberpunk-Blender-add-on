# Import a mlsetup file
# needs a mesh to apply to so a plane is created
import bpy
import os
import json
from ..material_types.multilayered import Multilayered

def import_mlsetup_and_create_plane():
    # Prompt user for .mlsetup.json file
    from bpy_extras.io_utils import ImportHelper
    class ImportMLSetupOperator(bpy.types.Operator, ImportHelper):
        bl_idname = "import_scene.mlsetup"
        bl_label = "Import MLSetup and Create Plane"
        filename_ext = ".json"
        filter_glob: bpy.props.StringProperty(default="*.mlsetup.json", options={'HIDDEN'})

        def execute(self, context):
            filepath = self.filepath
            # Load the mlsetup JSON
            with open(filepath, 'r') as f:
                mlsetup_data = json.load(f)
            # Extract paths
            base_path = os.path.dirname(filepath)
            image_format = 'PNG'  # Or detect from JSON or user input
            proj_path = base_path  # Or set as needed

            # Create the material using Multilayered
            multilayered = Multilayered(base_path, image_format, proj_path)
            mat_name = os.path.splitext(os.path.basename(filepath))[0]
            mat = bpy.data.materials.new(mat_name)
            mat.use_nodes = True
            multilayered.create(mlsetup_data["Data"], mat)

            # Create a plane and assign the material
            bpy.ops.mesh.primitive_plane_add(size=2)
            plane = bpy.context.active_object
            if plane.data.materials:
                plane.data.materials[0] = mat
            else:
                plane.data.materials.append(mat)

            # Ensure 0-1 UV mapping
            if not plane.data.uv_layers:
                plane.data.uv_layers.new(name="UVMap")
            uv_layer = plane.data.uv_layers.active.data
            # Set UVs for a quad (plane)
            uv_coords = [(0,0), (1,0), (1,1), (0,1)]
            for i, loop in enumerate(plane.data.loops):
                uv_layer[loop.index].uv = uv_coords[i % 4]

            return {'FINISHED'}

    bpy.utils.register_class(ImportMLSetupOperator)
    bpy.ops.import_scene.mlsetup('INVOKE_DEFAULT')