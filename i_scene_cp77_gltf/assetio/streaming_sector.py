from __future__ import annotations

import copy
import functools
import itertools
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from .documents import load_json_payload
from .handles import HandleIndex
from .headers import patch_2_5_header
from .names import fnv1a64
from .paths import depot_path_key, depot_to_local_fragment
from .resources import get_resources_dir
from .transform_values import (
    encode_wkit_quaternion,
    quaternion_ijkr_from_wxyz,
    quaternion_wxyz_from_wkit,
    vector3_entry,
    vector3_from_data,
    vector4_entry,
    world_transform_entry,
)
from .values import cname_entry, coerce_float, coerce_int, nested_dict

SECTOR_LAYOUT_VERSION = 68
# The instance index of a plain node's entry: it picks no inner node.
_PLAIN_NODE_INSTANCE_INDEX = 4294967295
# The fields of a node data entry that a copy of its node keeps: its streaming settings and the inplace resource of its
# node's resources. A copy takes the others afresh.
_COPIED_ENTRY_FIELDS = (
    "dataGroup",
    "externalInplaceResourceHash",
    "nodeFlags",
    "streamingPriority",
    "todvisMask",
)


def _casefold_sorted(fields: dict) -> dict:
    """fields in the order WolvenKit writes a node's fields"""
    return dict(sorted(fields.items(), key=lambda item: item[0].casefold()))


_NO_RESOURCE = {
    "DepotPath": {"$type": "ResourcePath", "$storage": "uint64", "$value": "0"},
    "Flags": "Soft",
}
_DEFAULT_APPEARANCE = cname_entry("default")
_ZERO_VECTOR4 = vector4_entry(0, 0, 0, 0)
# worldNode's fields as WolvenKit writes them, the RTTI class's two and five of WolvenKit's own, at their defaults.
_NODE_FIELDS = {
    "debugName": cname_entry("None"),
    "isHostOnly": 0,
    "isVisibleInGame": 1,
    "proxyScale": None,
    "sourcePrefabHash": "0",
    "tag": "None",
    "tagExt": "None",
}
_MESH_NODE_FIELDS = {
    **_NODE_FIELDS,
    "castLocalShadows": "Default",
    "castRayTracedGlobalShadows": "Default",
    "castRayTracedLocalShadows": "Default",
    "castShadows": "Default",
    "forceAutoHideDistance": 0,
    "lodLevelScales": 4294967295,
    "mesh": _NO_RESOURCE,
    "meshAppearance": _DEFAULT_APPEARANCE,
    "occluderAutohideDistanceScale": 255,
    "occluderType": "Default",
    "removeFromRainMap": 0,
    "renderSceneLayerMask": "Default",
    # Every plain mesh node of the patch 2.5 game sectors holds version 2.
    "version": 2,
    "windImpulseEnabled": 1,
}
_BENDED_MESH_NODE_FIELDS = {
    **_NODE_FIELDS,
    "castLocalShadows": "Default",
    "castShadows": "Default",
    "deformationData": [],
    "deformedBox": {"$type": "Box", "Max": _ZERO_VECTOR4, "Min": _ZERO_VECTOR4},
    "isBendedRoad": 0,
    "mesh": _NO_RESOURCE,
    "meshAppearance": _DEFAULT_APPEARANCE,
    "navigationSetting": {
        "$type": "NavGenNavigationSetting",
        "navmeshImpact": "Walkable",
    },
    "removeFromRainMap": 0,
    "version": 0,
}
# The plain classes a copy of a cooked or instanced node's placement is written as, each with its fields (the RTTI
# class's and its parents', as WolvenKit writes them) and the value of one its inner node does not hold: WolvenKit's
# default, or the game's where every game sector agrees on another.
PLAIN_NODE_FIELDS: Mapping[str, Mapping[str, Any]] = MappingProxyType(
    {
        name: MappingProxyType(_casefold_sorted(fields))
        for name, fields in {
            "worldAcousticSectorNode": {
                **_NODE_FIELDS,
                "data": _NO_RESOURCE,
                "edgeMask": 0,
                "generatorId": 0,
                "inSectorCoordsX": 0,
                "inSectorCoordsY": 0,
                "inSectorCoordsZ": 0,
            },
            "worldBendedMeshNode": _BENDED_MESH_NODE_FIELDS,
            "worldCableMeshNode": {
                **_BENDED_MESH_NODE_FIELDS,
                "cableLength": 0,
                "cableRadius": 0,
                "destructionHashes": ["0", "0"],
            },
            "worldGenericProxyMeshNode": {
                **_MESH_NODE_FIELDS,
                "nbNodesUnderProxy": 0,
                "nearAutoHideDistance": 0,
            },
            "worldMeshNode": _MESH_NODE_FIELDS,
            "worldStaticDecalNode": {
                **_NODE_FIELDS,
                "alpha": 1,
                "autoHideDistance": 20,
                "decalNodeVersion": 0,
                "decalRenderMode": "DRM_AllStatic",
                "diffuseColorScale": {
                    "$type": "HDRColor",
                    "Alpha": 1,
                    "Blue": 1,
                    "Green": 1,
                    "Red": 1,
                },
                "enableNormalTreshold": 1,
                "forcedAutoHideDistance": 0,
                "horizontalFlip": 0,
                "isStretchingEnabled": 0,
                "material": _NO_RESOURCE,
                "normalsBlendingMode": "AlphaBlending",
                "normalThreshold": 1,
                "orderNo": 0,
                "roughnessScale": 1,
                "shouldCollectWithRayTracing": 1,
                "surfaceType": "ROT_Static",
                "verticalFlip": 0,
            },
            "worldStaticMeshNode": _MESH_NODE_FIELDS,
        }.items()
    }
)

