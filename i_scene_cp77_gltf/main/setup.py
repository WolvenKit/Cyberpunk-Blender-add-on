import hashlib
import json
import os
import sys
from collections import OrderedDict

import bpy

from .material_registry import DECAL_REGISTRY, REGISTRY
from .material_profile import begin_material_phase, end_material_phase
from ..material_types.multilayered import clear_multilayer_cache, multilayer_cache_stats
from ..material_types.mat_common import clear_decal_helper_caches, decal_helper_cache_stats
from ..material_types.unknown import unknownMaterial

_MATERIAL_SIGNATURE_PROP = "_cp77_material_signature"
_MATERIAL_PROTOTYPE_SIGNATURE_PROP = "_cp77_material_prototype_signature"
_MATERIAL_CACHE_VERSION = 2
_MATERIAL_CACHE = {}
_MATERIAL_PROTOTYPE_CACHE = {}
_MATERIAL_CACHE_INDEXED = False
_MATERIAL_CACHE_STATS = {
    "hits": 0,
    "exact_hits": 0,
    "prototype_hits": 0,
    "misses": 0,
    "builds": 0,
    "clones": 0,
    "forced_rebuilds": 0,
    "indexed": 0,
    "prototype_indexed": 0,
    "stale": 0,
}
_RAW_MATERIAL_DIGEST_CACHE = OrderedDict()
_RAW_MATERIAL_DIGEST_CACHE_LIMIT = 4096
_SOURCE_METADATA_KEYS = (
    "m",
    "BaseMaterial",
    "GlobalNormal",
    "MultilayerMask",
    "DiffuseMap",
)


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


def _context_path_key(path):
    if not path:
        return ""
    return os.path.normcase(os.path.abspath(os.path.normpath(str(path))))


def _material_is_live(material):
    if material is None:
        return False
    try:
        return bpy.data.materials.get(material.name) is material
    except (AttributeError, ReferenceError, TypeError):
        return False


def _prefer_material(cache, signature, material):
    current = cache.get(signature)
    if current is None or not _material_is_live(current):
        cache[signature] = material
        return True
    try:
        if material.users > current.users:
            cache[signature] = material
    except (AttributeError, ReferenceError, TypeError):
        pass
    return False


def _ensure_material_cache_indexed():
    global _MATERIAL_CACHE_INDEXED
    if _MATERIAL_CACHE_INDEXED:
        return

    indexed = 0
    prototype_indexed = 0
    for material in bpy.data.materials:
        try:
            signature = material.get(_MATERIAL_SIGNATURE_PROP)
            prototype_signature = material.get(
                _MATERIAL_PROTOTYPE_SIGNATURE_PROP
            )
        except (AttributeError, ReferenceError, TypeError):
            continue

        if isinstance(signature, str) and signature:
            indexed += int(_prefer_material(
                _MATERIAL_CACHE,
                signature,
                material,
            ))
        if isinstance(prototype_signature, str) and prototype_signature:
            prototype_indexed += int(_prefer_material(
                _MATERIAL_PROTOTYPE_CACHE,
                prototype_signature,
                material,
            ))

    _MATERIAL_CACHE_STATS["indexed"] += indexed
    _MATERIAL_CACHE_STATS["prototype_indexed"] += prototype_indexed
    _MATERIAL_CACHE_INDEXED = True


def _lookup_cached(cache, signature):
    global _MATERIAL_CACHE_INDEXED
    _ensure_material_cache_indexed()
    material = cache.get(signature)
    if _material_is_live(material):
        return material
    if material is None:
        return None

    cache.pop(signature, None)
    _MATERIAL_CACHE_STATS["stale"] += 1
    _MATERIAL_CACHE_INDEXED = False
    _ensure_material_cache_indexed()
    material = cache.get(signature)
    return material if _material_is_live(material) else None


def _record_exact_hit():
    _MATERIAL_CACHE_STATS["hits"] += 1
    _MATERIAL_CACHE_STATS["exact_hits"] += 1


def _record_prototype_hit():
    _MATERIAL_CACHE_STATS["hits"] += 1
    _MATERIAL_CACHE_STATS["prototype_hits"] += 1


