import bpy
from mathutils import Matrix, Vector

from . import dangles, pxbridge
from .dangles.ui import get_active_chain, get_active_dangle_node, get_active_rig


def _active_item(collection, index):
    if not collection:
        return None
    return collection[index] if 0 <= index < len(collection) else None


def _draw_dangle_nodes(layout, context, rig):
    st = rig.dangle_state
    header, panel = layout.panel("cp77_dangle_nodes", default_closed=False)
    header.label(text="Dangle Nodes", icon='PHYSICS')
    if panel is None:
        return

    row = panel.row()
    row.template_list(
            "DANGLE_UL_dangle_nodes", "",
            st, "dangle_nodes",
            st, "active_dangle_node",
            )
    col = row.column(align=True)
    col.operator("dangle.add_node", icon='ADD', text="")
    col.operator("dangle.remove_node", icon='REMOVE', text="")

    if st.evaluation_order:
        order_box = panel.box()
        order_box.label(text="Graph Evaluation Order", icon='NODETREE')
        for order_index, operation in enumerate(st.evaluation_order):
            if operation.node_type == 'DANGLE':
                node = _active_item(st.dangle_nodes, operation.node_index)
                label = node.name if node is not None else f"Dangle {operation.node_index}"
                icon = 'PHYSICS'
            else:
                node = _active_item(st.drag_nodes, operation.node_index)
                label = (
                    node.bone_name if node is not None
                    else f"Drag {operation.node_index}"
                )
                icon = 'CON_FOLLOWPATH'
            order_box.label(
                    text=f"{order_index + 1}. {operation.node_type.title()}: {label}",
                    icon=icon,
                    )

    dnode = get_active_dangle_node(context)
    if dnode is None:
        return

    chain = get_active_chain(context)
    solver = chain.solver if chain is not None else 'DYNG'

    box = panel.box()
    box.label(text=f"Node Settings — {solver}", icon='PREFERENCES')
    if solver == 'DYNG':
        col = box.column(align=True)
        col.prop(dnode, "substep_time")
        col.prop(dnode, "solver_iterations")
        col.prop(dnode, "gravity_ws")
        col.prop(dnode, "external_force_ws")
    elif solver == 'PBD':
        box.label(text="Pose projection; no time integration.", icon='CON_KINEMATIC')
    elif solver == 'SPRING':
        box.label(text="Single-bone spring-mass simulation.", icon='PHYSICS')
        col = box.column(align=True)
        col.prop(dnode, "gravity_ws")
        col.prop(dnode, "external_force_ws")
    elif solver == 'PENDULUM':
        box.label(text="Single-bone fixed-length pendulum.", icon='CON_ROTLIMIT')
        col = box.column(align=True)
        col.prop(dnode, "gravity_ws")
        col.prop(dnode, "external_force_ws")

    box.prop(dnode, "alpha")
    box.prop(dnode, "rotate_parent_to_look_at")
    if dnode.rotate_parent_to_look_at:
        box.prop(dnode, "look_at_axis")

    advanced = box.column(align=True)
    advanced.prop(dnode, "parent_rotation_alters_dangle_children")
    advanced.prop(dnode, "parent_rotation_alters_non_dangle_children")
    advanced.prop(dnode, "dangle_alters_children")


def _draw_dangle_chains(layout, context):
    dnode = get_active_dangle_node(context)
    if dnode is None:
        return

    header, panel = layout.panel("cp77_dangle_chains", default_closed=False)
    header.label(text="Chains", icon='LINKED')
    if panel is None:
        return

    row = panel.row()
    row.template_list(
            "DANGLE_UL_chains", "",
            dnode, "chains",
            dnode, "active_chain",
            )
    col = row.column(align=True)
    col.operator("dangle.add_chain", icon='ADD', text="")
    col.operator("dangle.remove_chain", icon='REMOVE', text="")
    col.operator("dangle.copy_chain", icon='DUPLICATE', text="")

    chain = get_active_chain(context)
    if chain is None:
        return

    panel.prop(chain, "solver")
    if chain.solver not in {'DYNG', 'PBD', 'SPRING', 'PENDULUM'}:
        panel.label(text="Preview and bake do not support this solver yet.", icon='ERROR')
    elif chain.solver == 'PBD' and len(chain.particles) != 1:
        panel.label(text="Position Projection requires exactly one bone.", icon='ERROR')
    elif chain.solver == 'SPRING' and len(chain.particles) != 1:
        panel.label(text="Spring requires exactly one bone.", icon='ERROR')
    elif chain.solver == 'PENDULUM' and len(chain.particles) != 1:
        panel.label(text="Pendulum requires exactly one bone.", icon='ERROR')


