# Blender Entity import script by Simarilius
import json
import glob
import os
import bpy
import time

# The appearance list needs to be the appearanceNames for each ent that you want to import, will import all if not specified
# if you've already imported the body/head and set the rig up you can exclude them by putting them in the exclude_meshes list 

def importEnt( filepath='', appearances=[], exclude_meshes=[] ): 
    C = bpy.context
    coll_scene = C.scene.collection
    start_time = time.time()

    before,mid,after=filepath.partition('source\\raw')
    path=before+mid

    ent_name=os.path.basename(filepath)[:-9]

    with open(filepath,'r') as f: 
        j=json.load(f) 
        
    ent_apps= j['Data']['RootChunk']['appearances']
    
    vehicle_slots=[x for x in j['Data']['RootChunk']['components'] if x['name']=='vehicle_slots'][0]['slots']
    
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

    # find the anims
    rigs = glob.glob(path+"\\base\\animations"+"\**\*.glb", recursive = True)
    if len(rigs)>0:
            oldarms= [x for x in bpy.data.objects if 'Armature' in x.name]
            bpy.ops.io_scene_gltf.cp77(filepath=rigs[0])
            arms=[x for x in bpy.data.objects if 'Armature' in x.name and x not in oldarms]
            rig=arms[0]
            bones=rig.pose.bones
            print('anim rig loaded')
            
    rigjsons = glob.glob(path+"\**\*.rig.json", recursive = True)
    if len(rigjsons)>0:
            with open(rigjsons[0],'r') as f: 
                rig_j=json.load(f)['Data']['RootChunk']
                print('rig json loaded')
                
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
                ent_app_idx=0
                # Find the appearance in the entity app list
                for i,a in enumerate(ent_apps):
                    if a['appearanceName']==app_name:
                        print('appearance matched, id = ',i)
                        ent_app_idx=i
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
                                try:
                                    meshApp='default'
                                    if 'meshAppearance' in c.keys():
                                        meshApp=c['meshAppearance']
                                        #print(meshApp)
                                    try:
                                        bpy.ops.io_scene_gltf.cp77(filepath=meshpath, appearances=meshApp)
                                    except:
                                        print('import threw an error')
                                    objs = C.selected_objects
                                    
                                    # NEW parentTransform stuff - should fix vehicles being exploded
                                    pt_trans=[0,0,0]
                                    pt_rot=[0,0,0,0]
                                    pT=c['parentTransform']
                                    pT_HId=pT['HandleRefId']
                                    print('pT_HId = ',pT_HId)
                                    chunk_pt = 0 
                                    for chunk in chunks:
                                        if 'parentTransform' in chunk.keys() and isinstance( chunk['parentTransform'], dict):
                                             #print('pt found')
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
                                            else:
                                                bindname= chunk_pt['Data']['slotName']
                                                #look to see if its in te
                                        print('bindname = ',bindname)
                                        bones=rig.pose.bones
                                        if bindname and bones:
                                            print('bindname and bones')
                                            if bindname not in bones.keys():
                                                print('bindname ',bindname, ' not in boneNames')
                                                # if bindname isnt in the bones then its a part thats already bound to a bone, find it and work out what the transform is
                                                for o in comps:
                                                    if o['name']==bindname:
                                                        pT=o['parentTransform']
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
                                                    
                                                    co=obj.constraints.new(type='CHILD_OF')
                                                    co.target=rig
                                                    co.subtarget= bindname
                                                    bpy.context.view_layer.objects.active = obj
                                                    bpy.ops.constraint.childof_set_inverse(constraint="Child Of", owner='OBJECT')
                                                        
                                            
                                                 

                                        
                                                                                
                                    # end new stuff
                                    
                                    x=c['localTransform']['Position']['x']['Bits']/131072
                                    y=c['localTransform']['Position']['y']['Bits']/131072
                                    z=c['localTransform']['Position']['z']['Bits']/131072
                                   
                                    for obj in objs:
                                        #print(obj.name, obj.type)
                                        obj.location.x =  obj.location.x+x
                                        obj.location.y = obj.location.y+y           
                                        obj.location.z =  obj.location.z+z 
                                        if not bindname:
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
                                except:
                                    print("Failed on ",c['mesh']['DepotPath'])
        print('Exported' ,app_name)
    print("--- %s seconds ---" % (time.time() - start_time))




# The above is  the code thats for the import plugin below is to allow testing/dev, you can run this file to import something

if __name__ == "__main__":

    path = 'D:\\temp\\quadra\\source\\raw'
    ent_name = 'v_sport1_quadra_turbo__basic_01.ent'
    # The list below needs to be the appearanceNames for each ent that you want to import 
    # NOT the name in appearances list, expand it and its the property inside, also its name in the app file
    appearances =['tygerclaws_05']

    jsonpath = glob.glob(path+"\**\*.ent.json", recursive = True)
    if len(jsonpath)==0:
        print('No jsons found')
        
    for i,e in enumerate(jsonpath):
        if os.path.basename(e)== ent_name+'.json' :
            filepath=e
            
    importEnt( filepath, appearances )