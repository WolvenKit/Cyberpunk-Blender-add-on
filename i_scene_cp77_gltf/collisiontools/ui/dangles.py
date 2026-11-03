from ...blender.workspace import is_animation_workspace
from ..blender.dangle_context import (
    get_active_chain,
    get_active_dangle_node,
    get_active_rig,
)


def _active_item(collection, index):
    if not collection:
        return None
    return collection[index] if 0 <= index < len(collection) else None


def _draw_dangle_nodes(layout, context, rig):
    st = rig.dangle_state
    header, panel = layout.panel("cp77_dangle_nodes", default_closed=False)
    header.label(text="Dangle Nodes", icon="PHYSICS")
    if panel is None:
        return

    row = panel.row()
    row.enabled = not st.is_playing
    row.template_list(
        "DANGLE_UL_dangle_nodes",
        "",
        st,
        "dangle_nodes",
        st,
        "active_dangle_node",
    )
    col = row.column(align=True)
    col.operator("dangle.add_node", icon="ADD", text="")
    col.operator("dangle.remove_node", icon="REMOVE", text="")

    dnode = get_active_dangle_node(context)
    if dnode is None:
        return

    chain = get_active_chain(context)
    solver = chain.solver if chain is not None else "DYNG"

    box = panel.box()
    box.label(text="Node Settings", icon="PREFERENCES")
    if solver == "DYNG":
        col = box.column(align=True)
        col.prop(dnode, "substep_time")
        col.prop(dnode, "solver_iterations")
        col.prop(dnode, "gravity_ws")
        col.prop(
            dnode,
            "external_force_ws",
            text="Static Force (unlinked only)"
            if dnode.external_force_linked
            else "External Force",
        )
    elif solver == "SPRING" or solver == "PENDULUM":
        col = box.column(align=True)
        col.prop(dnode, "gravity_ws")
        col.prop(
            dnode,
            "external_force_ws",
            text="Static Force (unlinked only)"
            if dnode.external_force_linked
            else "External Force",
        )

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
    header.label(text="Chains", icon="LINKED")
    if panel is None:
        return

    row = panel.row()
    row.template_list(
        "DANGLE_UL_chains",
        "",
        dnode,
        "chains",
        dnode,
        "active_chain",
    )
    col = row.column(align=True)
    col.operator("dangle.add_chain", icon="ADD", text="")
    col.operator("dangle.remove_chain", icon="REMOVE", text="")
    col.operator("dangle.copy_chain", icon="DUPLICATE", text="")

    chain = get_active_chain(context)
    if chain is None:
        return

    panel.prop(chain, "solver")
    if chain.solver not in {"DYNG", "PBD", "SPRING", "PENDULUM"}:
        panel.label(text="Preview can't run this solver", icon="ERROR")
    elif chain.solver == "PBD" and len(chain.particles) != 1:
        panel.label(text="Position Projection needs one bone", icon="ERROR")
    elif chain.solver == "SPRING" and len(chain.particles) != 1:
        panel.label(text="Spring needs one bone", icon="ERROR")
    elif chain.solver == "PENDULUM" and len(chain.particles) != 1:
        panel.label(text="Pendulum needs one bone", icon="ERROR")


