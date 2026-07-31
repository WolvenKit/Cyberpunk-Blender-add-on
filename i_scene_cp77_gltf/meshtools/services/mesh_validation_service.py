from ...blender.mesh_repair import (
    cleanup_validation_temporaries,
    commit_prepared_mesh_repairs,
    prepare_mesh_validation_copies,
)
from ...blender.mesh_validation import (
    MeshValidationError,
    collect_mesh_validation_issues,
    format_validation_issues,
)
from ..model import MeshToolResult, MeshValidationSummary


def selected_meshes(context):
    meshes = tuple(
        obj
        for obj in getattr(context, "selected_objects", ())
        if getattr(obj, "type", None) == "MESH"
    )
    if meshes:
        return meshes
    active = getattr(context, "active_object", None)
    if active is not None and getattr(active, "type", None) == "MESH":
        return (active,)
    return ()


def _validation_report(meshes, issues, *, heading):
    if not issues:
        return f"{heading}\n  No GLB export validation issues found."
    return format_validation_issues(issues, heading=heading)


def validate_selected_meshes(context, request):
    meshes = selected_meshes(context)
    if not meshes:
        return MeshToolResult.failure("Select at least one mesh to validate.")
    try:
        issues = collect_mesh_validation_issues(
            meshes,
            is_skinned=request.is_skinned,
            options=request.options,
        )
    except Exception as error:
        return MeshToolResult.failure(f"GLB mesh validation failed: {error}")

    report = _validation_report(
        meshes,
        issues,
        heading="GLB export mesh validation:",
    )
    summary = MeshValidationSummary(
        mesh_names=tuple(obj.name for obj in meshes),
        issues=issues,
        remaining_issues=issues,
        report=report,
    )
    if issues:
        return MeshToolResult.warning(
            f"Found {len(issues)} GLB export issue{'s' if len(issues) != 1 else ''} "
            f"across {len(meshes)} mesh{'es' if len(meshes) != 1 else ''}.",
            payload=summary,
        )
    return MeshToolResult.success(
        f"{len(meshes)} selected mesh{'es' if len(meshes) != 1 else ''} passed GLB export validation.",
        payload=summary,
    )


def fix_selected_meshes(context, request):
    meshes = selected_meshes(context)
    if not meshes:
        return MeshToolResult.failure("Select at least one mesh to repair.")

    prepared = None
    try:
        prepared = prepare_mesh_validation_copies(
            meshes,
            is_skinned=request.is_skinned,
            options=request.options,
            require_valid=False,
        )
        if not prepared.fixes_applied:
            summary = MeshValidationSummary(
                mesh_names=tuple(obj.name for obj in meshes),
                issues=prepared.issues_found,
                remaining_issues=prepared.remaining_issues,
                report=_validation_report(
                    meshes,
                    prepared.remaining_issues,
                    heading="GLB export mesh repair:",
                ),
            )
            cleanup_validation_temporaries(prepared.temp_objects, prepared.temp_armatures)
            prepared = None
            if summary.remaining_issues:
                return MeshToolResult.warning(
                    "Validation found issues, but none of their repair options are enabled.",
                    payload=summary,
                )
            return MeshToolResult.success("No GLB export mesh repairs were required.", payload=summary)

        committed = commit_prepared_mesh_repairs(
            prepared,
            is_skinned=request.is_skinned,
            options=request.options,
        )
        prepared = None
        report_lines = ["GLB export mesh repair:"]
        for object_name, fixes in committed.fixes_applied:
            report_lines.append(f"  {object_name}:")
            report_lines.extend(f"    - {fix}" for fix in fixes)
        if committed.remaining_issues:
            report_lines.append("")
            report_lines.append(
                format_validation_issues(
                    committed.remaining_issues,
                    heading="Remaining validation issues:",
                )
            )
        else:
            report_lines.extend(("", "All enabled validation requirements now pass."))

        summary = MeshValidationSummary(
            mesh_names=tuple(obj.name for obj in meshes),
            issues=committed.issues_found,
            remaining_issues=committed.remaining_issues,
            fixes_applied=committed.fixes_applied,
            report="\n".join(report_lines),
        )
        message = (
            f"Applied {summary.fix_count} GLB mesh repair"
            f"{'s' if summary.fix_count != 1 else ''}."
        )
        if summary.remaining_issues:
            return MeshToolResult.warning(
                f"{message} {summary.remaining_count} issue"
                f"{'s remain' if summary.remaining_count != 1 else ' remains'}.",
                payload=summary,
            )
        return MeshToolResult.success(message, payload=summary)
    except MeshValidationError as error:
        return MeshToolResult.failure(str(error))
    except Exception as error:
        return MeshToolResult.failure(f"GLB mesh repair failed: {error}")
    finally:
        if prepared is not None:
            cleanup_validation_temporaries(prepared.temp_objects, prepared.temp_armatures)
