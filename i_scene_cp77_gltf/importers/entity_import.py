# Blender Entity import script by Simarilius
# Updated May 23 with vehicle rig support
import json
import re
import glob
import os
import bpy
import time
import math
import traceback
from math import sin,cos
from mathutils import Vector, Matrix , Quaternion
import bmesh
from ..main.common import *
from ..jsontool import JSONTool
from .phys_import import cp77_phys_import
from ..collisiontools.collisions import draw_box_collider, draw_capsule_collider, draw_convex_collider, draw_sphere_collider
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
from .import_common import *
from bpy_extras import anim_utils


def create_axes(ent_coll,name):
    if name not in ent_coll.objects.keys():
        o = bpy.data.objects.new( name , None )

        ent_coll.objects.link( o )
        o.empty_display_size = .5
        o.empty_display_type = 'PLAIN_AXES'
        orig_rot= o.rotation_quaternion
        o.rotation_mode='XYZ'
    else:
        o=ent_coll.objects[name]
    return o

# The appearance list needs to be the appearanceNames for each ent that you want to import, will import all if not specified
# if you've already imported the body/head and set the rig up you can exclude them by putting them in the exclude_meshes list
# presto_stash=[]

def importEnt(with_materials, filepath='', appearances=[], exclude_meshes=[], include_collisions=False, include_phys=False,
                   include_entCollider=False, inColl='', remapdepot=False, meshes=None, mesh_jsons=None, escaped_path=None,
                   app_path=None, anim_files=None, rigjsons=None,generate_overrides=False):
    cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
    with_materials = with_materials
    if not cp77_addon_prefs.non_verbose:
        print('\n-------------------- Importing Cyberpunk 2077 Entity --------------------')
    C = bpy.context
    coll_scene = C.scene.collection
    start_time = time.time()

    before,mid,after=filepath.partition(os.path.join('source','raw'))
    path=before+mid

    error_messages = []
    entinitiatedcache = False
    if not JSONTool._use_cache:
        JSONTool.start_caching()
        entinitiatedcache = True

    ent_name=os.path.basename(filepath)[:-9]
    if not cp77_addon_prefs.non_verbose:
        if isinstance(appearances, list):
            print(f"Importing appearance: {', '.join(appearances)} from entity: {ent_name}")
        else:
            print(f"Importing appearance: {appearances} from entity: {ent_name}")
    if filepath is not None:
        ent_apps, ent_components, ent_component_data, res, ent_default = JSONTool.jsonload(filepath, error_messages)

    ent_applist=[]
    for app in ent_apps:
        ent_applist.append(app['appearanceName']['$value'])

    if len(ent_applist) == 0:
        print(f"No appearances found in entity file {ent_name}. Imported objects may be incomplete or missing.")
        #show_message("No appearances found in entity file. Imported objects may be incomplete or missing. "+ent_name)
        # this just isnt true, loads of stuff doesnt have appearances, and the popup is annoying

    #print(ent_applist)

    for appidx,app in enumerate(appearances):
        if app not in ent_applist and app.upper() !='ALL' and app !='default':
            print(f"Appearance {app} not found in entity {ent_name}. Available appearances: {', '.join(ent_applist)}")
            #show_message(f"Appearance {app} not found in entity {ent_name}. Available appearances: {', '.join(ent_applist)}")
            # this check is not actually checking all the options for how the app name is stored so its popping this up then loading it fine.
        if app not in ent_applist and app.upper() !='ALL' and app =='default':
            if ent_default and len(ent_default)>0 and ent_default!='None':
                print(f"Using default appearance {ent_default} for entity {ent_name}.")
                appearances[appidx]=ent_default
                print(appearances)
            else:                
                if len(ent_applist)>0:
                    print(f"No default appearance specified in entity {ent_name}. Using first available appearance {ent_applist[0]}.")
                    app=ent_applist[0]
                else:
                    print(f"No appearances specified in entity {ent_name}. Using root entities.")    
                    appearances[0]= 'BASE_COMPONENTS_ONLY'          
                    app='BASE_COMPONENTS_ONLY'


    #presto_stash.append(ent_components)
    ent_complist=[]
    ent_rigs=[]
    ent_colliderComps=[]
    ent_simpleCollComps=[]
    chassis_info=[]
    includes_license_plates=False
    for comp in ent_components:
        ent_complist.append(comp['name'])
        if 'rig' in comp.keys():
            print(f"Rig found in entity: {comp['rig']['DepotPath']['$value']}")
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
    for res_p in res:
        resolved.append(os.path.join(path,res_p['DepotPath']['$value']))

    # if no apps requested populate the list with all available.
    if len(appearances[0])==0 or appearances[0].upper()=='ALL':
        appearances=[]
        for app in ent_apps:
            appearances.append(app['appearanceName']['$value'])
        if len(appearances)==0:
            appearances.append('BASE_COMPONENTS_ONLY')

    VS=[]
    vehicle_slots=None
    for x in ent_components:
        if 'name' in x.keys() and x['name']['$value']=='vehicle_slots' or x['name']['$value']=='slots':
            VS.append(x)
    if len(VS)>0:
        vehicle_slots= VS[0]['slots']

    # find the appearance file jsons
    if not escaped_path:
        escaped_path = glob.escape(path)
    if not app_path:
        app_path = glob.glob(os.path.join(escaped_path,"**","*.app.json"), recursive = True)
    if len(app_path)==0:
        print('No Appearance file JSONs found in path, run the Ent export script first')

    # find the meshes
    if not meshes:
        meshes =  glob.glob(os.path.join(escaped_path,"**","*.glb"), recursive = True)
    if len(meshes)==0:
        print('No Meshes found in path, run the Ent export script first')
    if not mesh_jsons:
        mesh_jsons =  glob.glob(os.path.join(escaped_path,"**","*mesh.json"), recursive = True)

    # find the anims
    # look through the components and find an anim, and load that,
    # then check for an anim in the project thats using the rig (some things like the arch bike dont ref the anim in the ent)
    # otherwise just skip this section
    #
    if not anim_files:
        anim_files = glob.glob(os.path.join(escaped_path,"**","*anims.glb"), recursive = True)

    rig=None
    bones=None
    chunks=None

    if len(anim_files) == 0 or len(ent_rigs) == 0: # we have glbs and we have rigs called up in the ent
        print('no anim rig found')
    else:
        # get the armatures already in the model
        oldarms= [x for x in bpy.data.objects if 'Armature' in x.name]
        animsinres=[x for x in anim_files if x[:-4] in resolved]
        if len(animsinres)==0:
            for anim in anim_files:
                if os.path.exists(anim[:-3]+'anims.json'):
                    anm_j=JSONTool.jsonload(f"{anim[:-3]+'anims.json'}", error_messages)
                    if anm_j is not None:
                        if os.path.join(path,anm_j['Data']['RootChunk']['rig']['DepotPath']['$value']) in ent_rigs:
                            animsinres.append(os.path.join(path,anim))
                        # presto_stash.append(animsinres)

        if len(animsinres)>0 and os.path.exists(animsinres[0]):
            bpy.ops.io_scene_gltf.cp77(with_materials, filepath=animsinres[0],scripting=True)
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

    # find the rig json associated with the ent
    if not rigjsons:
        rigjsons = glob.glob(os.path.join(escaped_path,"**","*.rig.json"), recursive = True)
    rig_j=None
    if len(rigjsons)==0 or len(ent_rigs)==0:
        print('no rig json loaded')
    else:
        entrigjsons=[x for x in rigjsons if x[:-5] in ent_rigs]
        if len(entrigjsons)>0:
            for entrig in entrigjsons:
                rig_j=JSONTool.jsonload(entrig, error_messages)
                if rig_j is not None:
                    rig_j=rig_j['Data']['RootChunk']
                    print('rig json loaded')

    if len(meshes)<1 or len(app_path)<1 and len(ent_components)<1:
        print("You need to export the meshes and convert app and ent to json")
        pass

    else:
        coll_scene = C.scene.collection
        mis={}
        if "MasterInstances" not in coll_scene.children.keys():
            Masters=bpy.data.collections.new("MasterInstances")
            coll_scene.children.link(Masters)
        else:
            Masters=bpy.data.collections.get("MasterInstances")

        Masters.hide_viewport=False #if its hidden it breaks entity positioning for some reason?!?

        # loop through the appearances we want to import to find & load the meshes/appearances we need
        meshes={}
        app_comps={}
        ent_chunks={}
        for x,app_name in enumerate(appearances):
            app_comps[app_name]=[]
            # try to get components. only cases here.
            if len(ent_apps)==0 and ent_component_data:
                chunks= ent_component_data
            elif len(ent_apps)>0:
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

                if ent_app_idx<0:
                    if app_name != 'default':
                        ent_app_idx=0
                    else:
                        for i,a in enumerate(ent_apps):
                            if a['name']['$value']==ent_default:
                                print('appearance matched, id = ',i)
                                ent_app_idx=i
                                app_name=a['appearanceName']['$value']
                                continue


                app_file = ent_apps[ent_app_idx]['appearanceResource']['DepotPath']['$value']
                appfilepath=os.path.join(path,app_file).replace('\\',os.sep)+'.json'
                a_j=None
                if not os.path.exists(appfilepath):
                    print('app file not found -', filepath)
                else:
                    a_j=JSONTool.jsonload(appfilepath, error_messages)
                    if a_j is not None:
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
                                app_comps[app_name]= ent_components+a_j['Data']['RootChunk']['appearances'][app_idx]['Data']['components']
                            if 'compiledData' in a_j['Data']['RootChunk']['appearances'][app_idx]['Data'].keys():
                                chunks= a_j['Data']['RootChunk']['appearances'][app_idx]['Data']['compiledData']['Data']['Chunks']
                                ent_chunks[app_name]=chunks
                                print('Chunks found')


            if len(app_comps[app_name])==0:
                print('falling back to rootchunk components...')
                app_comps['BASE_COMPONENTS_ONLY']= ent_components
            exclude_meshes=[]
            for c in app_comps[app_name]:
                if not ( 'mesh' in c.keys() or 'graphicsMesh' in c.keys()):
                    continue
                if 'mesh' in c.keys() or 'graphicsMesh' in c.keys():
                   # print(c['mesh']['DepotPath']['$value'])
                    meshname=''
                    if 'mesh' in c.keys() and isinstance( c['mesh']['DepotPath']['$value'], str):
                        m=c['mesh']['DepotPath']['$value']
                        meshname=os.path.join(path, m).replace('\\', os.sep)
                    elif 'graphicsMesh' in c.keys() and isinstance( c['graphicsMesh']['DepotPath']['$value'], str):
                        m=c['graphicsMesh']['DepotPath']['$value']
                        meshname=os.path.join(path, m).replace('\\', os.sep)
                    if meshname and meshname not in exclude_meshes and os.path.exists(meshname[:-4]+'glb'):
                        meshApp='default'
                        if 'meshAppearance' in c.keys():
                            meshApp=c['meshAppearance']
                            #print(meshApp)
                        if(meshname != 0):
                            if meshname not in meshes:
                                meshes[meshname] = {'appearances':[meshApp],'sector':'ALL'}
                            else:
                                meshes[meshname]['appearances'].append(meshApp)

        meshes_w_apps={}

        for m in meshes:
            if len(m)>0:
                    add_to_list(m , meshes, meshes_w_apps)

        meshes_from_mesheswapps( meshes_w_apps, path, from_mesh_no=0, to_mesh_no=10000000, with_mats=with_materials, glbs=meshes, mesh_jsons=mesh_jsons,
                                    Masters=Masters,generate_overrides=generate_overrides)


        # loop through again to actually build the appearances
        for x,app_name in enumerate(appearances):
            print(f"\nImporting appearance {x+1} of {len(appearances)}: {app_name}")
            app_start_time = time.time()
            ent_coll = bpy.data.collections.new(ent_name+'_'+app_name)
            if inColl and inColl in coll_scene.children.keys():
                par_coll=bpy.data.collections.get(inColl)
                par_coll.children.link(ent_coll)
            else:
                #link it to the scene
                coll_scene.children.link(ent_coll)
            # tag it with some custom properties.
            ent_coll['depotPath']=after
            if len(ent_apps)==0 and ent_component_data:
                chunks= ent_component_data
            elif len(ent_apps)>0:
                ent_app_idx=-1
                # Find the appearance in the entity app list
                for i,a in enumerate(ent_apps):
                    if a['appearanceName']['$value']==app_name:
                        print('appearance matched, id = ',i)
                        ent_app_idx=i
                        continue

                # apparently they sometimes just sack it off and use the name not the appearanceName after all. (single_doors.ent for instance)
                if ent_app_idx<0:
                    for i,a in enumerate(ent_apps):
                        if a['name']['$value']==app_name:
                            print('appearance matched, id = ',i)
                            ent_app_idx=i
                            app_name=a['appearanceName']['$value']
                            continue

                if ent_app_idx<0:
                    if app_name != 'default':
                        ent_app_idx=0
                    else:
                        for i,a in enumerate(ent_apps):
                            if a['name']['$value']==ent_default:
                                print('appearance matched, id = ',i)
                                ent_app_idx=i
                                app_name=a['appearanceName']['$value']
                                continue
            if not chunks:
                chunks=ent_chunks[app_name]

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

            comps=app_comps[app_name]

            if not rig:
                for c in comps:
                    if 'name' in c.keys() and c['name']['$value']=='vehicle_slots' or c['name']['$value']=='slot':
                        VS.append(c)
                    if 'rig' in c.keys():
                        rig_path = os.path.join(path, c['rig']['DepotPath']['$value'])
                        ent_rigs.append(rig_path)
                        if rig_path in ent_rigs:
                            print(f"Rig found in app components: {c['rig']['DepotPath']['$value']}")
                            if rig is None:
                                rig_j=JSONTool.jsonload(rig_path+'.json', error_messages)
                                if rig_j is not None:
                                    rig_j=rig_j['Data']['RootChunk']
                                    print('rig json loaded')
                                if c['animations']['gameplay']!=None and len(c['animations']['gameplay'])>0 :                                # get the armatures already in the model
                                    oldarms= [x for x in bpy.data.objects if 'Armature' in x.name]
                                    animpath=os.path.join(path,c['animations']['gameplay'][0]['animSet']['DepotPath']['$value']+'.glb')
                                    if os.path.exists(animpath):
                                        bpy.ops.io_scene_gltf.cp77(with_materials, filepath=animpath, scripting=True)
                                        # find the armature we just loaded
                                        arms=[x for x in bpy.data.objects if 'Armature' in x.name and x not in oldarms]
                                        rig=arms[0]
                                        bones=rig.pose.bones
                                        rig["animset"] = animpath
                                        rig["rig"] = rig_path
                                        rig["ent"] = ent_name + ".ent.json"
                                        print('anim rig loaded')
                            elif rig['rig']==rig_path:
                                print('using existing rig')
                            else:
                                print('another rig',rig['rig'],' is already loaded ',rig_path)
            if not vehicle_slots:
                if len(VS)>0:
                    vehicle_slots= VS[0]['slots']


            for c in comps:
                vs_rot=None
                if 'license_plate' in c['name']['$value']:
                    includes_license_plates = True
                    print('License plate component found:', c['name']['$value'])
                if not (c['$type']=='gameTransformAnimatorComponent' or 'mesh' in c.keys() or 'graphicsMesh' in c.keys()):
                    continue

                if c['$type']=='gameTransformAnimatorComponent' and c['animations'][0]['$type']=='gameTransformAnimationDefinition':
                    duration=c['animations'][0]['timeline']['items'][0]['duration']
                    HRID=c['animations'][0]['timeline']['items'][0]['impl']['HandleRefId']
                    chunk_anim = 0
                    anim_HId=0
                    # find the anim data in the chunks
                    if chunks:
                        for chunk in chunks:
                            if chunk['$type']!='gameTransformAnimatorComponent':
                                continue
                            if 'HandleId' in chunk['animations'][0]['timeline']['items'][0]['impl'].keys():
                                if int(chunk['animations'][0]['timeline']['items'][0]['impl']['HandleId'])==int(HRID):
                                    chunk_anim=chunk['animations'][0]['timeline']['items'][0]['impl']['Data']
                    if isinstance(chunk_anim, dict) and chunk_anim['$type']=='gameTransformAnimation_RotateOnAxis':
                        rot_axis=chunk_anim['axis']
                        axis_no=0 # default to x
                        if rot_axis=='Z':
                            axis_no=2
                            
                        elif rot_axis=='Y': #y & z are swapped
                            axis_no=1

                        reverse=chunk_anim['reverseDirection']
                        no_rot=chunk_anim['numberOfFullRotations']
                        o = create_axes(ent_coll=ent_coll,name=c['name']['$value'])
                        o.keyframe_insert('rotation_euler', index=axis_no ,frame=1)
                        o.rotation_euler[axis_no] = o.rotation_euler[axis_no] +math.radians(no_rot*(-1*reverse)*360)
                        o.keyframe_insert('rotation_euler', index=axis_no ,frame=duration*24)
                        if o.animation_data.action:
                            obj_action = bpy.data.actions.get(o.animation_data.action.name)
                            obj_slot = o.animation_data.action_slot
                            channelbag = anim_utils.action_get_channelbag_for_slot(obj_action, obj_slot)
                            obj_fcu = channelbag.fcurves[0]
                            modifier = obj_fcu.modifiers.new(type='CYCLES')
                            modifier.mode_before = 'REPEAT'
                            modifier.mode_after = 'REPEAT'
                            for pt in obj_fcu.keyframe_points:
                                pt.interpolation = 'LINEAR'
                elif 'mesh' in c.keys() or 'graphicsMesh' in c.keys():
                    #print(c['mesh']['DepotPath']['$value'])
                    meshname=''
                    if 'mesh' in c.keys() and isinstance( c['mesh']['DepotPath']['$value'], str):
                        m=c['mesh']['DepotPath']['$value']
                        meshname=os.path.basename(m.replace('\\',os.sep))
                        meshpath=os.path.join(path, m[:-1*len(os.path.splitext(m)[1])]+'.glb').replace('\\', os.sep)
                    elif 'graphicsMesh' in c.keys() and isinstance( c['graphicsMesh']['DepotPath']['$value'], str):
                        m=c['graphicsMesh']['DepotPath']['$value']
                        meshname=os.path.basename(m)
                        meshpath=os.path.join(path, m[:-1*len(os.path.splitext(m)[1])]+'.glb').replace('\\', os.sep)
                    if meshname and meshname not in exclude_meshes and os.path.exists(meshpath):
                        new=None
                        try:
                            meshApp='default'
                            if 'meshAppearance' in c.keys():
                                meshApp=c['meshAppearance']['$value']
                                #print(meshApp)
                            try:
                                # TODO: sim, this is broken, pls fix Y_Y
                                # make this instance from masters rather than loading multiple times
                                #bpy.ops.io_scene_gltf.cp77(with_materials, filepath=meshpath, appearances=meshApp,scripting=True,generate_overrides=generate_overrides)
                                group, groupname = get_group(meshpath,meshApp,Masters)
                                if (group):
                                    new=bpy.data.collections.new(groupname)
                                    ent_coll.children.link(new)
                                    for old_obj in group.all_objects:
                                        obj=old_obj.copy()
                                        new.objects.link(obj)
                                    for obj in new.objects:
                                        obj['componentName'] = c['name']['$value']
                                        obj['sourcePath'] = meshpath
                                        obj['meshAppearance'] = meshApp
                                        if app_path:
                                            obj['appResource'] = app_path[0]
                                        obj['entAppearance'] = app_name
                                        if 'Armature' in obj.name:
                                            obj.hide_set(True)
                            except:
                                print('import threw an error:')
                                print(traceback.format_exc())
                                continue
                            print('checking for collection - ', meshname)
                            if new is None:
                                print('collection not found after import - ', meshname)
                                continue
                            objs = new.objects
                            if 'body_01' in meshname:
                                print('those annoying front forks')

                            # NEW parentTransform stuff - fixes vehicles being exploded
                            x=None
                            y=None
                            z=None
                            bindname=None
                            bindpt=None
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
                                                        break
                                                        #print('HandleId found',chunk['parentTransform']['HandleId'])

                                # if we found it then process it, most chars etc will just skip this
                                if chunk_pt:
                                    #print('in chunk pt processing bindName = ',chunk_pt['Data']['bindName'],' slotname= ',chunk_pt['Data']['slotName'])
                                    # parts have a bindname, and sometimes a slotname
                                    bindname=chunk_pt['Data']['bindName']['$value']
                                    slotname=chunk_pt['Data']['slotName']['$value']
                                    # if it has a bindname of vehicle_slots, you may need to find the bone name in the vehicle slots in the root ent components
                                    # this should have been loaded earlier, check for it in the vehicle slots if not just set to the slot value
                                    if bindname=='vehicle_slots' or bindname=='slots':
                                        if vehicle_slots:
                                            for slot in vehicle_slots:
                                                if slot['slotName']['$value']==slotname:
                                                    bindname=slot['boneName']['$value']
                                        else:
                                            bindname= chunk_pt['Data']['slotName']['$value']

                                    # some meshes have boneRigMatrices in the mesh file which means we need jsons for the meshes or we cant access it. oh joy
                                    elif bindname=="deformation_rig" and (not chunk_pt['Data']['slotName']['$value'] or len(chunk_pt['Data']['slotName']['$value'])==1 or chunk_pt['Data']['slotName']['$value']=='None'):
                                        json_name=os.path.join(path, c['mesh']['DepotPath']['$value']+'.json')
                                        #print:("in the deformation rig bit",json_name)
                                        if json_name in mesh_jsons:
                                            mesh_j = JSONTool.jsonload(json_name, error_messages)
                                            mesh_j=mesh_j['Data']['RootChunk']
                                        if mesh_j is not None:
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
                                                bn=mesh_j['boneNames'][0]['$value']
                                                xdisp=0
                                                ydisp=0
                                                zdisp=0

                                                if bn in bones.keys():
                                                    bone=bones[mesh_j['boneNames'][0]['$value']]
                                                    # the transform matrix above is in the orientation of the bone that its linked to, so I'm doing a bodged job of correcting for that here.
                                                    bone_mat_rot=bone.matrix.to_euler()
                                                    #print(bone_mat_rot)
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
                                        if bindname=='interior_02':
                                            print('interior_02')
                                        bindpt=[cmp for cmp in comps if cmp['name']['$value']==bindname]
                                        slotname= chunk_pt.get('Data').get('slotName').get('$value')
                                        #if bindpt and slotname:
                                            # Have a bindpoint and a slotname, so we can use the local transform from the bindpoint
                                            #print('bindpt and slotname found')

                                        if bindpt and len(bindpt)==1:
                                            if c['localTransform']['Position']['x']['Bits']==0 and c['localTransform']['Position']['y']['Bits']==0 and c['localTransform']['Position']['z']['Bits']==0 and 'localTransform' in bindpt[0]:
                                                c['localTransform']['Position']=bindpt[0]['localTransform']['Position']
                                            if c['localTransform']['Orientation']['i']==0 and c['localTransform']['Orientation']['j']==0 and c['localTransform']['Orientation']['k']==0 and c['localTransform']['Orientation']['r']==1 and 'localTransform' in bindpt[0]:
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
                                                if o['name']['$value']==bindname and 'parentTransform' in o.keys():
                                                    pT=o['parentTransform']
                                                    if pT:

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
                                        if bindname in bones.keys() and rig_j is not None and rig_j['boneNames'] is not None:
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
                                                vs=[slot for slot in vehicle_slots if slot['slotName']['$value']==slotname]
                                                vs_rot=Quaternion([0,0,0,1])
                                                vs_pos= Vector([0,0,0])
                                                vs_scale=Vector([1,1,1])
                                                if len(vs)>0:
                                                    vs=vs[0]
                                                    if 'relativeRotation' in vs.keys():
                                                        vs_rot[0]=vs['relativeRotation']['i']
                                                        vs_rot[1]=vs['relativeRotation']['j']
                                                        vs_rot[2]=vs['relativeRotation']['k']
                                                        vs_rot[3]=vs['relativeRotation']['r']
                                                    if 'relativePosition' in vs.keys():
                                                        vs_pos[0]=vs['relativePosition']['X']
                                                        vs_pos[1]=vs['relativePosition']['Y']
                                                        vs_pos[2]=vs['relativePosition']['Z']
                                                        #print('vs_rot = ',vs_rot)
                                                vs_mat=Matrix.LocRotScale(Vector([0,0,0]),vs_rot,vs_scale)
                                                pt_mat=Matrix.LocRotScale(Vector([0,0,0]),pt_rot,Vector(vs_scale))
                                                vs_z_ang=vs_mat.to_euler().z
                                                pt_z_ang=pt_mat.to_euler().z

                                                if obj.location != pt_trans:
                                                    obj.location.x +=  pt_trans[0]+vs_pos[0]
                                                    obj.location.y += pt_trans[1]+vs_pos[1]
                                                    obj.location.z +=  pt_trans[2]+vs_pos[2]
                                                else:    
                                                    obj.location.x =   pt_trans[0]+vs_pos[0]
                                                    obj.location.y = pt_trans[1]+vs_pos[1]
                                                    obj.location.z =  pt_trans[2]+vs_pos[2]

                                                obj.rotation_quaternion.x = btrans['Rotation']['i']
                                                obj.rotation_quaternion.y = btrans['Rotation']['j']
                                                obj.rotation_quaternion.z = btrans['Rotation']['k']
                                                obj.rotation_quaternion.w = btrans['Rotation']['r']


                                                obj.rotation_quaternion=obj.rotation_quaternion*Quaternion(vs_rot)
                                                #obj.matrix_local=  obj.matrix_local @ vs_mat
                                                #obj.matrix_world= pt_mat @ obj.matrix_world
                                                
                                                #Apply child of constraints to them and set the inverse
                                                if 'fuel_cap' not in bindname:
                                                    if 'Child Of' not in obj.constraints.keys():                                                        
                                                        co=obj.constraints.new(type='CHILD_OF')
                                                        co.target=rig
                                                        co.subtarget= bindname
                                                        bpy.context.view_layer.objects.active = obj
                                                        bpy.ops.constraint.childof_set_inverse(constraint=loc("Child Of"), owner='OBJECT')
                                                else:
                                                    # Apply location constraint to the fuel cap
                                                    co=obj.constraints.new(type='COPY_LOCATION')
                                                    co.target=rig
                                                    co.subtarget= bindname
                                                if 'wheel' in bindname:
                                                    # Apply Copy Rotation constraint to the wheels
                                                    cr=obj.constraints.new(type='COPY_ROTATION')
                                                    cr.target=rig
                                                    if 'steering' not in bindname:
                                                        cr.subtarget= bindname

                                    # Deal with TransformAnimators
                                    #if 'TransformAnimator' in bindname:
                                    if bindpt and bindpt[0]['$type']=='gameTransformAnimatorComponent':
                                        ta=[tacmp for tacmp in comps if tacmp['name']['$value']==bindname ][0]
                                        x=ta['localTransform']['Position']['x']['Bits']/131072
                                        y=ta['localTransform']['Position']['y']['Bits']/131072
                                        z=ta['localTransform']['Position']['z']['Bits']/131072
                                        target=create_axes(ent_coll, bindname)
                                        for ix,obj in enumerate(objs):
                                            if target:
                                                cr=obj.constraints.new(type='COPY_ROTATION')
                                                cr.target=target
                                            else:
                                                target=obj

                            # end new stuff
                            # dont get the local transform here if we already did it before
                            if not x:
                                x=c['localTransform']['Position']['x']['Bits']/131072
                            if not y:
                                y=c['localTransform']['Position']['y']['Bits']/131072
                            if not z:
                                z=c['localTransform']['Position']['z']['Bits']/131072
                            #print ('Local transform  x= ',x,'y= ',y,' z= ',z)

                            # local transforms are in the original mesh coord sys, but get applied after its already re-oriented, mainly only matters for wheels.
                            # this is hacky af as I cant be arsed dealing with doing it properly with quaternions or whatever right now. Feel free to fix it.
                            if bindname and bones and bindname in bones.keys() and bindname!='Base':
                                z_ang=bones[bindname].matrix.to_euler().z
                                x_orig=x
                                y_orig=y
                                x=x_orig*cos(z_ang)+y_orig*sin(z_ang)
                                y=x_orig*sin(z_ang)+y_orig*cos(z_ang)
                                #print ('Local transform  x= ',x,'y= ',y,' z= ',z)

                            for obj in new.objects:
                                #print(obj.name, obj.type)
                                obj.location.x =  obj.location.x+x
                                obj.location.y = obj.location.y+y
                                obj.location.z =  obj.location.z+z
                                # shouldnt need the 0 check, pretty sure I've fuked up a default somewhere, but at this point I just want it to work.
                                if 'Orientation' in c['localTransform'].keys() and (sum(obj.rotation_quaternion[:])<1.1  and sum(obj.rotation_quaternion[:])>0.9) or (sum(obj.rotation_quaternion[:])<0.1 and sum(obj.rotation_quaternion[:])>-0.1):
                                    lrot=get_rot(c['localTransform'])
                                    obj.rotation_quaternion = obj.rotation_quaternion * Quaternion(lrot)
                                    obj.rotation_quaternion.x = c['localTransform']['Orientation']['i']
                                    obj.rotation_quaternion.y = c['localTransform']['Orientation']['j']
                                    obj.rotation_quaternion.z = c['localTransform']['Orientation']['k']
                                    obj.rotation_quaternion.w = c['localTransform']['Orientation']['r']
                                #if vs_rot:
                                #    obj.matrix_local =  Matrix.LocRotScale(Vector(0,0,0),Quaternion(vs_rot),Vector(1,1,1)) @
                                if 'scale' in c['localTransform'].keys():
                                    obj.scale.x = c['localTransform']['scale']['X']
                                    obj.scale.y = c['localTransform']['scale']['Y']
                                    obj.scale.z = c['localTransform']['scale']['Z']
                                if 'visualScale' in c.keys():
                                    obj.scale.x = c['visualScale']['X']
                                    obj.scale.y = c['visualScale']['Y']
                                    obj.scale.z = c['visualScale']['Z']

                            if (len(objs) > 0):
                                move_coll=new
                                move_coll['depotPath']=c['mesh']['DepotPath']['$value']
                                move_coll['meshAppearance']=meshApp
                                if 'meshpath' not in move_coll:
                                    move_coll['meshpath']="its an entity"
                                if bindname:
                                    move_coll['bindname']=bindname
                                if move_coll.name in coll_scene.children:
                                    coll_scene.children.unlink(move_coll)

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
                                    subnum = None
                                    # Try to parse index from object name like 'submesh_00'
                                    m = re.search(r"submesh_(\d+)", obj.name, re.IGNORECASE)
                                    if m:
                                        subnum = int(m.group(1))
                                    else:
                                        # Fallback: try from material names
                                        mats = getattr(obj.data, 'materials', []) if hasattr(obj, 'data') else []
                                        for mat in mats:
                                            if mat and getattr(mat, 'name', None):
                                                m2 = re.search(r"submesh_(\d+)", mat.name, re.IGNORECASE)
                                                if m2:
                                                    subnum = int(m2.group(1))
                                                    break
                                    if subnum is None:
                                        continue
                                    bit = cm_list[subnum] if subnum < len(cm_list) else True
                                    obj.hide_set(not bit)
                                    obj.hide_render = not bit

                        except:
                            print("Failed on ",meshname)
                            print(traceback.format_exc())

            for c in ent_component_data:
                if (c['$type']=='entLightChannelComponent'):
                    print('Light channel found')
                    mesh_obj=None
                    lcgroup=None
                    lcgroupname=c['name']['$value']
                    if not lcgroupname in bpy.data.collections.get("MasterInstances").children.keys():
                        if 'shape' in c.keys() and 'Data' in c['shape'].keys() and 'vertices' in c['shape']['Data'].keys():
                            vertices=c['shape']['Data']['vertices']
                            if len(vertices)>0 and 'indices' in c['shape']['Data'].keys():
                                indices=c['shape']['Data']['indices']
                                if len(indices)>0:
                                    lcgroup=bpy.data.collections.new(lcgroupname)
                                    mesh_data = bpy.data.meshes.new(lcgroupname)
                                    mesh_obj = bpy.data.objects.new(mesh_data.name, mesh_data)
                                    mesh_obj.display_type = 'WIRE'
                                    mesh_obj.color = (0.005, 0.79105, 1, 1)
                                    mesh_obj.show_wire = True
                                    mesh_obj.show_in_front = True
                                    mesh_obj.display.show_shadows = False
                                    mesh_obj.rotation_mode = 'QUATERNION'
                                    verts=[]
                                    for v in vertices:
                                        verts.append((v['X'],v['Y'],v['Z']))
                                    edges=[]
                                    Faces=[indices[i:i+3] for i in range(0, len(indices), 3)]
                                    mesh_data.from_pydata(verts, edges, Faces)
                                    mesh_obj['ntype'] = 'entLightChannelComponent'
                                    mesh_obj['name'] = c['name']['$value']
                                    mesh_obj['entJSON'] = filepath

                                    bindname=c['parentTransform']['Data']['bindName']['$value']
                                    if bindname=='vehicle_slots':
                                        if vehicle_slots:
                                            slotname=c['parentTransform']['Data']['slotName']['$value']
                                            if slotname=='None':
                                                slotname='Base'
                                            for slot in vehicle_slots:
                                                if slot['slotName']['$value']==slotname:
                                                    bindname=slot['boneName']['$value']
                                                    mesh_obj['bindname']=bindname
                                    lcgroup.objects.link(mesh_obj)
                                    Masters.children.link(lcgroup)
                    if lcgroupname in bpy.data.collections.get("MasterInstances").children.keys():
                        Mastlcgroup=bpy.data.collections.get(lcgroupname)
                        if (Mastlcgroup):
                            lcgroup=bpy.data.collections.new(lcgroupname)
                            ent_coll.children.link(lcgroup)
                            for old_obj in Mastlcgroup.all_objects:
                                obj=old_obj.copy()
                                lcgroup.objects.link(obj)
                            mesh_obj=lcgroup.all_objects[0]
                            bindname=mesh_obj.get('bindname','')
                        if bindname and rig and lcgroup and mesh_obj:
                            co=mesh_obj.constraints.new(type='COPY_LOCATION')
                            co.target=rig
                            co.subtarget= bindname
            print('Appearance import time:', time.time() - app_start_time, 'Seconds')


        # am checking for license plates as we go rather than parsing all the components again.
        if includes_license_plates:
            license_plates = [obj for obj in bpy.data.objects if 'license_plate' in obj.get('componentName', '')]
            bumper_f_objs = [obj for obj in bpy.data.objects if 'bumper_f' in obj.get('componentName', '')]
            bumper_b_objs = [obj for obj in bpy.data.objects if 'bumper_b' in obj.get('componentName', '')]

            if len(license_plates) > 0:
                for obj in license_plates:
                    #print(obj.name)
                    if not len(obj.constraints)>0:
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

              # find the .phys file jsons
        if include_collisions:
            collision_collection = bpy.data.collections.new('colliders')
            ent_coll.children.link(collision_collection)
            if include_phys:
                try:
                    physJsonPaths = glob.glob(escaped_path + "\**\*.phys.json", recursive=True)
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
                                cp77_phys_import(physJsonPath, rig, chassis_z)
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
    if rig:
        arm=bpy.data.armatures[rig.name]
        arm.pose_position = 'REST'
    if entinitiatedcache:
        JSONTool.stop_caching()
    if len(error_messages) > 0:
        show_message('Errors during import:\n\t' + '\n\t'.join(error_messages))
    Masters.hide_viewport=True
    if not cp77_addon_prefs.non_verbose:
        print(f"Imported Entity in {time.time() - start_time} Seconds from {ent_name}.ent")
        print('-------------------- Finished Importing Cyberpunk 2077 Entity --------------------\n')

# The above is  the code thats for the import plugin below is to allow testing/dev, you can run this file to import something

if __name__ == "__main__":

    path = 'F:\\CPmod\\heist_hotel\\source\\raw'
    ent_name = 'single_door.ent'
    # The list below needs to be the appearanceNames for each ent that you want to import
    # NOT the name in appearances list, expand it and its the property inside, also its name in the app file
    appearances =['kitsch_f']
    escaped_path = glob.escape(path)
    jsonpath = glob.glob(escaped_path+"\**\*.ent.json", recursive = True)
    if len(jsonpath)==0:
        print('No jsons found')

    for i,e in enumerate(jsonpath):
        if os.path.basename(e)== ent_name+'.json' :
            filepath=e

    importEnt( filepath, appearances )
