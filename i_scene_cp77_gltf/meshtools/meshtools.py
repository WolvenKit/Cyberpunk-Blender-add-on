import bpy
import bmesh
import math
import re
import os
from collections import defaultdict
from .verttools import *
from ..cyber_props import *
from ..main.common import (
    loc, show_message, get_collection_children, 
    get_resources_dir
)
from ..main.bartmoss_functions import (
    get_safe_mode, safe_mode_switch, 
    store_current_context, restore_previous_context,
    hasShapeKeys, getShapeKeyNames, getShapeKeyByName, setActiveShapeKey,
    is_mesh
)
from ..main.npz_io import load_lattice_npz

def CP77SubPrep(self, context, smooth_factor: float, merge_distance: float):
    angle_deg = max(0.0, min(180.0, float(smooth_factor)))
    
    # Validate first
    targets = [ob for ob in context.selected_objects if ob.type == 'MESH']
    if not targets:
        show_message("Select one or more meshes.")
        return {'CANCELLED'}
    
    # Store context
    store_current_context()
    
    try:
        # Switch to object mode if needed
        if get_safe_mode() != 'OBJECT':
            safe_mode_switch('OBJECT')
        
        merged_total = 0
        for ob in targets:
            me = ob.data
            # avoid modifying other objects that share this mesh
            if me.users > 1:
                ob.data = me = me.copy()

            do_merge = merge_distance > 0.0 and not hasShapeKeys(ob)
            bm = bmesh.new()
            try:
                bm.from_mesh(me)
                bm.verts.ensure_lookup_table()
                bm.edges.ensure_lookup_table()
                bm.faces.ensure_lookup_table()
                
                start = len(bm.verts)
                # mark seams at boundaries & wires
                for e in bm.edges:
                    if len(e.link_faces) == 0 or e.is_boundary:
                        e.seam = True
                if do_merge:
                    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=float(merge_distance))
                bm.normal_update()
                for f in bm.faces:
                    f.smooth = True
                
                bm.to_mesh(me)
                merged_total += max(0, start - len(bm.verts))
            finally:
                bm.free()
            
            me.update(calc_edges=True, calc_edges_loose=True)
        
        # apply Shade Auto Smooth to selected meshes
        active_backup = context.view_layer.objects.active
        context.view_layer.objects.active = targets[0]
        bpy.ops.object.shade_auto_smooth(use_auto_smooth=True, angle=math.radians(angle_deg))
        context.view_layer.objects.active = active_backup
        
        show_message(f"Submesh preparation complete. {merged_total} verts merged across {len(targets)} object(s).")
        return {'FINISHED'}
    
    finally:
        # restore original context
        restore_previous_context()

def CP77ArmatureSet(self, context, reparent):
    """Set armature for a group of objects quickly with the option to reparent them if desired """
    selected_meshes = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    props = context.scene.cp77_panel_props
    target_armature_name = props.selected_armature
    target_armature = bpy.data.objects.get(target_armature_name)
    
    obj = context.object
    if not obj:
        show_message("No active object. Please Select a Mesh and try again")
        return {'CANCELLED'}
    if not is_mesh(obj):  
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
            if modifier.type == 'ARMATURE':
                if modifier.object != target_armature:
                    modifier.object = target_armature
                retargeted = True
                break
        
        if not retargeted:
            armature = mesh.modifiers.new('Armature', 'ARMATURE')
            armature.object = target_armature
        
        if reparent:
            mesh.parent = target_armature
            # Move to collection
            for col in list(mesh.users_collection):
                col.objects.unlink(mesh)
            target_collection.objects.link(mesh)
    
    return {'FINISHED'}

# UV Checker material name constant
uv_checker_matname = 'UV_Checker'