def _draw_dangle_particles(layout, context, rig):
    chain = get_active_chain(context)
    if chain is None:
        return

    header, panel = layout.panel("cp77_dangle_particles", default_closed=False)
    header.label(text="Particles & Constraints", icon="BONE_DATA")
    if panel is None:
        return

    row = panel.row()
    row.template_list(
        "DANGLE_UL_particles",
        "",
        chain,
        "particles",
        chain,
        "active_particle_index",
    )
    col = row.column(align=True)
    col.operator("dangle.add_particle", icon="ADD", text="")
    col.operator("dangle.remove_particle", icon="REMOVE", text="")
    col.operator("dangle.add_selected_bones_to_chain", icon="BONE_DATA", text="")

    particle = _active_item(chain.particles, chain.active_particle_index)
    if particle is None:
        return

    if chain.solver == "PBD":
        box = panel.box()
        box.label(text="Position Projection", icon="CON_KINEMATIC")
        box.prop_search(particle, "bone_name", rig.data, "bones", text="Dangle Bone")
        box.prop(particle, "pos_projection_type")
        if particle.pos_projection_type == "DIRECTIONAL":
            box.prop_search(
                particle,
                "direction_reference_bone",
                rig.data,
                "bones",
                text="Direction Reference",
            )
            box.prop(particle, "capsule_axis_ls", text="Fallback Axis (LS)")
            box.prop(particle, "capsule_height")
        box.prop(particle, "capsule_radius")
        return

    if chain.solver == "PENDULUM":
        box = panel.box()
        box.label(text="Pendulum", icon="CON_ROTLIMIT")
        box.prop_search(particle, "bone_name", rig.data, "bones", text="Dangle Bone")
        col = box.column(align=True)
        col.prop(particle, "pendulum_simulation_fps")
        col.prop(particle, "mass")
        col.prop(particle, "damping")
        col.prop(particle, "pull_force")
        box.prop(particle, "pendulum_pull_force_direction_ls")

        box = panel.box()
        box.label(text="Angular Constraint", icon="CON_ROTLIMIT")
        box.prop(particle, "pendulum_constraint_type")
        box.prop(particle, "pendulum_half_aperture_angle")
        box.prop(particle, "pendulum_constraint_orientation")

        box = panel.box()
        box.label(text="Collision", icon="MESH_CAPSULE")
        box.prop(particle, "pendulum_projection_type")
        if particle.pendulum_projection_type != "DISABLED":
            box.prop(particle, "pendulum_collision_radius")
            box.prop(particle, "pendulum_collision_height")
        return

    if chain.solver == "SPRING":
        box = panel.box()
        box.label(text="Spring", icon="PHYSICS")
        box.prop_search(particle, "bone_name", rig.data, "bones", text="Dangle Bone")
        col = box.column(align=True)
        col.prop(particle, "spring_simulation_fps")
        col.prop(particle, "mass")
        col.prop(particle, "damping")
        col.prop(particle, "pull_force")
        box.prop(particle, "spring_pull_force_origin_ls")

        box = panel.box()
        box.label(text="Constraint Ellipsoid", icon="MESH_UVSPHERE")
        col = box.column(align=True)
        col.prop(particle, "spring_constraint_radius")
        col.prop(particle, "spring_constraint_scale1")
        col.prop(particle, "spring_constraint_scale2")
        box.prop(particle, "spring_constraint_orientation")

        box = panel.box()
        box.label(text="Collision", icon="CON_KINEMATIC")
        box.prop(particle, "spring_projection_type")
        if particle.spring_projection_type != "DISABLED":
            box.prop(particle, "spring_collision_radius")
        return

    box = panel.box()
    box.label(text="Physics", icon="PHYSICS")
    box.prop_search(particle, "bone_name", rig.data, "bones", text="Target Bone")
    col = box.column(align=True)
    col.prop(particle, "mass")
    col.prop(particle, "damping")
    col.prop(particle, "pull_force")

    box = panel.box()
    box.label(text="Collision Geometry", icon="MESH_CAPSULE")
    col = box.column(align=True)
    col.prop(particle, "capsule_radius")
    col.prop(particle, "capsule_height")
    box.prop(particle, "capsule_axis_ls")

    box = panel.box()
    box.label(text="Projections", icon="CON_KINEMATIC")
    box.prop(particle, "dyng_projection_type")

    box = panel.box()
    row = box.row()
    row.label(text="Dyng Links", icon="CONSTRAINT")
    row.operator("dangle.add_link", icon="ADD", text="")
    for index, link in enumerate(particle.link_constraints):
        sub = box.box()
        row = sub.row(align=True)
        row.prop_search(link, "target_bone", rig.data, "bones", text="")
        row.prop(link, "link_type", text="")
        remove = row.operator("dangle.remove_link", icon="X", text="")
        remove.index = index
        if link.link_type != "FIXED":
            col = sub.column(align=True)
            col.prop(link, "lower_ratio")
            col.prop(link, "upper_ratio")
        col = sub.column(align=True)
        col.prop(link, "explicit_rest_distance")
        col.prop(link, "stiffness")
        col.prop(link, "look_at_axis")

    box = panel.box()
    row = box.row()
    row.label(text="Ellipsoid Volumes", icon="MESH_UVSPHERE")
    row.operator("dangle.add_ellipsoid", icon="ADD", text="")
    for index, ellipsoid in enumerate(particle.ellipsoid_constraints):
        sub = box.box()
        row = sub.row(align=True)
        row.prop_search(ellipsoid, "target_bone", rig.data, "bones", text="")
        remove = row.operator("dangle.remove_ellipsoid", icon="X", text="")
        remove.index = index
        col = sub.column(align=True)
        col.prop(ellipsoid, "radius")
        col.prop(ellipsoid, "scale1")
        col.prop(ellipsoid, "scale2")
        col.prop(ellipsoid, "ellipsoid_transform_ls_quat", text="LS Quat (wxyz)")
        col.prop(ellipsoid, "ellipsoid_transform_ls_offset", text="LS Offset")

    box = panel.box()
    row = box.row()
    row.label(text="Cone Constraints", icon="CON_ROTLIMIT")
    row.operator("dangle.add_pendulum", icon="ADD", text="")
    for index, pendulum in enumerate(particle.pendulum_constraints):
        sub = box.box()
        row = sub.row(align=True)
        row.prop_search(pendulum, "target_bone", rig.data, "bones", text="")
        row.prop(pendulum, "constraint_type", text="")
        remove = row.operator("dangle.remove_pendulum", icon="X", text="")
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
    header.label(text="Node Collision Shapes", icon="MESH_UVSPHERE")
    if panel is None:
        return

    row = panel.row()
    row.template_list(
        "DANGLE_UL_collision_shapes",
        "",
        dnode,
        "collision_shapes",
        dnode,
        "active_shape_index",
    )
    col = row.column(align=True)
    col.operator("dangle.add_shape", icon="ADD", text="")
    col.operator("dangle.remove_shape", icon="REMOVE", text="")

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
    header.label(text="Drag Nodes", icon="FORCE_DRAG")
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


