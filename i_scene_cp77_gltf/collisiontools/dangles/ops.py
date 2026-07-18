import time

import bpy
from bpy.props import IntProperty, StringProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

from . import draw, io
from .sim import core, solvers, spaces
from .ui import get_active_chain, get_active_dangle_node, get_active_rig

try:
    from ...main.animation_api import assign_action_with_slot
except (ImportError, ValueError):
    def assign_action_with_slot(id_data, action):
        animation_data = id_data.animation_data_create()
        animation_data.action = action
        slots = getattr(action, "slots", None)
        if slots is None:
            return animation_data
        if len(slots):
            slot = slots[0]
        else:
            try:
                slot = slots.new(id_type=id_data.id_type, name=id_data.name)
            except TypeError:
                slot = slots.new(id_type=id_data.id_type)
        if hasattr(animation_data, "action_slot"):
            animation_data.action_slot = slot
        return animation_data


SUPPORTED_PREVIEW_SOLVERS = {'DYNG', 'PBD', 'SPRING', 'PENDULUM'}
_ACTIVE_PREVIEW_SESSIONS = {}


def _runtime_target_errors(rig, require_state=True):
    errors = list(spaces.armature_space_errors(rig))
    if require_state:
        missing = spaces.unresolved_state_bones(
            rig, rig.dangle_state, executable_only=True
        )
        if missing:
            names = []
            seen = set()
            for _role, name in missing:
                if name not in seen:
                    seen.add(name)
                    names.append(name)
            preview = ", ".join(names[:10])
            suffix = f" (+{len(names) - 10} more)" if len(names) > 10 else ""
            errors.append(
                f"MetaRig is missing required Dangle bones: {preview}{suffix}"
            )
    return errors


def _report_target_errors(operator, rig, require_state=True):
    errors = _runtime_target_errors(rig, require_state=require_state)
    if not errors:
        return False
    operator.report({'ERROR'}, errors[0])
    return True


def _preview_session_key(rig):
    try:
        return int(rig.as_pointer())
    except (ReferenceError, AttributeError):
        return None


def _stop_preview_session(context, rig, restore_pose=True):
    key = _preview_session_key(rig)
    session = _ACTIVE_PREVIEW_SESSIONS.get(key) if key is not None else None
    if session is not None:
        session._finish(context, restore_pose=restore_pose)
        return True
    try:
        if rig is not None:
            rig.dangle_state.is_playing = False
    except ReferenceError:
        pass
    return False


def _unsupported_solver_names(state):
    return sorted({
        chain.solver
        for node in state.dangle_nodes
        for chain in node.chains
        if chain.solver not in SUPPORTED_PREVIEW_SOLVERS
    })


def _keyframe_pose_bone(pose_bone, frame):
    pose_bone.keyframe_insert(data_path="location", frame=frame)
    if pose_bone.rotation_mode == 'QUATERNION':
        rotation_path = "rotation_quaternion"
    elif pose_bone.rotation_mode == 'AXIS_ANGLE':
        rotation_path = "rotation_axis_angle"
    else:
        rotation_path = "rotation_euler"
    pose_bone.keyframe_insert(data_path=rotation_path, frame=frame)


class DANGLE_OT_enable_rig(bpy.types.Operator):
    bl_idname = "dangle.enable_rig"
    bl_label = "Enable Dangle Physics on Armature"

    def execute(self, context):
        if context.active_object and context.active_object.type == 'ARMATURE':
            if _report_target_errors(self, context.active_object, require_state=False):
                return {'CANCELLED'}
            context.active_object.dangle_state.is_dangle_rig = True
            for i, obj in enumerate(context.scene.objects):
                if obj == context.active_object:
                    context.scene.dangle_active_rig_index = i
                    break
        return {'FINISHED'}

