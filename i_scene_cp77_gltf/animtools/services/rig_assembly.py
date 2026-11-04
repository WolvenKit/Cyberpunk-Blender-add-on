from __future__ import annotations

import os

from ...animation.domain.rig.assembly import (
    metarig_imported_sources,
    metarig_ledger_signature,
    metarig_part_role,
    part_path_key,
)
from ...blender.animation_context import track_id_properties
from ...blender.operator_results import OperationResult
from ...blender.rig_metadata import metarig_part_ledger, record_metarig_user_edit
from ...blender.transactions import transactional
from ...core.log import get_logger
from ...importers.entity.rigs import reconcile_existing_metarig_parts
from ..runtime.read_models import metarig_ledger_signature_for

_LOG = get_logger(__name__)


def _state(context):
    return context.scene.cp77_rig_assembly


def state_is_current(context, armature=None) -> bool:
    armature = armature or context.active_object
    state = _state(context)
    return state.armature_name == getattr(
        armature, "name", ""
    ) and state.source_signature == metarig_ledger_signature_for(armature)


def sync_state(context, armature=None, *, force=False):
    """Mirror the armature's MetaRig ledger into the scene's part list shown by the panel"""
    armature = armature or context.active_object
    state = _state(context)
    ledger = metarig_part_ledger(armature)
    signature = metarig_ledger_signature(ledger)
    if (
        not force
        and state.armature_name == getattr(armature, "name", "")
        and state.source_signature == signature
    ):
        return state
    selected_identity = ""
    if 0 <= state.active_index < len(state.parts):
        selected = state.parts[state.active_index]
        selected_identity = part_path_key(selected.source_path or selected.path)
    state.parts.clear()
    for index, entry in enumerate(ledger):
        rig_path = entry["path"]
        item = state.parts.add()
        item.source_path = entry["source_path"]
        item.path = rig_path
        item.label = os.path.basename(rig_path)
        item.user_addition = bool(entry["user_addition"])
        item.role = metarig_part_role(rig_path, index, user_addition=item.user_addition)
    state.armature_name = getattr(armature, "name", "")
    state.source_signature = signature
    state.active_index = next(
        (
            index
            for index, item in enumerate(state.parts)
            if part_path_key(item.source_path or item.path) == selected_identity
        ),
        max(0, min(state.active_index, max(0, len(state.parts) - 1))),
    )
    return state


def _selected_index(state, ledger) -> int:
    return max(0, min(state.active_index, len(ledger) - 1))


def _reconcile(context, target, ledger, edit):
    sources = metarig_imported_sources(ledger)
    before = {bone.name for bone in target.data.bones}
    track_id_properties(target, label="MetaRig part edit")
    record_metarig_user_edit(target, **edit)
    try:
        reconcile_existing_metarig_parts(target, sources)
    except Exception as error:
        _LOG.error(
            "MetaRig update failed on '%s': %s: %s",
            target.name,
            type(error).__name__,
            error,
            exc_info=True,
        )
        return None, OperationResult(
            False, f"MetaRig update failed: {type(error).__name__}: {error}", "ERROR"
        )
    after = {bone.name for bone in target.data.bones}
    sync_state(context, target, force=True)
    return (len(after - before), len(before - after)), None


@transactional("MetaRig part edit")
def edit_part(context, target, operation: str, path: str) -> OperationResult:
    """Add a rig part, or replace the selected one, and rebuild the MetaRig from its sources"""
    state = sync_state(context, target)
    ledger = metarig_part_ledger(target)
    if operation == "ADD":
        if part_path_key(path) in {part_path_key(entry["path"]) for entry in ledger}:
            return OperationResult(
                False, "That rig part is already present in the MetaRig.", "ERROR"
            )
        edit = {"operation": "ADD", "new_path": path, "user_addition": True}
    else:
        if not ledger:
            return OperationResult(
                False,
                "The selected armature has no imported MetaRig part ledger.",
                "ERROR",
            )
        selected = ledger[_selected_index(state, ledger)]
        edit = {
            "operation": "REPLACE",
            "source_path": selected.get("source_path", ""),
            "old_path": selected["path"],
            "new_path": path,
            "user_addition": bool(selected.get("user_addition", False)),
        }
    counts, failure = _reconcile(context, target, ledger, edit)
    if failure is not None:
        return failure
    added, removed = counts
    return OperationResult(
        True, f"MetaRig updated: {added} bones added, {removed} removed."
    )


@transactional("MetaRig part removal")
def remove_selected_part(context, target) -> OperationResult:
    state = sync_state(context, target)
    ledger = metarig_part_ledger(target)
    if len(ledger) <= 1:
        return OperationResult(False, "The MetaRig base cannot be removed.", "ERROR")
    index = _selected_index(state, ledger)
    selected = ledger[index]
    if index == 0 and not selected.get("user_addition", False):
        return OperationResult(
            False, "Replace the MetaRig base rather than removing it.", "ERROR"
        )
    edit = {
        "operation": "REMOVE",
        "source_path": selected.get("source_path", ""),
        "old_path": selected["path"],
        "user_addition": bool(selected.get("user_addition", False)),
    }
    counts, failure = _reconcile(context, target, ledger, edit)
    if failure is not None:
        return failure
    added, removed = counts
    return OperationResult(
        True,
        f"Removed {os.path.basename(selected['path'])}; {added} bones added, {removed} removed.",
    )
