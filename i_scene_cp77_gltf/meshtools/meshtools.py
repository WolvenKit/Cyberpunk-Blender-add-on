import bpy
import json
from collections import defaultdict
import re
import os

from .verttools import *
from ..cyber_props import *
from ..main.common import loc, show_message, get_collection_children
from ..main.bartmoss_functions import setActiveShapeKey, getShapeKeyNames, getModNames
from ..jsontool import JSONTool
def CP77SubPrep(self, context, smooth_factor, merge_distance):
    scn = context.scene
    obj = context.object
    current_mode = context.mode
    if not obj:
        show_message("No active object. Please Select a Mesh and try again")
        return {'CANCELLED'}
    if obj.type != 'MESH':
        show_message("The active object is not a mesh.")
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

def CP77ArmatureSet(self, context, reparent):
    selected_meshes = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    props = context.scene.cp77_panel_props
    target_armature_name = props.selected_armature
    target_armature = bpy.data.objects.get(target_armature_name)
    obj = context.object
    if not obj:
        show_message("No active object. Please Select a Mesh and try again")
        return {'CANCELLED'}
    if obj.type != 'MESH':
        show_message("The active object is not a mesh.")
        return {'CANCELLED'}
    if len(selected_meshes) == 0 or not target_armature or target_armature.type != 'ARMATURE':
        return {'FINISHED'}

    # Ensure the target armature has a collection
    if not target_armature.users_collection:
        target_collection = bpy.data.collections.new(target_armature.name + "_collection")
        bpy.context.scene.collection.children.link(target_collection)
        target_collection.objects.link(target_armature)
    else:
        target_collection = target_armature.users_collection[0]

    for mesh in selected_meshes:
        retargeted = False
        for modifier in mesh.modifiers:
            if modifier.type == 'ARMATURE' and modifier.object is not target_armature:
                modifier.object = target_armature
                retargeted = True
            elif modifier.type == 'ARMATURE' and modifier.object is target_armature:
                retargeted = True
                continue

        if not retargeted:
            armature = mesh.modifiers.new('Armature', 'ARMATURE')
            armature.object = target_armature

        if reparent != True:
            continue

        # Set parent
        mesh.parent = target_armature

        # Unlink the mesh from its original collections
        for col in mesh.users_collection:
            col.objects.unlink(mesh)

        # Link the mesh to the target armature's collection
        target_collection.objects.link(mesh)


# find or create the uv checker material instance. We don't need the return value, but we need the material to exist.
def ensure_uv_checker_material():
    #check if it's already defined
    if (match := next((mat for mat in bpy.data.materials if mat.name == uv_checker_matname), None)) is not None:
        return match

    # Load the image texture
    image_path = os.path.join(resources_dir, "uvchecker.png")
    image = bpy.data.images.load(image_path)

    # Create a new material
    uvchecker = bpy.data.materials.new(name=uv_checker_matname)
    uvchecker.use_nodes = True

    # Create a new texture node
    texture_node = uvchecker.node_tree.nodes.new(type='ShaderNodeTexImage')
    texture_node.location = (-200, 0)
    texture_node.image = image

    # Connect the texture node to the shader node
    shader_node = uvchecker.node_tree.nodes[loc("Principled BSDF")]
    uvchecker.node_tree.links.new(texture_node.outputs[loc('Color')], shader_node.inputs[loc('Base Color')])