class DANGLE_OT_disable_rig(bpy.types.Operator):
    bl_idname = "dangle.disable_rig"
    bl_label = "Remove Dangle from Armature"
    bl_options = {'UNDO'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        rig = get_active_rig(context)
        if not rig:
            self.report({'WARNING'}, "No active Dangle rig selected.")
            return {'CANCELLED'}

        st = rig.dangle_state

        _stop_preview_session(context, rig, restore_pose=True)
        draw._DRAW_CACHES.pop(f"{rig.as_pointer()}", None)
        draw._DRAW_CACHES.pop(rig.name, None)

        st.dangle_nodes.clear()
        st.collision_shapes.clear()
        st.drag_nodes.clear()
        st.evaluation_order.clear()
        st.is_dangle_rig = False

        self.report({'INFO'}, f"Removed dangle data from {rig.name}.")
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}

class DANGLE_OT_preview_play(bpy.types.Operator):
    bl_idname = "dangle.preview_play"
    bl_label = "Play Dangle Simulation"

    _timer = None
    _simulator = None
    _rig = None
    _cache_key = None
    _last_time = 0.0
    _closed = False

    def modal(self, context, event):
        if self._closed:
            return {'CANCELLED'}
        rig = self._rig
        try:
            valid_rig = rig is not None and rig.name in bpy.data.objects
        except ReferenceError:
            valid_rig = False

        if not valid_rig or event.type == 'ESC' or not rig.dangle_state.is_playing:
            self._finish(context, restore_pose=valid_rig)
            return {'CANCELLED'}

        if event.type == 'TIMER':
            current_time = time.time()
            dt = min(current_time - self._last_time, 0.1)
            self._last_time = current_time

            solvers.update_simulation(self._simulator, dt, time_dilation=1.0)
            draw.update_draw_cache(self._cache_key, self._simulator)

            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

        return {'PASS_THROUGH'}

    def execute(self, context):
        rig = get_active_rig(context)
        if not rig:
            return {'CANCELLED'}
        state = rig.dangle_state
        if _report_target_errors(self, rig):
            return {'CANCELLED'}
        if not state.dangle_nodes and not state.drag_nodes:
            self.report({'WARNING'}, "No Dangle or Drag nodes imported.")
            return {'CANCELLED'}
        unsupported = _unsupported_solver_names(state)
        if unsupported:
            self.report({
                'ERROR'
            }, f"Preview does not support: {', '.join(unsupported)}")
            return {'CANCELLED'}
        if rig.mode != 'POSE':
            self.report({'WARNING'}, "Enter Pose Mode before starting Dangle preview.")
            return {'CANCELLED'}
        key = _preview_session_key(rig)
        existing = _ACTIVE_PREVIEW_SESSIONS.get(key) if key is not None else None
        if existing is not None:
            existing._finish(context, restore_pose=True)
        elif state.is_playing:
            state.is_playing = False

        self._closed = False
        self._rig = rig
        self._cache_key = f"{rig.as_pointer()}"
        try:
            self._simulator = core.DyngSimulator(rig)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            self._rig = None
            self._cache_key = None
            return {'CANCELLED'}
        self._last_time = time.time()

        wm = context.window_manager
        self._timer = wm.event_timer_add(1.0 / 60.0, window=context.window)
        wm.modal_handler_add(self)
        state.is_playing = True
        if key is not None:
            _ACTIVE_PREVIEW_SESSIONS[key] = self
        return {'RUNNING_MODAL'}

    def _finish(self, context, restore_pose=True):
        if self._closed:
            return
        self._closed = True

        rig = self._rig
        key = _preview_session_key(rig)
        simulator = self._simulator

        if restore_pose and simulator is not None:
            try:
                simulator.restore_upstream_pose()
            except ReferenceError:
                pass

        try:
            if rig is not None:
                rig.dangle_state.is_playing = False
        except ReferenceError:
            pass

        if key is not None and _ACTIVE_PREVIEW_SESSIONS.get(key) is self:
            _ACTIVE_PREVIEW_SESSIONS.pop(key, None)

        if self._cache_key is not None:
            draw._DRAW_CACHES.pop(self._cache_key, None)

        if self._timer is not None:
            try:
                context.window_manager.event_timer_remove(self._timer)
            except (ReferenceError, ValueError):
                pass
            self._timer = None

        screen = getattr(context, 'screen', None)
        if screen is not None:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

        self._simulator = None
        self._rig = None
        self._cache_key = None

    def cancel(self, context):
        self._finish(context, restore_pose=True)
        return {'CANCELLED'}

