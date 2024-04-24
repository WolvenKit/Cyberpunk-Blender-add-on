import zipfile
import bpy
import math
import json
import os
from .common import get_plugin_dir, get_resources_dir, get_refit_dir, get_rig_dir

plugin_dir = get_plugin_dir()
resources_dir = get_resources_dir()
refit_dir = get_refit_dir()
rig_dir = get_rig_dir()

def CP77CollectionList(self, context):
    items = []
    ## don't include these as their not useful
    excluded_names = ["Collection", "Scene Collection", "glTF_not_exported"]

    for collection in bpy.data.collections:
        if collection.name not in excluded_names:
            items.append((collection.name, collection.name, ""))
    return items


def CP77ArmatureList(self, context):
    items = []
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            items.append((obj.name, obj.name, ""))
    return items


def find_nearest_vertex_group(obj, vertex):
    min_distance = math.inf
    nearest_vertex = None
    for v in obj.data.vertices:
        if v.groups:
            distance = (v.co - vertex.co).length
            if distance < min_distance:
                min_distance = distance
                nearest_vertex = v
    return nearest_vertex


def CP77GroupUngroupedVerts(self, context):
    C = bpy.context
    obj = C.object
    current_mode = C.mode

    if obj.type != 'MESH':
        bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="The active object is not a mesh.")
        return {'CANCELLED'}
    else:
        if current_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        ungrouped_vertices = [v for v in obj.data.vertices if not v.groups]

        if ungrouped_vertices:
            try:
                for v in ungrouped_vertices:
                    nearest_vertex = find_nearest_vertex_group(obj, v)
                    if nearest_vertex:
                        for g in nearest_vertex.groups:
                            group_name = obj.vertex_groups[g.group].name
                            obj.vertex_groups[group_name].add([v.index], 1.0, 'ADD')
            except Exception as e:
                print(e)

        # Return to the mode the user was in edit_mesh was giving me a lot of trouble and is probably 
        # the most common it will be here so special handling for it
        if C.mode != current_mode:
            try:
                if current_mode == 'EDIT_MESH':
                    bpy.ops.object.mode_set(mode='EDIT')
                else:
                    bpy.ops.object.mode_set(mode=current_mode)
            except Exception as e:
                print(e)
    return {'FINISHED'}
    
def CP77SubPrep(self, context, smooth_factor, merge_distance):
    scn = context.scene
    obj = context.object
    current_mode = context.mode
    if obj.type != 'MESH':
        bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="The active object is not a mesh.")
        return {'CANCELLED'}  
    
    if current_mode != 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type="EDGE")
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_non_manifold(extend=False, use_wire=True, use_boundary=True, use_multi_face=False, use_non_contiguous=False, use_verts=False)
    bpy.ops.mesh.mark_seam(clear=False)
    bpy.ops.mesh.select_mode(type="VERT")
    bpy.ops.mesh.select_all(action='SELECT')
    
    # Store the number of vertices before merging
    bpy.ops.object.mode_set(mode='OBJECT')
    before_merge_count = len(obj.data.vertices)
    bpy.ops.object.mode_set(mode='EDIT')

    bpy.ops.mesh.remove_doubles(threshold=merge_distance)

    # Update the mesh and calculate the number of merged vertices
    bpy.ops.object.mode_set(mode='OBJECT')
    after_merge_count = len(obj.data.vertices)
    merged_vertices = before_merge_count - after_merge_count

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.faces_select_linked_flat()
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.smooth_normals()
    bpy.ops.cp77.message_box('INVOKE_DEFAULT', message=f"Submesh preparation complete. {merged_vertices} verts merged")
    if context.mode != current_mode:
        bpy.ops.object.mode_set(mode=current_mode)
        

def CP77ArmatureSet(self, context):
    selected_meshes = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    props = context.scene.cp77_panel_props
    target_armature_name = props.selected_armature
    target_armature = bpy.data.objects.get(target_armature_name)
    if target_armature and target_armature.type == 'ARMATURE':
        for mesh in selected_meshes:
            retargeted=False
            for modifier in mesh.modifiers:
                if modifier.type == 'ARMATURE' and modifier.object is not target_armature:
                    modifier.object = target_armature
                    retargeted=True
                else:
                    if modifier.type == 'ARMATURE' and modifier.object is target_armature:
                        retargeted=True
                        continue
            if not retargeted:
                armature = mesh.modifiers.new('Armature', 'ARMATURE')
                armature.object = target_armature


