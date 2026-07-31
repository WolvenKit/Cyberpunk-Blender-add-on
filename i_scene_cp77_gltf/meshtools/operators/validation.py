from bpy.types import Operator

from ...blender.mesh_validation import MeshValidationOptions
from ..model import MeshValidationRequest
from ..services.mesh_validation_service import fix_selected_meshes, validate_selected_meshes
from .result import finish_operator


def _request(context, *, try_fix):
    props = context.scene.cp77_mesh_validation
    return MeshValidationRequest(
        is_skinned=bool(props.is_skinned),
        options=MeshValidationOptions(
            advanced_validation=bool(props.advanced_validation),
            check_missing_uv=bool(props.check_missing_uv),
            check_degenerate_faces=bool(props.check_degenerate_faces),
            check_degenerate_uvs=bool(props.check_degenerate_uvs),
            check_unweighted_vertices=bool(props.check_unweighted_vertices),
            check_unused_bones=bool(props.check_unused_bones),
            try_fix=bool(try_fix),
            fix_remove_unmatched_vertex_groups=bool(props.fix_remove_unmatched_vertex_groups),
            fix_apply_autofitter_shape_keys=bool(props.fix_apply_autofitter_shape_keys),
            fix_add_missing_uv=bool(props.fix_add_missing_uv),
            fix_dissolve_degenerate_faces=bool(props.fix_dissolve_degenerate_faces),
            fix_dissolve_degenerate_uvs=bool(props.fix_dissolve_degenerate_uvs),
            fix_assign_unweighted_vertices=bool(props.fix_assign_unweighted_vertices),
            fix_remove_unused_bones=bool(props.fix_remove_unused_bones),
        ),
    )


def _store_result(context, result):
    props = context.scene.cp77_mesh_validation
    summary = result.payload
    props.last_status = "PASS" if result.ok and result.severity == "INFO" else result.severity
    props.last_report = getattr(summary, "report", "") or result.message
    props.last_mesh_count = len(getattr(summary, "mesh_names", ()))
    props.last_issue_count = len(getattr(summary, "issues", ()))
    props.last_fix_count = getattr(summary, "fix_count", 0)
    props.last_remaining_count = len(getattr(summary, "remaining_issues", ()))


def _has_selected_mesh(context):
    return any(getattr(obj, "type", None) == "MESH" for obj in context.selected_objects) or (
        getattr(getattr(context, "active_object", None), "type", None) == "MESH"
    )


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
    bl_label = "Apply Selected GLB Fixes"
    bl_description = "Apply enabled GLB export repairs to selected source meshes; this operation is undoable"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _has_selected_mesh(context)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        result = fix_selected_meshes(context, _request(context, try_fix=True))
        _store_result(context, result)
        return finish_operator(self, result)
