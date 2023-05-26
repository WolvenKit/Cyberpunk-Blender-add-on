import bpy 

def default_cp77_options():
    options = {
        'export_format': 'GLB',
        'export_normals': True,
        'check_existing': True,
        'export_skins': True,
        'export_cameras': False,
        'export_yup': True,
        'export_animations': True,
        'export_tangents': True,
        'export_morph': True,
        'export_morph_normal': True,
        'export_morph_tangent': True,
        'export_materials': 'NONE',
        'export_all_influences': True,
        'export_lights': False,
        'export_colors': True
    }
    return options

def pose_export_options():
    options = {
        'export_format': 'GLB',
        'check_existing': True,
        'export_skins': True,
        'export_cameras': False,
        'export_yup': True,
        'export_frame_range': False,
        'export_animations': True,
        'export_all_influences': True,
        'export_anim_single_armature': True,
        'export_apply': False,
        'export_tangents': True,
        'export_materials': 'NONE',
        'export_lights': False,
        'export_morph_normal': True
    }
    return options

    
def export_cyberpunk_glb(context, filepath, export_poses):
    # Retrieve the selected objects
    objects = context.selected_objects
    #if for photomode, make sure theres an armature selected, if not use the message box to show an error
    if export_poses:
        armatures = [obj for obj in objects if obj.type == 'ARMATURE']
        if not armatures:
            bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="No armature selected, please select an armature")
            return {'CANCELLED'}
        #if the export poses value is True, set the export options to ensure the armature is exported properly with the animations
        options = pose_export_options()
    else:
    #if export_poses option isn't used, check to make sure there are meshes selected and throw an error if not
        meshes = [obj for obj in objects if obj.type == 'MESH']
        if not meshes:
            bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="No meshes selected, please select at least one mesh")
            return {'CANCELLED'}
        #use the right options for exporting a mesh
        options = default_cp77_options()

    print(options)  

    # if exporting meshes, make sure that any hidden armatures connected to those meshes are exported by making them visible, selecting them
    hidden_armatures = []
    for obj in objects:
        if obj.type == 'MESH':
            for modifier in obj.modifiers:
                if modifier.type == 'ARMATURE' and modifier.object and modifier.object.hide_get():
                    modifier.object.hide_set(False)
                    modifier.object.select_set(True)
             #add these armatures to a dictionary so we can hide them again later
                    hidden_armatures.append(modifier.object)

    # Export the meshes to glb
    bpy.ops.export_scene.gltf(filepath=filepath, use_selection=True, **options)
    
    # Restore armature visibility and selection state
    for armature in hidden_armatures:
        armature.select_set(False)  # Deselect the armature
        armature.hide_set(True)  # Hide the armature
  # Report success               