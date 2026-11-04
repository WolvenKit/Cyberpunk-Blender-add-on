from __future__ import annotations

import os
from collections import defaultdict

from ...assetio.paths import depot_path_key, strip_json_suffix
from ...assetio.streaming_sector import (
    COOKED_PLAIN_TYPES,
    destructible_transforms,
    inner_nodes,
    node_instances,
    require_current_layout,
    resource_depot_paths,
    transform_range,
)
from ...assetio.values import cname_text, coerce_int, nested_dict
from ..common.paths import depot_path
from .model import ParsedSector, SectorNode, SectorResourceRef
from .options import classify_node_type

_DESTRUCTIBLE_NODE_TYPE = "worldInstancedDestructibleMeshNode"
_INSTANCED_MESH_NODE_TYPE = "worldInstancedMeshNode"
# The fields of a cooked or instanced node that hold its inner nodes and transforms rather than node settings.
_NODE_BUFFERS = frozenset({"buffer", "compiledData", "cookedWorldTransformsBuffer"})
# Inner-node fields WolvenKit names differently from the plain node's.
_RENAMED_FIELDS = {"forcedAutoHideDistance": "forceAutoHideDistance"}
# A cooked decal's flags, as WolvenKit names them, and the plain decal's switch for each.
_DECAL_FLAGS = {
    "VerticalFlip": "verticalFlip",
    "HorizontalFlip": "horizontalFlip",
    "IsStretchingEnabled": "isStretchingEnabled",
    "EnableNormalTreshold": "enableNormalTreshold",
    "ShouldCollectWithRayTracing": "shouldCollectWithRayTracing",
}


def _resource_refs(
    data,
    *,
    mesh_path="",
    entity_template_path="",
    foliage_resource_path="",
):
    refs = []
    for path, kind in (
        (mesh_path, "mesh"),
        (entity_template_path, "entity"),
        (foliage_resource_path, "foliage"),
        (depot_path(data, "resource"), "resource"),
    ):
        if path:
            refs.append(
                SectorResourceRef(
                    depot_path=path,
                    normalized_path=depot_path_key(path),
                    resource_kind=kind,
                )
            )
    return tuple(refs)


def _slice(values, start, count):
    if not isinstance(values, list) or start < 0 or count < 0:
        return []
    return list(values[start : start + count])


def _decal_fields(inner, buffer):
    fields = {
        key: value
        for key, value in inner.items()
        if key not in ("flags", "diffuseColorScaleIndex")
    }
    flags = {token.strip() for token in str(inner.get("flags", "") or "").split(",")}
    for flag, key in _DECAL_FLAGS.items():
        fields[key] = int(flag in flags)
    scales = buffer.get("DiffuseColorScales")
    index = coerce_int(inner.get("diffuseColorScaleIndex"), -1)
    if isinstance(scales, list) and 0 <= index < len(scales):
        fields["diffuseColorScale"] = scales[index]
    return fields


def _inner_fields(plain_type, inner, buffer):
    """The fields of the plain plain_type node that inner stands for"""
    if plain_type == "worldStaticDecalNode":
        return _decal_fields(inner, buffer)
    fields = {_RENAMED_FIELDS.get(key, key): value for key, value in inner.items()}
    if plain_type in ("worldBendedMeshNode", "worldCableMeshNode"):
        start = coerce_int(fields.pop("deformationDataStartIndex", 0), 0)
        count = coerce_int(fields.pop("deformationDataCount", 0), 0)
        fields["deformationData"] = _slice(buffer.get("DeformationData"), start, count)
        boxes = buffer.get("DeformedBoxes")
        box = coerce_int(fields.pop("index", -1), -1)
        if isinstance(boxes, list) and 0 <= box < len(boxes):
            fields["deformedBox"] = boxes[box]
    elif plain_type == "worldAcousticSectorNode":
        if "GeneratorId" in buffer:
            fields["generatorId"] = buffer["GeneratorId"]
    elif plain_type in ("worldCollisionNode", "worldFoliageDestructionNode"):
        fields.pop("dataOffset", None)
        elements = nested_dict(fields, "extents").get("Elements")
        if isinstance(elements, list) and len(elements) == 4:
            fields["extents"] = {
                "$type": "Vector4",
                **dict(zip(("X", "Y", "Z", "W"), elements)),
            }
        if plain_type == "worldFoliageDestructionNode":
            start = coerce_int(fields.get("populationIndex"), 0)
            count = coerce_int(fields.pop("populationCount", 0), 0)
            fields["populationIndex"] = _slice(
                buffer.get("PopulationIndex"), start, count
            )
            if "DataVersion" in buffer:
                fields["dataVersion"] = buffer["DataVersion"]
    return fields


