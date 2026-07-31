from __future__ import annotations
from ....blender.transactions import track_created_datablock

from dataclasses import dataclass
import hashlib
import math
import os

import bpy
import numpy as np
from mathutils import Matrix

from ....materials.blender.builder import MaterialBuilder
from ...common.paths import path_key


DECAL_PLACEMENT_CONTRACT = "DECAL_PROJECTOR_LOCAL_Z_UNIT_PLANE"


@dataclass(slots=True, frozen=True)
class DecalMaterialResult:
    material: object | None
    material_path: str
    resolved_path: str
    expected_path: str
    signature: tuple
    status: str
    error: str = ""


@dataclass(slots=True, frozen=True)
class _DecalResourceDescriptor:
    document: dict | None
    data_block: dict | None
    root_chunk: dict | None
    source_identity: tuple
    base_material_path: str
    status: str
    error: str = ""


@dataclass(slots=True, frozen=True)
class DecalPlacement:
    projector: object
    plane: object
    material_result: DecalMaterialResult



class DecalService:
    def __init__(self, session):
        self.session = session
        self.cache = session.caches.materials
        self.mesh_cache = session.caches.decal_meshes
        self.descriptor_cache = {}
        self._owned_material_ids = set()
        self.stats = {
            "descriptor_hits": 0,
            "descriptor_misses": 0,
            "documents_loaded": 0,
            "invalid_documents": 0,
            "variant_documents": 0,
            "materials_claimed": 0,
            "materials_cloned": 0,
        }

    @staticmethod
    def color_scale(data):
        color = (
            data.get("diffuseColorScale", {})
            if isinstance(data, dict)
            else {}
        )
        return (
            float(color.get("Red", 1.0)),
            float(color.get("Green", 1.0)),
            float(color.get("Blue", 1.0)),
            float(color.get("Alpha", 1.0)),
        )

    @classmethod
    def color(cls, data):
        color = cls.color_scale(data)
        return (
            color[0],
            color[1],
            color[2],
            color[3] * float(data.get("alpha", 1.0)),
        )

    @classmethod
    def material_signature(cls, material_path, data):
        color_scale = cls.color_scale(data)
        return (
            path_key(material_path),
            *(round(value, 6) for value in color_scale),
            round(float(data.get("alpha", 1.0)), 6),
            round(float(data.get("roughnessScale", 1.0)), 6),
            bool(data.get("horizontalFlip", 0)),
            bool(data.get("verticalFlip", 0)),
            bool(data.get("isStretchingEnabled", 0)),
            int(data.get("orderNo", 0)),
        )

    @staticmethod
    def set_uvs(
        mesh,
        *,
        horizontal_flip=False,
        vertical_flip=False,
    ):
        mesh.update()
        loop_count = len(mesh.loops)
        if loop_count == 0:
            return

        uv_layer = (
            mesh.uv_layers.get("UVMap")
            or mesh.uv_layers.new(name="UVMap")
        )
        loop_vertices = np.empty(loop_count, dtype=np.int32)
        mesh.loops.foreach_get("vertex_index", loop_vertices)

        vertex_coordinates = np.empty(
            len(mesh.vertices) * 3,
            dtype=np.float32,
        )
        mesh.vertices.foreach_get("co", vertex_coordinates)
        vertex_coordinates.shape = (-1, 3)

        loop_uv = np.empty((loop_count, 2), dtype=np.float32)
        loop_uv[:] = vertex_coordinates[loop_vertices, :2]
        loop_uv += 0.5
        if horizontal_flip:
            np.subtract(1.0, loop_uv[:, 0], out=loop_uv[:, 0])
        if vertical_flip:
            np.subtract(1.0, loop_uv[:, 1], out=loop_uv[:, 1])

        uv_layer.uv.foreach_set("vector", loop_uv.reshape(-1))
        mesh.update()

    @staticmethod
    def configure_render_state(material):
        if hasattr(material, "surface_render_method"):
            try:
                material.surface_render_method = "DITHERED"
            except (TypeError, ValueError):
                pass
        if hasattr(material, "blend_method"):
            try:
                material.blend_method = "HASHED"
            except (TypeError, ValueError):
                pass
        material["no_shadows"] = True

    @staticmethod
    def alpha_factor_present(
        alpha_socket,
        sector_alpha,
        tolerance=1e-6,
    ):
        if (
            alpha_socket is None
            or not getattr(alpha_socket, "is_linked", False)
        ):
            return False
        links = list(getattr(alpha_socket, "links", ()))
        if len(links) != 1:
            return False
        source_node = getattr(links[0], "from_node", None)
        if (
            source_node is None
            or getattr(source_node, "bl_idname", "")
            != "ShaderNodeMath"
            or getattr(source_node, "operation", "") != "MULTIPLY"
        ):
            return False
        for socket in list(getattr(source_node, "inputs", ()))[:2]:
            if getattr(socket, "is_linked", False):
                continue
            try:
                if math.isclose(
                    float(socket.default_value),
                    sector_alpha,
                    abs_tol=tolerance,
                ):
                    return True
            except (TypeError, ValueError):
                continue
        return False

    @classmethod
    def apply_sector_alpha(cls, material, sector_alpha):
        if not material.use_nodes or material.node_tree is None:
            return "NO_NODE_TREE"

        tree = material.node_tree
        alpha_sockets = []
        for node in tree.nodes:
            if (
                getattr(node, "bl_idname", "")
                != "ShaderNodeBsdfPrincipled"
            ):
                continue
            alpha_socket = node.inputs.get("Alpha")
            if alpha_socket is not None:
                alpha_sockets.append(alpha_socket)

        if not alpha_sockets:
            return "NO_PRINCIPLED_ALPHA"

        modes = []
        for alpha_socket in alpha_sockets:
            if cls.alpha_factor_present(
                alpha_socket,
                sector_alpha,
            ):
                modes.append("HANDLER")
                continue

            links = list(alpha_socket.links)
            if links:
                source_socket = links[0].from_socket
                for link in links:
                    tree.links.remove(link)
                multiply = tree.nodes.new("ShaderNodeMath")
                multiply.name = "CP77 Sector Decal Alpha"
                multiply.label = "CP77 Sector Decal Alpha"
                multiply.operation = "MULTIPLY"
                multiply.inputs[1].default_value = sector_alpha
                multiply.location = (
                    alpha_socket.node.location.x - 220.0,
                    alpha_socket.node.location.y - 260.0,
                )
                tree.links.new(source_socket, multiply.inputs[0])
                tree.links.new(multiply.outputs[0], alpha_socket)
                modes.append("POST_MULTIPLY")
            else:
                try:
                    alpha_socket.default_value = (
                        float(alpha_socket.default_value)
                        * sector_alpha
                    )
                except (TypeError, ValueError):
                    alpha_socket.default_value = sector_alpha
                modes.append("SOCKET_DEFAULT")

        return "+".join(sorted(set(modes)))

    @classmethod
    def apply_material_overrides(cls, material, data):
        color_scale = cls.color_scale(data)
        display_color = cls.color(data)
        sector_alpha = float(data.get("alpha", 1.0))

        material.diffuse_color = display_color
        material["cp77Alpha"] = sector_alpha
        material["cp77DiffuseColorScale"] = list(color_scale)
        material["cp77RoughnessScale"] = float(
            data.get("roughnessScale", 1.0)
        )
        material["cp77HorizontalFlip"] = bool(
            data.get("horizontalFlip", 0)
        )
        material["cp77VerticalFlip"] = bool(
            data.get("verticalFlip", 0)
        )
        material["cp77StretchingEnabled"] = bool(
            data.get("isStretchingEnabled", 0)
        )
        material["cp77OrderNo"] = int(data.get("orderNo", 0))
        cls.configure_render_state(material)

        if not material.use_nodes or material.node_tree is None:
            material["cp77SectorAlphaMode"] = "NO_NODE_TREE"
            return

        values = {
            "diffusecolorscale": color_scale,
            "roughnessscale": float(
                data.get("roughnessScale", 1.0)
            ),
        }
        for node in material.node_tree.nodes:
            for socket in getattr(node, "inputs", ()):
                key = (
                    socket.name
                    .replace(" ", "")
                    .replace("_", "")
                    .lower()
                )
                if (
                    key not in values
                    or not hasattr(socket, "default_value")
                ):
                    continue
                try:
                    socket.default_value = values[key]
                except (TypeError, ValueError):
                    pass

        if material.get("cp77SectorAlphaHandled"):
            material["cp77SectorAlphaMode"] = "HANDLER"
        else:
            material["cp77SectorAlphaMode"] = cls.apply_sector_alpha(
                material,
                sector_alpha,
            )
        material["cp77SectorAlphaApplied"] = True

    def resolve_material_path(self, material_path):
        resolved = self.session.resource_resolver.resolve_json(
            "material",
            material_path,
            ".mi.json",
        )
        return resolved.resolved_path, resolved.expected_path

    @staticmethod
    def _resource_revision(path):
        normalized = os.path.abspath(os.path.normpath(path))
        try:
            stat_result = os.stat(normalized)
        except OSError:
            return path_key(normalized), 0, 0
        mtime_ns = getattr(stat_result, "st_mtime_ns", None)
        if mtime_ns is None:
            mtime_ns = int(stat_result.st_mtime * 1_000_000_000)
        return path_key(normalized), int(mtime_ns), int(stat_result.st_size)

    @staticmethod
    def _base_material_path(root_chunk):
        base_material = (
            root_chunk.get("baseMaterial")
            if isinstance(root_chunk, dict)
            else None
        )
        depot_path = (
            base_material.get("DepotPath")
            if isinstance(base_material, dict)
            else None
        )
        if isinstance(depot_path, dict):
            return str(depot_path.get("$value", "") or "")
        return str(depot_path or "")

    def _descriptor(self, resolved_path):
        source_identity = self._resource_revision(resolved_path)
        cached = self.descriptor_cache.get(source_identity)
        if cached is not None:
            self.stats["descriptor_hits"] += 1
            return cached

        self.stats["descriptor_misses"] += 1
        self.stats["documents_loaded"] += 1
        resource = self.session.material_resources.load(resolved_path)
        document = resource.payload if resource is not None else None
        data_block = document.get("Data") if isinstance(document, dict) else None
        root_chunk = resource.root if resource is not None else None
        if not isinstance(root_chunk, dict):
            descriptor = _DecalResourceDescriptor(
                document=None,
                data_block=None,
                root_chunk=None,
                source_identity=source_identity,
                base_material_path="",
                status="INVALID_MATERIAL_DOCUMENT",
                error="Material JSON did not produce a RootChunk dictionary",
            )
            self.stats["invalid_documents"] += 1
        else:
            descriptor = _DecalResourceDescriptor(
                document=document,
                data_block=data_block,
                root_chunk=root_chunk,
                source_identity=source_identity,
                base_material_path=self._base_material_path(root_chunk),
                status="RESOLVED",
            )

        source_path = source_identity[0]
        stale_keys = [
            key for key in self.descriptor_cache
            if key[0] == source_path and key != source_identity
        ]
        for key in stale_keys:
            self.descriptor_cache.pop(key, None)
        self.descriptor_cache[source_identity] = descriptor
        return descriptor

    def _variant_document(self, descriptor, data):
        document = dict(descriptor.document)
        data_block = dict(descriptor.data_block)
        root_chunk = dict(descriptor.root_chunk)
        document["Data"] = data_block
        data_block["RootChunk"] = root_chunk

        color_scale = data.get("diffuseColorScale", {})
        root_chunk["alpha"] = float(data.get("alpha", 1.0))
        root_chunk["diffuseColorScale"] = (
            dict(color_scale)
            if isinstance(color_scale, dict)
            else color_scale
        )
        root_chunk["roughnessScale"] = float(
            data.get("roughnessScale", 1.0)
        )
        root_chunk["horizontalFlip"] = bool(
            data.get("horizontalFlip", 0)
        )
        root_chunk["verticalFlip"] = bool(
            data.get("verticalFlip", 0)
        )
        root_chunk["isStretchingEnabled"] = bool(
            data.get("isStretchingEnabled", 0)
        )
        self.stats["variant_documents"] += 1
        return document

    def _builder_cache_identity(self, descriptor, data):
        return (
            "sector_decal",
            *descriptor.source_identity,
            descriptor.base_material_path,
            float(data.get("alpha", 1.0)),
            self.color_scale(data),
            float(data.get("roughnessScale", 1.0)),
            bool(data.get("horizontalFlip", 0)),
            bool(data.get("verticalFlip", 0)),
            bool(data.get("isStretchingEnabled", 0)),
        )

    def _claim_or_clone_material(self, built_material):
        material_id = id(built_material)
        try:
            can_claim = (
                built_material.users == 0
                and material_id not in self._owned_material_ids
            )
        except (AttributeError, ReferenceError, TypeError):
            can_claim = False

        if can_claim:
            material = built_material
            self.stats["materials_claimed"] += 1
        else:
            material = track_created_datablock("materials", built_material.copy())
            self.stats["materials_cloned"] += 1
        self._owned_material_ids.add(id(material))
        return material

    def cache_stats(self):
        return {
            **self.stats,
            "descriptor_entries": len(self.descriptor_cache),
            "material_entries": len(self.cache),
            "mesh_entries": len(self.mesh_cache),
        }

    def plane_mesh(
        self,
        signature,
        material_result,
        *,
        horizontal_flip=False,
        vertical_flip=False,
    ):
        cached = self.mesh_cache.get(signature)
        if cached is not None:
            if (
                material_result.material is not None
                and not cached.materials
            ):
                cached.materials.append(material_result.material)
            return cached

        suffix = hashlib.sha1(
            repr(signature).encode("utf-8")
        ).hexdigest()[:12]
        mesh = track_created_datablock("meshes", bpy.data.meshes.new(f"CP77_DecalPlane_{suffix}"))
        mesh.from_pydata(
            (
                (-0.5, -0.5, 0.0),
                (0.5, -0.5, 0.0),
                (-0.5, 0.5, 0.0),
                (0.5, 0.5, 0.0),
            ),
            [],
            ((0, 1, 3, 2),),
        )
        self.set_uvs(
            mesh,
            horizontal_flip=horizontal_flip,
            vertical_flip=vertical_flip,
        )
        if material_result.material is not None:
            mesh.materials.append(material_result.material)
        self.mesh_cache[signature] = mesh
        return mesh

    def require_material(self, material_path, data):
        signature = self.material_signature(material_path, data)
        resolved_path, expected_path = self.resolve_material_path(
            material_path
        )

        if not self.session.options.with_materials:
            return DecalMaterialResult(
                material=None,
                material_path=material_path,
                resolved_path=resolved_path,
                expected_path=expected_path,
                signature=signature,
                status="MATERIALS_DISABLED",
            )
        if not material_path:
            return DecalMaterialResult(
                material=None,
                material_path="",
                resolved_path="",
                expected_path="",
                signature=signature,
                status="NO_MATERIAL_PATH",
            )
        if not resolved_path:
            return DecalMaterialResult(
                material=None,
                material_path=material_path,
                resolved_path="",
                expected_path=expected_path,
                signature=signature,
                status="MATERIAL_NOT_INDEXED",
                error=expected_path,
            )

        cached = self.cache.get(signature)
        if cached is not None:
            return DecalMaterialResult(
                material=cached,
                material_path=material_path,
                resolved_path=resolved_path,
                expected_path=expected_path,
                signature=signature,
                status="CACHE_HIT",
            )

        try:
            descriptor = self._descriptor(resolved_path)
            if descriptor.status != "RESOLVED":
                return DecalMaterialResult(
                    material=None,
                    material_path=material_path,
                    resolved_path=resolved_path,
                    expected_path=expected_path,
                    signature=signature,
                    status=descriptor.status,
                    error=descriptor.error,
                )

            document = self._variant_document(descriptor, data)
            builder = MaterialBuilder(
                document,
                self.session.raw_root,
                "png",
                self.session.raw_root,
            )
            built_material = builder.createdecal(
                0,
                cache_identity=self._builder_cache_identity(
                    descriptor,
                    data,
                ),
            )
            if built_material is None:
                return DecalMaterialResult(
                    material=None,
                    material_path=material_path,
                    resolved_path=resolved_path,
                    expected_path=expected_path,
                    signature=signature,
                    status="BUILDER_RETURNED_NONE",
                )

            base_name = built_material.name
            material = self._claim_or_clone_material(
                built_material
            )
            suffix = hashlib.sha1(
                repr(signature).encode("utf-8")
            ).hexdigest()[:8]
            material.name = f"{base_name}_{suffix}"[:63]
            self.apply_material_overrides(material, data)
            self.cache[signature] = material
            return DecalMaterialResult(
                material=material,
                material_path=material_path,
                resolved_path=resolved_path,
                expected_path=expected_path,
                signature=signature,
                status="BUILT",
            )
        except Exception as error:
            return DecalMaterialResult(
                material=None,
                material_path=material_path,
                resolved_path=resolved_path,
                expected_path=expected_path,
                signature=signature,
                status="MATERIAL_BUILD_FAILED",
                error=str(error),
            )

    @staticmethod
    def fallback_wire(plane):
        plane.display_type = "WIRE"
        plane.color = (1.0, 0.905, 0.062, 1.0)
        plane.show_wire = True
        plane.display.show_shadows = False

    def create(self, context, instance, instance_index):
        data = context.data
        material_path = context.operations.depot_path(
            data,
            "material",
        )
        projector = context.operations.new_empty(
            f'DecalProjector_{context.node_index}_'
            f'{instance["nodeDataIndex"]}',
            context.sector_collection,
            display_size=0.2,
        )
        projector.empty_display_type = "CUBE"
        projector.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )

        material_result = self.require_material(
            material_path,
            data,
        )
        mesh = self.plane_mesh(
            material_result.signature,
            material_result,
            horizontal_flip=bool(data.get("horizontalFlip", 0)),
            vertical_flip=bool(data.get("verticalFlip", 0)),
        )
        plane = track_created_datablock("objects", bpy.data.objects.new(
            f"DecalPlane_{context.node_index}_{instance_index}",
            mesh,
        ))
        context.sector_collection.objects.link(plane)
        plane.parent = projector
        plane.matrix_parent_inverse = Matrix.Identity(4)
        plane.matrix_basis = Matrix.Identity(4)
        plane.color = self.color(data)

        if material_result.material is None:
            self.fallback_wire(plane)

        return DecalPlacement(
            projector=projector,
            plane=plane,
            material_result=material_result,
        )
