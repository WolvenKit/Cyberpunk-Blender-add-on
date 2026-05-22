"""
Dangle Physics UI Panels and UILists.

Hierarchy (v5):
  Rig -> DangleNode[] -> Chain[] -> Particle[]

  DangleNodes hold simulation parameters (solver_iterations, substep, alpha...).
  Chains are prefix-split bone groups for navigation.
  Particles hold per-bone physics + constraints.
"""

import bpy


# UILists

class DANGLE_UL_rigs(bpy.types.UIList):
    def filter_items(self, context, data, property):
        objects = getattr(data, property)
        flt_flags = []
        flt_neworder = []
        for obj in objects:
            if obj.type == 'ARMATURE' and obj.dangle_state.is_dangle_rig:
                flt_flags.append(self.bitflag_filter_item)
            else:
                flt_flags.append(0)
        return flt_flags, flt_neworder

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        layout.prop(item, "name", text="", emboss=False, icon='ARMATURE_DATA')


class DANGLE_UL_dangle_nodes(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon='PHYSICS')
        n_chains = len(item.chains)
        total_p = sum(len(ch.particles) for ch in item.chains)
        row.label(text=f"{n_chains}ch {total_p}p")


class DANGLE_UL_chains(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        n_particles = len(item.particles)
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon='LINKED')
        row.label(text=f"{n_particles}p")


