import os

import bpy

from ...blender.context import restore_previous_context, safe_mode_switch, store_current_context
from ...blender.mesh import is_mesh
from ..model import MeshToolResult
from ...paths import get_resources_dir


UV_CHECKER_MATERIAL = "UV_Checker"


def ensure_uv_checker_material():
    """ find or create the uv checker material instance."""
    if UV_CHECKER_MATERIAL in bpy.data.materials:
        return bpy.data.materials[UV_CHECKER_MATERIAL]

    resources_dir = get_resources_dir()
    image_path = os.path.join(resources_dir, "uvchecker.png")

    if not os.path.exists(image_path):
        return None

    image = bpy.data.images.load(image_path)

    # Create material
    uvchecker = bpy.data.materials.new(name=UV_CHECKER_MATERIAL)
    uvchecker.use_nodes = True

    # Create texture node
    texture_node = uvchecker.node_tree.nodes.new(type='ShaderNodeTexImage')
    texture_node.location = (-200, 0)
    texture_node.image = image

    # Connect to shader
    shader_node = uvchecker.node_tree.nodes.get("Principled BSDF")
    color_output = texture_node.outputs.get("Color")
    base_color_input = shader_node.inputs.get("Base Color") if shader_node else None
    if color_output is None or base_color_input is None:
        bpy.data.materials.remove(uvchecker)
        return None
    uvchecker.node_tree.links.new(color_output, base_color_input)

    return uvchecker


def apply_uv_checker(context):
    """Apply UV checker material to meshes"""

    obj = context.object
    if not obj or not is_mesh(obj):
        return MeshToolResult.failure("No active mesh object. Please select a mesh and try again.")

    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
    if not selected_meshes:
        return MeshToolResult.failure("No meshes selected.")

    material = ensure_uv_checker_material()
    if material is None:
        return MeshToolResult.failure("UV checker image could not be loaded.")
    store_current_context()

    try:
        for mesh in selected_meshes:
            # Skip if it already has UV checker
            if any(mat and mat.name == UV_CHECKER_MATERIAL for mat in mesh.material_slots):
                continue

            # Otherwise store the current material so we can restore it later
            if mesh.active_material:
                mesh['uvCheckedMat'] = mesh.active_material.name

            # Add UV checker material to the mesh
            mesh.data.materials.append(material)
            mat_index = mesh.data.materials.find(UV_CHECKER_MATERIAL)

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

        return MeshToolResult.success(f"Applied UV checker to {len(selected_meshes)} mesh(es).")

    finally:
        # restore original context
        restore_previous_context()


def remove_uv_checker(context):
    """Remove UV checker material from a mesh"""

    obj = context.object
    if not obj or not is_mesh(obj):
        return MeshToolResult.failure("No active mesh object.")

    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
    store_current_context()

    try:
        for mesh in selected_meshes:
            if UV_CHECKER_MATERIAL not in [m.name for m in mesh.data.materials if m]:
                continue

            original_mat_name = mesh.get('uvCheckedMat')
            material_index = mesh.data.materials.find(UV_CHECKER_MATERIAL)

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

        return MeshToolResult.success(f"Removed UV checker from {len(selected_meshes)} mesh(es).")

    finally:
        restore_previous_context()