def _invalidate_material_signature(signature):
    _MATERIAL_CACHE.pop(signature, None)
    for material in bpy.data.materials:
        try:
            if material.get(_MATERIAL_SIGNATURE_PROP) == signature:
                del material[_MATERIAL_SIGNATURE_PROP]
        except (AttributeError, ReferenceError, TypeError):
            pass


def _cache_material(
    signature,
    prototype_signature,
    material,
    *,
    cloned=False,
):
    started = begin_material_phase()
    try:
        material[_MATERIAL_SIGNATURE_PROP] = signature
        material[_MATERIAL_PROTOTYPE_SIGNATURE_PROP] = prototype_signature
        _MATERIAL_CACHE[signature] = material
        _MATERIAL_PROTOTYPE_CACHE[prototype_signature] = material
        _MATERIAL_CACHE_STATS["clones" if cloned else "builds"] += 1
        return material
    finally:
        if started is not None:
            end_material_phase(
                started,
                "material.cache_store",
                label=getattr(material, "name", ""),
                metadata={"cloned": bool(cloned)},
            )


def _raw_material_digest(raw_material, *, include_name):
    cache_key = (id(raw_material), bool(include_name))
    cached = _RAW_MATERIAL_DIGEST_CACHE.get(cache_key)
    if cached is not None and cached[0] is raw_material:
        _RAW_MATERIAL_DIGEST_CACHE.move_to_end(cache_key)
        return cached[1]

    value = raw_material
    if not include_name and isinstance(raw_material, dict):
        value = {
            key: item
            for key, item in raw_material.items()
            if key != "Name"
        }
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    digest = hashlib.blake2b(encoded, digest_size=20).hexdigest()
    _RAW_MATERIAL_DIGEST_CACHE[cache_key] = (raw_material, digest)
    _RAW_MATERIAL_DIGEST_CACHE.move_to_end(cache_key)
    while len(_RAW_MATERIAL_DIGEST_CACHE) > _RAW_MATERIAL_DIGEST_CACHE_LIMIT:
        _RAW_MATERIAL_DIGEST_CACHE.popitem(last=False)
    return digest


def reset_material_cache_stats():
    for key in _MATERIAL_CACHE_STATS:
        _MATERIAL_CACHE_STATS[key] = 0


def clear_material_cache(
    *,
    clear_persistent=True,
    reset_stats=True,
    clear_helpers=True,
):
    """Clear transient lookup state without necessarily erasing telemetry or live signatures."""
    global _MATERIAL_CACHE_INDEXED
    _MATERIAL_CACHE.clear()
    _MATERIAL_PROTOTYPE_CACHE.clear()
    _RAW_MATERIAL_DIGEST_CACHE.clear()
    _MATERIAL_CACHE_INDEXED = False

    if reset_stats:
        reset_material_cache_stats()
    if clear_helpers:
        clear_multilayer_cache()
        clear_decal_helper_caches()

    if not clear_persistent:
        return
    for material in bpy.data.materials:
        try:
            for property_name in (
                _MATERIAL_SIGNATURE_PROP,
                _MATERIAL_PROTOTYPE_SIGNATURE_PROP,
            ):
                if property_name in material:
                    del material[property_name]
        except (AttributeError, ReferenceError, TypeError):
            pass


def warm_material_cache_index():
    """Index signature-tagged Blender materials for persistent cache reuse."""
    before_exact = len(_MATERIAL_CACHE)
    before_prototypes = len(_MATERIAL_PROTOTYPE_CACHE)
    _ensure_material_cache_indexed()
    return {
        "exact_entries_added": max(0, len(_MATERIAL_CACHE) - before_exact),
        "prototype_entries_added": max(
            0,
            len(_MATERIAL_PROTOTYPE_CACHE) - before_prototypes,
        ),
        "indexed": bool(_MATERIAL_CACHE_INDEXED),
    }


