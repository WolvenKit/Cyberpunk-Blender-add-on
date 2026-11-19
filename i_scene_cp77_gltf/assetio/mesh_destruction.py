"""Which render chunks of a destruction mesh the game draws before it breaks

A destruction mesh (``*_dst.mesh``) holds the intact object and its pre-fractured pieces as separate render chunks
that occupy the same space. ``meshMeshParamDestructionBoneChunkMapping.boneChunkMasks`` lists, per destruction bone,
the chunks that bone's geometry lives in; bone 0 (``b_000_0``) is the intact object, so its mask is what is drawn
until the object takes damage. The glTF export drops that parameter, so it is read from the binary ``.mesh`` in the
project's ``source/archive`` or the configured depot, or failing that from the mesh's ``.mesh.json`` sidecar.
"""

from __future__ import annotations

import json
import os
import struct
from dataclasses import dataclass

from .paths import confined_join
from .project_layout import project_layout_for

_MAPPING_CLASS = "meshMeshParamDestructionBoneChunkMapping"
_MAPPING_PROPERTY = "boneChunkMasks"
_CR2W_MAGIC = b"CR2W"
# Magic, file header and the ten table headers.
_CR2W_PREAMBLE = 4 + 36 + 10 * 12
_CR2W_EXPORT_SIZE = 24


@dataclass(frozen=True, slots=True)
class DestructionChunks:
    """What the lookup found for one mesh"""

    # Bone 0's chunk mask, or None when the mesh is not a destruction mesh or no resource was found.
    intact_mask: int | None
    # Whether a .mesh or .mesh.json was found to read.
    resolved: bool

    def is_fractured(self, submesh_index) -> bool:
        """Whether the chunk at submesh_index is only drawn once the object breaks"""
        if self.intact_mask is None or submesh_index is None:
            return False
        index = int(submesh_index)
        if not 0 <= index < 64:
            return False
        return not (self.intact_mask >> index) & 1


_NOT_DESTRUCTION = DestructionChunks(None, True)
_UNRESOLVED = DestructionChunks(None, False)


def _bone_zero_mask(masks) -> int | None:
    if not masks:
        return None
    try:
        return int(masks[0])
    except (TypeError, ValueError):
        return None


def bone_chunk_masks_from_cr2w(path: str) -> tuple[int, ...] | None:
    """The boneChunkMasks of a binary CR2W .mesh, or None when it has none"""
    try:
        with open(path, "rb") as stream:
            preamble = stream.read(_CR2W_PREAMBLE)
            if len(preamble) < _CR2W_PREAMBLE or preamble[:4] != _CR2W_MAGIC:
                return None
            tables = [
                struct.unpack_from("<III", preamble, 40 + 12 * index)
                for index in range(10)
            ]
            strings_offset, strings_size, _ = tables[0]
            names_offset, names_count, _ = tables[1]
            exports_offset, exports_count, _ = tables[4]

            stream.seek(strings_offset)
            strings = stream.read(strings_size)
            # Most meshes are not destruction meshes; skip them before parsing anything else.
            if _MAPPING_CLASS.encode("ascii") not in strings:
                return None

            stream.seek(names_offset)
            name_table = stream.read(8 * names_count)

            def name(index):
                offset = struct.unpack_from("<I", name_table, 8 * index)[0]
                end = strings.index(b"\0", offset)
                return strings[offset:end].decode("utf-8", "replace")

            names = [name(index) for index in range(names_count)]
            stream.seek(exports_offset)
            export_table = stream.read(_CR2W_EXPORT_SIZE * exports_count)
            for index in range(exports_count):
                class_index, _flags, _parent, data_size, data_offset = (
                    struct.unpack_from(
                        "<HHIII", export_table, _CR2W_EXPORT_SIZE * index
                    )
                )
                if class_index >= len(names) or names[class_index] != _MAPPING_CLASS:
                    continue
                stream.seek(data_offset)
                data = stream.read(data_size)
                return _read_mask_property(data, names)
    except (OSError, struct.error, ValueError, IndexError):
        return None
    return None


