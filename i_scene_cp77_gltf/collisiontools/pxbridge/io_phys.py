import bpy
import json
import base64
import sys
import os
from datetime import datetime, timezone
from mathutils import Vector
from . import physx_utils, viz


def get_physx_shape_type_mapping(physx_type):
    mapping = {
        'BOX': 'physicsColliderBox',
        'SPHERE': 'physicsColliderSphere',
        'CAPSULE': 'physicsColliderCapsule',
        'CONVEX': 'physicsColliderConvex',
        'TRIANGLE': 'physicsColliderMesh',
        'HEIGHTFIELD': 'physicsColliderMesh'
    }
    return mapping.get(physx_type, 'physicsColliderBox')


def extract_convex_verts_from_cooked(cooked_data):
    """ Extract vertex positions from PhysX cooked data """
    try:
        from . import pxbridge as _bridge
        raw_data = base64.b64decode(cooked_data.encode('ascii'))
        geom_data = _bridge.get_cooked_geometry('CONVEX', raw_data)
        vertices = []
        verts_flat = geom_data.get('vertices', [])
        for i in range(0, len(verts_flat), 3):
            vertices.append(
                {
                    "$type": "Vector3",
                    "X": verts_flat[i],
                    "Y": verts_flat[i + 1],
                    "Z": verts_flat[i + 2]
                }
            )
        return vertices
    except Exception as e:
        print(f"Warning: Could not extract convex vertices: {e}")
        return []


def import_collider_as_actor(obj, shape_type, shape_data, physmat, local_pos, local_rot, context):
    """
    Creates a PhysX shape on the given object based on CP77 collider data.
    Registers the object as a scene actor if not already registered.
    """
    px = obj.physx
    
    # Register as actor if not already
    is_registered = False
    for item in context.scene.physx.actors:
        if item.obj_ref == obj:
            is_registered = True
            break
            
    if not is_registered:
        px.actor_type = 'STATIC'
        new_item = context.scene.physx.actors.add()
        new_item.obj_ref = obj
        context.scene.physx.actor_list_index = len(context.scene.physx.actors) - 1
        
    shape_item = px.shapes.add()
    
    s_type_raw = shape_type
    shape_item.name = s_type_raw.replace('physicsCollider', '')
    
    shape_item.local_pos = local_pos
    shape_item.local_rot = local_rot
    shape_item.physics_material = physmat
    shape_item.collision_preset = "None"
    
    if s_type_raw == 'physicsColliderBox':
        shape_item.shape_type = 'BOX'
        extents = shape_data
        shape_item.dim_x = float(extents.get('X', 0.5))
        shape_item.dim_y = float(extents.get('Y', 0.5))
        shape_item.dim_z = float(extents.get('Z', 0.5))
        
    elif s_type_raw == 'physicsColliderSphere':
        shape_item.shape_type = 'SPHERE'
        shape_item.dim_x = float(shape_data)
        
    elif s_type_raw == 'physicsColliderCapsule':
        shape_item.shape_type = 'CAPSULE'
        shape_item.dim_x = float(shape_data.get('radius', 0.5))
        shape_item.dim_y = float(shape_data.get('height', 1.0)) / 2.0
        
    elif s_type_raw == 'physicsColliderConvex':
        shape_item.shape_type = 'CONVEX'
        raw_verts = shape_data
        shape_points = []
        for v in raw_verts:
            shape_points.extend([float(v.get('X', 0)), float(v.get('Y', 0)), float(v.get('Z', 0))])
            
        try:
            from . import pxbridge as _bridge
            if _bridge and shape_points:
                cooked = _bridge.cook_mesh("CONVEX", shape_points, [], 256)
                if cooked:
                    shape_item.cooked_data = base64.b64encode(cooked).decode('ascii')
                    shape_item.is_cooked = True
                    shape_item.name += " (Cooked)"
                else:
                    shape_item.name += " (Raw)"
        except Exception as e:
            print(f"Failed to cook: {e}")
            shape_item.name += " (Failed)"
            
    viz.invalidate_visualization_cache()
    return shape_item


