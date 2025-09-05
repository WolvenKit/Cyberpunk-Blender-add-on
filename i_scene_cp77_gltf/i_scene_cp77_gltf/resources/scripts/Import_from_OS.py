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


project_path=r'C:\CPMod\corpo_apt'
GroupName='corpo_wall_test'
with_mats=False

import bpy
import os
import json
from math import pi,radians,degrees
from mathutils import Vector, Matrix, Euler
import traceback
D=bpy.data
C=bpy.context
coll_scene = C.scene.collection
shapes=["Box", "Capsule", "Sphere" ]

def get_position(obj):
    pos = Vector((obj['spawnable']['position']['x'],obj['spawnable']['position']['y'],obj['spawnable']['position']['z']))
    rot= Euler((radians(obj['spawnable']['rotation']['pitch']),
                            radians(obj['spawnable']['rotation']['roll']),
                            radians(obj['spawnable']['rotation']['yaw'])))
    if 'scale' in obj['spawnable'].keys():
        scale =Vector((obj['spawnable']['scale']['x'],obj['spawnable']['scale']['y'],obj['spawnable']['scale']['z']))
    else:
        scale=(1,1,1)
    return pos,rot,scale

            
def process_group(group,target_coll):
    for child in group['childs']:
        if 'type' in child.keys() and child['type']=='object':
            process_object(child,target_coll)
        elif 'type' in child.keys() and child['type']=='group':
            process_group(child,target_coll)
    
def process_object(obj,parent_coll):
    Masters=bpy.data.collections.get("MasterInstances")
    spawndata=obj['spawnable']['spawnData'] 
    spawntype=obj['spawnable']['dataType'] 
    if spawndata[-5:]=='.mesh' :     
        meshpath=os.path.join(project_path,'source','raw', spawndata[:-1*len(os.path.splitext(spawndata)[1])]+'.glb').replace('\\', os.sep)
        impapps=obj['spawnable']['app']
        groupname = os.path.splitext(os.path.split(meshpath)[-1])[0]
        while len(groupname) > 63:
            groupname = groupname[:-1]
        if groupname not in Masters.children.keys() and os.path.exists(meshpath):
            try:
                bpy.ops.io_scene_gltf.cp77(with_mats, filepath=meshpath, appearances=impapps,scripting=True)
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
        if spawntype=="Entity Template":
            app=obj['spawnable']['app']
            entpath=os.path.join(project_path,'source','raw', spawndata).replace('\\', os.sep)+'.json'
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
                group=move_coll                            
                if (group):
                    groupname=move_coll.name
                    #print('Group found for ',groupname)     
                    new=bpy.data.collections.new(groupname)
                    parent_coll.children.link(new)
                    new['nodeType']='worldEntityNode'
                    new['debugName']=obj['name']
                    new['entityTemplate']=spawndata
                    new['appearanceName']=obj['spawnable']['app']
                    
                    pos,rot,scale=get_position(obj)
                    rot=rot.to_quaternion()
                    new['ent_rot']=rot
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
        elif spawntype=="Collision Shape":            
            # from entspawner code: o.shapeTypes = { "Box", "Capsule", "Sphere" } so 0=box, 1=capsule, 2 = sphere
            ShapeType=shapes[obj['spawnable']['shape']]
            if ShapeType=='Box' :
                #print('Box Collision Node')
                #pprint(act['Shapes'])
                extents=obj['spawnable']['extents']
                position=obj['spawnable']['position']
                if ShapeType=='Box':
                    bpy.ops.mesh.primitive_cube_add(size=1, scale=(float(extents['x'])*2,float(extents['y'])*2,float(extents['z'])*2),
                    location=(float(position['x']),float(position['y']),float(position['z'])))
                    #location=(float(position['x'])+float(extents['x'])*2,float(position['y'])+float(extents['y'])*2,float(position['z'])+float(extents['z'])*2))
                crash=C.selected_objects[0]
                crash.name=obj['name']
                par_coll=crash.users_collection[0]
                par_coll.objects.unlink(crash)
                coll_scene.objects.link(crash)
                crash['ShapeType']=obj['spawnable']['shape']
                crash['matrix']=crash.matrix_world
                rot=obj['spawnable']['rotation']
                crash.rotation_mode='XYZ'
                crash.rotation_euler=(radians(rot['pitch']),radians(rot['roll']),radians(rot['yaw']))

    elif spawntype=='Decals':  
        vert = [(-0.5, -0.5, 0.0), (0.5, -0.5, 0.0), (-0.5, 0.5, 0.0), (0.5,0.5, 0.0)]
        fac = [(0, 1, 3, 2)]
        pl_data = bpy.data.meshes.new("PL")
        pl_data.from_pydata(vert, [], fac)
        pl_data.uv_layers.new(name="UVMap")
        
        o = bpy.data.objects.new("Decal_Plane", pl_data)
        o['nodeType']='worldStaticDecalNode'
        o['decal']=spawndata
        o['debugName']=obj['name']
        o['horizontalFlip']=obj['spawnable']['horizontalFlip']
        o['verticalFlip']=obj['spawnable']['verticalFlip']
        o['alpha']=obj['spawnable']['alpha']
        o['appearanceName']=obj['spawnable']['app']

        parent_coll.objects.link(o)
        pos,rot,scale=get_position(obj)
        o.location = pos
        o.rotation_mode = 'XYZ'
        o.rotation_euler = rot
        o.scale = scale  
                
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