def _read_mask_property(data: bytes, names: list[str]) -> tuple[int, ...] | None:
    # An export's data is a zero byte, then (name, type, size, value) properties up to a zero name.
    if not data or data[0] != 0:
        return None
    position = 1
    while position + 8 <= len(data):
        name_index, _type_index, size = struct.unpack_from("<HHI", data, position)
        if name_index == 0 or name_index >= len(names) or size < 4:
            return None
        value = position + 8
        if names[name_index] == _MAPPING_PROPERTY:
            count = struct.unpack_from("<I", data, value)[0]
            if value + 4 + 8 * count > len(data):
                return None
            return struct.unpack_from(f"<{count}Q", data, value + 4)
        # The size counts its own four bytes.
        position += 4 + size
    return None


def bone_chunk_masks_from_json(document) -> tuple[int, ...] | None:
    """The boneChunkMasks of a WolvenKit .mesh.json document, or None when it has none"""
    try:
        parameters = document["Data"]["RootChunk"].get("parameters") or ()
    except (KeyError, TypeError, AttributeError):
        return None
    for parameter in parameters:
        data = parameter.get("Data") if isinstance(parameter, dict) else None
        if not isinstance(data, dict) or data.get("$type") != _MAPPING_CLASS:
            continue
        try:
            return tuple(int(value) for value in data.get(_MAPPING_PROPERTY) or ())
        except (TypeError, ValueError):
            return None
    return None


def _json_masks(path: str) -> tuple[int, ...] | None:
    try:
        with open(path, encoding="utf-8") as stream:
            text = stream.read()
    except (OSError, UnicodeDecodeError):
        return None
    if _MAPPING_CLASS not in text:
        return None
    try:
        return bone_chunk_masks_from_json(json.loads(text))
    except ValueError:
        return None


def _mesh_depot_path(glb_path: str) -> str:
    layout = project_layout_for(glb_path)
    if layout is None:
        return ""
    try:
        depot = layout.depot_path_for(glb_path)
    except ValueError:
        return ""
    return os.path.splitext(depot)[0] + ".mesh"


def _candidates(glb_path: str, depot_root: str):
    """(kind, path) of each resource that could hold the mesh's destruction parameters, best first"""
    stem = os.path.splitext(glb_path)[0]
    depot = _mesh_depot_path(glb_path)
    if depot:
        layout = project_layout_for(glb_path)
        try:
            yield "cr2w", layout.archive_file(depot)
        except ValueError:
            pass
        if depot_root:
            try:
                yield "cr2w", confined_join(depot_root, depot)
            except ValueError:
                pass
    yield "json", stem + ".mesh.json"


_CACHE: dict[tuple[str, str], tuple[float, DestructionChunks]] = {}


def destruction_chunks_for_glb(
    glb_path: str, depot_root: str = ""
) -> DestructionChunks:
    """What the mesh exported to glb_path draws before it breaks"""
    if not glb_path:
        return _NOT_DESTRUCTION
    key = (os.path.normcase(os.path.abspath(glb_path)), depot_root or "")
    try:
        stamp = os.path.getmtime(glb_path)
    except OSError:
        stamp = -1.0
    cached = _CACHE.get(key)
    if cached is not None and cached[0] == stamp:
        return cached[1]
    result = _UNRESOLVED
    for kind, path in _candidates(glb_path, depot_root):
        if not os.path.isfile(path):
            continue
        masks = (
            bone_chunk_masks_from_cr2w(path) if kind == "cr2w" else _json_masks(path)
        )
        mask = _bone_zero_mask(masks)
        result = _NOT_DESTRUCTION if mask is None else DestructionChunks(mask, True)
        break
    _CACHE[key] = (stamp, result)
    return result


def clear_destruction_cache() -> None:
    _CACHE.clear()
