from __future__ import annotations
from ....blender.transactions import track_created_datablock

import base64
import copy
import hashlib
import math

import bpy

from .fog import create_fog_volume_object
from ....assetio.values import axis_value


OUTLINE_COLORS = {
    "worldTriggerAreaNode": (1.0, 0.35, 0.05, 1.0),
    "gameKillTriggerNode": (1.0, 0.0, 0.0, 1.0),
    "worldAmbientAreaNode": (0.15, 0.55, 1.0, 1.0),
    "worldLightChannelVolumeNode": (0.75, 0.2, 1.0, 1.0),
    "gameWorldBoundaryNode": (1.0, 0.0, 0.4, 1.0),
    "worldGISpaceNode": (0.2, 1.0, 0.65, 1.0),
    "worldInteriorAreaNode": (0.2, 0.65, 1.0, 1.0),
}

OUTLINE_NODE_TYPES = frozenset(OUTLINE_COLORS)

WORLD_METADATA_CONTRACTS = {
    "worldTriggerAreaNode": "TRIGGER_OUTLINE_VOLUME_NODE_WORLD",
    "gameKillTriggerNode": "KILL_TRIGGER_OUTLINE_VOLUME_NODE_WORLD",
    "worldAmbientAreaNode": "AMBIENT_OUTLINE_VOLUME_NODE_WORLD",
    "worldLightChannelVolumeNode": "LIGHT_CHANNEL_OUTLINE_VOLUME_NODE_WORLD",
    "gameWorldBoundaryNode": "WORLD_BOUNDARY_OUTLINE_VOLUME_NODE_WORLD",
    "worldGISpaceNode": "GI_SPACE_OUTLINE_VOLUME_NODE_WORLD",
    "worldInteriorAreaNode": "INTERIOR_OUTLINE_VOLUME_NODE_WORLD",
    "worldInteriorMapNode": "INTERIOR_MAP_RASTER_METADATA_NODE_WORLD",
    "worldLightChannelShapeNode": "LIGHT_CHANNEL_SHAPE_NODE_WORLD",
    "worldStaticFogVolumeNode": "STATIC_FOG_VOLUME_NODE_WORLD",
    "worldStaticSoundEmitterNode": "STATIC_SOUND_EMITTER_NODE_WORLD",
}


