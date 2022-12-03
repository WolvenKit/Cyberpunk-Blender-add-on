# Blender Entity import script by Simarilius
import json
import glob
import os
import bpy
import time
C = bpy.context
coll_scene = C.scene.collection
start_time = time.time()
path = 'F:\\CPmod\\tygers\\source\\raw'
ent_name = 'gang__tyger_ma.ent'
# The list below needs to be the appearanceNames for each ent that you want to import 
# NOT the name in appearances list, expand it and its the property inside, also its name in the app file
appearances =['biker__lvl1_05']



def importEnt(path, entity, appearances): 
    jsonpath = glob.glob(path+"\**\*.ent.json", recursive = True)
    if len(jsonpath)==0:
        print('No jsons found')
    for i,e in enumerate(jsonpath):
        if os.path.basename(e)== ent_name+'.json' :
            filepath=e
    with open(filepath,'r') as f: 
        j=json.load(f) 
    ent_apps= j['Data']['RootChunk']['appearances']
    # if you've already imported the body/head and set the rig up you can exclude them by putting them in this list 
    exclude_meshes= ['h_012_ma_a__young.mesh' ,'t_000_ma_base__full.mesh']      

    app_path = glob.glob(path+"\**\*.app.json", recursive = True)
    meshes =  glob.glob(path+"\**\*.glb", recursive = True)
    glbnames = [ os.path.basename(x) for x in meshes]
    meshnames = [ os.path.splitext(x)[0]+".mesh" for x in glbnames]
    if len(meshnames)==0:
        print('No Meshes found')

    if len(meshnames)<1 or len(jsonpath)<1 or len(app_path)<1:
        print("You need to export the meshes and convert app and ent to json")
    else:
        for x,app_name in enumerate(appearances):
            ent_coll=bpy.data.collections.new(ent_name+'_'+app_name)
            ent_coll['appearanceName']=app_name
            ent_coll['depotPath']=ent_name
            coll_scene.children.link(ent_coll)
                  
            comps=[]
            
            if len(ent_apps)>0:
                app_idx=0
                for i,a in enumerate(ent_apps):
                    #print(i,a['appearanceName'])
                    if a['appearanceName']==app_name:
                        print('appearance matched, id = ',i)
                        app_idx=i
                app_file = ent_apps[app_idx]['appearanceResource']['DepotPath']
                for i,e in enumerate(app_path):
                    #print(os.path.basename(e))
                    if os.path.basename(e)== os.path.basename(app_file)+'.json' :
                        filepath=e
                        
                if len(filepath)>0:
                    with open(filepath,'r') as a: 
                        a_j=json.load(a)
                app_idx=0
                apps=a_j['Data']['RootChunk']['appearances']
                for i,a in enumerate(apps):
                    print(i,a['Data']['name'])
                    if a['Data']['name']==app_name:
                        print('appearance matched, id = ',i)
                        app_idx=i
                if 'Data' in a_j['Data']['RootChunk']['appearances'][app_idx].keys():
                    comps= a_j['Data']['RootChunk']['appearances'][app_idx]['Data']['components']
                        
            if len(comps)<1:      
                print('falling back to rootchunck comps')
                comps= j['Data']['RootChunk']['components']
            for c in comps:
                if 'mesh' in c.keys():
                    #print(c['mesh']['DepotPath'])
                    app='default'
                    meshname=os.path.basename(c['mesh']['DepotPath'])
                    if meshname not in exclude_meshes:                
                        if isinstance( c['mesh']['DepotPath'], str):       
                            if os.path.exists(os.path.join(path, c['mesh']['DepotPath'][:-4]+'glb')):
                                try:
                                   meshApp='default'
                                   if 'meshAppearance' in c.keys():
                                       meshApp=c['meshAppearance']
                                       #print(meshApp)
                                   #print(os.path.join(path, c['mesh']['DepotPath'][:-4]+'glb')+' , '+impapps)
                                   meshpath=os.path.join(path, c['mesh']['DepotPath'][:-4]+'glb')
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

#with all mats 280.71283984184265 seconds ---

importEnt(path, ent_name, appearances)