class DANGLE_OT_preview_stop(bpy.types.Operator):
    bl_idname = "dangle.preview_stop"
    bl_label = "Stop Simulation"

    def execute(self, context):
        rig = get_active_rig(context)
        if rig:
            _stop_preview_session(context, rig, restore_pose=True)
        return {'FINISHED'}

class DANGLE_OT_bake_to_keyframes(bpy.types.Operator):
    bl_idname = "dangle.bake_to_keyframes"
    bl_label = "Bake Dangle to Keyframes"
    bl_options = {'UNDO'}

    def execute(self, context):
        rig = get_active_rig(context)
        if not rig:
            return {'CANCELLED'}
        st = rig.dangle_state
        if _report_target_errors(self, rig):
            return {'CANCELLED'}
        if not st.dangle_nodes and not st.drag_nodes:
            self.report({'WARNING'}, "No Dangle or Drag nodes imported.")
            return {'CANCELLED'}
        unsupported = _unsupported_solver_names(st)
        if unsupported:
            self.report({'ERROR'}, f"Bake does not support: {', '.join(unsupported)}")
            return {'CANCELLED'}

        scene = context.scene
        original_frame = scene.frame_current
        bpy.ops.object.select_all(action='DESELECT')
        rig.select_set(True)
        context.view_layer.objects.active = rig
        if rig.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')

        scene.frame_set(scene.frame_start)
        context.view_layer.update()
        try:
            simulator = core.DyngSimulator(rig)
        except Exception as exc:
            scene.frame_set(original_frame)
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        dt = (1.0 / scene.render.fps) * scene.render.fps_base

        action = bpy.data.actions.new(name=f"{rig.name}_DangleBake")
        assign_action_with_slot(rig, action)

        for frame in range(scene.frame_start, scene.frame_end + 1):
            scene.frame_set(frame)
            solvers.update_simulation(simulator, dt)

            keyed_bones = {
                simulator.bone_names[index]
                for index in range(simulator.num_particles)
                if simulator.active_mask[index]
            }
            if getattr(simulator, 'link_idx_a', None) is not None:
                keyed_bones.update(
                    simulator.bone_names[int(index)]
                    for index in simulator.link_idx_a
                )
            keyed_bones.update(
                simulator.bone_names[int(index)]
                for index in getattr(simulator.drag_post, 'drag_indices', ())
                if 0 <= int(index) < len(simulator.bone_names)
            )
            for bone_name in keyed_bones:
                pose_bone = rig.pose.bones.get(bone_name)
                if pose_bone is not None:
                    _keyframe_pose_bone(pose_bone, frame)

        scene.frame_set(original_frame)
        self.report({'INFO'}, f"Baked frames {scene.frame_start}-{scene.frame_end} to {action.name}.")
        return {'FINISHED'}

class DANGLE_OT_import_json(bpy.types.Operator, ImportHelper):
    bl_idname = "dangle.import_json"
    bl_label = "Import Dangle JSON"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    def execute(self, context):
        rig = get_active_rig(context)
        if not rig:
            self.report({'ERROR'}, "No active Dangle Rig selected.")
            return {'CANCELLED'}
        if rig.dangle_state.is_playing:
            self.report({'ERROR'}, "Stop Dangle preview before importing.")
            return {'CANCELLED'}
        try:
            count = io.import_chains(self.filepath, rig.dangle_state)
            self.report({'INFO'}, f"Imported {count} dangle node(s).")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to import: {str(e)}")
            return {'CANCELLED'}
        return {'FINISHED'}

