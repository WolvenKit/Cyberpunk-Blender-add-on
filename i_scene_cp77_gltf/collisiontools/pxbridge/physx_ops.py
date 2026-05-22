import bpy
import math
import base64
from math import inf
from mathutils import Matrix, Vector, Quaternion, Euler
from bpy_extras.view3d_utils import region_2d_to_vector_3d, region_2d_to_origin_3d
from . import physx_utils, viz


class PHYSX_OT_init_scene(bpy.types.Operator):
    bl_idname = "physx.init_scene"
    bl_label = "Initialize Scene"

    add_ground = bpy.props.BoolProperty(name="Add Ground Plane", default=True)
    ground = None

    def execute(self, context):
        try:
            from . import pxbridge as _bridge
            if _bridge.init():
                context.scene.physx.is_initialized = True
                g = context.scene.physx.gravity
                _bridge.set_gravity(g[0], g[1], g[2])
                self.report({'INFO'}, "PhysX Initialized")
                if self.add_ground:
                    ground_obj = physx_utils.add_ground_plane(offset_below=0.0, xy_expand=50, height=1.0)
                    already_added = False
                    for item in context.scene.physx.actors:
                        if item.obj_ref == ground_obj:
                            already_added = True
                            break

                    if not already_added:
                        item = context.scene.physx.actors.add()
                        item.obj_ref = ground_obj
                        px = ground_obj.physx
                        px.actor_type = 'STATIC'
                        if len(px.shapes) == 0:
                            shp = px.shapes.add()
                            shp.name = "GroundBox"
                            shp.shape_type = 'BOX'
                            dims = ground_obj.dimensions
                            shp.dim_x = dims.x / 2.0
                            shp.dim_y = dims.y / 2.0
                            shp.dim_z = dims.z / 2.0
            else:
                self.report({'ERROR'}, "Init Failed")
        except ImportError:
            self.report({'ERROR'}, "DLL Missing")
        return {'FINISHED'}


class PHYSX_OT_validate_scene(bpy.types.Operator):
    bl_idname = "physx.validate_scene"
    bl_label = "Validate Scene"

    def execute(self, context):
        px_s = context.scene.physx
        errors = []
        for item in px_s.actors:
            obj = item.obj_ref
            if not obj: continue
            px = obj.physx
            for shape in px.shapes:
                if shape.shape_type in ('CONVEX', 'TRIANGLE', 'HEIGHTFIELD') and not shape.cooked_data:
                    errors.append(f"{obj.name}: {shape.name} not cooked")
        if errors:
            self.report({'ERROR'}, "Errors: " + "; ".join(errors))
            return {'CANCELLED'}
        self.report({'INFO'}, "Scene Valid")
        return {'FINISHED'}


class PHYSX_OT_build_scene(bpy.types.Operator):
    bl_idname = "physx.build_scene"
    bl_label = "Build PhysX Scene"

    def execute(self, context):
        bpy.ops.physx.validate_scene()
        try:
            from . import pxbridge as _bridge
            _bridge.reset()
            g = context.scene.physx.gravity
            _bridge.set_gravity(g[0], g[1], g[2])
            count = 0

            for item in context.scene.physx.actors:
                obj = item.obj_ref
                if not obj or obj.physx.actor_type == 'NONE': continue
                px = obj.physx

                shapes_list = []
                for shape in px.shapes:
                    raw = ""
                    if shape.shape_type in ('CONVEX', 'TRIANGLE', 'HEIGHTFIELD'):
                        if not shape.cooked_data: continue
                        raw = base64.b64decode(shape.cooked_data.encode('ascii'))

                    mat_data = physx_utils.get_mat_data(shape.physics_material)
                    q = shape.local_rot
                    l = shape.local_pos
                    px_quat = [q[1], q[2], q[3], q[0]]

                    w0 = physx_utils.bits_to_int(shape.filter_group)
                    w1 = physx_utils.bits_to_int(shape.filter_mask)
                    w2 = physx_utils.bits_to_int(shape.filter_query)
                    w3 = 0

                    shapes_list.append(
                            {
                                "type": shape.shape_type,
                                "data": raw,
                                "dims": [shape.dim_x, shape.dim_y, shape.dim_z],
                                "pos": [l[0], l[1], l[2]],
                                "rot": px_quat,
                                "mat": mat_data,
                                "filter": [w0, w1, w2, w3]
                                }
                            )

                if not shapes_list: continue
                loc, quat = physx_utils.get_actor_world_transform(item)
                actor_pose = [loc.x, loc.y, loc.z, quat.x, quat.y, quat.z, quat.w]
                com = [px.com_offset[0], px.com_offset[1], px.com_offset[2]]
                inert = [px.inertia[0], px.inertia[1], px.inertia[2]]

                handle = _bridge.create_actor(px.actor_type, actor_pose, shapes_list, px.mass, com, inert)
                item.actor_handle = str(handle)
                count += 1

            context.scene.physx.active_actor_count = _bridge.get_actor_count()
            context.scene.physx.scene_built = True
            self.report({'INFO'}, f"Built {count} actors")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'FINISHED'}