def CP77UvChecker(self, context):
    selected_meshes = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    bpy_mats=bpy.data.materials
    obj = context.object
    current_mode = context.mode

    if not obj:
        show_message("No active object. Please Select a Mesh and try again")
        return {'CANCELLED'}
    if obj.type != 'MESH':
        show_message("The active object is not a mesh.")
        return {'CANCELLED'}

    ensure_uv_checker_material()

    for mesh in selected_meshes:
        # the mesh already has an UV checker material slot, we have nothing to do
        if any(mat.name == uv_checker_matname for mat in context.object.material_slots):
            continue

        try:
            current_mat = context.object.active_material.name
            mesh['uvCheckedMat'] = current_mat
        except AttributeError:
            print(f"Mesh {mesh.name} already has an UV checker material")

        bpy.data.meshes[mesh.name].materials.append(bpy_mats[uv_checker_matname])
        i = mesh.data.materials.find(uv_checker_matname)

        if i >= 0:
            mesh.active_material_index = i
        if current_mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.object.material_slot_assign()

            #print(current_mode)

        if context.mode != current_mode:
            bpy.ops.object.mode_set(mode=current_mode)

    return {'FINISHED'}

uv_checker_matname = 'UV_Checker'

def CP77UvUnChecker(self, context):
    selected_meshes = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    obj = context.object
    current_mode = context.mode
    if not obj:
        show_message("No active object. Please Select a Mesh and try again")
        return {'CANCELLED'}
    if obj.type != 'MESH':
        show_message("The active object is not a mesh.")
        return {'CANCELLED'}

    original_mat_name = None
    for mesh in selected_meshes:
        if uv_checker_matname not in mesh.data.materials:
            continue
        if 'uvCheckedMat' in mesh.keys() and 'uvCheckedMat' != None:
            original_mat_name = mesh['uvCheckedMat']
        # Find the index of the material slot with the specified name
        material_index = mesh.data.materials.find(uv_checker_matname)
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

def CP77RefitChecker(self, context):
    scene = context.scene
    objects = scene.objects
    refitter = []
    addon = []
    for obj in objects:
        if obj.type =='LATTICE':
            if "refitter_type" in obj:
                refitter.append(obj)
                print('refitters found in scene:', refitter)
            if "refitter_addon" in obj:
                addon.append(obj)
                print('refitter addons found in scene:', addon)
    print(f'refitter result: {refitter} refitter addon: {addon}')
    return refitter, addon

def applyModifierAsShapeKey(obj):
    names = getModNames(obj)
    autoFitters =  [s for s in names if 'Autofitter' in s]

    if len(autoFitters) == 0:
        print(f"No autofitter found for {obj.name}. Current modifiers are {names}")
        return

    for refitter in autoFitters:
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        bpy.ops.object.modifier_apply_as_shapekey(keep_modifier=False, modifier=refitter)
        print(f"Applied modifier '{refitter}' as shape key.")

def applyRefitter(obj):
    applyModifierAsShapeKey(obj)
    orignames = getShapeKeyNames(obj)
    for name in orignames:
        if 'Autofitter' in name:
            refitkey = setActiveShapeKey(obj, name)
            refitkey.value = 1
        if 'Garment' in name:
            gskey = setActiveShapeKey(obj, name)
            gskey.value = 1

            bpy.ops.object.shape_key_add(from_mix=True)

            gskey.value = 0
            gskey = setActiveShapeKey(obj, name)
            bpy.ops.object.shape_key_remove(all=False)
    bpy.context.view_layer.objects.active = obj

    # if we have active shape keys: activate 'Basis' and remove it
    if not setActiveShapeKey(obj, 'Basis'):
        raise Exception("Failed to activate 'Basis' shape key")
    bpy.ops.object.shape_key_remove(all=False)

    newnames = getShapeKeyNames(obj)
    for name in newnames:
        if 'Autofitter' in name:
            refitkey = setActiveShapeKey(obj, name)
            refitkey.name = 'Basis'
        if name not in orignames:
            newgs = setActiveShapeKey(obj, name)
            newgs.name = 'GarmentSupport'

def CP77Refit(context, refitter, addon, target_body_path, target_body_name, useAddon, addon_target_body_path, addon_target_body_name, fbx_rot):
    autofitter(context, refitter, addon, target_body_path, useAddon, addon_target_body_path, addon_target_body_name, target_body_name, fbx_rot)

