import bpy


class DANGLE_UL_rigs(bpy.types.UIList):
    def filter_items(self, context, data, property):
        objects = getattr(data, property)
        flags = [
            self.bitflag_filter_item
            if obj.type == 'ARMATURE' and obj.dangle_state.is_dangle_rig
            else 0
            for obj in objects
        ]
        return flags, []

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        layout.prop(item, "name", text="", emboss=False, icon='ARMATURE_DATA')


class DANGLE_UL_dangle_nodes(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon='PHYSICS')
        chain_count = len(item.chains)
        particle_count = sum(len(chain.particles) for chain in item.chains)
        solver = item.chains[0].solver if item.chains else 'DYNG'
        row.label(text=f"{solver} {chain_count}ch {particle_count}p")


class DANGLE_UL_chains(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon='LINKED')
        row.label(text=f"{len(item.particles)}p")


class DANGLE_UL_particles(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        layout.label(text=item.bone_name or "Unassigned", icon='BONE_DATA')
        layout.prop(
            item,
            "is_pinned",
            text="",
            icon='PINNED' if item.is_pinned else 'UNPINNED',
        )


class DANGLE_UL_collision_shapes(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        shape_icon = {
            'CAPSULE': 'MESH_CAPSULE',
            'ROUNDED_BOX': 'MESH_CUBE',
        }.get(item.shape_type, 'MESH_UVSPHERE')
        layout.label(text=item.name, icon=shape_icon)
        layout.prop(item, "bone_name", text="", emboss=False)


def get_active_rig(context):
    objects = context.scene.objects
    index = context.scene.dangle_active_rig_index
    if 0 <= index < len(objects):
        obj = objects[index]
        if obj.type == 'ARMATURE' and obj.dangle_state.is_dangle_rig:
            return obj
    return None


def get_active_dangle_node(context):
    rig = get_active_rig(context)
    if rig is None:
        return None
    state = rig.dangle_state
    index = state.active_dangle_node
    if 0 <= index < len(state.dangle_nodes):
        return state.dangle_nodes[index]
    return None


def get_active_chain(context):
    dangle_node = get_active_dangle_node(context)
    if dangle_node is None:
        return None
    index = dangle_node.active_chain
    if 0 <= index < len(dangle_node.chains):
        return dangle_node.chains[index]
    return None


classes = (
    DANGLE_UL_rigs,
    DANGLE_UL_dangle_nodes,
    DANGLE_UL_chains,
    DANGLE_UL_particles,
    DANGLE_UL_collision_shapes,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