def export_actor_item_to_phys(actor_item, filepath):
    presets_lib = physx_utils.presets_lib

    if not actor_item or not actor_item.obj_ref:
        print("ERROR: Invalid actor item")
        return False

    obj_ref = actor_item.obj_ref
    if not hasattr(obj_ref, 'physx'):
        print("ERROR: Object has no PhysX properties")
        return False

    px_obj = obj_ref.physx

    total_mass = px_obj.mass
    inertia = Vector(px_obj.inertia)
    com = Vector(px_obj.com_offset)

    sim_type = "Static"
    if px_obj.actor_type == 'DYNAMIC':
        sim_type = "Dynamic"
    elif px_obj.actor_type == 'KINEMATIC':
        sim_type = "Kinematic"

    colliders = []
    current_handle = 1

    col_layer_offset = len(presets_lib.COLLISION_LAYERS)

    for shape in px_obj.shapes:
        preset_name = shape.collision_preset if shape.collision_preset else "World Static"
        mat_name = shape.physics_material if shape.physics_material else 'Default'
        if mat_name.lower().endswith('.physmat'): mat_name = "None"

        sim_group = 0
        sim_target_mask = 0
        query_mask = 0

        found_preset = False
        if preset_name in presets_lib.COLLISION_PRESETS:
            data = presets_lib.COLLISION_PRESETS[preset_name]
            for layer in data[0]:
                if layer in presets_lib.COLLISION_LAYERS:
                    bit = presets_lib.COLLISION_LAYERS.index(layer)
                    sim_group |= (1 << bit)

            for layer in data[1]:
                if layer in presets_lib.COLLISION_LAYERS:
                    bit = presets_lib.COLLISION_LAYERS.index(layer)
                    sim_target_mask |= (1 << bit)

            for layer in data[2]:
                if layer in presets_lib.QUERY_LAYERS:
                    idx = presets_lib.QUERY_LAYERS.index(layer)
                    bit = col_layer_offset + idx
                    query_mask |= (1 << bit)

            found_preset = True

        if not found_preset:
            print(f"Warning: Preset '{preset_name}' not found. Using truncated UI values.")
            sim_group = physx_utils.bits_to_int(shape.filter_group)

        filter_handle_id = str(current_handle + 1)
        shape_handle_id = str(current_handle)

        filter_data_wrapper = {
            "HandleId": filter_handle_id,
            "Data": {
                "$type": "physicsFilterData",
                "customFilterData": None,
                "preset": {
                    "$type": "CName",
                    "$storage": "string",
                    "$value": preset_name
                },
                "queryFilter": {
                    "$type": "physicsQueryFilter",
                    "mask1": "0",
                    "mask2": str(query_mask)
                },
                "simulationFilter": {
                    "$type": "physicsSimulationFilter",
                    "mask1": str(sim_group),
                    "mask2": str(sim_target_mask)
                }
            }
        }

        pos = shape.local_pos
        rot = shape.local_rot

        collider_data = {
            "$type": get_physx_shape_type_mapping(shape.shape_type),
            "compiledGeometryBuffer": None,
            "filterData": filter_data_wrapper,
            "indexBuffer": [],
            "isImported": 0,
            "isQueryShapeOnly": 0,
            "localToBody": {
                "$type": "Transform",
                "orientation": {
                    "$type": "Quaternion",
                    "i": rot[1], "j": rot[2], "k": rot[3], "r": rot[0]
                },
                "position": {
                    "$type": "Vector4", "W": 0,
                    "X": pos[0], "Y": pos[1], "Z": pos[2]
                }
            },
            "material": {"$type": "CName", "$storage": "string", "$value": mat_name},
            "materialApperanceOverrides": [],
            "polygonVertices": [],
            "tag": {"$type": "CName", "$storage": "string", "$value": "None"},
            "volumeModifier": 1
        }

        # Geometry
        if shape.shape_type == 'BOX':
            collider_data["halfExtents"] = {"$type": "Vector3", "X": shape.dim_x, "Y": shape.dim_y, "Z": shape.dim_z}
        elif shape.shape_type == 'SPHERE':
            collider_data["radius"] = shape.dim_x
        elif shape.shape_type == 'CAPSULE':
            collider_data["radius"] = shape.dim_x
            collider_data["height"] = shape.dim_y * 2
        elif shape.shape_type == 'CONVEX':
            verts = []
            if shape.cooked_data:
                verts = extract_convex_verts_from_cooked(shape.cooked_data)
            if not verts:
                depsgraph = bpy.context.evaluated_depsgraph_get()
                eval_obj = obj_ref.evaluated_get(depsgraph)
                temp = eval_obj.to_mesh()
                for v in temp.vertices:
                    vx = v.co.x * obj_ref.scale.x
                    vy = v.co.y * obj_ref.scale.y
                    vz = v.co.z * obj_ref.scale.z
                    verts.append({"$type": "Vector3", "X": vx, "Y": vy, "Z": vz})
                eval_obj.to_mesh_clear()
            collider_data["vertices"] = verts

        colliders.append({"HandleId": shape_handle_id, "Data": collider_data})
        current_handle += 2

    if not colliders:
        print(f"Warning: Actor {obj_ref.name} has no shapes.")
        return False

    # 3. Build JSON
    output_json = {
        "Header": {
            "WolvenKitVersion": "8.17.2",
            "WKitJsonVersion": "0.0.9",
            "GameVersion": 2310,
            "ExportedDateTime": datetime.now(timezone.utc).isoformat() + "Z",
            "DataType": "CR2W",
            "ArchiveFileName": filepath
        },
        "Data": {
            "Version": 195, "BuildVersion": 0,
            "RootChunk": {
                "$type": "physicsSystemResource",
                "bodies": [
                    {
                        "HandleId": "0",
                        "Data": {
                            "$type": "physicsSystemBody",
                            "collisionShapes": colliders,
                            "isQueryBodyOnly": 0,
                            "localToModel": {
                                "$type": "Transform",
                                "orientation": {"$type": "Quaternion", "i": 0, "j": 0, "k": 0, "r": 1},
                                "position": {"$type": "Vector4", "W": 0, "X": 0, "Y": 0, "Z": 0}
                            },
                            "mappedBoneName": {"$type": "CName", "$storage": "string", "$value": "None"},
                            "mappedBoneToBody": {
                                "$type": "Transform",
                                "orientation": {"$type": "Quaternion", "i": 0, "j": 0, "k": 0, "r": 1},
                                "position": {"$type": "Vector4", "W": 0, "X": 0, "Y": 0, "Z": 0}
                            },
                            "name": {"$type": "CName", "$storage": "string", "$value": obj_ref.name},
                            "params": {
                                "$type": "physicsSystemBodyParams",
                                "angularDamping": 0.0,
                                "linearDamping": 0.0,
                                "comOffset": {
                                    "$type": "Transform",
                                    "orientation": {"$type": "Quaternion", "i": 0, "j": 0, "k": 0, "r": 1},
                                    "position": {"$type": "Vector4", "W": 0, "X": com.x, "Y": com.y, "Z": com.z}
                                },
                                "inertia": {"$type": "Vector3", "X": inertia.x, "Y": inertia.y, "Z": inertia.z},
                                "mass": total_mass,
                                "maxAngularVelocity": -1, "maxContactImpulse": -1, "maxDepenetrationVelocity": -1,
                                "simulationType": sim_type,
                                "solverIterationsCountPosition": 4, "solverIterationsCountVelocity": 1
                            }
                        }
                    }
                ],
                "cookingPlatform": "PLATFORM_PC", "joints": []
            },
            "EmbeddedFiles": []
        }
    }

    try:
        with open(filepath, 'w') as f:
            json.dump(output_json, f, indent=4)
        return True
    except Exception as e:
        print(f"Export Error: {e}")
        return False


