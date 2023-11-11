import bpy
import os
import json
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
from io_scene_gltf2.blender.imp.gltf2_blender_gltf import BlenderGlTF
from ..main.setup import MaterialBuilder
from ..main.common import json_ver_validate
from ..main.common import UV_by_bounds
from .attribute_import import manage_garment_support

def CP77GLBimport(self, exclude_unused_mats=True, image_format='png', with_materials=True, filepath='', hide_armatures=True, update_gi=True, import_garmentsupport=False, files=[], directory='', appearances=[]):
    
    context=bpy.context
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
        print(filepath + " Loaded; With materials: "+str(with_materials))
        existingMeshes = bpy.data.meshes.keys()
       
        existingMaterials = bpy.data.materials.keys()
        BlenderGlTF.create(gltf_importer)
        imported= context.selected_objects #the new stuff should be selected 
        if f['name'][:7]=='terrain':
            UV_by_bounds(imported)
        collection = bpy.data.collections.new(os.path.splitext(f['name'])[0])
        bpy.context.scene.collection.children.link(collection)
        for o in imported:
            for parent in o.users_collection:
                    parent.objects.unlink(o)
            collection.objects.link(o)  
            #print('o.name - ',o.name)
            if 'Armature' in o.name:
                o.hide_set(hide_armatures)
        collection['orig_filepath']=filepath
        for name in bpy.data.materials.keys():
            if name not in existingMaterials:
                bpy.data.materials.remove(bpy.data.materials[name], do_unlink=True, do_id_user=True, do_ui_user=True)
        
        if import_garmentsupport:
            manage_garment_support(existingMeshes, gltf_importer)
        BasePath = os.path.splitext(filepath)[0]
        #Kwek: Gate this--do the block iff corresponding Material.json exist 
        #Kwek: was tempted to do a try-catch, but that is just La-Z
        #Kwek: Added another gate for materials
        if with_materials and os.path.exists(BasePath + ".Material.json"):
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
            
            Builder = MaterialBuilder(obj,DepotPath,str(image_format),BasePath)
            
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
                                                        if 'no_shadows' in bpymat.keys() and bpymat['no_shadows']:
                                                            bpy.data.objects[name].visible_shadow=False
                                                except FileNotFoundError as fnfe:
                                                    #Kwek -- finally, even if the Builder couldn't find the materials, keep calm and carry on
                                                    #print(str(fnfe))
                                                    pass                                            
                                            index = index + 1
                            else:
                                #print(matname, validmats.keys())
                                pass
                        
                    counter = counter + 1
            if not exclude_unused_mats:
                index = 0
                for rawmat in obj["Materials"]:
                    if rawmat["Name"] not in  bpy.data.materials.keys() and ((rawmat["Name"] in MatImportList) or len(MatImportList)<1):
                        Builder.create(index)
                    index = index + 1