class DANGLE_UL_particles(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        layout.label(
            text=item.bone_name if item.bone_name else "Unassigned",
            icon='BONE_DATA',
        )
        layout.prop(
            item, "is_pinned", text="",
            icon='PINNED' if item.is_pinned else 'UNPINNED',
        )


class DANGLE_UL_collision_shapes(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        layout.label(
            text=item.name,
            icon='MESH_CAPSULE' if item.shape_type == 'CAPSULE' else 'MESH_UVSPHERE',
        )
        layout.prop(item, "bone_name", text="", emboss=False)


# Helpers

def get_active_rig(context):
    if not context.scene.objects:
        return None
    idx = context.scene.dangle_active_rig_index
    if 0 <= idx < len(context.scene.objects):
        obj = context.scene.objects[idx]
        if obj.type == 'ARMATURE' and obj.dangle_state.is_dangle_rig:
            return obj
    return None


def get_active_dangle_node(context):
    """Return the active DANGLE_DangleNode or None."""
    rig = get_active_rig(context)
    if rig is None:
        return None
    st = rig.dangle_state
    if not st.dangle_nodes:
        return None
    idx = st.active_dangle_node
    if 0 <= idx < len(st.dangle_nodes):
        return st.dangle_nodes[idx]
    return None


def get_active_chain(context):
    """Return the active Chain within the active DangleNode, or None."""
    dnode = get_active_dangle_node(context)
    if dnode is None or not dnode.chains:
        return None
    idx = dnode.active_chain
    if 0 <= idx < len(dnode.chains):
        return dnode.chains[idx]
    return None


# Panels




class DANGLE_PT_collision_shapes(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "CP77 Modding"
    bl_label = "Rig Collision Shapes"
    bl_parent_id = "CP77_PT_physics"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        if context.scene.physx.ui_tab != 'DANGLES': return False
        return get_active_rig(context) is not None

    def draw(self, context):
        layout = self.layout
        rig = get_active_rig(context)
        st = rig.dangle_state

        row = layout.row()
        row.template_list(
            "DANGLE_UL_collision_shapes", "",
            st, "collision_shapes",
            st, "active_shape_index",
        )
        col = row.column(align=True)
        col.operator("dangle.add_shape", icon='ADD', text="")
        col.operator("dangle.remove_shape", icon='REMOVE', text="")

        if not st.collision_shapes:
            return

        shape = st.collision_shapes[st.active_shape_index]

        box = layout.box()
        box.prop(shape, "name")
        box.prop_search(shape, "bone_name", rig.data, "bones", text="Bone")
        box.prop(shape, "shape_type")

        col = box.column(align=True)
        col.prop(shape, "radius")
        if shape.shape_type == 'CAPSULE':
            col.prop(shape, "height_extent")

        box.prop(shape, "offset_ls")
        box.prop(shape, "rotation_ls_quat", text="Rotation (wxyz)")


class DANGLE_PT_dangle_nodes(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "CP77 Modding"
    bl_label = "Dangle Nodes"
    bl_parent_id = "CP77_PT_physics"

    @classmethod
    def poll(cls, context):
        if context.scene.physx.ui_tab != 'DANGLES': return False
        return get_active_rig(context) is not None

    def draw(self, context):
        layout = self.layout
        rig = get_active_rig(context)
        st = rig.dangle_state

        row = layout.row()
        row.template_list(
            "DANGLE_UL_dangle_nodes", "",
            st, "dangle_nodes",
            st, "active_dangle_node",
        )
        col = row.column(align=True)
        col.operator("dangle.add_node", icon='ADD', text="")
        col.operator("dangle.remove_node", icon='REMOVE', text="")

        dnode = get_active_dangle_node(context)
        if dnode is None:
            return

        # Per-node simulation settings
        box = layout.box()
        box.label(text="Node Settings", icon='PREFERENCES')
        col = box.column(align=True)
        col.prop(dnode, "substep_time")

        box.prop(dnode, "alpha")
        box.prop(dnode, "rotate_parent_to_look_at")
        if dnode.rotate_parent_to_look_at:
            box.prop(dnode, "look_at_axis")


class DANGLE_PT_chains(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "CP77 Modding"
    bl_label = "Chains"
    bl_parent_id = "CP77_PT_physics"

    @classmethod
    def poll(cls, context):
        if context.scene.physx.ui_tab != 'DANGLES': return False
        return get_active_dangle_node(context) is not None

    def draw(self, context):
        layout = self.layout
        dnode = get_active_dangle_node(context)

        row = layout.row()
        row.template_list(
            "DANGLE_UL_chains", "",
            dnode, "chains",
            dnode, "active_chain",
        )
        col = row.column(align=True)
        col.operator("dangle.add_chain", icon='ADD', text="")
        col.operator("dangle.remove_chain", icon='REMOVE', text="")
        col.operator("dangle.copy_chain", icon='DUPLICATE', text="")


class DANGLE_PT_particles(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "CP77 Modding"
    bl_label = "Particles & Constraints"
    bl_parent_id = "CP77_PT_physics"

    @classmethod
    def poll(cls, context):
        if context.scene.physx.ui_tab != 'DANGLES': return False
        return get_active_chain(context) is not None

    def draw(self, context):
        layout = self.layout
        rig = get_active_rig(context)
        chain = get_active_chain(context)

        row = layout.row()
        row.template_list(
            "DANGLE_UL_particles", "",
            chain, "particles",
            chain, "active_particle_index",
        )
        col = row.column(align=True)
        col.operator("dangle.add_particle", icon='ADD', text="")
        col.operator("dangle.remove_particle", icon='REMOVE', text="")
        col.operator("dangle.add_selected_bones_to_chain", icon='BONE_DATA', text="")

        if not chain.particles:
            return

        p = chain.particles[chain.active_particle_index]

        #  Physics Properties 
        box = layout.box()
        box.label(text="Physics", icon='PHYSICS')
        box.prop_search(p, "bone_name", rig.data, "bones", text="Target Bone")
        col = box.column(align=True)
        col.prop(p, "mass")
        col.prop(p, "damping")
        col.prop(p, "pull_force")

        #  Collision Capsule 
        box = layout.box()
        box.label(text="Collision Geometry", icon='MESH_CAPSULE')
        col = box.column(align=True)
        col.prop(p, "capsule_radius")
        col.prop(p, "capsule_height")
        box.prop(p, "capsule_axis_ls")

        #  Projections 
        box = layout.box()
        box.label(text="Projections", icon='CON_KINEMATIC')
        box.prop(p, "dyng_projection_type")
        box.prop(p, "pos_projection_type")
        if p.pos_projection_type == 'DIRECTIONAL':
            box.prop_search(
                p, "direction_reference_bone", rig.data, "bones", text="Ref Bone"
            )

        #  Dyng Links 
        box = layout.box()
        row = box.row()
        row.label(text="Dyng Links", icon='CONSTRAINT')
        row.operator("dangle.add_link", icon='ADD', text="")
        for i, link in enumerate(p.link_constraints):
            sub = box.box()
            row = sub.row(align=True)
            row.prop_search(link, "target_bone", rig.data, "bones", text="")
            row.prop(link, "link_type", text="")
            rem = row.operator("dangle.remove_link", icon='X', text="")
            rem.index = i

            if link.link_type != 'FIXED':
                col = sub.column(align=True)
                col.prop(link, "lower_ratio")
                col.prop(link, "upper_ratio")

            col = sub.column(align=True)
            col.prop(link, "explicit_rest_distance")
            col.prop(link, "stiffness")
            col.prop(link, "look_at_axis")

        #  Ellipsoid Volumes 
        box = layout.box()
        row = box.row()
        row.label(text="Ellipsoid Volumes", icon='MESH_UVSPHERE')
        row.operator("dangle.add_ellipsoid", icon='ADD', text="")
        for i, ell in enumerate(p.ellipsoid_constraints):
            sub = box.box()
            row = sub.row(align=True)
            row.prop_search(ell, "target_bone", rig.data, "bones", text="")
            rem = row.operator("dangle.remove_ellipsoid", icon='X', text="")
            rem.index = i

            col = sub.column(align=True)
            col.prop(ell, "radius")
            col.prop(ell, "scale1")
            col.prop(ell, "scale2")
            col.prop(ell, "ellipsoid_transform_ls_quat", text="LS Quat (wxyz)")
            col.prop(ell, "ellipsoid_transform_ls_offset", text="LS Offset")

        #  Pendulum / Cone Limits 
        box = layout.box()
        row = box.row()
        row.label(text="Cone Constraints", icon='CON_ROTLIMIT')
        row.operator("dangle.add_pendulum", icon='ADD', text="")
        for i, pen in enumerate(p.pendulum_constraints):
            sub = box.box()
            row = sub.row(align=True)
            row.prop_search(pen, "target_bone", rig.data, "bones", text="")
            row.prop(pen, "constraint_type", text="")
            rem = row.operator("dangle.remove_pendulum", icon='X', text="")
            rem.index = i

            col = sub.column(align=True)
            col.prop(pen, "half_aperture_angle")
            col.prop(pen, "projection_type")
            col.prop(pen, "cone_transform_ls_quat", text="Cone LS Quat (wxyz)")
            col.prop(pen, "cone_collision_radius")
            col.prop(pen, "cone_collision_height")


class DANGLE_PT_drag_nodes(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "CP77 Modding"
    bl_label = "Drag Nodes"
    bl_parent_id = "CP77_PT_physics"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        if context.scene.physx.ui_tab != 'DANGLES': return False
        rig = get_active_rig(context)
        return rig is not None and len(rig.dangle_state.drag_nodes) > 0

    def draw(self, context):
        layout = self.layout
        rig = get_active_rig(context)
        st = rig.dangle_state

        layout.label(text=f"{len(st.drag_nodes)} drag node(s)", icon='FORCE_DRAG')

        for dn in st.drag_nodes:
            box = layout.box()
            row = box.row()
            row.label(text=dn.bone_name, icon='BONE_DATA')
            row.label(text=f"fps={dn.simulation_fps:.0f}  spd={dn.source_speed_multiplier:.1f}")
            if dn.has_overshoot:
                box.label(
                    text=f"Overshoot: min={dn.overshoot_detection_min_speed:.2f}  "
                         f"max={dn.overshoot_detection_max_speed:.1f}  "
                         f"dur={dn.overshoot_duration:.1f}s",
                    icon='FORCE_HARMONIC',
                )


# Registration

classes = (
    DANGLE_UL_rigs,
    DANGLE_UL_dangle_nodes,
    DANGLE_UL_chains,
    DANGLE_UL_particles,
    DANGLE_UL_collision_shapes,
    DANGLE_PT_collision_shapes,
    DANGLE_PT_dangle_nodes,
    DANGLE_PT_chains,
    DANGLE_PT_particles,
    DANGLE_PT_drag_nodes,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
