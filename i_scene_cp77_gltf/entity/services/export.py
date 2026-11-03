from __future__ import annotations

import json
import os
from dataclasses import dataclass

from ...assetio.documents import load_json_payload
from ...assetio.paths import (
    normalize_local_path,
    same_local_path,
    split_source_tree_root,
)
from ...assetio.project_layout import base_mesh_copy_payloads, project_layout_for
from ...assetio.values import resource_path_text
from ..domain.appearances import (
    duplicate_appearance,
    keep_appearances,
    refresh_dependencies,
    remove_appearance,
    sync_entity_entries,
)
from ..domain.components import apply_appearance_edit, component_key, document_cruids
from ..domain.document import AppearanceDocument, EntityDocument
from ..domain.validation import validate
from ..model.edits import EntityEdit, ExportTarget, ValidationIssue

RAW_FOLDER_MESSAGE = "Export into the project's source/raw folder"
OVERWRITE_MESSAGE = "To write over the imported files, turn on Overwrite Imported"


@dataclass(frozen=True, slots=True)
class MeshWrite:
    glb_path: str
    payload: bytes


@dataclass(frozen=True, slots=True)
class BaseCopy:
    base_depot: str
    new_depot: str


@dataclass(frozen=True, slots=True)
class ExportPayloads:
    files: dict[str, bytes]
    issues: tuple[ValidationIssue, ...]


def _load(path: str) -> dict:
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"{path} is missing; it was moved or deleted after import"
        )
    return load_json_payload(path)


def _require_raw(path: str):
    root, remainder = split_source_tree_root(path, "raw")
    layout = project_layout_for(path)
    if not root or not remainder or layout is None:
        raise ValueError(RAW_FOLDER_MESSAGE)
    return layout


def _source_app_depot(ent: EntityDocument, edit: EntityEdit) -> str:
    for appearance in edit.appearances:
        entry = ent.entry_for(appearance.source_name) or ent.entry_for(appearance.name)
        if entry is not None:
            return resource_path_text(entry.get("appearanceResource"))
    layout = project_layout_for(edit.app_path)
    if layout is None:
        raise ValueError(f"{edit.app_path} is not inside a WolvenKit project")
    return layout.depot_path_for(edit.app_path)


def _replaced_meshes(source: AppearanceDocument, appearance_edit) -> dict[str, str]:
    current = {
        component_key(pair.listed): resource_path_text(pair.listed.get("mesh"))
        for pair in source.components(appearance_edit.source_name)
    }
    return {
        current[component.key]: component.mesh
        for component in appearance_edit.components
        if component.key in current
        and current[component.key]
        and current[component.key] != component.mesh
    }


def _json_bytes(document: dict) -> bytes:
    return json.dumps(document, indent=2, ensure_ascii=False).encode("utf-8")


def build_export_payloads(
    edit: EntityEdit,
    target: ExportTarget,
    *,
    meshes: tuple[MeshWrite, ...],
    base_copies: tuple[BaseCopy, ...],
) -> ExportPayloads:
    ent_source = _load(edit.ent_path)
    app_source = _load(edit.app_path)
    if target.overwrite:
        ent_path, app_path = edit.ent_path, edit.app_path
    else:
        ent_layout, app_layout = (
            _require_raw(target.ent_path),
            _require_raw(target.app_path),
        )
        # Absolute from here on: a relative spelling of the imported file is still the imported file.
        ent_path, app_path = (
            normalize_local_path(target.ent_path),
            normalize_local_path(target.app_path),
        )
        sources = (
            normalize_local_path(edit.ent_path),
            normalize_local_path(edit.app_path),
        )
        if any(
            same_local_path(path, source)
            for path in (ent_path, app_path)
            for source in sources
        ):
            raise ValueError(OVERWRITE_MESSAGE)

    source_app = AppearanceDocument(app_source)
    app = AppearanceDocument(json.loads(json.dumps(app_source)))
    ent = EntityDocument(ent_source)
    source_app_depot = _source_app_depot(ent, edit)

    for appearance in edit.appearances:
        if appearance.name not in app.appearance_names():
            duplicate_appearance(app, appearance.source_name, appearance.name)
    for name in edit.removed_appearances:
        remove_appearance(app, name)
    for appearance in edit.appearances:
        apply_appearance_edit(app, appearance, taken_cruids=document_cruids(app))
        refresh_dependencies(
            app, appearance.name, _replaced_meshes(source_app, appearance)
        )
    keep_all = target.overwrite or target.all_appearances
    if not keep_all:
        keep_appearances(
            app, frozenset(appearance.name for appearance in edit.appearances)
        )
    app_depot = (
        source_app_depot if target.overwrite else app_layout.depot_path_for(app_path)
    )
    sync_entity_entries(
        ent,
        edit,
        app_depot=app_depot,
        source_app_depot=source_app_depot,
        keep_all=keep_all,
    )

    issues = validate(
        app,
        ent,
        edit,
        source_app=source_app,
        source_ent=EntityDocument(load_json_payload(edit.ent_path)),
    )
    if issues:
        return ExportPayloads({}, issues)

    if not target.overwrite:
        ent.document["Header"]["ArchiveFileName"] = ent_layout.archive_file(
            ent_layout.depot_path_for(ent_path)
        )
        app.document["Header"]["ArchiveFileName"] = app_layout.archive_file(app_depot)
    files = {ent_path: _json_bytes(ent.document), app_path: _json_bytes(app.document)}
    for mesh in meshes:
        files[mesh.glb_path] = mesh.payload
    if base_copies:
        source_layout = project_layout_for(edit.app_path)
        if source_layout is None:
            raise ValueError(f"{edit.app_path} is not inside a WolvenKit project")
        for copy_ in base_copies:
            # A base copy that already exists may already hold the author's WolvenKit import; it is never rewritten.
            files.update(
                (path, payload)
                for path, payload in base_mesh_copy_payloads(
                    source_layout, copy_.base_depot, copy_.new_depot
                ).items()
                if not os.path.exists(path)
            )
    return ExportPayloads(files, ())
