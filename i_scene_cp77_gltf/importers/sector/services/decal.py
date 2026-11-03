from __future__ import annotations
<<<<<<< Updated upstream
from ....blender.transactions import track_created_datablock

from dataclasses import dataclass
import hashlib
import math
import os
=======

import hashlib
import os
import re
import time
from dataclasses import dataclass
>>>>>>> Stashed changes

import bpy
import numpy as np
from mathutils import Matrix

<<<<<<< Updated upstream
from ....materials.blender.builder import MaterialBuilder
from ...common.paths import path_key


DECAL_PLACEMENT_CONTRACT = "DECAL_PROJECTOR_LOCAL_Z_UNIT_PLANE"
=======
from ....assetio.documents import file_identity
from ....assetio.paths import local_path_key
from ....blender.decal_overrides import (
    apply_override_values,
    apply_sector_alpha,
    capture_graph_state,
    nodes_added_since,
    restore_graph_state,
)
from ....blender.identity import rna_identity, rna_is_live
from ....blender.naming import fit_id_name
from ....blender.shader_nodes import outputs_detached, remove_unused_shading
from ....blender.transactions import track_created_datablock
from ....core.log import get_logger, is_enabled, log_once
from ....material_types.decal_composite import PROJECTION_COVERAGE_ATTRIBUTE
from ....materials.blender.builder import MaterialBuilder
from ....materials.blender.bulk import bulk_material_import_scope
from ....materials.blender.cache import (
    _MATERIAL_CACHE,
    _cache_material,
    _lookup_cached,
    _record_prototype_hit,
    rename_cached_material,
)
from ....materials.blender.profiling import (
    detailed_material_profiling_requested,
    finish_material_profiling,
    merge_material_profiles,
    start_material_profiling,
)
from ....materials.blender.registry import DECAL_REGISTRY
from ....materials.parser import base_material_path
from ...common.paths import depot_path
from ..objects import new_empty
from .decal_projection import PendingDecalProjection, project_pending_decals

_LOG = get_logger(__name__)
>>>>>>> Stashed changes


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
<<<<<<< Updated upstream
    plane: object
    material_result: DecalMaterialResult



=======
    plane: object | None
    material_result: DecalMaterialResult


>>>>>>> Stashed changes
class DecalService:
    def __init__(self, session):
        self.session = session
        self.cache = session.caches.materials
        self.mesh_cache = session.caches.decal_meshes
        self.descriptor_cache = {}
<<<<<<< Updated upstream
        self._owned_material_ids = set()
=======
        self.graph_prototypes = {}
        self.pending_by_collection = {}
        self.projector_counts_by_collection = {}
        self.composite_material_cache = {}
        self._owned_materials = {}
        self._built_materials = {}
        self._material_names = {}
        self._retired_composites = []
        self.timings = {}
        self.material_profile = {}
>>>>>>> Stashed changes
        self.stats = {
            "descriptor_hits": 0,
            "descriptor_misses": 0,
            "documents_loaded": 0,
            "invalid_documents": 0,
            "variant_documents": 0,
<<<<<<< Updated upstream
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
=======
            "material_hits": 0,
            "material_misses": 0,
            "materials_claimed": 0,
            "materials_cloned": 0,
            "graph_reuses": 0,
            "conformal_projectors": 0,
            "conformal_patches": 0,
            "conformal_triangles": 0,
        }

    def record_timing(self, phase, started):
        elapsed = max(0.0, time.perf_counter() - started)
        self.timings[phase] = self.timings.get(phase, 0.0) + elapsed

    @staticmethod
    def color_scale(data):
        color = data.get("diffuseColorScale", {}) if isinstance(data, dict) else {}
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
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
=======
    def material_signature(cls, material_path, data, *, conformal=False):
        color_scale = cls.color_scale(data)
        signature = (
            local_path_key(material_path),
            *(round(value, 6) for value in color_scale),
            round(float(data.get("alpha", 1.0)), 6),
            round(float(data.get("roughnessScale", 1.0)), 6),
            round(float(data.get("emissiveScale", 1.0)), 6),
            int(data.get("normalBlendingMode", 0) or 0),
        )
        return ("CONFORMAL" if conformal else "PLANE", *signature)
