import bpy
from collections import defaultdict
import re
import os
from .verttools import *
from ..cyber_props import *
from ..main.common import loc, show_message, get_collection_children
from ..main.bartmoss_functions import get_safe_mode, safe_mode_switch
from ..main.npz_io import load_lattice_npz, save_lattice_npz

def CP77SubPrep(self, context, smooth_factor: float, merge_distance: float):
    angle_deg = max(0.0, min(180.0, float(smooth_factor)))
    original_mode = get_safe_mode()
    if original_mode != 'OBJECT':
        safe_mode_switch('OBJECT')

    targets = [ob for ob in context.selected_objects if ob.type == 'MESH']
    if not targets:
        show_message("Select one or more meshes.")
        if original_mode != 'OBJECT':
            safe_mode_switch(original_mode)
        return {'CANCELLED'}

    merged_total = 0
    for ob in targets:
        me = ob.data
        # avoid modifying other objects that share this mesh
        if me.users > 1:
            ob.data = me = me.copy()

        # shape-key safety
        do_merge = merge_distance > 0.0 and not (getattr(me, "shape_keys", None) and me.shape_keys.key_blocks)

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
    bpy.ops.object.shade_auto_smooth(use_auto_smooth=True, angle=radians(angle_deg))
    context.view_layer.objects.active = active_backup

    show_message(f"Submesh preparation complete. {merged_total} verts merged across {len(targets)} object(s).")
    if original_mode != 'OBJECT':
        safe_mode_switch(original_mode)
    return {'FINISHED'}

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

def keyblocks(obj):
    sk = obj.data.shape_keys
    return sk.key_blocks if sk else None

def ensure_basis(obj):
    kb = keyblocks(obj)
    if kb:
        return kb[0]
    bpy.ops.object.shape_key_add(from_mix=False)
    return obj.data.shape_keys.key_blocks[0]

def get_shape_key_names(obj):
    kb = keyblocks(obj)
    return [k.name for k in kb] if kb else []

def set_active_shape_key(obj, name):
    kb = keyblocks(obj)
    if not kb or name not in kb:
        return None
    obj.active_shape_key_index = list(kb).index(kb[name])
    return kb[name]

def unique_key_name(obj, base_name):
    existing = set(get_shape_key_names(obj))
    if base_name not in existing:
        return base_name
    i = 1
    while True:
        cand = f"{base_name}.{i:03d}"
        if cand not in existing:
            return cand
        i += 1

def remove_key(obj, name):
    kb = keyblocks(obj)
    if not kb or name not in kb:
        return
    obj.shape_key_remove(kb[name])

def add_key_from_mix(obj, name, values=None):
    kb = keyblocks(obj)
    if not kb:
        basis = ensure_basis(obj)
        kb = keyblocks(obj)
    else:
        basis = kb[0]

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
    kb = keyblocks(obj)
    if not kb or src_name not in kb:
        return False
    basis = kb[0]
    src = kb[src_name]
    if len(basis.data) != len(src.data):
        raise RuntimeError(f"Vertex count mismatch on {obj.name} for '{src_name}'")
    for i in range(len(basis.data)):
        basis.data[i].co = src.data[i].co
    return True

def apply_modifier_as_shapekey(obj, mod_name, keep_modifier=False):
    view_layer = bpy.context.view_layer
    prev_active = view_layer.objects.active
    preselected = [o for o in view_layer.objects if o.select_get()]
    prev_mode = getattr(prev_active, "mode", None) if prev_active else None
    prev_hide_viewport = getattr(obj, "hide_viewport", False)
    prev_hide = obj.hide_get()

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
                bpy.ops.object.mode_set(mode=prev_mode)
            except Exception:
                pass

def applyRefitter(obj):
    ensure_basis(obj)

    names = get_shape_key_names(obj)
    auto_names = [n for n in names if 'Autofitter' in n]
    garm_names = [n for n in names if 'Garment' in n]

    values = {}
    for n in auto_names + garm_names:
        values[n] = 1.0

    gs_key = add_key_from_mix(obj, 'GarmentSupport', values=values)

    for n in garm_names:
        remove_key(obj, n)

    if auto_names:
        # bake first autofitter into Basis
        baked = auto_names[0]
        if copy_key_to_basis(obj, baked):
            remove_key(obj, baked)

    return gs_key.name if gs_key else None

def CP77RefitChecker(self, context):
    scene = context.scene
    objects = scene.objects
    refitter = []
    addon = []
    for obj in objects:
        if obj.type =='LATTICE':
            if "refitter_type" in obj:
                refitter.append(obj)
            if "refitter_addon" in obj:
                addon.append(obj)
    print(f'refitter result: {refitter} refitter addon: {addon}')
    return refitter, addon