def _draw_dangle_particles(layout, context, rig):
    chain = get_active_chain(context)
    if chain is None:
        return

    header, panel = layout.panel("cp77_dangle_particles", default_closed=False)
    header.label(text="Particles & Constraints", icon='BONE_DATA')
    if panel is None:
        return

    row = panel.row()
    row.template_list(
            "DANGLE_UL_particles", "",
            chain, "particles",
            chain, "active_particle_index",
            )
    col = row.column(align=True)
    col.operator("dangle.add_particle", icon='ADD', text="")
    col.operator("dangle.remove_particle", icon='REMOVE', text="")
    col.operator("dangle.add_selected_bones_to_chain", icon='BONE_DATA', text="")

    particle = _active_item(chain.particles, chain.active_particle_index)
    if particle is None:
        return

    if chain.solver == 'PBD':
        box = panel.box()
        box.label(text="Position Projection", icon='CON_KINEMATIC')
        box.prop_search(particle, "bone_name", rig.data, "bones", text="Dangle Bone")
        box.prop(particle, "pos_projection_type")
        if particle.pos_projection_type == 'DIRECTIONAL':
            box.prop_search(
                    particle, "direction_reference_bone", rig.data, "bones",
                    text="Direction Reference",
                    )
            box.prop(particle, "capsule_axis_ls", text="Fallback Axis (LS)")
            box.prop(particle, "capsule_height")
        box.prop(particle, "capsule_radius")
        return

    if chain.solver == 'PENDULUM':
        box = panel.box()
        box.label(text="Pendulum", icon='CON_ROTLIMIT')
        box.prop_search(particle, "bone_name", rig.data, "bones", text="Dangle Bone")
        col = box.column(align=True)
        col.prop(particle, "pendulum_simulation_fps")
        col.prop(particle, "mass")
        col.prop(particle, "damping")
        col.prop(particle, "pull_force")
        box.prop(particle, "pendulum_pull_force_direction_ls")

        box = panel.box()
        box.label(text="Angular Constraint", icon='CON_ROTLIMIT')
        box.prop(particle, "pendulum_constraint_type")
        box.prop(particle, "pendulum_half_aperture_angle")
        box.prop(particle, "pendulum_constraint_orientation")

        box = panel.box()
        box.label(text="Collision", icon='MESH_CAPSULE')
        box.prop(particle, "pendulum_projection_type")
        if particle.pendulum_projection_type != 'DISABLED':
            box.prop(particle, "pendulum_collision_radius")
            box.prop(particle, "pendulum_collision_height")
        return

    if chain.solver == 'SPRING':
        box = panel.box()
        box.label(text="Spring", icon='PHYSICS')
        box.prop_search(particle, "bone_name", rig.data, "bones", text="Dangle Bone")
        col = box.column(align=True)
        col.prop(particle, "spring_simulation_fps")
        col.prop(particle, "mass")
        col.prop(particle, "damping")
        col.prop(particle, "pull_force")
        box.prop(particle, "spring_pull_force_origin_ls")

        box = panel.box()
        box.label(text="Constraint Ellipsoid", icon='MESH_UVSPHERE')
        col = box.column(align=True)
        col.prop(particle, "spring_constraint_radius")
        col.prop(particle, "spring_constraint_scale1")
        col.prop(particle, "spring_constraint_scale2")
        box.prop(particle, "spring_constraint_orientation")

        box = panel.box()
        box.label(text="Collision", icon='CON_KINEMATIC')
        box.prop(particle, "spring_projection_type")
        if particle.spring_projection_type != 'DISABLED':
            box.prop(particle, "spring_collision_radius")
        return

    box = panel.box()
    box.label(text="Physics", icon='PHYSICS')
    box.prop_search(particle, "bone_name", rig.data, "bones", text="Target Bone")
    col = box.column(align=True)
    col.prop(particle, "mass")
    col.prop(particle, "damping")
    col.prop(particle, "pull_force")

    box = panel.box()
    box.label(text="Collision Geometry", icon='MESH_CAPSULE')
    col = box.column(align=True)
    col.prop(particle, "capsule_radius")
    col.prop(particle, "capsule_height")
    box.prop(particle, "capsule_axis_ls")

    box = panel.box()
    box.label(text="Projections", icon='CON_KINEMATIC')
    box.prop(particle, "dyng_projection_type")

    box = panel.box()
    row = box.row()
    row.label(text="Dyng Links", icon='CONSTRAINT')
    row.operator("dangle.add_link", icon='ADD', text="")
    for index, link in enumerate(particle.link_constraints):
        sub = box.box()
        row = sub.row(align=True)
        row.prop_search(link, "target_bone", rig.data, "bones", text="")
        row.prop(link, "link_type", text="")
        remove = row.operator("dangle.remove_link", icon='X', text="")
        remove.index = index
        if link.link_type != 'FIXED':
            col = sub.column(align=True)
            col.prop(link, "lower_ratio")
            col.prop(link, "upper_ratio")
        col = sub.column(align=True)
        col.prop(link, "explicit_rest_distance")
        col.prop(link, "stiffness")
        col.prop(link, "look_at_axis")

    box = panel.box()
    row = box.row()
    row.label(text="Ellipsoid Volumes", icon='MESH_UVSPHERE')
    row.operator("dangle.add_ellipsoid", icon='ADD', text="")
    for index, ellipsoid in enumerate(particle.ellipsoid_constraints):
        sub = box.box()
        row = sub.row(align=True)
        row.prop_search(ellipsoid, "target_bone", rig.data, "bones", text="")
        remove = row.operator("dangle.remove_ellipsoid", icon='X', text="")
        remove.index = index
        col = sub.column(align=True)
        col.prop(ellipsoid, "radius")
        col.prop(ellipsoid, "scale1")
        col.prop(ellipsoid, "scale2")
        col.prop(ellipsoid, "ellipsoid_transform_ls_quat", text="LS Quat (wxyz)")
        col.prop(ellipsoid, "ellipsoid_transform_ls_offset", text="LS Offset")

    box = panel.box()
    row = box.row()
    row.label(text="Cone Constraints", icon='CON_ROTLIMIT')
    row.operator("dangle.add_pendulum", icon='ADD', text="")
    for index, pendulum in enumerate(particle.pendulum_constraints):
        sub = box.box()
        row = sub.row(align=True)
        row.prop_search(pendulum, "target_bone", rig.data, "bones", text="")
        row.prop(pendulum, "constraint_type", text="")
        remove = row.operator("dangle.remove_pendulum", icon='X', text="")
        remove.index = index
        col = sub.column(align=True)
        col.prop(pendulum, "half_aperture_angle")
        col.prop(pendulum, "projection_type")
        col.prop(pendulum, "cone_transform_ls_quat", text="Cone LS Quat (wxyz)")
        col.prop(pendulum, "cone_transform_ls_offset", text="Cone LS Offset")
        col.prop(pendulum, "cone_collision_radius")
        col.prop(pendulum, "cone_collision_height")


