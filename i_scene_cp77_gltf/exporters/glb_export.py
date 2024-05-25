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

        if vers[1] >= 1:
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
        'export_anim_slide_to_zero': True,
        'export_animation_mode': 'ACTIONS',
        'export_anim_single_armature': True,
        "export_bake_animation": True
    }
    return options


red_color = (1, 0, 0, 1)  # RGBA
garment_cap_name="_GarmentSupportCap"
garment_weight_name="_GarmentSupportWeight"

def add_garment_cap(mesh):

    cap_layer = None
    weight_layer = None

    try:
        cap_layer = mesh.data.color_attributes.get(garment_cap_name)
    except:
        print("cap layer doesn't exist")

    try:
        weight_layer = mesh.data.color_attributes.get(garment_weight_name)
    except:
        print("weight layer doesn't exist")

    if cap_layer == None:
        bpy.context.view_layer.objects.active = mesh
        bpy.ops.geometry.color_attribute_add(name=garment_cap_name, domain='CORNER', data_type='BYTE_COLOR')
    # else:
        # TODO Presto show a warning

    # do not overwrite already-existing garment weight layers. Newly-created layer will be black anyway, nothing to do here.
    if weight_layer == None:
        bpy.context.view_layer.objects.active = mesh
        bpy.ops.geometry.color_attribute_add(name=garment_weight_name, domain='CORNER', data_type='BYTE_COLOR')

    # Now Paint the entire cap layer red
    for poly in mesh.data.polygons:
        for loop_index in poly.loop_indices:
            # paint cap layer red as per export option
            if cap_layer != None and loop_index < (len(cap_layer.data)):
                cap_layer.data[loop_index].color = red_color


# setup the actual exporter - rewrote almost all of this, much quicker now
# mana: by assigning default attributes, we make this update-safe (some older scripts broke). Just don't re-name them!
def export_cyberpunk_glb(context, filepath=None, export_poses=False, export_visible=False, limit_selected=True, static_prop=False, red_garment_col=False):

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
            # TODO should that be here?
            return{'FINISHED'}

        return {'FINISHED'}

    if not limit_selected:
        for obj in bpy.data.objects:
            if obj.type == 'MESH' and not "Icosphere" in obj.name:
                obj.select_set(True)

    #if export_poses option isn't used, check to make sure there are meshes selected and throw an error if not
    meshes = [obj for obj in objects if obj.type == 'MESH' and not "Icosphere" in obj.name]

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
            bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="Meshes must have UV layers in order to import in Wolvenkit. See https://tinyurl.com/uv-layers")
            return {'CANCELLED'}

        #check submesh vertex count to ensure it's less than the maximum for import
        vert_count = len(mesh.data.vertices)
        if vert_count > 65535:
            message=(f"{mesh.name} has {vert_count} vertices.           Each submesh must have less than 65,535 vertices. See https://tinyurl.com/vertex-count")
            bpy.ops.cp77.message_box('INVOKE_DEFAULT', message=message)
            return {'CANCELLED'}

        #check that faces are triangulated, cancel export, switch to edit mode with the untriangulated faces selected and throw an error
        for face in mesh.data.polygons:
            if len(face.vertices) != 3:
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_mode(type='FACE')
                bpy.ops.mesh.select_face_by_sides(number=3, type='NOTEQUAL', extend=False)
                bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="All faces must be triangulated before exporting. Untriangulated faces have been selected for you. See https://tinyurl.com/triangulate-faces")
                return {'CANCELLED'}

        # Check for ungrouped vertices, if they're found, switch to edit mode and select them
        # No need to do this for static props
        if not static_prop:
            ungrouped_vertices = [v for v in mesh.data.vertices if not v.groups]
            if ungrouped_vertices:
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_mode(type='VERT')
                try:
                    bpy.ops.mesh.select_ungrouped()
                    bpy.ops.cp77.message_box('INVOKE_DEFAULT', message=f"Ungrouped vertices found and selected in: {mesh.name}. See https://tinyurl.com/ungrouped-vertices")
                except RuntimeError:
                    bpy.ops.cp77.message_box('INVOKE_DEFAULT', message=f"No vertex groups in: {mesh.name} are assigned weights. Assign weights before exporting. See https://tinyurl.com/assign-vertex-weights")
                return {'CANCELLED'}

        if red_garment_col:
            add_garment_cap(mesh)

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
                        bpy.ops.cp77.message_box('INVOKE_DEFAULT', message=(f"Armature missing from: {obj.name} Armatures are required for movement. If this is intentional, try 'export as static prop'. See https://tinyurl.com/armature-missing"))
                        return {'CANCELLED'}
                    # Store original visibility and selection state
                    armature = armature_modifier.object
                    armature_states[armature] = {"hide": armature.hide_get(),
                                                "select": armature.select_get()}

                    # Make necessary to armature visibility and selection state for export
                    armature.hide_set(False)
                    armature.select_set(True)

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
                    bpy.ops.cp77.message_box('INVOKE_DEFAULT', message=(f"The following vertex groups are not assigned to a bone, this will result in blender creating a neutral_bone and cause Wolvenkit import to fail:    {groupless_bones_list}\nSee https://tinyurl.com/unassigned-bone"))
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
