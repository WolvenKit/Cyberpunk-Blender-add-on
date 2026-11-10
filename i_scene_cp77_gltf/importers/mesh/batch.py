import os
from dataclasses import dataclass

from ...assetio.documents import DocumentSession
from ...assetio.index import IndexPolicy
from ...blender.operator_results import OperationResult
from ...blender.selection import select_objects
from ...core.log import get_logger
from ...gltf.provenance import inspect_glb
from ...materials.repository import MaterialResourceRepository
from .external import import_external_glb
from .orchestration import import_cyberpunk_glb

_LOG = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GlbBatchRequest:
    paths: tuple[str, ...]
    appearances: tuple[str, ...]
    animation_target: str
    with_materials: bool
    remap_depot: bool
    image_format: str
    hide_armatures: bool
    import_garmentsupport: bool
    import_tracks: bool
    refresh_asset_index: bool


def _import_file(context, path, request, documents, resources, report_owner, warnings):
    inspection = inspect_glb(path)
    kind = inspection.content_kind.value
    if kind == "empty":
        raise ValueError("The file contains no mesh or animation payload.")
    if not inspection.claims_cp77_origin and kind not in {"animation", "rig"}:
        import_external_glb(path, inspection)
        return list(context.selected_objects)
    if inspection.claims_cp77_origin and not inspection.direct_import_supported:
        raise ValueError(f"Unsupported CP77 payload: {kind}.")
    result = import_cyberpunk_glb(
        path,
        with_materials=request.with_materials,
        remap_depot=request.remap_depot,
        image_format=request.image_format,
        hide_armatures=request.hide_armatures,
        import_garmentsupport=request.import_garmentsupport,
        appearances=request.appearances,
        import_tracks=request.import_tracks,
        animation_target=request.animation_target,
        content_kind=kind,
        document_session=documents,
        material_resources=resources,
        report_owner=report_owner,
    )
    if result.failures:
        raise RuntimeError("; ".join(result.failures))
    warnings.extend(
        f"{os.path.basename(path)}: {message}" for message in result.warnings
    )
    return [
        obj
        for item in result
        for obj in (item.get("all_objects") or (item.get("armature"),))
    ]


def import_glb_files(context, request, *, report_owner=None):
    imported, warnings, failures, objects = 0, [], [], []
    with DocumentSession() as documents:
        resources = MaterialResourceRepository(
            documents,
            image_index_policy=(
                IndexPolicy.REFRESH
                if request.refresh_asset_index
                else IndexPolicy.REUSE
            ),
        )
        for path in request.paths:
            try:
                objects.extend(
                    _import_file(
                        context,
                        path,
                        request,
                        documents,
                        resources,
                        report_owner,
                        warnings,
                    )
                )
                imported += 1
            except Exception as error:
                message = f"{os.path.basename(path)}: {error}"
                failures.append(message)
                _LOG.exception("Import failed: %s", message)
    shown = list(
        dict.fromkeys(obj for obj in objects if obj is not None and not obj.hide_get())
    )
    if shown:
        select_objects(shown, clear=True, context=context)
    notes = list(failures)
    if warnings:
        notes.append(f"{len(warnings)} warning(s); first: {warnings[0]}")
    if not imported:
        return OperationResult(False, "No files were imported.", "ERROR", tuple(notes))
    return OperationResult.finished(
        f"Imported {imported} of {len(request.paths)} file(s).",
        "WARNING" if failures else "INFO",
        warnings=notes,
    )
