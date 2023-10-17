import zipfile
import bpy
import math
import json
import os


plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
resources_dir = os.path.join(plugin_dir, "resources")
refit_dir = os.path.join(resources_dir, "refitters")

def CP77MeshList(self, context):
    items = []
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            items.append((obj.name, obj.name, ""))
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
    """Main function to assign unassigned vertices to nearest vertex group."""
    obj = bpy.context.object
    if obj.type != 'MESH':
        bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="The active object is not a mesh.")
        return {'CANCELLED'}
    
    ungrouped_vertices = [v for v in obj.data.vertices if not v.groups]  
    for v in ungrouped_vertices:
        nearest_vertex = find_nearest_vertex_group(obj, v)
        if nearest_vertex:
            for g in nearest_vertex.groups:
                group_name = obj.vertex_groups[g.group].name
                obj.vertex_groups[group_name].add([v.index], 1.0, 'ADD')

def CP77ArmatureSet(self, context):
    selected_meshes = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    props = context.scene.cp77_panel_props
    target_armature_name = props.selected_armature
    target_armature = bpy.data.objects.get(target_armature_name)
    if target_armature and target_armature.type == 'ARMATURE':
        for mesh in selected_meshes:
            for modifier in mesh.modifiers:
                if modifier.type == 'ARMATURE' and modifier.object is not target_armature:
                        modifier.object = target_armature
                else:
                    if modifier.type == 'ARMATURE' and modifier.object is target_armature:
                        continue
            armature = mesh.modifiers.new('Armature', 'ARMATURE')
            armature.object = target_armature


def trans_weights(self, context):
    props = context.scene.cp77_panel_props
    source_mesh_name = props.mesh_source
    target_mesh_name = props.mesh_target
    source_obj = bpy.data.objects.get(source_mesh_name)
    target_obj = bpy.data.objects.get(target_mesh_name)

    if source_obj and target_obj:
        bpy.context.view_layer.objects.active = target_obj
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        target_obj.select_set(True)
        bpy.context.view_layer.objects.active = source_obj
        source_obj.select_set(True)

        bpy.ops.object.data_transfer(
            use_reverse_transfer=False,
            vert_mapping='POLYINTERP_NEAREST',
            data_type='VGROUP_WEIGHTS',
            layers_select_dst='NAME',
            layers_select_src='ALL'
        )

        source_obj.select_set(False)
        target_obj.select_set(False)


def CP77UvChecker(self, context):
    selected_meshes = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    bpy_mats=bpy.data.materials
    existing_materials = bpy_mats.keys()
    current_mode = context.mode
    if 'UV_Checker' not in existing_materials:
        image_path = os.path.join(resources_dir, "uvchecker.png")
        # Load the image texture
        image = bpy.data.images.load(image_path)
        # Create a new material if it doesn't exist
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
        for mat in context.object.material_slots:
            if mat.name == 'UV_Checker':
                uvchecker = mat
        if 'UV_Checker' not in context.object.material_slots.keys():
            bpy.data.meshes[mesh.name].materials.append(bpy_mats['UV_Checker'])
            i = context.object.active_material_index + 1
            bpy.context.object.active_material_index = i
        else:
            uvchecker = mat in context.object.material_slots if mat.name == 'UV_Checker' else None
            if current_mode is not 'EDIT':
                print(current_mode)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.object.material_slot_assign()
        print(current_mode)
    bpy.ops.object.mode_set(mode=current_mode)

    return {'FINISHED'}


def cp77riglist(context):
    cp77rigs = []
    man_base = os.path.join(resources_dir, "man_base_full.glb")
    woman_base = os.path.join(resources_dir, "woman_base_full.glb")
    man_big = os.path.join(resources_dir, "man_big_full.glb")
    man_fat = os.path.join(resources_dir, "man_fat_full.glb")
    Rhino = os.path.join(resources_dir, "rhino_full.glb")
    Judy = os.path.join(resources_dir, "Judy_full.glb")
    Panam = os.path.join(resources_dir, "Panam_full.glb")
    
    # Store the variable names in a list
    cp77rigs = [man_base, woman_base, man_big, man_fat, Rhino, Judy, Panam]
    cp77rig_names = ['man_base', 'woman_base', 'man_big', 'man_fat', 'Rhino', 'Judy', 'Panam']
    
    # Return the list of variable names
    return cp77rigs, cp77rig_names


def CP77RefitList(context):
    target_body_paths = []
    SoloArmsAddon = os.path.join(refit_dir, "SoloArmsAddon.zip")
    Adonis = os.path.join(refit_dir, "Adonis.zip")
    VanillaFemToMasc = os.path.join(refit_dir, "f2m.zip")
    VanillaMascToFem = os.path.join(refit_dir, "m2f.zip")
    Lush = os.path.join(refit_dir, "lush.zip")
    Hyst_RB = os.path.join(refit_dir, "hyst_rb.zip")
    Hyst_EBB = os.path.join(refit_dir, "hyst_ebb.zip")
    Hyst_EBB_RB = os.path.join(refit_dir, "hyst_ebb_rb.zip")
    Flat_Chest = os.path.join(refit_dir, "flat_chest.zip")
    Solo_Ultimate = os.path.join(refit_dir, "solo_ultimate.zip")
    
    # Convert the dictionary to a list of tuples
    target_body_paths = [SoloArmsAddon, Solo_Ultimate, Adonis, Flat_Chest, Hyst_EBB_RB, Hyst_EBB, Hyst_RB, Lush, VanillaFemToMasc, VanillaMascToFem ]
    target_body_names = ['SoloArmsAddon', 'Solo_Ultimate', 'Adonis', 'Flat_Chest', 'Hyst_EBB_RB', 'Hyst_EBB', 'Hyst_RB', 'Lush', 'VanillaFemToMasc', 'VanillaMascToFem' ]

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
    selected_meshes = []
    scene = context.scene
    r_c = None
    refitter_obj = None
    print(fbx_rot)

    if len(refitter) != 0:
        for obj in refitter:
            if obj['refitter_type'] == target_body_name:
                refitter_obj = obj 
                if refitter_obj is not None:
                    print('theres a refitter')
                    for mesh in selected_meshes:
                        if refitter_obj.name in mesh.modifiers:
                            print(mesh.name, 'already fitted to:', refitter_obj["refitter_type"])
                            continue 
                        else:            
                            print('refitting:', mesh.name, 'to:', refitter_obj["refitter_type"])
                            lattice_modifier = mesh.modifiers.new(refitter_obj.name, 'LATTICE')
                            lattice_modifier.object = refitter_obj

                    print('all done')
                    return{'FINISHED'}
            else:
                print('lets generate something ')
                continue

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
            selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
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
    
            for obj in selected_meshes:
                lattice_modifier = obj.modifiers.new(new_lattice.name,'LATTICE')
                for obj in selected_meshes:
                    print('refitting:', obj.name, 'to:', new_lattice["refitter_type"])
                    lattice_modifier.object = new_lattice
