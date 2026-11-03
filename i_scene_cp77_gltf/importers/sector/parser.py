from __future__ import annotations

from collections import defaultdict
import os
from .model import ParsedSector, SectorNode, SectorResourceRef
from .options import classify_node_type
from ..common.paths import depot_path, normalize_depot_path
from ...assetio.values import cname_text as cname_value


def resource_depot_paths(*values):
    paths = []

    def visit(item):
        if isinstance(item, dict):
            depot = item.get("DepotPath")
            if isinstance(depot, dict):
                raw = depot.get("$value")
                if raw not in (None, "", 0, "0"):
                    paths.append(normalize_depot_path(raw))
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    for value in values:
        visit(value)
    result = []
    seen = set()
    for path in paths:
        key = path.replace("\\", "/").lower()
        if key and key not in seen:
            seen.add(key)
            result.append(path)
    return tuple(result)


def is_streaming_sector_resource(path):
    normalized = normalize_depot_path(path).lower()
    return normalized.endswith((
        ".streamingsector",
        ".streamingsector_inplace",
        ".streamingsector.json",
        ".streamingsector_inplace.json",
    ))


def shared_transform_buffer_lookups(nodes):
    world_lookup = {}
    cooked_lookup = {}
    targets = (
        ("worldTransformsBuffer", world_lookup),
        ("cookedInstanceTransforms", cooked_lookup),
    )
    for node in nodes:
        if not isinstance(node, dict):
            continue
        data = node.get("Data")
        if not isinstance(data, dict):
            continue
        for buffer_key, lookup in targets:
            buffer_owner = data.get(buffer_key)
            if not isinstance(buffer_owner, dict):
                continue
            shared = buffer_owner.get("sharedDataBuffer")
            if not isinstance(shared, dict):
                continue
            handle_id = shared.get("HandleId")
            if handle_id is None:
                continue
            transforms = (
                shared.get("Data", {})
                .get("buffer", {})
                .get("Data", {})
                .get("Transforms")
            )
            if transforms is not None:
                lookup[str(handle_id)] = tuple(transforms)
    return world_lookup, cooked_lookup


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
            refs.append(SectorResourceRef(
                depot_path=path,
                normalized_path=path.replace("\\", "/").lower(),
                resource_kind=kind,
            ))
    return tuple(refs)


def parse_sector_document(
    payload,
    *,
    source_path="",
    parent_sector="",
    parent_sector_path="",
    composition_depth=0,
    source_kind="root",
    source_depot_path="",
):
    if not isinstance(payload, dict):
        raise TypeError("Streaming-sector payload must be a dictionary")

    root = payload.get("Data", {}).get("RootChunk", {})
    raw_node_data = root.get("nodeData", {}).get("Data", [])
    raw_nodes = root.get("nodes", [])
    if not isinstance(raw_node_data, list):
        raw_node_data = []
    if not isinstance(raw_nodes, list):
        raw_nodes = []

    indexed_node_data = []
    instances_by_node = defaultdict(list)
    for node_data_index, item in enumerate(raw_node_data):
        if not isinstance(item, dict):
            continue
        indexed = dict(item)
        indexed["nodeDataIndex"] = node_data_index
        indexed_node_data.append(indexed)
        instances_by_node[indexed.get("NodeIndex")].append(indexed)

    raw_instances_by_node = {
        key: tuple(value)
        for key, value in instances_by_node.items()
    }
    world_transform_buffers, cooked_transform_buffers = (
        shared_transform_buffer_lookups(raw_nodes)
    )
    parsed_nodes = []
    for node_index, entry in enumerate(raw_nodes):
        entry = entry if isinstance(entry, dict) else {}
        data = entry.get("Data")
        data = data if isinstance(data, dict) else {}
        node_type = str(data.get("$type", ""))
        mesh_path = depot_path(data, "mesh", "meshRef")
        entity_template_path = depot_path(data, "entityTemplate")
        foliage_resource_path = depot_path(data, "foliageResource")
        raw_handle_id = entry.get("HandleId")
        handle_id = str(raw_handle_id or "")
        parsed_nodes.append(SectorNode(
            index=node_index,
            handle_id=handle_id,
            node_type=node_type,
            data=data,
            raw_entry=entry,
            raw_instances=raw_instances_by_node.get(node_index, ()),
            category=classify_node_type(node_type),
            mesh_path=mesh_path,
            mesh_appearance=cname_value(data.get("meshAppearance"), "default"),
            entity_template_path=entity_template_path,
            entity_appearance=cname_value(data.get("appearanceName"), "default"),
            foliage_resource_path=foliage_resource_path,
            resource_refs=_resource_refs(
                data,
                mesh_path=mesh_path,
                entity_template_path=entity_template_path,
                foliage_resource_path=foliage_resource_path,
            ),
        ))

    referenced_paths = resource_depot_paths(
        root.get("externInplaceResource"),
        root.get("localInplaceResource"),
    )
    inplace_paths = tuple(
        path for path in referenced_paths
        if is_streaming_sector_resource(path)
    )

    sector_name = os.path.basename(source_path)
    if sector_name.lower().endswith(".json"):
        sector_name = sector_name[:-5]

    return ParsedSector(
        source_path=source_path,
        sector_name=sector_name,
        indexed_node_data=tuple(indexed_node_data),
        nodes=tuple(parsed_nodes),
        world_transform_buffers=world_transform_buffers,
        cooked_transform_buffers=cooked_transform_buffers,
        category=root.get("category", ""),
        level=int(root.get("level", 0) or 0),
        variant_indices=tuple(
            int(value) for value in root.get("variantIndices", ())
        ),
        variant_nodes=tuple(root.get("variantNodes", ())),
        inplace_depot_paths=inplace_paths,
        parent_sector=parent_sector,
        parent_sector_path=parent_sector_path,
        composition_parents=(parent_sector,) if parent_sector else (),
        composition_parent_paths=(parent_sector_path,) if parent_sector_path else (),
        composition_depth=int(composition_depth),
        source_kind=source_kind,
        source_depot_path=source_depot_path,
    )
