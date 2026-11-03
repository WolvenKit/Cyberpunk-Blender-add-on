from __future__ import annotations

import os

from ...assetio.atomic import atomic_write_many
from ...assetio.paths import is_plain_file_name
from ...assetio.project_layout import project_layout_for
from ...blender.mesh_source import (
    base_mesh,
    is_edited,
    mesh_source,
    record_import_signature,
)
from ...blender.operator_results import OperationResult
from ...blender.transactions import transactional
from ...entity.model.component_types import SKINNED_TYPES
from ...entity.model.edits import ExportTarget, ValidationIssue
from ...entity.services.export import BaseCopy, MeshWrite, build_export_payloads
from ...exporters.mesh.orchestration import build_mesh_glb_payload
from ..blender.scene import component_objects
from ..blender.state import component_mesh_path, ensure_appearance_state, entity_edit
from ..model.requests import EntityExportRequest
from ..runtime.scene_cache import entity_index
from ..runtime.updates import suspended


def _app_target(edit, request: EntityExportRequest) -> str:
    folder = request.appearances_folder or os.path.dirname(edit.app_path)
    name = os.path.basename(request.filepath)
    stem = (
        name[: -len(".ent.json")]
        if name.casefold().endswith(".ent.json")
        else os.path.splitext(name)[0]
    )
    return os.path.join(folder, stem + ".app.json")


def _mesh_writes(import_id: str, edited_meshes: bool, layout):
    """The meshes to write"""
    writes, copies, written_objects, issues = {}, {}, [], []
    for collection in entity_index().collections(import_id):
        state = ensure_appearance_state(collection)
        if state.removed:
            continue
        for item in state.components:
            if item.removed:
                continue
            objects = [
                obj
                for obj in component_objects(collection, item.name)
                if obj.type == "MESH"
            ]
            if not objects:
                continue
            mesh_path = component_mesh_path(item)
            if mesh_path != item.mesh and not is_plain_file_name(
                item.mesh_collection.name
            ):
                issues.append(
                    ValidationIssue(
                        state.name,
                        item.name,
                        f'"{item.mesh_collection.name}" cannot name a mesh file',
                    )
                )
                continue
            key = mesh_path.casefold()
            if key in writes or key in copies:
                continue
            source = mesh_source(objects[0])
            new_file = (
                source is None
                or mesh_path != item.mesh
                or source.depot_path.casefold() != key
            )
            if new_file:
                base = (
                    item.base_mesh
                    or base_mesh(objects[0])
                    or (item.mesh if mesh_path != item.mesh else "")
                )
                if not base:
                    issues.append(
                        ValidationIssue(
                            state.name, item.name, f'"{mesh_path}" needs a base mesh'
                        )
                    )
                    continue
                try:
                    glb_path = layout.raw_file(mesh_path, ".glb")
                except ValueError as error:
                    issues.append(ValidationIssue(state.name, item.name, str(error)))
                    continue
                copies[key] = BaseCopy(base, mesh_path)
            elif edited_meshes and any(is_edited(obj) for obj in objects):
                glb_path = source.glb_path
            else:
                continue
            payload, _summary = build_mesh_glb_payload(
                objects,
                is_skinned=item.type_key in SKINNED_TYPES,
                garment=item.type_key == "GARMENT",
            )
            writes[key] = MeshWrite(glb_path, payload)
            written_objects.extend(objects)
    return tuple(writes.values()), tuple(copies.values()), written_objects, issues


def _store_issues(context, issues) -> None:
    tools = context.scene.cp77_entity_tools
    with suspended():
        tools.issues.clear()
        for issue in issues:
            entry = tools.issues.add()
            entry.appearance, entry.component, entry.message = (
                issue.appearance,
                issue.component,
                issue.message,
            )


@transactional("Entity export")
def export_entity(
    context, import_id: str, request: EntityExportRequest
) -> OperationResult:
    try:
        edit, issues = entity_edit(import_id)
    except (FileNotFoundError, ValueError) as error:
        return OperationResult.cancelled(str(error), error=error)
    layout = project_layout_for(edit.app_path)
    if layout is None:
        return OperationResult.cancelled(
            f"{edit.app_path} is not inside a WolvenKit project"
        )
    meshes, copies, written_objects, mesh_issues = _mesh_writes(
        import_id, request.edited_meshes, layout
    )
    if request.overwrite:
        target = ExportTarget(
            edit.ent_path, edit.app_path, True, request.all_appearances
        )
    else:
        target = ExportTarget(
            request.filepath, _app_target(edit, request), False, request.all_appearances
        )
    try:
        payloads = build_export_payloads(
            edit, target, meshes=meshes, base_copies=copies
        )
    except (FileNotFoundError, ValueError, KeyError) as error:
        return OperationResult.cancelled(str(error).strip("'\""), error=error)
    problems = (*issues, *mesh_issues, *payloads.issues)
    if problems:
        _store_issues(context, problems)
        return OperationResult.cancelled(f"Export found {len(problems)} problems")
    atomic_write_many(payloads.files)
    _store_issues(context, ())
    for obj in written_objects:
        record_import_signature(obj)
    return OperationResult.finished(
        f"Exported {os.path.basename(target.ent_path)} and {len(meshes)} meshes."
    )