class DANGLE_OT_export_json(bpy.types.Operator, ExportHelper):
    bl_idname = "dangle.export_json"
    bl_label = "Export Editor JSON"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    def execute(self, context):
        rig = get_active_rig(context)
        if not rig:
            self.report({'ERROR'}, "No active Dangle Rig selected.")
            return {'CANCELLED'}
        try:
            io.export_chains(self.filepath, rig.dangle_state)
            self.report({'INFO'}, "Exported successfully.")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export: {str(e)}")
            return {'CANCELLED'}
        return {'FINISHED'}

class DANGLE_OT_add_dangle_node(bpy.types.Operator):
    bl_idname = "dangle.add_node"
    bl_label = "Add Node"

    def execute(self, context):
        rig = get_active_rig(context)
        if not rig:
            return {'CANCELLED'}
        st = rig.dangle_state
        node = st.dangle_nodes.add()
        node.name = f"Node_{len(st.dangle_nodes)}"
        st.active_dangle_node = len(st.dangle_nodes) - 1
        operation = st.evaluation_order.add()
        operation.node_type = 'DANGLE'
        operation.node_index = st.active_dangle_node
        operation.source_handle = 'editor'
        operation.graph_path = f'editor.dangle[{st.active_dangle_node}]'
        return {'FINISHED'}

class DANGLE_OT_remove_dangle_node(bpy.types.Operator):
    bl_idname = "dangle.remove_node"
    bl_label = "Remove Node"

    def execute(self, context):
        rig = get_active_rig(context)
        if not rig:
            return {'CANCELLED'}
        st = rig.dangle_state
        if not st.dangle_nodes:
            return {'CANCELLED'}
        removed_index = st.active_dangle_node
        st.dangle_nodes.remove(removed_index)
        for operation_index in reversed(range(len(st.evaluation_order))):
            operation = st.evaluation_order[operation_index]
            if operation.node_type != 'DANGLE':
                continue
            if operation.node_index == removed_index:
                st.evaluation_order.remove(operation_index)
            elif operation.node_index > removed_index:
                operation.node_index -= 1
        if st.active_dangle_node > 0:
            st.active_dangle_node -= 1
        return {'FINISHED'}

class DANGLE_OT_add_chain(bpy.types.Operator):
    bl_idname = "dangle.add_chain"
    bl_label = "Add Chain"

    def execute(self, context):
        dnode = get_active_dangle_node(context)
        if not dnode:
            return {'CANCELLED'}
        ch = dnode.chains.add()
        ch.name = f"Chain_{len(dnode.chains)}"
        dnode.active_chain = len(dnode.chains) - 1
        return {'FINISHED'}

class DANGLE_OT_remove_chain(bpy.types.Operator):
    bl_idname = "dangle.remove_chain"
    bl_label = "Remove Chain"

    def execute(self, context):
        dnode = get_active_dangle_node(context)
        if not dnode or not dnode.chains:
            return {'CANCELLED'}
        dnode.chains.remove(dnode.active_chain)
        if dnode.active_chain > 0:
            dnode.active_chain -= 1
        return {'FINISHED'}

class DANGLE_OT_add_particle(bpy.types.Operator):
    bl_idname = "dangle.add_particle"
    bl_label = "Add Particle"

    def execute(self, context):
        chain = get_active_chain(context)
        if not chain:
            return {'CANCELLED'}
        if chain.solver in {'PBD', 'SPRING', 'PENDULUM'} and chain.particles:
            solver_name = {'PBD': 'Position Projection', 'SPRING': 'Spring', 'PENDULUM': 'Pendulum'}[chain.solver]
            self.report({'WARNING'}, f"{solver_name} supports one bone only.")
            return {'CANCELLED'}
        chain.particles.add()
        chain.active_particle_index = len(chain.particles) - 1
        return {'FINISHED'}

