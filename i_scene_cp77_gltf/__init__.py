bl_info = {
    "name": "Cyberpunk 2077 IO Suite",
    "author": "HitmanHimself, Turk, Jato, dragonzkiller, kwekmaster, glitchered, Simarilius, The Magnificent Doctor Presto",
    "version": (1,4, 0),
    "blender": (3, 1, 0),
    "location": "File > Import-Export",
    "description": "Import and Export WolvenKit Cyberpunk2077 gLTF models with materials, Import .streamingsector and .ent from .json",
    "warning": "",
    "category": "Import-Export",}


import bpy
import bpy.utils.previews
import json
import os
import textwrap

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
from .main.attribute_import import manage_garment_support
from .main.sector_import import *
from bpy_extras.io_utils import ExportHelper
from .main.exporters import *
from .main.common import json_ver_validate
from .main.collisions import CP77CollisionGen
from .main.animtools import play_anim 


### plugin preferences class to allow for personalized used settings - this needs to be commented out 
### or hooked up to something
class CP77IOSuitePreferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    experimental_features: bpy.props.BoolProperty(
    name= "Enable Experimental Features",
    description="Experimental Features for Mod Developers, may encounter bugs",
    default=False,
    )
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "experimental_features")


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
       

icons_dir = os.path.join(os.path.dirname(__file__), "icons")
custom_icon_col = {}


### allow deleting animations from the animset panel, regardless of editor context
class CP77AnimsDelete(bpy.types.Operator):

    bl_idname = 'cp77.delete_anims'
    bl_label = "Delete an action from the animslist"
    bl_options = {'INTERNAL', 'UNDO'}

    name: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.animation_data

    def execute(self, context):
        obj = context.active_object
        action = bpy.data.actions.get(self.name, None)
        if not action:
            return {'CANCELLED'}

        bpy.data.actions.remove(action)

        return {'FINISHED'}
    

## this class is where most of the function is so far - play/pause 
## Todo: fix renaming actions from here
class CP77Animset(bpy.types.Operator):

    bl_idname = 'cp77.set_animset'
    bl_label = "Available Animsets"
    bl_options = {'INTERNAL', 'UNDO'}

    name: bpy.props.StringProperty(options={'HIDDEN'})
    new_name: bpy.props.StringProperty(name="New name", default="")
    play: bpy.props.BoolProperty(options={'HIDDEN'}, default=False)

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.animation_data
    
    def execute(self, context):
        obj = context.active_object
        if obj and obj.type == 'ARMATURE':
            if self.play:
                # Pass the animation name to the play_anim function
                play_anim(self, context, self.name)
            return {'FINISHED'}5

### Draw a panel within the modtools tree to store anims functions
class CP77_PT_AnimsPanel(bpy.types.Panel):
    bl_parent_id = "CP77_PT_modtools"
    bl_idname = "CP77_PT_animspanel"
    bl_space_type = "VIEW_3D"
    bl_label = "Animation Tools"
    bl_region_type = "UI"
    bl_category = "CP77 Modding"

    name: bpy.props.StringProperty(options={'HIDDEN'})

## make sure the context is unrestricted as possible, ensure there's an armature selected 
    def draw(self, context):
        layout = self.layout 
        if bpy.context.mode in {'OBJECT', 'POSE', 'EDIT_ARMATURE'}:
            obj = bpy.context.active_object
            if obj and obj.type == 'ARMATURE':
                available_anims = bpy.data.actions
                active_action = obj.animation_data.action if obj.animation_data else None

                box = layout.box()
                row = box.row(align=True)
                row.label(text='Animsets', icon_value=custom_icon_col["import"]['WKIT'].icon_id)
                if available_anims:
                    col = box.column(align=True)
                    for action in available_anims:
                        selected = action == active_action
                        row = col.row(align=True)
                        sub = row.column(align=True)
                        sub.ui_units_x = 1.0
                        if selected and context.screen.is_animation_playing:
                            op = sub.operator('screen.animation_cancel', icon='PAUSE', text="", emboss=False)
                            op.restore_frame = False
                        else:
                            icon = 'PLAY' if selected else 'TRIA_RIGHT'
                            op = sub.operator('cp77.set_animset', icon=icon, text="", emboss=False)
                            op.name = action.name
                            op.play = True

                            op = row.operator('cp77.set_animset', text=action.name)
                            op.name = action.name
                            op.play = False
                            row.operator('cp77.delete_anims', icon='X', text="").name = action.name