def material_cache_stats():
    return {
        **_MATERIAL_CACHE_STATS,
        "entries": sum(
            1
            for material in _MATERIAL_CACHE.values()
            if _material_is_live(material)
        ),
        "prototype_entries": sum(
            1
            for material in _MATERIAL_PROTOTYPE_CACHE.values()
            if _material_is_live(material)
        ),
        "raw_digests": len(_RAW_MATERIAL_DIGEST_CACHE),
        "multilayer": multilayer_cache_stats(),
        "decal_helpers": decal_helper_cache_stats(),
    }


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class MaterialBuilder:
    def __init__(self, obj, BasePath, image_format, MeshPath):
        self.BasePath = BasePath
        self.image_format = image_format
        self.obj = obj
        self.MeshPath = MeshPath
        before, mid, _ = MeshPath.partition(
            "source\\raw\\".replace("\\", os.sep)
        )
        self.ProjPath = before + mid
        self.addon_module = sys.modules["i_scene_cp77_gltf"]
        self.addon_ver = self.addon_module.bl_info["version"]
        try:
            self.experimental_features = bool(
                bpy.context.preferences.addons[
                    __name__.split(".")[0]
                ].preferences.experimental_features
            )
        except Exception:
            self.experimental_features = False
        self._signature_cache = {}
        self._signature_prefix = json.dumps(
            {
                "cache_version": _MATERIAL_CACHE_VERSION,
                "base_path": _context_path_key(self.BasePath),
                "project_path": _context_path_key(self.ProjPath),
                "image_format": str(self.image_format).lower(),
                "blender_version": tuple(bpy.app.version),
                "addon_version": tuple(self.addon_ver),
                "experimental_features": self.experimental_features,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

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
                _context_path_key(self.MeshPath).encode("utf-8")
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
            end_material_phase(
                started,
                "material.default_graph",
                label=getattr(bpyMat, "name", ""),
                metadata={"created": created, "nodesAdded": 2 if created else 0, "linksAdded": 1 if created else 0},
            )

    def _new_material(self, name):
        started = begin_material_phase()
        bpyMat = None
        try:
            bpyMat = bpy.data.materials.new(name)
            self._ensure_nodes(bpyMat)
            return bpyMat
        finally:
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
            material = prototype.copy()
            material.name = raw_material["Name"]
            self._clear_source_metadata(material)
            self._set_material_source_properties(
                material,
                raw_material,
            )
            return material
        finally:
            end_material_phase(
                started,
                "material.datablock_clone",
                label=raw_material.get("Name", "") if isinstance(raw_material, dict) else "",
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
    ):
        lookup_started = begin_material_phase()
        rule = registry.resolve(template_path)
        end_material_phase(
            lookup_started,
            "material.registry_lookup",
            label=template_path,
            metadata={"resolved": rule is not None, "decal": bool(is_decal)},
        )
        if not rule:
            label = "decal" if is_decal else "mt"
            print(
                f"{bcolors.WARNING}Unhandled {label} - "
                f"{template_path}{bcolors.ENDC}"
            )
            finalize_started = begin_material_phase()
            try:
                _set_hashed_render_method(bpyMat)
                if not is_decal:
                    bpyMat["no_shadows"] = False
            finally:
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
            end_material_phase(
                factory_started,
                "material.factory",
                label=template_path,
                metadata={"handler": getattr(getattr(rule, "factory", None), "__name__", "")},
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
        try:
            signature = self.material_signature(rawMat)
            prototype_signature = self.material_prototype_signature(rawMat)
        finally:
            end_material_phase(
                signature_started,
                "material.signature",
                label=rawMat.get("Name", "") if isinstance(rawMat, dict) else "",
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
                end_material_phase(
                    lookup_started,
                    "material.cache_lookup",
                    label=rawMat.get("Name", "") if isinstance(rawMat, dict) else "",
                    metadata={
                        "exactHit": cached is not None if 'cached' in locals() else False,
                        "prototypeHit": prototype is not None if 'prototype' in locals() else False,
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
                end_material_phase(
                    metadata_started,
                    "material.source_metadata",
                    label=rawMat.get("Name", "") if isinstance(rawMat, dict) else "",
                )

            material_template = rawMat["MaterialTemplate"]
            if self._route_material(
                material_template,
                rawMat,
                rawMat["Data"],
                bpyMat,
                REGISTRY,
            ):
                return _cache_material(
                    signature,
                    prototype_signature,
                    bpyMat,
                )

            if self.experimental_features:
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
                end_material_phase(
                    lookup_started,
                    "material.cache_lookup",
                    label=self._archive_material_name(),
                    metadata={"exactHit": cached is not None if 'cached' in locals() else False, "decal": True},
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
                    f"{bcolors.WARNING}Unhandled decal - missing "
                    f"baseMaterial DepotPath{bcolors.ENDC}"
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