>>>>>>> Stashed changes

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

<<<<<<< Updated upstream
        uv_layer = (
            mesh.uv_layers.get("UVMap")
            or mesh.uv_layers.new(name="UVMap")
        )
=======
        uv_layer = mesh.uv_layers.get("UVMap") or mesh.uv_layers.new(name="UVMap")
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
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
=======
        material.surface_render_method = "DITHERED"
        material["cp77_no_shadows"] = True
>>>>>>> Stashed changes

    @classmethod
    def apply_material_overrides(cls, material, data):
        color_scale = cls.color_scale(data)
        display_color = cls.color(data)
        sector_alpha = float(data.get("alpha", 1.0))

        material.diffuse_color = display_color
<<<<<<< Updated upstream
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
=======
        material["alpha"] = sector_alpha
        material["diffuseColorScale"] = list(color_scale)
        material["normalBlendingMode"] = int(data.get("normalBlendingMode", 0) or 0)
        cls.configure_render_state(material)

        if not material.use_nodes or material.node_tree is None:
            return
        # Written with the output unlinked, so each write updates only this material.
        with outputs_detached(material.node_tree):
            cls._apply_node_overrides(material, data, color_scale, sector_alpha)

    @classmethod
    def _apply_node_overrides(cls, material, data, color_scale, sector_alpha):
        values = {
            "diffusecolorscale": color_scale,
            "roughnessscale": float(data.get("roughnessScale", 1.0)),
            "decalalpha": sector_alpha,
            "emissivescale": float(data.get("emissiveScale", 1.0)),
        }
        apply_override_values(material.node_tree, values)
        if not material.get("cp77SectorAlphaHandled"):
            apply_sector_alpha(material, sector_alpha)
>>>>>>> Stashed changes

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
<<<<<<< Updated upstream
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
=======
        identity = file_identity(normalized)
        return local_path_key(normalized), identity.mtime_ns, identity.size
>>>>>>> Stashed changes

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
<<<<<<< Updated upstream
                base_material_path=self._base_material_path(root_chunk),
=======
                base_material_path=base_material_path(root_chunk),
>>>>>>> Stashed changes
                status="RESOLVED",
            )

        source_path = source_identity[0]
        stale_keys = [
<<<<<<< Updated upstream
            key for key in self.descriptor_cache
=======
            key
            for key in self.descriptor_cache
>>>>>>> Stashed changes
            if key[0] == source_path and key != source_identity
        ]
        for key in stale_keys:
            self.descriptor_cache.pop(key, None)
        self.descriptor_cache[source_identity] = descriptor
        return descriptor

<<<<<<< Updated upstream
    def _variant_document(self, descriptor, data):
=======
    def _variant_document(
        self,
        descriptor,
        data,
        material_path,
        *,
        conformal=False,
    ):