def ensure_uv_checker_material():
    """ find or create the uv checker material instance."""
    if uv_checker_matname in bpy.data.materials:
        return bpy.data.materials[uv_checker_matname]
    
    resources_dir = get_resources_dir()
    image_path = os.path.join(resources_dir, "uvchecker.png")
    
    if not os.path.exists(image_path):
        show_message("UV checker image not found")
        return None
    
    image = bpy.data.images.load(image_path)
    
    # Create material
    uvchecker = bpy.data.materials.new(name=uv_checker_matname)
    uvchecker.use_nodes = True
    
    # Create texture node
    texture_node = uvchecker.node_tree.nodes.new(type='ShaderNodeTexImage')
    texture_node.location = (-200, 0)
    texture_node.image = image
    
    # Connect to shader
    shader_node = uvchecker.node_tree.nodes[loc("Principled BSDF")]
    uvchecker.node_tree.links.new(
        texture_node.outputs[loc('Color')], 
        shader_node.inputs[loc('Base Color')]
    )
    
    return uvchecker

def CP77UvChecker(self, context):
    """Apply UV checker material to meshes"""

    obj = context.object
    if not obj or not is_mesh(obj):
        show_message("No active mesh object. Please select a mesh and try again")
        return {'CANCELLED'}
    
    selected_meshes = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    if not selected_meshes:
        show_message("No meshes selected")
        return {'CANCELLED'}
    
    ensure_uv_checker_material()
    store_current_context()
    
    try:
        for mesh in selected_meshes:
            # Skip if it already has UV checker
            if any(mat and mat.name == uv_checker_matname for mat in mesh.material_slots):
                continue
            
            # Otherwise store the current material so we can restore it later
            if mesh.active_material:
                mesh['uvCheckedMat'] = mesh.active_material.name
            
            # Add UV checker material to the mesh
            mesh.data.materials.append(bpy.data.materials[uv_checker_matname])
            mat_index = mesh.data.materials.find(uv_checker_matname)
            
            if mat_index >= 0:
                mesh.active_material_index = mat_index
                
                # select faces and assign
                context.view_layer.objects.active = mesh
                safe_mode_switch('EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                
                # Assign material to selected faces
                bpy.ops.object.material_slot_assign()
                
                # Back to object mode and repeat for the next mesh
                safe_mode_switch('OBJECT')
        
        return {'FINISHED'}
    
    finally:
        # restore original context
        restore_previous_context()

def CP77UvUnChecker(self, context):
    """Remove UV checker material from a mesh"""

    obj = context.object
    if not obj or not is_mesh(obj):
        show_message("No active mesh object")
        return {'CANCELLED'}
    
    selected_meshes = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    store_current_context()
    
    try:
        for mesh in selected_meshes:
            if uv_checker_matname not in [m.name for m in mesh.data.materials if m]:
                continue
            
            original_mat_name = mesh.get('uvCheckedMat')
            material_index = mesh.data.materials.find(uv_checker_matname)
            
            # Restore original material if we have one
            if original_mat_name:
                original_index = mesh.data.materials.find(original_mat_name)
                
                if original_index >= 0:
                    mesh.active_material_index = original_index
                    
                    # Reassign the material to faces
                    context.view_layer.objects.active = mesh
                    safe_mode_switch('EDIT')
                    bpy.ops.mesh.select_all(action='SELECT')
                    bpy.ops.object.material_slot_assign()
                    safe_mode_switch('OBJECT')
                
                # Remove the custom property
                if 'uvCheckedMat' in mesh:
                    del mesh['uvCheckedMat']
            
            # Remove UV checker material
            if material_index >= 0:
                mesh.data.materials.pop(index=material_index)
        
        return {'FINISHED'}
    
    finally:
        restore_previous_context()

# Shape key helpers

def ensure_basis(obj):
    """Ensure basis shapekey exists."""
    if hasShapeKeys(obj):
        return obj.data.shape_keys.key_blocks[0]
    
    obj.shape_key_add(name="Basis", from_mix=False)
    return obj.data.shape_keys.key_blocks[0]

def unique_key_name(obj, base_name):
    """Generate unique shape key name."""
    existing = set(getShapeKeyNames(obj) or [])
    if base_name not in existing:
        return base_name
    i = 1
    while f"{base_name}.{i:03d}" in existing:
        i += 1
    return f"{base_name}.{i:03d}"

def remove_key(obj, name):
    """Remove a shape key by name."""
    key = getShapeKeyByName(obj, name)
    if key:
        obj.shape_key_remove(key)

def add_key_from_mix(obj, name, values=None):
    """Add shape key from mix."""
    if not hasShapeKeys(obj):
        basis = ensure_basis(obj)
    else:
        basis = obj.data.shape_keys.key_blocks[0]
    
    kb = obj.data.shape_keys.key_blocks
    new_name = unique_key_name(obj, name)
    new_key = obj.shape_key_add(name=new_name, from_mix=False)
    
    src_keys = list(kb)[1:]
    val_map = {k.name: (values.get(k.name, k.value) if values else k.value) for k in src_keys}
    
    n = len(basis.data)
    for i in range(n):
        bco = basis.data[i].co
        out = bco.copy()
        for k in src_keys:
            v = val_map.get(k.name, 0.0)
            if v != 0.0:
                out += (k.data[i].co - bco) * v
        new_key.data[i].co = out
    return new_key

def copy_key_to_basis(obj, src_name):
    """Copy a shape key to basis."""
    if not hasShapeKeys(obj):
        return False
    
    basis = obj.data.shape_keys.key_blocks[0]
    src = getShapeKeyByName(obj, src_name)
    
    if not src:
        return False
    
    if len(basis.data) != len(src.data):
        raise RuntimeError(f"Vertex count mismatch on {obj.name}")
    
    for i in range(len(basis.data)):
        basis.data[i].co = src.data[i].co
    return True

def apply_modifier_as_shapekey(obj, mod_name, keep_modifier=False):
    # don't use store/restore context functions here because they'll overwrite the more important main context
    view_layer = bpy.context.view_layer
    prev_active = view_layer.objects.active
    preselected = [o for o in view_layer.objects if o.select_get()]
    prev_mode = getattr(prev_active, "mode", None) if prev_active else None
    prev_hide_viewport = getattr(obj, "hide_viewport", False)
    prev_hide = obj.hide_get()
    
    # just to be extra sure we're in object mode
    safe_mode_switch('OBJECT')

    try:
        if prev_hide_viewport:
            obj.hide_viewport = False
        if prev_hide:
            obj.hide_set(False)

        for o in preselected:
            o.select_set(False)

        view_layer.objects.active = obj
        obj.select_set(True)

        result = bpy.ops.object.modifier_apply_as_shapekey(modifier=mod_name)
        if result != {'FINISHED'}:
            raise RuntimeError(f"Failed to apply '{mod_name}' on {obj.name}: {result}")

        if not keep_modifier and mod_name in obj.modifiers:
            obj.modifiers.remove(obj.modifiers[mod_name])

    finally:
        try:
            obj.hide_viewport = prev_hide_viewport
            obj.hide_set(prev_hide)
        except Exception:
            pass

        for o in view_layer.objects:
            o.select_set(False)
        for o in preselected:
            o.select_set(True)

        view_layer.objects.active = prev_active
        if prev_active and prev_mode and prev_mode != 'OBJECT':
            try:
                safe_mode_switch(prev_mode)
            except Exception:
                pass

# Refitter functions

def applyRefitter(obj):
    """Apply refitter"""
    ensure_basis(obj)
    
    names = getShapeKeyNames(obj) or []
    auto_names = [n for n in names if 'Autofitter' in n]
    garm_names = [n for n in names if 'Garment' in n]
    
    if auto_names:
        auto_values = {n: 1.0 for n in auto_names}
        temp_mix_key = add_key_from_mix(obj, 'TempAutofitMix', values=auto_values)
        
        if temp_mix_key:
            copy_key_to_basis(obj, temp_mix_key.name)
            remove_key(obj, temp_mix_key.name)
        
        for n in auto_names:
            remove_key(obj, n)
    
    gs_key = None
    if garm_names:
        garm_values = {n: 1.0 for n in garm_names}
        gs_key = add_key_from_mix(obj, 'GarmentSupport', values=garm_values)
        
        for n in garm_names:
            remove_key(obj, n)
    
    return gs_key.name if gs_key else None

def CP77RefitChecker(self, context):
    """Check for existing refitters."""
    refitters, addons = [], []
    for obj in context.scene.objects:
        if obj.type == 'LATTICE':
            if "refitter_type" in obj:
                refitters.append(obj)
            elif "refitter_addon" in obj or "refitter_addon_type" in obj:
                addons.append(obj)
    print(f'Refitters: {len(refitters)}, Addons: {len(addons)}')
    return refitters, addons

def CP77Refit(context, refitter, addon, target_body_path, target_body_name, 
              useAddon, addon_target_body_path, addon_target_body_name, fbx_rot, try_auto_apply):
    return autofitter(context, refitter, addon, target_body_path, useAddon, 
                      addon_target_body_path, addon_target_body_name, target_body_name, fbx_rot, try_auto_apply)

def autofitter(context, refitter, addon, target_body_path, useAddon, 
               addon_target_body_path, addon_target_body_name, target_body_name, fbx_rot, try_auto_apply):
    store_current_context()
    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
    if not selected_meshes:
        show_message("No meshes selected. Please select at least one mesh and try again.")
        return {'CANCELLED'}

    if 'Refitters' in context.scene.collection.children:
        r_c = context.scene.collection.children['Refitters']
    else:
        r_c = bpy.data.collections.new('Refitters')
        context.scene.collection.children.link(r_c)

    main_lattice = next((obj for obj in refitter if obj.get('refitter_type') == target_body_name), None)
    if not main_lattice and target_body_name and target_body_name != 'None':
        main_lattice = add_lattice(target_body_path, r_c, fbx_rot, target_body_name)
    
    addon_lattice = None
    if useAddon:
        addon_lattice = next((obj for obj in addon if obj.get('refitter_addon_type') == addon_target_body_name), None)
        if not addon_lattice and addon_target_body_path:
            addon_lattice = add_lattice(addon_target_body_path, r_c, fbx_rot, addon_target_body_name)
            if addon_lattice:
                addon_lattice["refitter_addon_type"] = addon_target_body_name

    meshes_modified_count = 0
    for mesh in selected_meshes:
        added_mods_names = []

        if main_lattice and not any(mod.type == 'LATTICE' and mod.object == main_lattice for mod in mesh.modifiers):
            mod = mesh.modifiers.new(main_lattice.name, 'LATTICE')
            mod.object = main_lattice
            print(f'Refitting: {mesh.name} to: {main_lattice["refitter_type"]}')
            added_mods_names.append(mod.name)
        
        if addon_lattice and not any(mod.type == 'LATTICE' and mod.object == addon_lattice for mod in mesh.modifiers):
            mod = mesh.modifiers.new(addon_lattice.name, 'LATTICE')
            mod.object = addon_lattice
            print(f'Using Refitter Addon: {addon_lattice.name}')
            added_mods_names.append(mod.name)
        
        if added_mods_names:
            meshes_modified_count += 1
            if try_auto_apply:
                for mod_name in added_mods_names:
                    apply_modifier_as_shapekey(mesh, mod_name)
                applyRefitter(mesh)

    if meshes_modified_count == 0:
        show_message("All selected meshes already have the requested modifiers.")
        return {'CANCELLED'}

    for obj in bpy.context.scene.objects:
        obj.select_set(False)
    for obj in selected_meshes:
        obj.select_set(True)
    context.view_layer.objects.active = selected_meshes[0]
    
    return {'FINISHED'}

def add_lattice(target_body_path, collection, fbx_rot, target_body_name):
    """Add lattice from .npz file."""
    lattice_name = f"{target_body_name}Autofitter"
    if lattice_name in collection.objects:
        print(f"{lattice_name} already exists")
        return collection.objects[lattice_name]
    
    print(f"Creating {lattice_name} from file '{target_body_path}'")
    refitter = load_lattice_npz(target_body_path, name=lattice_name, link_to_collection=collection)
    refitter["refitter_type"] = target_body_name
    
    if not fbx_rot:
        refitter.rotation_euler[2] += math.pi
    
    # Hide the lattice
    refitter.hide_viewport = True
    return refitter

def create_color_attributes(obj):
    """Create color attributes for garment support."""
    mesh = obj.data
    
    attrs = [
        ("_GARMENTSUPPORTWEIGHT", (1.0, 0.0, 0.0, 1.0)),
        ("_GARMENTSUPPORTCAP", (0.0, 0.0, 0.0, 1.0)),
    ]
    
    for name, color in attrs:
        if name in mesh.color_attributes:
            continue
        
        attr = mesh.color_attributes.new(
            name=name,
            domain='CORNER',
            type='BYTE_COLOR'
        )
        
        for i in range(len(attr.data)):
            attr.data[i].color = color

def add_shrinkwrap(context, target_collection_name, offset, wrap_method, 
                   as_garment_support=True, apply_immediately=True, vertex_group=None):
    """Add shrinkwrap"""
    
    # Get target mesh
    target_collection_children = get_collection_children(target_collection_name, "MESH")
    if not target_collection_children:
        show_message(f"Target collection '{target_collection_name}' not found.")
        return {'CANCELLED'}
    
    if len(target_collection_children) == 0:
        show_message(f"No meshes found in collection '{target_collection_name}'.")
        return {'CANCELLED'}
    
    target_mesh = target_collection_children[0]
    
    if len(target_collection_children) > 1:
        show_message(f"Target collection contains {len(target_collection_children)} meshes. Using first one.")
    
    selected_meshes = [obj for obj in context.selected_objects 
                      if obj.type == 'MESH' and obj != target_mesh]
    
    if not selected_meshes:
        show_message("No objects selected, or only the target mesh selected!")
        return {'CANCELLED'}
    
    shapekey_name = "GarmentSupport" if as_garment_support else "Shrinkwrap"
    
    # Store current context if we're applying
    if apply_immediately:
        store_current_context()
    
    try:
        # Switch to object mode if applying
        if apply_immediately and get_safe_mode() != 'OBJECT':
            safe_mode_switch('OBJECT')
        
        for obj in selected_meshes:
            # Add modifier
            shrinkwrap = obj.modifiers.new(name=shapekey_name, type='SHRINKWRAP')
            
            if vertex_group:
                if vertex_group not in obj.vertex_groups:
                    continue
                shrinkwrap.vertex_group = vertex_group
            
            if as_garment_support:
                create_color_attributes(obj)
                # Clear shape keys
                if hasShapeKeys(obj):
                    for key in reversed(obj.data.shape_keys.key_blocks):
                        obj.shape_key_remove(key)
            
            shrinkwrap.target = target_mesh
            shrinkwrap.wrap_method = wrap_method
            shrinkwrap.wrap_mode = 'ABOVE_SURFACE'
            shrinkwrap.offset = offset
            
            if not apply_immediately:
                continue
            
            # Apply modifier
            context.view_layer.objects.active = obj
            
            if not hasShapeKeys(obj):
                if as_garment_support:
                    bpy.ops.object.modifier_apply_as_shapekey(modifier=shrinkwrap.name)
                else:
                    bpy.ops.object.modifier_apply(modifier=shrinkwrap.name)
            elif as_garment_support:
                gs_key = getShapeKeyByName(obj, 'GarmentSupport')
                if gs_key:
                    obj.shape_key_remove(gs_key)
                bpy.ops.object.modifier_apply_as_shapekey(modifier=shrinkwrap.name)
            else:
                # Check for basis
                if not getShapeKeyByName(obj, 'Basis'):
                    bpy.ops.object.modifier_apply(modifier=shrinkwrap.name)
                else:
                    # Merge with basis
                    shrinkwrap.name = 'TEMP_MERGE'
                    bpy.ops.object.modifier_apply_as_shapekey(modifier=shrinkwrap.name)
                    
                    basis = obj.data.shape_keys.key_blocks['Basis']
                    temp = getShapeKeyByName(obj, 'TEMP_MERGE')
                    
                    for i, v in enumerate(basis.data):
                        v.co += (temp.data[i].co - basis.data[i].co)
                    
                    obj.shape_key_remove(temp)
        
        return {'FINISHED'}
    
    except Exception as e:
        show_message(f"Error: {str(e)}")
        return {'CANCELLED'}
    
    finally:
        if apply_immediately:
            restore_previous_context()

# Material storage for join/split
material_storage = defaultdict(dict)

def safe_join(self, context):
    """Safely join meshes for sculpting etc.."""
    
    selected_meshes = [
        obj for obj in context.selected_objects 
        if obj.type == 'MESH' and re.match(r'submesh_\d\d', obj.name)
    ]
    
    if not selected_meshes:
        self.report({'ERROR'}, "No valid submeshes selected")
        return {'CANCELLED'}
    
    # Store context
    store_current_context()
    
    try:
        # Store materials
        for obj in selected_meshes:
            material_storage[obj.name].clear()
            for i, slot in enumerate(obj.material_slots):
                if slot.material:
                    material_storage[obj.name][i] = slot.material.name
            
            # Create submesh material
            if obj.name not in bpy.data.materials:
                mat = bpy.data.materials.new(name=obj.name)
                mat.diffuse_color = (0.8, 0.8, 0.8, 1)
            
            # Clear and assign
            obj.data.materials.clear()
            obj.data.materials.append(bpy.data.materials[obj.name])
            
            # Assign to faces
            context.view_layer.objects.active = obj
            safe_mode_switch('EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            obj.active_material_index = 0
            bpy.ops.object.material_slot_assign()
            safe_mode_switch('OBJECT')
        
        # Join
        bpy.ops.object.select_all(action='DESELECT')
        for obj in selected_meshes:
            obj.select_set(True)
        context.view_layer.objects.active = selected_meshes[0]
        bpy.ops.object.join()
        
        return {'FINISHED'}
    
    finally:
        restore_previous_context()


def _restore_original_materials(self, obj):
    """Restore materials from storage."""
    stored_materials = material_storage.get(obj.name, {})
    
    max_slot = max(stored_materials.keys(), default=-1) + 1
    while len(obj.data.materials) < max_slot:
        obj.data.materials.append(None)
    
    for slot_idx, mat_name in stored_materials.items():
        if mat_name in bpy.data.materials:
            obj.data.materials[slot_idx] = bpy.data.materials[mat_name]


def safe_split(self, context):
    """Safely split meshes that were joined with safe_join"""
    
    obj = context.active_object
    if not obj or not is_mesh(obj):
        show_message("No mesh selected")
        return {'CANCELLED'}
    
    # Store context
    store_current_context()
    
    try:
        # Split by material
        safe_mode_switch('EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.separate(type='MATERIAL')
        safe_mode_switch('OBJECT')
        
        # Process split objects
        new_objects = list(context.selected_objects)
        
        for new_obj in new_objects:
            # Rename to material
            if new_obj.data.materials and new_obj.data.materials[0]:
                new_obj.name = new_obj.data.materials[0].name
            
            # Clear and restore
            new_obj.data.materials.clear()
            if new_obj.name in material_storage:
                _restore_original_materials(self, new_obj)
        
        return {'FINISHED'}
    
    finally:
        restore_previous_context()