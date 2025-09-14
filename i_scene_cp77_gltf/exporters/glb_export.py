import bpy
from .. animtools import reset_armature
from ..main.common import show_message
from ..animtools.tracks import export_anim_tracks
from ..main.bartmoss_functions import get_safe_mode, safe_mode_switch
POSE_EXPORT_OPTIONS = {
    'export_animations': True,
    'export_anim_slide_to_zero': True,
    'export_animation_mode': 'ACTIONS',
    'export_anim_single_armature': True,
    'export_bake_animation': False,
}

red_color = (1, 0, 0, 1)  # RGBA

garment_cap_name = "_GarmentSupportCap"
garment_weight_name = "_GarmentSupportWeight"

# make sure that a custom scale or whatever won't screw up the export
export_defaults = {
    'system': 'METRIC',
    'length_unit': 'METERS',
    'scale_length': 1.0,
    'system_rotation': 'DEGREES',
    'mass_unit': 'KILOGRAMS',
    'temperature_unit': 'KELVIN',
    'time_unit': 'SECONDS',
    'use_separate': False,
}

# setup the default options to be applied to all export types
def default_cp77_options():
    major, minor = bpy.app.version[:2]
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
    if major >= 4:
        options.update({
            'export_image_format': 'NONE',
            'export_try_sparse_sk': False,
        })
        if minor >= 1:
            options.update({
                'export_shared_accessors': True,
                'export_try_omit_sparse_sk': False,
            })
        return options
    # keep original behavior for <4 as-is
    return options

# make sure meshes are exported with tangents, morphs and vertex colors
def cp77_mesh_options():
    major, minor = bpy.app.version[:2]
    options = {
        'export_animations': False,
        'export_tangents': True,
        'export_normals': True,
        'export_morph_tangent': True,
        'export_morph_normal': True,
        'export_morph': True,
        'export_attributes': True,
    }
    if major < 4:
        options.update({
            'export_colors': True,
        })
        if minor >= 2:
            # NOTE: original had a trailing space in key 'export_all_vertex_colors '
            options.update({
                "export_all_vertex_colors ": True,
                "export_active_vertex_color_when_no_material": True,
            })
    return options

# the options for anims
def pose_export_options():
    # return a copy to avoid accidental mutation across calls
    return POSE_EXPORT_OPTIONS.copy()

# Garment support layers
def add_garment_cap(mesh):
    cap_layer = mesh.data.color_attributes.get(garment_cap_name)
    weight_layer = mesh.data.color_attributes.get(garment_weight_name)

    if cap_layer is None:
        cap_layer = mesh.data.color_attributes.new(
            name=garment_cap_name, domain='CORNER', type='BYTE_COLOR'
        )

    # do not overwrite existing garment weight; create when missing
    if weight_layer is None:
        weight_layer = mesh.data.color_attributes.new(
            name=garment_weight_name, domain='CORNER', type='BYTE_COLOR'
        )

    # Paint the entire cap layer red 
    if cap_layer is not None:
        n = len(cap_layer.data)
        if n:
            cap_layer.data.foreach_set("color", red_color * n)

# back up user's current workbench configuration and reset to factory defaults
def save_user_settings_and_reset_to_default():
    us = bpy.context.scene.unit_settings
    user_settings = {
        'bpy_context': bpy.context.mode,
        'system': us.system,
        'length_unit': us.length_unit,
        'scale_length': us.scale_length,
        'system_rotation': us.system_rotation,
        'mass_unit': us.mass_unit,
        'temperature_unit': us.temperature_unit,
        'time_unit': us.time_unit,
        'use_separate': us.use_separate,
    }
    for key, value in export_defaults.items():
        setattr(us, key, value)
    return user_settings

# restore user's previous state
def restore_user_settings(user_settings):
    us = bpy.context.scene.unit_settings
    for key, value in user_settings.items():
        if key == 'bpy_context':
            continue
        setattr(us, key, value)
    if bpy.context.mode != user_settings['bpy_context']:
        bpy.ops.object.mode_set(mode=user_settings['bpy_context'])

