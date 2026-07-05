import bpy
import os
import json
import time
from io_scene_gltf2.io.imp.gltf2_io_gltf import glTFImporter
vers = bpy.app.version
if vers[0] == 4 and vers[1] < 3:
    from io_scene_gltf2.blender.imp.gltf2_blender_gltf import BlenderGlTF
else:
    from io_scene_gltf2.blender.imp.blender_gltf import BlenderGlTF
from ..main.setup import MaterialBuilder
from ..main.bartmoss_functions import UV_by_bounds
from .import_from_external import *
from .attribute_import import manage_garment_support
from ..cyber_props import add_anim_props, add_skin_props
from ..jsontool import JSONTool
from ..main.common import show_message, exclusion_cache
from ..animtools.tracks import import_anim_tracks, fix_anim_frame_alignment
import traceback

def get_anim_info(animations, oldanims, import_tracks):
    """Integrate track import/alignment when properties are added to actions.
    Keeps original logic/printing; only adds track import + alignment.
    """
    cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
    verbose = not cp77_addon_prefs.non_verbose

    if bpy.app.version >= (4, 4, 0):
        old_names = {getattr(x, 'name', x) for x in (oldanims or [])}
        # Only actions created during this import
        new_actions = [a for a in bpy.data.actions if a.name not in old_names]
        for anim in (animations or []):
            base = anim.name
            found = False
            for act in new_actions:
                n = act.name
                if n == base or (n.startswith(base + ".") and n[len(base) + 1 :].isdigit()):
                    add_anim_props(anim, act)
                    if import_tracks:
                        try:
                            import_anim_tracks(act)
                            fix_anim_frame_alignment(act)
                        except Exception as e:
                            if verbose:
                                print(f"Track integration failed for action {n}: {e}")
                        found = True
                        if verbose:
                            print(f"Properties added to action: {n} succesfully")
            if not found and verbose:
                print(f"No action found for {base}")
        return{'FINISHED'}
    else:
        # left in for pre blender 4.4 users
        for animation in animations:
            if verbose:
                print(f"Processing animation: {animation.name}")

            # Find an action whose name contains the animation name
            action = next((act for act in bpy.data.actions if act.name.startswith(animation.name + "_Armature")), None)

            if action:
                add_anim_props(animation, action)
                try:
                    import_anim_tracks(action)
                    fix_anim_frame_alignment(action)
                except Exception as e:
                    if verbose:
                        print(f"Track integration failed for action {action.name}: {e}")
                if verbose:
                    print("Properties added to", action.name)
            else:
                if verbose:
                    print("No action found for", animation.name)

def objs_in_col(top_coll, objtype):
    return sum(1 for obj in top_coll.all_objects if obj.type == objtype)

# will collapse glTF_not_exported collection in the outliner
def disable_collection_by_name(collection_name):
    for vl in bpy.context.scene.view_layers:
        for l in vl.layer_collection.children:
             if l.name.lower() == collection_name.lower():
                l.exclude = True


existingMaterials = None
imported = None
appearances = None
collection = None