class CP77CollisionGenerator(bpy.types.Operator):
    bl_idname = "generate_cp77.collisions"
    bl_parent_id = "CP77_PT_collisions"
    bl_label = "Generate Convex Collider"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CP77 Modding"


    def draw(self, context):
        layout = self.layout

    def execute(self, context):
        props = context.scene.cp77_collision_tools_panel_props
        CP77CollisionGen(context, props.sampleverts)
        return {"FINISHED"}
    

class CP77CollisionExport(bpy.types.Operator):
    bl_idname = "export_scene.collisions"
    bl_label = "Export Collisions to .JSON"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CP77 Modding"
    bl_parent_id = "CP77_PT_collisions"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
  
    def execute(self, context):
        cp77_collision_export(self.filepath)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        layout = self.layout


class CP77_PT_CollisionToolsPanelProps(bpy.types.PropertyGroup):
    sampleverts: bpy.props.StringProperty(
        name="Vertices to Sample",
        description="This is the number of vertices in your new collider",
        default="100",
    )


class CP77_PT_CollisionTools(bpy.types.Panel):
    bl_parent_id = "CP77_PT_modtools"
    bl_label = "Collision Tools"
    bl_idname = "CP77_PT_collisions"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CP77 Modding"

    def draw(self, context):
        layout = self.layout
        props = context.scene.cp77_collision_tools_panel_props
        
        layout.prop(props, "sampleverts")
        layout.operator("export_scene.collisions")
        layout.operator("generate_cp77.collisions")



class CP77_PT_ModTools(bpy.types.Panel):
    bl_label = "Cyberpunk Modding Tools"
    bl_idname = "CP77_PT_modtools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_category = "CP77Modding"

    def draw(self, context):
        layout = self.layout


## adds a message box for the exporters to use for error notifications, will also be used later for redmod integration    
class ShowMessageBox(bpy.types.Operator):
    bl_idname = "cp77.message_box"
    bl_label = "Message"

    message: bpy.props.StringProperty(default="")

    def execute(self, context):
        self.report({'INFO'}, self.message)
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=300)

    def draw(self, context):
        wrapp = textwrap.TextWrapper(width=50) #50 = maximum length       
        wList = wrapp.wrap(text=self.message) 
        for text in wList: 
            row = self.layout.row(align = True)
            row.alignment = 'EXPAND'
            row.label(text=text)     
        