def CP77Refit(context, refitter, addon, target_body_path, target_body_name, useAddon, addon_target_body_path, addon_target_body_name, fbx_rot, try_auto_apply):
    autofitter(context, refitter, addon, target_body_path, useAddon, addon_target_body_path, addon_target_body_name, target_body_name, fbx_rot, try_auto_apply)

def autofitter(context, refitter, addon, target_body_path, useAddon, addon_target_body_path, addon_target_body_name, target_body_name, fbx_rot, try_auto_apply):
    scene = context.scene
    refitter_obj = None
    addon_obj = None
    r_c = None

    if target_body_name == 'None' and addon_target_body_name is not None:
        target_body_name = addon_target_body_name
        target_body_path = addon_target_body_path
        useAddon = False


    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
    if not selected_meshes:
        show_message("No meshes selected. Please select at least one mesh and try again.")
        return {'CANCELLED'}

    if refitter:
        for obj in refitter:
            if obj.get('refitter_type') == target_body_name:
                print(f"{obj['refitter_type']} refitter found")
                refitter_obj = obj
                break

        if refitter_obj:
            print(f"Refitter found: {refitter_obj.name} (type: {refitter_obj['refitter_type']})")
            selected_meshes = [
                mesh for mesh in selected_meshes
                if not any(
                    modifier.type == 'LATTICE' and modifier.object == refitter_obj
                    for modifier in mesh.modifiers)]
    if useAddon:
        if addon:
            for obj in addon:
                if obj.get('refitter_addon_type') == addon_target_body_name:
                    print(f"{obj['refitter_addon_type']} refitter addon found")
                    addon_obj = obj
                    break

            if addon_obj:
                print(f"Refitter addon found: {addon_obj.name} (type: {addon_obj['refitter_addon_type']})")
                selected_meshes = [
                    mesh for mesh in selected_meshes
                    if not any(
                        modifier.type == 'LATTICE' and modifier.object == addon_obj
                        for modifier in mesh.modifiers
                    )
                ]

    if not selected_meshes:
        show_message("No mesh needs refitting. Please select at least one mesh and try again.")
        return {'CANCELLED'}

    r_c = next((c for c in scene.collection.children if c.name == 'Refitters'), None)
    if r_c is None:
        r_c = bpy.data.collections.new('Refitters')
        scene.collection.children.link(r_c)

    new_lattice = add_lattice(target_body_path, r_c, fbx_rot, target_body_name)

    for mesh in selected_meshes:
        lattice_modifier = mesh.modifiers.new(new_lattice.name,'LATTICE')
        print(f'refitting: {mesh.name} to: {new_lattice["refitter_type"]}')

        if useAddon:
            new_lattice = add_lattice(addon_target_body_path, r_c, fbx_rot, addon_target_body_name)
            lattice_modifier.object = new_lattice

        lattice_modifier.object = new_lattice

        if try_auto_apply:
            applyRefitter(mesh)

    for mesh in selected_meshes:
        mesh.select_set(True)

def add_lattice(target_body_path, collection, fbx_rot, target_body_name):
    """re-use previous lattice, or add a new one if there isn't one"""
    for refitter in collection.objects:
        if refitter.name == f"{target_body_name}Autofitter":
            print(f"{target_body_name}Autofitter already exists")
            return refitter

    print(f"Creating {target_body_name}Autofitter from file '{target_body_path}'")
    refitter = load_lattice_npz(target_body_path, name=f"{target_body_name}Autofitter", link_to_collection=collection)
    refitter["refitter_type"] = target_body_name

    if fbx_rot:
        refitter.rotation_euler[2] += math.pi

    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = refitter
    refitter.select_set(True)

    bpy.context.object.hide_viewport = True

    return refitter

def _legacy_add_lattice(target_body_path, r_c, fbx_rot, target_body_name):
    """old method to load a '.json in a .zip' lattice refitter"""
    for refitter in r_c.objects:
        if refitter.name == f"{target_body_name}Autofitter":
            print(f"{target_body_name}Autofitter already exists")
            return refitter

    print(f"Creating {target_body_name}Autofitter from json file (reading {target_body_path})")
    from ..jsontool import JSONTool
    # Get the JSON file path for the selected target_body
    lattice_object_name, control_points, lattice_points, lattice_object_location, lattice_object_rotation, lattice_object_scale, lattice_interpolation_u, lattice_interpolation_v, lattice_interpolation_w  = JSONTool.jsonload(target_body_path)
    bpy.ops.object.add(type='LATTICE', enter_editmode=False, location=(0, 0, 0))
    new_lattice = bpy.context.object
    new_lattice.name = lattice_object_name
    new_lattice["refitter_type"] = target_body_name
    lattice = new_lattice.data
    try:
        r_c.objects.link(new_lattice)
        bpy.context.collection.objects.unlink(new_lattice)
    except RuntimeError:
        pass # Ignore error if the object is already in the collection

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

    return new_lattice