def CP77GLBimport( with_materials=False, remap_depot=False, exclude_unused_mats=True, image_format='png', filepath='', hide_armatures=True, import_garmentsupport=False, files=[], directory='', appearances=[], scripting=False, import_tracks=False, generate_overrides=False):
    cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
    verbose = not cp77_addon_prefs.non_verbose
    context=bpy.context
    oldanims = None
    ## switch to pose mode if it's not already
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

   # obj = None
    start_time = time.time()
    if not scripting:
        loadfiles=files
    else:
        f={}
        f['name']=os.path.basename(filepath)
        loadfiles=(f,)
    glbname=os.path.basename(filepath)
    DepotPath=cp77_addon_prefs

    oldanims={}
    if verbose:
        if ".anims.glb" in filepath:
            bpy.context.scene.render.fps = 30
            oldanims = {act.name for act in bpy.data.actions}
            print('\n-------------------- Beginning Cyberpunk Animation Import --------------------')
            print(f"Importing Animations From: {glbname}")

        else:
            print('\n-------------------- Beginning Cyberpunk Model Import --------------------')
            if with_materials==True:
                print(f"Importing: {glbname} with materials")
                print(f"Appearances to Import: ",appearances)
            else:
                print(f"Importing: {glbname}")
    # prevent crash if no directory supplied when using filepath
    if len(directory)==0 or scripting:
        directory = os.path.dirname(filepath)


    file_names=[]
    file_paths=[]
    for f in loadfiles:
        file_names.append( f['name'])
        file_paths.append(os.path.join(directory, f['name']))

    # check materials
    heuristic='BLENDER'
    if cp77_addon_prefs.enable_temperance:
        heuristic='TEMPERANCE'
    octos=False
    if cp77_addon_prefs.enable_octo:
        octos=True

    #mana: error messages - display one popup, not 500k
    errorMessages = []
    meshinitiated_cache = False
    if not JSONTool._use_cache:
        JSONTool.start_caching()
        meshinitiated_cache = True

    #Kwek: Gate this--do the block iff corresponding Material.json exist
    #Kwek: was tempted to do a try-catch, but that is just La-Z
    #Kwek: Added another gate for materials
    for f in loadfiles:
        filename=os.path.splitext(os.path.splitext(f['name'])[0])[0]
        filepath = os.path.join(directory, f['name'])
        if vers[0] == 4 and vers[1] >= 2 and vers[1] < 4:
            gltf_importer = glTFImporter(filepath, { "files": None, "loglevel": 0, "import_pack_images" :True, "merge_vertices" :False, "import_shading" : 'NORMALS', "bone_heuristic":heuristic, "guess_original_bind_pose" : False, "import_user_extensions": "",'disable_bone_shape':octos, 'bone_shape_scale_factor':1.0})
        elif vers[0] == 4 and vers[1] > 3 and vers[1] < 5:
            gltf_importer = glTFImporter(filepath, { "files": None, "loglevel": 0, "import_pack_images" :True, "merge_vertices" :False, "import_shading" : 'NORMALS', "bone_heuristic":heuristic, "guess_original_bind_pose" : False, "import_user_extensions": "",'disable_bone_shape':octos, 'bone_shape_scale_factor':1.0, 'import_scene_extras':True, 'import_select_created_objects':True})
        elif (vers[0] == 4 and vers[1] >= 5) or vers[0] > 4:
            gltf_importer = glTFImporter(filepath, { "files": None, "loglevel": 0, "import_pack_images" :True, 'import_unused_materials' :False, "merge_vertices" :False, "import_shading" : 'NORMALS', "bone_heuristic":heuristic, "guess_original_bind_pose" : False, "import_user_extensions": "",'disable_bone_shape':octos, 'bone_shape_scale_factor':1.0, 'import_scene_as_collection':True, 'import_scene_extras':True, 'import_select_created_objects':True, 'import_merge_material_slots':False})
        else:
            gltf_importer = glTFImporter(filepath, { "files": None, "loglevel": 0, "import_pack_images" :True, "merge_vertices" :False, "import_shading" : 'NORMALS', "bone_heuristic":heuristic, "guess_original_bind_pose" : False, "import_user_extensions": "",'disable_bone_shape':octos, 'import_select_created_objects':True,})
        gltf_importer.read()
        gltf_importer.checks()
        existingMeshes = {mesh.name for mesh in bpy.data.meshes}

        current_file_base_path = os.path.join(os.path.dirname(filepath),filename)
        has_material_json = os.path.exists(current_file_base_path + ".Material.json")

        existingMaterials = {mat.name for mat in bpy.data.materials}
        BlenderGlTF.create(gltf_importer)
        exclusion_cache.clear_cache()
        imported=context.selected_objects #the new stuff should be selected

        # if we're not importing a Cyberpunk mesh, not all submesh names will start with submesh_00, and they will be nested weirdly.
        # we want to clean this up.
        imported_meshes = [obj for obj in imported if obj.type == "MESH"]
        imported_empties = [obj for obj in imported if obj.type == "EMPTY"]
        isExternalImport = len(imported_empties) > 0 or sum(1 for mesh in imported_meshes if mesh.name.startswith("submesh")) != len(imported_meshes)

        mesh_objects = [obj for obj in imported if obj.type == 'MESH']
        multimesh = any(
            obj.name and obj.name[0].isdigit() and '_' in obj.name
            for obj in mesh_objects
        )
        exclude_unused_mats = exclude_unused_mats and all(obj.type == 'MESH' for obj in imported)

        if multimesh:
            isExternalImport = False

        if isExternalImport:
            CP77_cleanup_external_export(imported)


        imported= context.selected_objects #the new stuff should be selected
        if f['name'][:7]=='terrain':
            UV_by_bounds(imported)

        #create a collection by file name
        collection = bpy.data.collections.new(filename)
        bpy.context.scene.collection.children.link(collection)
        for o in imported:
            import_meshes_and_anims(collection, gltf_importer, hide_armatures, o, filename, oldanims, import_tracks)

        collection['orig_filepath']=filepath
        collection['numMeshChildren']=objs_in_col(collection, 'MESH')
        collection['numArmatureChildren']=objs_in_col(collection, 'ARMATURE')

        disable_collection_by_name("glTF_not_exported")

        #for sketchfab exports, we want to keep our materials
        if not isExternalImport:
            for mat in list(bpy.data.materials):
                if mat.name not in existingMaterials:
                    bpy.data.materials.remove(mat, do_unlink=True, do_id_user=True, do_ui_user=True)

        #Kwek: Gate this--do the block if corresponding Material.json exist
        #Kwek: was tempted to do a try-catch, but that is just La-Z
        #Kwek: Added another gate for materials
        DepotPath=None

        blender_4_scale_armature_bones(imported)

        if ".anims.glb" in filepath:
            continue


        if with_materials == True:
            json_apps = {} # always initialize this

            if has_material_json:
                matjsonpath = current_file_base_path + ".Material.json"
                DepotPath, json_apps, mats = JSONTool.jsonload(matjsonpath, errorMessages)

            if DepotPath == None:
                print(f"Failed to read DepotPath, skipping material import (hasMaterialJson: {has_material_json})")
                continue

        #DepotPath = str(obj["MaterialRepo"])  + "\\"
        context=bpy.context # TODO: Do we need this here?
        if remap_depot and os.path.exists(cp77_addon_prefs.depotfolder_path):
            DepotPath = cp77_addon_prefs.depotfolder_path
            if verbose:
                print(f"Using depot path: {DepotPath}")
        if DepotPath!=None:
            DepotPath= DepotPath.replace('\\', os.sep)

        if import_garmentsupport:
            manage_garment_support(existingMeshes, gltf_importer)

        # the rest of the function deals with material import and validation
        if with_materials != True:
            continue

        # validate materials, and don't import duplicates. Have this outside the loop/conditional so that it's valid but empty.
        validmats={}
        # fix the app names as for some reason they have their index added on the end.
        if len(json_apps) > 0:

            appkeys = list(json_apps)
            for i,k in enumerate(appkeys):
                json_apps[k[:-1*len(str(i))]]=json_apps.pop(k)

            # save the json_apps to the collection so that we can use it later
            collection['json_apps']=json.dumps(json_apps)

            #appearances = ({'name':'short_hair'},{'name':'02_ca_limestone'},{'name':'ml_plastic_doll'},{'name':'03_ca_senna'})
            #if appearances defined populate valid mats with the mats for them, otherwise populate with everything used.
            if len(appearances)>0 and 'ALL' not in appearances:
                if 'Default' in appearances:
                    first_key = next(iter(json_apps))
                    for m in json_apps[first_key]:
                        validmats[m] = True
                else:
                    for key in json_apps:
                        if key in appearances:
                            for m in json_apps[key]:
                                validmats[m]=True
            # there isnt always a default, so if none were listed, or ALL was used, or an invalid one add everything.
            if len(validmats)==0:
                for key in json_apps:
                    for m in json_apps[key]:
                        validmats[m]=True

            try:
                import_mats(current_file_base_path, DepotPath, exclude_unused_mats, existingMeshes, gltf_importer, image_format, mats, validmats,multimesh)

            except Exception as e:
                print("Exception when trying to import mats: " + str(e))
                raise e
            
            if generate_overrides:
                try:
                    from ..exporters.mlsetup_export import cp77_mlsetup_generateoverrides
                    cp77_mlsetup_generateoverrides(None, bpy.context)
                except Exception as e:
                    print("Exception when trying to generate multilayer overrides: " + str(e))
                    raise e
    if meshinitiated_cache:
        JSONTool.stop_caching()


    if len(errorMessages) > 0:
        show_message("\n".join(errorMessages))

    if verbose:
        print(f"GLB Import Time: {(time.time() - start_time)} Seconds")
        print('-------------------- Finished importing Cyberpunk 2077 Model --------------------\n')