def draw_dangles(layout, context, px_s):
    row = layout.row()
    row.template_list(
        "DANGLE_UL_rigs",
        "",
        context.scene,
        "objects",
        context.scene,
        "dangle_active_rig_index",
    )
    col = row.column(align=True)
    col.operator("dangle.enable_rig", icon="ADD", text="")
    col.operator("dangle.disable_rig", icon="REMOVE", text="")

    rig = get_active_rig(context)
    if rig is None:
        layout.label(text="Select or enable an armature", icon="INFO")
        return

    st = rig.dangle_state

    row = layout.row(align=True)
    row.operator("dangle.import_json", icon="IMPORT", text="Import AnimGraph")
    if st.animgraph_source_text:
        row.operator("dangle.export_animgraph", icon="EXPORT", text="Export AnimGraph")

    if st.animgraph_source_text:
        row = layout.row(align=True)
        row.operator("dangle.validate_animgraph", icon="CHECKMARK", text="Validate")
        row.operator("dangle.switch_to_graph", icon="NODETREE", text="Graph View")
        if st.animgraph_tree_name:
            sync_row = layout.row(align=True)
            sync_row.operator(
                "dangle.push_to_graph", icon="FILE_REFRESH", text="Resync Graph"
            )

    # The whole graph plays in the Animation workspace; here the selected dangle simulates on the current pose.
    preview_box = layout.box()
    preview_box.prop(st, "preview_force_ws")
    if not is_animation_workspace(context):
        preview_box.operator("dangle.preview_whole_graph", icon="NODETREE")

    selected = st.active_dangle_node
    messages = [
        node.external_force_preview_error
        for index, node in enumerate(st.dangle_nodes)
        if index == selected and node.external_force_preview_error
    ]
    messages.extend(
        node.import_warnings
        for index, node in enumerate(st.dangle_nodes)
        if index == selected
    )
    for message in messages:
        for line in message.splitlines():
            layout.label(text=line, icon="ERROR")

    row = layout.row(align=True)
    if st.is_playing:
        row.operator("dangle.preview_stop", icon="PAUSE", text="Stop Simulation")
    else:
        row.operator("dangle.preview_play", icon="PLAY", text="Play Simulation")

    if px_s.viz_enabled:
        box = layout.box()
        box.label(text="Overlays", icon="OVERLAY")
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