def _draw_dangle_collision_shapes(layout, context, rig):
    dnode = get_active_dangle_node(context)
    if dnode is None:
        return

    header, panel = layout.panel("cp77_dangle_collision_shapes", default_closed=True)
    header.label(text="Node Collision Shapes", icon='MESH_UVSPHERE')
    if panel is None:
        return

    row = panel.row()
    row.template_list(
            "DANGLE_UL_collision_shapes", "",
            dnode, "collision_shapes",
            dnode, "active_shape_index",
            )
    col = row.column(align=True)
    col.operator("dangle.add_shape", icon='ADD', text="")
    col.operator("dangle.remove_shape", icon='REMOVE', text="")

    shape = _active_item(dnode.collision_shapes, dnode.active_shape_index)
    if shape is None:
        return

    box = panel.box()
    box.prop(shape, "name")
    box.prop_search(shape, "bone_name", rig.data, "bones", text="Bone")
    box.prop(shape, "shape_type")

    col = box.column(align=True)
    col.prop(shape, "radius")
    col.prop(shape, "x_box_extent")
    col.prop(shape, "y_box_extent")
    col.prop(shape, "height_extent")
    box.prop(shape, "offset_ls")
    box.prop(shape, "rotation_ls_quat", text="Rotation (wxyz)")


def _draw_drag_nodes(layout, rig):
    st = rig.dangle_state
    if not st.drag_nodes:
        return

    header, panel = layout.panel("cp77_dangle_drag_nodes", default_closed=True)
    header.label(text=f"Drag Nodes ({len(st.drag_nodes)})", icon='FORCE_DRAG')
    if panel is None:
        return

    for drag_node in st.drag_nodes:
        box = panel.box()
        box.prop_search(drag_node, "source_bone_name", rig.data, "bones", text="Source")
        box.prop_search(drag_node, "bone_name", rig.data, "bones", text="Output Target")
        col = box.column(align=True)
        col.prop(drag_node, "simulation_fps")
        col.prop(drag_node, "source_speed_multiplier")
        box.prop(drag_node, "has_overshoot")
        if drag_node.has_overshoot:
            col = box.column(align=True)
            col.prop(drag_node, "overshoot_detection_min_speed")
            col.prop(drag_node, "overshoot_detection_max_speed")
            col.prop(drag_node, "overshoot_duration")
        box.prop(drag_node, "use_steps")
        if drag_node.use_steps:
            col = box.column(align=True)
            col.prop(drag_node, "steps_target_speed_multiplier")
            col.prop(drag_node, "time_between_steps")
            col.prop(drag_node, "time_in_step")


