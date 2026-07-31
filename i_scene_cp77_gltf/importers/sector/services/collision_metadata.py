from __future__ import annotations
from ....blender.transactions import track_created_datablock

import base64
import copy
from dataclasses import dataclass
import hashlib

import bpy

from ....assetio.values import vector3


COLLISION_METADATA_CONTRACTS = {
    "worldFoliageDestructionNode": (
        "COLLISION_METADATA_FOLIAGE_DESTRUCTION"
    ),
    "worldTerrainCollisionNode": (
        "COLLISION_METADATA_TERRAIN_HEIGHTFIELD"
    ),
}


@dataclass(slots=True, frozen=True)
class CollisionMetadataPlacement:
    object: object
    byte_count: int
    digest: str


class CollisionMetadataService:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def contract(node_type):
        try:
            return COLLISION_METADATA_CONTRACTS[node_type]
        except KeyError as error:
            raise ValueError(
                f"Unsupported collision metadata node type: {node_type}"
            ) from error

    @staticmethod
    def binary_digest(encoded):
        if not encoded:
            return b"", ""
        try:
            raw = base64.b64decode(
                encoded,
                validate=False,
            )
        except (ValueError, TypeError):
            return b"", ""
        return raw, hashlib.sha1(raw).hexdigest()

    def create(self, context, instance, instance_index):
        data = context.data
        node_type = context.node_type
        name = context.operations.trim_name(
            f"{node_type}_{context.node_index}_{instance_index}"
        )

        mesh = None
        if node_type == "worldFoliageDestructionNode":
            extents = vector3(data.get("extents"))
            mesh = self.session.primitive_meshes.centered_box(
                name,
                extents,
                shared=False,
            )

        obj = track_created_datablock("objects", bpy.data.objects.new(name, mesh))
        if mesh is None:
            obj.empty_display_type = "CUBE"
            obj.empty_display_size = 1.0
        context.sector_collection.objects.link(obj)
        obj.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )
        obj.display_type = "WIRE"
        obj.color = (0.85, 0.25, 0.05, 1.0)
        obj.show_wire = mesh is not None

        context.operations.assign_custom_properties(
            obj,
            data,
            context.sector_name,
            context.node_index,
            nodeDataIndex=instance["nodeDataIndex"],
            instance_idx=instance_index,
            collisionRepresentation=(
                "METADATA_ONLY_NO_PHYSX_ACTOR"
            ),
        )

        compact = copy.deepcopy(data)
        byte_count = 0
        digest = ""

        if node_type == "worldTerrainCollisionNode":
            geometry = compact.get(
                "heightfieldGeometry",
                {},
            )
            encoded = (
                geometry.get("Bytes", "")
                if isinstance(geometry, dict)
                else ""
            )
            raw, digest = self.binary_digest(encoded)
            byte_count = len(raw)
            if (
                isinstance(geometry, dict)
                and "Bytes" in geometry
            ):
                geometry["Bytes"] = (
                    f"<{byte_count} bytes sha1={digest}>"
                    if raw
                    else "<unavailable>"
                )
            obj["heightfieldByteCount"] = byte_count
            obj["heightfieldSha1"] = digest
            obj["rowScale"] = float(
                data.get("rowScale", 0.0) or 0.0
            )
            obj["columnScale"] = float(
                data.get("columnScale", 0.0) or 0.0
            )
            obj["heightScale"] = float(
                data.get("heightScale", 0.0) or 0.0
            )
            obj["terrainActorTransform"] = (
                context.operations.safe_json(
                    data.get("actorTransform", {})
                )
            )
        else:
            compiled = compact.get("compiledData", {})
            encoded_compiled = (
                context.operations.safe_json(
                    compiled
                ).encode("utf-8")
                if compiled
                else b""
            )
            digest = (
                hashlib.sha1(encoded_compiled).hexdigest()
                if encoded_compiled
                else ""
            )
            byte_count = len(encoded_compiled)
            compact["compiledData"] = (
                f"<json bytes={byte_count} sha1={digest}>"
                if encoded_compiled
                else "<unavailable>"
            )
            obj["compiledDataByteCount"] = byte_count
            obj["compiledDataSha1"] = digest
            obj["populationIndex"] = list(
                data.get("populationIndex", [])
            )

        obj["collisionNodeData"] = (
            context.operations.safe_json(compact)
        )
        return CollisionMetadataPlacement(
            object=obj,
            byte_count=byte_count,
            digest=digest,
        )
