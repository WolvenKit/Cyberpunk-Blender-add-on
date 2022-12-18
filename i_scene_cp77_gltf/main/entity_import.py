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
                filepath=os.path.join(path,app_file)+'.json'
                        
                if os.path.exists(filepath):
                    with open(filepath,'r') as a: 
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
                        
            if len(comps)==0:      
                print('falling back to rootchunk comps')
                comps= j['Data']['RootChunk']['components']
            for c in comps:
                if 'mesh' in c.keys():
                    #print(c['mesh']['DepotPath'])
                    app='default'
                    meshname=os.path.basename(c['mesh']['DepotPath'])
                    meshpath=os.path.join(path, c['mesh']['DepotPath'][:-4]+'glb')
                    if meshname not in exclude_meshes:                
                        if isinstance( c['mesh']['DepotPath'], str):       
                            if os.path.exists(meshpath):
                                try:
                                    meshApp='default'
                                    if 'meshAppearance' in c.keys():
                                        meshApp=c['meshAppearance']
                                        #print(meshApp)
                                   
                                    bpy.ops.io_scene_gltf.cp77(filepath=meshpath, appearances=meshApp)
                                    objs = C.selected_objects
                                    x=c['localTransform']['Position']['x']['Bits']/131072
                                    y=c['localTransform']['Position']['y']['Bits']/131072
                                    z=c['localTransform']['Position']['z']['Bits']/131072
                                   
                                    for obj in objs:
                                        #print(obj.name, obj.type)
                                        obj.location.x = x
                                        obj.location.y = y                     
                                        obj.location.z = z 
                                        obj.rotation_quaternion.x = c['localTransform']['Orientation']['i']
                                        obj.rotation_quaternion.y = c['localTransform']['Orientation']['j']
                                        obj.rotation_quaternion.z = c['localTransform']['Orientation']['k']
                                        obj.rotation_quaternion.w = c['localTransform']['Orientation']['r']
                                        if 'scale' in c['localTransform'].keys():    
                                            obj.scale.x = c['localTransform']['scale']['X'] 
                                            obj.scale.y = c['localTransform']['scale']['Y'] 
                                            obj.scale.z = c['localTransform']['scale']['Z'] 

                                    move_coll= coll_scene.children.get( objs[0].users_collection[0].name )
                                    move_coll['depotPath']=c['mesh']['DepotPath']
                                    move_coll['meshAppearance']=meshApp
                                    ent_coll.children.link(move_coll) 
                                    coll_scene.children.unlink(move_coll)
                                except:
                                    print("Failed on ",c['mesh']['DepotPath'])
        print('Exported' ,app_name)
    print("--- %s seconds ---" % (time.time() - start_time))