def process_phys_import(filepath, target_obj, context):
    try:
        from . import pxbridge as _bridge
    except ImportError:
        _bridge = None
        print("PhysX Bridge missing: Imported colliders will not be cooked.")

    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON: {e}")
        return False

    try:
        root = data.get('Data', {}).get('RootChunk', {})
        bodies = root.get('bodies', [])

        if not bodies:
            print("No bodies found in .phys.json")
            return False

        body_data = bodies[0].get('Data', {})
        px = target_obj.physx

        if px.actor_type == 'NONE':
            px.actor_type = 'STATIC'
            params = body_data.get('params', {})
            sim_type = params.get('simulationType', 'Static')
            if sim_type in ('Dynamic', 'Kinematic'):
                px.actor_type = sim_type.upper()
            px.mass = float(params.get('mass', 10.0))
            px.calc_mass = True

        shapes = body_data.get('collisionShapes', [])
        count = 0

        for shape_entry in shapes:
            s_data = shape_entry.get('Data', {})
            s_type_raw = s_data.get('$type', '')

            # Add to the object's shape list
            shape_item = px.shapes.add()
            shape_item.name = s_type_raw.replace('physicsCollider', '')

            # Transform
            ltb = s_data.get('localToBody', {})
            pos = ltb.get('position', {})
            rot = ltb.get('orientation', {})

            shape_item.local_pos = (float(pos.get('X', 0)), float(pos.get('Y', 0)), float(pos.get('Z', 0)))
            shape_item.local_rot = (
                float(rot.get('r', 1.0)),
                float(rot.get('i', 0.0)),
                float(rot.get('j', 0.0)),
                float(rot.get('k', 0.0))
            )

            mat_info = s_data.get('material', {})
            mat_name = mat_info.get('$value', 'Default')
            if mat_name == 'None':
                mat_name = 'Default'
            shape_item.physics_material = mat_name

            # Filter
            fd = s_data.get('filterData')
            if fd and isinstance(fd, dict):
                filter_wrapper = fd.get('Data', {})
                preset_info = filter_wrapper.get('preset', {})
                preset_name = preset_info.get('$value', 'None')
                try:
                    shape_item.collision_preset = preset_name
                    physx_utils.update_collision_bits(shape_item, context)
                except TypeError:
                    pass
            else:
                shape_item.collision_preset = "None"

            # Geometry & Cooking
            if s_type_raw == 'physicsColliderBox':
                shape_item.shape_type = 'BOX'
                extents = s_data.get('halfExtents', {})
                shape_item.dim_x = float(extents.get('X', 0.5))
                shape_item.dim_y = float(extents.get('Y', 0.5))
                shape_item.dim_z = float(extents.get('Z', 0.5))

            elif s_type_raw == 'physicsColliderSphere':
                shape_item.shape_type = 'SPHERE'
                shape_item.dim_x = float(s_data.get('radius', 0.5))

            elif s_type_raw == 'physicsColliderCapsule':
                shape_item.shape_type = 'CAPSULE'
                shape_item.dim_x = float(s_data.get('radius', 0.5))
                shape_item.dim_y = float(s_data.get('height', 1.0)) / 2.0

            elif s_type_raw == 'physicsColliderConvex':
                shape_item.shape_type = 'CONVEX'
                raw_verts = s_data.get('vertices', [])
                shape_points = []
                for v in raw_verts:
                    shape_points.extend([float(v.get('X', 0)), float(v.get('Y', 0)), float(v.get('Z', 0))])

                if _bridge and shape_points:
                    try:
                        # Use eCOMPUTE_CONVEX via bridge (pass empty indices)
                        cooked = _bridge.cook_mesh("CONVEX", shape_points, [], 256)
                        if cooked:
                            shape_item.cooked_data = base64.b64encode(cooked).decode('ascii')
                            shape_item.is_cooked = True
                            shape_item.name += " (Cooked)"
                    except Exception as e:
                        print(f"Failed to cook: {e}")
                else:
                    shape_item.name += " (Raw)"

            count += 1

        if context.scene.physx:
            is_registered = False
            for item in context.scene.physx.actors:
                if item.obj_ref == target_obj:
                    is_registered = True
                    break

            if not is_registered:
                new_item = context.scene.physx.actors.add()
                new_item.obj_ref = target_obj
                context.scene.physx.actor_list_index = len(context.scene.physx.actors) - 1
            viz.invalidate_visualization_cache()
        return True

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False