>>>>>>> Stashed changes
        document = dict(descriptor.document)
        data_block = dict(descriptor.data_block)
        root_chunk = dict(descriptor.root_chunk)
        document["Data"] = data_block
        data_block["RootChunk"] = root_chunk

        color_scale = data.get("diffuseColorScale", {})
        root_chunk["alpha"] = float(data.get("alpha", 1.0))
        root_chunk["diffuseColorScale"] = (
<<<<<<< Updated upstream
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
=======
            dict(color_scale) if isinstance(color_scale, dict) else color_scale
        )
        root_chunk["roughnessScale"] = float(data.get("roughnessScale", 1.0))
        root_chunk["emissiveScale"] = float(data.get("emissiveScale", 1.0))
        root_chunk["normalBlendingMode"] = int(data.get("normalBlendingMode", 0) or 0)
        if not conformal:
            root_chunk["horizontalFlip"] = bool(data.get("horizontalFlip", 0))
            root_chunk["verticalFlip"] = bool(data.get("verticalFlip", 0))
        root_chunk["isStretchingEnabled"] = bool(data.get("isStretchingEnabled", 0))
        root_chunk["__sectorMaterialPath"] = str(material_path or "")
        self.stats["variant_documents"] += 1
        return document

    def _builder_cache_identity(self, descriptor, data, *, conformal=False):
        identity = (
>>>>>>> Stashed changes
            "sector_decal",
            *descriptor.source_identity,
            descriptor.base_material_path,
            float(data.get("alpha", 1.0)),
            self.color_scale(data),
            float(data.get("roughnessScale", 1.0)),
<<<<<<< Updated upstream
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
=======
            float(data.get("emissiveScale", 1.0)),
            int(data.get("normalBlendingMode", 0) or 0),
        )
        return ("CONFORMAL" if conformal else "PLANE", *identity)

    def _claim_or_clone_material(self, built_material):
        try:
            can_claim = (
                built_material.users == 0
                and rna_identity(built_material) not in self._owned_materials
            )
        except (AttributeError, ReferenceError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("DecalService._claim_or_clone_material", type(error).__name__),
                "claim or clone material: fell back after %s",
                error,
                exc_info=True,
            )
>>>>>>> Stashed changes
            can_claim = False

        if can_claim:
            material = built_material
            self.stats["materials_claimed"] += 1
        else:
            material = track_created_datablock("materials", built_material.copy())
            self.stats["materials_cloned"] += 1