class DANGLE_OT_remove_particle(bpy.types.Operator):
    bl_idname = "dangle.remove_particle"
    bl_label = "Remove Particle"

    def execute(self, context):
        chain = get_active_chain(context)
        if not chain or not chain.particles:
            return {'CANCELLED'}
        chain.particles.remove(chain.active_particle_index)
        if chain.active_particle_index > 0:
            chain.active_particle_index -= 1
        return {'FINISHED'}

def _copy_shape(source, target):
    target.name = source.name
    target.bone_name = source.bone_name
    target.shape_type = source.shape_type
    target.radius = source.radius
    target.x_box_extent = source.x_box_extent
    target.y_box_extent = source.y_box_extent
    target.height_extent = source.height_extent
    target.offset_ls = source.offset_ls
    target.rotation_ls_quat = source.rotation_ls_quat


class DANGLE_OT_add_shape(bpy.types.Operator):
    bl_idname = "dangle.add_shape"
    bl_label = "Add Node Shape"
    bl_options = {'UNDO'}

    def execute(self, context):
        rig = get_active_rig(context)
        dnode = get_active_dangle_node(context)
        if rig is None or dnode is None:
            return {'CANCELLED'}
        if not dnode.collision_shapes and rig.dangle_state.collision_shapes:
            for legacy_shape in rig.dangle_state.collision_shapes:
                _copy_shape(legacy_shape, dnode.collision_shapes.add())
        dnode.collision_shapes.add()
        dnode.active_shape_index = len(dnode.collision_shapes) - 1
        return {'FINISHED'}


class DANGLE_OT_remove_shape(bpy.types.Operator):
    bl_idname = "dangle.remove_shape"
    bl_label = "Remove Node Shape"
    bl_options = {'UNDO'}

    def execute(self, context):
        dnode = get_active_dangle_node(context)
        if dnode is None or not dnode.collision_shapes:
            return {'CANCELLED'}
        dnode.collision_shapes.remove(dnode.active_shape_index)
        dnode.active_shape_index = min(
            dnode.active_shape_index, max(0, len(dnode.collision_shapes) - 1)
        )
        return {'FINISHED'}

def _get_active_particle(context):
    chain = get_active_chain(context)
    if not chain or not chain.particles:
        return None
    idx = chain.active_particle_index
    if 0 <= idx < len(chain.particles):
        return chain.particles[idx]
    return None

class DANGLE_OT_add_link(bpy.types.Operator):
    bl_idname = "dangle.add_link"
    bl_label = "Add Dyng Link"

    def execute(self, context):
        p = _get_active_particle(context)
        if not p:
            return {'CANCELLED'}
        p.link_constraints.add()
        return {'FINISHED'}

class DANGLE_OT_remove_link(bpy.types.Operator):
    bl_idname = "dangle.remove_link"
    bl_label = "Remove Link"
    index: IntProperty()

    def execute(self, context):
        p = _get_active_particle(context)
        if not p:
            return {'CANCELLED'}
        p.link_constraints.remove(self.index)
        return {'FINISHED'}

class DANGLE_OT_add_ellipsoid(bpy.types.Operator):
    bl_idname = "dangle.add_ellipsoid"
    bl_label = "Add Ellipsoid"

    def execute(self, context):
        p = _get_active_particle(context)
        if not p:
            return {'CANCELLED'}
        p.ellipsoid_constraints.add()
        return {'FINISHED'}

class DANGLE_OT_remove_ellipsoid(bpy.types.Operator):
    bl_idname = "dangle.remove_ellipsoid"
    bl_label = "Remove Ellipsoid"
    index: IntProperty()

    def execute(self, context):
        p = _get_active_particle(context)
        if not p:
            return {'CANCELLED'}
        p.ellipsoid_constraints.remove(self.index)
        return {'FINISHED'}

