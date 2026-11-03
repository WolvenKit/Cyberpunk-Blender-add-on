import bpy
from bpy.props import IntProperty

from ...blender.operator_results import finish_operator
from ..services.dangles.editing import (
    add_chain,
    add_dangle_node,
    add_particle,
    add_selected_bones_to_chain,
    add_shape,
    copy_chain,
    mutate_particle_constraint,
    remove_chain,
    remove_dangle_node,
    remove_particle,
    remove_shape,
)


class DANGLE_OT_add_dangle_node(bpy.types.Operator):
    bl_idname = "dangle.add_node"
    bl_label = "Add Node"

    def execute(self, context):
        return finish_operator(self, add_dangle_node(context))


class DANGLE_OT_remove_dangle_node(bpy.types.Operator):
    bl_idname = "dangle.remove_node"
    bl_label = "Remove Node"

    def execute(self, context):
        return finish_operator(self, remove_dangle_node(context))


class DANGLE_OT_add_chain(bpy.types.Operator):
    bl_idname = "dangle.add_chain"
    bl_label = "Add Chain"

    def execute(self, context):
        return finish_operator(self, add_chain(context))


class DANGLE_OT_remove_chain(bpy.types.Operator):
    bl_idname = "dangle.remove_chain"
    bl_label = "Remove Chain"

    def execute(self, context):
        return finish_operator(self, remove_chain(context))


class DANGLE_OT_add_particle(bpy.types.Operator):
    bl_idname = "dangle.add_particle"
    bl_label = "Add Particle"

    def execute(self, context):
        return finish_operator(self, add_particle(context))


class DANGLE_OT_remove_particle(bpy.types.Operator):
    bl_idname = "dangle.remove_particle"
    bl_label = "Remove Particle"

    def execute(self, context):
        return finish_operator(self, remove_particle(context))


class DANGLE_OT_add_shape(bpy.types.Operator):
    bl_idname = "dangle.add_shape"
    bl_label = "Add Node Shape"
    bl_options = {"UNDO"}

    def execute(self, context):
        return finish_operator(self, add_shape(context))


class DANGLE_OT_remove_shape(bpy.types.Operator):
    bl_idname = "dangle.remove_shape"
    bl_label = "Remove Node Shape"
    bl_options = {"UNDO"}

    def execute(self, context):
        return finish_operator(self, remove_shape(context))


class _DANGLE_OT_constraint_action:
    collection_name = ""
    action = "ADD"

    def execute(self, context):
        index = getattr(self, "index", -1)
        return finish_operator(
            self,
            mutate_particle_constraint(
                context, self.collection_name, self.action, index
            ),
        )


class DANGLE_OT_add_link(_DANGLE_OT_constraint_action, bpy.types.Operator):
    bl_idname = "dangle.add_link"
    bl_label = "Add Dyng Link"
    collection_name = "link_constraints"


class DANGLE_OT_remove_link(_DANGLE_OT_constraint_action, bpy.types.Operator):
    bl_idname = "dangle.remove_link"
    bl_label = "Remove Link"
    collection_name = "link_constraints"
    action = "REMOVE"
    index: IntProperty()


class DANGLE_OT_add_ellipsoid(_DANGLE_OT_constraint_action, bpy.types.Operator):
    bl_idname = "dangle.add_ellipsoid"
    bl_label = "Add Ellipsoid"
    collection_name = "ellipsoid_constraints"


class DANGLE_OT_remove_ellipsoid(_DANGLE_OT_constraint_action, bpy.types.Operator):
    bl_idname = "dangle.remove_ellipsoid"
    bl_label = "Remove Ellipsoid"
    collection_name = "ellipsoid_constraints"
    action = "REMOVE"
    index: IntProperty()


class DANGLE_OT_add_pendulum(_DANGLE_OT_constraint_action, bpy.types.Operator):
    bl_idname = "dangle.add_pendulum"
    bl_label = "Add Pendulum"
    collection_name = "pendulum_constraints"


class DANGLE_OT_remove_pendulum(_DANGLE_OT_constraint_action, bpy.types.Operator):
    bl_idname = "dangle.remove_pendulum"
    bl_label = "Remove Pendulum"
    collection_name = "pendulum_constraints"
    action = "REMOVE"
    index: IntProperty()


class DANGLE_OT_copy_chain(bpy.types.Operator):
    bl_idname = "dangle.copy_chain"
    bl_label = "Copy Chain"

    def execute(self, context):
        return finish_operator(self, copy_chain(context))


class DANGLE_OT_add_selected_bones_to_chain(bpy.types.Operator):
    bl_idname = "dangle.add_selected_bones_to_chain"
    bl_label = "Add Selected Bones"

    def execute(self, context):
        return finish_operator(self, add_selected_bones_to_chain(context))
