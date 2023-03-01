bl_info = {
    "name": "Cyberpunk 2077 glTF Importer",
    "author": "HitmanHimself, Turk, Jato, dragonzkiller, kwekmaster, glitchered, Simarilius",
    "version": (1, 2, 0),
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
from .main.entity_import import *
from .main.sector_import import *

icons_dir = os.path.join(os.path.dirname(__file__), "icons")
custom_icon_col = {}

def SetCyclesRenderer(set_gi_params=False):
    # set the render engine for all scenes to Cycles
    for scene in bpy.data.scenes:
        scene.render.engine = 'CYCLES'

    if set_gi_params:
        cycles = bpy.context.scene.cycles
        cycles.max_bounces = 32
        cycles.caustics_reflective = True
        cycles.caustics_refractive = True
        cycles.diffuse_bounces = 32
        cycles.glossy_bounces = 32
        cycles.transmission_bounces = 32
        cycles.volume_bounces = 32
        cycles.transparent_max_bounces = 32
        cycles.use_fast_gi = False
        cycles.ao_bounces = 1
        cycles.ao_bounces_render = 1

class CP77EntityImport(bpy.types.Operator,ImportHelper):

    bl_idname = "io_scene_gltf.cp77entity"
    bl_label = "Import Ent from JSON"
    
    filter_glob: StringProperty(
        default="*.json",
        options={'HIDDEN'},
        )

    filepath: StringProperty(name= "Filepath",
                             subtype = 'FILE_PATH')

    appearances: StringProperty(name= "Appearances",
                                description="Entity Appearances to extract. Needs appearanceName from ent. Comma seperate multiples",
                                default="default",
                                )
    exclude_meshes: StringProperty(name= "Meshes_to_Exclude",
                                description="Meshes to skip during import",
                                default="",
                                options={'HIDDEN'})
    
    update_gi: BoolProperty(name="Update Global Illumination",default=True,description="Update Cycles global illumination options for transparency fixes and higher quality renders")

    def execute(self, context):
        SetCyclesRenderer(self.update_gi)

        apps=self.appearances.split(",")
        print('apps - ',apps)
        excluded=self.appearances.split(",")
        bob=self.filepath
        print('Bob - ',bob)
        importEnt( bob, apps, excluded)

        return {'FINISHED'}

class CP77StreamingSectorImport(bpy.types.Operator,ImportHelper):

    bl_idname = "io_scene_gltf.cp77sector"
    bl_label = "Import All StreamingSectors from project"
    
    filter_glob: StringProperty(
        default="*.cpmodproj",
        options={'HIDDEN'},
        )
    
    filepath: StringProperty(name= "Filepath",
                             subtype = 'FILE_PATH')

    want_collisions: BoolProperty(name="Import Collisions",default=False,description="Import Box and Capsule Collision objects (mesh not yet supported)")
    am_modding: BoolProperty(name="Generate New Collectors",default=False,description="Generate _new collectors for sectors to allow modifications to be saved back to game")
    
    def execute(self, context):
        bob=self.filepath
        print('Importing Sectors from project - ',bob)
        importSectors( bob, self.want_collisions, self.am_modding)
        return {'FINISHED'}

# Material Sub-panel
class CP77_PT_ImportWithMaterial(bpy.types.Panel):
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
        layout.prop(operator, 'hide_armatures')
        layout.prop(operator, 'update_gi')


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

    hide_armatures: BoolProperty(name="Hide Armatures",default=True,description="Hide the armatures on imported meshes")

    update_gi: BoolProperty(name="Update Global Illumination",default=True,description="Update Cycles global illumination options for transparency fixes and higher quality renders")
    
    filepath: StringProperty(subtype = 'FILE_PATH')

    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: StringProperty()
    
    appearances: StringProperty(name= "Appearances",
                                description="Appearances to extract with models",
                                default="ALL",
                                options={'HIDDEN'}
                                )

    #kwekmaster: refactor UI layout from the operator.
    def draw(self, context):
        pass

    def execute(self, context):
        SetCyclesRenderer(self.update_gi)

        loadfiles=self.files
        appearances=self.appearances.split(",")
        for f in appearances:
            print(f)
        
        # prevent crash if no directory supplied when using filepath
        if len(self.directory)>0:
            directory = self.directory
        else:
            directory = os.path.dirname(self.filepath)
            
        #if no files were supplied and a filepath is populate the files from the filepath
        if len(loadfiles)==0 and len(self.filepath)>0:
            f={}
            f['name']=os.path.basename(self.filepath)
            loadfiles=(f,)
            
        
        for f in loadfiles:
            filepath = os.path.join(directory, f['name'])
                        
            gltf_importer = glTFImporter(filepath, { "files": None, "loglevel": 0, "import_pack_images" :True, "merge_vertices" :False, "import_shading" : 'NORMALS', "bone_heuristic":'TEMPERANCE', "guess_original_bind_pose" : False, "import_user_extensions": ""})
            gltf_importer.read()
            gltf_importer.checks()
            
            #kwekmaster: modified to reflect user choice
            print(filepath + " Loaded; With materials: "+str(self.with_materials))

            existingMeshes = bpy.data.meshes.keys()
           
            existingMaterials = bpy.data.materials.keys()

            BlenderGlTF.create(gltf_importer)

            imported= context.selected_objects #the new stuff should be selected 
            collection = bpy.data.collections.new(os.path.splitext(f['name'])[0])
            bpy.context.scene.collection.children.link(collection)
            for o in imported:
                for parent in o.users_collection:
                        parent.objects.unlink(o)
                collection.objects.link(o)  
                #print('o.name - ',o.name)
                if 'Armature' in o.name:
                    o.hide_set(self.hide_armatures)
                
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

               
                json_apps=obj['Appearances']
                # fix the app names as for some reason they have their index added on the end.
                appkeys=[k for k in json_apps.keys()]
                for i,k in enumerate(appkeys):
                    json_apps[k[:-1*len(str(i))]]=json_apps.pop(k)

                validmats={}
                #appearances = ({'name':'short_hair'},{'name':'02_ca_limestone'},{'name':'ml_plastic_doll'},{'name':'03_ca_senna'})
                #if appearances defined populate valid mats with the mats for them, otherwise populate with everything used.

                if len(appearances)>0 and 'ALL' not in appearances:
                    for key in json_apps.keys():
                        if key in  appearances:
                            for m in json_apps[key]:
                                validmats[m]=True
                # there isnt always a default, so if none were listed, or ALL was used, or an invalid one add everything. 
                if len(validmats)==0:
                    for key in json_apps.keys():
                        for m in json_apps[key]:
                            validmats[m]=True

                for mat in validmats.keys():
                    for m in obj['Materials']:
                        if m['Name']==mat:
                            if 'BaseMaterial' in m.keys():
                                 if 'GlobalNormal' in m['Data'].keys():
                                     GlobalNormal=m['Data']['GlobalNormal']
                                 else:
                                     GlobalNormal='None'
                                 if 'MultilayerMask' in m['Data'].keys():
                                     MultilayerMask=m['Data']['MultilayerMask']
                                 else:
                                     MultilayerMask='None'
                                 validmats[mat]={'Name':m['Name'], 'BaseMaterial': m['BaseMaterial'],'GlobalNormal':GlobalNormal, 'MultilayerMask':MultilayerMask}
                            else:
                                print(m.keys())

                MatImportList=[k for k in validmats.keys()]
                

                Builder = MaterialBuilder(obj,BasePath,str(self.image_format))
                
                counter = 0
                bpy_mats=bpy.data.materials
                for name in bpy.data.meshes.keys():
                    if name not in existingMeshes:
                        bpy.data.meshes[name].materials.clear()
                        if gltf_importer.data.meshes[counter].extras is not None: #Kwek: I also found that other material hiccups will cause the Collection to fail
                            for matname in gltf_importer.data.meshes[counter].extras["materialNames"]:
                                if matname in validmats.keys():
                                    #print('matname: ',matname, validmats[matname])
                                    m=validmats[matname]
                                    if matname in bpy_mats.keys() and matname[:5]!='Atlas' and bpy_mats[matname]['BaseMaterial']==m['BaseMaterial'] and bpy_mats[matname]['GlobalNormal']==m['GlobalNormal'] and bpy_mats[matname]['MultilayerMask']==m['MultilayerMask'] :
                                        bpy.data.meshes[name].materials.append(bpy_mats[matname])
                                    elif matname in bpy_mats.keys() and matname[:5]=='Atlas' and bpy_mats[matname]['BaseMaterial']==m['BaseMaterial'] and bpy_mats[matname]['DiffuseMap']==m['DiffuseMap'] :
                                        bpy.data.meshes[name].materials.append(bpy_mats[matname])
                                    else:
                                        if matname in validmats.keys():
                                            index = 0
                                            for rawmat in obj["Materials"]:
                                                if rawmat["Name"] == matname :
                                                    try:
                                                        bpymat = Builder.create(index)
                                                        if bpymat:
                                                            bpymat['BaseMaterial']=validmats[matname]['BaseMaterial']
                                                            bpymat['GlobalNormal']=validmats[matname]['GlobalNormal']
                                                            bpymat['MultilayerMask']=validmats[matname]['MultilayerMask']
                                                            bpy.data.meshes[name].materials.append(bpymat)
                                                    except FileNotFoundError as fnfe:
                                                        #Kwek -- finally, even if the Builder couldn't find the materials, keep calm and carry on
                                                        #print(str(fnfe))
                                                        pass                                            
                                                index = index + 1
                                else:
                                    #print(matname, validmats.keys())
                                    pass
                            
                        counter = counter + 1

                if not self.exclude_unused_mats:
                    index = 0
                    for rawmat in obj["Materials"]:
                        if rawmat["Name"] not in  bpy.data.materials.keys() and ((rawmat["Name"] in MatImportList) or len(MatImportList)<1):
                            Builder.create(index)
                        index = index + 1
                        
        return {'FINISHED'}

def menu_func_import(self, context):
    self.layout.operator(CP77Import.bl_idname, text="Cyberpunk GLTF (.gltf/.glb)", icon_value=custom_icon_col["import"]['WKIT'].icon_id)
    self.layout.operator(CP77EntityImport.bl_idname, text="Cyberpunk Entity (.json)", icon_value=custom_icon_col["import"]['WKIT'].icon_id)
    self.layout.operator(CP77StreamingSectorImport.bl_idname, text="Cyberpunk StreamingSector", icon_value=custom_icon_col["import"]['WKIT'].icon_id)

#kwekmaster - Minor Refactoring 
classes = (
    CP77Import,
    CP77EntityImport,
    CP77_PT_ImportWithMaterial,
    CP77StreamingSectorImport,
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
