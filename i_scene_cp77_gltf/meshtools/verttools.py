import bpy
import bpy.utils.previews
import os
import math
import json
from ..main.common import  (get_resources_dir, get_script_dir, show_message)
from bpy.props import (StringProperty, EnumProperty, FloatVectorProperty)
from ..cyber_props import *


res_dir = get_resources_dir()

def del_empty_vgroup(self, context):
    obj = context.object
    if not obj:
        show_message("No active object. Please Select a Mesh and try again")
        return {'CANCELLED'}
    if obj.type != 'MESH':
        show_message("The active object is not a mesh.")
        return {'CANCELLED'}
    try:
        for obj in bpy.context.selected_objects:
            groups = {r: 0 for r in range(len(obj.vertex_groups))}
            for vert in obj.data.vertices:
                for vg in vert.groups:
                    i = vg.group
                    if i in groups: del groups[i]
            for i in sorted(groups.keys(), reverse=True):
                obj.vertex_groups.remove(obj.vertex_groups[i])
    except Exception as e:
        print(f"encountered the following error:")
        print(e)

def find_nearest_vertex_group(obj, vertex):
    min_distance = math.inf
    nearest_vertex = None
    if not obj:
        show_message("No active object. Please Select a Mesh and try again")
        return {'CANCELLED'}
    if obj.type != 'MESH':
        show_message("The active object is not a mesh.")
        return {'CANCELLED'}
    for v in obj.data.vertices:
        if v.groups:
            distance = (v.co - vertex.co).length
            if distance < min_distance:
                min_distance = distance
                nearest_vertex = v
    return nearest_vertex

def CP77GroupUngroupedVerts(self, context):
    C = bpy.context
    obj = C.object
    current_mode = C.mode
    if not obj:
        show_message("No active object. Please Select a Mesh and try again")
        return {'CANCELLED'}
    if obj.type != 'MESH':
        show_message("The active object is not a mesh.")
        return {'CANCELLED'}
    else:
        if current_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        ungrouped_vertices = [v for v in obj.data.vertices if not v.groups]

        if ungrouped_vertices:
            try:
                for v in ungrouped_vertices:
                    nearest_vertex = find_nearest_vertex_group(obj, v)
                    if nearest_vertex:
                        for g in nearest_vertex.groups:
                            group_name = obj.vertex_groups[g.group].name
                            vertex_weight = obj.vertex_groups[g.group].weight(nearest_vertex.index)
                            obj.vertex_groups[group_name].add([v.index], vertex_weight, 'ADD')
            except Exception as e:
                print(e)

        # Return to the mode the user was in edit_mesh was giving me a lot of trouble and is probably
        # the most common it will be here so special handling for it
        if C.mode != current_mode:
            try:
                if current_mode == 'EDIT_MESH':
                    bpy.ops.object.mode_set(mode='EDIT')
                else:
                    bpy.ops.object.mode_set(mode=current_mode)
            except Exception as e:
                print(e)
    return {'FINISHED'}

def trans_weights(self, context, vertInterop):
    current_mode = context.mode
    props = context.scene.cp77_panel_props
    source_mesh = bpy.data.collections.get(props.mesh_source)
    target_mesh = bpy.data.collections.get(props.mesh_target)
    active_objs = context.selected_objects

    if source_mesh and target_mesh:
        if current_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        bpy.ops.object.select_all(action='DESELECT')

        for source_obj in source_mesh.objects:
            source_obj.select_set(True)

        context.view_layer.objects.active = source_mesh.objects[-1]

        for target_obj in target_mesh.objects:
            target_obj.select_set(True)

        bpy.ops.object.data_transfer(
            use_reverse_transfer=False,
            vert_mapping='POLYINTERP_NEAREST',
            data_type='VGROUP_WEIGHTS',
            layers_select_dst='NAME',
            layers_select_src='ALL'
        )
        bpy.ops.object.select_all(action='DESELECT')
        context.view_layer.objects.active = None

    for obj in active_objs:
        obj.select_set(True)
        context.view_layer.objects.active = obj

    if context.mode != current_mode:
        mode_map = {
            'PAINT_WEIGHT': 'WEIGHT_PAINT',
            'EDIT_MESH': 'EDIT',
            'PAINT_VERTEX': 'VERTEX_PAINT'
        }
        bpy.ops.object.mode_set(mode=mode_map.get(current_mode, current_mode))