def trans_weights(self, context):
    current_mode = context.mode
    props = context.scene.cp77_panel_props
    source_mesh_name = props.mesh_source
    target_mesh_name = props.mesh_target
    active_objs = context.selected_objects
    # Get the source collection
    source_mesh = bpy.data.collections.get(source_mesh_name)
    
    # Get the target collection
    target_mesh = bpy.data.collections.get(target_mesh_name)
    
    

    if source_mesh and target_mesh:
        if current_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        # Deselect all objects in the scene
        bpy.ops.object.select_all(action='DESELECT')
        
        # Select the objects in the source collection
        for source_obj in source_mesh.objects:
            source_obj.select_set(True)
            
        # Set the active object to the last selected source object
        bpy.context.view_layer.objects.active = source_obj
        
        # Iterate through objects in the target collection
        for target_obj in target_mesh.objects:
            target_obj.select_set(True)
        
        # Perform the data transfer
        bpy.ops.object.data_transfer(
            use_reverse_transfer=False,
            vert_mapping='POLYINTERP_NEAREST',
            data_type='VGROUP_WEIGHTS',
            layers_select_dst='NAME',
            layers_select_src='ALL'
        )
        bpy.ops.object.select_all(action='DESELECT')
        context.view_layer.objects.active = None
        
    for obj in active_objs:
        obj.select_set(True)
        context.view_layer.objects.active = obj
   
        
    if context.mode != current_mode:
        try:
            bpy.ops.object.mode_set(mode=current_mode)
            
        except TypeError:
      
            if current_mode == 'PAINT_WEIGHT':
                bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
            elif current_mode == 'EDIT_MESH':
                bpy.ops.object.mode_set(mode='EDIT')
            elif current_mode == 'PAINT_VERTEX':
                bpy.ops.object.mode_set(mode='VERTEX_PAINT')
    
        

def CP77UvChecker(self, context):
    selected_meshes = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    bpy_mats=bpy.data.materials
    current_mode = context.mode
    current_mat = None
    uv_checker = None
    for mat in bpy_mats:
        if mat.name == 'UV_Checker':
            uvchecker = mat
            uv_checker = True
    if uv_checker == None:
        image_path = os.path.join(resources_dir, "uvchecker.png")
        # Load the image texture
        image = bpy.data.images.load(image_path)
        # Create a new material
        uvchecker = bpy_mats.new(name="UV_Checker")
        uvchecker.use_nodes = True
        # Create a new texture node
        texture_node = uvchecker.node_tree.nodes.new(type='ShaderNodeTexImage')
        texture_node.location = (-200, 0)
        texture_node.image = image
        # Connect the texture node to the shader node
        shader_node = uvchecker.node_tree.nodes["Principled BSDF"]
        uvchecker.node_tree.links.new(texture_node.outputs['Color'], shader_node.inputs['Base Color'])
    for mesh in selected_meshes:
        mat_assigned = False
        for mat in context.object.material_slots:
            if mat.name == 'UV_Checker':
                uvchecker = mat
                mat_assigned = True
        if not mat_assigned:
            try:
                current_mat = context.object.active_material.name
                mesh['uvCheckedMat'] = current_mat
                bpy.data.meshes[mesh.name].materials.append(bpy_mats['UV_Checker'])
                i = mesh.data.materials.find('UV_Checker')
            except AttributeError:
                bpy.data.meshes[mesh.name].materials.append(bpy_mats['UV_Checker'])
                i = mesh.data.materials.find('UV_Checker')
           
            if i >= 0:
                mesh.active_material_index = i
            if current_mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.object.material_slot_assign()
                
                #print(current_mode)
        
        if context.mode != current_mode:
            bpy.ops.object.mode_set(mode=current_mode)

    return {'FINISHED'}


