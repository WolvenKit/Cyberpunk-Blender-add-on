from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def runtime_diagnostics(result: Any, prefix: str) -> tuple[str, ...]:
    """Return node-runtime findings without promoting them to export blockers"""
    messages = []
    seen = set()
    for collection in (
        getattr(result, "blocking", ()) or (),
        getattr(result, "warnings", ()) or (),
    ):
        for item in collection:
            text = f"{prefix}: {item}"
            if text not in seen:
                seen.add(text)
                messages.append(text)
    return tuple(messages)


def attach_runtime_context(
    report: dict,
    *,
    missing_bones: Iterable[str] = (),
    editor_audit: Any = None,
    editor_audit_error: str = "",
) -> dict:
    """Attach preview/editor diagnostics without changing document validity"""
    missing = tuple(dict.fromkeys(str(name) for name in missing_bones if name))
    report["documentReady"] = bool(report.get("ready", False))
    report["missingBones"] = list(missing)
    report["previewReady"] = not missing

    warnings = list(report.get("warnings", ()) or ())
    if missing:
        warnings.append(
            f"Bound rig is missing {len(missing)} referenced bone(s): "
            + ", ".join(missing[:12])
        )

    if isinstance(editor_audit, dict):
        report["fullEditorAudit"] = editor_audit
        report["editorProjectionReady"] = bool(editor_audit.get("ready", False))
        for item in editor_audit.get("blocking", ()) or ():
            warnings.append(f"Editor projection: {item}")
    else:
        report["editorProjectionReady"] = editor_audit is None

    if editor_audit_error:
        report["fullEditorAuditError"] = str(editor_audit_error)
        report["editorProjectionReady"] = False
        warnings.append(f"Editor projection audit failed: {editor_audit_error}")

    report["warnings"] = list(dict.fromkeys(str(item) for item in warnings))
    return report