# mana: by assigning default attributes, we make this update-safe.
def export_cyberpunk_glb(context, filepath, export_poses=False, export_visible=False, 
                         limit_selected=True, static_prop=False, red_garment_col=False, apply_transform=True,
                         action_filter=False, export_tracks=False):
    user_settings = save_user_settings_and_reset_to_default()

    objects = context.selected_objects
    options = default_cp77_options()

    # ensure object mode
    if get_safe_mode() != 'OBJECT':
        safe_mode_switch('OBJECT')

    try:
        if export_poses:
            armatures = [obj for obj in objects if obj.type == 'ARMATURE']
            if not armatures:
                raise ValueError("No armature objects are selected, please select an armature")
            # TODO: fix this
            if bpy.app.version >= (4, 0, 0) and action_filter:
                options['export_action_filter'] = True
            export_anims(context, filepath, options, armatures)
        else:
            #if export_poses option isn't used, check to make sure there are meshes selected and throw an error if not
            meshes = [obj for obj in objects if obj.type == 'MESH' and not "Icosphere" in obj.name]
            if not meshes:
                raise ValueError("No meshes selected, please select at least one mesh")
            export_meshes(context, filepath, export_visible, limit_selected, static_prop, red_garment_col, apply_transform, meshes, options)
    except Exception as e:
        show_message(str(e))  # why: robust even if e.args is empty
        return {'CANCELLED'}
    finally:
        restore_user_settings(user_settings)
        return {'FINISHED'}

def export_anims(context, filepath, options, armatures, export_tracks = False):
    cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
    for action in bpy.data.actions:
        # schema & base defaults
        if "schema" not in action:
            action["schema"] = {"type": "wkit.cp2077.gltf.anims", "version": 4}
        if "animationType" not in action:
            action["animationType"] = "Normal"
        if "rootMotionType" not in action:
            action["rootMotionType"] = "Unknown"
        if "frameClamping" not in action:
            action["frameClamping"] = False
        if "frameClampingStartFrame" not in action:
            action["frameClampingStartFrame"] = -1
        if "frameClampingEndFrame" not in action:
            action["frameClampingEndFrame"] = -1
        if "numExtraJoints" not in action:
            action["numExtraJoints"] = 0
        if "numExtraTracks" not in action:
            action["numExtraTracks"] = 0
        if "constTrackKeys" not in action:
            action["constTrackKeys"] = []
        if "trackKeys" not in action:
            action["trackKeys"] = []
        if "fallbackFrameIndices" not in action:
            action["fallbackFrameIndices"] = []
        if "optimizationHints" not in action:
            action["optimizationHints"] = {"preferSIMD": False, "maxRotationCompression": 0}

        if export_tracks:
            try:
                if any(fc.data_path and fc.data_path.startswith('["T') for fc in action.fcurves):
                    export_anim_tracks(action)
                    # verbose summary
                    try:
                        tk = len(action.get("trackKeys", []))
                        ctk = len(action.get("constTrackKeys", []))
                        try:
                            _vprint(f"Exported tracks for {action.name}: {tk} animated, {ctk} constant")
                        except NameError:
                            pass
                    except Exception:
                        pass
                else:
                    try:
                        _vprint(f'No track FCurves found on {action.name}; skipping export_anim_tracks')
                    except NameError:
                        pass
            except Exception as e:
                print(f"export_anim_tracks failed for {action.name}: {e}")

    options.update(pose_export_options())
    for armature in armatures:
        reset_armature(armature, context)
        print(options)
        bpy.ops.export_scene.gltf(filepath=filepath, use_selection=True, **options)
        # only one armature expected
        return {'FINISHED'}

    return {'FINISHED'}

