from dataclasses import replace

from ...blender.context import preserved_context, safe_mode_switch
from ...blender.mesh_repair import (
    cleanup_validation_temporaries,
    commit_prepared_mesh_repairs,
    prepare_mesh_validation_copies,
)
from ...blender.mesh_validation import (
    MeshValidationError,
    collect_mesh_validation_issues,
    format_validation_issues,
    issue_fix_enabled,
)
from ...blender.operator_results import OperationResult
from ...blender.outliner import name_submeshes
from ...blender.selection import selected_meshes
from ...core.log import get_logger
from ..model import MeshValidationSummary

_LOG = get_logger(__name__)


def _validation_report(issues, *, heading):
    if not issues:
        return f"{heading}\n  No GLB export validation issues found."
    return format_validation_issues(issues, heading=heading)


def validate_selected_meshes(context, request):
    meshes = selected_meshes(context, include_active=True)
    if not meshes:
        return OperationResult.cancelled("Select at least one mesh to validate.")
    try:
        # Edit Mode keeps a mesh's corner data in the edit mesh, so its UVs and colors read as empty.
        with preserved_context():
            safe_mode_switch("OBJECT")
            issues = collect_mesh_validation_issues(
                meshes,
                is_skinned=request.is_skinned,
                options=request.options,
            )
    except Exception as error:
        return OperationResult.cancelled(
            f"GLB mesh validation failed: {error}", error=error
        )

    report = _validation_report(
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
        return OperationResult.finished(
            f"Found {len(issues)} GLB export issue{'s' if len(issues) != 1 else ''} "
            f"across {len(meshes)} mesh{'es' if len(meshes) != 1 else ''}.",
            level="WARNING",
            payload=summary,
        )
    return OperationResult.finished(
        f"{len(meshes)} selected mesh{'es' if len(meshes) != 1 else ''} passed GLB export validation.",
        payload=summary,
    )


def fix_selected_meshes(context, request):
    meshes = selected_meshes(context, include_active=True)
    if not meshes:
        return OperationResult.cancelled("Select at least one mesh to repair.")
    # Repairs are written into the meshes, which Edit Mode would overwrite on leaving it.
    with preserved_context():
        safe_mode_switch("OBJECT")
        renamed = name_submeshes(context, meshes)
        result = _fix_meshes(meshes, request)
    if not renamed or not result.ok:
        return result
    note = f"Renamed {len(renamed)} submeshes for their order."
    summary = result.details.get("payload")
    if summary is not None:
        summary = replace(
            summary,
            mesh_names=tuple(obj.name for obj in meshes),
            report="\n".join(
                (
                    summary.report,
                    "",
                    note,
                    *(f"  {old} → {new}" for old, new in renamed),
                )
            ),
        )
    return OperationResult.finished(
        f"{result.message} {note}",
        level=result.level,
        warnings=result.warnings,
        payload=summary,
    )


def _fix_meshes(meshes, request):
    prepared = None
    issues_found = None
    applied = {}
    remaining = ()
    try:
        # A fix can leave a problem of its own behind, as limiting influences can empty a vertex group and orphan its
        # bone, so Fix goes round again while there is something left to fix.
        for _round in range(4):
            prepared = prepare_mesh_validation_copies(
                meshes,
                is_skinned=request.is_skinned,
                options=request.options,
                require_valid=False,
            )
            if issues_found is None:
                issues_found = prepared.issues_found
            if not prepared.fixes_applied:
                remaining = prepared.remaining_issues
                cleanup_validation_temporaries(
                    prepared.temp_objects, prepared.temp_armatures
                )
                prepared = None
                break
            committed = commit_prepared_mesh_repairs(
                prepared,
                is_skinned=request.is_skinned,
                options=request.options,
            )
            prepared = None
            for object_name, fixes in committed.fixes_applied:
                applied.setdefault(object_name, []).extend(fixes)
            remaining = committed.remaining_issues
            if not any(
                issue_fix_enabled(issue, request.options) for issue in remaining
            ):
                break

        report_lines = ["GLB export mesh repair:"]
        for object_name, fixes in applied.items():
            report_lines.append(f"  {object_name}:")
            report_lines.extend(f"    - {fix}" for fix in fixes)
        if remaining:
            report_lines.append("")
            report_lines.append(
                format_validation_issues(
                    remaining,
                    heading="Remaining validation issues:",
                )
            )
        elif applied:
            report_lines.extend(("", "All enabled validation requirements now pass."))
        else:
            report_lines.append("  No GLB export validation issues found.")

        summary = MeshValidationSummary(
            mesh_names=tuple(obj.name for obj in meshes),
            issues=issues_found or (),
            remaining_issues=remaining,
            fixes_applied=tuple(
                (object_name, tuple(fixes)) for object_name, fixes in applied.items()
            ),
            report="\n".join(report_lines),
        )
        if not applied:
            if remaining:
                return OperationResult.finished(
                    "Validation found problems Fix cannot repair; the report lists them.",
                    level="WARNING",
                    payload=summary,
                )
            return OperationResult.finished(
                "No GLB export mesh repairs were required.", payload=summary
            )
        message = (
            f"Applied {summary.fix_count} GLB mesh repair"
            f"{'s' if summary.fix_count != 1 else ''}."
        )
        if summary.remaining_issues:
            return OperationResult.finished(
                f"{message} {summary.remaining_count} issue"
                f"{'s remain' if summary.remaining_count != 1 else ' remains'}.",
                level="WARNING",
                payload=summary,
            )
        return OperationResult.finished(message, payload=summary)
    except MeshValidationError as error:
        return OperationResult.cancelled(str(error), error=error)
    except Exception as error:
        return OperationResult.cancelled(
            f"GLB mesh repair failed: {error}", error=error
        )
    finally:
        if prepared is not None:
            cleanup_validation_temporaries(
                prepared.temp_objects, prepared.temp_armatures
            )