class CP77GLBExport(bpy.types.Operator,ExportHelper):
  ### cleaned this up and moved most code to exporters.py
    bl_idname = "export_scene.cp77_glb"
    bl_label = "Export for Cyberpunk"
    bl_options = {'REGISTER','UNDO'}
    filename_ext = ".glb"
   ### adds a checkbox for anim export settings
    filter_glob: StringProperty(default="*.glb", options={'HIDDEN'})
    export_poses: BoolProperty(
        name="As Photomode Pose",
        default=False,
        description="Use this option if you are exporting anims to be imported into wkit as .anim"
    )
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "export_poses")
        
    def execute(self, context):
        export_cyberpunk_glb(context, self.filepath, self.export_poses)
        return {'FINISHED'}


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
    with_materials: BoolProperty(name="With Materials",default=True,description="Import Wolvenkit-exported materials")   
    include_collisions: BoolProperty(name="Include Vehicle Collisions",default=False,description="Use this option if you want to include the .phys collision info for vehicle modding")
     
    def execute(self, context):
        SetCyclesRenderer(self.update_gi)

        apps=self.appearances.split(",")
        print('apps - ',apps)
        excluded=""
        bob=self.filepath
        #print('Bob - ',bob)
        importEnt( bob, apps, excluded,self.with_materials, self.include_collisions)

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
    with_materials: BoolProperty(name="With Materials",default=False,description="Import Wolvenkit-exported materials")

    def execute(self, context):
        bob=self.filepath
        print('Importing Sectors from project - ',bob)
        importSectors( bob, self.want_collisions, self.am_modding, self.with_materials)
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
        layout.prop(operator, 'import_garmentsupport')


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

    import_garmentsupport: BoolProperty(name="Import Garment Support (Experimental)",default=True,description="Imports Garment Support mesh data as color attributes")
    
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

            collection['orig_filepath']=filepath    
            for name in bpy.data.materials.keys():
                if name not in existingMaterials:
                    bpy.data.materials.remove(bpy.data.materials[name], do_unlink=True, do_id_user=True, do_ui_user=True)
            
            if self.import_garmentsupport:
                manage_garment_support(existingMeshes, gltf_importer)

            BasePath = os.path.splitext(filepath)[0]
            #Kwek: Gate this--do the block iff corresponding Material.json exist 
            #Kwek: was tempted to do a try-catch, but that is just La-Z
            #Kwek: Added another gate for materials
            if self.with_materials and os.path.exists(BasePath + ".Material.json"):
                file = open(BasePath + ".Material.json",mode='r')
                obj = json.loads(file.read())
                file.close()
                valid_json=json_ver_validate(obj)
                if not valid_json:
                    self.report({'ERROR'}, "Incompatible material.json file detected. This add-on version requires materials generated WolvenKit 8.9.1 or higher.")    
                    break

                DepotPath = str(obj["MaterialRepo"])  + "\\"

               
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
                                 if 'DiffuseMap' in m['Data'].keys():
                                     DiffuseMap=m['Data']['DiffuseMap']
                                 else:
                                     DiffuseMap='None'
 
                                 validmats[mat]={'Name':m['Name'], 'BaseMaterial': m['BaseMaterial'],'GlobalNormal':GlobalNormal, 'MultilayerMask':MultilayerMask,'DiffuseMap':DiffuseMap}
                            else:
                                print(m.keys())

                MatImportList=[k for k in validmats.keys()]
                

                Builder = MaterialBuilder(obj,DepotPath,str(self.image_format),BasePath)
                
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
                                    # Should create a list of mis that dont play nice with this and just check if the mat is using one.
                                    if matname in bpy_mats.keys() and 'glass' not in matname and matname[:5]!='Atlas' and 'BaseMaterial' in bpy_mats[matname].keys() and bpy_mats[matname]['BaseMaterial']==m['BaseMaterial'] and bpy_mats[matname]['GlobalNormal']==m['GlobalNormal'] and bpy_mats[matname]['MultilayerMask']==m['MultilayerMask'] :
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
                                                            bpymat['DiffuseMap']=validmats[matname]['DiffuseMap']
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

def menu_func_export(self, context):
    self.layout.operator(CP77GLBExport.bl_idname, text="Export Selection to GLB for Cyberpunk", icon_value=custom_icon_col["import"]['WKIT'].icon_id)
    

bpy.utils.register_class(CP77_PT_CollisionToolsPanelProps)
    
#kwekmaster - Minor Refactoring 
classes = (
    CP77Import,
    CP77EntityImport,
    CP77_PT_ImportWithMaterial,
    CP77StreamingSectorImport,
    CP77GLBExport,
    ShowMessageBox,
    CP77_PT_ModTools,
    CP77_PT_AnimsPanel,
    CP77_PT_CollisionTools,
    CP77CollisionExport,
    CP77CollisionGenerator,
    CP77Animset,
    CP77AnimsDelete,
    CP77IOSuitePreferences,
    )
    

def register():
    custom_icon = bpy.utils.previews.new()
    custom_icon.load("WKIT", os.path.join(icons_dir, "wkit.png"), 'IMAGE')
    custom_icon_col["import"] = custom_icon

    bpy.types.Scene.cp77_collision_tools_panel_props = bpy.props.PointerProperty(type=CP77_PT_CollisionToolsPanelProps) 

    #kwekmaster - Minor Refactoring 
    for cls in classes:
        bpy.utils.register_class(cls)
        
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export) 


def unregister():
    bpy.utils.previews.remove(custom_icon_col["import"])
    del bpy.types.Scene.cp77_collision_tools_panel_props
    
    #kwekmaster - Minor Refactoring 
    for cls in classes:
        bpy.utils.unregister_class(cls)

        
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

    bpy.utils.unregister_class(CP77_PT_CollisionToolsPanelProps)    

if __name__ == "__main__":
    register()