def CP77UvUnChecker(self, context):
    selected_meshes = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    current_mode = context.mode
    uvchecker = 'UV_Checker'
    original_mat_name = None
    for mesh in selected_meshes:
        if 'uvCheckedMat' in mesh.keys() and 'uvCheckedMat' is not None:
            original_mat_name = mesh['uvCheckedMat']
        if uvchecker in mesh.data.materials:
            # Find the index of the material slot with the specified name
            material_index = mesh.data.materials.find(uvchecker)
            mesh.data.materials.pop(index=material_index)
            if original_mat_name is not None:
                i = mesh.data.materials.find(original_mat_name)
                bpy.ops.wm.properties_remove(data_path="object", property_name="uvCheckedMat")
                if i >= 0:
                    mesh.active_material_index = i
                if current_mode != 'EDIT':
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.object.material_slot_assign()
        if context.mode != current_mode:
            bpy.ops.object.mode_set(mode=current_mode)
                

def cp77riglist(context):
    cp77rigs = []
    man_base = os.path.join(rig_dir, "man_base_full.glb")
    woman_base = os.path.join(rig_dir, "woman_base_full.glb")
    Jackie = os.path.join(rig_dir, "jackie_full.glb")
    man_big = os.path.join(rig_dir, "man_big_full.glb")
    man_fat = os.path.join(rig_dir, "man_fat_full.glb")
    Rhino = os.path.join(rig_dir, "rhino_full.glb")
    Judy = os.path.join(rig_dir, "Judy_full.glb")
    Panam = os.path.join(rig_dir, "Panam_full.glb")
    
    # Store the variable names in a list
    cp77rigs = [man_base, woman_base, Jackie, man_big, man_fat, Rhino, Judy, Panam]
    cp77rig_names = ['man_base', 'woman_base', 'Jackie', 'man_big', 'man_fat', 'Rhino', 'Judy', 'Panam']

    # Return the list of variable names
    return cp77rigs, cp77rig_names


def CP77RefitList(context):
    target_addon_paths = [None]
    target_addon_names = ['None']
    
    SoloArmsAddon = os.path.join(refit_dir, "SoloArmsAddon.zip")
    Adonis = os.path.join(refit_dir, "Adonis.zip")
    VanillaFemToMasc = os.path.join(refit_dir, "f2m.zip")
    VanillaFem_BigBoobs = os.path.join(refit_dir, "f_normal_to_big_boobs.zip")
    VanillaFem_SmallBoobs = os.path.join(refit_dir, "f_normal_to_small_boobs.zip")
    VanillaMascToFem = os.path.join(refit_dir, "m2f.zip")
    Lush = os.path.join(refit_dir, "lush.zip")
    Hyst_RB = os.path.join(refit_dir, "hyst_rb.zip")
    Hyst_EBB = os.path.join(refit_dir, "hyst_ebb.zip")
    Hyst_EBB_RB = os.path.join(refit_dir, "hyst_ebb_rb.zip")
    Flat_Chest = os.path.join(refit_dir, "flat_chest.zip")
    Solo_Ultimate = os.path.join(refit_dir, "solo_ultimate.zip")
    Gymfiend = os.path.join(refit_dir, "gymfiend.zip")
    Freyja = os.path.join(refit_dir, "freyja.zip")
    # Hyst_EBBP_Addon = os.path.join(refit_dir, "hyst_ebbp_addon.zip")
    
    # Return the list of variable names
    target_body_paths = [ Gymfiend, Freyja, SoloArmsAddon, Solo_Ultimate, Adonis, Flat_Chest, Hyst_EBB_RB, Hyst_EBB, Hyst_RB, Lush, VanillaFemToMasc, VanillaMascToFem, VanillaFem_BigBoobs, VanillaFem_SmallBoobs ]
    target_body_names = [ 'Gymfiend', 'Freyja', 'SoloArmsAddon', 'Solo_Ultimate', 'Adonis', 'Flat_Chest', 'Hyst_EBB_RB', 'Hyst_EBB', 'Hyst_RB', 'Lush', 'VanillaFemToMasc', 'VanillaMascToFem', 'VanillaFem_BigBoobs', 'VanillaFem_SmallBoobs' ]

    # Return the list of tuples
    return target_body_paths, target_body_names


def CP77RefitChecker(self, context):
    scene = context.scene
    objects = scene.objects
    refitter = []

    for obj in objects:
        if obj.type =='LATTICE':
            if "refitter_type" in obj:
                refitter.append(obj)
                print('refitters found in scene:', refitter)

    print('refitter result:', refitter)
    return refitter


