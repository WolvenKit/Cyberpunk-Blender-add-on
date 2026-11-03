from __future__ import annotations

from collections.abc import Mapping, Sequence

import bpy

from ..animation.domain.rig.assembly import (
    METARIG_PART_LEDGER_KEY,
    METARIG_PART_OVERRIDES_KEY,
    METARIG_REMOVED_PARTS_KEY,
    METARIG_REMOVED_SLOTS_KEY,
    METARIG_USER_ADDITIONS_KEY,
    MetaRigUserEdits,
    apply_metarig_user_edit,
    decode_metarig_part_ledger,
    normalized_part_path,
    resolve_metarig_part_ledger,
)
from ..animation.domain.rig.masks import (
    RIG_PART_MASKS_KEY,
    RIG_PART_ROTATION_MS_KEY,
    decode_rig_part_masks,
    decode_rig_part_rotation_ms,
    encode_rig_part_masks,
    encode_rig_part_rotation_ms,
)
from ..animation.domain.rig.metadata import (
    RIG_PART_DOCUMENTS_KEY,
    decode_rig_part_bindings,
    decode_rig_part_documents,
    encode_json_document,
    source_rig_paths_from,
)
from ..assetio.paths import local_path_key
from ..assetio.values import json_array

_STORED_DOCUMENT_LIMIT = 8
_STORED_DOCUMENTS = {}


def store_rig_part_rotation_ms(
    armature, rotation_ms: Mapping[str, Sequence[str]]
) -> None:
    armature[RIG_PART_ROTATION_MS_KEY] = encode_rig_part_rotation_ms(rotation_ms)


def load_rig_part_rotation_ms(armature) -> dict[str, list[str]]:
    return decode_rig_part_rotation_ms(
        armature.get(RIG_PART_ROTATION_MS_KEY) if armature is not None else None
    )


def store_rig_part_masks(armature, masks: Mapping[str, Mapping[str, float]]) -> None:
    armature[RIG_PART_MASKS_KEY] = encode_rig_part_masks(masks)


def load_rig_part_masks(armature) -> dict[str, dict[str, float]]:
    return decode_rig_part_masks(
        armature.get(RIG_PART_MASKS_KEY) if armature is not None else None
    )


def rig_part_mask_names(armature) -> tuple[str, ...]:
    return tuple(load_rig_part_masks(armature))


def source_rig_paths(armature) -> tuple[str, ...]:
    """Collect active source parts, including legacy single-rig import metadata"""
    data = getattr(armature, "data", {})
    return source_rig_paths_from(
        armature.get(METARIG_PART_LEDGER_KEY, "[]"),
        armature.get("cp77_rig_merge_order") or (),
        (
            str(owner.get(key, "") or "")
            for owner in (armature, data)
            for key in ("rig", "cp77_source_rig_file")
        ),
    )


def store_rig_part_documents(armature, documents: Mapping[str, dict]) -> None:
    """Keep the rig documents of armature's parts on it, by part path, for the tools that read a part's rig"""
    armature.data[RIG_PART_DOCUMENTS_KEY] = encode_json_document(dict(documents))


def _stored_documents(payload: str) -> dict:
    documents = _STORED_DOCUMENTS.get(payload)
    if documents is None:
        documents = {
            local_path_key(path): document
            for path, document in decode_rig_part_documents(payload).items()
        }
        if len(_STORED_DOCUMENTS) >= _STORED_DOCUMENT_LIMIT:
            _STORED_DOCUMENTS.pop(next(iter(_STORED_DOCUMENTS)))
        _STORED_DOCUMENTS[payload] = documents
    return documents


def stored_rig_part_document(path):
    """The rig document a MetaRig in the file carries for the part path path, or None"""
    key = local_path_key(path)
    for armature in bpy.data.armatures:
        payload = armature.get(RIG_PART_DOCUMENTS_KEY)
        if payload:
            document = _stored_documents(str(payload)).get(key)
            if document is not None:
                return document
    return None


def source_rig_part_bindings(armature) -> tuple[dict[str, str], ...]:
    return decode_rig_part_bindings(armature.get("cp77_metarig_part_bindings", "[]"))


def imported_bone_names(armature):
    """Legacy imports already stamp each source bone, so ownership is never inferred by exclusion"""
    source_names = tuple(str(name) for name in armature.data.get("boneNames", ()))
    result = set()
    for bone in armature.data.bones:
        source = str(bone.get("cp77_rig_source_name", "") or "")
        index = bone.get("cp77_rig_index")
        if source == bone.name or (
            not source
            and isinstance(index, int)
            and 0 <= index < len(source_names)
            and source_names[index] == bone.name
        ):
            result.add(bone.name)
    return frozenset(result)


def stored_json_array(owner, key: str) -> list:
    return json_array(owner.get(key, "[]"))


def metarig_user_edits(owner) -> MetaRigUserEdits:
    return MetaRigUserEdits.decode(
        owner.get(METARIG_PART_OVERRIDES_KEY, "{}"),
        owner.get(METARIG_USER_ADDITIONS_KEY, "[]"),
        owner.get(METARIG_REMOVED_PARTS_KEY, "[]"),
        owner.get(METARIG_REMOVED_SLOTS_KEY, "[]"),
    )


def effective_metarig_part_ledger(existing_rig, source_paths):
    return resolve_metarig_part_ledger(source_paths, metarig_user_edits(existing_rig))


def metarig_part_ledger(armature) -> tuple[dict, ...]:
    """The armature's active MetaRig parts, falling back to its legacy source-rig metadata"""
    if armature is None or getattr(armature, "type", None) != "ARMATURE":
        return ()
    entries = decode_metarig_part_ledger(armature.get(METARIG_PART_LEDGER_KEY, "[]"))
    if entries:
        return entries
    return tuple(
        {
            "source_path": normalized_part_path(value),
            "path": normalized_part_path(value),
            "user_addition": False,
        }
        for value in source_rig_paths(armature)
        if value
    )


def record_metarig_user_edit(
    target,
    operation,
    *,
    source_path="",
    old_path="",
    new_path="",
    user_addition=False,
) -> None:
    """Record a user ADD, REPLACE or REMOVE so effective_metarig_part_ledger reproduces it"""
    edits = apply_metarig_user_edit(
        metarig_user_edits(target),
        operation,
        source_path=source_path,
        old_path=old_path,
        new_path=new_path,
        user_addition=user_addition,
    )
    for key, text in edits.encoded().items():
        target[key] = text
