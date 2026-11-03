from bpy.types import Operator

from ..services.uv_service import UV_CHECKER_MATERIAL, apply_uv_checker, remove_uv_checker
from .result import finish_operator


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
        material = getattr(getattr(context, "object", None), "active_material", None)
        return material is not None and material.name == UV_CHECKER_MATERIAL

    def execute(self, context):
        return finish_operator(self, remove_uv_checker(context))