def reload_mats(self, context):
    active_obj = bpy.context.active_object
    active_material = active_obj.active_material
    if active_material is None:
        self.report({'ERROR'}, "No active material selected")
        return {'CANCELLED'}

    orig_mat_name = active_material.name
    if 'm' in active_material:
        orig_mat_name = str(active_material['m']['Name'])

    BasePath = active_material.get('MeshPath')
    DepotPath = active_material.get('DepotPath')
    ProjPath = active_material.get('ProjPath')

    if BasePath is None:
        for collection in bpy.data.collections:
            if active_obj.name in collection.objects:
                MeshPath = collection.get('mesh')
                if MeshPath and ProjPath:
                    MeshPathNoSuffix = MeshPath[:MeshPath.rfind('.')]
                    BasePath = os.path.join(ProjPath, MeshPathNoSuffix)
                break

    if BasePath is None:
        self.report({'ERROR'}, "Could not resolve material base path")
        return {'CANCELLED'}

    errorMessages = []
    matjsonpath = BasePath + ".Material.json"

    if not os.path.exists(matjsonpath):
        self.report({'ERROR'}, ('Material.json not found: ' + matjsonpath))
        return {'CANCELLED'}

    image_format = 'png'
    initiated_cache = False
    if not JSONTool._use_cache:
        JSONTool.start_caching()
        initiated_cache = True

    try:
        somejunk, otherjunk, mats = JSONTool.jsonload(matjsonpath, errorMessages)
        Builder = MaterialBuilder(mats, DepotPath, str(image_format), BasePath)
    finally:
        if initiated_cache:
            JSONTool.stop_caching()

    if len(errorMessages) > 0:
        show_message("\n".join(errorMessages))

    newmat = None
    old_base_name = orig_mat_name.split('.')[0]
    for index, rawmat in enumerate(mats):
        if rawmat.get("Name") == old_base_name:
            newmat = Builder.create(mats, index)
            break

    if newmat is None:
        self.report({'ERROR'}, "New material not created")
        return {'CANCELLED'}

    for k in active_material.keys():
        if k in ('BaseMaterial', 'DiffuseMap', 'GlobalNormal', 'MultilayerMask'):
            newmat[k] = active_material[k]

    old_material = active_material
    active_obj.material_slots[active_obj.active_material_index].material = newmat
    if old_material.users == 0:
        bpy.data.materials.remove(old_material, do_unlink=True, do_id_user=True, do_ui_user=True)

    return newmat