# The cooked node classes of the RTTI dump, each with the plain class that holds one placement of it.
COOKED_PLAIN_TYPES: Mapping[str, str] = MappingProxyType(
    {
        name: name.replace("Cooked", "", 1)
        for name in (
            "worldCookedAcousticSectorNode",
            "worldCookedAreaProxyMeshNode",
            "worldCookedBendedMeshNode",
            "worldCookedBuildingProxyMeshNode",
            "worldCookedCableMeshNode",
            "worldCookedCollisionNode",
            "worldCookedDecorationProxyMeshNode",
            "worldCookedDestructibleEntityProxyMeshNode",
            "worldCookedDestructibleProxyMeshNode",
            "worldCookedEntityProxyMeshNode",
            "worldCookedFoliageDestructionNode",
            "worldCookedGenericProxyMeshNode",
            "worldCookedInvalidProxyMeshNode",
            "worldCookedMeshNode",
            "worldCookedNode",
            "worldCookedPrefabProxyMeshNode",
            "worldCookedQuestProxyMeshNode",
            "worldCookedRoadProxyMeshNode",
            "worldCookedStaticDecalNode",
            "worldCookedStaticMeshNode",
            "worldCookedTerrainProxyMeshNode",
            "worldCookedWaterPatchProxyMeshNode",
        )
    }
)


class SectorLayoutError(ValueError):
    """A streaming sector that is not in the patch 2.5 layout"""


@dataclass(frozen=True, slots=True)
class NodeInstance:
    """One node data entry of a sector"""

    index: int
    node_index: int
    instance_index: int
    position: tuple[float, float, float]
    orientation: tuple[float, float, float, float]
    scale: tuple[float, float, float]
    streaming_distance: float
    raw: Mapping[str, Any] = field(compare=False, repr=False)


def require_current_layout(root_chunk: dict, source_path: str) -> None:
    """Raise SectorLayoutError naming source_path unless root_chunk is in the patch 2.5 layout"""
    version = root_chunk.get("version")
    if coerce_int(version, -1) != SECTOR_LAYOUT_VERSION:
        found = "no layout version" if version is None else f"layout version {version}"
        raise SectorLayoutError(
            f"{source_path}: this sector has {found}, but only the patch 2.5 layout (version "
            f"{SECTOR_LAYOUT_VERSION}) is supported. Export it again from the current game."
        )


def node_instances(root_chunk: dict) -> tuple[NodeInstance, ...]:
    """The node data entries of a sector's root chunk, in node data order"""
    entries = nested_dict(root_chunk, "nodeData").get("Data")
    found = []
    for index, entry in enumerate(entries if isinstance(entries, list) else ()):
        node_index = (
            coerce_int(entry.get("nodeIdx"), -1) if isinstance(entry, dict) else -1
        )
        if node_index < 0:
            continue
        transform = nested_dict(entry, "transform")
        found.append(
            NodeInstance(
                index=index,
                node_index=node_index,
                instance_index=coerce_int(entry.get("instanceIndex"), 0),
                position=vector3_from_data(transform.get("position")),
                orientation=quaternion_ijkr_from_wxyz(
                    quaternion_wxyz_from_wkit(transform.get("orientation"))
                ),
                scale=vector3_from_data(entry.get("scale"), (1.0, 1.0, 1.0)),
                streaming_distance=coerce_float(entry.get("streamingDistance"), 0.0),
                raw=entry,
            )
        )
    return tuple(found)