class PHYSX_OT_run_steps(bpy.types.Operator):
    bl_idname = "physx.run_steps"
    bl_label = "Step N"

    @classmethod
    def poll(cls, context):
        return context.scene.physx.is_initialized

    def execute(self, context):
        px_s = context.scene.physx
        if not px_s.is_initialized: return {'CANCELLED'}
        try:
            from . import pxbridge as _bridge
            dt = 1.0 / 60.0
            for _ in range(px_s.sim_steps):
                _bridge.start_step(dt)
                _bridge.fetch_results(True)
            poses = _bridge.get_active_poses()
            if poses:
                for item in px_s.actors:
                    h = item.actor_handle
                    if h in poses and item.obj_ref:
                        p = poses[h]
                        loc = Vector((p[0], p[1], p[2]))
                        quat = Quaternion((p[6], p[3], p[4], p[5]))
                        world_matrix = Matrix.Translation(loc) @ quat.to_matrix().to_4x4()
                        if item.use_bone_parent and item.parent_armature != "NONE" and item.target_bone != "NONE":
                            armature_obj = context.scene.objects.get(item.parent_armature)
                            if armature_obj:
                                physx_utils.set_bone_world_matrix(armature_obj, item.target_bone, world_matrix)
                        else:
                            item.obj_ref.matrix_world = world_matrix
            # Update viz after stepping
            viz.invalidate_visualization_cache()
            for window in context.window_manager.windows:
                for area in window.screen.areas: area.tag_redraw()
            self.report({'INFO'}, f"Stepped {px_s.sim_steps}")
        except Exception as e:
            self.report({'ERROR'}, str(e))
        return {'FINISHED'}