def _draw_dangles(layout, context, px_s):
    row = layout.row()
    row.template_list(
            "DANGLE_UL_rigs", "",
            context.scene, "objects",
            context.scene, "dangle_active_rig_index",
            )
    col = row.column(align=True)
    col.operator("dangle.enable_rig", icon='ADD', text="")
    col.operator("dangle.disable_rig", icon='REMOVE', text="")

    rig = get_active_rig(context)
    if rig is None:
        layout.label(text="Select or enable an armature for Dangle editing.", icon='INFO')
        return

    st = rig.dangle_state

    row = layout.row(align=True)
    row.operator("dangle.import_json", icon='IMPORT', text="Import")
    row.operator("dangle.export_json", icon='EXPORT', text="Export")

    row = layout.row(align=True)
    if st.is_playing:
        row.operator("dangle.preview_stop", icon='PAUSE', text="Stop Simulation")
    else:
        row.operator("dangle.preview_play", icon='PLAY', text="Play Simulation")
    row.operator("dangle.bake_to_keyframes", icon='KEYINGSET', text="Bake")

    if px_s.viz_enabled:
        box = layout.box()
        box.label(text="Overlays", icon='OVERLAY')
        row = box.row(align=True)
        row.prop(st, "show_global_body_shapes", toggle=True, text="Bodies")
        row.prop(st, "show_global_capsules", toggle=True, text="Capsules")
        row = box.row(align=True)
        row.prop(st, "show_global_constraints", toggle=True, text="Links")
        row.prop(st, "show_global_cones", toggle=True, text="Cones")
        row.prop(st, "show_global_velocity", toggle=True, text="Vel")

    _draw_dangle_nodes(layout, context, rig)
    _draw_dangle_chains(layout, context)
    _draw_dangle_particles(layout, context, rig)
    _draw_dangle_collision_shapes(layout, context, rig)
    _draw_drag_nodes(layout, rig)