def resource_depot_paths(*values) -> tuple[str, ...]:
    """The depot paths of the resources values reference, as local path fragments"""
    result = []
    seen = set()
    stack = list(reversed(values))
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            depot = item.get("DepotPath")
            if isinstance(depot, dict):
                raw = depot.get("$value")
                if raw not in (None, "", 0, "0"):
                    path = depot_to_local_fragment(raw)
                    key = depot_path_key(path)
                    if key and key not in seen:
                        seen.add(key)
                        result.append(path)
            stack.extend(reversed(tuple(item.values())))
        elif isinstance(item, (list, tuple)):
            stack.extend(reversed(item))
    return tuple(result)


def inner_nodes(node_data: dict) -> tuple[dict, ...]:
    """The inner nodes of a cooked or instanced node"""
    buffer = nested_dict(node_data, "buffer", "Data")
    infos = buffer.get("CollisionNodeInfos")
    if isinstance(infos, list):
        compiled = nested_dict(node_data, "compiledData", "Data").get("CollisionNodes")
        return tuple(
            {
                **(info if isinstance(info, dict) else {}),
                **(node if isinstance(node, dict) else {}),
            }
            for info, node in zip(infos, compiled if isinstance(compiled, list) else ())
        )
    inner = buffer.get("InnerNodes")
    return tuple(inner) if isinstance(inner, list) else ()


def _shape_run(inner: Mapping, actor: Mapping) -> range:
    """The places in shapes of the shapes of an actor of a cooked collision inner node"""
    shapes = inner.get("shapes")
    start = max(coerce_int(actor.get("shapeStartIndex"), 0), 0)
    end = start + max(coerce_int(actor.get("shapeCount"), 0), 0)
    return range(start, min(end, len(shapes)) if isinstance(shapes, list) else start)


def collision_actor_shapes(inner: Mapping, actor: Mapping) -> tuple:
    """The shapes of an actor of a cooked collision inner node"""
    return tuple(inner["shapes"][index] for index in _shape_run(inner, actor))


def collision_actor_scale(
    inner: Mapping, actor: Mapping
) -> tuple[float, float, float] | None:
    """The scale of an actor of a cooked collision inner node, or None when it is unscaled"""
    scales = inner.get("scales")
    index = coerce_int(actor.get("scaleIndex"), -1)
    if not isinstance(scales, list) or not 0 <= index < len(scales):
        return None
    return vector3_from_data(scales[index], (1.0, 1.0, 1.0))


def collision_shape_rotation(
    inner: Mapping, shape: Mapping
) -> tuple[float, float, float, float] | None:
    """The rotation of a shape of a cooked collision inner node in its actor, or None when it is unturned"""
    rotations = inner.get("shapeRotations")
    index = coerce_int(shape.get("shapeRotationIndex"), -1)
    if not isinstance(rotations, list) or not 0 <= index < len(rotations):
        return None
    return quaternion_wxyz_from_wkit(rotations[index])


def _replaced(mapping: Mapping, values: Mapping) -> dict:
    """A copy of mapping with values in place of its own"""
    result = {
        key: values[key] if key in values else copy.deepcopy(value)
        for key, value in mapping.items()
    }
    result.update((key, value) for key, value in values.items() if key not in mapping)
    return result


def _renumbering(values: Sequence, what: str):
    """(place, kept) for renumbering the items of values"""
    kept, places = [], {}

    def place(index):
        index = coerce_int(index, -1)
        if index < 0:
            return -1
        if index >= len(values):
            raise ValueError(
                f"its collision data names {what} {index} of {len(values)}"
            )
        if index not in places:
            places[index] = len(kept)
            kept.append(copy.deepcopy(values[index]))
        return places[index]

    return place, kept


