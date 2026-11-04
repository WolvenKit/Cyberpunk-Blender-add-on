import bpy

from ...blender.operator_results import finish_operator
from ..services.actors import (
    apply_force_to_active_actor,
    calculate_dynamics,
    cook_active_shape,
    fit_bounds_shape,
    mutate_actor_list,
    mutate_shape_list,
)


class PHYSX_OT_apply_force(bpy.types.Operator):
    bl_idname = "physx.apply_force"
    bl_label = "Apply Force"

    def execute(self, context):
        return finish_operator(self, apply_force_to_active_actor(context))


class PHYSX_OT_cook_mesh(bpy.types.Operator):
    bl_idname = "physx.cook_mesh"
    bl_label = "Cook"

    @classmethod
    def poll(cls, context):
        obj = getattr(context, "object", None)
        px = getattr(obj, "physx", None) if obj is not None else None
        return (
            obj is not None
            and getattr(obj, "type", None) == "MESH"
            and px is not None
            and len(px.shapes) > 0
            and 0 <= px.shape_index < len(px.shapes)
        )

    def execute(self, context):
        return finish_operator(self, cook_active_shape(context))


class PHYSX_OT_fit_bounds_shape(bpy.types.Operator):
    bl_idname = "physx.fit_bounds_shape"
    bl_label = "Fit"

    shape_index: bpy.props.IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        obj = getattr(context, "object", None)
        px = getattr(obj, "physx", None) if obj is not None else None
        return (
            obj is not None
            and getattr(obj, "type", None) == "MESH"
            and px is not None
            and len(px.shapes) > 0
        )

    def execute(self, context):
        return finish_operator(self, fit_bounds_shape(context, self.shape_index))


class PHYSX_OT_calc_dynamics(bpy.types.Operator):
    bl_idname = "physx.calc_dynamics"
    bl_label = "Auto Calc"

    def execute(self, context):
        return finish_operator(self, calculate_dynamics(context))


class PHYSX_OT_shape_action(bpy.types.Operator):
    bl_idname = "physx.shape_action"
    bl_label = "Action"

    action: bpy.props.EnumProperty(items=[("ADD", "Add", ""), ("REMOVE", "Remove", "")])

    @classmethod
    def poll(cls, context):
        # Imported .phys actors are empties.
        obj = getattr(context, "object", None)
        return (
            obj is not None
            and getattr(obj, "type", None) in {"MESH", "EMPTY"}
            and getattr(obj, "physx", None) is not None
        )

    def execute(self, context):
        return finish_operator(self, mutate_shape_list(context, self.action))


class PHYSX_OT_list_action(bpy.types.Operator):
    bl_idname = "physx.list_action"
    bl_label = "List Action"

    action: bpy.props.EnumProperty(items=[("ADD", "Add", ""), ("REMOVE", "Remove", "")])

    def execute(self, context):
        return finish_operator(self, mutate_actor_list(context, self.action))
