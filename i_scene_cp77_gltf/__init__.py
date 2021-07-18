bl_info = {
    "name": "Cyberpunk 2077 glTF Importer",
    "author": "HitmanHimself, Turk, Jato",
    "version": (1, 0, 1),
    "blender": (2, 93, 0),
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
from .main.setup import MaterialBuilder

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
        description="Texture Format",
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


        existingMeshes = bpy.data.meshes.keys()
        existingObjects = bpy.data.objects.keys()
        existingMaterials = bpy.data.materials.keys()

        BlenderGlTF.create(gltf_importer)

        for name in bpy.data.materials.keys():
            if name not in existingMaterials:
                bpy.data.materials.remove(bpy.data.materials[name], do_unlink=True, do_id_user=True, do_ui_user=True)

        BasePath = os.path.splitext(self.filepath)[0] + "\\"
        file = open(BasePath + "Material.json",mode='r')
        obj = json.loads(file.read())
        BasePath = str(obj["MaterialRepo"])  + "\\"

        Builder = MaterialBuilder(obj,BasePath,str(self.image_format))

        usedMaterials = {}
        counter = 0
        for name in bpy.data.meshes.keys():
            if name not in existingMeshes:
                bpy.data.meshes[name].materials.clear()
                for matname in gltf_importer.data.meshes[counter].extras["materialNames"]:
                    if matname not in usedMaterials.keys():
                        index = 0
                        for rawmat in obj["Materials"]:
                            if rawmat["Name"] == matname:
                                bpymat = Builder.create(index)
                                bpy.data.meshes[name].materials.append(bpymat)
                                usedMaterials.update( {matname: bpymat} )
                            index = index + 1
                    else:
                        bpy.data.meshes[name].materials.append(usedMaterials[matname])
                        
                counter = counter + 1

        index = 0
        for rawmat in obj["Materials"]:
            if rawmat["Name"] not in usedMaterials:
                Builder.create(index)
            index = index + 1


        collection = bpy.data.collections.new(os.path.splitext(os.path.basename(self.filepath))[0])
        bpy.context.scene.collection.children.link(collection)

        for name in bpy.data.objects.keys():
            if name not in existingObjects:
                for parent in bpy.data.objects[name].users_collection:
                    parent.objects.unlink(bpy.data.objects[name])
                collection.objects.link(bpy.data.objects[name])

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