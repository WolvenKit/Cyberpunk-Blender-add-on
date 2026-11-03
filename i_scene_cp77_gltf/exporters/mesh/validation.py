from ...blender.mesh_repair import PreparedMeshValidation, prepare_mesh_validation_copies
from ...blender.mesh_validation import MeshValidationOptions


def prepare_meshes_for_export(meshes, *, is_skinned=False, options=None):
    return prepare_mesh_validation_copies(
        meshes,
        is_skinned=is_skinned,
        options=options or MeshValidationOptions(),
        require_valid=True,
    )


def format_fix_summary(result: PreparedMeshValidation):
    if not result.fixes_applied:
        return ""
    lines = ["Export used temporary mesh fixes; source objects were not changed:"]
    for object_name, fixes in result.fixes_applied.items():
        lines.append(f"  {object_name}:")
        lines.extend(f"    - {fix}" for fix in fixes)
    return "\n".join(lines)


__all__ = (
    "MeshValidationOptions",
    "format_fix_summary",
    "prepare_meshes_for_export",
)
