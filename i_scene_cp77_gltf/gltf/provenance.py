from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

from .container import GLBContainerError, read_glb_container

DIRECT_MESH_GENERATOR = "Cyberpunk 2077 IO Suite direct mesh exporter"
DIRECT_ANIMATION_GENERATOR = "Cyberpunk 2077 IO Suite direct animation exporter"
ORIGIN_KEY = "cp77_io_origin"
ORIGIN_VERSION_KEY = "cp77_io_origin_version"
SOURCE_GENERATOR_KEY = "cp77_io_source_generator"
SOURCE_PATH_KEY = "cp77_io_source_path"
ORIGIN_PLUGIN = "plugin"
ORIGIN_EXTERNAL = "external"
ORIGIN_VERSION = 1

_PLUGIN_MESH_KEYS = frozenset({
    "cp77_direct_document_metadata",
    "cp77_direct_mesh_extras",
    "cp77_direct_node_extras",
    "cp77_direct_mesh_skin_binding",
    "cp77_direct_mesh_source_rest_json",
    "cp77_material_name",
    "sourcePath",
})
_PLUGIN_COLLECTION_KEYS = frozenset({
    "orig_filepath",
    "cp77_direct_document_metadata",
    "cp77_direct_mesh_skin_binding",
    "cp77_material_preparation_version",
    "json_apps",
    "mesh",
})
_PLUGIN_ARMATURE_KEYS = frozenset({
    "cp77_skin_extras_json",
    "cp77_animation_source_rest_json",
    "source_rig_file",
    "rigPath",
    "merged_rigs",
})
_PLUGIN_ARMATURE_DATA_KEYS = frozenset({
    "cp77_rig_space_contract",
    "source_rig_file",
})
_WOLVENKIT_DOCUMENT_KEYS = frozenset({
    "experimentalMergedMeshes",
})
_WOLVENKIT_MESH_KEYS = frozenset({
    "materialNames",
})
_WOLVENKIT_SKIN_KEYS = frozenset({
    "rigPath",
    "boneNames",
    "boneParentIndexes",
})
_WOLVENKIT_ANIMATION_KEYS = frozenset({
    "animationType",
    "rootMotionType",
    "optimizationHints",
})


class GLBProvenanceError(RuntimeError):
    pass


class GLBSource(str, Enum):
    WOLVENKIT = "wolvenkit"
    DIRECT_MESH = "direct_mesh"
    DIRECT_ANIMATION = "direct_animation"
    EXTERNAL = "external"


class GLBContentKind(str, Enum):
    MESH = "mesh"
    ANIMATION = "animation"
    MIXED = "mixed"
    EMPTY = "empty"


class SelectionOrigin(str, Enum):
    PLUGIN = "plugin"
    EXTERNAL = "external"
    MIXED = "mixed"
    EMPTY = "empty"


@dataclass(frozen=True, slots=True)
class GLBInspection:
    filepath: str
    generator: str
    source: GLBSource
    content_kind: GLBContentKind
    asset_version: str

    @property
    def direct_import_supported(self) -> bool:
        if self.source is GLBSource.DIRECT_MESH:
            return self.content_kind is GLBContentKind.MESH
        if self.source is GLBSource.DIRECT_ANIMATION:
            return self.content_kind is GLBContentKind.ANIMATION
        if self.source is GLBSource.WOLVENKIT:
            return self.content_kind in {
                GLBContentKind.MESH,
                GLBContentKind.ANIMATION,
            }
        return False

    @property
    def claims_cp77_origin(self) -> bool:
        return self.source is not GLBSource.EXTERNAL


def _source_from_generator(generator: str) -> GLBSource:
    normalized = generator.strip().casefold()
    if normalized.startswith(DIRECT_MESH_GENERATOR.casefold()):
        return GLBSource.DIRECT_MESH
    if normalized.startswith(DIRECT_ANIMATION_GENERATOR.casefold()):
        return GLBSource.DIRECT_ANIMATION
    if "wolvenkit" in normalized:
        return GLBSource.WOLVENKIT
    return GLBSource.EXTERNAL


def _mapping_has_keys(value, keys) -> bool:
    return isinstance(value, dict) and keys.issubset(value)


