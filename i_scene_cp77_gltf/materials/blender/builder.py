import copy
import hashlib
import json
import os
import time
from collections import defaultdict
from functools import lru_cache

import bpy

from ...assetio.paths import absolute_local_path_key, backslash_depot_key
from ...blender.shader_nodes import outputs_detached
from ...blender.transactions import track_created_datablock
from ...core.addon_identity import get_addon_preferences, get_addon_version
from ...core.log import get_logger
from ...material_types.graph import (
    bundle_principled_surface_links,
    organize_material_graph,
    organize_material_groups,
)
from ..parser import base_material_path
from .cache import (
    _MATERIAL_CACHE,
    _MATERIAL_CACHE_STATS,
    _MATERIAL_PROTOTYPE_CACHE,
    _cache_material,
    _invalidate_material_signature,
    _lookup_cached,
    _raw_material_digests,
    _record_exact_hit,
    _record_prototype_hit,
    record_structure_copy,
    remember_structure,
    structure_sharing_active,
    structure_snapshot,
)
from .images import embedded_textures_of, record_material_placeholders
from .profiling import (
    begin_material_phase,
    end_material_phase,
    finish_material_build,
    start_material_build,
)
from .registry import DECAL_REGISTRY, REGISTRY

_LOG = get_logger(__name__)

_MATERIAL_CACHE_VERSION = 55

_MATERIAL_HANDLER_TIMINGS = defaultdict(lambda: [0.0, 0])
_MATERIAL_TEMPLATE_TIMINGS = defaultdict(lambda: [0.0, 0])
_MATERIAL_HANDLER_ORGANIZATION_TIMINGS = defaultdict(lambda: [0.0, 0])
_MATERIAL_TEMPLATE_ORGANIZATION_TIMINGS = defaultdict(lambda: [0.0, 0])
_MATERIAL_ORGANIZATION_PHASE_TIMINGS = defaultdict(float)


def _material_timing_stats(body_timings, organization_timings):
    names = set(body_timings) | set(organization_timings)
    return {
        name: {
            "seconds": float(body_timings.get(name, (0.0, 0))[0]),
            "count": int(body_timings.get(name, (0.0, 0))[1]),
            "organization_seconds": float(organization_timings.get(name, (0.0, 0))[0]),
            "organization_count": int(organization_timings.get(name, (0.0, 0))[1]),
        }
        for name in names
    }


def material_handler_timing_stats():
    return _material_timing_stats(
        _MATERIAL_HANDLER_TIMINGS,
        _MATERIAL_HANDLER_ORGANIZATION_TIMINGS,
    )


def material_template_timing_stats():
    return _material_timing_stats(
        _MATERIAL_TEMPLATE_TIMINGS,
        _MATERIAL_TEMPLATE_ORGANIZATION_TIMINGS,
    )


def material_organization_phase_timing_stats():
    return {
        name: float(seconds)
        for name, seconds in _MATERIAL_ORGANIZATION_PHASE_TIMINGS.items()
    }


def _record_material_organization_phases(timings):
    for name, seconds in (timings or {}).items():
        _MATERIAL_ORGANIZATION_PHASE_TIMINGS[str(name)] += max(0.0, float(seconds))


def _record_material_handler_timing(name, template_path, seconds):
    elapsed = max(0.0, float(seconds))
    handler_name = str(name or "<unknown>")
    values = _MATERIAL_HANDLER_TIMINGS[handler_name]
    values[0] += elapsed
    values[1] += 1
    template_key = f"{handler_name}:{template_path or '<unknown>'!s}"
    values = _MATERIAL_TEMPLATE_TIMINGS[template_key]
    values[0] += elapsed
    values[1] += 1


def _record_material_organization_timing(name, template_path, seconds):
    elapsed = max(0.0, float(seconds))
    handler_name = str(name or "<unknown>")
    values = _MATERIAL_HANDLER_ORGANIZATION_TIMINGS[handler_name]
    values[0] += elapsed
    values[1] += 1
    template_key = f"{handler_name}:{template_path or '<unknown>'!s}"
    values = _MATERIAL_TEMPLATE_ORGANIZATION_TIMINGS[template_key]
    values[0] += elapsed
    values[1] += 1


_BUNDLING_FAILED = {}


def _bundle_surface_links(material):
    """Bundle the principled surface links ahead of the layout (while the build's output is still unlinked)"""
    started = time.perf_counter()
    try:
        stats = bundle_principled_surface_links(material)
    except Exception:
        _LOG.debug(
            "Material graph organization failed for %s",
            getattr(material, "name", "<unnamed>"),
            exc_info=True,
        )
        return _BUNDLING_FAILED
    stats["seconds"] = time.perf_counter() - started
    return stats