class WorldMetadataService:
    @staticmethod
    def audio_events(settings, cname_value):
        data = settings.get("Data", {}) if isinstance(settings, dict) else {}
        events = {}
        for key in ("EventsOnActive", "EventsOnEnter", "EventsOnExit"):
            values = []
            source = data.get(key, []) if isinstance(data, dict) else []
            for item in source:
                value = cname_value(
                    item.get("event") if isinstance(item, dict) else None
                )
                if value:
                    values.append(value)
            events[key] = values
        return events

    @staticmethod
    def _outline_data(data):
        outline = data.get("outline", {}) if isinstance(data, dict) else {}
        outline_data = (
            outline.get("Data", {})
            if isinstance(outline, dict)
            else {}
        )
        points = (
            outline_data.get("points", [])
            if isinstance(outline_data, dict)
            else []
        )
        height = (
            float(outline_data.get("height", 0.0) or 0.0)
            if isinstance(outline_data, dict)
            else 0.0
        )
        return points, height

    def create_outline_volume(self, context, instance, instance_index):
        data = context.data
        points, height = self._outline_data(data)
        if len(points) < 3:
            context.operations.warning(
                f"{context.sector_name}: {context.node_type} node "
                f"{context.node_index} has no usable outline"
            )
            return None

        half_height = height * 0.5
        vertices = []
        for z_value in (-half_height, half_height):
            vertices.extend(
                (
                    float(axis_value(point, "X")),
                    float(axis_value(point, "Y")),
                    float(axis_value(point, "Z")) + z_value,
                )
                for point in points
            )
        count = len(points)
        faces = [
            tuple(range(count - 1, -1, -1)),
            tuple(range(count, count * 2)),
        ]
        faces.extend(
            (
                index,
                (index + 1) % count,
                (index + 1) % count + count,
                index + count,
            )
            for index in range(count)
        )

        name = context.operations.trim_name(
            f"{context.node_type}_{context.node_index}_{instance_index}"
        )
        mesh = track_created_datablock("meshes", bpy.data.meshes.new(name))
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        obj = track_created_datablock("objects", bpy.data.objects.new(name, mesh))
        context.sector_collection.objects.link(obj)
        obj.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )
        obj.display_type = "WIRE"
        obj.color = OUTLINE_COLORS.get(
            context.node_type,
            (0.8, 0.8, 0.8, 1.0),
        )
        obj.show_wire = True
        context.operations.assign_custom_properties(
            obj,
            data,
            context.sector_name,
            context.node_index,
            nodeDataIndex=instance["nodeDataIndex"],
            instance_idx=instance_index,
            outlineHeight=height,
            outlinePointCount=count,
        )
        obj["outlineData"] = context.operations.safe_json(
            data.get("outline", {})
        )
        if "notifiers" in data:
            obj["notifiers"] = context.operations.safe_json(
                data.get("notifiers", [])
            )
        return obj

    @staticmethod
    def interior_map_raster(data):
        buffer_data = (
            data.get("buffer", {})
            if isinstance(data, dict)
            else {}
        )
        encoded = (
            buffer_data.get("Bytes", "")
            if isinstance(buffer_data, dict)
            else ""
        )
        if not encoded:
            return b"", 0, 0, ""
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError):
            return b"", 0, 0, ""
        side = math.isqrt(len(raw))
        width = side if side * side == len(raw) else len(raw)
        height = side if side * side == len(raw) else 1
        return raw, width, height, hashlib.sha1(raw).hexdigest()

    def _interior_map_image(self, context):
        raw, width, height, digest = self.interior_map_raster(
            context.data
        )
        if not raw:
            context.operations.warning(
                f"{context.sector_name}: interior map node "
                f"{context.node_index} has no decodable buffer"
            )
            return None, b"", 0, 0, ""
        if width * height != len(raw):
            context.operations.warning(
                f"{context.sector_name}: interior map node "
                f"{context.node_index} buffer length {len(raw)} "
                "is not rectangular"
            )

        image_name = context.operations.trim_name(
            f"InteriorMap_{digest[:16]}"
        )
        image = bpy.data.images.get(image_name)
        if image is None:
            image = track_created_datablock("images", bpy.data.images.new(
                image_name,
                width=width,
                height=height,
                alpha=True,
            ))
            pixels = [0.0] * (len(raw) * 4)
            for index, value in enumerate(raw):
                normalized = value / 255.0
                offset = index * 4
                pixels[offset] = normalized
                pixels[offset + 1] = normalized
                pixels[offset + 2] = normalized
                pixels[offset + 3] = 1.0
            image.pixels.foreach_set(pixels)
            image.update()
            try:
                image.colorspace_settings.name = "Non-Color"
            except (TypeError, ValueError):
                pass
            image.pack()
            image["interiorMapRaster"] = True
            image["sourceByteCount"] = len(raw)
            image["sourceWidth"] = width
            image["sourceHeight"] = height
            image["sourceSha1"] = digest
            image["sourceRowOrder"] = "ROW_MAJOR_UNFLIPPED"
        return image, raw, width, height, digest

    def create_interior_map(self, context, instance, instance_index):
        data = context.data
        image, raw, width, height, digest = self._interior_map_image(
            context
        )
        name = context.operations.trim_name(
            "InteriorMap_"
            f"{context.operations.cname_value(data.get('debugName'), str(context.node_index))}_"
            f"{instance_index}"
        )
        obj = track_created_datablock("objects", bpy.data.objects.new(name, None))
        obj.empty_display_type = "CUBE"
        obj.empty_display_size = 1.0
        obj.display_type = "WIRE"
        obj.color = (0.1, 0.65, 1.0, 1.0)
        context.sector_collection.objects.link(obj)
        obj.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )

        compact_data = copy.deepcopy(data)
        compact_buffer = compact_data.get("buffer")
        if isinstance(compact_buffer, dict) and "Bytes" in compact_buffer:
            compact_buffer["Bytes"] = (
                f"<{len(raw)} bytes sha1={digest}>"
                if raw
                else "<unavailable>"
            )

        context.operations.assign_custom_properties(
            obj,
            data,
            context.sector_name,
            context.node_index,
            nodeDataIndex=instance["nodeDataIndex"],
            instance_idx=instance_index,
            interiorMapCoords=str(data.get("coords", "")),
            interiorMapVersion=int(data.get("version", 0) or 0),
            interiorMapBufferId=str(
                data.get("buffer", {}).get("BufferId", "")
            ),
            interiorMapByteCount=len(raw),
            interiorMapWidth=width,
            interiorMapHeight=height,
            interiorMapSha1=digest,
            interiorMapImage=image.name if image is not None else "",
            interiorMapRepresentation="RASTER_IMAGE_METADATA_ONLY",
        )
        obj["interiorMapNodeData"] = context.operations.safe_json(
            compact_data
        )
        obj["nodeDataBounds"] = context.operations.safe_json(
            instance.get("Bounds", {})
        )
        obj["rasterNonZeroCount"] = sum(1 for value in raw if value)
        obj["rasterUniqueValueCount"] = len(set(raw))
        return obj

    def create_light_channel_shape(
        self,
        context,
        instance,
        instance_index,
    ):
        data = context.data
        shape = data.get("shape", {}).get("Data", {})
        source_vertices = (
            shape.get("vertices", [])
            if isinstance(shape, dict)
            else []
        )
        indices = (
            shape.get("indices", [])
            if isinstance(shape, dict)
            else []
        )
        vertices = [
            (
                float(axis_value(vertex, "X")),
                float(axis_value(vertex, "Y")),
                float(axis_value(vertex, "Z")),
            )
            for vertex in source_vertices
            if isinstance(vertex, dict)
        ]
        faces = []
        invalid_indices = 0
        for offset in range(0, len(indices) - 2, 3):
            try:
                face = tuple(
                    int(indices[offset + step])
                    for step in range(3)
                )
            except (TypeError, ValueError):
                invalid_indices += 1
                continue
            if any(
                index < 0 or index >= len(vertices)
                for index in face
            ):
                invalid_indices += 1
                continue
            faces.append(face)
        if len(indices) % 3:
            invalid_indices += len(indices) % 3
        if not vertices or not faces:
            context.operations.warning(
                f"{context.sector_name}: light channel shape node "
                f"{context.node_index} has no usable mesh"
            )
            return None

        name = context.operations.trim_name(
            f"LightChannelShape_{context.node_index}_{instance_index}"
        )
        mesh = track_created_datablock("meshes", bpy.data.meshes.new(name))
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        obj = track_created_datablock("objects", bpy.data.objects.new(name, mesh))
        context.sector_collection.objects.link(obj)
        obj.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )
        obj.display_type = "WIRE"
        obj.color = (0.75, 0.2, 1.0, 1.0)
        obj.show_wire = True
        context.operations.assign_custom_properties(
            obj,
            data,
            context.sector_name,
            context.node_index,
            nodeDataIndex=instance["nodeDataIndex"],
            instance_idx=instance_index,
            lightChannels=str(data.get("channels", "")),
            streamingDistanceFactor=float(
                data.get("streamingDistanceFactor", 0.0) or 0.0
            ),
            shapeVertexCount=len(vertices),
            shapeTriangleCount=len(faces),
            invalidShapeIndices=invalid_indices,
        )
        obj["shapeDataSha1"] = hashlib.sha1(
            context.operations.safe_json(shape).encode("utf-8")
        ).hexdigest()
        if invalid_indices:
            context.operations.warning(
                f"{context.sector_name}: light channel shape node "
                f"{context.node_index} skipped {invalid_indices} "
                "invalid indices"
            )
        return obj

    def create_fog_volume(self, context, instance, instance_index):
        data = context.data
        name = context.operations.trim_name(
            f"{context.node_type}_{context.node_index}_{instance_index}"
        )
        obj = create_fog_volume_object(
            name,
            data,
            context.sector_collection,
            matrix=context.operations.instance_matrix(
                instance,
                context.execution.scale_factor,
            ),
            source_kind="sector",
        )
        context.operations.assign_custom_properties(
            obj,
            data,
            context.sector_name,
            context.node_index,
            nodeDataIndex=instance["nodeDataIndex"],
            instance_idx=instance_index,
        )
        obj["fogVolumeRepresentation"] = (
            "CP77_UNIT_BOX_MINUS_ONE_TO_ONE_SCALED_BY_NODE_DATA"
        )
        obj["fogLightChannels"] = str(data.get("lightChannels", ""))
        obj["fogEnvironmentColorGroup"] = str(
            data.get("envColorGroup", "")
        )
        obj["fogApplyGlobalHeightFalloff"] = bool(
            data.get("applyHeightFalloff", 0)
        )
        obj["fogNodeData"] = context.operations.safe_json(data)
        return obj

    def create_sound_emitter(
        self,
        context,
        instance,
        instance_index,
    ):
        data = context.data
        name = context.operations.trim_name(
            f"{context.node_type}_"
            f"{context.operations.cname_value(data.get('debugName'), str(context.node_index))}_"
            f"{instance_index}"
        )
        obj = track_created_datablock("objects", bpy.data.objects.new(name, None))
        obj.empty_display_type = "SPHERE"
        obj.empty_display_size = max(
            0.1,
            float(data.get("radius", 1.0) or 1.0),
        )
        context.sector_collection.objects.link(obj)
        obj.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )
        context.operations.assign_custom_properties(
            obj,
            data,
            context.sector_name,
            context.node_index,
            nodeDataIndex=instance["nodeDataIndex"],
            instance_idx=instance_index,
            radius=float(data.get("radius", 0.0) or 0.0),
            audioName=context.operations.cname_value(
                data.get("audioName")
            ),
            emitterMetadataName=context.operations.cname_value(
                data.get("emitterMetadataName")
            ),
            occlusionEnabled=bool(data.get("occlusionEnabled", 0)),
            usePhysicsObstruction=bool(
                data.get("usePhysicsObstruction", 0)
            ),
            useDoppler=bool(data.get("useDoppler", 0)),
            dopplerFactor=float(
                data.get("dopplerFactor", 1.0) or 1.0
            ),
        )
        events = self.audio_events(
            data.get("Settings", {}),
            context.operations.cname_value,
        )
        obj["audioEvents"] = context.operations.safe_json(events)
        obj["audioSettings"] = context.operations.safe_json(
            data.get("Settings", {})
        )
        return obj