class PHYSX_OT_export_phys(bpy.types.Operator):
    """Export the currently selected Actor"""
    bl_idname = "physx.export_phys"
    bl_label = "Export .phys (Cyberpunk)"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.phys.json", options={'HIDDEN'})

    def execute(self, context):
        px_s = context.scene.physx
        if len(px_s.actors) == 0:
            self.report({'ERROR'}, "Actor list is empty.")
            return {'CANCELLED'}
        index = px_s.actor_list_index
        if index < 0 or index >= len(px_s.actors):
            self.report({'ERROR'}, "No actor selected in list.")
            return {'CANCELLED'}
        target_actor = px_s.actors[index]
        if not target_actor.obj_ref:
            self.report({'ERROR'}, "Actor object is missing.")
            return {'CANCELLED'}
        success = export_actor_item_to_phys(target_actor, self.filepath)
        if success:
            self.report({'INFO'}, f"Exported: {target_actor.obj_ref.name}")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Export Failed. Check Console.")
            return {'CANCELLED'}

    def invoke(self, context, event):
        px_s = context.scene.physx
        if len(px_s.actors) > 0 and px_s.actor_list_index < len(px_s.actors):
            actor = px_s.actors[px_s.actor_list_index]
            if actor.obj_ref:
                self.filepath = actor.obj_ref.name + ".phys.json"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class PHYSX_OT_confirm_import(bpy.types.Operator):
    """Select the object to attach the physics shapes to"""
    bl_idname = "physx.confirm_import"
    bl_label = "Select Target Object"
    bl_options = {'REGISTER', 'INTERNAL'}

    filepath: bpy.props.StringProperty()
    target_obj_name: bpy.props.StringProperty(name="Target Object")

    def invoke(self, context, event):
        if context.active_object:
            self.target_obj_name = context.active_object.name
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Attach physics shapes to:")
        layout.prop_search(self, "target_obj_name", context.scene, "objects")

    def execute(self, context):
        obj = context.scene.objects.get(self.target_obj_name)
        if not obj:
            self.report({'ERROR'}, "Target object does not exist!")
            return {'CANCELLED'}
        if process_phys_import(self.filepath, obj, context):
            self.report({'INFO'}, f"Successfully imported to {obj.name}")
            obj.select_set(True)
            context.view_layer.objects.active = obj
            context.scene.physx.ui_tab = 'ACTORS'
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Import failed. Check Console.")
            return {'CANCELLED'}


