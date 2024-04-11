import bpy
from ..main.animtools import reset_armature

#setup the default options to be applied to all export types
def default_cp77_options():
    vers=bpy.app.version
    options = {
        'export_format': 'GLB',
        'check_existing': True,
        'export_skins': True,
        'export_yup': True,
        'export_cameras': False,
        'export_materials': 'NONE',
        'export_all_influences': True,
        'export_lights': False,
        'export_apply': False,
        'export_extras': True,
    }
    if vers[0] >= 4:
        options.update({
            'export_image_format': 'NONE', 
            'export_try_sparse_sk': False,
        })
        
    if vers[0] >= 4.1:
        options.update({
            "export_shared_accessors": True,
            "export_try_omit_sparse_sk": False,
        })
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
        'export_colors': True,
        'export_attributes': True,
    }
    return options

#the options for anims
def pose_export_options():
    options = {
        'export_animations': True,
        'export_frame_range': True,
        'export_animation_mode': 'ACTIONS',
        'export_anim_single_armature': True,  
        "export_bake_animation": True
    }
    return options

#setup the actual exporter - rewrote almost all of this, much quicker now
def export_cyberpunk_glb(context, filepath, export_poses, export_visible, limit_selected, static_prop):
    groupless_bones = set()
    bone_names = []
    
    #check if the scene is in object mode, if it's not, switch to object mode
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    objects = context.selected_objects
    armatures = [obj for obj in objects if obj.type == 'ARMATURE']

    #if for photomode, make sure there's an armature selected, if not use the message box to show an error
    if export_poses:
        if not armatures:
            bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="No armature objects are selected, please select an armature")
            return {'CANCELLED'}
        for action in bpy.data.actions:
            if "schema" not in action:
                action["schema"] ={"type": "wkit.cp2077.gltf.anims","version": 3}
            if "animationType" not in action:
                action["animationType"] = 'Normal'
            if "frameClamping" not in action:	
                action["frameClamping"] = True
            if "frameClampingStartFrame" not in action:
                action["frameClampingStartFrame"] = -1
            if "frameClampingEndFrame" not in action:
                action["frameClampingEndFrame"] = -1
            if "numExtraJoints" not in action:
                action["numExtraJoints"] = 0
            if "numeExtraTracks" not in action:
                action["numeExtraTracks"] = 0
            if "constTrackKeys" not in action:
                action["constTrackKeys"] = []
            if "trackKeys" not in action:
                action["trackKeys"] = []
            if "fallbackFrameIndices" not in action:
                action["fallbackFrameIndices"] = []
            if "optimizationHints" not in action:
                action["optimizationHints"] = { "preferSIMD": False, "maxRotationCompression": 1}
        
        #if the export poses value is True, set the export options to ensure the armature is exported properly with the animations
        options = default_cp77_options()
        options.update(pose_export_options())
        for armature in armatures:
            reset_armature(armature, context)
            print(options)
            bpy.ops.export_scene.gltf(filepath=filepath, use_selection=True, **options)
            return{'FINISHED'}
    else:
        if not limit_selected:
            for obj in bpy.data.objects:
                if obj.type == 'MESH':
                    obj.select_set(True) 
        #if export_poses option isn't used, check to make sure there are meshes selected and throw an error if not
        meshes = [obj for obj in objects if obj.type == 'MESH']

        #throw an error in the message box if you haven't selected a mesh to export
        if not export_poses:
            if not meshes:
                bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="No meshes selected, please select at least one mesh")
                return {'CANCELLED'}
        
        #check that meshes include UVs and have less than 65000 verts, throw an error if not
        for mesh in meshes:

            # apply transforms
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            if not mesh.data.uv_layers:
                bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="Meshes must have UV layers in order to import in Wolvenkit")
                return {'CANCELLED'}
            
            #check submesh vertex count to ensure it's less than the maximum for import
            for submesh in mesh.data.polygons:
                if len(submesh.vertices) > 65535:
                    bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="Each submesh must have less than 65,535 vertices")
                    return {'CANCELLED'}
                
            #check that faces are triangulated, cancel export, switch to edit mode with the untriangulated faces selected and throw an error
            for face in mesh.data.polygons:
                if len(face.vertices) != 3:
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_face_by_sides(number=3, type='NOTEQUAL', extend=False)
                    bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="All faces must be triangulated before exporting. Untriangulated faces have been selected for you")
                    return {'CANCELLED'}
                
        # set the export options for meshes
        options = default_cp77_options()
        options.update(cp77_mesh_options())

        #print the options to the console
        print(options)

    # if exporting meshes, iterate through any connected armatures, store their current state. if hidden, unhide them and select them for export
        armature_states = {}

        if not static_prop:
            for obj in objects:
                if obj.type == 'MESH' and obj.select_get():
                    armature_modifier = None
                    for modifier in obj.modifiers:
                        if modifier.type == 'ARMATURE' and modifier.object:
                            armature_modifier = modifier
                            break

                    if not armature_modifier:
                        bpy.ops.cp77.message_box('INVOKE_DEFAULT', message=(f"Armature missing from: (obj.name) armatures are required for movement. If this is intentional, try 'export as static prop'"))
                        return {'CANCELLED'}
                    # Store original visibility and selection state
                    armature = armature_modifier.object
                    armature_states[armature] = {"hide": armature.hide_get(),
                                                "select": armature.select_get()}

                    # Make necessary to armature visibility and selection state for export
                    armature.hide_set(False)
                    armature.select_set(True)

                    # Check for ungrouped vertices, if they're found, switch to edit mode and select them
                    ungrouped_vertices = [v for v in mesh.data.vertices if not v.groups]
                    if ungrouped_vertices:
                        bpy.ops.object.mode_set(mode='EDIT')
                        bpy.ops.mesh.select_mode(type='VERT')
                        try:
                            bpy.ops.mesh.select_ungrouped()
                            armature.hide_set(True)
                        except RuntimeError:
                            bpy.ops.cp77.message_box('INVOKE_DEFAULT', message=f"No vertex groups in: {obj.name} are assigned weights. Assign weights before exporting.")                
                        bpy.ops.cp77.message_box('INVOKE_DEFAULT', message=f"Ungrouped vertices found and selected in: {obj.name}")                
                        return {'CANCELLED'}

                    for bone in armature.pose.bones:
                        bone_names.append(bone.name)
                    
                    if armature_modifier.object != mesh.parent:
                        armature_modifier.object = mesh.parent

                    group_has_bone = {group.index: False for group in obj.vertex_groups}
                    # groupless_bones = {}
                    for group in obj.vertex_groups:
                        if group.name in bone_names:
                            group_has_bone[group.index] = True
                             # print(vertex_group.name)
                                
                        # Add groups with no weights to the set
                    for group_index, has_bone in group_has_bone.items():
                        if not has_bone:
                            groupless_bones.add(obj.vertex_groups[group_index].name)

                if len(groupless_bones) is not 0:
                    bpy.ops.object.mode_set(mode='OBJECT')  # Ensure in object mode for consistent behavior
                    groupless_bones_list = ", ".join(sorted(groupless_bones))
                    armature.hide_set(True)
                    bpy.ops.cp77.message_box('INVOKE_DEFAULT', message=(f"the following vertex groups are not assigned to a bone, this will result in blender creating a neutral_bone and cause Wolvenkit import to Fail:    {groupless_bones_list}"))
                    return {'CANCELLED'}
                
                if mesh.data.name != mesh.name:
                    mesh.data.name = mesh.name

        if limit_selected:
            try:
                bpy.ops.export_scene.gltf(filepath=filepath, use_selection=True, **options)
                if not static_prop:
                    armature.hide_set(True)
            except Exception as e:
                print(e)
               
        else:
            if export_visible:
                try:
                    bpy.ops.export_scene.gltf(filepath=filepath, use_visible=True, **options)
                    if not static_prop:
                        armature.hide_set(True)
                except Exception as e:
                    print(e)

            else:
                try:
                    bpy.ops.export_scene.gltf(filepath=filepath, **options)
                    if not static_prop:
                         armature.hide_set(True)
                except Exception as e:
                    print(e)


        # Restore original armature visibility and selection states
        # for armature, state in armature_states.items():
            # armature.select_set(state["select"])
            # armature.hide_set(state["hide"])
            
        
# def ExportAll(self, context):
#     #Iterate through all objects in the scene
def ExportAll(self, context):
    # Iterate through all objects in the scene
    to_exp = [obj for obj in context.scene.objects if obj.type == 'MESH' and ('sourcePath' in obj or 'projPath' in obj)]

    if len(to_exp) > 0:
        for obj in to_exp:
            filepath = obj.get('projPath', '')  # Use 'projPath' property or empty string if it doesn't exist
            export_cyberpunk_glb(filepath=filepath, export_poses=False)