def _organize_material_graph(material, bundled=None):
    if bundled is _BUNDLING_FAILED:
        return {}
    try:
        stats = organize_material_graph(material, bundled=bundled)
        if stats.get("cycles") or stats.get("backward_links"):
            _LOG.debug(
                "Material graph layout for %s is not strictly left-to-right: "
                "%d cycle node(s), %d backward link(s)",
                getattr(material, "name", "<unnamed>"),
                int(stats.get("cycles", 0)),
                int(stats.get("backward_links", 0)),
            )
        return stats
    except Exception:
        _LOG.debug(
            "Material graph organization failed for %s",
            getattr(material, "name", "<unnamed>"),
            exc_info=True,
        )
        return {}


_SOURCE_METADATA_KEYS = (
    "BaseMaterial",
    "GlobalNormal",
    "MultilayerMask",
    "DiffuseMap",
    "cp77_source_material_name",
)


@lru_cache(maxsize=4096)
def _project_path_from_mesh(mesh_path):
    before, marker, _ = str(mesh_path).partition("source\\raw\\".replace("\\", os.sep))
    return before + marker if marker else ""


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
            "base_path": absolute_local_path_key(base_path),
            "project_path": absolute_local_path_key(project_path),
            "image_format": str(image_format).lower(),
            "blender_version": tuple(blender_version),
            "addon_version": tuple(addon_version),
            "experimental_features": bool(experimental_features),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _set_dithered_render_method(material):
    material.surface_render_method = "DITHERED"


def _refresh_copied_tree(material):
    """Refresh a copied material's socket availability"""
    tree = getattr(material, "node_tree", None)
    if tree is not None and len(tree.nodes):
        first = tree.nodes[0]
        first.location = first.location.copy()