def import_mats(BasePath, DepotPath, exclude_unused_mats, existingMeshes, gltf_importer, image_format, mats, validmatnames,multimesh=False,generate_overrides=False):
    excluded_objects = exclusion_cache.get_excluded_objects()
    failedon = []
    cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
    verbose = not cp77_addon_prefs.non_verbose
    start_time = time.time()
    validmats = {}
    for m in mats: #obj['Materials']:
        mat = m.get('Name')
        if mat is None:
            continue
        if mat not in validmatnames:
            continue
        if 'BaseMaterial' in m:
            data = m.get('Data', {})
            GlobalNormal = data.get('GlobalNormal', 'None')
            MultilayerMask = data.get('MultilayerMask', 'None')
            DiffuseMap = data.get('DiffuseMap', data.get('BaseColor', data.get('DiffuseTexture', 'None')))

            validmats[mat] = {'Name': mat, 'BaseMaterial': m['BaseMaterial'],
                              'GlobalNormal': GlobalNormal, 'MultilayerMask': MultilayerMask,
                              'DiffuseMap': DiffuseMap}
        else:
            print(m.keys())

    MatImportList = list(validmats)
    mat_index_by_name = {m['Name']: i for i, m in enumerate(mats) if 'Name' in m}
    Builder = MaterialBuilder(mats, DepotPath, str(image_format), BasePath)
    counter = 0
    bpy_mats = bpy.data.materials
    excluded_mesh_names = {
        obj.data.name for obj in excluded_objects
        if getattr(obj, "type", "") == 'MESH' and obj.data
        }
    existing_mesh_names = set(existingMeshes)
    names = [
        mesh.name for mesh in bpy.data.meshes
        if mesh.name not in existing_mesh_names and mesh.name not in excluded_mesh_names
    ]
    if multimesh:
        names = sorted(names, key=lambda x: int(x.split('_', 1)[0]) if x.split('_', 1)[0].isdigit() else 0)

    bpy_meshes = bpy.data.meshes
    for name in names:
        mesh = bpy_meshes.get(name)
        if mesh is None:
            continue

        mesh.materials.clear()
        # we're not getting the materials from the json, but from the glTF importer data
        extras = gltf_importer.data.meshes[counter].extras

        # morphtargets don't have material names. Just use all of them.
        materialNames = None
        if extras is None or ("materialNames" not in extras or extras["materialNames"] is None):
            if BasePath.endswith(".morphtarget"):
                materialNames = validmats.keys()
            else:
                counter = counter + 1
                continue
        else:
            materialNames = extras["materialNames"]

        # remove duplicate material names (why does "extras" end up with 10k "decals" entries when I import the maimai?)
        # Sim - because of a bug in wkit I'd assume mana
        materialNames = list(dict.fromkeys(materialNames))

        # Kwek: I also found that other material hiccups will cause the Collection to fail
        for matname in materialNames:

            if matname not in validmats:
                continue

            # print('matname: ',matname, validmats[matname])
            m = validmats[matname]
            if matname == 'decal_diffuse1':
                print('debug')
            # Should create a list of mis that dont play nice with this and just check if the mat is using one.
            cached = bpy_mats.get(matname)
            if cached is not None and 'm' in cached and dict(cached['m']) == m:
                mesh.materials.append(cached)
                continue

            index = mat_index_by_name.get(matname)
            if index is None:
                continue
            try:
                bpymat = Builder.create(mats, index)
                if bpymat:
                    bpymat['m'] = m
                    bpymat['BaseMaterial'] = m['BaseMaterial']
                    bpymat['GlobalNormal'] = m['GlobalNormal']
                    bpymat['MultilayerMask'] = m['MultilayerMask']
                    if 'DiffuseMap' in m:
                        bpymat['DiffuseMap'] = m['DiffuseMap']
                    if 'DiffuseTexture' in m:
                        bpymat['DiffuseTexture'] = m['DiffuseTexture']
                    mesh.materials.append(bpymat)
                    if bpymat.get('no_shadows'):
                        shadow_obj = bpy.data.objects.get(name)
                        if shadow_obj is not None:
                            shadow_obj.visible_shadow = False
            except:
                # Kwek -- finally, even if the Builder couldn't find the materials, keep calm and carry on
                print(traceback.format_exc())
                failedon.append(matname)

        counter = counter + 1
    if verbose:
        if len(failedon) == 0:
            print(f'Shader Setup Completed Succesfully in {(time.time() - start_time)} Seconds')
        else:
            line_separator = '\n    '
            print(f'Material Setup Failed on: {line_separator}{line_separator.join(failedon)}')
            print(f'Attempted Setup for {(time.time() - start_time)} seconds')

    if exclude_unused_mats:
        return

    for name, index in mat_index_by_name.items():
        if name in bpy.data.materials:
            continue
        if MatImportList and name not in MatImportList:
            continue
        Builder.create(mats, index)