def autofitter(context, refitter, addon, target_body_path, useAddon, addon_target_body_path, addon_target_body_name, target_body_name, fbx_rot):
    if target_body_name is None:
        show_message("No target body selected. Please select a target body and try again.")
        return {'CANCELLED'}

    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
    if len(selected_meshes) == 0:
        show_message("No meshes selected. Please select at least one mesh and try again.")
        return {'CANCELLED'}
    
    scene = context.scene
    refitter_obj = None
    addon_obj = None
    r_c = None

    if len(refitter) != 0:
        for obj in refitter:
            if obj['refitter_type'] == target_body_name:
                print(obj['refitter_type'], 'refitter found')
                refitter_obj = obj
                break
                
        if refitter_obj:
            print('theres a refitter:', refitter_obj.name, 'type:', refitter_obj['refitter_type'])
            for mesh in selected_meshes[:]:
                print('Checking mesh for refits:', mesh.name)
                for modifier in mesh.modifiers:
                    if modifier.type == 'LATTICE' and modifier.object == refitter_obj:
                        print(mesh.name, 'is already refit for', target_body_name)
                        selected_meshes.pop(selected_meshes.index(mesh))
                        break
    if len(addon) != 0:
        for obj in addon:
            if obj['refitter_addon_type'] == addon_target_body_name:
                print(obj['refitter_addon_type'], 'refitter addon found')
                addon_obj = obj
                break

        if addon_obj:
            print('theres a refitter addon:', addon_obj.name, 'type:', addon_obj['refitter_addon_type'])
            for mesh in selected_meshes:
                print('Checking mesh for refit addons:', mesh.name)
                for modifier in mesh.modifiers:
                    if modifier.type == 'LATTICE' and modifier.object == addon_obj:
                        print(mesh.name, 'is already refit for', addon_target_body_name)
                        selected_meshes.pop(selected_meshes.index(mesh))
                        break
                        
    if len(selected_meshes) == 0:
        show_message("No mesh needs refitting. Please select at least one mesh and try again.")
        return {'CANCELLED'}
                        
    for collection in scene.collection.children:
        if collection.name == 'Refitters':
            r_c = collection
            break
    if r_c is None:
        r_c = bpy.data.collections.new('Refitters')
        scene.collection.children.link(r_c)

    new_lattice = add_lattice(target_body_path, r_c, fbx_rot, target_body_name)

    for mesh in selected_meshes:
        lattice_modifier = mesh.modifiers.new(new_lattice.name,'LATTICE')
        print(f'refitting: {mesh.name} to: {new_lattice["refitter_type"]}')

        if useAddon:
            lattice_object_name, control_points, lattice_points, lattice_object_location, lattice_object_rotation, lattice_object_scale, lattice_interpolation_u, lattice_interpolation_v, lattice_interpolation_w  = JSONTool.jsonload(addon_target_body_path)
            new_lattice = setup_lattice(r_c, fbx_rot, lattice_object_name, addon_target_body_name, control_points, lattice_points, lattice_object_location, lattice_object_rotation, lattice_object_scale,lattice_interpolation_u, lattice_interpolation_v, lattice_interpolation_w)
            lattice_modifier.object = new_lattice

        lattice_modifier.object = new_lattice
        applyRefitter(mesh)

