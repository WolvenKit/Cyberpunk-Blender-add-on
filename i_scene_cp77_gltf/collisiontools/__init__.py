import bpy
import sys
from mathutils import Vector, Matrix
from .dangles.ui import get_active_rig
from . import pxbridge
from . import dangles

class CP77_PT_PhysicsTools(bpy.types.Panel):
    bl_label = "Physics Tools"
    bl_idname = "CP77_PT_physics"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CP77 Modding"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences
        if cp77_addon_prefs.context_only:
            return context.active_object and context.active_object.type == 'MESH' 
        else:
            return context

    def draw(self, context):
        layout = self.layout
        cp77_addon_prefs = bpy.context.preferences.addons['i_scene_cp77_gltf'].preferences

        if not cp77_addon_prefs.show_modtools or not cp77_addon_prefs.show_physicstools:
            return

        l = layout
        px_s = context.scene.physx
        
        if not px_s.is_initialized:
            l.operator("physx.init_scene", icon='PLAY', text="Initialize PhysX")
            return
            
        row = l.row()
        l.prop(px_s, "viz_enabled", text="Draw Colliders")
        row.prop(px_s, "ui_tab", expand=True)

        if px_s.ui_tab == 'WORLD':
            # Environment settings
            gbox = l.box()
            gbox.label(text="Environment", icon='WORLD_DATA')
            gbox.prop(px_s, "gravity")
            gbox.operator("physx.update_gravity", icon='FORCE_FORCE', text="Update Gravity")
            
            rig = get_active_rig(context)
            if rig:
                st = rig.dangle_state
                gbox.prop(st, "gravity_scale", text="Dangle Gravity Scale")
                gbox.prop(st, "external_force_ws", text="Dangle Wind/Force")
                gbox.prop(st, "substep_time", text="Dangle Substep Time")

            # Interaction tools
            fbox = l.box()
            fbox.label(text="Interaction")
            r = fbox.row()

            if not px_s.use_grab_mode:
                fbox.prop(px_s, "force_mode")
                fbox.prop(px_s, "use_force_pos", icon='CURSOR')
                row = fbox.row()
                row.prop(px_s, "force_value")
                row.operator("physx.apply_force", icon='FORCE_LENNARDJONES', text="Apply Force")

            io_box = l.box()
            io_box.label(text="Export to Phys")
            r = io_box.row()
            r.operator("physx.export_phys", icon='EXPORT')
            r.operator("physx.import_phys", icon='IMPORT')

        elif px_s.ui_tab == 'ACTORS':
            # Main actor list
            row = l.row()
            row.template_list("PHYSX_UL_actor_list", "", px_s, "actors", px_s, "actor_list_index")
            col = row.column(align=True)
            col.operator("physx.list_action", icon='ADD', text="").action = 'ADD'
            col.operator("physx.list_action", icon='REMOVE', text="").action = 'REMOVE'

            # Active actor details
            if len(px_s.actors) > 0 and px_s.actor_list_index < len(px_s.actors):
                item = px_s.actors[px_s.actor_list_index]
                obj = item.obj_ref
                if obj:
                    px = obj.physx

                    # Actor settings panel
                    header_set, panel_set = l.panel("physx_actor_settings", default_closed=True)
                    header_set.label(text="Actor Settings")

                    if panel_set:
                        panel_set.label(text=obj.name, icon='EDITMODE_HLT')
                        panel_set.prop(px, "is_terrain", text="Is Terrain")

                        # Dynamics sub-panel
                        header_dyn, panel_dyn = panel_set.panel("physx_actor_dynamics", default_closed=True)
                        header_dyn.label(text="Dynamics")

                        if panel_dyn:
                            r = panel_dyn.row()
                            r.prop(px, "calc_mass", toggle=True)
                            r.prop(px, "calc_offset", toggle=True)
                            r.prop(px, "calc_inertia", toggle=True)
                            panel_dyn.operator("physx.calc_dynamics", icon='PREFERENCES')

                            col = panel_dyn.column()
                            col.active = not px.calc_mass
                            col.prop(px, "mass")

                            col = panel_dyn.column()
                            col.active = not px.calc_offset
                            col.prop(px, "com_offset")

                            col = panel_dyn.column()
                            col.active = not px.calc_inertia
                            col.prop(px, "inertia")

                    # Colliders panel
                    header_col, panel_col = l.panel("physx_colliders", default_closed=True)
                    header_col.label(text="Colliders")

                    if panel_col:
                        # Shapes list
                        header_shp, panel_shp = panel_col.panel("physx_shapes_list", default_closed=True)
                        header_shp.label(text="Shapes")
                        header_shp.operator("physx.shape_action", icon='ADD', text="").action = 'ADD'
                        header_shp.operator("physx.shape_action", icon='REMOVE', text="").action = 'REMOVE'

                        if panel_shp:
                            row = panel_shp.row()
                            row.template_list("PHYSX_UL_shape_list", "", px, "shapes", px, "shape_index")

                        if len(px.shapes) > 0 and px.shape_index < len(px.shapes):
                            shape = px.shapes[px.shape_index]

                            shp_box = panel_col.box()
                            shp_box.label(text="Shape Properties")
                            r = shp_box.row(align=True)
                            r.prop(shape, "name", text="Name: ")
                            r = shp_box.row(align=True)
                            r.prop(shape, "physics_material", text="Material: ")
                            r = shp_box.row(align=True)
                            r.prop(shape, "collision_preset", text="Filter: ")

                            # Dimensions
                            shp_box = panel_col.box()
                            r = shp_box.row(align=True)
                            r.label(text="Dimensions: ")
                            r = shp_box.row(align=True)
                            r.operator("physx.fit_bounds_shape", icon='FULLSCREEN_ENTER', text="Fit to Bounds")
                            r = shp_box.row(align=True)
                            if shape.shape_type == 'BOX':
                                r.prop(shape, "dim_x", text="X")
                                r.prop(shape, "dim_y", text="Y")
                                r.prop(shape, "dim_z", text="Z")
                            elif shape.shape_type in ('SPHERE', 'CAPSULE'):
                                r.prop(shape, "dim_x", text="R")

                            if shape.shape_type == 'CAPSULE':
                                r.prop(shape, "dim_y", text="H-H")
                            if shape.shape_type == 'HEIGHTFIELD':
                                r.prop(shape, "hf_resolution")

                            # Mesh processing
                            if shape.shape_type in ('CONVEX', 'TRIANGLE', 'HEIGHTFIELD'):
                                cbox = panel_col.box()
                                cbox.label(text="Processing")
                                cbox.prop(shape, "vertex_limit")
                                cbox.operator("physx.cook_mesh", icon='SCULPTMODE_HLT')
                                if shape.is_cooked:
                                    cbox.label(text="Cooked", icon='CHECKMARK')
                                    row = cbox.row(align=True)
                                    row.operator("physx.save_cooked", icon='FILE_TICK', text="Save")
                                    row.operator("physx.load_cooked", icon='FILE_FOLDER', text="Load")
                                else:
                                    cbox.label(text="Needs Processing", icon='ERROR')

                            # Local transforms
                            header_trn, panel_trn = panel_col.panel("physx_transforms", default_closed=True)
                            header_trn.label(text="Local Transform")

                            if panel_trn:
                                # Bone parent target
                                if item.poll_armature_availability():
                                    box = panel_trn.box()
                                    box.label(text="Transform Target (Bone)", icon='BONE_DATA')
                                    box.prop(item, "use_bone_parent", text="Use Bone Parent", toggle=True)
                                    if item.use_bone_parent:
                                        col = box.column()
                                        col.prop(item, "parent_armature", text="Armature")
                                        if item.parent_armature and item.parent_armature != "NONE":
                                            col.prop(item, "target_bone", text="Bone")
                                            if item.target_bone and item.target_bone != "NONE":
                                                pass
                                        else:
                                            col.label(text="Select an armature first", icon='ERROR')

                                # Local offset
                                box = panel_trn.box()
                                box.label(text="Local Transform")
                                box.prop(shape, "local_pos")
                                box.prop(shape, "local_rot")

        elif px_s.ui_tab == 'SIM':
            r = l.row()
            if px_s.sim_running:
                r.operator("physx.stop_sim", icon='PAUSE', text="Stop")
            else:
                r.operator("physx.sim_step", icon='PLAY', text="Start")
            l.prop(px_s, "sim_steps", text="Step Count")
            r = l.row()
            r.operator("physx.build_scene", text="Rebuild Scene", icon='FILE_REFRESH')
            r.operator("physx.run_steps", icon='NEXT_KEYFRAME', text="Step N")

        elif px_s.ui_tab == 'DANGLES':
            row = l.row()
            row.template_list(
                "DANGLE_UL_rigs", "",
                context.scene, "objects",
                context.scene, "dangle_active_rig_index",
            )
            col = row.column(align=True)
            col.operator("dangle.enable_rig", icon='ADD', text="")
            col.operator("dangle.disable_rig", icon='REMOVE', text="")

            rig = get_active_rig(context)
            if not rig:
                return

            st = rig.dangle_state

            row = l.row(align=True)
            row.operator("dangle.import_json", icon='IMPORT', text="Import")
            row.operator("dangle.export_json", icon='EXPORT', text="Export")

            l.separator()
            row = l.row(align=True)
            if st.is_playing:
                row.operator("dangle.preview_stop", icon='PAUSE', text="Stop Simulation")
            else:
                row.operator("dangle.preview_play", icon='PLAY', text="Play Simulation")
            row.operator("dangle.bake_to_keyframes", icon='KEYINGSET', text="Bake")

            # Global visibility toggles
            if px_s.viz_enabled:
                l.separator()
                box = l.box()
                box.label(text="Overlays", icon='OVERLAY')
                row = box.row(align=True)
                row.prop(st, "show_global_body_shapes", toggle=True, text="Bodies")
                row.prop(st, "show_global_capsules", toggle=True, text="Capsules")
                row = box.row(align=True)
                row.prop(st, "show_global_constraints", toggle=True, text="Links")
                row.prop(st, "show_global_cones", toggle=True, text="Cones")
                row.prop(st, "show_global_velocity", toggle=True, text="Vel")

classes = [CP77_PT_PhysicsTools]

def register_collisiontools():
    for cls in classes:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)
    pxbridge.register()
    dangles.register()

def unregister_collisiontools():
    dangles.unregister()
    pxbridge.unregister()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)