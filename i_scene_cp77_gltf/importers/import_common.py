import bpy
import os
import json
import traceback
from .import_with_materials import CP77GLBimport


def get_groupname(meshname, meshAppearance):
    groupname = os.path.splitext(os.path.split(meshname)[-1])[0]
    if 'intersection' in meshname:
        groupname = os.path.dirname(meshname).split(os.sep)[-1] + '_' + groupname
    if len(meshAppearance)>0:
        groupname += '@' + meshAppearance
    while len(groupname) > 63:
        groupname = groupname[:-1]
    return groupname

# Get the group name for the mesh based on its name and appearance
# group, groupname = get_group(meshname,meshAppearance)
def get_group(meshname,meshAppearance,Masters):
    groups= [g for g in Masters.children if 'meshpath' in g.keys() and g['meshpath']==meshname and 'appearance' in g.keys() and g['appearance']==meshAppearance]
    if len(groups)>0:
        group=groups[0]
        groupname = group.name
    else:
        groupname = get_groupname(meshname, meshAppearance)
        group = Masters.children.get(groupname)
        
    return group, groupname 

# add_to_list(m , meshes_w_apps)
def add_to_list(basename, meshes, dict):
     mesh = meshes[basename]
     if basename in dict:
        for app in mesh['appearances']:
            if app not in dict[basename]['apps'] and get_groupname(meshname, meshAppearance) not in bpy.data.collections.get("MasterInstances").children.keys():
                dict[basename]['apps'].append(mesh['appearance'])
        if mesh['sector'] not in dict[basename]['sectors']:
            dict[basename]['sectors'].append(mesh['sector'])
     else:
        dict[basename]={'apps':[mesh['appearances']],'sectors':[mesh['sector']]}

def meshes_from_mesheswapps( meshes_w_apps,path='', from_mesh_no=0, to_mesh_no=10000000, with_mats=False, glbs=[], mesh_jsons=[],Masters=None,generate_overrides=False):
    props = bpy.context.scene.cp77_panel_props 
    C=bpy.context
    coll_scene = C.scene.collection
    for i,m in enumerate(meshes_w_apps):
        if i>=from_mesh_no and i<=to_mesh_no and (m[-4:]=='mesh' or m[-13:]=='physicalscene' or m[-6:]=='w2mesh'):
            apps=[]
            for meshApp in meshes_w_apps[m]['apps'][0]:
                if meshApp['$value'] not in apps and meshApp['$value']!='':                   
                    apps.append(meshApp['$value'])
            if m[-13:]=='physicalscene' or m[-6:]=='w2mesh':
                meshpath=os.path.join(path, m+'.glb').replace('\\', os.sep)
                print('not a standard mesh')
            else:
                meshpath=os.path.join(path, m[:-1*len(os.path.splitext(m)[1])]+'.glb').replace('\\', os.sep)
            print(meshpath)
            groupname = get_groupname(meshpath, '')
            
            if groupname not in Masters.children.keys() and os.path.exists(meshpath):
                try:                    
                    CP77GLBimport( with_materials=with_mats,remap_depot= props.remap_depot, filepath=meshpath, appearances=apps,
                                    scripting=True, generate_overrides=generate_overrides)
                    
                    objs = C.selected_objects
                    if objs[0].users_collection[0].name!= groupname:
                        objs[0].users_collection[0].name= groupname
                    move_coll= coll_scene.children.get( objs[0].users_collection[0].name )
                    move_coll['meshpath']=m
                    move_coll['appearance']='default'
                    Masters.children.link(move_coll)
                    for app in apps:
                        # Create a completely new collection for this appearance
                        new_coll = bpy.data.collections.new(groupname + '@' + app)
                        Masters.children.link(new_coll)
                        new_coll['meshpath']=m
                        new_coll['appearance'] = app
                        # Set the appearance property
                        json_apps= None
                        if 'json_apps' in move_coll.keys():
                            json_apps =  json.loads(move_coll['json_apps'])
                        else:
                            print(f'{bcolors.FAIL}No material json found for - {m}{bcolors.ENDC}')
                        for idx,obj in enumerate(move_coll.objects):
                            obj_copy=obj.copy()
                            obj_copy.data = obj.data.copy()
                            if obj_copy.type == 'MESH':
                                if json_apps and app in json_apps and idx < len(json_apps[app]):
                                    # Assign the material from the json_apps if it exists
                                    mat_name = json_apps.get(app)[idx]
                                    if 'sidewalk' in m:
                                        mat_name = 'sidewalksidewalksidewalksidewalksidewalksidewalksidewalksidewalksidewalk'
                                       
                                    if len(mat_name)<63 and len(obj_copy.data.materials)>1 and mat_name in obj_copy.data.materials.keys():
                                        for ii in range(len(obj_copy.data.materials)-1,-1,-1):
                                            mat=obj_copy.data.materials.keys()[ii]
                                            if mat.split('.')[0]!=mat_name:
                                                obj_copy.data.materials.pop(index=ii)
                            new_coll.objects.link(obj_copy)                    
                    coll_scene.children.unlink(move_coll)
                except:
                    print('failed on ',os.path.basename(meshpath))                    
                    print(traceback.print_exc())
            elif not os.path.exists(meshpath):
                print('Mesh ', meshpath, ' does not exist')