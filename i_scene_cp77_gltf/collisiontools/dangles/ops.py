import bpy
import time
from bpy.props import StringProperty, IntProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper
from .sim import core, solvers
from . import draw, io
from .ui import get_active_rig, get_active_dangle_node, get_active_chain

class DANGLE_OT_enable_rig(bpy.types.Operator):
    bl_idname = "dangle.enable_rig"
    bl_label = "Enable Dangle Physics on Armature"

    def execute(self, context):
        if context.active_object and context.active_object.type == 'ARMATURE':
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

        st.is_playing = False
        rig_id = f"{rig.name}"
        if rig_id in draw._DRAW_CACHES:
            del draw._DRAW_CACHES[rig_id]

        st.dangle_nodes.clear()
        st.collision_shapes.clear()
        st.drag_nodes.clear()
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
    _last_time = 0.0

    def modal(self, context, event):
        rig = get_active_rig(context)
        if not rig or event.type == 'ESC' or not rig.dangle_state.is_playing:
            return self.cancel(context)

        if event.type == 'TIMER':
            current_time = time.time()
            dt = min(current_time - self._last_time, 0.1)
            self._last_time = current_time

            solvers.update_simulation(self._simulator, dt, time_dilation=1.0)
            draw.update_draw_cache(f"{rig.name}", self._simulator)

            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

        return {'PASS_THROUGH'}

    def execute(self, context):
        rig = get_active_rig(context)
        if not rig:
            return {'CANCELLED'}
        st = rig.dangle_state
        if not st.dangle_nodes:
            self.report({'WARNING'}, "No dangle nodes imported.")
            return {'CANCELLED'}

        self._simulator = core.DyngSimulator(rig)
        self._last_time = time.time()

        wm = context.window_manager
        self._timer = wm.event_timer_add(1.0 / 60.0, window=context.window)
        wm.modal_handler_add(self)
        st.is_playing = True

        return {'RUNNING_MODAL'}

    def cancel(self, context):
        rig = get_active_rig(context)
        if rig:
            rig.dangle_state.is_playing = False
            rig_id = f"{rig.name}"
            if rig_id in draw._DRAW_CACHES:
                del draw._DRAW_CACHES[rig_id]

        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        self._simulator = None
        return {'CANCELLED'}

class DANGLE_OT_preview_stop(bpy.types.Operator):
    bl_idname = "dangle.preview_stop"
    bl_label = "Stop Simulation"

    def execute(self, context):
        rig = get_active_rig(context)
        if rig:
            rig.dangle_state.is_playing = False
        return {'FINISHED'}

class DANGLE_OT_bake_to_keyframes(bpy.types.Operator):
    bl_idname = "dangle.bake_to_keyframes"
    bl_label = "Bake to Keyframes"

    def execute(self, context):
        rig = get_active_rig(context)
        if not rig:
            return {'CANCELLED'}
        st = rig.dangle_state
        if not st.dangle_nodes:
            self.report({'WARNING'}, "No dangle nodes imported.")
            return {'CANCELLED'}

        simulator = core.DyngSimulator(rig)
        scene = context.scene
        dt = (1.0 / scene.render.fps) * scene.render.fps_base

        bpy.ops.object.select_all(action='DESELECT')
        rig.select_set(True)
        context.view_layer.objects.active = rig
        if rig.mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')

        if not rig.animation_data:
            rig.animation_data_create()
        if not rig.animation_data.action:
            action = bpy.data.actions.new(name=f"{rig.name}_DangleBake")
            rig.animation_data.action = action

        for frame in range(scene.frame_start, scene.frame_end + 1):
            scene.frame_set(frame)
            solvers.update_simulation(simulator, dt)

            for i, p in enumerate(simulator.particles):
                if simulator.is_free[i] and simulator.active_mask[i]:
                    pb = rig.pose.bones.get(p.bone_name)
                    if pb:
                        pb.keyframe_insert(data_path="location", frame=frame)
                        pb.keyframe_insert(
                            data_path="rotation_quaternion", frame=frame
                        )
                        dnode = simulator.particle_dnode_map[i]
                        if getattr(dnode, 'rotate_parent_to_look_at', True) and pb.parent:
                            pb.parent.keyframe_insert(
                                data_path="rotation_quaternion", frame=frame
                            )

        self.report({'INFO'}, f"Baked frames {scene.frame_start}-{scene.frame_end}.")
        return {'FINISHED'}

class DANGLE_OT_import_json(bpy.types.Operator, ImportHelper):
    bl_idname = "dangle.import_json"
    bl_label = "Import JSON"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={'HIDDEN'})

    def execute(self, context):
        rig = get_active_rig(context)
        if not rig:
            self.report({'ERROR'}, "No active Dangle Rig selected.")
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
    bl_label = "Export JSON"
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

class DANGLE_OT_add_shape(bpy.types.Operator):
    bl_idname = "dangle.add_shape"
    bl_label = "Add Shape"

    def execute(self, context):
        rig = get_active_rig(context)
        if not rig:
            return {'CANCELLED'}
        st = rig.dangle_state
        st.collision_shapes.add()
        st.active_shape_index = len(st.collision_shapes) - 1
        return {'FINISHED'}

class DANGLE_OT_remove_shape(bpy.types.Operator):
    bl_idname = "dangle.remove_shape"
    bl_label = "Remove Shape"

    def execute(self, context):
        rig = get_active_rig(context)
        if not rig:
            return {'CANCELLED'}
        st = rig.dangle_state
        if st.collision_shapes:
            st.collision_shapes.remove(st.active_shape_index)
            if st.active_shape_index > 0:
                st.active_shape_index -= 1
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

classes = (
    DANGLE_OT_enable_rig,
    DANGLE_OT_disable_rig,
    DANGLE_OT_preview_play,
    DANGLE_OT_preview_stop,
    DANGLE_OT_bake_to_keyframes,
    DANGLE_OT_import_json,
    DANGLE_OT_export_json,
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
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)