def blender_4_scale_armature_bones(imported_objects):
    vers = bpy.app.version
    if vers[0] >= 4:
        for arm in (obj for obj in imported_objects if obj.type == 'ARMATURE'):
            for pb in arm.pose.bones:
                pb.custom_shape_scale_xyz = (.0175, .0175, .0175)
                pb.use_custom_shape_bone_size = True


def import_meshes_and_anims(collection, gltf_importer, hide_armatures, o, filename, oldanims, import_tracks):
    # TODO: check if this is a Cyberpunk import or something else entirely
    cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
    verbose = not cp77_addon_prefs.non_verbose

    for parent in o.users_collection:
        parent.objects.unlink(o)
    collection.objects.link(o)

    # We should probably break the base import out into a separate function, have it check the gltf file and then send the info either to anim import or import with materials, but this works too
    animations = gltf_importer.data.animations
    meshes = gltf_importer.data.meshes

    if o.type == 'ARMATURE' and hasattr(gltf_importer.data, 'skins') and gltf_importer.data.skins:
        for skin in gltf_importer.data.skins:
            try:
                add_skin_props(skin, o)
                if verbose:
                    print(f"Skin properties added to armature: {o.name}")
                break  # typically one skin per armature
            except Exception as e:
                if verbose:
                    print(f"could not add skin properties to '{o.name}': {e}")

    # if animations exist, don't hide the armature and get the extras properties
    if animations:
        get_anim_info(animations, oldanims, import_tracks)

    # if no meshes exist, don't hide the armature
    elif meshes and o.type == 'ARMATURE':
        o.hide_set(hide_armatures)
        o.name = "Armature__" + filename