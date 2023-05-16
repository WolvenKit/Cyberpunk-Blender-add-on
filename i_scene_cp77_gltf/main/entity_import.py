# Blender Entity import script by Simarilius
# Updated May 23 with vehicle rig support
import json
import glob
import os
import bpy
import time
from math import sin,cos
from mathutils import Vector, Matrix , Quaternion

# The appearance list needs to be the appearanceNames for each ent that you want to import, will import all if not specified
# if you've already imported the body/head and set the rig up you can exclude them by putting them in the exclude_meshes list 

def importEnt( filepath='', appearances=[], exclude_meshes=[] , with_materials=True): 
    
    C = bpy.context
    coll_scene = C.scene.collection
    start_time = time.time()

    before,mid,after=filepath.partition('source\\raw')
    path=before+mid

    ent_name=os.path.basename(filepath)[:-9]
    print('Importing Entity', ent_name)
    with open(filepath,'r') as f: 
        j=json.load(f) 
        
    ent_apps= j['Data']['RootChunk']['appearances']
    
    VS=[]
    for x in j['Data']['RootChunk']['components']:
        if 'name' in x.keys() and x['name']=='vehicle_slots':
            VS.append(x)
    if len(VS)>0:
        vehicle_slots= VS[0]['slots']
    
    # if no apps requested populate the list with all available.
    if len(appearances[0])==0:
        for app in ent_apps:
            appearances.append(app['appearanceName'])
    
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
    rigs = glob.glob(path+"\\base\\animations"+"\**\*.glb", recursive = True)
    rig=None
    bones=None
    chunks=None
    if len(rigs)>0:
            oldarms= [x for x in bpy.data.objects if 'Armature' in x.name]
            bpy.ops.io_scene_gltf.cp77(filepath=rigs[0])
            arms=[x for x in bpy.data.objects if 'Armature' in x.name and x not in oldarms]
            rig=arms[0]
            bones=rig.pose.bones
            print('anim rig loaded')
    else:
        print('no anim rig found')
            
    rigjsons = glob.glob(path+"\**\*.rig.json", recursive = True)
    rig_j=None
    if len(rigjsons)>0:
            with open(rigjsons[0],'r') as f: 
                rig_j=json.load(f)['Data']['RootChunk']
                print('rig json loaded')
    else: 
        print('no rig json found')
                
    if len(meshes)<1 or len(app_path)<1:
        print("You need to export the meshes and convert app and ent to json")

    else:
        for x,app_name in enumerate(appearances):
            # Put each appearance in a collector with the ent name and app name
            ent_coll=bpy.data.collections.new(ent_name+'_'+app_name)
            # tag it with some custom properties.
            ent_coll['appearanceName']=app_name
            ent_coll['depotPath']=ent_name
            #link it to the scene
            coll_scene.children.link(ent_coll)
                  
            comps=[]
            
            if len(ent_apps)>0:
                ent_app_idx=-1
                # Find the appearance in the entity app list
                for i,a in enumerate(ent_apps):
                    if a['appearanceName']==app_name:
                        print('appearance matched, id = ',i)
                        ent_app_idx=i

                # apparently they sometimes just sack it off and use the name not the appearanceName after all. (single_doors.ent for instance)
                if ent_app_idx<0:
                    for i,a in enumerate(ent_apps):
                        if a['name']==app_name:
                            print('appearance matched, id = ',i)
                            ent_app_idx=i
                            app_name=a['appearanceName']

                if ent_app_idx<0:
                    ent_app_idx=0

                app_file = ent_apps[ent_app_idx]['appearanceResource']['DepotPath']
                appfilepath=os.path.join(path,app_file)+'.json'
                        
                if os.path.exists(appfilepath):
                    with open(appfilepath,'r') as a: 
                        a_j=json.load(a)
                else:
                    print('app file not found - ',filepath)
                    
                app_idx=0
                apps=a_j['Data']['RootChunk']['appearances']
                for i,a in enumerate(apps):
                    print(i,a['Data']['name'])
                    if a['Data']['name']==app_name:
                        print('appearance matched, id = ',i)
                        app_idx=i
                chunks=None
                if 'Data' in a_j['Data']['RootChunk']['appearances'][app_idx].keys():
                    comps= a_j['Data']['RootChunk']['appearances'][app_idx]['Data']['components']
                    if 'compiledData' in a_j['Data']['RootChunk']['appearances'][app_idx]['Data'].keys():
                        chunks= a_j['Data']['RootChunk']['appearances'][app_idx]['Data']['compiledData']['Data']['Chunks']
                        print('Chunks found')
                        
            if len(comps)==0:      
                print('falling back to rootchunk comps')
                comps= j['Data']['RootChunk']['components']
            for c in comps:
                if 'mesh' in c.keys():
                    #print(c['mesh']['DepotPath'])
                    if isinstance( c['mesh']['DepotPath'], str):
                        meshname=os.path.basename(c['mesh']['DepotPath'])
                        meshpath=os.path.join(path, c['mesh']['DepotPath'][:-4]+'glb')
                        if meshname not in exclude_meshes:      
                            if os.path.exists(meshpath):
                                if True:
                                #try:
                                    meshApp='default'
                                    if 'meshAppearance' in c.keys():
                                        meshApp=c['meshAppearance']
                                        #print(meshApp)
                                    try:
                                        bpy.ops.io_scene_gltf.cp77(filepath=meshpath, appearances=meshApp, with_materials=with_materials)
                                    except:
                                        print('import threw an error')
                                        continue
                                    objs = C.selected_objects
                                    
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
                                        print('pT_HId = ',pT_HId)
                                        chunk_pt = 0 
                                        # find the parent transform in the chunks
                                        if chunks:
                                            for chunk in chunks:
                                                if 'parentTransform' in chunk.keys() and isinstance( chunk['parentTransform'], dict):
                                                     #print('pt found')
                                                     if 'HandleId' in chunk['parentTransform'].keys():
                                                
                                                         if chunk['parentTransform']['HandleId']==pT_HId:
                                                             chunk_pt=chunk['parentTransform']
                                                             print('HandleId found',chunk['parentTransform']['HandleId'])
                                        # if we found it then process it, most chars etc will just skip this                                                     
                                        if chunk_pt:   
                                            print('in chunk pt processing bindName = ',chunk_pt['Data']['bindName'],' slotname= ',chunk_pt['Data']['slotName'])                                     
                                            # parts have a bindname, and sometimes a slotname
                                            bindname=chunk_pt['Data']['bindName']
                                            # if it has a bindname of vehicle_slots, you may need to find the bone name in the vehicle slots in the root ent components
                                            # this should have been loaded earlier, check for it in the vehicle slots if not just set to the slot value
                                            if bindname=='vehicle_slots':
                                                if vehicle_slots:
                                                    slotname=chunk_pt['Data']['slotName']
                                                    for slot in vehicle_slots:
                                                        if slot['slotName']==slotname:
                                                            bindname=slot['boneName']
                                                else:
                                                    bindname= chunk_pt['Data']['slotName']

                                            # some meshes have boneRigMatrices in the mesh file which means we need jsons for the meshes or we cant access it. oh joy
                                            if bindname=="deformation_rig" and not chunk_pt['Data']['slotName'] :
                                                json_name=os.path.join(path, c['mesh']['DepotPath']+'.json')
                                                print("in the deformation rig bit",json_name)
                                                if json_name in mesh_jsons:
                                                    with open(mesh_jsons[mesh_jsons.index(json_name)],'r') as f: 
                                                        mesh_j=json.load(f)['Data']['RootChunk']
                                                
                                                    print('bindname from json ' ,mesh_j['boneNames'][0],bindname)
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
                                                        print(bone_mat_rot)
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
                                                            print(xdisp, ydisp ,zdisp)
                                                            obj.location.x =  obj.location.x+xdisp
                                                            obj.location.y = obj.location.y+ydisp          
                                                            obj.location.z =  obj.location.z+zdisp
                                                            # Apply child of constraints to them and set the inverse
                                                           
                                                            co=obj.constraints.new(type='CHILD_OF')
                                                            co.target=rig
                                                            co.subtarget= mesh_j['boneNames'][0]
                                                            bpy.context.view_layer.objects.active = obj
                                                            bpy.ops.constraint.childof_set_inverse(constraint="Child Of", owner='OBJECT')

                                            print('bindname = ',bindname)
                                            if rig:
                                                bones=rig.pose.bones
                                            if bindname and bones:
                                                print('bindname and bones')
                                                if bindname not in bones.keys():
                                                    print('bindname ',bindname, ' not in boneNames')
                                                    # if bindname isnt in the bones then its a part thats already bound to a bone, 
                                                    # These inherit the parent and local transforms from the other part, find it and work out what the transform is
                                                    for o in comps:
                                                        if o['name']==bindname:
                                                            pT=o['parentTransform']                                                        
                                                            x=o['localTransform']['Position']['x']['Bits']/131072
                                                            y=o['localTransform']['Position']['y']['Bits']/131072
                                                            z=o['localTransform']['Position']['z']['Bits']/131072
                                                            pT_HId=pT['HandleRefId']
                                                            print(bindname, 'pT_HId = ',pT_HId)
                                                            chunk_pt = 0 
                                                            for chunk in chunks:
                                                                if 'parentTransform' in chunk.keys() and isinstance( chunk['parentTransform'], dict):
                                                                     if 'HandleId' in chunk['parentTransform'].keys():                                                                    
                                                                         if chunk['parentTransform']['HandleId']==pT_HId:
                                                                             chunk_pt=chunk['parentTransform']
                                                                             print('HandleId found',chunk['parentTransform']['HandleId'])
                                                            if chunk_pt:   
                                                                print('in chunk pt processing')                                     
                                                                bindname=chunk_pt['Data']['bindName']
                                                                if bindname=='vehicle_slots':
                                                                    if vehicle_slots:
                                                                        slotname=chunk_pt['Data']['slotName']
                                                                        for slot in vehicle_slots:
                                                                            if slot['slotName']==slotname:
                                                                                bindname=slot['boneName']
                                                                                       
                                                ######
                                                if bindname in bones.keys(): 
                                                    print('bindname in bones')
                                                    bidx=0
                                                    for bid, b in enumerate(rig_j['boneNames']):
                                                        if b==bindname:
                                                            bidx=bid
                                                            print('bone found - ',bidx)                                                
                                                    btrans=rig_j['boneTransforms'][bidx]
                                                
                                                    for obj in objs:
                                                        print(bindname, bones[bindname].head)
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
                                        print ('Local transform  x= ',x,'  y= ',y,' z= ',z)
                                        
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
                                    move_coll['depotPath']=c['mesh']['DepotPath']
                                    move_coll['meshAppearance']=meshApp
                                    if bindname:
                                        move_coll['bindname']=bindname
                                    ent_coll.children.link(move_coll) 
                                    coll_scene.children.unlink(move_coll)
                                    # New chunkMask reading 
                                    # convert the value to a list of bools, then apply those statuses to the submeshes.
                                    if 'chunkMask' in c.keys():
                                        bin_str = bin(c['chunkMask'])[2:]
                                        cm_list = [bool(int(bit)) for bit in bin_str]
                                        cm_list.reverse()
                                        for obj in objs:
                                            subnum=int(obj.name[8:10])
                                            obj.hide_viewport=not cm_list[subnum]
                                            obj.hide_set(not cm_list[subnum])
                                #except:
                                 #   print("Failed on ",c['mesh']['DepotPath'])
        print('Exported' ,app_name)
    print("--- %s seconds ---" % (time.time() - start_time))




# The above is  the code thats for the import plugin below is to allow testing/dev, you can run this file to import something

if __name__ == "__main__":

    path = 'F:\\CPMod\\arch\\source\\raw'
    ent_name = 'v_sportbike2_arch_nemesis_basic_01.ent'
    # The list below needs to be the appearanceNames for each ent that you want to import 
    # NOT the name in appearances list, expand it and its the property inside, also its name in the app file
    appearances =['player_01']

    jsonpath = glob.glob(path+"\**\*.ent.json", recursive = True)
    if len(jsonpath)==0:
        print('No jsons found')
        
    for i,e in enumerate(jsonpath):
        if os.path.basename(e)== ent_name+'.json' :
            filepath=e
            
    importEnt( filepath, appearances )