class CP77_PT_PhysicsTools(bpy.types.Panel):
    bl_label = "Physics Tools"
    bl_idname = "CP77_PT_physics"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CP77 Modding"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        cp77_addon_prefs = context.preferences.addons['i_scene_cp77_gltf'].preferences
        if not cp77_addon_prefs.context_only:
            return True

        active_object = context.active_object
        if active_object is None:
            return False
        if active_object.type == 'MESH':
            return True

        px_s = getattr(context.scene, "physx", None)
        return bool(active_object.type == 'ARMATURE' and px_s and px_s.ui_tab == 'DANGLES')

    def draw(self, context):
        layout = self.layout
        cp77_addon_prefs = context.preferences.addons['i_scene_cp77_gltf'].preferences

        if not cp77_addon_prefs.show_modtools or not cp77_addon_prefs.show_physicstools:
            return

        px_s = context.scene.physx

        row = layout.row(align=True)
        row.prop(px_s, "viz_enabled", text="Draw Colliders")
        row.prop(px_s, "ui_tab", expand=True)

        if px_s.ui_tab == 'DANGLES':
            _draw_dangles(layout, context, px_s)
            return

        if not px_s.is_initialized:
            layout.operator("physx.init_scene", icon='PLAY', text="Initialize PhysX")
            return

        if px_s.ui_tab == 'WORLD':
            gbox = layout.box()
            gbox.label(text="Environment", icon='WORLD_DATA')
            gbox.prop(px_s, "gravity")
            gbox.operator("physx.update_gravity", icon='FORCE_FORCE', text="Update Gravity")

            fbox = layout.box()
            fbox.label(text="Interaction")
            if not px_s.use_grab_mode:
                fbox.prop(px_s, "force_mode")
                fbox.prop(px_s, "use_force_pos", icon='CURSOR')
                row = fbox.row()
                row.prop(px_s, "force_value")
                row.operator("physx.apply_force", icon='FORCE_LENNARDJONES', text="Apply Force")

            io_box = layout.box()
            io_box.label(text="Export to Phys")
            row = io_box.row()
            row.operator("physx.export_phys", icon='EXPORT')
            row.operator("physx.import_phys", icon='IMPORT')

        elif px_s.ui_tab == 'ACTORS':
            row = layout.row()
            row.template_list("PHYSX_UL_actor_list", "", px_s, "actors", px_s, "actor_list_index")
            col = row.column(align=True)
            col.operator("physx.list_action", icon='ADD', text="").action = 'ADD'
            col.operator("physx.list_action", icon='REMOVE', text="").action = 'REMOVE'

            if len(px_s.actors) > 0 and px_s.actor_list_index < len(px_s.actors):
                item = px_s.actors[px_s.actor_list_index]
                obj = item.obj_ref
                if obj:
                    px = obj.physx

                    header_set, panel_set = layout.panel("physx_actor_settings", default_closed=True)
                    header_set.label(text="Actor Settings")
                    if panel_set:
                        panel_set.label(text=obj.name, icon='EDITMODE_HLT')
                        panel_set.prop(px, "is_terrain", text="Is Terrain")

                        header_dyn, panel_dyn = panel_set.panel("physx_actor_dynamics", default_closed=True)
                        header_dyn.label(text="Dynamics")
                        if panel_dyn:
                            row = panel_dyn.row()
                            row.prop(px, "calc_mass", toggle=True)
                            row.prop(px, "calc_offset", toggle=True)
                            row.prop(px, "calc_inertia", toggle=True)
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

                    header_col, panel_col = layout.panel("physx_colliders", default_closed=True)
                    header_col.label(text="Colliders")
                    if panel_col:
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
                            row = shp_box.row(align=True)
                            row.prop(shape, "name", text="Name: ")
                            row = shp_box.row(align=True)
                            row.prop(shape, "physics_material", text="Material: ")
                            row = shp_box.row(align=True)
                            row.prop(shape, "collision_preset", text="Filter: ")

                            shp_box = panel_col.box()
                            row = shp_box.row(align=True)
                            row.label(text="Dimensions: ")
                            row = shp_box.row(align=True)
                            row.operator("physx.fit_bounds_shape", icon='FULLSCREEN_ENTER', text="Fit to Bounds")
                            row = shp_box.row(align=True)
                            if shape.shape_type == 'BOX':
                                row.prop(shape, "dim_x", text="X")
                                row.prop(shape, "dim_y", text="Y")
                                row.prop(shape, "dim_z", text="Z")
                            elif shape.shape_type in ('SPHERE', 'CAPSULE'):
                                row.prop(shape, "dim_x", text="R")
                            if shape.shape_type == 'CAPSULE':
                                row.prop(shape, "dim_y", text="H-H")
                            if shape.shape_type == 'HEIGHTFIELD':
                                row.prop(shape, "hf_resolution")

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

                            header_trn, panel_trn = panel_col.panel("physx_transforms", default_closed=True)
                            header_trn.label(text="Local Transform")
                            if panel_trn:
                                if item.poll_armature_availability():
                                    box = panel_trn.box()
                                    box.label(text="Transform Target (Bone)", icon='BONE_DATA')
                                    box.prop(item, "use_bone_parent", text="Use Bone Parent", toggle=True)
                                    if item.use_bone_parent:
                                        col = box.column()
                                        col.prop(item, "parent_armature", text="Armature")
                                        if item.parent_armature and item.parent_armature != "NONE":
                                            col.prop(item, "target_bone", text="Bone")
                                        else:
                                            col.label(text="Select an armature first", icon='ERROR')

                                box = panel_trn.box()
                                box.label(text="Local Transform")
                                box.prop(shape, "local_pos")
                                box.prop(shape, "local_rot")

        elif px_s.ui_tab == 'SIM':
            row = layout.row()
            if px_s.sim_running:
                row.operator("physx.stop_sim", icon='PAUSE', text="Stop")
            else:
                row.operator("physx.sim_step", icon='PLAY', text="Start")
            layout.prop(px_s, "sim_steps", text="Step Count")
            row = layout.row()
            row.operator("physx.build_scene", text="Rebuild Scene", icon='FILE_REFRESH')
            row.operator("physx.run_steps", icon='NEXT_KEYFRAME', text="Step N")


classes = [CP77_PT_PhysicsTools]


def register_collisiontools():
    pxbridge.register()
    dangles.register()
    for cls in classes:
        if not hasattr(bpy.types, cls.__name__):
            bpy.utils.register_class(cls)


def unregister_collisiontools():
    for cls in reversed(classes):
        if hasattr(bpy.types, cls.__name__):
            bpy.utils.unregister_class(cls)
    dangles.unregister()
    pxbridge.unregister()