def CP77Refit(context, refitter, target_body_path, target_body_name, fbx_rot):
    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
    scene = context.scene
    refitter_obj = None
    r_c = None
    print(fbx_rot)
    print(refitter)

    if len(refitter) != 0:
        for obj in refitter:
            print('refitter object:', obj.name)
            if obj['refitter_type'] == target_body_name:
                print(obj['refitter_type'], 'refitter found')
                refitter_obj = obj
            
        if refitter_obj:
            print('theres a refitter:', refitter_obj.name, 'type:', refitter_obj['refitter_type'])
            for mesh in selected_meshes:
                print('checking for refits:', mesh.name)
                refit = False
                for modifier in mesh.modifiers:
                    if modifier.type == 'LATTICE' and modifier.object == refitter_obj:
                        refit = True
                        print(mesh.name, 'is already refit for', target_body_name)

                if not refit:
                    print('refitting:', mesh.name, 'to:', target_body_name)
                    lattice_modifier = mesh.modifiers.new(refitter_obj.name, 'LATTICE')
                    lattice_modifier.object = refitter_obj
            return{'FINISHED'}    
        

    for collection in scene.collection.children:
        if collection.name == 'Refitters':
            r_c = collection
            break
    if r_c is None:
        r_c = bpy.data.collections.new('Refitters')
        scene.collection.children.link(r_c)

    # Get the JSON file path for the selected target_body
    with zipfile.ZipFile(target_body_path, "r") as z:
        filename=z.namelist()[0]
        print(filename)
        with z.open(filename) as f:
            data = f.read()
            data = json.loads(data)

        if data:
            control_points = data.get("deformed_control_points", [])

            # Create a new lattice object
            bpy.ops.object.add(type='LATTICE', enter_editmode=False, location=(0, 0, 0))
            new_lattice = bpy.context.object
            new_lattice.name = data.get("lattice_object_name", "NewLattice")
            new_lattice["refitter_type"] = target_body_name
            lattice = new_lattice.data
            r_c.objects.link(new_lattice)
            bpy.context.collection.objects.unlink(new_lattice)
                  
            # Set the dimensions of the lattice
            lattice.points_u = data["lattice_points"][0]
            lattice.points_v = data["lattice_points"][1]
            lattice.points_w = data["lattice_points"][2]
            new_lattice.location[0] = data["lattice_object_location"][0]
            new_lattice.location[1] = data["lattice_object_location"][1]
            new_lattice.location[2] = data["lattice_object_location"][2]
            if fbx_rot:
            # Rotate the Z-axis by 180 degrees (pi radians)
                new_lattice.rotation_euler = (data["lattice_object_rotation"][0], data["lattice_object_rotation"][1], data["lattice_object_rotation"][2] + 3.14159)
            else:
                new_lattice.rotation_euler = (data["lattice_object_rotation"][0], data["lattice_object_rotation"][1], data["lattice_object_rotation"][2])
            new_lattice.scale[0] = data["lattice_object_scale"][0]
            new_lattice.scale[1] = data["lattice_object_scale"][1]
            new_lattice.scale[2] = data["lattice_object_scale"][2]
            
            # Set interpolation types
            lattice.interpolation_type_u = data.get("lattice_interpolation_u", 'KEY_BSPLINE')
            lattice.interpolation_type_v = data.get("lattice_interpolation_v", 'KEY_BSPLINE')
            lattice.interpolation_type_w = data.get("lattice_interpolation_w", 'KEY_BSPLINE')
                
            # Create a flat list of lattice points
            lattice_points = lattice.points
            flat_lattice_points = [lattice_points[w + v * lattice.points_u + u * lattice.points_u * lattice.points_v] for u in range(lattice.points_u) for v in range(lattice.points_v) for w in range(lattice.points_w)]
        
            for control_point, lattice_point in zip(control_points, flat_lattice_points):
                lattice_point.co_deform = control_point
                
            if new_lattice:
                bpy.context.object.hide_viewport = True
    
            for mesh in selected_meshes:
                lattice_modifier = mesh.modifiers.new(new_lattice.name,'LATTICE')
                for mesh in selected_meshes:
                    print('refitting:', mesh.name, 'to:', new_lattice["refitter_type"])
                    lattice_modifier.object = new_lattice
