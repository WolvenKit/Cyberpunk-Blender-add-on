bl_info = {
    "name": "Cyberpunk 2077 glTF Importer",
    "author": "HitmanHimself, Turk, Jato, dragonzkiller, kwek/kwekmaster, glitchered",
    "version": (1, 0, 9),
    "blender": (3, 1, 0),
    "location": "File > Import-Export",
    "description": "Import WolvenKit Cyberpunk2077 glTF Models With Materials",
    "warning": "",
    "category": "Import-Export",
}

import bpy
import bpy.utils.previews
import json
import os

from bpy.props import (
    StringProperty,
    EnumProperty,
    BoolProperty,
    CollectionProperty)
from bpy_extras.io_utils import ImportHelper
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
from io_scene_gltf2.blender.imp.gltf2_blender_gltf import BlenderGlTF
from .main.setup import MaterialBuilder

icons_dir = os.path.join(os.path.dirname(__file__), "icons")
custom_icon_col = {}

class CP77StreamingSectorImport(bpy.types.Operator,ImportHelper):

    bl_idname = "io_scene_glft.cp77sector"
    bl_label = "Import StreamingSector"
    use_filter_folder = True
    filter_glob: StringProperty(
        default=".",
        options={'HIDDEN'},
        )

    def execute(self, context):
        self.report({'ERROR'}, "Streaming Sector Import is not yet implemented!")
        return {'FINISHED'}

# Material Sub-panel
class CP77ImportWithMaterial(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "With Materials"

    @classmethod
    def poll(cls, context):
        operator = context.space_data.active_operator
        return operator.bl_idname == "IO_SCENE_GLTF_OT_cp77"

    def draw_header(self, context):
        operator = context.space_data.active_operator
        self.layout.prop(operator, "with_materials", text="")

    def draw(self, context):
        operator = context.space_data.active_operator
        layout = self.layout
        layout.enabled = operator.with_materials
        layout.use_property_split = True
        layout.prop(operator, 'exclude_unused_mats')
        layout.prop(operator, 'image_format')


class CP77Import(bpy.types.Operator,ImportHelper):
    bl_idname = "io_scene_gltf.cp77"
    bl_label = "Import glTF"
    bl_description = "Load glTF 2.0 files with Cyberpunk 2077 materials" #Kwek: tooltips towards a more polished UI.
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
    exclude_unused_mats: BoolProperty(name="Exclude Unused Materials",default=True,description="Enabling this options skips all the materials that aren't being used by any mesh")
    
    #Kwekmaster: QoL option to match WolvenKit GUI options - Name change to With Materials
    with_materials: BoolProperty(name="With Materials",default=True,description="Import mesh with Wolvenkit-exported materials")
    
    filepath: StringProperty(subtype = 'FILE_PATH')

    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: StringProperty()

    #kwekmaster: refactor UI layout from the operator.
    def draw(self, context):
        pass

        
        

    def execute(self, context):
        directory = self.directory

        for f in self.files:
            filepath = os.path.join(directory, f.name)
            
            #kwekmaster: modified to reflect user choice
            print(filepath + " Loaded; With materials: "+str(self.with_materials))

            gltf_importer = glTFImporter(filepath, { "files": None, "loglevel": 0, "import_pack_images" :True, "merge_vertices" :False, "import_shading" : 'NORMALS', "bone_heuristic":'TEMPERANCE', "guess_original_bind_pose" : False, "import_user_extensions": ""})
            gltf_importer.read()
            gltf_importer.checks()


            existingMeshes = bpy.data.meshes.keys()
            existingObjects = bpy.data.objects.keys()
            existingMaterials = bpy.data.materials.keys()

            BlenderGlTF.create(gltf_importer)

            for name in bpy.data.materials.keys():
                if name not in existingMaterials:
                    bpy.data.materials.remove(bpy.data.materials[name], do_unlink=True, do_id_user=True, do_ui_user=True)

            BasePath = os.path.splitext(filepath)[0]
            #Kwek: Gate this--do the block iff corresponding Material.json exist 
            #Kwek: was tempted to do a try-catch, but that is just La-Z
            #Kwek: Added another gate for materials
            if self.with_materials and os.path.exists(BasePath + ".Material.json"):
                file = open(BasePath + ".Material.json",mode='r')
                obj = json.loads(file.read())
                BasePath = str(obj["MaterialRepo"])  + "\\"
                
                

                Builder = MaterialBuilder(obj,BasePath,str(self.image_format))

                usedMaterials = {}
                counter = 0
                for name in bpy.data.meshes.keys():
                    if name not in existingMeshes:
                        bpy.data.meshes[name].materials.clear()
                        if gltf_importer.data.meshes[counter].extras is not None: #Kwek: I also found that other material hiccups will cause the Collection to fail
                            for matname in gltf_importer.data.meshes[counter].extras["materialNames"]:
                                if matname not in usedMaterials.keys():
                                    index = 0
                                    for rawmat in obj["Materials"]:
                                        if rawmat["Name"] == matname:
                                            try:
                                                bpymat = Builder.create(index)
                                                bpy.data.meshes[name].materials.append(bpymat)
                                                usedMaterials.update( {matname: bpymat} )
                                            except FileNotFoundError as fnfe:
                                                #Kwek -- finally, even if the Builder couldn't find the materials, keep calm and carry on
                                                print(str(fnfe))
                                                pass                                            
                                        index = index + 1
                                else:
                                    bpy.data.meshes[name].materials.append(usedMaterials[matname])
                            
                        counter = counter + 1

                if not self.exclude_unused_mats:
                    index = 0
                    for rawmat in obj["Materials"]:
                        if rawmat["Name"] not in usedMaterials:
                            Builder.create(index)
                        index = index + 1


            collection = bpy.data.collections.new(os.path.splitext(f.name)[0])
            bpy.context.scene.collection.children.link(collection)

            for name in bpy.data.objects.keys():
                if name not in existingObjects:
                    for parent in bpy.data.objects[name].users_collection:
                        parent.objects.unlink(bpy.data.objects[name])
                    collection.objects.link(bpy.data.objects[name])

        return {'FINISHED'}

def menu_func_import(self, context):
    self.layout.operator(CP77Import.bl_idname, text="Cyberpunk GLTF (.gltf/.glb)", icon_value=custom_icon_col["import"]['WKIT'].icon_id)
    #self.layout.operator(CP77StreamingSectorImport.bl_idname, text="Cyberpunk StreamingSector (.json)")

#kwekmaster - Minor Refactoring 
classes = (
    CP77Import,
    CP77ImportWithMaterial,
#    CP77StreamingSectorImport, #kwekmaster: keeping this in--to mimic previous structure.
)

def register():
    custom_icon = bpy.utils.previews.new()
    custom_icon.load("WKIT", os.path.join(icons_dir, "wkit.png"), 'IMAGE')
    custom_icon_col["import"] = custom_icon

    #kwekmaster - Minor Refactoring 
    for cls in classes:
        bpy.utils.register_class(cls)
        
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    
def unregister():
    bpy.utils.previews.remove(custom_icon_col["import"])

    #kwekmaster - Minor Refactoring 
    for cls in classes:
        bpy.utils.unregister_class(cls)
        
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
        
if __name__ == "__main__":
    register()