class PHYSX_OT_import_phys(bpy.types.Operator):
    """Import a .phys.json file"""
    bl_idname = "physx.import_phys"
    bl_label = "Import .phys.json"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.phys.json;*.json", options={'HIDDEN'})

    def execute(self, context):
        bpy.ops.physx.confirm_import('INVOKE_DEFAULT', filepath=self.filepath)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class PHYSX_OT_save_cooked(bpy.types.Operator):
    bl_idname = "physx.save_cooked"
    bl_label = "Export NXS/CVXM"
    bl_description = "Save the raw PhysX Cooked Mesh data (NXS/CVXM/TRIM) to a file"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        obj = context.object
        if not obj or not obj.physx.shapes: return {'CANCELLED'}
        shape = obj.physx.shapes[obj.physx.shape_index]
        if not shape.cooked_data:
            self.report({'WARNING'}, "Mesh not cooked yet. Run 'Cook' first.")
            return {'CANCELLED'}
        try:
            data = base64.b64decode(shape.cooked_data.encode('ascii'))
            with open(self.filepath, 'wb') as f:
                f.write(data)
            self.report({'INFO'}, f"Saved NXS data: {len(data)} bytes")
        except Exception as e:
            self.report({'ERROR'}, str(e))
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class PHYSX_OT_load_cooked(bpy.types.Operator):
    bl_idname = "physx.load_cooked"
    bl_label = "Import NXS/CVXM"
    bl_description = "Load a raw PhysX Cooked Mesh file (NXS/CVXM/TRIM) into this shape"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        obj = context.object
        if not obj or not obj.physx.shapes: return {'CANCELLED'}
        shape = obj.physx.shapes[obj.physx.shape_index]
        try:
            with open(self.filepath, 'rb') as f:
                raw_data = f.read()
            if not raw_data.startswith(b'NXS'): self.report({'WARNING'}, "File does not look like PhysX NXS data")
            shape.cooked_data = base64.b64encode(raw_data).decode('ascii')
            shape.is_cooked = True
            self.report({'INFO'}, f"Loaded NXS data: {len(raw_data)} bytes")
        except Exception as e:
            self.report({'ERROR'}, str(e))
        viz.invalidate_visualization_cache()
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class PHYSX_OT_export_scene(bpy.types.Operator):
    bl_idname = "physx.export_scene"
    bl_label = "Export Binary"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        try:
            from . import pxbridge as _bridge
            if _bridge.export_scene(self.filepath):
                self.report({'INFO'}, f"Scene Exported to {self.filepath}")
            else:
                self.report({'ERROR'}, "Export Failed")
        except Exception as e:
            self.report({'ERROR'}, str(e))
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class PHYSX_OT_import_scene(bpy.types.Operator):
    bl_idname = "physx.import_scene"
    bl_label = "Import Binary"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        try:
            from . import pxbridge as _bridge
            if _bridge.import_scene(self.filepath):
                self.report({'INFO'}, "Scene Imported successfully")
            else:
                self.report({'ERROR'}, "Import Failed")
        except Exception as e:
            self.report({'ERROR'}, str(e))
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}