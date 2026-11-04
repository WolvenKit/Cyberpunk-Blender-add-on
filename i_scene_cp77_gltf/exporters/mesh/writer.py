import os

from ...assetio.paths import is_morphtarget_path
from ...gltf.container import encode_glb
from ...gltf.provenance import SOURCE_PATH_KEY, SelectionOrigin, object_origin
from ..common.glb_output import write_validated_glb
from .document import build_direct_mesh_glb
from .document_validation import (
    validate_direct_mesh_document,
    validate_direct_mesh_glb_file,
    validate_direct_mesh_glb_payload,
)


def mesh_glb_path(filepath: str, objects) -> str:
    """Retain the resource suffix when exporting imported WolvenKit morph meshes"""
    path = os.fspath(filepath)
    meshes = tuple(obj for obj in objects if obj.type == "MESH")
    if not meshes or not all(
        object_origin(obj) is SelectionOrigin.PLUGIN
        and is_morphtarget_path(obj.get(SOURCE_PATH_KEY, ""))
        for obj in meshes
    ):
        return path
    for extension in (".glb", ".gltf"):
        if path.casefold().endswith(extension):
            path = path[: -len(extension)]
            break
    while path.casefold().endswith(".morphtarget"):
        path = path[: -len(".morphtarget")]
    return path + ".morphtarget.glb"


def export_mesh_glb_direct(
    filepath: str,
    objects,
    *,
    armature=None,
    is_skinned: bool = True,
    apply_modifiers: bool = True,
    encode_wolvenkit_uvs: bool = True,
    bake_transforms: bool = True,
    export_garment_morph: bool = True,
    export_garment_attributes: bool = True,
    ensure_garment_attributes: bool = False,
) -> dict:
    """Write a WolvenKit-compatible mesh GLB and validate the result on disk"""
    objects = tuple(objects)
    document, binary, summary = _validated_document(
        objects,
        armature=armature,
        is_skinned=is_skinned,
        apply_modifiers=apply_modifiers,
        encode_wolvenkit_uvs=encode_wolvenkit_uvs,
        bake_transforms=bake_transforms,
        export_garment_morph=export_garment_morph,
        export_garment_attributes=export_garment_attributes,
        ensure_garment_attributes=ensure_garment_attributes,
    )
    summary.update(
        write_validated_glb(
            mesh_glb_path(filepath, objects),
            document,
            binary,
            validate_direct_mesh_glb_file,
        )
    )
    return summary


def mesh_glb_payload(objects, **options) -> tuple[bytes, dict]:
    """The bytes export_mesh_glb_direct would write for objects"""
    document, binary, summary = _validated_document(tuple(objects), **options)
    payload = encode_glb(document, binary)
    summary["file_validation"] = validate_direct_mesh_glb_payload(payload)
    summary["file_bytes"] = len(payload)
    return payload, summary


def _validated_document(objects, **options):
    document, binary, summary = build_direct_mesh_glb(objects, **options)
    summary["document_validation"] = validate_direct_mesh_document(document, binary)
    return document, binary, summary