def _is_wolvenkit_sharpgltf(document: dict, generator: str) -> bool:
    if not generator.strip().casefold().startswith("sharpgltf"):
        return False

    extras = document.get("extras")
    if isinstance(extras, dict) and any(
        key in extras for key in _WOLVENKIT_DOCUMENT_KEYS
    ):
        return True

    for mesh in document.get("meshes", ()) or ():
        mesh_extras = mesh.get("extras") if isinstance(mesh, dict) else None
        if isinstance(mesh_extras, dict) and any(
            key in mesh_extras for key in _WOLVENKIT_MESH_KEYS
        ):
            return True

    for skin in document.get("skins", ()) or ():
        skin_extras = skin.get("extras") if isinstance(skin, dict) else None
        if _mapping_has_keys(skin_extras, _WOLVENKIT_SKIN_KEYS):
            return True

    for animation in document.get("animations", ()) or ():
        animation_extras = (
            animation.get("extras") if isinstance(animation, dict) else None
        )
        if _mapping_has_keys(animation_extras, _WOLVENKIT_ANIMATION_KEYS):
            return True
    return False


def _source_from_document(document: dict, generator: str) -> GLBSource:
    source = _source_from_generator(generator)
    if source is not GLBSource.EXTERNAL:
        return source
    if _is_wolvenkit_sharpgltf(document, generator):
        return GLBSource.WOLVENKIT
    return GLBSource.EXTERNAL


def _content_kind(document: dict) -> GLBContentKind:
    has_meshes = bool(document.get("meshes"))
    has_animations = bool(document.get("animations"))
    if has_meshes and has_animations:
        return GLBContentKind.MIXED
    if has_meshes:
        return GLBContentKind.MESH
    if has_animations:
        return GLBContentKind.ANIMATION
    return GLBContentKind.EMPTY


def read_glb_json(filepath: str) -> dict:
    path = os.path.abspath(os.fspath(filepath))
    if not path.casefold().endswith(".glb"):
        raise GLBProvenanceError("Only binary glTF .glb files are supported.")
    try:
        return read_glb_container(path).document
    except GLBContainerError as error:
        raise GLBProvenanceError(str(error)) from error


def inspect_glb(filepath: str) -> GLBInspection:
    document = read_glb_json(filepath)
    asset = document["asset"]
    generator = str(asset.get("generator", "") or "").strip()
    return GLBInspection(
        filepath=os.path.abspath(os.fspath(filepath)),
        generator=generator,
        source=_source_from_document(document, generator),
        content_kind=_content_kind(document),
        asset_version=str(asset.get("version", "")),
    )


def _contains_any(owner, keys) -> bool:
    if owner is None:
        return False
    try:
        return any(key in owner for key in keys)
    except TypeError:
        return False


def mark_origin(owner, origin: str, *, generator: str = "", source_path: str = "") -> None:
    if owner is None:
        return
    owner[ORIGIN_KEY] = str(origin)
    owner[ORIGIN_VERSION_KEY] = ORIGIN_VERSION
    if generator:
        owner[SOURCE_GENERATOR_KEY] = str(generator)
    if source_path:
        owner[SOURCE_PATH_KEY] = os.path.abspath(os.fspath(source_path))


def object_origin(obj) -> SelectionOrigin:
    if obj is None:
        return SelectionOrigin.EXTERNAL
    explicit = str(obj.get(ORIGIN_KEY, "") or "").casefold()
    if explicit == ORIGIN_EXTERNAL:
        return SelectionOrigin.EXTERNAL
    if explicit == ORIGIN_PLUGIN:
        return SelectionOrigin.PLUGIN

    object_type = str(getattr(obj, "type", ""))
    if object_type == "MESH" and _contains_any(obj, _PLUGIN_MESH_KEYS):
        return SelectionOrigin.PLUGIN
    if object_type == "ARMATURE":
        if _contains_any(obj, _PLUGIN_ARMATURE_KEYS):
            return SelectionOrigin.PLUGIN
        if _contains_any(getattr(obj, "data", None), _PLUGIN_ARMATURE_DATA_KEYS):
            return SelectionOrigin.PLUGIN

    for collection in getattr(obj, "users_collection", ()) or ():
        explicit = str(collection.get(ORIGIN_KEY, "") or "").casefold()
        if explicit == ORIGIN_EXTERNAL:
            return SelectionOrigin.EXTERNAL
        if explicit == ORIGIN_PLUGIN or _contains_any(collection, _PLUGIN_COLLECTION_KEYS):
            return SelectionOrigin.PLUGIN
    return SelectionOrigin.EXTERNAL


def selection_origin(objects) -> SelectionOrigin:
    origins = {
        object_origin(obj)
        for obj in objects
        if str(getattr(obj, "type", "")) in {"MESH", "ARMATURE"}
    }
    if not origins:
        return SelectionOrigin.EMPTY
    if origins == {SelectionOrigin.PLUGIN}:
        return SelectionOrigin.PLUGIN
    if origins == {SelectionOrigin.EXTERNAL}:
        return SelectionOrigin.EXTERNAL
    return SelectionOrigin.MIXED
