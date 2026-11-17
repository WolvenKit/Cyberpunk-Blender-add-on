from bpy.types import Operator

from ...blender.mesh_validation import MeshValidationOptions
from ...blender.operator_results import finish_operator
from ..model import MeshValidationRequest
from ..services.mesh_validation_service import (
    fix_selected_meshes,
    validate_selected_meshes,
)


def _request(context, *, try_fix):
    props = context.scene.cp77_mesh_validation
    return MeshValidationRequest(
        is_skinned=bool(props.is_skinned),
        options=MeshValidationOptions(
            check_unweighted_vertices=bool(props.check_unweighted_vertices),
            check_unused_bones=bool(props.check_unused_bones),
            check_unused_vertex_groups=bool(props.check_unused_vertex_groups),
            check_missing_uv=bool(props.check_missing_uv),
            check_degenerate_faces=bool(props.check_degenerate_faces),
            check_degenerate_uvs=bool(props.check_degenerate_uvs),
            try_fix=bool(try_fix),
        ),
    )


def _store_result(context, result):
    props = context.scene.cp77_mesh_validation
    summary = result.details.get("payload")
    props.last_status = "PASS" if result.ok and result.level == "INFO" else result.level
    props.last_report = getattr(summary, "report", "") or result.message
    props.last_mesh_count = len(getattr(summary, "mesh_names", ()))
    props.last_issue_count = len(getattr(summary, "issues", ()))
    props.last_fix_count = getattr(summary, "fix_count", 0)
    props.last_remaining_count = len(getattr(summary, "remaining_issues", ()))


def _has_selected_mesh(context):
    return any(
        getattr(obj, "type", None) == "MESH" for obj in context.selected_objects
    ) or (getattr(getattr(context, "active_object", None), "type", None) == "MESH")


class CP77_OT_ValidateGLBMeshes(Operator):
    bl_idname = "cp77.validate_glb_meshes"
    bl_label = "Validate Selected Meshes"
    bl_description = "Run the same mesh requirements used by Cyberpunk GLB export"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return _has_selected_mesh(context)

    def execute(self, context):
        result = validate_selected_meshes(context, _request(context, try_fix=False))
        _store_result(context, result)
        return finish_operator(self, result)


class CP77_OT_FixGLBMeshes(Operator):
    bl_idname = "cp77.fix_glb_meshes"
    bl_label = "Fix GLB Export Problems"
    bl_description = "Fix every problem the checks find on the selected meshes and name them for their submesh order"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _has_selected_mesh(context)

    def execute(self, context):
        result = fix_selected_meshes(context, _request(context, try_fix=True))
        _store_result(context, result)
        return finish_operator(self, result)