class DANGLE_OT_add_pendulum(bpy.types.Operator):
    bl_idname = "dangle.add_pendulum"
    bl_label = "Add Pendulum"

    def execute(self, context):
        p = _get_active_particle(context)
        if not p:
            return {'CANCELLED'}
        p.pendulum_constraints.add()
        return {'FINISHED'}

class DANGLE_OT_remove_pendulum(bpy.types.Operator):
    bl_idname = "dangle.remove_pendulum"
    bl_label = "Remove Pendulum"
    index: IntProperty()

    def execute(self, context):
        p = _get_active_particle(context)
        if not p:
            return {'CANCELLED'}
        p.pendulum_constraints.remove(self.index)
        return {'FINISHED'}

class DANGLE_OT_copy_chain(bpy.types.Operator):
    bl_idname = "dangle.copy_chain"
    bl_label = "Copy Chain"

    def execute(self, context):
        dnode = get_active_dangle_node(context)
        if not dnode or not dnode.chains:
            return {'CANCELLED'}
        
        src_ch = dnode.chains[dnode.active_chain]
        new_ch = dnode.chains.add()
        new_ch.name = src_ch.name + "_copy"
        new_ch.solver = src_ch.solver
        
        for src_p in src_ch.particles:
            new_p = new_ch.particles.add()
            new_p.bone_name = src_p.bone_name
            new_p.mass = src_p.mass
            new_p.damping = src_p.damping
            new_p.pull_force = src_p.pull_force
            new_p.is_pinned = src_p.is_pinned
            new_p.capsule_radius = src_p.capsule_radius
            new_p.capsule_height = src_p.capsule_height
            new_p.capsule_axis_ls = src_p.capsule_axis_ls
            new_p.dyng_projection_type = src_p.dyng_projection_type
            new_p.pos_projection_type = src_p.pos_projection_type
            new_p.direction_reference_bone = src_p.direction_reference_bone
            new_p.spring_simulation_fps = src_p.spring_simulation_fps
            new_p.spring_constraint_radius = src_p.spring_constraint_radius
            new_p.spring_constraint_scale1 = src_p.spring_constraint_scale1
            new_p.spring_constraint_scale2 = src_p.spring_constraint_scale2
            new_p.spring_constraint_orientation = src_p.spring_constraint_orientation
            new_p.spring_pull_force_origin_ls = src_p.spring_pull_force_origin_ls
            new_p.spring_projection_type = src_p.spring_projection_type
            new_p.spring_collision_radius = src_p.spring_collision_radius
            new_p.pendulum_simulation_fps = src_p.pendulum_simulation_fps
            new_p.pendulum_constraint_type = src_p.pendulum_constraint_type
            new_p.pendulum_half_aperture_angle = src_p.pendulum_half_aperture_angle
            new_p.pendulum_constraint_orientation = src_p.pendulum_constraint_orientation
            new_p.pendulum_pull_force_direction_ls = src_p.pendulum_pull_force_direction_ls
            new_p.pendulum_projection_type = src_p.pendulum_projection_type
            new_p.pendulum_collision_radius = src_p.pendulum_collision_radius
            new_p.pendulum_collision_height = src_p.pendulum_collision_height
            
            for src_link in src_p.link_constraints:
                new_link = new_p.link_constraints.add()
                new_link.target_bone = src_link.target_bone
                new_link.link_type = src_link.link_type
                new_link.lower_ratio = src_link.lower_ratio
                new_link.upper_ratio = src_link.upper_ratio
                new_link.explicit_rest_distance = src_link.explicit_rest_distance
                new_link.stiffness = src_link.stiffness
                new_link.look_at_axis = src_link.look_at_axis
                
            for src_ell in src_p.ellipsoid_constraints:
                new_ell = new_p.ellipsoid_constraints.add()
                new_ell.target_bone = src_ell.target_bone
                new_ell.radius = src_ell.radius
                new_ell.scale1 = src_ell.scale1
                new_ell.scale2 = src_ell.scale2
                new_ell.ellipsoid_transform_ls_quat = src_ell.ellipsoid_transform_ls_quat
                new_ell.ellipsoid_transform_ls_offset = src_ell.ellipsoid_transform_ls_offset
                
            for src_pen in src_p.pendulum_constraints:
                new_pen = new_p.pendulum_constraints.add()
                new_pen.target_bone = src_pen.target_bone
                new_pen.constraint_type = src_pen.constraint_type
                new_pen.half_aperture_angle = src_pen.half_aperture_angle
                new_pen.projection_type = src_pen.projection_type
                new_pen.cone_collision_radius = src_pen.cone_collision_radius
                new_pen.cone_collision_height = src_pen.cone_collision_height
                new_pen.cone_transform_ls_quat = src_pen.cone_transform_ls_quat
                new_pen.cone_transform_ls_offset = src_pen.cone_transform_ls_offset
                
        dnode.active_chain = len(dnode.chains) - 1
        return {'FINISHED'}