def add_garment_support(context, target_collection_name):
    target_collection_children = get_collection_children(target_collection_name, "MESH")
    if not target_collection_children:
        show_message(f"Target collection '{target_collection_name}' not found.")
        return {'CANCELLED'}
    if len(target_collection_children) == 0:
        show_message(f"No meshes found in collection '{target_collection_name}'.")
        return {'CANCELLED'}
    if len(target_collection_children) > 1:
        show_message(f"Target collection '{target_collection_name}' contains multiple meshes. Please join them into a single mesh before proceeding.")
        return {'CANCELLED'}

    target_mesh = target_collection_children[0]

    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj != target_mesh]

    if not selected_meshes or len(selected_meshes) == 0:
        show_message("No objects selected, or only the target mesh selected!")
        return {'CANCELLED'}

    current_mode = context.mode

    try:
        # Remember current mode and switch to OBJECT mode
        if current_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        for obj in selected_meshes:
            # Remove existing 'GarmentSupport' shape key if it exists
            if obj.data.shape_keys:
                for shape_key in reversed(obj.data.shape_keys.key_blocks):
                    obj.shape_key_remove(shape_key)

            # Add shrinkwrap modifier
            shrinkwrap = obj.modifiers.new(name="GarmentSupport", type='SHRINKWRAP')
            shrinkwrap.target = target_mesh
            shrinkwrap.wrap_method = 'NEAREST_SURFACEPOINT'
            shrinkwrap.wrap_mode = 'ON_SURFACE'  # Note: 'Snap Mode' is actually 'wrap_mode' in API
            shrinkwrap.offset = 0.001

            # Apply modifier as shape key
            bpy.context.view_layer.objects.active = obj  # Set active object
            bpy.ops.object.modifier_apply_as_shapekey(modifier=shrinkwrap.name)

    except Exception as e:
        # delete the modifier if an error occurred
        if "GarmentSupport" in obj.modifiers:
            obj.modifiers.remove(obj.modifiers["GarmentSupport"])
        show_message("An error occurred while creating garment support: " + str(e))
        return {'CANCELLED'}
    finally:
        # Switch back to original mode
        if  context.mode != current_mode:
            bpy.ops.object.mode_set(mode=current_mode)

    return {'FINISHED'}


# re-use previous lattice, or add a new one if there isn't one
def add_lattice(target_body_path, r_c, fbx_rot, target_body_name):
    for refitter in r_c.objects:
        if refitter.name == f"{target_body_name}Autofitter":
            print(f"{target_body_name}Autofitter already exists")
            return refitter

    print(f"Creating {target_body_name}Autofitter from json file (reading {target_body_path})")
    # Get the JSON file path for the selected target_body
    lattice_object_name, control_points, lattice_points, lattice_object_location, lattice_object_rotation, lattice_object_scale, lattice_interpolation_u, lattice_interpolation_v, lattice_interpolation_w  = JSONTool.jsonload(target_body_path)
    new_lattice = setup_lattice(r_c, fbx_rot, lattice_object_name, target_body_name, control_points, lattice_points, lattice_object_location, lattice_object_rotation, lattice_object_scale,lattice_interpolation_u, lattice_interpolation_v, lattice_interpolation_w)
    return new_lattice


def setup_lattice(r_c, fbx_rot, lattice_object_name, target_body_name, control_points, lattice_points, lattice_object_location, lattice_object_rotation, lattice_object_scale,lattice_interpolation_u, lattice_interpolation_v, lattice_interpolation_w):
    bpy.ops.object.add(type='LATTICE', enter_editmode=False, location=(0, 0, 0))
    new_lattice = bpy.context.object
    new_lattice.name = lattice_object_name
    new_lattice["refitter_type"] = target_body_name
    lattice = new_lattice.data
    r_c.objects.link(new_lattice)
    bpy.context.collection.objects.unlink(new_lattice)

    # Set the dimensions of the lattice
    lattice.points_u = lattice_points[0]
    lattice.points_v = lattice_points[1]
    lattice.points_w = lattice_points[2]
    new_lattice.location[0] = lattice_object_location[0]
    new_lattice.location[1] = lattice_object_location[1]
    new_lattice.location[2] = lattice_object_location[2]
    if fbx_rot:
    # Rotate the Z-axis by 180 degrees (pi radians)
        new_lattice.rotation_euler = (lattice_object_rotation[0], lattice_object_rotation[1],lattice_object_rotation[2] + 3.14159)
    else:
        new_lattice.rotation_euler = (lattice_object_rotation[0], lattice_object_rotation[1],lattice_object_rotation[2])
    new_lattice.scale[0] = lattice_object_scale[0]
    new_lattice.scale[1] = lattice_object_scale[1]
    new_lattice.scale[2] = lattice_object_scale[2]

    # Set interpolation types
    lattice.interpolation_type_u = lattice_interpolation_u
    lattice.interpolation_type_v = lattice_interpolation_v
    lattice.interpolation_type_w = lattice_interpolation_w

    # Create a flat list of lattice points
    lattice_points = lattice.points
    flat_lattice_points = [lattice_points[w + v * lattice.points_u + u * lattice.points_u * lattice.points_v] for u in range(lattice.points_u) for v in range(lattice.points_v) for w in range(lattice.points_w)]

    for control_point, lattice_point in zip(control_points, flat_lattice_points):
        lattice_point.co_deform = control_point

    if new_lattice:
        bpy.context.object.hide_viewport = True
    return new_lattice