def export_meshes(context, filepath, export_visible, limit_selected, static_prop, red_garment_col, apply_transform, meshes, options):
    groupless_bones = set()
    bone_names = []
    options.update(cp77_mesh_options())

    if not limit_selected:
        for obj in bpy.data.objects:
            if obj.type == 'MESH' and "Icosphere" not in obj.name:
                obj.select_set(True)

    armature_modifier = None
    armature = None

    try:
        for mesh in meshes:
            if not mesh.data.uv_layers:
                raise ValueError("Meshes must have UV layers in order to import in Wolvenkit. See https://tinyurl.com/uv-layers")

            #check submesh vertex count to ensure it's less than the maximum for import
            vert_count = len(mesh.data.vertices)
            if vert_count > 65535:
                raise ValueError(f"{mesh.name} has {vert_count} vertices.           Each submesh must have less than 65,535 vertices. See https://tinyurl.com/vertex-count")

            # apply transforms
            if apply_transform:
                bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

            #check that faces are triangulated, cancel export, switch to edit mode with the untriangulated faces selected and throw an error
            if False: #any(len(face.vertices) != 3 for face in mesh.data.polygons):
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_mode(type='FACE')
                bpy.ops.mesh.select_face_by_sides(number=3, type='NOTEQUAL', extend=False)
                raise ValueError("All faces must be triangulated before exporting. Untriangulated faces have been selected for you. See https://tinyurl.com/triangulate-faces")

            if red_garment_col:
                add_garment_cap(mesh)

            if mesh.data.name != mesh.name:
                mesh.data.name = mesh.name

            # Check for ungrouped vertices, if they're found, switch to edit mode and select them
            # No need to do this for static props
            if static_prop:
                continue

            # ungrouped vertices: generator avoids list allocation
            if any(not v.groups for v in mesh.data.vertices):
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_mode(type='VERT')
                try:
                    bpy.ops.mesh.select_ungrouped()
                    raise ValueError(f"Ungrouped vertices found and selected in: {mesh.name}. See https://tinyurl.com/ungrouped-vertices")
                except RuntimeError:
                    raise ValueError(f"No vertex groups in: {mesh.name} are assigned weights. Assign weights before exporting. See https://tinyurl.com/assign-vertex-weights")

            # find armature modifier per-mesh
            armature_modifier = None
            for modifier in mesh.modifiers:
                if modifier.type == 'ARMATURE' and modifier.object:
                    armature_modifier = modifier
                    break
            if not armature_modifier:
                raise ValueError((f"Armature missing from: {mesh.name} Armatures are required for movement. If this is intentional, try 'export as static prop'. See https://tinyurl.com/armature-missing"))

            armature = armature_modifier.object

            # visibility & selection for export
            armature.hide_set(False)
            armature.select_set(True)

            # ensure modifier references the parent armature
            if armature_modifier.object != mesh.parent:
                armature_modifier.object = mesh.parent
                armature = armature_modifier.object

            # set-based membership for speed; identical result
            bone_names = {bone.name for bone in armature.pose.bones}
            group_names = {group.name for group in mesh.vertex_groups}
            missing = group_names - bone_names

            if missing:
                bpy.ops.object.mode_set(mode='OBJECT')
                groupless_bones_list = ", ".join(sorted(missing))
                raise ValueError(
                    "The following vertex groups are not assigned to a bone, this will result in blender creating a neutral_bone and cause Wolvenkit import to fail:    "
                    f"{groupless_bones_list}\nSee https://tinyurl.com/unassigned-bone"
                )

        if limit_selected:
            try:
                bpy.ops.export_scene.gltf(filepath=filepath, use_selection=True, **options)
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
        return {'FINISHED'}

    except Exception as e:
        print(f"{e}")
        return {'CANCELLED'}

    finally:
        if armature is not None and not static_prop:
            armature.hide_set(True)

# def ExportAll(self, context):
#     #Iterate through all objects in the scene

def ExportAll(self, context):
    # Iterate through all objects in the scene
    to_exp = [obj for obj in context.scene.objects if obj.type == 'MESH' and ('sourcePath' in obj or 'projPath' in obj)]

    if len(to_exp) > 0:
        for obj in to_exp:
            filepath = obj.get('projPath', '')  # Use 'projPath' property or empty string if it doesn't exist
            export_cyberpunk_glb(filepath=filepath, export_poses=False)






