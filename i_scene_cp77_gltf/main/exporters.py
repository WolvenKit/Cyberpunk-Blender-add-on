import json
import os
import mathutils
import bpy

#setup the default options to be applied to all export types
def default_cp77_options():
    options = {
        'export_format': 'GLB',
        'check_existing': True,
        'export_skins': True,
        'export_yup': True,
        'export_cameras': False,
        'export_materials': 'NONE',
        'export_all_influences': True,
        'export_lights': False,
        'export_apply': False
    }
    return options
#make sure meshes are exported with tangents, morphs and vertex colors
def cp77_mesh_options():
    options = {
        'export_animations': False,
        'export_tangents': True,
        'export_normals': True,
        'export_morph_tangent': True,
        'export_morph_normal': True,
        'export_morph': True,
        'export_colors': True
    }
    return options
#the options for anims
def pose_export_options():
    options = {
        'export_animations': True,
        'export_frame_range': False,
        'export_anim_single_armature': True       
    }
    return options
#setup the actual exporter - rewrote almost all of this, much quicker now
def export_cyberpunk_glb(context, filepath, export_poses):
    # Retrieve the selected objects
    objects = context.selected_objects
    # apply transforms
    for obj in objects:
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    #if for photomode, make sure there's an armature selected, if not use the message box to show an error
    if export_poses:
        armatures = [obj for obj in objects if obj.type == 'ARMATURE']
        if not armatures:
            bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="No armature selected, please select an armature")
            return {'CANCELLED'}
        #if the export poses value is True, set the export options to ensure the armature is exported properly with the animations
        options = default_cp77_options()
        options.update(pose_export_options())
    else:
        #if export_poses option isn't used, check to make sure there are meshes selected and throw an error if not
        meshes = [obj for obj in objects if obj.type == 'MESH']
        if not meshes:
            #throw an error in the message box if you haven't selected a mesh to export
            bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="No meshes selected, please select at least one mesh")
            return {'CANCELLED'}
        #check that meshes include UVs and have less than 65000 verts, throw an error if not
        for mesh in meshes:
            if not mesh.data.uv_layers:
                bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="Meshes must have UV layers in order to import in Wolvenkit")
                return {'CANCELLED'}
            for submesh in mesh.data.polygons:
                if len(submesh.vertices) > 65000:
                    bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="Each submesh must have less than 65,000 vertices")
                    return {'CANCELLED'}
            #check that faces are triangulated, if not cancel and throw an error
            for face in mesh.data.polygons:
                if len(face.vertices) != 3:
                    bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="All faces must be triangulated before exporting to glb")
                    return {'CANCELLED'}
        options = default_cp77_options()
        options.update(cp77_mesh_options())

    print(options)  
    # if exporting meshes, iterate through any connected armatures, store their currebt state. if hidden, unhide them and select them for export
    armature_states = {}

    for obj in objects: 
        if obj.type == 'MESH' and obj.select_get():
            armature_modifier = None
            for modifier in obj.modifiers:
                if modifier.type == 'ARMATURE' and modifier.object:
                    armature_modifier = modifier
                    break

            if armature_modifier:
                # Store original visibility and selection state
                armature = armature_modifier.object
                armature_states[armature] = {"hide": armature.hide_get(),
                                            "select": armature.select_get()}

                # Make necessary to armature visibility and selection state for export
                armature.hide_set(False)
                armature.select_set(True)

                # Check for ungrouped vertices, throw an error if any are found
                ungrouped_vertices = [v for v in obj.data.vertices if not v.groups]
                if ungrouped_vertices:
                    bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="Export Cancelled: Ungrouped vertices found in mesh, please add these vertices to a group or delete them before exporting.")
                    return {'CANCELLED'}

    # Export the selected meshes to glb
    bpy.ops.export_scene.gltf(filepath=filepath, use_selection=True, **options)

    # Restore original armature visibility and selection states
    for armature, state in armature_states.items():
        armature.select_set(state["select"])
        armature.hide_set(state["hide"])


def cp77_collision_export(filepath):
    with open(filepath, 'r') as phys:
        data = json.load(phys)
        physJsonPath = filepath

        dir_name, file_name = os.path.split(filepath)
        new_file_name = 'new_' + file_name
        output = os.path.join(dir_name, new_file_name)

        collection_name = os.path.splitext(os.path.basename(physJsonPath))[0]
        collection = bpy.data.collections.get(collection_name)

        if collection is not None:
            for index, obj in enumerate(collection.objects):
                colliderType = obj.name.split('_')[1]
                i = data['Data']['RootChunk']['bodies'][0]['Data']['collisionShapes'][index]

                i['Data']['localToBody']['position']['X'] = obj.location.x
                i['Data']['localToBody']['position']['Y'] = obj.location.y
                i['Data']['localToBody']['position']['Z'] = obj.location.z
                i['Data']['localToBody']['orientation']['i'] = obj.rotation_quaternion.z
                i['Data']['localToBody']['orientation']['j'] = obj.rotation_quaternion.x
                i['Data']['localToBody']['orientation']['k'] = obj.rotation_quaternion.y
                i['Data']['localToBody']['orientation']['r'] = obj.rotation_quaternion.w

                if colliderType == "physicsColliderConvex" or colliderType == "physicsColliderConcave":
                    mesh = obj.data
                    if 'vertices' in i['Data']:
                        for j, vert in enumerate(mesh.vertices):
                            i['Data']['vertices'][j]['X'] = vert.co.x
                            i['Data']['vertices'][j]['Y'] = vert.co.y
                            i['Data']['vertices'][j]['Z'] = vert.co.z

                elif colliderType == "physicsColliderBox":
                    # Calculate world-space bounding box vertices
                    world_bounds = [obj.matrix_world @ mathutils.Vector(coord) for coord in obj.bound_box]

                    # Get center of the box in world space
                    center = sum(world_bounds, mathutils.Vector()) / 8

                    # Update position in the json based on the center of the cube in world space
                    i['Data']['localToBody']['position']['X'] = center.x
                    i['Data']['localToBody']['position']['Y'] = center.y
                    i['Data']['localToBody']['position']['Z'] = center.z
                    # Update halfExtents
                    i['Data']['halfExtents']['X'] = obj.dimensions.x / 2
                    i['Data']['halfExtents']['Y'] = obj.dimensions.y / 2
                    i['Data']['halfExtents']['Z'] = obj.dimensions.z / 2

                elif colliderType == "physicsColliderCapsule":
                    i['Data']['radius'] = obj.dimensions.x / 2  # Divided by 2 because blender dimensions are diameter
                    i['Data']['height'] = obj.dimensions.z 
                
            bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="Succesfully Exported Collisions")
        with open(output, 'w') as f:
            json.dump(data, f, indent=2)

    print(f'Finished exporting {new_file_name}')