class MaterialBuilder:
    def __init__(self, obj, BasePath, image_format, MeshPath):
        self.BasePath = BasePath
        self.image_format = image_format
        self.obj = obj
        self.MeshPath = MeshPath
        self.ProjPath = _project_path_from_mesh(MeshPath)
        self.addon_ver = get_addon_version()
        preferences = get_addon_preferences(required=False)
        self.experimental_features = (
            bool(preferences.experimental_features)
            if preferences is not None
            else False
        )
        self._signature_cache = {}
        self._raw_digest_cache = {}
        self._semantic_identity_cache = {}
        self._source_snapshots = {}
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

        raw_identity = id(raw_material)
        raw_digests = self._raw_digest_cache.get(raw_identity)
        if raw_digests is None or raw_digests[0] is not raw_material:
            exact_digest, prototype_digest = _raw_material_digests(raw_material)
            raw_digests = (raw_material, exact_digest, prototype_digest)
            self._raw_digest_cache[raw_identity] = raw_digests

        digest = hashlib.blake2b(digest_size=20)
        digest.update(self._signature_prefix)
        digest.update(b"\0")
        digest.update(str(kind).encode("utf-8"))
        digest.update(b"\0")
        digest.update(raw_digests[1 if include_name else 2].encode("ascii"))
        if mesh_path_sensitive:
            digest.update(b"\0")
            digest.update(absolute_local_path_key(self.MeshPath).encode("utf-8"))
        signature = digest.hexdigest()
        self._signature_cache[cache_key] = signature
        return signature

    def _verify_material_source(self, raw_material):
        """Require source payloads to remain stable during one builder lifetime"""
        identity = id(raw_material)
        stored = self._source_snapshots.get(identity)
        if stored is None or stored[0] is not raw_material:
            self._source_snapshots[identity] = (
                raw_material,
                copy.deepcopy(raw_material),
            )
        elif stored[1] != raw_material:
            raise ValueError(
                "Material source changed during builder lifetime; create a new MaterialBuilder."
            )

    @staticmethod
    def material_rule(raw_material):
        if not isinstance(raw_material, dict):
            return None
        return REGISTRY.resolve(raw_material.get("MaterialTemplate", ""))

    def _material_cache_identity(self, raw_material, rule):
        self._verify_material_source(raw_material)
        if (
            rule is None
            or not rule.semantic_cache_identity
            or not isinstance(raw_material, dict)
        ):
            return raw_material

        raw_id = id(raw_material)
        cached = self._semantic_identity_cache.get(raw_id)
        if cached is not None and cached[0] is raw_material:
            return cached[1]

        identity = rule.factory.cache_identity(raw_material)
        if identity is None:
            identity = raw_material
        self._semantic_identity_cache[raw_id] = (raw_material, identity)
        if identity is raw_material:
            return identity

        _MATERIAL_CACHE_STATS["semantic_identities"] += 1
        raw_data = raw_material.get("Data")
        identity_data = identity.get("Data") if isinstance(identity, dict) else None
        if isinstance(raw_data, dict) and isinstance(identity_data, dict):
            trimmed = max(0, len(raw_data) - len(identity_data))
            if trimmed:
                _MATERIAL_CACHE_STATS["semantic_reduced_materials"] += 1
                _MATERIAL_CACHE_STATS["semantic_trimmed_keys"] += trimmed
        return identity

    def material_signature(self, raw_material):
        rule = self.material_rule(raw_material)
        cache_identity = self._material_cache_identity(raw_material, rule)
        return self._signature(
            "material",
            cache_identity,
            include_name=True,
            mesh_path_sensitive=bool(rule and rule.mesh_path_sensitive),
        )

    def material_prototype_signature(self, raw_material):
        rule = self.material_rule(raw_material)
        cache_identity = self._material_cache_identity(raw_material, rule)
        return self._signature(
            "material",
            cache_identity,
            include_name=False,
            mesh_path_sensitive=bool(rule and rule.mesh_path_sensitive),
        )

    def material_prefetch_indices(self, mats, material_indices):
        """Prefetch dependencies only for graphs that may need construction"""
        pending = []
        pending_prototypes = set()
        for index in material_indices:
            try:
                raw_material = mats[index]
                signature = self.material_signature(raw_material)
                if _lookup_cached(_MATERIAL_CACHE, signature) is not None:
                    continue
                prototype_signature = self.material_prototype_signature(raw_material)
                if prototype_signature in pending_prototypes:
                    continue
                if (
                    _lookup_cached(_MATERIAL_PROTOTYPE_CACHE, prototype_signature)
                    is not None
                ):
                    continue
                pending_prototypes.add(prototype_signature)
            except (IndexError, KeyError, TypeError, ValueError):
                pending.append(index)
                continue
            pending.append(index)
        return tuple(pending)

    def decal_signature(self, root, cache_identity=None):
        self._verify_material_source(root)
        if cache_identity is not None:
            self._verify_material_source(cache_identity)
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
                bsdf.outputs["BSDF"],
                output.inputs["Surface"],
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
        except (ReferenceError, RuntimeError):
            pass

    def archive_material_name(self):
        archive_name = self.obj.get("Header", {}).get("ArchiveFileName")
        return os.path.basename(archive_name) if archive_name else "decal_material"

    def _set_material_source_properties(
        self,
        bpyMat,
        raw_material,
        *,
        include_template=True,
    ):
        bpyMat["sourcePath"] = self.MeshPath
        bpyMat["DepotPath"] = self.BasePath
        bpyMat["cp77_project_path"] = self.ProjPath
        bpyMat["cp77_image_format"] = str(self.image_format)
        bpyMat["cp77_source_material_name"] = raw_material.get("Name", bpyMat.name)
        if include_template:
            bpyMat["MaterialTemplate"] = raw_material["MaterialTemplate"]

    @staticmethod
    def _clear_source_metadata(material):
        for key in _SOURCE_METADATA_KEYS:
            try:
                if key in material:
                    del material[key]
            except ReferenceError:
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
            _refresh_copied_tree(material)
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

    def _structure_key(self, rule, handler, raw_material):
        """The graph shape the handler declares for this material, or None to build it in full"""
        try:
            handler.material_template = backslash_depot_key(
                raw_material.get("MaterialTemplate", "")
            )
            key = handler.structure_key(raw_material["Data"])
        except Exception:
            _LOG.debug(
                "Material shape unavailable for %s; building it in full",
                raw_material.get("Name", ""),
                exc_info=True,
            )
            return None
        if key is None:
            return None
        return (
            self._signature_prefix,
            backslash_depot_key(raw_material.get("MaterialTemplate", "")),
            type(handler).__name__,
            absolute_local_path_key(self.MeshPath) if rule.mesh_path_sensitive else "",
            key,
        )

    def _copy_structure(self, entry, handler, raw_material):
        """A copy of the shape's snapshot carrying this material's own values, or None"""
        snapshot, slots = entry
        started = time.perf_counter()
        material = track_created_datablock("materials", snapshot.copy())
        try:
            material.name = raw_material["Name"]
            self._set_material_source_properties(material, raw_material)
            with outputs_detached(material.node_tree):
                handler.apply_structure_values(raw_material["Data"], material, slots)
                organize_material_groups(material)
                _refresh_copied_tree(material)
        except Exception:
            _LOG.debug(
                "Material %s could not be copied from its shape; building it in full",
                raw_material.get("Name", ""),
                exc_info=True,
            )
            self._remove_failed_material(material)
            return None
        _record_material_handler_timing(
            f"{type(handler).__name__} (shape copy)",
            raw_material.get("MaterialTemplate", ""),
            time.perf_counter() - started,
        )
        record_structure_copy()
        return material

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
        handler=None,
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
            _LOG.warning(
                "Unsupported %s material template %s; a basic fallback graph was used",
                label,
                template_path,
            )
            finalize_started = begin_material_phase()
            try:
                _set_dithered_render_method(bpyMat)
                if not is_decal:
                    bpyMat["cp77_no_shadows"] = False
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
            instance = (
                handler if handler is not None else rule.factory(self, factory_data)
            )
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
        node_tree = (
            getattr(bpyMat, "node_tree", None) if handler_started is not None else None
        )
        nodes_before = len(node_tree.nodes) if node_tree is not None else 0
        links_before = len(node_tree.links) if node_tree is not None else 0
        node_groups_before = (
            len(bpy.data.node_groups) if handler_started is not None else 0
        )
        handler_name = type(instance).__name__
        build_session = start_material_build(
            getattr(bpyMat, "name", ""),
            template_path,
            handler_name,
            decal=is_decal,
        )
        body_seconds = 0.0
        organization_seconds = 0.0
        succeeded = False
        coarse_handler_started = time.perf_counter()
        try:
            body_started = begin_material_phase()
            try:
                # The graph is built and its surface links bundled with the output unlinked, so each edit updates
                # only this material.
                with (
                    outputs_detached(getattr(bpyMat, "node_tree", None)),
                    embedded_textures_of(self.MeshPath),
                ):
                    instance.create(create_data, bpyMat)
                    bundled = _bundle_surface_links(bpyMat)
            finally:
                _record_material_handler_timing(
                    handler_name,
                    template_path,
                    time.perf_counter() - coarse_handler_started,
                )
                body_seconds = end_material_phase(
                    body_started,
                    "material.handler_body",
                    label=template_path,
                    metadata={
                        "handler": handler_name,
                        "material": getattr(bpyMat, "name", ""),
                    },
                )
            organization_started = begin_material_phase()
            coarse_organization_started = time.perf_counter()
            organization_stats = {}
            try:
                organization_stats = _organize_material_graph(bpyMat, bundled)
            finally:
                _record_material_organization_phases(
                    organization_stats.get("timings", {})
                )
                _record_material_organization_timing(
                    handler_name,
                    template_path,
                    time.perf_counter() - coarse_organization_started,
                )
                organization_seconds = end_material_phase(
                    organization_started,
                    "material.graph_organization",
                    label=template_path,
                    metadata={
                        "handler": handler_name,
                        "material": getattr(bpyMat, "name", ""),
                    },
                )
            succeeded = True
        finally:
            if handler_started is not None:
                nodes_after = (
                    len(node_tree.nodes) if node_tree is not None else nodes_before
                )
                links_after = (
                    len(node_tree.links) if node_tree is not None else links_before
                )
                node_groups_after = len(bpy.data.node_groups)
                handler_seconds = end_material_phase(
                    handler_started,
                    "material.handler_create",
                    label=template_path,
                    metadata={
                        "handler": handler_name,
                        "material": getattr(bpyMat, "name", ""),
                        "decal": bool(is_decal),
                        "nodesAdded": max(0, nodes_after - nodes_before),
                        "linksAdded": max(0, links_after - links_before),
                        "nodeGroupsAdded": max(
                            0,
                            node_groups_after - node_groups_before,
                        ),
                    },
                )
                finish_material_build(
                    build_session,
                    seconds=handler_seconds,
                    body_seconds=body_seconds,
                    organization_seconds=organization_seconds,
                    nodes_added=max(0, nodes_after - nodes_before),
                    links_added=max(0, links_after - links_before),
                    node_groups_added=max(
                        0,
                        node_groups_after - node_groups_before,
                    ),
                    succeeded=succeeded,
                )

        finalize_started = begin_material_phase()
        try:
            if not rule.preserve_render_method:
                _set_dithered_render_method(bpyMat)
            if not is_decal:
                bpyMat["cp77_no_shadows"] = rule.no_shadows
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
        rule = self.material_rule(rawMat)
        mesh_path_sensitive = bool(rule and rule.mesh_path_sensitive)
        cache_identity = self._material_cache_identity(rawMat, rule)
        try:
            signature = self._signature(
                "material",
                cache_identity,
                include_name=True,
                mesh_path_sensitive=mesh_path_sensitive,
            )
            prototype_signature = self._signature(
                "material",
                cache_identity,
                include_name=False,
                mesh_path_sensitive=mesh_path_sensitive,
            )
        finally:
            if signature_started is not None:
                end_material_phase(
                    signature_started,
                    "material.signature",
                    label=(rawMat.get("Name", "") if isinstance(rawMat, dict) else ""),
                )

        if not force_rebuild:
            lookup_started = begin_material_phase()
            cached = prototype = None
            try:
                cached = _lookup_cached(_MATERIAL_CACHE, signature)
                if cached is not None:
                    _record_exact_hit()
                    record_material_placeholders(cached)
                    return cached

                prototype = _lookup_cached(
                    _MATERIAL_PROTOTYPE_CACHE,
                    prototype_signature,
                )
                if prototype is not None:
                    _record_prototype_hit()
                    record_material_placeholders(prototype)
                    material = self._clone_material(
                        prototype,
                        rawMat,
                    )
                    material = _cache_material(
                        signature,
                        prototype_signature,
                        material,
                        cloned=True,
                    )
                    return material
            finally:
                if lookup_started is not None:
                    end_material_phase(
                        lookup_started,
                        "material.cache_lookup",
                        label=(
                            rawMat.get("Name", "") if isinstance(rawMat, dict) else ""
                        ),
                        metadata={
                            "exactHit": cached is not None,
                            "prototypeHit": prototype is not None,
                        },
                    )
        else:
            _MATERIAL_CACHE_STATS["forced_rebuilds"] += 1
            _invalidate_material_signature(signature)

        _MATERIAL_CACHE_STATS["misses"] += 1
        handler = rule.factory(self, rawMat) if rule is not None else None
        structure_key = None
        if handler is not None and not force_rebuild and structure_sharing_active():
            structure_key = self._structure_key(rule, handler, rawMat)
            entry = (
                structure_snapshot(structure_key) if structure_key is not None else None
            )
            if entry is not None:
                copied = self._copy_structure(entry, handler, rawMat)
                if copied is not None:
                    return _cache_material(
                        signature, prototype_signature, copied, cloned=True
                    )
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
                            rawMat.get("Name", "") if isinstance(rawMat, dict) else ""
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
                handler=handler,
            ):
                if structure_key is not None:
                    remember_structure(structure_key, bpyMat, handler.structure_slots)
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

            _organize_material_graph(bpyMat)
            _set_dithered_render_method(bpyMat)
            bpyMat["cp77_no_shadows"] = False
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
                    label=self.archive_material_name(),
                    metadata={"decal": True},
                )
        if not force_rebuild:
            lookup_started = begin_material_phase()
            cached = None
            try:
                cached = _lookup_cached(_MATERIAL_CACHE, signature)
                if cached is not None:
                    _record_exact_hit()
                    record_material_placeholders(cached)
                    return cached
            finally:
                if lookup_started is not None:
                    end_material_phase(
                        lookup_started,
                        "material.cache_lookup",
                        label=self.archive_material_name(),
                        metadata={
                            "exactHit": cached is not None,
                            "decal": True,
                        },
                    )
        else:
            _MATERIAL_CACHE_STATS["forced_rebuilds"] += 1
            _invalidate_material_signature(signature)

        _MATERIAL_CACHE_STATS["misses"] += 1
        bpyMat = self._new_material(self.archive_material_name())
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
                        label=self.archive_material_name(),
                        metadata={"decal": True},
                    )
            base_path = base_material_path(root)
            if base_path:
                bpyMat["MaterialTemplate"] = base_path
                self._route_material(
                    base_path,
                    root,
                    root,
                    bpyMat,
                    DECAL_REGISTRY,
                    is_decal=True,
                )
            else:
                _LOG.warning("Unhandled decal - missing baseMaterial DepotPath")
                _organize_material_graph(bpyMat)
                _set_dithered_render_method(bpyMat)
            return _cache_material(
                signature,
                signature,
                bpyMat,
            )
        except Exception:
            self._remove_failed_material(bpyMat)
            raise
