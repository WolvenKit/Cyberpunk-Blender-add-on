#     ____  __      _           __  _____                                         ____                  __ 
#    / __ \/ /_    (_)__  _____/ /_/ ___/____  ____ __      ______  ___  _____   /  _/___  ____  __  __/ /_
#   / / / / __ \  / / _ \/ ___/ __/\__ \/ __ \/ __ `/ | /| / / __ \/ _ \/ ___/   / // __ \/ __ \/ / / / __/
#  / /_/ / /_/ / / /  __/ /__/ /_ ___/ / /_/ / /_/ /| |/ |/ / / / /  __/ /     _/ // / / / /_/ / /_/ / /_  
#  \____/_.___/_/ /\___/\___/\__//____/ .___/\__,_/ |__/|__/_/ /_/\___/_/     /___/_/ /_/ .___/\__,_/\__/  
#            /___/                   /_/                                               /_/       
#
# Object Spawner Group input
# Project path needs to be set to the top level folder of the project that has the meshes in it to find (sector that you created from if there is one)
# groupname is the json filename without .json
#
#

project_path='C:\\CPMod\\notell'
GroupName='blender_group3'
with_mats=False

import bpy
import os
import json
from math import pi,radians,degrees
from mathutils import Vector
D=bpy.data
C=bpy.context
coll_scene = C.scene.collection

def get_position(obj):
    pos = Vector((obj['spawnable']['position']['x'],obj['spawnable']['position']['y'],obj['spawnable']['position']['z']))
    rot= Vector((radians(obj['spawnable']['rotation']['pitch']),
                            radians(obj['spawnable']['rotation']['roll']),
                            radians(obj['spawnable']['rotation']['yaw'])))
    scale =Vector((obj['spawnable']['scale']['x'],obj['spawnable']['scale']['y'],obj['spawnable']['scale']['z']))
    return pos,rot,scale
                

def process_group(group,target_coll):
    for child in group['childs']:
        if child['type']=='group':
            coll_target=bpy.data.collections.new(child['name'])
            target_coll.children.link(coll_target)
            process_group(child,coll_target)
        elif child['type']=='object':
            process_object(child,target_coll)
    
def process_object(obj,parent_coll):
    Masters=bpy.data.collections.get("MasterInstances")
    spawndata=obj['spawnable']['spawnData'] 
    if spawndata[-5:]=='.mesh' :     
        meshpath=os.path.join(project_path,'source','raw', spawndata[:-1*len(os.path.splitext(spawndata)[1])]+'.glb').replace('\\', os.sep)
        impapps=obj['spawnable']['app']
        groupname = os.path.splitext(os.path.split(meshpath)[-1])[0]
        while len(groupname) > 63:
            groupname = groupname[:-1]
        if groupname not in Masters.children.keys() and os.path.exists(meshpath):
            try:
                bpy.ops.io_scene_gltf.cp77(with_mats, filepath=meshpath, appearances=impapps)
                objs = C.selected_objects
                move_coll= coll_scene.children.get( objs[0].users_collection[0].name )
                Masters.children.link(move_coll) 
                C.scene.collection.children.unlink(move_coll)
            except:
                print('failed on ',meshpath)
        elif groupname not in Masters.children.keys() and not os.path.exists(meshpath):
            print('Mesh ', meshpath, ' does not exist')
        
        if groupname  in Masters.children.keys():
            group=Masters.children.get(groupname)
            if group:
                new=bpy.data.collections.new(groupname)
                parent_coll.children.link(new)
                new['nodeType']=obj['type']
                #new['entityTemplate']=data['entityTemplate']['DepotPath']['$value']
                new['appearanceName']=obj['spawnable']['app']
                new['obj']=obj
                pos,rot,scale=get_position(obj)
                for old_obj in group.all_objects:                            
                    newobj=old_obj.copy()  
                    new.objects.link(newobj)     
                    newobj.location = pos
                    newobj.rotation_mode = 'XYZ'
                    newobj.rotation_euler = rot
                    newobj.scale = scale
    elif spawndata[-4:]=='.ent' :
        app=obj['app']
        entpath=os.path.join(path,spawndata).replace('\\', os.sep)+'.json'
        ent_groupname=os.path.basename(entpath).split('.')[0]+'_'+app
        while len(ent_groupname) > 63:
            ent_groupname = ent_groupname[:-1]
        imported=False
        if ent_groupname in Masters.children.keys():
            move_coll=Masters.children.get(ent_groupname)
            imported=True
        else:
            try:
                #print('Importing ',entpath, ' using app ',app)
                incoll='MasterInstances'
                bpy.ops.io_scene_gltf.cp77entity(with_mats, filepath=entpath, appearances=app, inColl=incoll)
                move_coll=Masters.children.get(ent_groupname)
                imported=True
            except:
                print(traceback.print_exc())
                print(f"Failed during Entity import on {entpath} from app {app}")
        if imported:
            instances = [x for x in t if x['NodeIndex'] == i]
            for idx,inst in enumerate(instances):
                #print(inst)
                group=move_coll                            
                if (group):
                    groupname=move_coll.name
                    #print('Group found for ',groupname)     
                    new=bpy.data.collections.new(groupname)
                    Sector_coll.children.link(new)
                    new['nodeType']='worldEntityNode'
                    new['debugName']=obj['name']
                    new['entityTemplate']=spawndata
                    new['appearanceName']=obj['app']
                    
                    pos,rot,scale=get_position(obj)
                    new['ent_rot']=rot.to_euler('XYZ')
                    new['ent_pos']=pos
                    inst_trans_mat=Matrix.LocRotScale(pos,rot,scale)
                    for child in group.children:
                        newchild=bpy.data.collections.new(child.name)
                        new.children.link(newchild)
                        for old_obj in child.objects:                            
                            obj=old_obj.copy()  
                            obj.color = (0.567942, 0.0247339, 0.600028, 1)
                            newchild.objects.link(obj)                                     
                            obj.matrix_local=  inst_trans_mat @ obj.matrix_local 
                            if 'Armature' in obj.name:
                                obj.hide_set(True)
                    for old_obj in group.objects:                            
                        obj=old_obj.copy()  
                        obj.color = (0.567942, 0.0247339, 0.600028, 1)
                        new.objects.link(obj)                                     
                        obj.matrix_local=  inst_trans_mat @ obj.matrix_local 
                        if 'Armature' in obj.name:
                            obj.hide_set(True)
                    if len(group.all_objects)>0:
                        new['matrix']=group.all_objects[0].matrix_world
        
                
if "MasterInstances" not in coll_scene.children.keys():
    coll_target=bpy.data.collections.new("MasterInstances")
    coll_scene.children.link(coll_target)
else:
    coll_target=bpy.data.collections.get("MasterInstances")



sectpathin = os.path.join(project_path,GroupName+'.json')
#sectpathin='C:\\CPMod\\notell\\blender_group5.json'
with open(sectpathin, 'r') as inputfile:
    j = json.load(inputfile)
print('loaded json for ', GroupName)
group_coll=bpy.data.collections.new(GroupName+'.json')
coll_scene.children.link(group_coll)
process_group(j,group_coll)
coll_target.hide_viewport=True
