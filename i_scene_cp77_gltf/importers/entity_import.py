# Blender Entity import script by Simarilius
# Updated May 23 with vehicle rig support
import json
import glob
import os
import bpy
import time
from math import sin,cos
from mathutils import Vector, Matrix , Quaternion
import bmesh
from ..main.common import json_ver_validate
from .phys_import import cp77_phys_import
from ..main.collisions import draw_box_collider, draw_capsule_collider, draw_convex_collider, draw_sphere_collider

# The appearance list needs to be the appearanceNames for each ent that you want to import, will import all if not specified
# if you've already imported the body/head and set the rig up you can exclude them by putting them in the exclude_meshes list 
#presto_stash=[]

def importEnt( filepath='', appearances=[], exclude_meshes=[], with_materials=True, include_collisions=False, include_phys=False, include_entCollider=False, inColl=''): 
    
    C = bpy.context
    coll_scene = C.scene.collection
    start_time = time.time()

    before,mid,after=filepath.partition('source\\raw')
    path=before+mid

    ent_name=os.path.basename(filepath)[:-9]
    print('Importing Entity', ent_name)
    with open(filepath,'r') as f: 
        j=json.load(f) 
    valid_json=json_ver_validate(j)
    if not valid_json:
        bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="Incompatible entity json file detected. This add-on version requires materials generated WolvenKit 8.9.1 or higher.")
        return {'CANCELLED'}
     
    ent_apps= j['Data']['RootChunk']['appearances']
    ent_applist=[]
    for app in ent_apps:
        ent_applist.append(app['appearanceName']['$value'])
        #presto_stash.append(ent_apps)
    ent_components= j['Data']['RootChunk']['components']
    ent_component_data= j['Data']['RootChunk']['compiledData']['Data']['Chunks']
    #presto_stash.append(ent_components)    
    ent_complist=[]
    ent_rigs=[]
    ent_colliderComps=[]
    ent_simpleCollComps=[]
    chassis_info=[]  
    for comp in ent_components:
        ent_complist.append(comp['name'])
        if 'rig' in comp.keys():
            print(comp['rig'])
            ent_rigs.append(os.path.join(path,comp['rig']['DepotPath']['$value']))
        if comp['name']['$value'] == 'Chassis':            
            chassis_info = comp
    for comp in ent_component_data:
        if comp['$type'] == 'entColliderComponent':
            ent_colliderComps.append(comp)
        if comp['$type'] == 'entSimpleColliderComponent':
            ent_simpleCollComps.append(comp)
    #print('collider components:', ent_colliderComps)
    #print('simple collider components:', ent_simpleCollComps)
    #    presto_stash.append(ent_rigs)
                
    resolved=[]
    for res_p in j['Data']['RootChunk']['resolvedDependencies']:
        resolved.append(os.path.join(path,res_p['DepotPath']['$value']))
        
    # if no apps requested populate the list with all available.
    if len(appearances[0])==0 or appearances[0]=='ALL':
        appearances=[]
        for app in ent_apps:
            appearances.append(app['appearanceName']['$value'])

    VS=[]
    for x in j['Data']['RootChunk']['components']:
        if 'name' in x.keys() and x['name']['$value']=='vehicle_slots':
            VS.append(x)
    if len(VS)>0:
        vehicle_slots= VS[0]['slots']
    
    # find the appearance file jsons
    app_path = glob.glob(path+"\**\*.app.json", recursive = True)
    if len(app_path)==0:
        print('No Appearance file JSONs found in path')

    # find the meshes
    meshes =  glob.glob(path+"\**\*.glb", recursive = True)
    if len(meshes)==0:
        print('No Meshes found in path')
    mesh_jsons =  glob.glob(path+"\**\*mesh.json", recursive = True)
    
    # find the anims  
    # look through the components and find an anim, and load that, 
    # then check for an anim in the project thats using the rig (some things like the arch bike dont ref the anim in the ent)
    # otherwise just skip this section
    #
    anim_files = glob.glob(path+"\\base\\animations\\"+"\**\*.glb", recursive = True)
    ep1_anim_files = glob.glob(path+"\\ep1\\animations\\"+"\**\*.glb", recursive = True)
    anim_files = anim_files + ep1_anim_files

    rig=None
    bones=None
    chunks=None
    if len(anim_files)>0 and len(ent_rigs)>0: # we have glbs and we have rigs called up in the ent
            # get the armatures already in the model
            oldarms= [x for x in bpy.data.objects if 'Armature' in x.name]
            animsinres=[x for x in anim_files if x[:-3]+'anims' in resolved] 
            if len(animsinres)==0:
                for anim in anim_files:
                    if os.path.exists(anim[:-3]+'anims.json'):
                        with open(anim[:-3]+'anims.json','r') as f: 
                            anm_j=json.load(f) 
                        valid_json=json_ver_validate(anm_j)
                        if not valid_json:
                            bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="Incompatible anim json file detected. This add-on version requires materials generated WolvenKit 8.9.1 or higher.")
                            return {'CANCELLED'}
                        if os.path.join(path,anm_j['Data']['RootChunk']['rig']['DepotPath']['$value']) in ent_rigs:
                            animsinres.append(os.path.join(path,anim))
                           # presto_stash.append(animsinres)
            
            if len(animsinres)>0:
                bpy.ops.io_scene_gltf.cp77(filepath=animsinres[0])
                #find what we just loaded
                arms=[x for x in bpy.data.objects if 'Armature' in x.name and x not in oldarms]
                rig=arms[0]
                bones=rig.pose.bones
                print('anim rig loaded')
                
                if animsinres[0].endswith(".glb"):
                    anim_file_name = (animsinres[0])  
                    rig_file_name = anim_file_name + ".rig.json"
                    rig["animset"] = anim_file_name
                    rig["rig"] = rig_file_name
                    rig["ent"] = ent_name + ".ent.json"
      
    else:
        print('no anim rig found')

    # find the rig json associated with the ent
    rigjsons = glob.glob(path+"\**\*.rig.json", recursive = True)
    rig_j=None
    if len(rigjsons)>0 and len(ent_rigs)>0:
            entrigjsons=[x for x in rigjsons if x[:-5] in ent_rigs] 
            if len(entrigjsons)>0:
                with open(entrigjsons[0],'r') as f: 
                    rig_j=json.load(f)
                    valid_json=json_ver_validate(rig_j)
                    if not valid_json:
                        bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="Incompatible rig json file detected. This add-on version requires materials generated WolvenKit 8.9.1 or higher.")
                        return {'CANCELLED'}
                    rig_j=rig_j['Data']['RootChunk']
                    print('rig json loaded')
    else: 
        print('no rig json loaded')
                
    if len(meshes)<1 or len(app_path)<1:
        print("You need to export the meshes and convert app and ent to json")
        return

    else:
        for x,app_name in enumerate(appearances):
            
            ent_coll = bpy.data.collections.new(ent_name+'_'+app_name)
            if inColl and inColl in coll_scene.children.keys():
                par_coll=bpy.data.collections.get(inColl)
                par_coll.children.link(ent_coll)
            else:
                #link it to the scene
                coll_scene.children.link(ent_coll)  
            # tag it with some custom properties.
            ent_coll['depotPath']=ent_name
            

            enum_items = []
            default_index = None 

            for idx, variant in enumerate(ent_applist):
                enum_items.append((str(idx), variant, f"appearanceName {idx + 1}"))
                if variant == app_name:  # Check if the variant matches the passed app_name
                    default_index = str(idx)  # Set the default index if found

            if default_index is None:
                default_index = '0'

            if len(enum_items)>0:
                bpy.types.Collection.appearanceName = bpy.props.EnumProperty(
                    name="Ent Appearances",
                    items=enum_items,
                    default=default_index,
                )

            comps=[]
            
            if len(ent_apps)>0:
                ent_app_idx=-1
                # Find the appearance in the entity app list
                for i,a in enumerate(ent_apps):
                    if a['appearanceName']['$value']==app_name:
                        print('appearance matched, id = ',i)
                        ent_app_idx=i

                # apparently they sometimes just sack it off and use the name not the appearanceName after all. (single_doors.ent for instance)
                if ent_app_idx<0:
                    for i,a in enumerate(ent_apps):
                        if a['name']['$value']==app_name:
                            print('appearance matched, id = ',i)
                            ent_app_idx=i
                            app_name=a['appearanceName']['$value']

                if ent_app_idx<0 and app_name =='default':
                    ent_default=j['Data']['RootChunk']['defaultAppearance']['$value']
                    for i,a in enumerate(ent_apps):
                        if a['name']['$value']==ent_default:
                            print('appearance matched, id = ',i)
                            ent_app_idx=i
                            app_name=a['appearanceName']['$value']
                            continue
                        if a['name']['$value']==ent_default:
                            print('appearance matched, id = ',i)
                            ent_app_idx=i
                            app_name=a['appearanceName']['$value']
                            continue
                elif ent_app_idx<0:
                    ent_app_idx=0

                app_file = ent_apps[ent_app_idx]['appearanceResource']['DepotPath']['$value']
                appfilepath=os.path.join(path,app_file)+'.json'
                a_j=None        
                if os.path.exists(appfilepath):
                    with open(appfilepath,'r') as a: 
                        a_j=json.load(a)
                    valid_json=json_ver_validate(a_j)
                    if not valid_json:
                        bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="Incompatible app json file detected. This add-on version requires materials generated WolvenKit 8.9.1 or higher.")
                        return {'CANCELLED'}
                    apps=a_j['Data']['RootChunk']['appearances']
                    app_idx=0
                    for i,a in enumerate(apps):
                        #print(i,a['Data']['name'])
                        if a['Data']['name']['$value']==app_name:
                            print('appearance matched, id = ',i)
                            app_idx=i
                    chunks=None
                    if 'Data' in a_j['Data']['RootChunk']['appearances'][app_idx].keys():
                        if a_j['Data']['RootChunk']['appearances'][app_idx]['Data']['components']:
                            comps= a_j['Data']['RootChunk']['appearances'][app_idx]['Data']['components']
                        if 'compiledData' in a_j['Data']['RootChunk']['appearances'][app_idx]['Data'].keys():
                            chunks= a_j['Data']['RootChunk']['appearances'][app_idx]['Data']['compiledData']['Data']['Chunks']
                            print('Chunks found')
                else:
                    print('app file not found -', filepath)
                              
            if len(comps)==0:      
                print('falling back to rootchunk comps')
                comps= j['Data']['RootChunk']['components']

            for c in comps:
                if 'mesh' in c.keys() or 'graphicsMesh' in c.keys():
                   # print(c['mesh']['DepotPath']['$value'])
                    meshname=''
                    if 'mesh' in c.keys() and isinstance( c['mesh']['DepotPath']['$value'], str):
                        m=c['mesh']['DepotPath']['$value']
                        meshname=os.path.basename(m)
                        meshpath=os.path.join(path, m[:-1*len(os.path.splitext(m)[1])]+'.glb')
                    elif 'graphicsMesh' in c.keys() and isinstance( c['graphicsMesh']['DepotPath']['$value'], str):
                        m=c['graphicsMesh']['DepotPath']['$value']
                        meshname=os.path.basename(m)
                        meshpath=os.path.join(path, m[:-1*len(os.path.splitext(m)[1])]+'.glb')
                    if meshname:
                        if meshname not in exclude_meshes:      
                            if os.path.exists(meshpath):
                                #if True:
                                try:
                                    meshApp='default'
                                    if 'meshAppearance' in c.keys():
                                        meshApp=c['meshAppearance']['$value']
                                        #print(meshApp)
                                    try:
                                        bpy.ops.io_scene_gltf.cp77(filepath=meshpath, appearances=meshApp, with_materials=with_materials, update_gi=False,)
                                        for obj in C.selected_objects:            
                                            obj['componentName'] = c['name']['$value']
                                            obj['sourcePath'] = meshpath
                                            obj['meshAppearance'] = meshApp
                                            obj['appResource'] = app_path[0]
                                            obj['entAppearance'] = app_name
                                    except:
                                        print('import threw an error')
                                        continue
                                    objs = C.selected_objects
                                    if meshname=='v_sportbike2_arch_nemesis__ext01_axle_f_a_01':
                                        print('those annoying front forks')
                                                                           
                                    # NEW parentTransform stuff - fixes vehicles being exploded
                                    x=None
                                    y=None
                                    z=None
                                    bindname=None
                                    pt_trans=[0,0,0]
                                    pt_rot=[0,0,0,0]
                                    pt_eul=None
                                    pT=c['parentTransform']
                                    if pT:
                                        pT_HId=pT['HandleRefId']
                                        #print('pT_HId = ',pT_HId)
                                        chunk_pt = 0 
                                        # find the parent transform in the chunks
                                        if chunks:
                                            for chunk in chunks:
                                                if 'parentTransform' in chunk.keys() and isinstance( chunk['parentTransform'], dict):
                                                     #print('pt found')
                                                     if 'HandleId' in chunk['parentTransform'].keys():
                                                
                                                         if chunk['parentTransform']['HandleId']==pT_HId:
                                                             chunk_pt=chunk['parentTransform']
                                                             #print('HandleId found',chunk['parentTransform']['HandleId'])
                                        # if we found it then process it, most chars etc will just skip this                                                     
                                        if chunk_pt:   
                                            #print('in chunk pt processing bindName = ',chunk_pt['Data']['bindName'],' slotname= ',chunk_pt['Data']['slotName'])                                     
                                            # parts have a bindname, and sometimes a slotname
                                            bindname=chunk_pt['Data']['bindName']['$value']
                                            # if it has a bindname of vehicle_slots, you may need to find the bone name in the vehicle slots in the root ent components
                                            # this should have been loaded earlier, check for it in the vehicle slots if not just set to the slot value
                                            if bindname=='vehicle_slots':
                                                if vehicle_slots:
                                                    slotname=chunk_pt['Data']['slotName']['$value']
                                                    for slot in vehicle_slots:
                                                        if slot['slotName']['$value']==slotname:
                                                            bindname=slot['boneName']['$value']
                                                else:
                                                    bindname= chunk_pt['Data']['slotName']['$value']

                                            # some meshes have boneRigMatrices in the mesh file which means we need jsons for the meshes or we cant access it. oh joy
                                            elif bindname=="deformation_rig" and (not chunk_pt['Data']['slotName']['$value'] or len(chunk_pt['Data']['slotName']['$value'])==1):
                                                json_name=os.path.join(path, c['mesh']['DepotPath']['$value']+'.json')
                                                #print("in the deformation rig bit",json_name)
                                                if json_name in mesh_jsons:
                                                    with open(mesh_jsons[mesh_jsons.index(json_name)],'r') as f: 
                                                        mesh_j=json.load(f)
                                                    valid_json=json_ver_validate(mesh_j)
                                                    if not valid_json:
                                                        bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="Incompatible anim json file detected. This add-on version requires materials generated WolvenKit 8.9.1 or higher.")
                                                        return {'CANCELLED'}
                                                    mesh_j=mesh_j['Data']['RootChunk']
                                                    #print('bindname from json ' ,mesh_j['boneNames'][0],bindname)
                                                    if 'boneRigMatrices' in mesh_j.keys():
                                                        bm= mesh_j['boneRigMatrices'][0]
                                                        row0=[bm['X']['X'],bm['Y']['X'],bm['Z']['X'],bm['W']['X']]
                                                        row1=[bm['X']['Y'],bm['Y']['Y'],bm['Z']['Y'],bm['W']['Y']]
                                                        row2=[bm['X']['Z'],bm['Y']['Z'],bm['Z']['Z'],bm['W']['Z']]
                                                        row3=[bm['X']['W'],bm['Y']['W'],bm['Z']['W'],bm['W']['W']]

                                                        matrix = Matrix()
                                                        matrix[0]=Vector(row0)
                                                        matrix[1]=Vector(row1)
                                                        matrix[2]=Vector(row2)
                                                        matrix[3]=Vector(row3)
                                                        # mx = '\n'.join([''.join(['{:4.2f} '.format(item) for item in row]) for row in matrix])
                                                        # print(mx)
                                                        bones=rig.pose.bones
                                                        #there are occasionally more than 1 bone in here, not worked out what/how maps to those
                                                        bone=bones[mesh_j['boneNames'][0]]
                                                        # the transform matrix above is in the orientation of the bone that its linked to, so I'm doing a bodged job of correcting for that here.
                                                        bone_mat_rot=bone.matrix.to_euler()
                                                        #print(bone_mat_rot)
                                                        xdisp=0
                                                        ydisp=0
                                                        zdisp=0
                                                
                                                        if abs(bone_mat_rot.y)>0.001:
                                                            xdisp = -matrix[1][3]/sin(bone_mat_rot.y)
                                                        if abs(bone_mat_rot.x)>0.001:
                                                            ydisp = -matrix[1][3]/sin(bone_mat_rot.x)
                                                        if abs(bone_mat_rot.z)>0.001:  
                                                            zdisp = matrix[2][3]/sin(bone_mat_rot.z)
                                                        #print(xdisp, ydisp ,zdisp)
                                                        # now we have the displacements. move things
                                                        for obj in objs:
                                                            #print(xdisp, ydisp ,zdisp)
                                                            obj.location.x =  obj.location.x+xdisp
                                                            obj.location.y = obj.location.y+ydisp          
                                                            obj.location.z =  obj.location.z+zdisp
                                                            # Apply child of constraints to them and set the inverse
                                                           
                                                            co=obj.constraints.new(type='CHILD_OF')
                                                            co.target=rig
                                                            co.subtarget= mesh_j['boneNames'][0]
                                                            bpy.context.view_layer.objects.active = obj
                                                            bpy.ops.constraint.childof_set_inverse(constraint="Child Of", owner='OBJECT')

                                            # things like the tvs have a bindname but no slotname, bindname appears to point at the name of the main component, and its the only one with a transform applied
                                            elif bindname:
                                                #see if we can find a component that matches it
                                                bindpt=[cmp for cmp in comps if cmp['name']==bindname]
                                                if bindpt and len(bindpt)==1:
                                                    if c['localTransform']['Position']['x']['Bits']==0 and c['localTransform']['Position']['y']['Bits']==0 and c['localTransform']['Position']['z']['Bits']==0:
                                                        c['localTransform']['Position']=bindpt[0]['localTransform']['Position']
                                                    if c['localTransform']['Orientation']['i']==0 and c['localTransform']['Orientation']['j']==0 and c['localTransform']['Orientation']['k']==0 and c['localTransform']['Orientation']['r']==1:
                                                        c['localTransform']['Orientation']=bindpt[0]['localTransform']['Orientation']


                                            #print('bindname = ',bindname)
                                            if rig:
                                                bones=rig.pose.bones
                                            if bindname and bones:
                                                #print('bindname and bones')
                                                if bindname not in bones.keys():
                                                    #print('bindname ',bindname, ' not in boneNames')
                                                    # if bindname isnt in the bones then its a part thats already bound to a bone, 
                                                    # These inherit the parent and local transforms from the other part, find it and work out what the transform is
                                                    for o in comps:
                                                        if o['name']['$value']==bindname:
                                                            pT=o['parentTransform']                                                        
                                                            x=o['localTransform']['Position']['x']['Bits']/131072
                                                            y=o['localTransform']['Position']['y']['Bits']/131072
                                                            z=o['localTransform']['Position']['z']['Bits']/131072
                                                            pT_HId=pT['HandleRefId']
                                                            #print(bindname, 'pT_HId = ',pT_HId)
                                                            chunk_pt = 0 
                                                            for chunk in chunks:
                                                                if 'parentTransform' in chunk.keys() and isinstance( chunk['parentTransform'], dict):
                                                                     if 'HandleId' in chunk['parentTransform'].keys():                                                                    
                                                                         if chunk['parentTransform']['HandleId']==pT_HId:
                                                                             chunk_pt=chunk['parentTransform']
                                                                             #print('HandleId found',chunk['parentTransform']['HandleId'])
                                                            if chunk_pt:   
                                                                #print('in chunk pt processing')                                     
                                                                bindname=chunk_pt['Data']['bindName']['$value']
                                                                if bindname=='vehicle_slots':
                                                                    if vehicle_slots:
                                                                        slotname=chunk_pt['Data']['slotName']['$value']
                                                                        for slot in vehicle_slots:
                                                                            if slot['slotName']['$value']==slotname:
                                                                                bindname=slot['boneName']['$value']
                                                                                       
                                                ######
                                                if bindname in bones.keys(): 
                                                    #print('bindname in bones')
                                                    bidx=0
                                                    for bid, b in enumerate(rig_j['boneNames']):
                                                        if b['$value']==bindname:
                                                            bidx=bid
                                                            #print('bone found - ',bidx)                                                
                                                    btrans=rig_j['boneTransforms'][bidx]
                                                
                                                    for obj in objs:
                                                        #print(bindname, bones[bindname].head)
                                                        obj['bindname']=bindname
                                                        pt_trans=bones[bindname].head
                                                        pt_rot=bones[bindname].rotation_quaternion
                                                    
                                                        obj.location.x =  obj.location.x+pt_trans[0]
                                                        obj.location.y = obj.location.y+pt_trans[1]
                                                        obj.location.z =  obj.location.z+pt_trans[2]
                                            
                                                        obj.rotation_quaternion.x = btrans['Rotation']['i'] 
                                                        obj.rotation_quaternion.y = btrans['Rotation']['j'] 
                                                        obj.rotation_quaternion.z = btrans['Rotation']['k'] 
                                                        obj.rotation_quaternion.w = btrans['Rotation']['r']
                                                        # Apply child of constraints to them and set the inverse
                                                        co=obj.constraints.new(type='CHILD_OF')
                                                        co.target=rig
                                                        co.subtarget= bindname
                                                        bpy.context.view_layer.objects.active = obj
                                                        bpy.ops.constraint.childof_set_inverse(constraint="Child Of", owner='OBJECT')
                                                                
                                    # end new stuff
                                    # dont get the local transform here if we already did it before
                                    if not x:   
                                        x=c['localTransform']['Position']['x']['Bits']/131072
                                    if not y: 
                                        y=c['localTransform']['Position']['y']['Bits']/131072
                                    if not z: 
                                        z=c['localTransform']['Position']['z']['Bits']/131072
                                    #print ('Local transform  x= ',x,'  y= ',y,' z= ',z)
                                    
                                    # local transforms are in the original mesh coord sys, but get applied after its already re-oriented, mainly only matters for wheels.
                                    # this is hacky af as I cant be arsed dealing with doing it properly with quaternions or whatever right now. Feel free to fix it.
                                    if bindname and bones and bindname in bones.keys() and bindname!='Base':
                                        z_ang=bones[bindname].matrix.to_euler().z
                                        x_orig=x
                                        y_orig=y
                                        x=x_orig*cos(z_ang)+y_orig*sin(z_ang)
                                        y=x_orig*sin(z_ang)+y_orig*cos(z_ang)
                                        #print ('Local transform  x= ',x,'  y= ',y,' z= ',z)
                                        
                                    for obj in objs:
                                        #print(obj.name, obj.type)
                                        obj.location.x =  obj.location.x+x
                                        obj.location.y = obj.location.y+y           
                                        obj.location.z =  obj.location.z+z 
                                        if 'Orientation' in c['localTransform'].keys() and not rig:    
                                            obj.rotation_quaternion.x = c['localTransform']['Orientation']['i']
                                            obj.rotation_quaternion.y = c['localTransform']['Orientation']['j']
                                            obj.rotation_quaternion.z = c['localTransform']['Orientation']['k']
                                            obj.rotation_quaternion.w = c['localTransform']['Orientation']['r']
                                        if 'scale' in c['localTransform'].keys():    
                                            obj.scale.x = c['localTransform']['scale']['X'] 
                                            obj.scale.y = c['localTransform']['scale']['Y'] 
                                            obj.scale.z = c['localTransform']['scale']['Z'] 
                                        if 'visualScale' in c.keys():
                                            obj.scale.x = c['visualScale']['X'] 
                                            obj.scale.y = c['visualScale']['Y'] 
                                            obj.scale.z = c['visualScale']['Z']

                                    move_coll= coll_scene.children.get( objs[0].users_collection[0].name )
                                    move_coll['depotPath']=c['mesh']['DepotPath']['$value']
                                    move_coll['meshAppearance']=meshApp
                                    if bindname:
                                        move_coll['bindname']=bindname
                                    ent_coll.children.link(move_coll) 
                                    coll_scene.children.unlink(move_coll)                                    
                            
                                #can probably a better way to pull this from somewhere but this works for now.                             
                                    license_plates = [obj for obj in bpy.data.objects if 'license_plate' in obj.get('componentName', '')]
                                    bumper_f_objs = [obj for obj in bpy.data.objects if 'bumper_f' in obj.get('componentName', '')]
                                    bumper_b_objs = [obj for obj in bpy.data.objects if 'bumper_b' in obj.get('componentName', '')]
                                   
                                    if len(license_plates) > 0:
                                        for obj in license_plates:
                                            try:
                                                # use the component name to figure out if this supposed to be attached to the front or back bumper
                                                componentName = obj.get('componentName', '')
                                                bumper_type = 'bumper_f' if 'license_plate_f' in componentName else 'bumper_b'
                                                # Find the correct bumper and match it to the license plate
                                                potential_parents = bumper_f_objs if bumper_type == 'bumper_f' else bumper_b_objs
                                                # Check if there's actually an object to parent the license plate to, if there is set it to obj.parent
                                                if potential_parents:  
                                                    obj.parent = potential_parents[0]
                                                # I'm pretty certain you have this stored somewhere else already - we should probably look at just adding all of the localTransforms 
                                                # to a dict seperate from comp earlier on and just matching them by componnent name whenever we need to apply transforms    
                                                    lct = next((comp for comp in comps if comp["name"]["$value"] == componentName), None)
                                                    #print(lct["localTransform"])
                                                    if lct:
                                                        obj.location[0] = lct["localTransform"]["Position"]["x"]["Bits"]/ 131072
                                                        obj.location[1] = lct["localTransform"]["Position"]["y"]["Bits"]/ 131072
                                                        obj.location[2] = lct["localTransform"]["Position"]["z"]["Bits"]/ 131072                                        
                                                else:
                                                    print('no bumper found to parent license plate to')
                                            except Exception as e:
                                                print(e)
                                    # New chunkMask reading
                                    # convert the value to a list of bools, then apply those statuses to the submeshes.                                   
                                    if 'chunkMask' in c.keys():       
                                        cm= c['chunkMask']                              
                                        if isinstance(cm,str):
                                            bin_str = bin(int(cm))[2:]
                                        else:
                                            bin_str = bin(cm)[2:]
                                        cm_list = [bool(int(bit)) for bit in bin_str]
                                        cm_list.reverse()
                                        for obj in objs:
                                            subnum=int(obj.name[8:10])
                                            # obj.hide_viewport=not cm_list[subnum]
                                            obj.hide_set(not cm_list[subnum])
                                #else:
                                except:
                                    print("Failed on ",meshname)
     
              # find the .phys file jsons
        if include_collisions:
            collision_collection = bpy.data.collections.new('colliders')
            ent_coll.children.link(collision_collection)
            if include_phys:
                try:
                    physJsonPaths = glob.glob(path + "\**\*.phys.json", recursive=True)
                    if len(physJsonPaths) == 0:
                        print('No phys file JSONs found in path')
                    else:
                        if len(chassis_info) > 0:
                            chassis_z = chassis_info['localTransform']['Position']['z']['Bits'] / 131072
                            chassis_phys_j=os.path.basename(chassis_info['collisionResource']['DepotPath']['$value'])+'.json'
                        else:
                            #this isn't really right, but the value seems to always be very close so it's better than 0
                            chassis_z = rig_j['boneTransforms'][2]['Translation']['Z']
                        #print('colliders:', ent_colliderComps)
                        for physJsonPath in physJsonPaths:
                            if os.path.basename(physJsonPath)==chassis_phys_j:
                                cp77_phys_import(collision_collection, physJsonPath, rig, chassis_z)
                except Exception as e:
                    print(e)
            
            if include_entCollider:
                if len(ent_colliderComps) == 0 and len(ent_simpleCollComps)== 0:
                    print('No entColliderComponent or entSimpleColliderComponents found')
                    return('FINISHED')
                else:
                    for index, i in enumerate(ent_component_data):
                    #for comp in ent_component_data:
                        if i['$type'] == 'entColliderComponent':
                            new_col = bpy.data.collections.new('entColliderComponent')
                            collision_collection.children.link(new_col)
                            collision_type = 'ENTITY'
                            cdata = i['colliders'][0]['Data']
                            collision_shape = cdata['$type']
                            transform = cdata['localToBody']
                            simulationType = i['simulationType']
                            submeshName = '_' + collision_shape
                            physmat = cdata['material']['$value']
                            position = transform['position']['X'], transform['position']['Y'], transform['position']['Z']
                            rotation = transform['orientation']['r'], transform['orientation']['j'], transform['orientation']['k'], transform['orientation']['i']                
                            #print('cdata:', cdata)                            
                            print('collider info:', collision_shape, submeshName, physmat, position, rotation)
                            if collision_shape == 'physicsColliderBox':
                                try:
                                    half_extents = cdata['halfExtents']
                                    draw_box_collider(submeshName, new_col, half_extents, transform,  physmat, collision_type)
                                    obj = bpy.context.object
                                    box = obj
                                    #set_collider_props(box, collision_shape, physmat, collision_type)
                                    box['simulationType'] = simulationType
                                except Exception as e:
                                    print('uh oh', e)
                            if collision_shape == 'physicsColliderConvex':
                                try:
                                    vertices = cdata['vertices']
                                    obj = draw_convex_collider(submeshName, new_col, vertices, transform, physmat, collision_type)
                                    convcol = obj
                                    #set_collider_props(convcol, collision_shape, physmat, collision_type)
                                    convcol['simulationType'] = simulationType
                                except Exception as e:
                                    print('uh oh', e)
                            if collision_shape == 'physicsColliderSphere':
                                try:
                                    r = cdata['radius']
                                    submeshName = '_' + collision_shape
                                    obj = draw_sphere_collider(submeshName, new_col, r, position, physmat, collision_type)
                                except Exception as e:
                                    print('uh oh', e)
                            if collision_shape == 'physicsColliderCapsule':
                                try:
                                    r = cdata['radius'] 
                                    h = cdata['height']    
                                    submeshName = '_' + collision_shape
                                    obj = draw_capsule_collider(submeshName, new_col, r, h, position, rotation, physmat, collision_type)
                                except Exception as e:
                                    print('uh oh', e)
                        if i['$type'] == 'entSimpleColliderComponent':
                            collision_type = 'ENTITY'
                            new_col = bpy.data.collections.new('entSimpleColliderComponent')
                            collision_collection.children.link(new_col)
                            cdata = i['colliders'][0]['Data']
                            collision_shape = cdata['$type']
                            transform = cdata['localToBody']
                            #simulationType = i['simulationType']
                            submeshName = '_' + collision_shape
                            physmat = cdata['material']['$value']
                            position = transform['position']['X'], transform['position']['Y'], transform['position']['Z']
                            rotation = transform['orientation']['r'], transform['orientation']['j'], transform['orientation']['k'], transform['orientation']['i']                
                            #print('position:', position[0], position[1], position[2], 'rotation', rotation[0], rotation[1], rotation[2], rotation[3])                 
                           # print('collider info:', collision_shape, submeshName, physmat, position, rotation)
                            if collision_shape == 'physicsColliderBox':
                                try:
                                    half_extents = cdata['halfExtents']
                                    draw_box_collider(submeshName, new_col, half_extents, transform,  physmat, collision_type)
                                    obj = bpy.context.object
                                    box = obj
                                    #set_collider_props(box, collision_shape, physmat, collision_type)
                                   # box['simulationType'] = simulationType
                                except Exception as e:
                                    print('uh oh', e)
                            if collision_shape == 'physicsColliderConvex':
                                try:
                                    vertices = cdata['vertices']
                                    obj = draw_convex_collider(submeshName, new_col, vertices, transform, physmat, collision_type)
                                    convcol = obj
                                    #set_collider_props(convcol, collision_shape, physmat, collision_type)
                                   # convcol['simulationType'] = simulationType
                                except Exception as e:
                                    print('uh oh', e)
                            if collision_shape == 'physicsColliderSphere':
                                try:
                                    r = cdata['radius']
                                    submeshName = '_' + collision_shape
                                    obj = draw_sphere_collider(submeshName, new_col, r, position, physmat, collision_type)
                                except Exception as e:
                                    print('uh oh', e)
                            if collision_shape == 'physicsColliderCapsule':
                                try:
                                    r = cdata['radius']
                                    h = cdata['height']    
                                    submeshName = '_' + collision_shape
                                    obj = draw_capsule_collider(submeshName, new_col, r, h, position, rotation, physmat, collision_type)
                                except Exception as e:
                                    print('uh oh', e)

                            


    if app_name:
        print('Exported' ,app_name)

    print("--- %s seconds ---" % (time.time() - start_time))

# The above is  the code thats for the import plugin below is to allow testing/dev, you can run this file to import something

if __name__ == "__main__":

    path = 'F:\\CPmod\\heist_hotel\\source\\raw'
    ent_name = 'single_door.ent'
    # The list below needs to be the appearanceNames for each ent that you want to import 
    # NOT the name in appearances list, expand it and its the property inside, also its name in the app file
    appearances =['kitsch_f']

    jsonpath = glob.glob(path+"\**\*.ent.json", recursive = True)
    if len(jsonpath)==0:
        print('No jsons found')
        
    for i,e in enumerate(jsonpath):
        if os.path.basename(e)== ent_name+'.json' :
            filepath=e
            
    importEnt( filepath, appearances )