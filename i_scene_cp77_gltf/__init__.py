bl_info = {
    "name": "Cyberpunk 2077 glTF Importer",
    "author": "HitmanHimself, Turk",
    "version": (0, 0, 1),
    "blender": (2, 92, 0),
    "location": "File > Import-Export",
    "description": "Import WolvenKit Cyberpunk2077 glTF Models With Materials",
    "warning": "",
    "category": "Import-Export",
}
import bpy
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
from io_scene_gltf2.blender.imp.gltf2_blender_gltf import BlenderGlTF
from io_scene_gltf2.blender.imp.gltf2_blender_mesh import BlenderMesh
from .material_types.multilayer import Multilayered
import os
from .main.setup import createMaterials
class CP77Import(bpy.types.Operator,ImportHelper):
    bl_idname = "io_scene_gltf.cp77"
    bl_label = "Import glTF"
    filter_glob: StringProperty(
        default="*.gltf;*.glb",
        options={'HIDDEN'},
        )
    filepath: StringProperty(subtype = 'FILE_PATH')
    def draw(self, context):
        layout = self.layout
    def execute(self, context):
        gltf_importer = glTFImporter(self.filepath, { "files": None, "loglevel": 0, "import_pack_images" :True, "merge_vertices" :False, "import_shading" : 'NORMALS', "bone_heuristic":'TEMPERANCE', "guess_original_bind_pose" : False})
        gltf_importer.read()
        gltf_importer.checks()

        obj = gltf_importer.data.extras
        BasePath = os.path.splitext(self.filepath)[0] + "_Textures\\"
        createMaterials(obj,BasePath)

        BlenderGlTF.set_convert_functions(gltf_importer)
        BlenderGlTF.pre_compute(gltf_importer)
        for i in range(0,len(gltf_importer.data.meshes)):
            bpymesh = BlenderMesh.create(gltf_importer,i,None)
            bpymesh.materials.clear()
            for e in range (0,len(gltf_importer.data.meshes[i].extras["materialNames"])):
                bpymesh.materials.append(bpy.data.materials.get(gltf_importer.data.meshes[i].extras["materialNames"][e]))
            mesh_object = bpy.data.objects.new(name=gltf_importer.data.meshes[i].name, object_data=bpymesh)
            bpy.context.view_layer.active_layer_collection.collection.objects.link(mesh_object)

        return {'FINISHED'}

def menu_func_import(self, context):
    self.layout.operator(CP77Import.bl_idname, text="Cyberpunk GLTF (.gltf/.glb)")
def register():
    bpy.utils.register_class(CP77Import)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    
def unregister():
    bpy.utils.unregister_class(CP77Import)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
        
if __name__ == "__main__":
    register()