from __future__ import annotations

import sys

import bpy

from ...animation.domain.clip.additive import is_additive_animation_type
from ...animation.domain.rig.assembly import metarig_ledger_signature
from ...animation.domain.rig.masks import RIG_PART_MASKS_KEY
from ...animation.model.clip.metadata import SKIN_EXTRAS_SNAPSHOT_KEY
from ...assetio.metarig_bundle import bundled_metarigs
from ...assetio.values import json_object
from ...blender.animgraph import sm_edit
from ...blender.animgraph.validation import reporting
from ...blender.identity import rna_identity
from ...blender.rig_metadata import metarig_part_ledger, rig_part_mask_names
from ..blender.root_motion_targets import motion_targets
from ..model.animgraph import VALIDATION_REPORT_KEY

_LEDGER_KEYS = (
    "cp77_metarig_part_ledger",
    "cp77_rig_merge_order",
    "rig",
    "cp77_source_rig_file",
)
_LEDGER_SIGNATURES: dict[tuple, str] = {}
_LEDGER_LIMIT = 32
_VALIDATION_REPORTS: dict[int, tuple[str, dict]] = {}
_STATE_ROWS: dict[int, tuple] = {}

_FULL_BODY_MASK_ITEM = ("NONE", "Full Body", "Full pose", 0)
_NO_SECOND_ADDITIVE_ITEM = ("NONE", "None", "No second additive", 0)
_NO_RIGS = (("", "No bundled rigs", ""),)
# Blender keeps pointers into dynamic enum item strings, so the last items stay referenced here.
_ENUM_ITEMS: dict[str, tuple] = {
    "masks": (None, (_FULL_BODY_MASK_ITEM,)),
    "additive_actions": (None, (_NO_SECOND_ADDITIVE_ITEM,)),
    "bundled_rigs": (None, _NO_RIGS),
}
_MOTION_TARGETS: dict[int, tuple[tuple, tuple[str, str]]] = {}


def _raw_ledger_inputs(armature) -> tuple:
    data = getattr(armature, "data", None)
    return tuple(
        repr(owner.get(key)) if owner is not None else ""
        for owner in (armature, data)
        for key in _LEDGER_KEYS
    )


def metarig_ledger_signature_for(armature) -> str:
    """Signature of the armature's MetaRig ledger, decoded only when its source properties change"""
    if armature is None:
        return metarig_ledger_signature(())
    key = (rna_identity(armature), _raw_ledger_inputs(armature))
    signature = _LEDGER_SIGNATURES.get(key)
    if signature is None:
        if len(_LEDGER_SIGNATURES) >= _LEDGER_LIMIT:
            _LEDGER_SIGNATURES.clear()
        signature = metarig_ledger_signature(metarig_part_ledger(armature))
        _LEDGER_SIGNATURES[key] = signature
    return signature


def validation_report(tree) -> dict:
    """The stored Graph Validator report of tree's root graph, decoded once per stored revision"""
    root = reporting.root_tree(tree)
    raw = reporting.report_text(root, report_key=VALIDATION_REPORT_KEY)
    if not raw:
        return {}
    key = rna_identity(root)
    cached = _VALIDATION_REPORTS.get(key)
    if cached is None or cached[0] != raw:
        cached = (raw, json_object(raw))
        _VALIDATION_REPORTS[key] = cached
    return cached[1]


def refresh_state_rows(sm_node) -> tuple:
    """Recompute the state list rows of sm_node"""
    rows = sm_edit.state_rows(sm_node)
    _STATE_ROWS[rna_identity(sm_node)] = rows
    return rows


def state_rows(sm_node) -> tuple:
    rows = _STATE_ROWS.get(rna_identity(sm_node))
    return rows if rows is not None else refresh_state_rows(sm_node)


def _cached_enum(name: str, signature, build) -> tuple:
    cached_signature, items = _ENUM_ITEMS[name]
    if cached_signature != signature:
        items = tuple(build())
        _ENUM_ITEMS[name] = (signature, items)
    return items


def additive_mask_items(armature) -> tuple:
    """Rig part mask enum items for armature"""
    if armature is None:
        return (_FULL_BODY_MASK_ITEM,)
    signature = (
        str(getattr(armature, "name", "")),
        str(armature.get(RIG_PART_MASKS_KEY, "")),
    )

    def build():
        yield _FULL_BODY_MASK_ITEM
        for index, name in enumerate(rig_part_mask_names(armature), start=1):
            identifier = sys.intern(str(name))
            yield (identifier, identifier, sys.intern(f"Mask: {name}"), index)

    return _cached_enum("masks", signature, build)


def additive_action_items() -> tuple:
    """Enum items for the second additive slot"""
    entries = tuple(
        (action.name, str(action.get("animationType", "Normal") or "Normal"))
        for action in bpy.data.actions
    )

    def build():
        yield _NO_SECOND_ADDITIVE_ITEM
        index = 1
        for name, animation_type in entries:
            if is_additive_animation_type(animation_type):
                yield (
                    sys.intern(name),
                    sys.intern(name),
                    sys.intern(animation_type),
                    index,
                )
                index += 1

    return _cached_enum("additive_actions", entries, build)


def bundled_rig_items(_self=None, _context=None) -> tuple:
    """Enum items for the bundled rig list"""
    bundles = bundled_metarigs()
    return _cached_enum(
        "bundled_rigs",
        bundles,
        lambda: (
            tuple((identifier, name, "") for identifier, name, _path in bundles)
            or _NO_RIGS
        ),
    )


def root_motion_targets(armature, root: str, source: str) -> tuple[str, str]:
    """motion_targets() for the root motion panel"""
    action = armature.animation_data.action
    key = rna_identity(armature)
    signature = (
        rna_identity(action),
        str(root),
        str(source),
        len(armature.pose.bones),
        str(action.get(SKIN_EXTRAS_SNAPSHOT_KEY, "")),
        str(armature.get(SKIN_EXTRAS_SNAPSHOT_KEY, "")),
    )
    cached = _MOTION_TARGETS.get(key)
    if cached is None or cached[0] != signature:
        cached = (signature, motion_targets(armature, root, source))
        _MOTION_TARGETS[key] = cached
    return cached[1]


def clear() -> None:
    _LEDGER_SIGNATURES.clear()
    _VALIDATION_REPORTS.clear()
    _STATE_ROWS.clear()
    _MOTION_TARGETS.clear()
