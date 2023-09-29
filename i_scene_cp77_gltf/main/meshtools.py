import bpy
import math


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