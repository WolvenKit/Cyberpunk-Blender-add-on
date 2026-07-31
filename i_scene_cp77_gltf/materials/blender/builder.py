from ...blender.transactions import track_created_datablock
import hashlib
import json
import os
from functools import lru_cache

import bpy

from ...addon_identity import get_addon_preferences, get_addon_version
from .cache import (
    _MATERIAL_CACHE,
    _MATERIAL_CACHE_STATS,
    _MATERIAL_PROTOTYPE_CACHE,
    _cache_material,
    _invalidate_material_signature,
    _lookup_cached,
    _raw_material_digest,
    _record_exact_hit,
    _record_prototype_hit,
)
from .profiling import begin_material_phase, end_material_phase
from ..pathing import context_path_key
from .registry import DECAL_REGISTRY, REGISTRY

_MATERIAL_CACHE_VERSION = 2
_SOURCE_METADATA_KEYS = (
    "m",
    "BaseMaterial",
    "GlobalNormal",
    "MultilayerMask",
    "DiffuseMap",
    "SourceMaterialName",
)


@lru_cache(maxsize=4096)
def _project_path_from_mesh(mesh_path):
    before, marker, _ = str(mesh_path).partition(
        "source\\raw\\".replace("\\", os.sep)
    )
    return before + marker