material_storage = defaultdict(dict)  # {object_name: {slot_index: material_name}}

def safe_join(self, context):

        # Get selected meshes matching submesh pattern
        selected_meshes = [
            obj for obj in context.selected_objects if obj.type == 'MESH' and re.match(r'submesh_\d\d', obj.name)
        ]

        if not selected_meshes:
            self.report({'ERROR'}, "No valid submeshes selected (must be named 'submesh_XX')")
            return {'CANCELLED'}

        # Store original materials and assign submesh materials
        for obj in selected_meshes:
            # Store original materials
            material_storage[obj.name].clear()
            for i, slot in enumerate(obj.material_slots):
                if slot.material:
                    material_storage[obj.name][i] = slot.material.name

            # Create/assign submesh material
            if  obj.name not in bpy.data.materials:
                mat = bpy.data.materials.new(name= obj.name)
                mat.diffuse_color = (0.8, 0.8, 0.8, 1)

            # Clear and assign new material
            obj.data.materials.clear()
            obj.data.materials.append(bpy.data.materials[obj.name])

            # Enter edit mode to assign material to all geometry
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='EDIT')

            # Select all geometry
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.mesh.select_all(action='SELECT')

            # Assign material to selected faces
            bpy.context.object.active_material_index = 0
            bpy.ops.object.material_slot_assign()

            bpy.ops.object.mode_set(mode='OBJECT')

        # Join meshes
        bpy.ops.object.select_all(action='DESELECT')

        for obj in selected_meshes:
            obj.select_set(True)

        context.view_layer.objects.active = selected_meshes[0]
        bpy.ops.object.join()

        return {'FINISHED'}


def _restore_original_materials(self, obj):
    """Restore materials from storage to given object."""
    if not obj.data.materials:
        obj.data.materials.clear()

    stored_materials = material_storage.get(obj.name, {})

    # Ensure we have enough material slots
    max_slot = max(stored_materials.keys(), default=-1) + 1
    while len(obj.data.materials) < max_slot:
        obj.data.materials.append(None)

    # Restore materials to correct slots
    for slot_idx, mat_name in stored_materials.items():
        if mat_name in bpy.data.materials:
            obj.data.materials[slot_idx] = bpy.data.materials[mat_name]
        else:
            self.report({'WARNING'}, f"Missing material: {mat_name}")

def safe_split(self, context):
    obj = context.active_object

    if obj is None or obj.type != 'MESH':
        show_message("No meshes selected. Please select a mesh and try again.")
        return {'CANCELLED'}

    # Enter edit mode to split by material
    bpy.ops.object.mode_set(mode='EDIT')

    # Select all geometry and separate by materials
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.separate(type='MATERIAL')
    bpy.ops.object.mode_set(mode='OBJECT')

    # Get newly created objects from the split
    new_objects = [o for o in context.selected_objects]

    # Process each split object
    for new_obj in new_objects:
        # Rename object to match its material
        if new_obj.data.materials and new_obj.data.materials[0]:
            new_obj.name = new_obj.data.materials[0].name


        new_obj.data.materials.clear()
        # Restore original materials if available
        if new_obj.name in material_storage:
            _restore_original_materials(self, new_obj)

    return {'FINISHED'}

