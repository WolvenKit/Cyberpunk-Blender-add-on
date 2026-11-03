from __future__ import annotations

import base64
import hashlib
import math

import bpy

from ....assetio.transform_values import vector3_from_data
from ....assetio.values import cname_text
from ....blender.naming import fit_id_name
from ....blender.transactions import track_created_datablock
from .fog import create_fog_volume_object

OUTLINE_COLORS = {
    "worldTriggerAreaNode": (1.0, 0.35, 0.05, 1.0),
    "gameKillTriggerNode": (1.0, 0.0, 0.0, 1.0),
    "worldAmbientAreaNode": (0.15, 0.55, 1.0, 1.0),
    "worldLightChannelVolumeNode": (0.75, 0.2, 1.0, 1.0),
    "gameWorldBoundaryNode": (1.0, 0.0, 0.4, 1.0),
    "worldGISpaceNode": (0.2, 1.0, 0.65, 1.0),
    "worldInteriorAreaNode": (0.2, 0.65, 1.0, 1.0),
}


class WorldMetadataService:
    @staticmethod
    def _outline_data(data):
        outline = data.get("outline", {}) if isinstance(data, dict) else {}
        outline_data = outline.get("Data", {}) if isinstance(outline, dict) else {}
        points = (
            outline_data.get("points", []) if isinstance(outline_data, dict) else []
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
                (x, y, z + z_value)
                for x, y, z in (vector3_from_data(point) for point in points)
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

        name = fit_id_name(f"{context.node_type}_{context.node_index}_{instance_index}")
        mesh = track_created_datablock("meshes", bpy.data.meshes.new(name))
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        obj = track_created_datablock("objects", bpy.data.objects.new(name, mesh))
        context.collection_for_instance(instance).objects.link(obj)
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
            context.node,
            context.sector_name,
            cp77_node_data_index=instance.index,
            cp77_instance_idx=instance_index,
        )
        if "notifiers" in data:
            obj["notifiers"] = context.session.safe_json(data.get("notifiers", []))
        return obj

    @staticmethod
    def interior_map_raster(data):
        buffer_data = data.get("buffer", {}) if isinstance(data, dict) else {}
        encoded = buffer_data.get("Bytes", "") if isinstance(buffer_data, dict) else ""
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
        """Load the interior map node's buffer as a packed greyscale image, once per buffer"""
        raw, width, height, digest = self.interior_map_raster(context.data)
        if not raw:
            context.operations.warning(
                f"{context.sector_name}: interior map node "
                f"{context.node_index} has no decodable buffer"
            )
            return
        if width * height != len(raw):
            context.operations.warning(
                f"{context.sector_name}: interior map node "
                f"{context.node_index} buffer length {len(raw)} "
                "is not rectangular"
            )

        image_name = fit_id_name(f"InteriorMap_{digest[:16]}")
        image = bpy.data.images.get(image_name)
        if image is None:
            image = track_created_datablock(
                "images",
                bpy.data.images.new(
                    image_name,
                    width=width,
                    height=height,
                    alpha=True,
                ),
            )
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

    def create_interior_map(self, context, instance, instance_index):
        data = context.data
        self._interior_map_image(context)
        name = fit_id_name(
            "InteriorMap_"
            f"{cname_text(data.get('debugName'), str(context.node_index))}_"
            f"{instance_index}"
        )
        obj = track_created_datablock("objects", bpy.data.objects.new(name, None))
        obj.empty_display_type = "CUBE"
        obj.empty_display_size = 1.0
        obj.display_type = "WIRE"
        obj.color = (0.1, 0.65, 1.0, 1.0)
        context.collection_for_instance(instance).objects.link(obj)
        obj.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )

        context.operations.assign_custom_properties(
            obj,
            context.node,
            context.sector_name,
            cp77_node_data_index=instance.index,
            cp77_instance_idx=instance_index,
        )
        return obj

    def create_light_channel_shape(
        self,
        context,
        instance,
        instance_index,
    ):
        data = context.data
        shape = data.get("shape", {}).get("Data", {})
        source_vertices = shape.get("vertices", []) if isinstance(shape, dict) else []
        indices = shape.get("indices", []) if isinstance(shape, dict) else []
        vertices = [
            vector3_from_data(vertex)
            for vertex in source_vertices
            if isinstance(vertex, dict)
        ]
        faces = []
        invalid_indices = 0
        for offset in range(0, len(indices) - 2, 3):
            try:
                face = tuple(int(indices[offset + step]) for step in range(3))
            except (TypeError, ValueError):
                invalid_indices += 1
                continue
            if any(index < 0 or index >= len(vertices) for index in face):
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

        name = fit_id_name(f"LightChannelShape_{context.node_index}_{instance_index}")
        mesh = track_created_datablock("meshes", bpy.data.meshes.new(name))
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        obj = track_created_datablock("objects", bpy.data.objects.new(name, mesh))
        context.collection_for_instance(instance).objects.link(obj)
        obj.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )
        obj.display_type = "WIRE"
        obj.color = (0.75, 0.2, 1.0, 1.0)
        obj.show_wire = True
        context.operations.assign_custom_properties(
            obj,
            context.node,
            context.sector_name,
            cp77_node_data_index=instance.index,
            cp77_instance_idx=instance_index,
            lightChannels=str(data.get("channels", "")),
            streamingDistanceFactor=float(
                data.get("streamingDistanceFactor", 0.0) or 0.0
            ),
        )
        obj["cp77_light_channel_volume"] = True
        obj.hide_render = True
        if invalid_indices:
            context.operations.warning(
                f"{context.sector_name}: light channel shape node "
                f"{context.node_index} skipped {invalid_indices} "
                "invalid indices"
            )
        return obj

    def create_fog_volume(self, context, instance, instance_index):
        data = context.data
        name = fit_id_name(f"{context.node_type}_{context.node_index}_{instance_index}")
        obj = create_fog_volume_object(
            name,
            data,
            context.collection_for_instance(instance),
            matrix=context.operations.instance_matrix(
                instance,
                context.execution.scale_factor,
            ),
            source_kind="sector",
        )
        context.operations.assign_custom_properties(
            obj,
            context.node,
            context.sector_name,
            cp77_node_data_index=instance.index,
            cp77_instance_idx=instance_index,
        )
        return obj

    def create_sound_emitter(
        self,
        context,
        instance,
        instance_index,
    ):
        data = context.data
        name = fit_id_name(
            f"{context.node_type}_"
            f"{cname_text(data.get('debugName'), str(context.node_index))}_"
            f"{instance_index}"
        )
        obj = track_created_datablock("objects", bpy.data.objects.new(name, None))
        obj.empty_display_type = "SPHERE"
        obj.empty_display_size = max(
            0.1,
            float(data.get("radius", 1.0) or 1.0),
        )
        context.collection_for_instance(instance).objects.link(obj)
        obj.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )
        context.operations.assign_custom_properties(
            obj,
            context.node,
            context.sector_name,
            cp77_node_data_index=instance.index,
            cp77_instance_idx=instance_index,
            radius=float(data.get("radius", 0.0) or 0.0),
            audioName=cname_text(data.get("audioName")),
            emitterMetadataName=cname_text(data.get("emitterMetadataName")),
            occlusionEnabled=bool(data.get("occlusionEnabled", 0)),
            usePhysicsObstruction=bool(data.get("usePhysicsObstruction", 0)),
            useDoppler=bool(data.get("useDoppler", 0)),
            dopplerFactor=float(data.get("dopplerFactor", 1.0) or 1.0),
        )
        return obj
