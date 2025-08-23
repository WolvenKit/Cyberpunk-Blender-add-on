import bpy
import bpy.utils.previews
import os
import math
import re
import traceback
import json
from ..main.common import  (get_resources_dir, get_script_dir, show_message)
from ..main.bartmoss_functions import get_safe_mode, safe_mode_switch, restore_previous_context
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
    """
    Transfer vertex-group weights between two collections chosen in scene.cp77_panel_props.

      - If both collections are from cyberpunk (named like 'submesh_XX' naming -> pair by index (LOD ignored).
      - Otherwise -> ordered pairing (1→1, 2→2, ...).
      - Special-cases:
          * one source, many targets -> source → all targets
          * many sources, one target -> each source → that one target (last wins)
    """
    props = context.scene.cp77_panel_props
    src_col = bpy.data.collections.get(props.mesh_source)
    tgt_col = bpy.data.collections.get(props.mesh_target)

    sources = [o for o in src_col.objects if o.type == 'MESH']
    targets = [o for o in tgt_col.objects if o.type == 'MESH']

    if not sources or not targets:
        show_message("Both collections must contain at least one mesh.")
        return {'CANCELLED'}

    # Save user context and switch to OBJECT safely
    original_mode = get_safe_mode()
    original_active = context.view_layer.objects.active
    original_selection = list(context.selected_objects)

    if original_mode != 'OBJECT':
        safe_mode_switch('OBJECT')

    # Mapping toggle
    vert_mapping = 'POLYINTERP_NEAREST' if bool(vertInterop) else 'NEAREST'

    # Submesh parser
    submesh_rx = re.compile(r'^submesh_(\d+)(?:_LOD_(\d+))?$', re.IGNORECASE)
    def parse_submesh(name: str):
        """Return (index:int, lod:int|None) for 'submesh_00_LOD_1', else (None, None)."""
        m = submesh_rx.match(name)
        if not m:
            return None, None
        idx = int(m.group(1))
        lod = int(m.group(2)) if m.group(2) is not None else None
        return idx, lod

    src_all_submesh = all(parse_submesh(o.name)[0] is not None for o in sources)
    tgt_all_submesh = all(parse_submesh(o.name)[0] is not None for o in targets)

    # Build (source, [targets...]) pairs
    pairs = []

    if len(sources) == 1 and len(targets) >= 1:
        pairs.append((sources[0], list(targets)))  # single → all
    elif len(targets) == 1 and len(sources) >= 1:
        for s in sources:                          # each source → single
            pairs.append((s, [targets[0]]))
    else:
        if src_all_submesh and tgt_all_submesh:
            # Pair by submesh index (LOD ignored)
            src_by_idx = {}
            for s in sources:
                idx, _ = parse_submesh(s.name)
                if idx is not None and idx not in src_by_idx:
                    src_by_idx[idx] = s
            tgt_by_idx = {}
            for t in targets:
                idx, _ = parse_submesh(t.name)
                if idx is not None:
                    tgt_by_idx.setdefault(idx, []).append(t)
            for idx in sorted(tgt_by_idx.keys()):
                s = src_by_idx.get(idx)
                if s:
                    pairs.append((s, tgt_by_idx[idx]))
            # indices without a matching source are skipped (simple, predictable)
        else:
            # Ordered pairing: 1→1, 2→2, extras ignored
            for s, t in zip(sources, targets):
                pairs.append((s, [t]))

    # Execute transfers
    passes = 0
    errors = []

    try:
        bpy.ops.object.select_all(action='DESELECT')
    except Exception:
        pass

    for s, t_list in pairs:
        try:
            bpy.ops.object.select_all(action='DESELECT')
        except Exception:
            pass

        for t in t_list:
            t.select_set(True)

        try:
            context.view_layer.objects.active = s
            s.select_set(True)

            bpy.ops.object.data_transfer(
                use_reverse_transfer=False,          # ACTIVE (source) → SELECTED (targets)
                use_object_transform=True,
                vert_mapping=vert_mapping,
                data_type='VGROUP_WEIGHTS',
                layers_select_src='ALL',
                layers_select_dst='NAME',
                mix_mode='REPLACE',                  # last pass wins
                mix_factor=1.0
            )
            passes += 1
        except Exception as e:
            errors.append(f"{s.name}: {e}")
        finally:
            s.select_set(False)   # targets selection reset next loop

    # Restore selection/active and original mode
    try:
        bpy.ops.object.select_all(action='DESELECT')
        for ob in original_selection:
            if ob and ob.name in bpy.data.objects:
                ob.select_set(True)
        context.view_layer.objects.active = original_active
    except Exception:
        pass

    if original_mode != 'OBJECT':
        safe_mode_switch(original_mode)

    # Feedback
    if errors:
        show_message(f"Weights transferred ({passes} pass(es)). Errors: {'; '.join(errors[:3])}{'...' if len(errors) > 3 else ''}")
    else:
        if src_all_submesh and tgt_all_submesh and len(sources) > 1 and len(targets) > 1:
            show_message(f"Weights transferred by submesh index across {passes} pass(es).")
        else:
            show_message(f"Weights transferred in order across {passes} pass(es).")

    return {'FINISHED'}