<<<<<<< Updated upstream
        self._owned_material_ids.add(id(material))
        return material

    def cache_stats(self):
        return {
            **self.stats,
=======
        self._owned_materials[rna_identity(material)] = material
        return material

    def _graph_prototype_key(self, descriptor, material_path, data, conformal):
        """Share only the projected handler's graph with instance-only overrides"""
        rule = DECAL_REGISTRY.resolve(descriptor.base_material_path)
        if (
            rule is None
            or rule.factory.module_name != "decal_nodes"
            or rule.factory.class_name != "ProjectedDecal"
            or not isinstance(descriptor.root_chunk.get("values"), list)
        ):
            return None
        return (
            descriptor.source_identity,
            descriptor.base_material_path,
            str(material_path),
            bool(conformal),
            int(data.get("normalBlendingMode", 0) or 0),
            bool(data.get("isStretchingEnabled", 0)),
            bool(data.get("horizontalFlip", 0)) if not conformal else False,
            bool(data.get("verticalFlip", 0)) if not conformal else False,
        )

    def _clone_graph_prototype(self, builder, key, identity):
        """Restore the pre-finalization graph before applying another decal's overrides"""
        entry = self.graph_prototypes.get(key) if key is not None else None
        if entry is None or not rna_is_live(entry[0]):
            return None, None
        root = builder.obj["Data"]["RootChunk"]
        signature = builder.decal_signature(root, cache_identity=identity)
        if _lookup_cached(_MATERIAL_CACHE, signature) is not None:
            return None, None
        prototype, state, added_nodes = entry
        material = track_created_datablock("materials", prototype.copy())
        try:
            material.name = builder.archive_material_name()
            restore_graph_state(material.node_tree, state, added_nodes)
            builder._set_material_source_properties(
                material, {}, include_template=False
            )
            _cache_material(signature, signature, material, cloned=True)
            _record_prototype_hit()
            self.stats["graph_reuses"] += 1
            return material, state
        except Exception:
            builder._remove_failed_material(material)
            raise

    def cache_stats(self):
        return {
            **self.stats,
            "timings": dict(self.timings),
            "material_profile": {
                phase: dict(values) for phase, values in self.material_profile.items()
            },
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
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
=======
        mesh_signature = (
            *signature,
            "STANDARD_WINDING",
            bool(horizontal_flip),
            bool(vertical_flip),
        )
        cached = self.mesh_cache.get(mesh_signature)
        if cached is not None:
            if material_result.material is not None and not cached.materials:
                cached.materials.append(material_result.material)
            return cached

        suffix = hashlib.sha1(repr(mesh_signature).encode("utf-8")).hexdigest()[:12]
        mesh = track_created_datablock(
            "meshes", bpy.data.meshes.new(f"CP77_DecalPlane_{suffix}")
        )
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
        if material_result.material is not None:
            mesh.materials.append(material_result.material)
        self.mesh_cache[signature] = mesh
        return mesh

    def require_material(self, material_path, data):
        signature = self.material_signature(material_path, data)
        resolved_path, expected_path = self.resolve_material_path(
            material_path
        )
=======
        coverage = mesh.attributes.new(
            name=PROJECTION_COVERAGE_ATTRIBUTE,
            type="FLOAT",
            domain="POINT",
        )
        coverage.data.foreach_set(
            "value",
            np.ones(len(mesh.vertices), dtype=np.float32),
        )
        if material_result.material is not None:
            mesh.materials.append(material_result.material)
        self.mesh_cache[mesh_signature] = mesh
        return mesh

    def require_material(self, material_path, data):
        resolution_started = time.perf_counter()
        conformal = self.session.options.decal_mode == "CONFORMAL"
        signature = self.material_signature(
            material_path,
            data,
            conformal=conformal,
        )
        resolved_path, expected_path = self.resolve_material_path(material_path)
        self.record_timing("dependency_resolution", resolution_started)
>>>>>>> Stashed changes

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

<<<<<<< Updated upstream
        cached = self.cache.get(signature)
        if cached is not None:
=======
        cache_started = time.perf_counter()
        cached = self.cache.get(signature)
        self.record_timing("material_cache_lookup", cache_started)
        if cached is not None:
            self.stats["material_hits"] += 1
>>>>>>> Stashed changes
            return DecalMaterialResult(
                material=cached,
                material_path=material_path,
                resolved_path=resolved_path,
                expected_path=expected_path,
                signature=signature,
                status="CACHE_HIT",
            )

<<<<<<< Updated upstream
        try:
            descriptor = self._descriptor(resolved_path)
=======
        self.stats["material_misses"] += 1
        try:
            descriptor_started = time.perf_counter()
            descriptor = self._descriptor(resolved_path)
            self.record_timing("descriptor_load", descriptor_started)
>>>>>>> Stashed changes
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

<<<<<<< Updated upstream
            document = self._variant_document(descriptor, data)
=======
            variant_started = time.perf_counter()
            document = self._variant_document(
                descriptor,
                data,
                material_path,
                conformal=conformal,
            )
            self.record_timing("material_variant", variant_started)
>>>>>>> Stashed changes
            builder = MaterialBuilder(
                document,
                self.session.raw_root,
                "png",
                self.session.raw_root,
            )
<<<<<<< Updated upstream
            built_material = builder.createdecal(
                0,
                cache_identity=self._builder_cache_identity(
                    descriptor,
                    data,
                ),
            )
=======
            builder_identity = self._builder_cache_identity(
                descriptor, data, conformal=conformal
            )
            graph_key = self._graph_prototype_key(
                descriptor, material_path, data, conformal
            )
            graph_state = None
            build_started = time.perf_counter()
            profile_session = start_material_profiling(
                is_enabled("DEBUG", _LOG) and detailed_material_profiling_requested()
            )
            try:
                with bulk_material_import_scope(True):
                    built_material, graph_state = self._clone_graph_prototype(
                        builder,
                        graph_key,
                        builder_identity,
                    )
                    if built_material is None:
                        built_material = builder.createdecal(
                            0, cache_identity=builder_identity
                        )
            finally:
                self.record_timing("material_build", build_started)
                merge_material_profiles(
                    self.material_profile, finish_material_profiling(profile_session)
                )
>>>>>>> Stashed changes
            if built_material is None:
                return DecalMaterialResult(
                    material=None,
                    material_path=material_path,
                    resolved_path=resolved_path,
                    expected_path=expected_path,
                    signature=signature,
                    status="BUILDER_RETURNED_NONE",
                )

<<<<<<< Updated upstream
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
=======
            finalize_started = time.perf_counter()
            self._built_materials.setdefault(
                rna_identity(built_material), built_material
            )
            if graph_key is not None and graph_state is None:
                graph_state = capture_graph_state(built_material)
            material = self._claim_or_clone_material(built_material)
            suffix = hashlib.sha1(repr(signature).encode("utf-8")).hexdigest()[:8]
            # The name comes from the source and signature, never from the datablock, which may be a cached material
            # an earlier import already renamed. A claimed material stays the cached decal material of its signature.
            name = fit_id_name(builder.archive_material_name(), f"_{suffix}")
            rename_cached_material(material, name)
            self._material_names[rna_identity(material)] = (material, name)
            self.apply_material_overrides(
                material,
                data,
            )
            if graph_key is not None and graph_state is not None:
                added_nodes = nodes_added_since(material.node_tree, graph_state)
                self.graph_prototypes[graph_key] = (material, graph_state, added_nodes)
            self.cache[signature] = material
            self.record_timing("material_finalize", finalize_started)
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
        material_path = context.operations.depot_path(
            data,
            "material",
        )
        projector = context.operations.new_empty(
            f'DecalProjector_{context.node_index}_'
            f'{instance["nodeDataIndex"]}',
            context.sector_collection,
=======
        material_path = depot_path(
            data,
            "material",
        )
        mode = self.session.options.decal_mode
        projector_started = time.perf_counter()
        source_collection = context.collection_for_instance(instance)
        projector = new_empty(
            f"DecalProjector_{context.node_index}_{instance.index}",
            source_collection,
>>>>>>> Stashed changes
            display_size=0.2,
        )
        projector.empty_display_type = "CUBE"
        projector.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )
<<<<<<< Updated upstream
=======
        self.record_timing("projector_create", projector_started)
        collection_key = context.sector_collection.as_pointer()
        self.projector_counts_by_collection[collection_key] = (
            self.projector_counts_by_collection.get(collection_key, 0) + 1
        )
        if mode == "PROJECTORS_ONLY":
            resolved_path, expected_path = self.resolve_material_path(material_path)
            material_result = DecalMaterialResult(
                material=None,
                material_path=material_path,
                resolved_path=resolved_path,
                expected_path=expected_path,
                signature=self.material_signature(
                    material_path,
                    data,
                    conformal=False,
                ),
                status="PROJECTORS_ONLY",
            )
            return DecalPlacement(
                projector=projector,
                plane=None,
                material_result=material_result,
            )
>>>>>>> Stashed changes

        material_result = self.require_material(
            material_path,
            data,
        )
<<<<<<< Updated upstream
=======
        surface_started = time.perf_counter()
        if mode == "CONFORMAL":
            if material_result.material is not None:
                self.pending_by_collection.setdefault(
                    context.sector_collection.as_pointer(),
                    [],
                ).append(
                    PendingDecalProjection(
                        projector=projector,
                        material=material_result.material,
                        data=dict(data),
                        node_index=context.node_index,
                        instance_index=instance_index,
                    )
                )
            placement = DecalPlacement(
                projector=projector,
                plane=None,
                material_result=material_result,
            )
            self.record_timing("surface_placement", surface_started)
            return placement

>>>>>>> Stashed changes
        mesh = self.plane_mesh(
            material_result.signature,
            material_result,
            horizontal_flip=bool(data.get("horizontalFlip", 0)),
            vertical_flip=bool(data.get("verticalFlip", 0)),
        )
<<<<<<< Updated upstream
        plane = track_created_datablock("objects", bpy.data.objects.new(
            f"DecalPlane_{context.node_index}_{instance_index}",
            mesh,
        ))
        context.sector_collection.objects.link(plane)
=======
        plane = track_created_datablock(
            "objects",
            bpy.data.objects.new(
                f"DecalPlane_{context.node_index}_{instance_index}",
                mesh,
            ),
        )
        source_collection.objects.link(plane)
>>>>>>> Stashed changes
        plane.parent = projector
        plane.matrix_parent_inverse = Matrix.Identity(4)
        plane.matrix_basis = Matrix.Identity(4)
        plane.color = self.color(data)

        if material_result.material is None:
            self.fallback_wire(plane)

<<<<<<< Updated upstream
        return DecalPlacement(
=======
        placement = DecalPlacement(
>>>>>>> Stashed changes
            projector=projector,
            plane=plane,
            material_result=material_result,
        )
<<<<<<< Updated upstream
=======
        self.record_timing("surface_placement", surface_started)
        return placement

    def finalize_sector(self, execution_context):
        collection = execution_context.sector_collection
        collection_key = collection.as_pointer()
        pending = self.pending_by_collection.pop(collection_key, [])
        projector_count = self.projector_counts_by_collection.pop(
            collection_key,
            0,
        )
        mode = self.session.options.decal_mode
        if mode != "CONFORMAL":
            return {
                "projectors": projector_count,
                "patches": 0,
                "triangles": 0,
                "errors": (),
            }
        output_collection = (
            execution_context.generated_collection("DecalProjection")
            if pending
            else collection
        )
        summary = project_pending_decals(
            collection,
            pending,
            self.composite_material_cache,
            output_collection=output_collection,
        )
        summary["projectors"] = projector_count
        self.stats["conformal_projectors"] += summary["projectors"]
        self.stats["conformal_patches"] += summary["patches"]
        self.stats["conformal_triangles"] += summary["triangles"]
        return summary

    def invalidate_projection_cache(self):
        self._retired_composites.extend(
            _cached_datablocks(self.composite_material_cache)
        )
        self.composite_material_cache.clear()

    def release_unused_materials(self):
        """Remove the decal materials this import left without users"""
        composites = (
            *_cached_datablocks(self.composite_material_cache),
            *self._retired_composites,
        )
        removed = remove_unused_shading(
            (
                *self._built_materials.values(),
                *self._owned_materials.values(),
                *composites,
            )
        )
        for material, name in self._material_names.values():
            if rna_is_live(material):
                _reclaim_name(material, bpy.data.materials, name)
        for value in composites:
            if rna_is_live(value):
                collection = (
                    bpy.data.materials
                    if isinstance(value, bpy.types.Material)
                    else bpy.data.node_groups
                )
                _reclaim_name(
                    value, collection, _BLENDER_DUPLICATE_SUFFIX.sub("", value.name)
                )
        _LOG.debug("Decal shading released: %d material(s) and node group(s)", removed)
        self._built_materials.clear()
        self._owned_materials.clear()
        self._material_names.clear()
        self._retired_composites.clear()
        self.graph_prototypes.clear()
        self.composite_material_cache.clear()
        self.cache.clear()


_BLENDER_DUPLICATE_SUFFIX = re.compile(r"\.\d{3,}$")


def _reclaim_name(datablock, collection, name):
    """Give datablock the name it was built with once nothing else holds it"""
    if datablock.name == name or collection.get(name) is not None:
        return
    if isinstance(datablock, bpy.types.Material):
        rename_cached_material(datablock, name)
    else:
        datablock.name = name


def _cached_datablocks(cache):
    """The materials and node groups a composite cache holds"""
    for value in cache.values():
        if isinstance(value, tuple) and value:
            value = value[0]
        if isinstance(value, bpy.types.ID):
            yield value
>>>>>>> Stashed changes
