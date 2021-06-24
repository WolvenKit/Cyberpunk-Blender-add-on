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
import json
from bpy.props import (StringProperty,EnumProperty)
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
    image_format: EnumProperty(
        name="Textures",
        items=(("png", "Use PNG textures", ""),
                ("dds", "Use DDS textures", ""),
                ("jpg", "Use JPG textures", ""),
                ("tga", "Use TGA textures", ""),
                ("bmp", "Use BMP textures", ""),
                ("jpeg", "Use JPEG textures", "")),
        description="How normals are computed during import",
        default="png")
    filepath: StringProperty(subtype = 'FILE_PATH')
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True

        layout.prop(self, 'image_format')

    def execute(self, context):
        gltf_importer = glTFImporter(self.filepath, { "files": None, "loglevel": 0, "import_pack_images" :True, "merge_vertices" :False, "import_shading" : 'NORMALS', "bone_heuristic":'TEMPERANCE', "guess_original_bind_pose" : False})
        gltf_importer.read()
        gltf_importer.checks()

        BasePath = os.path.splitext(self.filepath)[0] + "\\"
        file = open(BasePath + "Material.json",mode='r')
        obj = json.loads(file.read())
        createMaterials(obj,BasePath,str(self.image_format))

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