def one_actor_collision_node(
    node_data: Mapping,
    inner_index: int,
    actor_index: int,
    *,
    position: Sequence[float],
    orientation: Sequence[float],
    scale: Sequence[float] | None,
    extents: Sequence[float],
) -> dict:
    """A copy of a cooked collision node holding only one actor of one inner node, at a new placement"""
    info = nested_dict(node_data, "buffer", "Data")["CollisionNodeInfos"][inner_index]
    compiled = nested_dict(node_data, "compiledData", "Data")["CollisionNodes"][
        inner_index
    ]
    actor = compiled["actors"][actor_index]
    run = _shape_run(compiled, actor)
    # Every game sector's shapeIndices number its shapes 0, 1, 2 and so on, which the trimmed node goes on doing.
    if [
        coerce_int(value, -1)
        for value in (compiled.get("shapeIndices") or [])[run.start : run.stop]
    ] != list(run):
        raise ValueError(
            f"its collision data numbers the shapes of actor {actor_index} in a way the export cannot "
            "trim"
        )
    position_of, shape_positions = _renumbering(
        compiled.get("shapePositions") or [], "shape position"
    )
    rotation_of, shape_rotations = _renumbering(
        compiled.get("shapeRotations") or [], "shape rotation"
    )
    preset_of, presets = _renumbering(compiled.get("presets") or [], "preset")
    material_of, materials = _renumbering(compiled.get("materials") or [], "material")
    source_indices = compiled.get("materialIndices") or []
    material_indices, shapes = [], []
    for index in run:
        shape = compiled["shapes"][index]
        first, count = (
            coerce_int(shape.get("index"), 0),
            coerce_int(shape.get("materialCount"), 0),
        )
        if first < 0 or count < 0 or first + count > len(source_indices):
            raise ValueError(
                f"its collision data names material indices {first} to {first + count} of "
                f"{len(source_indices)}"
            )
        start = len(material_indices)
        material_indices.extend(
            material_of(value) for value in source_indices[first : first + count]
        )
        shapes.append(
            _replaced(
                shape,
                {
                    "index": start,
                    "shapePositionIndex": position_of(shape.get("shapePositionIndex")),
                    "shapePresetIndex": preset_of(shape.get("shapePresetIndex")),
                    "shapeRotationIndex": rotation_of(shape.get("shapeRotationIndex")),
                },
            )
        )
    scales = []
    if scale is not None:
        x, y, z = (float(value) for value in scale)
        scales.append(vector3_entry(x, y, z))
    kept = _replaced(
        actor,
        {
            "scaleIndex": 0 if scales else -1,
            "shapeCount": len(shapes),
            "shapeStartIndex": 0,
            "transform": world_transform_entry(position, orientation),
        },
    )
    inner = _replaced(
        compiled,
        {
            "actors": [kept],
            "materialIndices": material_indices,
            "materials": materials,
            "presets": presets,
            "scales": scales,
            "shapeIndices": list(range(len(shapes))),
            "shapePositions": shape_positions,
            "shapeRotations": shape_rotations,
            "shapes": shapes,
        },
    )
    info = _replaced(
        info,
        {
            "dataOffset": 0,
            "extents": _replaced(
                nested_dict(info, "extents"), {"Elements": [*map(float, extents), 0.0]}
            ),
            "numActors": 1,
            "numMaterialIndices": len(material_indices),
            "numMaterials": len(materials),
            "numPresets": len(presets),
            "numScales": len(scales),
            "numShapeIndices": len(shapes),
            "numShapeInfos": len(shapes),
            "numShapePositions": len(shape_positions),
            "numShapeRotations": len(shape_rotations),
        },
    )
    return _replaced(
        node_data,
        {
            "buffer": _replaced(
                node_data["buffer"],
                {
                    "Data": _replaced(
                        node_data["buffer"]["Data"], {"CollisionNodeInfos": [info]}
                    )
                },
            ),
            "compiledData": _replaced(
                node_data["compiledData"],
                {
                    "Data": _replaced(
                        node_data["compiledData"]["Data"], {"CollisionNodes": [inner]}
                    )
                },
            ),
        },
    )


def transform_range(node_data: dict, instance_index: int) -> range | None:
    """The transform indices one TransformRanges entry of a worldInstancedMeshNode covers"""
    ranges = nested_dict(node_data, "buffer", "Data").get("TransformRanges")
    if not isinstance(ranges, list) or not 0 <= instance_index < len(ranges):
        return None
    entry = ranges[instance_index]
    transforms = nested_dict(node_data, "cookedWorldTransformsBuffer", "Data").get(
        "Transforms"
    )
    if not isinstance(entry, dict) or not isinstance(transforms, list):
        return None
    start = coerce_int(entry.get("transformIndex"), -1)
    count = coerce_int(entry.get("transformCount"), -1)
    if start < 0 or count < 0 or start + count > len(transforms):
        return None
    return range(start, start + count)