@lru_cache(maxsize=8192)
def _signature_prefix(
    base_path,
    project_path,
    image_format,
    blender_version,
    addon_version,
    experimental_features,
):
    return json.dumps(
        {
            "cache_version": _MATERIAL_CACHE_VERSION,
            "base_path": context_path_key(base_path),
            "project_path": context_path_key(project_path),
            "image_format": str(image_format).lower(),
            "blender_version": tuple(blender_version),
            "addon_version": tuple(addon_version),
            "experimental_features": bool(experimental_features),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

def _set_hashed_render_method(material):
    if hasattr(material, "surface_render_method"):
        try:
            material.surface_render_method = "DITHERED"
            return
        except (TypeError, ValueError):
            pass
    if hasattr(material, "blend_method"):
        try:
            material.blend_method = "HASHED"
        except (TypeError, ValueError):
            pass


class MaterialBuilder:
    def __init__(self, obj, BasePath, image_format, MeshPath):
        self.BasePath = BasePath
        self.image_format = image_format
        self.obj = obj
        self.MeshPath = MeshPath
        self.ProjPath = _project_path_from_mesh(MeshPath)
        self.addon_ver = get_addon_version()
        try:
            self.experimental_features = bool(
                get_addon_preferences().experimental_features
            )
        except Exception:
            self.experimental_features = False
        self._signature_cache = {}
        self._signature_prefix = _signature_prefix(
            self.BasePath,
            self.ProjPath,
            self.image_format,
            tuple(bpy.app.version),
            tuple(self.addon_ver),
            self.experimental_features,
        )

    def _signature(
        self,
        kind,
        raw_material,
        *,
        include_name,
        mesh_path_sensitive=False,
    ):
        cache_key = (
            kind,
            bool(include_name),
            bool(mesh_path_sensitive),
            id(raw_material),
        )
        signature = self._signature_cache.get(cache_key)
        if signature is not None:
            return signature

        digest = hashlib.blake2b(digest_size=20)
        digest.update(self._signature_prefix)
        digest.update(b"\0")
        digest.update(str(kind).encode("utf-8"))
        digest.update(b"\0")
        digest.update(
            _raw_material_digest(
                raw_material,
                include_name=include_name,
            ).encode("ascii")
        )
        if mesh_path_sensitive:
            digest.update(b"\0")
            digest.update(
                context_path_key(self.MeshPath).encode("utf-8")
            )
        signature = digest.hexdigest()
        self._signature_cache[cache_key] = signature
        return signature

    @staticmethod
    def _material_rule(raw_material):
        if not isinstance(raw_material, dict):
            return None
        return REGISTRY.resolve(raw_material.get("MaterialTemplate", ""))

    def material_signature(self, raw_material):
        rule = self._material_rule(raw_material)
        return self._signature(
            "material",
            raw_material,
            include_name=True,
            mesh_path_sensitive=bool(
                rule and rule.mesh_path_sensitive
            ),
        )

    def material_prototype_signature(self, raw_material):
        rule = self._material_rule(raw_material)
        return self._signature(
            "material",
            raw_material,
            include_name=False,
            mesh_path_sensitive=bool(
                rule and rule.mesh_path_sensitive
            ),
        )

    def decal_signature(self, root, cache_identity=None):
        return self._signature(
            "decal_identity" if cache_identity is not None else "decal",
            cache_identity if cache_identity is not None else root,
            include_name=True,
        )

    def _ensure_nodes(self, bpyMat):
        started = begin_material_phase()
        created = False
        try:
            bpyMat.use_nodes = True
            nodes = bpyMat.node_tree.nodes
            if len(nodes) != 0:
                return
            output = nodes.new("ShaderNodeOutputMaterial")
            output.location = (400, 0)
            bsdf = nodes.new("ShaderNodeBsdfPrincipled")
            bpyMat.node_tree.links.new(
                output.inputs["Surface"],
                bsdf.outputs["BSDF"],
            )
            created = True
        finally:
            if started is not None:
                end_material_phase(
                    started,
                    "material.default_graph",
                    label=getattr(bpyMat, "name", ""),
                    metadata={
                        "created": created,
                        "nodesAdded": 2 if created else 0,
                        "linksAdded": 1 if created else 0,
                    },
                )

    def _new_material(self, name):
        started = begin_material_phase()
        bpyMat = None
        try:
            bpyMat = track_created_datablock("materials", bpy.data.materials.new(name))
            self._ensure_nodes(bpyMat)
            return bpyMat
        finally:
            if started is not None:
                end_material_phase(
                    started,
                    "material.datablock_create",
                    label=getattr(bpyMat, "name", name),
                )

    def _remove_failed_material(self, material):
        try:
            if (
                bpy.data.materials.get(material.name) is material
                and material.users == 0
            ):
                bpy.data.materials.remove(material)
        except (
            AttributeError,
            ReferenceError,
            RuntimeError,
            TypeError,
        ):
            pass

    def _archive_material_name(self):
        archive_name = self.obj.get("Header", {}).get(
            "ArchiveFileName"
        )
        return (
            os.path.basename(archive_name)
            if archive_name
            else "decal_material"
        )

    @staticmethod
    def _base_material_path(data_chunk):
        base_material = (
            data_chunk.get("baseMaterial")
            if isinstance(data_chunk, dict)
            else None
        )
        depot_path = (
            base_material.get("DepotPath")
            if isinstance(base_material, dict)
            else None
        )
        return (
            depot_path.get("$value")
            if isinstance(depot_path, dict)
            else None
        )

    def _set_material_source_properties(
        self,
        bpyMat,
        raw_material,
        *,
        include_template=True,
    ):
        bpyMat["MeshPath"] = self.MeshPath
        bpyMat["DepotPath"] = self.BasePath
        bpyMat["ProjPath"] = self.ProjPath
        bpyMat["AddonVersion"] = self.addon_ver
        bpyMat["SourceMaterialName"] = raw_material.get("Name", bpyMat.name)
        if include_template:
            bpyMat["MaterialTemplate"] = raw_material["MaterialTemplate"]

    @staticmethod
    def _clear_source_metadata(material):
        for key in _SOURCE_METADATA_KEYS:
            try:
                if key in material:
                    del material[key]
            except (
                AttributeError,
                ReferenceError,
                TypeError,
            ):
                pass

    def _clone_material(
        self,
        prototype,
        raw_material,
    ):
        started = begin_material_phase()
        material = None
        try:
            material = track_created_datablock("materials", prototype.copy())
            material.name = raw_material["Name"]
            self._clear_source_metadata(material)
            self._set_material_source_properties(
                material,
                raw_material,
            )
            return material
        finally:
            if started is not None:
                end_material_phase(
                    started,
                    "material.datablock_clone",
                    label=(
                        raw_material.get("Name", "")
                        if isinstance(raw_material, dict)
                        else ""
                    ),
                    metadata={"prototype": getattr(prototype, "name", "")},
                )

    def _route_material(
        self,
        template_path,
        factory_data,
        create_data,
        bpyMat,
        registry,
        *,
        is_decal=False,
        rule=None,
    ):
        lookup_started = begin_material_phase()
        if rule is None:
            rule = registry.resolve(template_path)
        if lookup_started is not None:
            end_material_phase(
                lookup_started,
                "material.registry_lookup",
                label=template_path,
                metadata={"resolved": rule is not None, "decal": bool(is_decal)},
            )
        if not rule:
            label = "decal" if is_decal else "mt"
            print(
                f"Unhandled {label} - {template_path}"
            )
            finalize_started = begin_material_phase()
            try:
                _set_hashed_render_method(bpyMat)
                if not is_decal:
                    bpyMat["no_shadows"] = False
            finally:
                if finalize_started is not None:
                    end_material_phase(
                        finalize_started,
                        "material.finalize",
                        label=template_path,
                        metadata={"handled": False, "decal": bool(is_decal)},
                    )
            return False

        factory_started = begin_material_phase()
        try:
            instance = rule.factory(self, factory_data)
        finally:
            if factory_started is not None:
                end_material_phase(
                    factory_started,
                    "material.factory",
                    label=template_path,
                    metadata={
                        "handler": getattr(rule.factory, "class_name", ""),
                    },
                )

        handler_started = begin_material_phase()
        node_tree = getattr(bpyMat, "node_tree", None) if handler_started is not None else None
        nodes_before = len(node_tree.nodes) if node_tree is not None else 0
        links_before = len(node_tree.links) if node_tree is not None else 0
        try:
            instance.create(create_data, bpyMat)
        finally:
            if handler_started is not None:
                nodes_after = len(node_tree.nodes) if node_tree is not None else nodes_before
                links_after = len(node_tree.links) if node_tree is not None else links_before
                end_material_phase(
                    handler_started,
                    "material.handler_create",
                    label=template_path,
                    metadata={
                        "handler": type(instance).__name__,
                        "decal": bool(is_decal),
                        "nodesAdded": max(0, nodes_after - nodes_before),
                        "linksAdded": max(0, links_after - links_before),
                    },
                )

        finalize_started = begin_material_phase()
        try:
            if not rule.preserve_render_method:
                _set_hashed_render_method(bpyMat)
            if not is_decal:
                bpyMat["no_shadows"] = rule.no_shadows
        finally:
            if finalize_started is not None:
                end_material_phase(
                    finalize_started,
                    "material.finalize",
                    label=template_path,
                    metadata={"handled": True, "decal": bool(is_decal)},
                )
        return True

    def create(self, mats, materialIndex, *, force_rebuild=False):
        if not mats:
            return self.createdecal(
                materialIndex,
                force_rebuild=force_rebuild,
            )

        rawMat = mats[materialIndex]
        signature_started = begin_material_phase()
        rule = self._material_rule(rawMat)
        mesh_path_sensitive = bool(rule and rule.mesh_path_sensitive)
        try:
            signature = self._signature(
                "material",
                rawMat,
                include_name=True,
                mesh_path_sensitive=mesh_path_sensitive,
            )
            prototype_signature = self._signature(
                "material",
                rawMat,
                include_name=False,
                mesh_path_sensitive=mesh_path_sensitive,
            )
        finally:
            if signature_started is not None:
                end_material_phase(
                    signature_started,
                    "material.signature",
                    label=(
                        rawMat.get("Name", "")
                        if isinstance(rawMat, dict)
                        else ""
                    ),
                )

        if not force_rebuild:
            lookup_started = begin_material_phase()
            try:
                cached = _lookup_cached(_MATERIAL_CACHE, signature)
                if cached is not None:
                    _record_exact_hit()
                    return cached

                prototype = _lookup_cached(
                    _MATERIAL_PROTOTYPE_CACHE,
                    prototype_signature,
                )
                if prototype is not None:
                    _record_prototype_hit()
                    material = self._clone_material(
                        prototype,
                        rawMat,
                    )
                    return _cache_material(
                        signature,
                        prototype_signature,
                        material,
                        cloned=True,
                    )
            finally:
                if lookup_started is not None:
                    end_material_phase(
                        lookup_started,
                        "material.cache_lookup",
                        label=(
                            rawMat.get("Name", "")
                            if isinstance(rawMat, dict)
                            else ""
                        ),
                        metadata={
                            "exactHit": (
                                cached is not None if "cached" in locals() else False
                            ),
                            "prototypeHit": (
                                prototype is not None
                                if "prototype" in locals()
                                else False
                            ),
                        },
                    )
        else:
            _MATERIAL_CACHE_STATS["forced_rebuilds"] += 1
            _invalidate_material_signature(signature)

        _MATERIAL_CACHE_STATS["misses"] += 1
        bpyMat = self._new_material(rawMat["Name"])
        try:
            metadata_started = begin_material_phase()
            try:
                self._set_material_source_properties(
                    bpyMat,
                    rawMat,
                )
            finally:
                if metadata_started is not None:
                    end_material_phase(
                        metadata_started,
                        "material.source_metadata",
                        label=(
                            rawMat.get("Name", "")
                            if isinstance(rawMat, dict)
                            else ""
                        ),
                    )

            material_template = rawMat["MaterialTemplate"]
            if self._route_material(
                material_template,
                rawMat,
                rawMat["Data"],
                bpyMat,
                REGISTRY,
                rule=rule,
            ):
                return _cache_material(
                    signature,
                    prototype_signature,
                    bpyMat,
                )

            if self.experimental_features:
                from ...material_types.unknown import unknownMaterial

                unknown = unknownMaterial(
                    self.BasePath,
                    self.image_format,
                    self.ProjPath,
                )
                unknown.create(rawMat["Data"], bpyMat)

            _set_hashed_render_method(bpyMat)
            bpyMat["no_shadows"] = False
            return _cache_material(
                signature,
                prototype_signature,
                bpyMat,
            )
        except Exception:
            self._remove_failed_material(bpyMat)
            raise

    def createdecal(
        self,
        materialIndex,
        *,
        force_rebuild=False,
        cache_identity=None,
    ):
        root = self.obj.get("Data", {}).get("RootChunk", {})
        if not root.get("baseMaterial"):
            return None

        signature_started = begin_material_phase()
        try:
            signature = self.decal_signature(
                root,
                cache_identity=cache_identity,
            )
        finally:
            if signature_started is not None:
                end_material_phase(
                    signature_started,
                    "material.signature",
                    label=self._archive_material_name(),
                    metadata={"decal": True},
                )
        if not force_rebuild:
            lookup_started = begin_material_phase()
            try:
                cached = _lookup_cached(_MATERIAL_CACHE, signature)
                if cached is not None:
                    _record_exact_hit()
                    return cached
            finally:
                if lookup_started is not None:
                    end_material_phase(
                        lookup_started,
                        "material.cache_lookup",
                        label=self._archive_material_name(),
                        metadata={
                            "exactHit": (
                                cached is not None if "cached" in locals() else False
                            ),
                            "decal": True,
                        },
                    )
        else:
            _MATERIAL_CACHE_STATS["forced_rebuilds"] += 1
            _invalidate_material_signature(signature)

        _MATERIAL_CACHE_STATS["misses"] += 1
        bpyMat = self._new_material(self._archive_material_name())
        try:
            metadata_started = begin_material_phase()
            try:
                self._set_material_source_properties(
                    bpyMat,
                    {},
                    include_template=False,
                )
            finally:
                if metadata_started is not None:
                    end_material_phase(
                        metadata_started,
                        "material.source_metadata",
                        label=self._archive_material_name(),
                        metadata={"decal": True},
                    )
            base_path = self._base_material_path(root)
            if base_path:
                self._route_material(
                    base_path,
                    root,
                    root,
                    bpyMat,
                    DECAL_REGISTRY,
                    is_decal=True,
                )
            else:
                print(
                    "Unhandled decal - missing baseMaterial DepotPath"
                )
                _set_hashed_render_method(bpyMat)
            return _cache_material(
                signature,
                signature,
                bpyMat,
            )
        except Exception:
            self._remove_failed_material(bpyMat)
            raise
