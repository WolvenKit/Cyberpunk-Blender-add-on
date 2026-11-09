from __future__ import annotations

import numpy as np

from ...animation.domain.rig.assembly import merge_rig_datas
from ...animation.services.rig.parser import parse_rig_payload
from ...assetio.metarig_bundle import read_metarig_bundle
from ...assetio.paths import local_path_key
from ...assetio.values import json_array
from ...blender.rig_metadata import store_rig_part_documents
from ...blender.transactions import transactional
from ...core.log import get_logger
from .reader import (
    create_armature_from_rig_data,
    merged_rig_document,
    rig_data_definition_hash,
)

_LOG = get_logger(__name__)
# What entity import gives a MetaRig that no part edit has touched.
_UNEDITED = {
    "cp77_metarig_part_overrides": "{}",
    "cp77_metarig_user_additions": "[]",
    "cp77_metarig_removed_parts": "[]",
    "cp77_metarig_removed_slots": "[]",
}
_REST_TOLERANCE = 1.0e-4


def _base_rig_datas(properties, paths, rig_datas) -> list:
    """The base parts' rigs in merge order"""
    keys = {
        local_path_key(path)
        for path in json_array(properties.get("cp77_metarig_base_effective_order"))
    }
    keys |= {
        local_path_key(entry.get("path", ""))
        for entry in json_array(properties.get("cp77_metarig_part_ledger"))
        if isinstance(entry, dict) and entry.get("user_addition")
    }
    return [
        data for path, data in zip(paths, rig_datas) if local_path_key(path) in keys
    ]


def _check_rest(armature, bundle, path) -> None:
    bones = armature.data.bones
    missing = [name for name in bundle.rest_bone_names if bones.get(name) is None]
    worst = max(
        (
            float(np.max(np.abs(np.array(bones[name].matrix_local) - matrix)))
            for name, matrix in zip(bundle.rest_bone_names, bundle.rest_matrices)
            if bones.get(name) is not None
        ),
        default=0.0,
    )
    if missing or worst > _REST_TOLERANCE:
        _LOG.warning(
            "%s rebuilt differently from the rig it was written from: %d bone(s) missing, rest off by up to %.6f",
            path,
            len(missing),
            worst,
        )


@transactional("Load bundled rig")
def import_bundled_metarig(path, *, collection=None):
    """Build the MetaRig bundled at path and return its armature"""
    bundle = read_metarig_bundle(path)
    if not bundle.parts:
        raise ValueError(f"{path} bundles no rig parts")
    paths = [part.path for part in bundle.parts]
    rig_datas = [parse_rig_payload(part.document, part.path) for part in bundle.parts]
    name = bundle.rig_name or bundle.name
    merged = merge_rig_datas(rig_datas, name)
    source_label = "metarig:" + ";".join(paths)
    armature = create_armature_from_rig_data(
        merged,
        "A-Pose",
        source_rig_file=source_label,
        source_document=merged_rig_document(paths, merged, source_label, rig_datas),
        collection=collection,
    )
    store_rig_part_documents(
        armature, {part.path: part.document for part in bundle.parts}
    )
    definition_hash = rig_data_definition_hash(merged)
    properties = {**_UNEDITED, **bundle.properties}
    properties.update(
        {
            "rig": paths[0],
            "cp77_source_rig_file": source_label,
            "cp77_rig_merge_order": list(paths),
            "cp77_metarig_definition_hash": definition_hash,
            "cp77_metarig_overlay_owner_hash": definition_hash,
        }
    )
    base = _base_rig_datas(bundle.properties, paths, rig_datas)
    if base:
        base_rig = merge_rig_datas(base, name + "_base")
        properties["cp77_metarig_base_definition_hash"] = rig_data_definition_hash(
            base_rig
        )
    for key, value in properties.items():
        armature[key] = value
    _check_rest(armature, bundle, path)
    return armature