def destructible_transforms(node_data: dict) -> tuple[dict | None, ...]:
    """The instanceTransforms of a worldInstancedDestructibleMeshNode"""
    items = node_data.get("instanceTransforms") if isinstance(node_data, dict) else None
    return (
        tuple(item if isinstance(item, dict) else None for item in items)
        if isinstance(items, list)
        else ()
    )


@functools.cache
def _template_entry() -> dict:
    return load_json_payload(os.path.join(get_resources_dir(), "base.nodeData.json"))


def node_instance_entry(
    node_index: int,
    matrix_values: tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]],
    *,
    streaming_distance: float,
    source: Mapping | None = None,
    inner_index: int | None = None,
) -> dict:
    """A new node data entry placing node node_index at matrix_values"""
    position, orientation, scale = (
        tuple(float(value) for value in values) for values in matrix_values
    )
    entry = copy.deepcopy(dict(source) if source is not None else _template_entry())
    entry["nodeIdx"] = str(int(node_index))
    entry["instanceIndex"] = (
        _PLAIN_NODE_INSTANCE_INDEX if inner_index is None else int(inner_index)
    )
    transform = entry.setdefault("transform", {"$type": "Transform"})
    transform["position"] = vector4_entry(
        *position, nested_dict(transform, "position").get("W", 0.0)
    )
    transform["orientation"] = encode_wkit_quaternion(orientation)
    entry["scale"] = vector3_entry(*scale)
    entry["streamingDistance"] = float(streaming_distance)
    for key in ("streamingRefPoint", "preboostStreamingRefPoint"):
        entry[key] = vector3_entry(*position)
    return entry


def copied_entry_source(entry: Mapping, *, global_node_id: int) -> dict:
    """The node data entry a copy of the node entry places starts from"""
    source = copy.deepcopy(_template_entry())
    source.update(
        {key: copy.deepcopy(entry[key]) for key in _COPIED_ENTRY_FIELDS if key in entry}
    )
    source["globalNodeId"] = {
        "$type": "worldGlobalNodeID",
        "hash": str(int(global_node_id)),
    }
    return source


def entry_global_node_id(entry: Mapping) -> int:
    """The global node id of a node data entry, or 0 for none"""
    return coerce_int(nested_dict(entry, "globalNodeId").get("hash"), 0)


def copied_global_node_id(entry: Mapping, sector_path: str, occurrence: int) -> int:
    """The global node id of the occurrence-th copy of the node entry places"""
    original = entry_global_node_id(entry)
    if not original:
        return 0
    return fnv1a64(f"{sector_path}|{original}|{occurrence}") or 1


def plain_node_data(node_type: str, data: Mapping) -> dict:
    """The Data of a plain node_type node"""
    return {
        "$type": node_type,
        **{
            key: copy.deepcopy(data.get(key, default))
            for key, default in PLAIN_NODE_FIELDS[node_type].items()
        },
    }


@functools.cache
def _template_sector() -> dict:
    return load_json_payload(
        os.path.join(get_resources_dir(), "empty.streamingsector.json")
    )


def _number_buffers(value: Any, numbers) -> None:
    if isinstance(value, dict):
        if "BufferId" in value:
            value["BufferId"] = str(next(numbers))
        for item in value.values():
            _number_buffers(item, numbers)
    elif isinstance(value, list):
        for item in value:
            _number_buffers(item, numbers)


def streaming_sector_document(
    nodes: Sequence[Mapping],
    entries: Sequence[Mapping],
    *,
    category: str,
    archive_file_name: str,
    extern_inplace_resource: Mapping | None = None,
) -> dict:
    """A patch 2.5 sector document holding nodes and their node data entries"""
    document = copy.deepcopy(_template_sector())
    document["Header"] = patch_2_5_header(archive_file_name)
    root = document["Data"]["RootChunk"]
    root["category"] = category
    if extern_inplace_resource is not None:
        root["externInplaceResource"] = copy.deepcopy(dict(extern_inplace_resource))
    handles = HandleIndex()
    root["nodes"] = [handles.rehandle(node) for node in nodes]
    root["nodeData"]["Data"] = [copy.deepcopy(dict(entry)) for entry in entries]
    root["persistentNodes"] = copy.deepcopy(root["nodeData"]["Data"])
    _number_buffers(root, itertools.count())
    return document