class DANGLE_OT_add_selected_bones_to_chain(bpy.types.Operator):
    bl_idname = "dangle.add_selected_bones_to_chain"
    bl_label = "Add Selected Bones"

    def execute(self, context):
        chain = get_active_chain(context)
        if not chain:
            return {'CANCELLED'}
        
        added = 0
        if context.active_object and context.active_object.type == 'ARMATURE' and context.active_object.mode == 'POSE':
            selected_bones = list(context.selected_pose_bones)
            if chain.solver in {'PBD', 'SPRING', 'PENDULUM'}:
                solver_name = {
                    'PBD': 'Position Projection',
                    'SPRING': 'Spring',
                    'PENDULUM': 'Pendulum',
                }[chain.solver]
                if chain.particles:
                    self.report({'WARNING'}, f"{solver_name} supports one bone only.")
                    return {'CANCELLED'}
                if len(selected_bones) != 1:
                    self.report({'WARNING'}, f"Select exactly one bone for {solver_name}.")
                    return {'CANCELLED'}
            for pb in selected_bones:
                p = chain.particles.add()
                p.bone_name = pb.name
                added += 1
        else:
            self.report({'WARNING'}, "Must be in Pose Mode with bones selected.")
            return {'CANCELLED'}
            
        if added > 0:
            chain.active_particle_index = len(chain.particles) - 1
            self.report({'INFO'}, f"Added {added} bones to chain.")
            
        return {'FINISHED'}

classes = (
    DANGLE_OT_copy_chain,
    DANGLE_OT_add_selected_bones_to_chain,
    DANGLE_OT_enable_rig,
    DANGLE_OT_disable_rig,
    DANGLE_OT_preview_play,
    DANGLE_OT_preview_stop,
    DANGLE_OT_bake_to_keyframes,
    DANGLE_OT_import_json,
    DANGLE_OT_export_json,
    DANGLE_OT_add_dangle_node,
    DANGLE_OT_remove_dangle_node,
    DANGLE_OT_add_chain,
    DANGLE_OT_remove_chain,
    DANGLE_OT_add_particle,
    DANGLE_OT_remove_particle,
    DANGLE_OT_add_shape,
    DANGLE_OT_remove_shape,
    DANGLE_OT_add_link,
    DANGLE_OT_remove_link,
    DANGLE_OT_add_ellipsoid,
    DANGLE_OT_remove_ellipsoid,
    DANGLE_OT_add_pendulum,
    DANGLE_OT_remove_pendulum,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for session in list(_ACTIVE_PREVIEW_SESSIONS.values()):
        session._finish(bpy.context, restore_pose=True)
    _ACTIVE_PREVIEW_SESSIONS.clear()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)