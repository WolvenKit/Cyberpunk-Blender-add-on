from bpy.types import Operator

from ...blender.operator_results import finish_operator
from ..services.uv_service import (
    apply_uv_checker,
    apply_uv_density,
    has_uv_checker,
    has_uv_density,
    remove_uv_checker,
    remove_uv_density,
)


class CP77UVTool(Operator):
    bl_idname = "cp77.uv_checker"
    bl_label = "UV Checker"
    bl_description = "Apply a texture to assist with UV coordinate mapping"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return finish_operator(self, apply_uv_checker(context))


class CP77UVCheckRemover(Operator):
    bl_idname = "cp77.uv_unchecker"
    bl_label = "Remove UV Checker"
    bl_description = "Restore the material used before the UV checker"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return any(has_uv_checker(obj) for obj in context.selected_objects)

    def execute(self, context):
        return finish_operator(self, remove_uv_checker(context))


class CP77UVDensity(Operator):
    bl_idname = "cp77.uv_density"
    bl_label = "UV Density"
    bl_description = "Visualize stable texel density using world-space polygon area and active UV area"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.cp77_mesh_analysis
        return finish_operator(
            self, apply_uv_density(context, props.uv_density_reference)
        )


class CP77UVDensityRemover(Operator):
    bl_idname = "cp77.uv_density_remove"
    bl_label = "Remove UV Density"
    bl_description = (
        "Restore the exact per-face material assignments used before UV Density"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return any(has_uv_density(obj) for obj in context.selected_objects)

    def execute(self, context):
        return finish_operator(self, remove_uv_density(context))
