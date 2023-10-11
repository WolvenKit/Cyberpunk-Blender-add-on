import bpy
import math
import os

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

    bpy.ops.cp77.message_box('INVOKE_DEFAULT', message="Assigned {len(unassigned_vertices)} unassigned vertices.")



def trans_weights(self, context):
        source_mesh_name = context.scene.mesh_source
        target_mesh_name = context.scene.mesh_target
        source_obj = bpy.data.objects.get(source_mesh_name)
        target_obj = bpy.data.objects.get(target_mesh_name)
        original_object_mode = source_obj.mode

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
    existing_material = bpy.data.materials.get("UV_Checker")
    if existing_material is not None:
        uvchecker = existing_material
    else:
        plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        resources_dir = os.path.join(plugin_dir, "resources")
        image_path = os.path.join(resources_dir, "uvchecker.png")
        # Load the image texture
        image = bpy.data.images.load(image_path)
        # Create a new material if it doesn't exist
        uvchecker = bpy.data.materials.new(name="UV_Checker")
        uvchecker.use_nodes = True
        # Create a new texture node
        texture_node = uvchecker.node_tree.nodes.new(type='ShaderNodeTexImage')
        texture_node.location = (-200, 0)
        texture_node.image = image
        # Connect the texture node to the shader node
        shader_node = uvchecker.node_tree.nodes["Principled BSDF"]
        uvchecker.node_tree.links.new(texture_node.outputs['Color'], shader_node.inputs['Base Color'])
    # Apply the material to selected objects without replacing existing materials
    selected_objects = context.selected_objects
    for obj in selected_objects:
        if obj.type == 'MESH':
            if len(obj.material_slots) == 0:
                obj.data.materials.append(uvchecker)
            else:
                obj.material_slots[0].material = uvchecker  # Use the first material slot
    # Update the UI to reflect the changes
    bpy.context.view_layer.update()
    return {'FINISHED'}

# def cp77riglist(context):
#     cp77rigs = []
#     plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#     resources_dir = os.path.join(plugin_dir, "resources")
    
#     man_base = os.path.join(resources_dir, "man_base_full.glb")
#     woman_base = os.path.join(resources_dir, "woman_base_full.glb")
#     man_big = os.path.join(resources_dir, "man_big_full.glb")
#     man_fat = os.path.join(resources_dir, "man_fat_full.glb")
#     Rhino = os.path.join(resources_dir, "rhino_full.glb")
#     Judy = os.path.join(resources_dir, "Judy_full.glb")
#     Panam = os.path.join(resources_dir, "Panam_full.glb")
    
#     cp77rigs.append(man_base)
#     cp77rigs.append(woman_base)
#     cp77rigs.append(man_big)
#     cp77rigs.append(man_fat)
#     cp77rigs.append(Rhino)
#     return cp77rigs