def convert_legacy_lattice(filepath):
    """Convert a legacy .zip lattice file to a new format."""
    lattice = _legacy_add_lattice(filepath, bpy.context.collection, False, "Legacy")
    save_lattice_npz(lattice, filepath.replace(".zip", ".npz"))
    bpy.data.objects.remove(lattice, do_unlink=True)

def create_color_attributes(obj):
    mesh = obj.data

    # Attribute settings
    attrs = [
        ("_GARMENTSUPPORTWEIGHT", (1.0, 0.0, 0.0, 1.0)),    # RGBA (full red, float)
        ("_GARMENTSUPPORTCAP", (0.0, 0.0, 0.0, 1.0)),       # RGBA (full black, float)
    ]

    for name, color in attrs:
        if name in mesh.color_attributes:
            continue

        mesh.color_attributes.new(
            name=name,
            domain='CORNER',           # Face corner domain
            type='BYTE_COLOR'          # Byte color
        )
        attr = mesh.color_attributes[name]
        # Set all values (loops = face corners)
        for i in range(len(attr.data)):
            attr.data[i].color = color


def add_shrinkwrap(context, target_collection_name, offset, wrap_method, as_garment_support=True, apply_immediately=True):
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
    shapekey_name = "GarmentSupport" if as_garment_support else "Shrinkwrap"

    try:
        # Remember current mode and switch to OBJECT mode
        if current_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        for obj in selected_meshes:
            if as_garment_support:
                create_color_attributes(obj)
                bpy.ops.object.mode_set(mode='OBJECT')
                # Remove existing 'GarmentSupport' shape key if it exists
                if obj.data.shape_keys:
                    for shape_key in reversed(obj.data.shape_keys.key_blocks):
                        obj.shape_key_remove(shape_key)

            # Add shrinkwrap modifier
            shrinkwrap = obj.modifiers.new(name=shapekey_name, type='SHRINKWRAP')
            shrinkwrap.target = target_mesh
            shrinkwrap.wrap_method = wrap_method
            shrinkwrap.wrap_mode = 'ABOVE_SURFACE'
            shrinkwrap.offset = offset

            if not apply_immediately:
                continue

            bpy.context.view_layer.objects.active = obj  # Set active object

            # Check if shape keys exist
            has_shape_keys = obj.data.shape_keys is not None

            if not has_shape_keys:
                if as_garment_support:
                    # Create new GarmentSupport shape key
                    bpy.ops.object.modifier_apply_as_shapekey(modifier=shrinkwrap.name)
                else:
                    # Apply modifier directly to mesh
                    bpy.ops.object.modifier_apply(modifier=shrinkwrap.name)
                continue

            # Replace or create GarmentSupport shapekey
            if as_garment_support:
                if 'GarmentSupport' in obj.data.shape_keys.key_blocks:
                    obj.shape_key_remove(obj.data.shape_keys.key_blocks['GarmentSupport'])
                bpy.ops.object.modifier_apply_as_shapekey(modifier=shrinkwrap.name)
                continue

            if 'Basis' not in obj.data.shape_keys.key_blocks:
                # No Basis shape key - apply modifier normally
                bpy.ops.object.modifier_apply(modifier=shrinkwrap.name)
                continue

            # Merge with existing Basis shape key

            # Apply modifier as temporary shape key
            shrinkwrap.name = 'TEMP_MERGE'
            bpy.ops.object.modifier_apply_as_shapekey(modifier=shrinkwrap.name)

            # Get references to shape keys
            basis = obj.data.shape_keys.key_blocks['Basis']
            temp = obj.data.shape_keys.key_blocks['TEMP_MERGE']

            # Apply changes to Basis
            for i, v in enumerate(basis.data):
                v.co += (temp.data[i].co - basis.data[i].co)

            # Remove temporary shape key
            obj.shape_key_remove(temp)

    except Exception as e:
        # delete the modifier if an error occurred
        if "GarmentSupport" in obj.modifiers:
            obj.modifiers.remove(obj.modifiers["GarmentSupport"])
        show_message("An error occurred while creating garment support: " + str(e))
        raise e
        return {'CANCELLED'}
    finally:
        # Switch back to original mode
        try:
            if  context.mode != current_mode:
                bpy.ops.object.mode_set(mode=current_mode)
        except Exception:
            pass

    return {'FINISHED'}

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