class PHYSX_OT_sim_step(bpy.types.Operator):
    bl_idname = "physx.sim_step"
    bl_label = "Run Simulation"
    _timer = None
    _cursor_handle = "0"
    cursor_radius: bpy.props.FloatProperty(name="Cursor Radius", default=1.0)

    @classmethod
    def poll(cls, context):
        px_s = context.scene.physx
        return px_s.is_initialized and not px_s.sim_running

    def invoke(self, context, event):
        if not context.scene.physx.scene_built:
            bpy.ops.physx.build_scene()
        context.scene.physx.sim_running = True
        self._timer = context.window_manager.event_timer_add(1.0 / 60.0, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        px_s = context.scene.physx
        if not px_s.sim_running:
            return self.cancel(context)
        if event.type in {'ESC', 'RIGHTMOUSE'}:
            return self.cancel(context)
        from . import pxbridge as _bridge

        # Manipulator
        if event.type == 'MOUSEMOVE':
            if context.region and context.region_data:
                vec = region_2d_to_vector_3d(
                        context.region, context.region_data, (event.mouse_region_x, event.mouse_region_y)
                        )
                orig = region_2d_to_origin_3d(
                        context.region, context.region_data, (event.mouse_region_x, event.mouse_region_y)
                        )
                if abs(vec.z) > 0.0001:
                    t = -orig.z / vec.z
                    if t > 0:
                        pos = orig + vec * t
                        px_s.manipulator_pos = pos
                        if px_s.use_grab_mode:
                            if self._cursor_handle == "0":
                                target_preset_name = physx_utils.presets_lib._OVERRIDES.get(
                                        "All Collision Touch All", "World Dynamic"
                                        )
                                w0, w1, w2, w3 = 0, 0, 0, 0
                                if target_preset_name in physx_utils.presets_lib._RAW_PRESETS:
                                    data = physx_utils.presets_lib._RAW_PRESETS[target_preset_name]
                                    for name in data[0]:
                                        idx = physx_utils.presets_lib.get_layer_bit(name, is_query=False)
                                        if idx >= 0: w0 |= (1 << idx)
                                    for name in data[1]:
                                        idx = physx_utils.presets_lib.get_layer_bit(name, is_query=False)
                                        if idx >= 0: w1 |= (1 << idx)
                                    for name in data[2]:
                                        idx = physx_utils.presets_lib.get_layer_bit(name, is_query=True)
                                        if idx >= 0: w2 |= (1 << idx)

                                start_pose = [pos.x, pos.y, pos.z, 0, 0, 0, 1]
                                shape_def = {
                                    "type": "SPHERE", "data": "", "dims": [self.cursor_radius, 0, 0],
                                    "pos": [0, 0, 0], "rot": [0, 0, 0, 1], "mat": [0.5, 0.5, 0.5],
                                    "filter": [w0, w1, w2, w3]
                                    }
                                h = _bridge.create_actor(
                                        "KINEMATIC", start_pose, [shape_def], 1.0, [0, 0, 0], [1, 1, 1]
                                        )
                                self._cursor_handle = str(h)
                                px_s.manipulator_handle = str(h)
                            else:
                                bridge_pos = [pos.x, pos.y, pos.z]
                                bridge_rot = [0, 0, 0, 1]
                                try:
                                    _bridge.set_kinematic_target(int(self._cursor_handle), bridge_pos, bridge_rot)
                                except Exception:
                                    pass

        if event.type == 'TIMER':
            _bridge.start_step(1.0 / 60.0)
            _bridge.fetch_results(True)
            poses = _bridge.get_active_poses()
            for item in px_s.actors:
                h = item.actor_handle
                if h in poses and item.obj_ref:
                    p = poses[h]
                    loc = Vector((p[0], p[1], p[2]))
                    quat = Quaternion((p[6], p[3], p[4], p[5]))
                    world_matrix = Matrix.Translation(loc) @ quat.to_matrix().to_4x4()
                    if item.use_bone_parent and item.parent_armature != "NONE" and item.target_bone != "NONE":
                        armature_obj = context.scene.objects.get(item.parent_armature)
                        if armature_obj:
                            physx_utils.set_bone_world_matrix(armature_obj, item.target_bone, world_matrix)
                    else:
                        item.obj_ref.matrix_world = world_matrix

            # Force update
            viz.invalidate_visualization_cache()
            context.view_layer.update()
        return {'PASS_THROUGH'}

    def execute(self, context):
        return self.invoke(context, None)

    def cancel(self, context):
        context.scene.physx.sim_running = False
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        if self._cursor_handle != "0":
            from . import pxbridge as _bridge
            try:
                _bridge.remove_actor(int(self._cursor_handle))
            except:
                pass
            self._cursor_handle = "0"
            context.scene.physx.manipulator_handle = "0"
        return {'CANCELLED'}


class PHYSX_OT_stop_sim(bpy.types.Operator):
    bl_idname = "physx.stop_sim"
    bl_label = "Stop"

    def execute(self, context):
        context.scene.physx.sim_running = False
        return {'FINISHED'}


class PHYSX_OT_apply_force(bpy.types.Operator):
    bl_idname = "physx.apply_force"
    bl_label = "Apply Force"

    def execute(self, context):
        px_s = context.scene.physx
        obj = context.active_object
        h = "0"
        for item in px_s.actors:
            if item.obj_ref == obj:
                h = item.actor_handle
                break
        if h == "0": return {'CANCELLED'}
        from . import pxbridge as _bridge
        f = px_s.force_value
        p = context.scene.cursor.location if px_s.use_force_pos else Vector((0, 0, 0))
        _bridge.apply_force(int(h), [f[0], f[1], f[2]], int(px_s.force_mode), px_s.use_force_pos, [p.x, p.y, p.z])
        return {'FINISHED'}


class PHYSX_OT_update_gravity(bpy.types.Operator):
    bl_idname = "physx.update_gravity"
    bl_label = "Update Gravity"

    def execute(self, context):
        try:
            from . import pxbridge as _bridge
            g = context.scene.physx.gravity
            _bridge.set_gravity(g[0], g[1], g[2])
        except:
            pass
        return {'FINISHED'}


class PHYSX_OT_cook_mesh(bpy.types.Operator):
    bl_idname = "physx.cook_mesh";
    bl_label = "Cook"

    def execute(self, context):
        try:
            from . import pxbridge as _bridge
            if not _bridge.init(): return {'CANCELLED'}
            obj = context.object
            shape = obj.physx.shapes[obj.physx.shape_index]
            if shape.shape_type == 'HEIGHTFIELD':
                mw = obj.matrix_world
                min_x = min_y = min_z = inf
                max_x = max_y = max_z = -inf
                for b in obj.bound_box:
                    x, y, z = mw @ Vector(b)
                    if x < min_x: min_x = x
                    if x > max_x: max_x = x
                    if y < min_y: min_y = y
                    if y > max_y: max_y = y
                    if z < min_z: min_z = z
                    if z > max_z: max_z = z
                rows = shape.hf_resolution
                cols = shape.hf_resolution
                if rows < 2 or cols < 2: raise ValueError("Resolution must be >= 2")
                step_x = (max_x - min_x) / (cols - 1)
                step_y = (max_y - min_y) / (rows - 1)
                verts, indices = physx_utils.get_raw_mesh_data(obj)
                loc = obj.matrix_world.to_translation()
                rot = obj.matrix_world.to_quaternion()
                transform = [loc.x, loc.y, loc.z, rot.x, rot.y, rot.z, rot.w]
                cooked = _bridge.cook_hf_from_mesh(
                        rows, cols, [min_x, min_y, min_z], [step_x, step_y], verts, indices, transform
                        )
            else:
                verts, indices = physx_utils.get_clean_mesh_data(obj, shape.shape_type, shape.vertex_limit)
                cooked = _bridge.cook_mesh(shape.shape_type, verts, indices, shape.vertex_limit)
            if cooked:
                shape.cooked_data = base64.b64encode(cooked).decode('ascii')
                shape.is_cooked = True
                shape.local_pos = (0, 0, 0)
                shape.local_rot = (1.0, 0.0, 0.0, 0.0)
                viz.invalidate_visualization_cache()
                self.report({'INFO'}, "Cooking Complete")
        except Exception as e:
            self.report({'ERROR'}, str(e))
        return {'FINISHED'}


class PHYSX_OT_fit_bounds_shape(bpy.types.Operator):
    bl_idname = "physx.fit_bounds_shape"
    bl_label = "Fit"
    shape_index: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        obj = context.object
        px = obj.physx
        idx = self.shape_index if self.shape_index >= 0 else px.shape_index
        shape = px.shapes[idx]
        bbox = [Vector(b) for b in obj.bound_box]
        for v in bbox:
            v.x *= obj.scale.x;
            v.y *= obj.scale.y;
            v.z *= obj.scale.z
        min_v = Vector((min(v.x for v in bbox), min(v.y for v in bbox), min(v.z for v in bbox)))
        max_v = Vector((max(v.x for v in bbox), max(v.y for v in bbox), max(v.z for v in bbox)))
        size = max_v - min_v
        center = (min_v + max_v) / 2.0
        if shape.shape_type in ('CONVEX', 'TRIANGLE', 'HEIGHTFIELD'):
            shape.local_pos = (0, 0, 0)
        else:
            shape.local_pos = center
        if shape.shape_type == 'BOX':
            shape.dim_x = size.x / 2;
            shape.dim_y = size.y / 2;
            shape.dim_z = size.z / 2
        elif shape.shape_type == 'SPHERE':
            shape.dim_x = max(size) / 2.0
        elif shape.shape_type == 'CAPSULE':
            rad = max(size.x, size.y) / 2.0
            hh = (size.z / 2.0) - rad
            if hh < 0: hh = 0; rad = size.z / 2.0
            shape.dim_x = rad;
            shape.dim_y = hh
            shape.local_rot = Euler((0, math.radians(90), 0)).to_quaternion()
        elif shape.shape_type == 'HEIGHTFIELD':
            shape.dim_x = size.x / 2.0;
            shape.dim_y = size.y / 2.0;
            shape.dim_z = size.z / 2.0
        viz.invalidate_visualization_cache()
        context.area.tag_redraw()
        return {'FINISHED'}


class PHYSX_OT_calc_dynamics(bpy.types.Operator):
    bl_idname = "physx.calc_dynamics"
    bl_label = "Auto Calc"

    def execute(self, context):
        obj = context.object
        px = obj.physx
        try:
            from . import pxbridge as _bridge
            shapes_data = []
            densities = []
            for shape in px.shapes:
                raw = ""
                if shape.cooked_data:
                    raw = base64.b64decode(shape.cooked_data.encode('ascii'))
                dens = physx_utils.get_mat_density(shape.physics_material)
                densities.append(dens)
                l = shape.local_pos
                q = shape.local_rot
                data = {
                    "type": shape.shape_type, "data": raw, "dims": [shape.dim_x, shape.dim_y, shape.dim_z],
                    "pos": [l[0], l[1], l[2]], "rot": [q[1], q[2], q[3], q[0]], "mat": [0, 0, 0]
                    }
                shapes_data.append(data)
            res = _bridge.compute_mass_props(shapes_data, densities)
            if px.calc_mass: px.mass = res['mass']
            if px.calc_offset: px.com_offset = res['com']
            if px.calc_inertia: px.inertia = res['inertia']
        except Exception as e:
            print(f"Mass Calc Error: {e}")
        return {'FINISHED'}


class PHYSX_OT_shape_action(bpy.types.Operator):
    bl_idname = "physx.shape_action"
    bl_label = "Action"
    action: bpy.props.EnumProperty(items=[('ADD', "Add", ""), ('REMOVE', "Remove", "")])

    def execute(self, context):
        px = context.object.physx
        if self.action == 'ADD':
            s = px.shapes.add()
            s.name = f"Shape {len(px.shapes)}"
            bpy.ops.physx.fit_bounds_shape(shape_index=len(px.shapes) - 1)
            px.shape_index = len(px.shapes) - 1
        elif self.action == 'REMOVE' and len(px.shapes) > 0:
            px.shapes.remove(px.shape_index)
            px.shape_index = max(0, px.shape_index - 1)
        viz.invalidate_visualization_cache()
        return {'FINISHED'}


class PHYSX_OT_list_action(bpy.types.Operator):
    bl_idname = "physx.list_action"
    bl_label = "List Action"
    action: bpy.props.EnumProperty(items=[('ADD', "Add", ""), ('REMOVE', "Remove", "")])

    def execute(self, context):
        px_s = context.scene.physx
        if self.action == 'ADD':
            obj = context.active_object
            if not obj: return {'CANCELLED'}
            for item in px_s.actors:
                if item.obj_ref == obj: return {'CANCELLED'}
            item = px_s.actors.add()
            item.obj_ref = obj
            if len(obj.physx.shapes) == 0:
                s = obj.physx.shapes.add()
                s.name = "Shape 1"
                bpy.ops.physx.fit_bounds_shape(shape_index=0)
            px_s.actor_list_index = len(px_s.actors) - 1
        elif self.action == 'REMOVE':
            if len(px_s.actors) > 0: px_s.actors.remove(px_s.actor_list_index)
        viz.invalidate_visualization_cache()
        return {'FINISHED'}


class PHYSX_OT_reset_session(bpy.types.Operator):
    bl_idname = "physx.reset_session"
    bl_label = "Reset"

    def execute(self, context):
        try:
            from . import pxbridge as _bridge
            _bridge.reset()
            context.scene.physx.active_actor_count = 0
            context.scene.physx.scene_built = False
        except Exception:
            pass
        return {'FINISHED'}