def _inner_node_data(node_data, node_type, inner):
    """The node data of one inner node of the cooked or instanced node_data"""
    data = {key: value for key, value in node_data.items() if key not in _NODE_BUFFERS}
    data.update(
        _inner_fields(node_type, inner, nested_dict(node_data, "buffer", "Data"))
    )
    data["$type"] = node_type
    return data


def _sector_node(
    index, entry, node_type, source_node_type, inner_index, data, instances
):
    mesh_path = depot_path(data, "mesh", "meshRef")
    entity_template_path = depot_path(data, "entityTemplate")
    foliage_resource_path = depot_path(data, "foliageResource")
    return SectorNode(
        index=index,
        handle_id=str(entry.get("HandleId") or ""),
        node_type=node_type,
        source_node_type=source_node_type,
        inner_index=inner_index,
        data=data,
        raw_entry=entry,
        instances=tuple(instances),
        category=classify_node_type(node_type),
        mesh_path=mesh_path,
        mesh_appearance=cname_text(data.get("meshAppearance"), "default"),
        entity_template_path=entity_template_path,
        entity_appearance=cname_text(data.get("appearanceName"), "default"),
        foliage_resource_path=foliage_resource_path,
        resource_refs=_resource_refs(
            data,
            mesh_path=mesh_path,
            entity_template_path=entity_template_path,
            foliage_resource_path=foliage_resource_path,
        ),
    )


def _inner_sector_nodes(index, entry, data, instances):
    """One node per inner node the entries pick of the cooked or instanced node data"""
    source_type = str(data.get("$type", ""))
    node_type = COOKED_PLAIN_TYPES.get(source_type, source_type)
    inner = inner_nodes(data)
    by_inner = defaultdict(list)
    for instance in instances:
        picked = instance.instance_index
        if 0 <= picked < len(inner) and (
            source_type != _INSTANCED_MESH_NODE_TYPE
            or transform_range(data, picked) is not None
        ):
            by_inner[picked].append(instance)
    return tuple(
        _sector_node(
            index,
            entry,
            node_type,
            source_type,
            picked,
            _inner_node_data(data, node_type, inner[picked]),
            by_inner[picked],
        )
        for picked in sorted(by_inner)
    )


def parse_sector_document(
    payload,
    *,
    source_path="",
    parent_sector="",
    parent_sector_path="",
):
    if not isinstance(payload, dict):
        raise TypeError("Streaming-sector payload must be a dictionary")

    root = nested_dict(payload, "Data", "RootChunk")
    require_current_layout(root, source_path)
    raw_node_data = nested_dict(root, "nodeData").get("Data")
    node_data_count = len(raw_node_data) if isinstance(raw_node_data, list) else 0
    raw_nodes = root.get("nodes", [])
    if not isinstance(raw_nodes, list):
        raw_nodes = []

    instances = node_instances(root)
    instances_by_node = defaultdict(list)
    for instance in instances:
        instances_by_node[instance.node_index].append(instance)

    parsed_nodes = []
    placed = set()
    for node_index, entry in enumerate(raw_nodes):
        entry = entry if isinstance(entry, dict) else {}
        data = entry.get("Data")
        data = data if isinstance(data, dict) else {}
        node_type = str(data.get("$type", ""))
        entries = instances_by_node.get(node_index, ())
        if node_type in COOKED_PLAIN_TYPES or node_type == _INSTANCED_MESH_NODE_TYPE:
            nodes = _inner_sector_nodes(node_index, entry, data, entries)
        else:
            nodes = (
                _sector_node(
                    node_index, entry, node_type, node_type, -1, data, entries
                ),
            )
        parsed_nodes.extend(nodes)
        placed.update(instance.index for node in nodes for instance in node.instances)

    sector_name = strip_json_suffix(os.path.basename(source_path))

    return ParsedSector(
        source_path=source_path,
        sector_name=sector_name,
        node_data_count=node_data_count,
        instances=instances,
        nodes=tuple(parsed_nodes),
        skipped_node_data=tuple(
            index for index in range(node_data_count) if index not in placed
        ),
        skipped_instances=tuple(
            (node.index, item)
            for node in parsed_nodes
            if node.source_node_type == _DESTRUCTIBLE_NODE_TYPE and node.instances
            for item, transform in enumerate(destructible_transforms(node.data))
            if transform is None
        ),
        category=root.get("category", ""),
        variant_indices=tuple(int(value) for value in root.get("variantIndices", ())),
        variant_nodes=tuple(root.get("variantNodes", ())),
        extern_inplace_resource=root.get("externInplaceResource"),
        local_inplace_paths=resource_depot_paths(root.get("localInplaceResource")),
        parent_sector=parent_sector,
        parent_sector_path=parent_sector_path,
        composition_parent_paths=(parent_sector_path,) if parent_sector_path else (),
    )
