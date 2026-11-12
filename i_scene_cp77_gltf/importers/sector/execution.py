import hashlib
import json
import logging
import os
import re
import time
from bisect import bisect_right
from contextlib import contextmanager
from dataclasses import dataclass, replace
from functools import partial

import bpy
from mathutils import Matrix, Quaternion, Vector

from ...assetio.paths import local_path_key, same_local_path
from ...assetio.streaming_sector import COOKED_PLAIN_TYPES
from ...assetio.values import cname_text, coerce_int, json_array
from ...bartmoss.matrix import flatten_matrix, matrix_is_identity
from ...blender.identity import rna_identity, rna_is_live
from ...blender.matrix import instance_matrix, object_world_matrix
from ...blender.mesh import is_preview_only_modifier
from ...blender.naming import fit_id_name
from ...blender.physics.actors import prune_actor_registry
from ...blender.shader_nodes import remove_unused_shading
from ...blender.transactions import (
    BlenderImportTransaction,
    child_import_savepoint,
    current_import_transaction,
    raise_if_rollback_incomplete,
    rollback_import_child,
    rollback_report_message,
    track_collection_state,
    track_created_datablock,
    track_mutation,
)
from ...core.addon_identity import get_addon_preferences
from ...core.log import (
    LogLimiter,
    debug_exception,
    get_logger,
    is_enabled,
    log_once,
    operation,
)
from ...materials.blender.images import (
    clear_image_load_failures,
    consume_image_load_failures,
    image_load_failure_message,
)
from ...materials.blender.multilayer import override_palette_batched
from ...materials.blender.profiling import (
    material_profile_details,
    material_profile_phase,
    material_profile_total,
)
from ..common.cache import acquire_material_cache, release_material_cache
from ..common.light_channels import (
    clear_light_channel_records,
    is_light_channel_volume,
    rebuild_light_channel_links,
    retire_light_channel_volumes,
    stored_light_channel_records,
)
from ..common.paths import depot_path
from ..common.progress import NO_PROGRESS, BlenderImportProgress
from ..common.reflection_probe_registry import mark_registered_reflection_probes_dirty
from ..common.results import ImportResult, unique_messages
from ..entity.transforms import (
    clear_pending_child_of_inverse_requests,
    flush_pending_child_of_inverse_requests,
    pending_child_of_inverse_count,
    request_child_of_inverse,
)
from .context import (
    SectorContentError,
    SectorExecutionContext,
    SectorNodeContext,
    SectorPlacementOperations,
)
from .model import PlacedContent
from .objects import (
    NodePropertyAssigner,
    assign_id_properties,
    copy_object,
    new_empty,
    node_records,
)
from .options import COLLISION_CHOICES, PROXY_NODE_TYPES
from .planner import exclude_placed_entries
from .registry import NODE_HANDLERS
from .services.decal_projection import COMPOSITE_BUILD_PROFILE_DEFAULTS
from .session import SectorImportSession

_LOG = get_logger(__name__)

_REPLACED_NAME_PREFIX = "[replaced] "
_SUPERSEDED_NAME_PREFIX = "[superseded] "
# Collections with more children than this have them unlinked while replaced content is deleted.
_WIDE_COLLECTION = 64


_FLAT_STATIC_NODE_TYPES = frozenset(
    {
        "worldStaticMeshNode",
        "worldAdvertisingNode",
        "worldAdvertisementNode",
        "worldStaticOccluderMeshNode",
        "worldTerrainMeshNode",
        "worldDecorationMeshNode",
        "worldMeshNode",
        "worldWaterPatchNode",
        "worldBuildingProxyMeshNode",
        "worldGenericProxyMeshNode",
        "worldTerrainProxyMeshNode",
        "worldRoadProxyMeshNode",
    }
)
# The placement timings and counts the debug summary reports, each at its starting value.
_PLACEMENT_PERF_DEFAULTS = {
    **{
        f"decal_material_{key}": value
        for key, value in COMPOSITE_BUILD_PROFILE_DEFAULTS.items()
    },
    "blueprint_builds": 0,
    "blueprint_hits": 0,
    "lean_collections": 0,
    "lean_objects": 0,
    "full_collections": 0,
    "child_of_inverse_updates": 0,
    "child_of_inverse_flushes": 0,
    "child_of_inverse_flush_elapsed": 0.0,
    "child_of_inverse_pending_after_flush": 0,
    "child_of_inverse_transform_mismatches": 0,
    "child_of_inverse_max_translation_error": 0.0,
    "child_of_inverse_max_basis_error": 0.0,
    "flat_groups": 0,
    "flat_single_groups": 0,
    "flat_multi_groups": 0,
    "flat_objects": 0,
    "flat_elapsed": 0.0,
    "handler_elapsed": 0.0,
    "decal_elapsed": 0.0,
    "decal_receiver_scan": 0.0,
    "decal_triangle_collect": 0.0,
    "decal_patch_build": 0.0,
    "decal_patch_geometry": 0.0,
    "decal_geometry_setup": 0.0,
    "decal_geometry_classification": 0.0,
    "decal_geometry_full_emit": 0.0,
    "decal_geometry_full_projection": 0.0,
    "decal_geometry_full_geometry": 0.0,
    "decal_geometry_full_attributes": 0.0,
    "decal_geometry_full_material": 0.0,
    "decal_geometry_boundary_clip": 0.0,
    "decal_geometry_boundary_select": 0.0,
    "decal_geometry_boundary_box_clip": 0.0,
    "decal_geometry_boundary_scalar_clip": 0.0,
    "decal_geometry_boundary_triangulate": 0.0,
    "decal_geometry_boundary_chunk_merge": 0.0,
    "decal_geometry_boundary_material": 0.0,
    "decal_geometry_boundary_emit": 0.0,
    "decal_geometry_boundary_assemble": 0.0,
    "decal_geometry_boundary_surface_eval": 0.0,
    "decal_geometry_boundary_geometry": 0.0,
    "decal_geometry_boundary_attributes": 0.0,
    "decal_material_index_calls": 0,
    "decal_material_overlay_calls": 0,
    "decal_material_resolved_hits": 0,
    "decal_material_resolved_misses": 0,
    "decal_material_pointer_hits": 0,
    "decal_material_pointer_misses": 0,
    "decal_material_pointer_miss_seconds": 0.0,
    "decal_material_receiver_only_resolutions": 0,
    "decal_material_composite_calls": 0,
    "decal_material_composite_cache_hits": 0,
    "decal_material_composite_cache_misses": 0,
    "decal_material_composite_hit_seconds": 0.0,
    "decal_material_composite_miss_seconds": 0.0,
    "decal_material_composite_none": 0,
    "decal_material_fallback_calls": 0,
    "decal_material_fallback_seconds": 0.0,
    "decal_material_slot_hits": 0,
    "decal_material_slot_misses": 0,
    "decal_surface_commit": 0.0,
    "decal_receiver_count": 0,
    "decal_unique_meshes": 0,
    "decal_array_cache_hits": 0,
    "decal_array_cache_misses": 0,
    "decal_source_triangles": 0,
    "decal_candidate_triangles": 0,
    "decal_triangle_projector_matches": 0,
    "decal_oriented_bounds_rejected": 0,
    "decal_triangle_batches": 0,
    "decal_surface_objects": 0,
    "decal_fully_inside_triangles": 0,
    "decal_boundary_clipped_triangles": 0,
    "decal_fast_volume_rejected": 0,
    "validation_elapsed": 0.0,
    "organization_elapsed": 0.0,
}
_PLACEMENT_PERF = dict(_PLACEMENT_PERF_DEFAULTS)
_PLACEMENT_HANDLER_PERF = {}
# The timings (seconds) and the metrics a sector's decal projection summary carries; each adds to the placement
# total of its name with "decal_" before it.
_DECAL_TIMINGS = (
    "receiver_scan",
    "triangle_collect",
    "patch_build",
    "patch_geometry",
    *(
        f"geometry_{part}"
        for part in (
            "setup",
            "classification",
            "full_emit",
            "full_projection",
            "full_geometry",
            "full_attributes",
            "full_material",
            "boundary_clip",
            "boundary_select",
            "boundary_box_clip",
            "boundary_scalar_clip",
            "boundary_triangulate",
            "boundary_chunk_merge",
            "boundary_material",
            "boundary_emit",
            "boundary_assemble",
            "boundary_surface_eval",
            "boundary_geometry",
            "boundary_attributes",
        )
    ),
    "surface_commit",
)
_DECAL_METRICS = (
    *(
        f"material_{name}"
        for name in (
            "index_calls",
            "overlay_calls",
            "resolved_hits",
            "resolved_misses",
            "pointer_hits",
            "pointer_misses",
            "pointer_miss_seconds",
            "receiver_only_resolutions",
            "composite_calls",
            "composite_cache_hits",
            "composite_cache_misses",
            "composite_hit_seconds",
            "composite_miss_seconds",
            "composite_none",
            "fallback_calls",
            "fallback_seconds",
            "slot_hits",
            "slot_misses",
            *COMPOSITE_BUILD_PROFILE_DEFAULTS,
        )
    ),
    "receiver_count",
    "unique_meshes",
    "array_cache_hits",
    "array_cache_misses",
    "source_triangles",
    "candidate_triangles",
    "triangle_projector_matches",
    "oriented_bounds_rejected",
    "triangle_batches",
    "surface_objects",
    "fully_inside_triangles",
    "boundary_clipped_triangles",
    "fast_volume_rejected",
)


def _reset_placement_perf():
    _PLACEMENT_PERF.update(_PLACEMENT_PERF_DEFAULTS)
    _PLACEMENT_HANDLER_PERF.clear()


@contextmanager
def _timed(key):
    """Add the time the block takes to the placement total key"""
    started = time.perf_counter()
    try:
        yield
    finally:
        _PLACEMENT_PERF[key] += time.perf_counter() - started


def _add_decal_summary(summary):
    """Add a sector's decal projection timings and metrics to the placement totals"""
    timings = summary.get("timings", {})
    metrics = summary.get("projection_metrics", {})
    for name in _DECAL_TIMINGS:
        _PLACEMENT_PERF[f"decal_{name}"] += float(timings.get(name, 0.0))
    for name in _DECAL_METRICS:
        key = f"decal_{name}"
        _PLACEMENT_PERF[key] += type(_PLACEMENT_PERF_DEFAULTS[key])(
            metrics.get(name, 0)
        )


def _add_handler_time(plan, elapsed):
    """Add a node handler's time to the placement totals, and to those of its handler and node type"""
    _PLACEMENT_PERF["handler_elapsed"] += elapsed
    stats = _PLACEMENT_HANDLER_PERF.setdefault(
        f"{plan.handler_name}:{plan.node.node_type}", [0.0, 0, 0]
    )
    stats[0] += elapsed
    stats[1] += 1
    stats[2] += len(plan.node.instances)


def _log_parts(label, total, parts, note=""):
    """Log at DEBUG how total seconds of label divide into the named parts, and what they leave"""
    _LOG.debug(
        "%s timing: %s, residual=%.3fs%s",
        label,
        ", ".join(f"{name}={seconds:.3f}s" for name, seconds in parts),
        max(0.0, total - sum(seconds for _name, seconds in parts)),
        note,
    )


def _log_decal_material_profile_details(profile):
    details = material_profile_details(profile)
    for section, label in (
        ("handlers", "handler"),
        ("templates", "template"),
    ):
        rows = sorted(
            details.get(section, {}).items(),
            key=lambda item: float(item[1].get("seconds", 0.0)),
            reverse=True,
        )
        for name, values in rows:
            _LOG.debug(
                "Decal material %s aggregate: name=%s total=%.3fs/%d, "
                "body=%.3fs, organization=%.3fs, residual=%.3fs, "
                "nodes=%.3fs/%d, links=%.3fs/%d, images=%.3fs, "
                "cold_groups=%.3fs/%d",
                label,
                name,
                float(values.get("seconds", 0.0)),
                int(values.get("count", 0)),
                float(values.get("body_seconds", 0.0)),
                float(values.get("organization_seconds", 0.0)),
                float(values.get("residual_seconds", 0.0)),
                float(values.get("node_seconds", 0.0)),
                int(values.get("nodes_added", 0)),
                float(values.get("link_seconds", 0.0)),
                int(values.get("links_added", 0)),
                float(values.get("image_seconds", 0.0)),
                float(values.get("node_group_seconds", 0.0)),
                int(values.get("node_groups_added", 0)),
            )
    for name, values in sorted(
        details.get("node_groups", {}).items(),
        key=lambda item: float(item[1].get("seconds", 0.0)),
        reverse=True,
    ):
        _LOG.debug(
            "Decal material node-group cold build: name=%s total=%.3fs/%d, "
            "maximum=%.3fs",
            name,
            float(values.get("seconds", 0.0)),
            int(values.get("count", 0)),
            float(values.get("maximum", 0.0)),
        )
    slowest = details.get("slowest_builds", ())
    for index, build in enumerate(slowest, start=1):
        _LOG.debug(
            "Slow decal material build %d/%d: material=%s, template=%s, "
            "handler=%s, total=%.3fs, body=%.3fs, organization=%.3fs, "
            "residual=%.3fs, nodes=%.3fs/%d, links=%.3fs/%d, "
            "images=%.3fs, cold_groups=%.3fs/%d, status=%s",
            index,
            len(slowest),
            build.get("material", ""),
            build.get("template", ""),
            build.get("handler", ""),
            float(build.get("seconds", 0.0)),
            float(build.get("body_seconds", 0.0)),
            float(build.get("organization_seconds", 0.0)),
            float(build.get("residual_seconds", 0.0)),
            float(build.get("node_seconds", 0.0)),
            int(build.get("nodes_added", 0)),
            float(build.get("link_seconds", 0.0)),
            int(build.get("links_added", 0)),
            float(build.get("image_seconds", 0.0)),
            float(build.get("node_group_seconds", 0.0)),
            int(build.get("node_groups_added", 0)),
            "ok" if build.get("succeeded", False) else "failed",
        )


def _log_decal_debug_timings(cache_stats):
    timings = cache_stats.get("timings", {})
    object_placement = sum(
        timings.get(phase, 0.0)
        for phase in (
            "projector_create",
            "surface_placement",
            "placement_metadata",
        )
    )
    _LOG.debug(
        "Decal debug timing: dependency_resolution=%.3fs, "
        "material_cache_lookup=%.3fs, descriptor_load=%.3fs, "
        "material_variant=%.3fs, material_build=%.3fs, "
        "material_finalize=%.3fs, object_placement=%.3fs "
        "(projectors=%.3fs, surfaces=%.3fs, metadata=%.3fs)",
        timings.get("dependency_resolution", 0.0),
        timings.get("material_cache_lookup", 0.0),
        timings.get("descriptor_load", 0.0),
        timings.get("material_variant", 0.0),
        timings.get("material_build", 0.0),
        timings.get("material_finalize", 0.0),
        object_placement,
        timings.get("projector_create", 0.0),
        timings.get("surface_placement", 0.0),
        timings.get("placement_metadata", 0.0),
    )
    profile = cache_stats.get("material_profile", {})
    if not profile:
        return
    details = material_profile_details(profile)
    sampled = any(
        int(values.get("count", 0)) > 0
        for phase, values in profile.items()
        if phase != "__material_builds__" and isinstance(values, dict)
    )
    sampled = sampled or bool(details.get("slowest_builds"))
    if not sampled:
        return
    signature = material_profile_phase(profile, "material.signature")
    cache_lookup = material_profile_phase(profile, "material.cache_lookup")
    registry = material_profile_phase(profile, "material.registry_lookup")
    factory = material_profile_phase(profile, "material.factory")
    handler = material_profile_phase(profile, "material.handler_create")
    handler_body = material_profile_phase(profile, "material.handler_body")
    organization = material_profile_phase(
        profile,
        "material.graph_organization",
    )
    nodes = material_profile_phase(profile, "material.node_create")
    links = material_profile_phase(profile, "material.link_create")
    node_groups = material_profile_phase(
        profile,
        "material.node_group_cold_build",
    )
    image_lookup = material_profile_phase(profile, "material.image_lookup")
    image_resolve = material_profile_phase(profile, "material.image_resolve")
    image_load = material_profile_phase(profile, "material.image_create")
    _LOG.debug(
        "Decal material debug timing: signatures=%.3fs/%d, "
        "cache_lookup=%.3fs/%d, shader_routing=%.3fs/%d, "
        "handler_graph=%.3fs/%d (body=%.3fs, organization=%.3fs, "
        "residual=%.3fs), node_create=%.3fs/%d, "
        "link_create=%.3fs/%d, "
        "node_group_cold=%.3fs/%d, "
        "image_lookup=%.3fs/%d, image_resolve=%.3fs/%d, "
        "image_load=%.3fs/%d; maxima handler=%.3fs, image_load=%.3fs",
        signature[0],
        signature[1],
        cache_lookup[0],
        cache_lookup[1],
        registry[0] + factory[0],
        registry[1] + factory[1],
        handler[0],
        handler[1],
        handler_body[0],
        organization[0],
        material_profile_total(
            details,
            "residual_seconds",
        ),
        nodes[0],
        nodes[1],
        links[0],
        links[1],
        node_groups[0],
        node_groups[1],
        image_lookup[0],
        image_lookup[1],
        image_resolve[0],
        image_resolve[1],
        image_load[0],
        image_load[1],
        handler[2],
        image_load[2],
    )
    _log_decal_material_profile_details(profile)


def _sector_warning(message, **kwargs):
    kwargs["stacklevel"] = kwargs.get("stacklevel", 1) + 1
    _LOG.warning("%s", message, **kwargs)


def _warning_kind(message):
    """The part of a sector warning that repeats across sectors and nodes"""
    normalized = str(message or "")
    normalized = re.sub(r"^[^:]+:\s*", "", normalized)
    normalized = re.sub(r"\bnode \d+\b", "node #", normalized)
    normalized = re.sub(r" - \d+ - [^ ]+$", "", normalized)
    return normalized


def _rollback_child_diagnostic(state, label):
    try:
        rollback_import_child(state, label)
    except Exception as error:
        debug_exception(_LOG, "Could not roll back %s", label)
        return str(error)
    return ""


def _existing_sector_collections():
    result = {}
    for collection in bpy.data.collections:
        try:
            stored_path = collection.get("cp77_sector_path", "")
        except (AttributeError, ReferenceError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_existing_sector_collections", type(error).__name__),
                "existing sector collections: fell back after %s",
                error,
                exc_info=True,
            )
            continue
        if stored_path:
            result[local_path_key(stored_path)] = collection
    return result


def _sector_collection_for_parsed(
    scene_collection,
    parsed_sector,
    created_by_path,
    created_by_name,
    existing_by_path,
    *,
    defer_scene_link=False,
):
    filepath = parsed_sector.source_path
    path_key = local_path_key(filepath)
    collection = created_by_path.get(path_key) or existing_by_path.get(path_key)
    created_new = collection is None
    if collection is None:
        base_name = parsed_sector.sector_name
        name = base_name
        existing = bpy.data.collections.get(name)
        if existing is not None and not same_local_path(
            existing.get("cp77_sector_path", ""),
            filepath,
        ):
            identity = hashlib.sha1(path_key.encode("utf-8")).hexdigest()[:8]
            name = fit_id_name(base_name, f"_{identity}")
        collection = track_created_datablock(
            "collections", bpy.data.collections.new(name)
        )

    created_by_path[path_key] = collection
    created_by_name.setdefault(parsed_sector.sector_name, collection)
    existing_by_path[path_key] = collection

    parent_collection = None
    if parsed_sector.parent_sector_path:
        parent_collection = created_by_path.get(
            local_path_key(parsed_sector.parent_sector_path)
        )
    if parent_collection is None and parsed_sector.parent_sector:
        parent_collection = created_by_name.get(parsed_sector.parent_sector)

    if parent_collection is not None and parent_collection is not collection:
        if parent_collection.children.get(collection.name) is not collection:
            parent_collection.children.link(collection)
        if scene_collection.children.get(collection.name) is collection:
            scene_collection.children.unlink(collection)
    elif (
        not defer_scene_link
        and scene_collection.children.get(collection.name) is not collection
    ):
        scene_collection.children.link(collection)
    elif (
        defer_scene_link
        and created_new
        and scene_collection.children.get(collection.name) is collection
    ):
        scene_collection.children.unlink(collection)
    return collection


def _link_sector_composition(
    planned_sectors,
    created_collections,
    scene_collection,
):
    created_values = {
        collection
        for collection in created_collections.values()
        if collection is not None
    }
    for planned in planned_sectors:
        parsed = planned.parsed
        child = created_collections.get(local_path_key(parsed.source_path))
        if child is None:
            continue
        parent_paths = list(parsed.composition_parent_paths)
        if parsed.parent_sector_path:
            parent_paths.append(parsed.parent_sector_path)
        for parent_path in parent_paths:
            parent = created_collections.get(local_path_key(parent_path))
            if parent is None or parent is child:
                continue
            if parent.children.get(child.name) is not child:
                parent.children.link(child)

    nested = set()
    for parent in created_values:
        try:
            for child in tuple(parent.children):
                if child in created_values:
                    nested.add(child)
        except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_link_sector_composition", type(error).__name__),
                "link sector composition: fell back after %s",
                error,
                exc_info=True,
            )
            continue

    for collection in created_values:
        linked = scene_collection.children.get(collection.name) is collection
        if collection in nested:
            if linked:
                scene_collection.children.unlink(collection)
        elif not linked:
            scene_collection.children.link(collection)


class _InstanceMatrixResolver:
    __slots__ = ("_cache",)

    def __init__(self):
        self._cache = {}

    def __call__(self, instance, scale=1):
        key = (instance, float(scale))
        matrix = self._cache.get(key)
        if matrix is None:
            matrix = self._cache[key] = instance_matrix(instance, scale)
        return matrix


@dataclass(slots=True, frozen=True)
class _CollectionBlueprint:
    child_collections: tuple
    object_links: tuple
    source_objects: frozenset
    parent_links: tuple
    root_links: tuple
    modifier_links: tuple
    constraint_links: tuple
    animated_widget_roots: tuple


def _collection_blueprint(src_collection):
    child_collections = []
    object_links = []
    source_objects = set()
    source_order = []

    def visit(collection, destination_index):
        for old_obj in tuple(collection.objects):
            if not rna_is_live(old_obj):
                continue
            object_links.append((destination_index, old_obj))
            if old_obj not in source_objects:
                source_objects.add(old_obj)
                source_order.append(old_obj)
        for child in tuple(collection.children):
            child_index = len(child_collections) + 1
            child_collections.append((destination_index, child.name))
            visit(child, child_index)

    visit(src_collection, 0)
    parent_links = []
    root_links = []
    modifier_links = []
    constraint_links = []
    animated_widget_roots = []
    for source in source_order:
        if not rna_is_live(source):
            continue
        try:
            parent = source.parent
        except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_collection_blueprint 1", type(error).__name__),
                "collection blueprint: fell back after %s",
                error,
                exc_info=True,
            )
            parent = None
        if rna_is_live(parent) and parent in source_objects:
            parent_links.append(
                (
                    source,
                    parent,
                    source.matrix_parent_inverse.copy(),
                    source.matrix_basis.copy(),
                )
            )
        else:
            root_links.append(
                (
                    source,
                    (
                        source.matrix_basis.copy()
                        if parent is None
                        else source.matrix_world.copy()
                    ),
                )
            )
        try:
            if source.get("cp77_ink_animation_json"):
                animated_widget_roots.append(source)
        except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_collection_blueprint 2", type(error).__name__),
                "collection blueprint: fell back after %s",
                error,
                exc_info=True,
            )
        try:
            modifiers = tuple(source.modifiers)
        except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_collection_blueprint 3", type(error).__name__),
                "collection blueprint: fell back after %s",
                error,
                exc_info=True,
            )
            modifiers = ()
        for modifier_index, modifier in enumerate(modifiers):
            try:
                target = getattr(modifier, "object", None)
            except (ReferenceError, RuntimeError):
                target = None
            if rna_is_live(target) and target in source_objects:
                modifier_links.append((source, modifier_index, target))
        try:
            constraints = tuple(source.constraints)
        except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_collection_blueprint 4", type(error).__name__),
                "collection blueprint: fell back after %s",
                error,
                exc_info=True,
            )
            constraints = ()
        for constraint_index, constraint in enumerate(constraints):
            try:
                target = getattr(constraint, "target", None)
            except (ReferenceError, RuntimeError):
                target = None
            if rna_is_live(target) and target in source_objects:
                constraint_links.append((source, constraint_index, target))
    return _CollectionBlueprint(
        child_collections=tuple(child_collections),
        object_links=tuple(object_links),
        source_objects=frozenset(source_objects),
        parent_links=tuple(parent_links),
        root_links=tuple(root_links),
        modifier_links=tuple(modifier_links),
        constraint_links=tuple(constraint_links),
        animated_widget_roots=tuple(animated_widget_roots),
    )


def _cached_collection_blueprint(src_collection, cache):
    if cache is None:
        _PLACEMENT_PERF["blueprint_builds"] += 1
        return _collection_blueprint(src_collection)
    key = rna_identity(src_collection)
    cached = cache.get(key)
    if cached is not None and cached[0] is src_collection:
        _PLACEMENT_PERF["blueprint_hits"] += 1
        return cached[1]
    blueprint = _collection_blueprint(src_collection)
    _PLACEMENT_PERF["blueprint_builds"] += 1
    cache[key] = (src_collection, blueprint)
    return blueprint


def _remap_blueprint_references(copy_map, blueprint):
    for source, parent_source, parent_inverse, matrix_basis in blueprint.parent_links:
        obj = copy_map.get(source)
        parent = copy_map.get(parent_source)
        if obj is None or parent is None:
            continue
        obj.parent = parent
        obj.matrix_parent_inverse = parent_inverse
        obj.matrix_basis = matrix_basis

    for source, modifier_index, target_source in blueprint.modifier_links:
        obj = copy_map.get(source)
        target = copy_map.get(target_source)
        if obj is None or target is None or modifier_index >= len(obj.modifiers):
            continue
        obj.modifiers[modifier_index].object = target

    for source, constraint_index, target_source in blueprint.constraint_links:
        obj = copy_map.get(source)
        target = copy_map.get(target_source)
        if obj is None or target is None or constraint_index >= len(obj.constraints):
            continue
        obj.constraints[constraint_index].target = target


def _new_static_instance_object(source, source_collection, *, color=None):
    obj = track_created_datablock(
        "objects",
        bpy.data.objects.new(source.name, source.data),
    )
    # Assigning these updates the whole scene's layer and collection state (seconds over a sector's instances), even
    # when the value is unchanged; most masters keep the new object's defaults.
    try:
        for name in ("display_type", "show_in_front", "hide_render"):
            value = getattr(source, name)
            if getattr(obj, name) != value:
                setattr(obj, name, value)
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_new_static_instance_object 1", type(error).__name__),
            "new static instance object: fell back after %s",
            error,
            exc_info=True,
        )
    if color is not None and tuple(obj.color) != tuple(color):
        obj.color = color
    try:
        for index, source_slot in enumerate(source.material_slots):
            if index >= len(obj.material_slots):
                break
            if source_slot.link != "OBJECT":
                continue
            target_slot = obj.material_slots[index]
            target_slot.link = "OBJECT"
            target_slot.material = source_slot.material
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_new_static_instance_object 2", type(error).__name__),
            "new static instance object: fell back after %s",
            error,
            exc_info=True,
        )
    obj["cp77_master_source_object"] = source.name
    obj["cp77_master_source_collection"] = source_collection.name
    for key in (
        "cp77_material_name",
        "sourcePath",
        "cp77_imported_mesh",
        "cp77_single_material_submesh",
    ):
        try:
            if key in source:
                obj[key] = source[key]
        except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_new_static_instance_object 3", type(error).__name__),
                "new static instance object: fell back after %s",
                error,
                exc_info=True,
            )
            continue
    # A master placed earlier in the session carries the preview its import finalized (mesh decal receivers); the
    # instance shows the same preview, and the finalizer will not run for a reused master.
    for modifier in source.modifiers:
        if is_preview_only_modifier(modifier):
            preview = obj.modifiers.new(modifier.name, "NODES")
            preview.node_group = modifier.node_group
            preview.show_in_editmode = modifier.show_in_editmode
    return obj


def _simple_static_blueprint_roots(blueprint, *, rotating):
    if rotating or blueprint.child_collections or not blueprint.object_links:
        return None
    if (
        blueprint.parent_links
        or blueprint.modifier_links
        or blueprint.constraint_links
        or blueprint.animated_widget_roots
    ):
        return None
    if len(blueprint.object_links) != len(blueprint.root_links):
        return None
    root_matrices = {source: matrix for source, matrix in blueprint.root_links}
    result = []
    for destination_index, source in blueprint.object_links:
        if destination_index != 0 or source not in root_matrices:
            return None
        try:
            if source.type != "MESH" or source.parent is not None:
                return None
            if len(source.constraints) or not all(
                map(is_preview_only_modifier, source.modifiers)
            ):
                return None
        except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_simple_static_blueprint_roots", type(error).__name__),
                "simple static blueprint roots: fell back after %s",
                error,
                exc_info=True,
            )
            return None
        result.append((source, root_matrices[source]))
    return tuple(result)


def _flat_placement(
    src_collection, simple_roots, name, transform, color, target_collection
):
    """Place a simple master's objects straight in target_collection"""
    direct_single = len(simple_roots) == 1 and matrix_is_identity(simple_roots[0][1])
    if direct_single:
        source, _root_matrix = simple_roots[0]
        placement_root = _new_static_instance_object(
            source,
            src_collection,
            color=color,
        )
        target_collection.objects.link(placement_root)
        placement_root.matrix_basis = transform
        _PLACEMENT_PERF["flat_single_groups"] += 1
        object_count = 1
    else:
        placement_root = new_empty(name, target_collection)
        placement_root.matrix_world = transform
        placement_root["cp77_master_source_collection"] = src_collection.name
        placement_root["cp77_master_source_object"] = simple_roots[0][0].name
        if color is not None:
            placement_root.color = color
        identity = Matrix.Identity(4)
        for source, root_matrix in simple_roots:
            obj = _new_static_instance_object(
                source,
                src_collection,
                color=color,
            )
            target_collection.objects.link(obj)
            obj.parent = placement_root
            obj.matrix_parent_inverse = identity
            obj.matrix_basis = root_matrix
            obj["cp77_flat_instance_owner"] = placement_root.name
        _PLACEMENT_PERF["flat_multi_groups"] += 1
        object_count = len(simple_roots) + 1
    _PLACEMENT_PERF["flat_groups"] += 1
    _PLACEMENT_PERF["flat_objects"] += object_count
    return placement_root, placement_root, None


def _copy_collection_tree_with_placement_root(
    src_collection,
    name,
    transform,
    color=None,
    hide_armatures=True,
    rotating=False,
    *,
    blueprint_cache=None,
    flat_target_collection=None,
    allow_flat_objects=False,
):
    blueprint = _cached_collection_blueprint(src_collection, blueprint_cache)
    simple_roots = _simple_static_blueprint_roots(
        blueprint,
        rotating=rotating,
    )
    if (
        simple_roots is not None
        and allow_flat_objects
        and flat_target_collection is not None
    ):
        with _timed("flat_elapsed"):
            return _flat_placement(
                src_collection,
                simple_roots,
                name,
                transform,
                color,
                flat_target_collection,
            )

    dst_root = track_created_datablock(
        "collections", bpy.data.collections.new(fit_id_name(name))
    )
    if simple_roots is not None:
        first_obj = None
        for source, root_matrix in simple_roots:
            obj = _new_static_instance_object(
                source,
                src_collection,
                color=color,
            )
            dst_root.objects.link(obj)
            obj.matrix_basis = transform @ root_matrix
            if first_obj is None:
                first_obj = obj
        _PLACEMENT_PERF["lean_collections"] += 1
        _PLACEMENT_PERF["lean_objects"] += len(simple_roots)
        return dst_root, first_obj, None

    _PLACEMENT_PERF["full_collections"] += 1
    destinations = [dst_root]
    for parent_index, collection_name in blueprint.child_collections:
        child_dst = track_created_datablock(
            "collections",
            bpy.data.collections.new(collection_name),
        )
        destinations[parent_index].children.link(child_dst)
        destinations.append(child_dst)

    copy_map = {}
    for destination_index, old_obj in blueprint.object_links:
        obj = copy_object(
            old_obj,
            color=color,
            hide_armature=hide_armatures,
        )
        copy_map[old_obj] = obj
        destinations[destination_index].objects.link(obj)
    _remap_blueprint_references(copy_map, blueprint)

    if blueprint.animated_widget_roots:
        from ...blender.ink import screens as ink_screens

        for source_root in blueprint.animated_widget_roots:
            copied_root = copy_map.get(source_root)
            if copied_root is not None:
                ink_screens.clone(source_root, copied_root, copy_map)

    placement_root = new_empty(f"{name}_Placement", dst_root)
    content_root = placement_root
    rotation_root = None
    if rotating:
        location, rotation, scale = transform.decompose()
        placement_root.matrix_world = Matrix.LocRotScale(
            location, rotation, Vector((1.0, 1.0, 1.0))
        )
        rotation_root = new_empty(f"{name}_Rotation", dst_root)
        rotation_root.parent = placement_root
        rotation_root.matrix_parent_inverse = Matrix.Identity(4)
        rotation_root.matrix_basis = Matrix.Identity(4)
        scale_root = new_empty(f"{name}_Scale", dst_root)
        scale_root.parent = rotation_root
        scale_root.matrix_parent_inverse = Matrix.Identity(4)
        scale_root.matrix_basis = Matrix.LocRotScale(
            Vector((0.0, 0.0, 0.0)), Quaternion((1.0, 0.0, 0.0, 0.0)), scale
        )
        content_root = scale_root
    else:
        placement_root.matrix_world = transform

    identity = Matrix.Identity(4)
    for old_obj, root_matrix in blueprint.root_links:
        obj = copy_map.get(old_obj)
        if obj is None:
            continue
        obj.parent = content_root
        obj.matrix_parent_inverse = identity
        obj.matrix_basis = root_matrix

    for source, constraint_index, _target_source in blueprint.constraint_links:
        obj = copy_map.get(source)
        if obj is None or constraint_index >= len(obj.constraints):
            continue
        constraint = obj.constraints[constraint_index]
        if constraint.type != "CHILD_OF" or constraint.target is None:
            continue
        expected_world = transform @ source.matrix_world.copy()
        constraint.set_inverse_pending = True
        request_child_of_inverse(obj, constraint_index, expected_world)
        _PLACEMENT_PERF["child_of_inverse_updates"] += 1

    return dst_root, placement_root, rotation_root


def _variant_for_node_data(
    variant_indices,
    node_data_index,
    *,
    monotonic=None,
):
    if len(variant_indices) < 2 or node_data_index is None:
        return None
    index = int(node_data_index)
    if monotonic is None:
        monotonic = all(
            start <= end for start, end in zip(variant_indices, variant_indices[1:])
        )
    if monotonic:
        variant_index = bisect_right(variant_indices, index) - 1
        if (
            0 <= variant_index < len(variant_indices) - 1
            and index < variant_indices[variant_index + 1]
        ):
            return variant_index
        return None
    for variant_index, (start, end) in enumerate(
        zip(variant_indices, variant_indices[1:])
    ):
        if start <= index < end:
            return variant_index
    return None


def _variant_lookup(variant_indices, node_data_count):
    if len(variant_indices) < 2 or node_data_count <= 0:
        return ()
    monotonic = all(
        start <= end for start, end in zip(variant_indices, variant_indices[1:])
    )
    return tuple(
        _variant_for_node_data(
            variant_indices,
            node_data_index,
            monotonic=monotonic,
        )
        for node_data_index in range(node_data_count)
    )


def _is_sector_collection(collection):
    try:
        return bool(collection.get("cp77_sector_path"))
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_is_sector_collection", type(error).__name__),
            "is sector collection: fell back after %s",
            error,
            exc_info=True,
        )
        return False


def _sector_content_tree(root):
    """Collections owned by root"""
    stack = [child for child in root.children if not _is_sector_collection(child)]
    seen = set()
    while stack:
        collection = stack.pop()
        identity = rna_identity(collection)
        if identity in seen:
            continue
        seen.add(identity)
        yield collection
        stack.extend(
            child for child in collection.children if not _is_sector_collection(child)
        )


def _item_node(item):
    """The (sector name or None, node index) an object or collection was placed for, or None"""
    try:
        node_index = item.get("nodeIndex")
        owner = item.get("cp77_sector_name")
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_item_node", type(error).__name__),
            "item node: fell back after %s",
            error,
            exc_info=True,
        )
        return None
    if node_index is None:
        return None
    try:
        return owner, int(node_index)
    except (TypeError, ValueError):
        return None


def _placed_content(sector_collection, sector_name, *, count_records=True):
    """What of sector_name the sector collection holds"""
    collections = tuple(_sector_content_tree(sector_collection))
    node_data = set()
    recorded_nodes = set()
    entryless_nodes = set()

    def record(item):
        node = _item_node(item)
        if node is not None and (node[0] is None or node[0] == sector_name):
            index = _placement_node_data_index(item)
            if index is None or index < 0:
                entryless_nodes.add(node[1])
            else:
                node_data.add(index)

    for owner in (sector_collection, *collections):
        for obj in owner.objects:
            record(obj)
    for collection in collections:
        if not collection.get("cp77_organizational_collection", False):
            record(collection)
    # A placed entity is found by its own collection; only the sector's channel volume nodes stand as records, and
    # only while the import keeps no volume objects.
    for retired in (
        stored_light_channel_records((sector_collection,)) if count_records else ()
    ):
        if (
            not retired["component"]
            and retired["node_index"] is not None
            and retired["sector_name"] in ("", sector_name)
        ):
            recorded_nodes.add(int(retired["node_index"]))
    return PlacedContent(
        node_data=frozenset(node_data),
        recorded_nodes=frozenset(recorded_nodes),
        entryless_nodes=frozenset(entryless_nodes),
    )


def _sector_content_identities(sector_collections):
    """The collections and objects the sectors hold before this import places anything"""
    identities = set()
    for sector_collection in sector_collections:
        tree = tuple(_sector_content_tree(sector_collection))
        identities.update(rna_identity(collection) for collection in tree)
        for owner in (sector_collection, *tree):
            identities.update(rna_identity(obj) for obj in owner.objects)
    return identities


def _content_nodes(sector_collection):
    """The node each content collection of a sector belongs to"""
    nodes = {}
    for collection in _sector_content_tree(sector_collection):
        identity = rna_identity(collection)
        node = _item_node(collection) or nodes.get(identity)
        nodes[identity] = node
        for child in collection.children:
            nodes.setdefault(rna_identity(child), node)
    return nodes


def _volume_node(obj, *, nodes, owners, sector_name):
    node = _item_node(obj) or next(
        (
            nodes[rna_identity(owner)]
            for owner in owners[rna_identity(obj)]
            if nodes.get(rna_identity(owner)) is not None
        ),
        None,
    )
    return None if node is None else (node[0] or sector_name, node[1])


def _retire_new_channel_volumes(sector_collections, kept):
    """Keep the channel volumes this import placed as records on their sector collection"""
    retired = 0
    emptied = {}
    for sector_collection in sector_collections:
        if sector_collection is None:
            continue
        sector_name = str(sector_collection.get("cp77_sector_name", "") or "")
        nodes = _content_nodes(sector_collection)
        owners = {}
        for owner in (sector_collection, *_sector_content_tree(sector_collection)):
            for obj in owner.objects:
                identity = rna_identity(obj)
                if identity not in kept and is_light_channel_volume(obj):
                    owners.setdefault(identity, []).append(owner)
        if not owners:
            continue
        volumes = [
            obj for obj in sector_collection.all_objects if rna_identity(obj) in owners
        ]
        retired += retire_light_channel_volumes(
            sector_collection,
            volumes,
            node_of=partial(
                _volume_node, nodes=nodes, owners=owners, sector_name=sector_name
            ),
        )
        for owner_list in owners.values():
            for owner in owner_list:
                if owner is not sector_collection and rna_identity(owner) not in kept:
                    emptied[rna_identity(owner)] = owner
    removable = [
        collection
        for collection in emptied.values()
        if not collection.objects and not collection.children
    ]
    if removable:
        bpy.data.batch_remove(removable)
    return retired


def _relink_sector_light_channels(
    scene_collection, sector_collections, timing, *, retire_kept=None
):
    """Link the lights of the registered sectors and sector_collections and register them"""
    channel_scope_started = time.perf_counter()
    encoded_names = scene_collection.get("cp77_sector_light_channel_collections", "[]")
    registered_names = (
        json_array(encoded_names) if isinstance(encoded_names, str) else []
    )

    scoped_collections = []
    seen_collections = set()
    for name in (
        *registered_names,
        *(
            collection.name
            for collection in sector_collections
            if collection is not None
        ),
    ):
        collection = bpy.data.collections.get(str(name))
        if collection is None:
            continue
        pointer = collection.as_pointer()
        if pointer in seen_collections:
            continue
        seen_collections.add(pointer)
        scoped_collections.append(collection)

    scoped_objects = []
    seen_objects = set()
    for collection in scoped_collections:
        for obj in collection.all_objects:
            pointer = obj.as_pointer()
            if pointer in seen_objects:
                continue
            seen_objects.add(pointer)
            scoped_objects.append(obj)

    timing["channel_scope"] = time.perf_counter() - channel_scope_started
    channel_links_started = time.perf_counter()
    channel_summary = rebuild_light_channel_links(
        scene_collection,
        objects=tuple(scoped_objects),
        record_collections=tuple(scoped_collections),
        mode="SECTOR",
    )
    timing["channel_links"] = time.perf_counter() - channel_links_started
    scene_collection["cp77_sector_light_channel_collections"] = json.dumps(
        [collection.name for collection in scoped_collections],
        separators=(",", ":"),
    )
    scene_collection["cp77_sector_light_channel_scope"] = True
    if retire_kept is not None:
        channel_summary["retired"] = _retire_new_channel_volumes(
            sector_collections, retire_kept
        )
    return channel_summary


def _is_light_link_collection(collection):
    try:
        return bool(collection.get("cp77_light_link_scope"))
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_is_light_link_collection", type(error).__name__),
            "is light link collection: fell back after %s",
            error,
            exc_info=True,
        )
        return False


def _restore_replaced_names(renamed):
    indexes = {}
    for datablock, original in renamed:
        if not rna_is_live(datablock) or datablock.name == original:
            continue
        kind = (
            "collections" if isinstance(datablock, bpy.types.Collection) else "objects"
        )
        index = indexes.get(kind)
        if index is None:
            index = indexes[kind] = {
                item.name: item for item in getattr(bpy.data, kind)
            }
        occupant = index.get(original)
        if occupant is not None and rna_identity(occupant) != rna_identity(datablock):
            occupant.name = f"{_SUPERSEDED_NAME_PREFIX}{original}"
            index[occupant.name] = occupant
        datablock.name = original
        index[original] = datablock


def _replaced_names_restored(renamed):
    return all(
        not rna_is_live(datablock) or datablock.name == original
        for datablock, original in renamed
    )


def _reclaim_free_names(renamed):
    indexes = {}
    for datablock, original in renamed:
        if not rna_is_live(datablock) or datablock.name == original:
            continue
        kind = (
            "collections" if isinstance(datablock, bpy.types.Collection) else "objects"
        )
        index = indexes.get(kind)
        if index is None:
            index = indexes[kind] = {item.name for item in getattr(bpy.data, kind)}
        if original not in index:
            datablock.name = original
            index.add(original)


def _object_owners():
    """The collections holding each object, by the object's identity"""
    owners = {}
    for owner in (
        *bpy.data.collections,
        *(scene.collection for scene in bpy.data.scenes),
    ):
        for obj in owner.objects:
            owners.setdefault(rna_identity(obj), []).append(owner)
    return owners


def _wide_collections(skipped=frozenset()):
    """The collections with more than _WIDE_COLLECTION children, but for those in skipped"""
    return [
        collection
        for collection in bpy.data.collections
        if len(collection.children) > _WIDE_COLLECTION
        and rna_identity(collection) not in skipped
    ]


@contextmanager
def _children_held(collections):
    """Unlink the collections' children for the duration and link them back in order"""
    held = []
    try:
        for collection in collections:
            children = tuple(collection.children)
            for child in children:
                collection.children.unlink(child)
            held.append((collection, children))
        yield
    finally:
        for collection, children in held:
            for child in children:
                if rna_is_live(child):
                    collection.children.link(child)


def _remove_replaced_sector_content(replaced):
    """Remove what Replace detached from the import's sectors"""
    collections = {
        rna_identity(collection): collection
        for _sector, sector_collections, _objects, _renamed in replaced
        for collection in sector_collections
    }.values()
    objects = {
        rna_identity(obj): obj
        for _sector, _collections, sector_objects, _renamed in replaced
        for obj in sector_objects
    }.values()
    renamed = tuple(
        item
        for _sector, _collections, _objects, sector_renamed in replaced
        for item in sector_renamed
    )
    live_collections = [
        collection for collection in collections if rna_is_live(collection)
    ]
    tree = {rna_identity(collection) for collection in live_collections}
    internal_parents = {}
    for collection in live_collections:
        for child in collection.children:
            identity = rna_identity(child)
            if identity in tree:
                internal_parents[identity] = internal_parents.get(identity, 0) + 1
    shared = [
        collection
        for collection in live_collections
        if collection.users > internal_parents.get(rna_identity(collection), 0)
    ]
    kept = {rna_identity(collection) for collection in shared}
    while shared:
        collection = shared.pop()
        for child in collection.children:
            identity = rna_identity(child)
            if identity in tree and identity not in kept:
                kept.add(identity)
                shared.append(child)
    doomed_collections = [
        collection
        for collection in live_collections
        if rna_identity(collection) not in kept
    ]
    doomed_ids = {rna_identity(collection) for collection in doomed_collections}
    owners = _object_owners()
    doomed_objects = [
        obj
        for obj in objects
        if rna_is_live(obj)
        and all(
            rna_identity(owner) in doomed_ids or _is_light_link_collection(owner)
            for owner in owners.get(rna_identity(obj), ())
        )
    ]
    doomed_object_ids = {rna_identity(obj) for obj in doomed_objects}
    _reclaim_free_names(
        tuple(
            (datablock, original)
            for datablock, original in renamed
            if rna_identity(datablock) not in doomed_ids
            and rna_identity(datablock) not in doomed_object_ids
        )
    )
    object_data = {}
    materials = {}
    for obj in doomed_objects:
        data = obj.data
        if isinstance(data, bpy.types.ID):
            object_data.setdefault(rna_identity(data), data)
        for slot in obj.material_slots:
            if slot.link == "OBJECT" and slot.material is not None:
                materials.setdefault(rna_identity(slot.material), slot.material)
    # The removed objects leave their collections first, light link collections holding thousands of objects among
    # them, rather than one by one as Blender deletes them.
    for obj in doomed_objects:
        for owner in owners.get(rna_identity(obj), ()):
            owner.objects.unlink(obj)
    with _children_held(_wide_collections(doomed_ids)):
        if doomed_objects or doomed_collections:
            bpy.data.batch_remove((*doomed_objects, *doomed_collections))
    orphaned = tuple(
        data for data in object_data.values() if rna_is_live(data) and data.users == 0
    )
    for data in orphaned:
        for material in getattr(data, "materials", ()):
            if material is not None:
                materials.setdefault(rna_identity(material), material)
    if orphaned:
        bpy.data.batch_remove(orphaned)
    released = remove_unused_shading(materials.values())
    _LOG.debug(
        "Replaced sector content removed: %d object(s), %d collection(s), "
        "%d data-block(s), %d material(s) and node group(s); %d shared collection(s) kept",
        len(doomed_objects),
        len(doomed_collections),
        len(orphaned),
        released,
        len(kept),
    )


def _detach_sector_content(sector_collection, replaced):
    """Move existing sector content aside"""
    top_children = tuple(
        child
        for child in sector_collection.children
        if not _is_sector_collection(child)
    )
    top_objects = tuple(sector_collection.objects)
    if not top_children and not top_objects:
        return 0
    collections = tuple(_sector_content_tree(sector_collection))
    objects = {}
    for owner in (sector_collection, *collections):
        for obj in owner.objects:
            objects.setdefault(rna_identity(obj), obj)
    objects = tuple(objects.values())
    track_collection_state(
        sector_collection,
        label=f"sector collection {sector_collection.name}",
    )
    renamed = tuple(
        (datablock, datablock.name) for datablock in (*collections, *objects)
    )
    track_mutation(
        ("sector_replaced_names", rna_identity(sector_collection)),
        lambda renamed=renamed: _restore_replaced_names(renamed),
        verify=lambda renamed=renamed: _replaced_names_restored(renamed),
        label=f"replaced sector names {sector_collection.name}",
    )
    for datablock, original in renamed:
        datablock.name = f"{_REPLACED_NAME_PREFIX}{original}"
    for child in top_children:
        sector_collection.children.unlink(child)
    for obj in top_objects:
        sector_collection.objects.unlink(obj)

    detached = (sector_collection, collections, objects, renamed)
    transaction = current_import_transaction()
    if transaction is None:
        _remove_replaced_sector_content((detached,))
    else:
        if not replaced:
            transaction.defer_commit_cleanup(
                lambda: _remove_replaced_sector_content(replaced)
            )
        replaced.append(detached)
    return len(objects)


def _source_node_display_name(node):
    data = node.data
    debug_name = cname_text(data.get("debugName"), "")
    # A cooked node's inner nodes share its debug name, which is the empty CName "None".
    if debug_name and debug_name != "None":
        return str(debug_name)
    for path in (
        node.mesh_path,
        node.entity_template_path,
        node.foliage_resource_path,
        depot_path(data, "resource"),
    ):
        if not path:
            continue
        basename = os.path.basename(str(path).replace("\\", "/"))
        if basename:
            return basename.split(".")[0]
    return node.node_type or f"Node_{node.index}"


def _collection_name_token(value):
    token = re.sub(r"[^0-9A-Za-z_.-]+", "_", str(value or "")).strip("_.")
    return token or "Unnamed"


def _stable_sector_child_name(semantic_name, sector_identity):
    return fit_id_name(semantic_name, f"__{sector_identity}")


class _SectorCollectionRouter:
    __slots__ = (
        "existing_generated",
        "existing_sources",
        "flat",
        "generated_cache",
        "parsed_sector",
        "sector_collection",
        "sector_identity",
        "source_cache",
        "variant_lookup",
    )

    def __init__(self, sector_collection, parsed_sector, *, flat=False):
        self.sector_collection = sector_collection
        self.parsed_sector = parsed_sector
        self.flat = bool(flat)
        identity_source = (
            local_path_key(parsed_sector.source_path) or parsed_sector.sector_name
        )
        self.sector_identity = hashlib.sha1(
            identity_source.encode("utf-8")
        ).hexdigest()[:8]
        self.variant_lookup = _variant_lookup(
            parsed_sector.variant_indices,
            parsed_sector.node_data_count,
        )
        self.source_cache = {}
        self.generated_cache = {}
        self.existing_sources = {}
        self.existing_generated = {}
        for collection in _sector_content_tree(sector_collection):
            try:
                if collection.get("cp77_source_node_collection", False):
                    key = (
                        int(collection.get("nodeIndex", -1)),
                        int(collection.get("cp77_instance_index", -1)),
                        int(collection.get("cp77_node_variant_index", -1)),
                    )
                    self.existing_sources.setdefault(key, collection)
                elif collection.get("cp77_generated_collection", False):
                    semantic = str(collection.get("cp77_generated_collection_name", ""))
                    if semantic:
                        self.existing_generated.setdefault(semantic, collection)
            except (AttributeError, ReferenceError, TypeError, ValueError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    ("_SectorCollectionRouter.__init__", type(error).__name__),
                    "init: fell back after %s",
                    error,
                    exc_info=True,
                )
                continue

    def _variant_index(self, node_data_index):
        if node_data_index is None:
            return None
        try:
            index = int(node_data_index)
        except (TypeError, ValueError):
            return None
        if 0 <= index < len(self.variant_lookup):
            return self.variant_lookup[index]
        return None

    def source_collection(self, plan, node_data_index=None):
        if self.flat:
            return self.sector_collection
        return self.node_owned_collection(plan, node_data_index)

    def node_owned_collection(self, plan, node_data_index=None):
        node = plan.node
        variant_index = self._variant_index(node_data_index)
        variant_key = -1 if variant_index is None else int(variant_index)
        key = (int(node.index), int(node.inner_index), variant_key)
        cached = self.source_cache.get(key)
        if cached is not None:
            return cached
        collection = self.existing_sources.get(key)
        display_name = _collection_name_token(_source_node_display_name(node))
        node_type = _collection_name_token(node.node_type or "Node")
        variant_token = (
            f"_V{int(variant_index):02d}" if variant_index is not None else ""
        )
        inner_token = f"_I{node.inner_index:04d}" if node.inner_index >= 0 else ""
        semantic = (
            f"N{node.index:04d}{inner_token}{variant_token}_{node_type}_{display_name}"
        )
        desired_name = _stable_sector_child_name(
            semantic,
            self.sector_identity,
        )
        if collection is None:
            collection = track_created_datablock(
                "collections",
                bpy.data.collections.new(desired_name),
            )
        elif collection.name != desired_name:
            collection.name = desired_name
        if self.sector_collection.children.get(collection.name) is not collection:
            self.sector_collection.children.link(collection)
        collection["cp77_source_node_collection"] = True
        collection["cp77_organizational_collection"] = True
        collection["cp77_semantic_collection_name"] = semantic
        collection["cp77_node_variant_index"] = variant_key
        for property_name, value in node_records(node, self.parsed_sector.sector_name):
            collection[property_name] = value
        if len(node.instances) == 1 and node_data_index is not None:
            try:
                collection["cp77_node_data_index"] = int(node_data_index)
            except (TypeError, ValueError):
                debug_exception(
                    _LOG,
                    "Node data index %r of %s is not a number",
                    node_data_index,
                    collection.name,
                )
        elif "cp77_node_data_index" in collection:
            del collection["cp77_node_data_index"]
        self.source_cache[key] = collection
        return collection

    def generated_collection(self, name):
        semantic = _collection_name_token(name)
        cached = self.generated_cache.get(semantic)
        if cached is not None:
            return cached
        collection = self.existing_generated.get(semantic)
        semantic_name = f"Generated_{semantic}"
        desired_name = _stable_sector_child_name(
            semantic_name,
            self.sector_identity,
        )
        if collection is None:
            collection = track_created_datablock(
                "collections",
                bpy.data.collections.new(desired_name),
            )
        elif collection.name != desired_name:
            collection.name = desired_name
        if self.sector_collection.children.get(collection.name) is not collection:
            self.sector_collection.children.link(collection)
        collection["cp77_generated_collection"] = True
        collection["cp77_organizational_collection"] = True
        collection["cp77_generated_collection_name"] = semantic
        collection["cp77_semantic_collection_name"] = semantic_name
        collection["cp77_sector_name"] = self.parsed_sector.sector_name
        self.generated_cache[semantic] = collection
        return collection


def _ensure_child_collection(parent, name):
    for collection in parent.children:
        if (
            collection.get("cp77_semantic_collection_name") == name
            or collection.name == name
        ):
            return collection
    collection = track_created_datablock(
        "collections",
        bpy.data.collections.new(fit_id_name(f"{parent.name}_{name}")),
    )
    collection["cp77_semantic_collection_name"] = name
    collection["cp77_organizational_collection"] = True
    parent.children.link(collection)
    return collection


def _placement_node_data_index(item):
    value = item.get("cp77_node_data_index")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_proxy_node_type(node_type):
    """Whether node_type places a proxy"""
    return COOKED_PLAIN_TYPES.get(str(node_type), str(node_type)) in PROXY_NODE_TYPES


def _organize_sector_placements(
    sector_collection,
    parsed_sector,
    *,
    selected_variant=None,
    safe_json,
    variant_lookup=None,
):
    variant_indices = parsed_sector.variant_indices
    variant_nodes = parsed_sector.variant_nodes
    variant_root = None
    variant_collections = {}
    child_cache = {}

    def semantic_child(parent, name):
        cache_key = (id(parent), name)
        collection = child_cache.get(cache_key)
        if collection is None:
            collection = _ensure_child_collection(parent, name)
            child_cache[cache_key] = collection
        return collection

    if len(variant_indices) >= 2:
        variant_root = semantic_child(sector_collection, "_Variants")
        variant_root["variantIndices"] = list(variant_indices)
        for variant_index in range(len(variant_indices) - 1):
            collection = semantic_child(
                variant_root,
                f"Variant_{variant_index:02d}",
            )
            collection["variantNodes"] = safe_json(
                variant_nodes[variant_index]
                if variant_index < len(variant_nodes)
                else ()
            )
            is_selected = selected_variant is None or variant_index == int(
                selected_variant
            )
            collection.hide_viewport = not is_selected
            collection.hide_render = not is_selected
            variant_collections[variant_index] = collection

    available_variants = max(0, len(variant_indices) - 1)
    if (
        selected_variant is not None
        and not 0 <= int(selected_variant) < available_variants
    ):
        _sector_warning(
            f"{parsed_sector.sector_name}: selected variant "
            f"{selected_variant} is outside the available range"
        )

    if variant_lookup is None:
        variant_lookup = _variant_lookup(variant_indices, parsed_sector.node_data_count)

    def variant_of(item):
        explicit_variant = item.get("cp77_node_variant_index")
        if explicit_variant is not None:
            explicit_variant = coerce_int(explicit_variant, -1, unwrap=False)
        if explicit_variant is not None and explicit_variant >= 0:
            return explicit_variant
        node_data_index = _placement_node_data_index(item)
        if node_data_index is not None and 0 <= node_data_index < len(variant_lookup):
            return variant_lookup[node_data_index]
        return None

    def destination(item):
        parent = variant_collections.get(variant_of(item), sector_collection)
        if _is_proxy_node_type(item.get("cp77_node_type", "")):
            parent = semantic_child(parent, "_Proxies")
        return parent

    protected = {"_Variants", "_Proxies"}
    for collection in tuple(sector_collection.children):
        semantic_name = collection.get("cp77_semantic_collection_name")
        if (
            semantic_name in protected
            or collection.name in protected
            or collection is variant_root
            or _is_sector_collection(collection)
        ):
            continue
        target = destination(collection)
        if target is not sector_collection:
            if target.children.get(collection.name) is not collection:
                target.children.link(collection)
            if sector_collection.children.get(collection.name) is collection:
                sector_collection.children.unlink(collection)

    root_objects = tuple(sector_collection.objects)
    flat_children = {}
    for obj in root_objects:
        owner_name = str(obj.get("cp77_flat_instance_owner", "") or "")
        if owner_name:
            flat_children.setdefault(owner_name, []).append(obj)

    for obj in root_objects:
        if obj.get("cp77_flat_instance_owner"):
            continue
        target = destination(obj)
        if target is sector_collection:
            continue
        group = (obj, *flat_children.get(obj.name, ()))
        for member in group:
            if target.objects.get(member.name) is not member:
                target.objects.link(member)
            if sector_collection.objects.get(member.name) is member:
                sector_collection.objects.unlink(member)


def _place_copied_mesh_instances(
    *,
    node,
    sector_name,
    sector_collection,
    masters,
    master_assets,
    scale,
    assign_properties,
    blueprint_cache,
    color=(0.3, 0.3, 0.3, 1),
    rotating=False,
    extra_props=None,
    source_collection_for_instance=None,
):
    node_type = node.node_type
    meshname = node.mesh_path
    mesh_appearance = node.mesh_appearance
    group, groupname = master_assets.get_mesh_master(
        masters,
        meshname,
        mesh_appearance,
    )
    if group is None:
        message = (
            f"Mesh not found in masters - {meshname} - {node.index} - {node.handle_id}"
        )
        _sector_warning(f"{sector_name}: {message}")
        return []

    placed = []
    for instance_index, inst in enumerate(node.instances):
        target_collection = (
            source_collection_for_instance(inst)
            if source_collection_for_instance is not None
            else sector_collection
        )
        node_matrix = instance_matrix(inst, scale)
        prefix = {
            "worldRotatingMeshNode": "ROT",
            "worldPhysicalDestructionNode": "PDEST",
            "worldBakedDestructionNode": "BDEST",
        }.get(node_type, "MESH")
        instance_name = fit_id_name(f"{prefix}_{inst.index}_{groupname}")
        new, placement_root, rotation_root = _copy_collection_tree_with_placement_root(
            group,
            instance_name,
            node_matrix,
            color=color,
            hide_armatures=True,
            rotating=rotating,
            blueprint_cache=blueprint_cache,
            flat_target_collection=target_collection,
            allow_flat_objects=(not rotating and node_type in _FLAT_STATIC_NODE_TYPES),
        )
        properties = {
            "cp77_node_data_index": inst.index,
            "cp77_instance_idx": instance_index,
            "mesh": meshname,
            "meshAppearance": mesh_appearance,
            "appearanceName": mesh_appearance,
        }
        if extra_props:
            properties.update(extra_props)
        assign_properties(new, node, sector_name, **properties)
        if placement_root is not new:
            if placement_root.get("cp77_master_source_object"):
                assign_id_properties(
                    placement_root,
                    **dict(node_records(node, sector_name)),
                    cp77_node_data_index=inst.index,
                    mesh=meshname,
                    appearanceName=mesh_appearance,
                )
            else:
                assign_properties(placement_root, node, sector_name, **properties)
        if isinstance(new, bpy.types.Collection):
            new["cp77_matrix"] = flatten_matrix(node_matrix).tolist()
            if target_collection.children.get(new.name) is not new:
                target_collection.children.link(new)
        placed.append((new, placement_root, rotation_root, inst, instance_index))
    return placed


def _normalize_selected_variant(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        _sector_warning(f"Invalid selected_variant {value!r}; importing all variants")
        return None


def _set_sector_view_clip(scale):
    """Extend the viewport far clip to world scale without lowering a larger user value"""
    if float(scale) != 1.0:
        return
    screen = getattr(bpy.context, "screen", None)
    if screen is None:
        return
    for area in screen.areas:
        if area.type != "VIEW_3D":
            continue
        for space in area.spaces:
            if space.type == "VIEW_3D" and space.clip_end < 50000:
                space.clip_end = 50000


def record_import_coverage(collection, sector_name):
    """Record on a sector collection what of it the scene holds after an import"""
    collections = tuple(_sector_content_tree(collection))
    node_data = set()

    def record(item):
        if item.get("cp77_sector_name", sector_name) != sector_name:
            return
        try:
            node_data.add(int(item["cp77_node_data_index"]))
        except (KeyError, TypeError, ValueError):
            pass

    for owner in (collection, *collections):
        for obj in owner.objects:
            record(obj)
    for child in collections:
        if not child.get("cp77_organizational_collection", False):
            record(child)
    actors = {}
    for item in getattr(getattr(bpy.context.scene, "physx", None), "actors", ()):
        px = getattr(item.obj_ref, "physx", None) if item.obj_ref is not None else None
        if (
            px is None
            or px.source_kind != "WORLD_COLLISION"
            or px.source_sector != sector_name
        ):
            continue
        actors.setdefault(str(int(px.source_node_data_index)), set()).add(
            int(px.source_actor_index)
        )
    collection["cp77_imported_node_data"] = json.dumps(sorted(node_data))
    collection["cp77_imported_collision_actors"] = json.dumps(
        {key: sorted(value) for key, value in sorted(actors.items())}
    )


def record_import_choices(collection, options):
    """Record on a sector collection what its import brought"""
    collection["cp77_import_choices"] = json.dumps(sorted(options.choices))


def _assign_sector_collection_metadata(collection, parsed_sector, options):
    collection["cp77_sector_path"] = parsed_sector.source_path
    collection["expectedNodes"] = int(parsed_sector.node_data_count)
    collection["cp77_sector_name"] = parsed_sector.sector_name
    record_import_choices(collection, options)


def _create_placement_operations(warning):
    property_assigner = NodePropertyAssigner()
    matrix_resolver = _InstanceMatrixResolver()
    blueprint_cache = {}

    def copy_collection_tree(*args, **kwargs):
        kwargs["blueprint_cache"] = blueprint_cache
        return _copy_collection_tree_with_placement_root(*args, **kwargs)

    def place_copied_mesh_instances(**kwargs):
        kwargs["assign_properties"] = property_assigner
        kwargs["blueprint_cache"] = blueprint_cache
        return _place_copied_mesh_instances(**kwargs)

    return SectorPlacementOperations(
        place_copied_mesh_instances=place_copied_mesh_instances,
        copy_collection_tree_with_placement_root=copy_collection_tree,
        assign_custom_properties=property_assigner,
        instance_matrix=matrix_resolver,
        warning=warning,
    )


def _unrecorded_placements(sector_collection):
    """The objects placing a sector's node data that record no import matrix yet"""
    return [
        obj
        for owner in (sector_collection, *_sector_content_tree(sector_collection))
        for obj in owner.objects
        if "cp77_node_data_index" in obj and "cp77_matrix" not in obj
    ]


def _capture_import_matrices(placement_collections, matrix_objects):
    if not placement_collections and not matrix_objects:
        return

    seen_collections = set()
    for collection in placement_collections:
        identity = id(collection)
        if identity in seen_collections:
            continue
        seen_collections.add(identity)
        try:
            if collection.get("cp77_organizational_collection", False):
                continue
            if "cp77_matrix" in collection:
                continue
            first_object = next(iter(collection.all_objects), None)
        except (AttributeError, ReferenceError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_capture_import_matrices 1", type(error).__name__),
                "capture import matrices: fell back after %s",
                error,
                exc_info=True,
            )
            continue
        if first_object is not None:
            collection["cp77_matrix"] = flatten_matrix(
                first_object.matrix_world
            ).tolist()

    seen = set()
    for obj in matrix_objects:
        identity = id(obj)
        if identity in seen:
            continue
        seen.add(identity)
        try:
            obj["cp77_matrix"] = flatten_matrix(object_world_matrix(obj)).tolist()
        except (AttributeError, ReferenceError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_capture_import_matrices 2", type(error).__name__),
                "capture import matrices: fell back after %s",
                error,
                exc_info=True,
            )
            continue


def _import_sectors_transactional(
    filepath,
    options,
    *,
    force_refresh=False,
    report_owner=None,
):
    options = replace(
        options,
        selected_variant=_normalize_selected_variant(options.selected_variant),
    )
    depot_root = ""
    preferences = get_addon_preferences(required=False)
    configured = str(getattr(preferences, "depotfolder_path", "") or "")
    if configured and os.path.isdir(configured):
        depot_root = configured
    transaction = BlenderImportTransaction(capture_existing_state=False)
    material_cache_acquired = acquire_material_cache(options.with_materials)
    clear_image_load_failures()
    progress = BlenderImportProgress(bpy.context, "Sector Import")
    try:
        with progress:
            progress.set(0.0, "Preparing asset index", force=True)
            try:
                with transaction.scope():
                    with SectorImportSession(
                        filepath,
                        options,
                        force_refresh=force_refresh,
                        depot_root=depot_root,
                    ) as session:
                        progress.set(5.0, "Planning sectors", force=True)
                        result = _import_sectors(
                            session,
                            progress=progress,
                            _override_palette_owner=report_owner,
                        )
                        if session.decal_assets is not None:
                            # Registered last, so it runs after Replace has removed the sectors this import superseded.
                            transaction.defer_commit_cleanup(
                                session.decal_assets.release_unused_materials
                            )
            except Exception as error:
                raise_if_rollback_incomplete(transaction.rollback(), error)
                raise
            if result.failures:
                report = transaction.rollback()
                failures = list(result.failures)
                rollback_error = rollback_report_message(report)
                if rollback_error:
                    failures.append("Rollback incomplete: " + rollback_error)
                _LOG.error(
                    "Sector import failed: %s",
                    "; ".join(failures[:3])
                    + (f"; and {len(failures) - 3} more" if len(failures) > 3 else ""),
                )
                return ImportResult(
                    created_items=(),
                    warnings=result.warnings,
                    failures=tuple(failures),
                    label=result.label,
                )
            transaction.commit()
            progress.set(100.0, "Complete", force=True)
        message = image_load_failure_message(consume_image_load_failures())
        if message:
            _sector_warning(message)
            result = ImportResult(
                created_items=result.created_items,
                warnings=unique_messages((*result.warnings, message)),
                failures=result.failures,
                label=result.label,
            )
        return result
    finally:
        if options.choices & COLLISION_CHOICES:
            # Rolled-back actors, from the whole import or from one failed master, leave entries without an object.
            prune_actor_registry(bpy.context)
        clear_image_load_failures()
        release_material_cache(material_cache_acquired)


def import_sectors(filepath, options, *, force_refresh=False, report_owner=None):
    project = os.path.basename(filepath or "")
    with operation(_LOG, f"sector import from {project}", project=project):
        return _import_sectors_transactional(
            filepath,
            options,
            force_refresh=force_refresh,
            report_owner=report_owner,
        )


@override_palette_batched
def _import_sectors(session, *, progress=NO_PROGRESS):
    options = session.options
    # The first three warnings of each kind at WARNING, the rest at DEBUG, and a summary per kind.
    warning_limiter = LogLimiter(
        _LOG,
        logging.WARNING,
        3,
        "%d more warning(s) like this one, logged at DEBUG: %s",
    )

    def warn(message, **kwargs):
        kwargs["stacklevel"] = kwargs.get("stacklevel", 1) + 1
        return warning_limiter.log(_warning_kind(message), "%s", message, **kwargs)

    _reset_placement_perf()
    clear_pending_child_of_inverse_requests()
    _LOG.debug("Raw root: %s", session.raw_root)

    start_time = time.perf_counter()
    progress.set(5.0, "Planning sectors", force=True)
    planned_sectors = session.planned_sectors()
    if not planned_sectors:
        return ImportResult(
            failures=(
                "No streaming sectors were found under "
                f"{session.raw_root}; nothing was imported",
            ),
            label="sector import",
        )
    _set_sector_view_clip(options.scale_factor)

    warnings = []
    existing_by_path = _existing_sector_collections()
    retire_channel_volumes = options.chosen("light_linking") and not options.chosen(
        "light_channel_volumes"
    )
    kept_sector_content = (
        _sector_content_identities(existing_by_path.values())
        if retire_channel_volumes
        else frozenset()
    )
    reused_sector_ids = {
        rna_identity(collection) for collection in existing_by_path.values()
    }
    skipped_existing = {}
    if options.existing_sector_mode == "ADD_MISSING" and existing_by_path:
        filtered = []
        for planned_sector in planned_sectors:
            parsed = planned_sector.parsed
            path_key = local_path_key(parsed.source_path)
            existing = existing_by_path.get(path_key)
            if existing is not None:
                planned_sector, skipped = exclude_placed_entries(
                    planned_sector,
                    _placed_content(
                        existing,
                        parsed.sector_name,
                        count_records=not options.chosen("light_channel_volumes"),
                    ),
                    "existing",
                )
                if skipped:
                    skipped_existing[path_key] = skipped
            filtered.append(planned_sector)
        planned_sectors = tuple(filtered)
        skipped_total = sum(skipped_existing.values())
        if skipped_total:
            _LOG.info(
                "Existing sectors: kept %d placed node(s) across %d sector(s)",
                skipped_total,
                len(skipped_existing),
            )
            if not any(
                planned_sector.ordered_placement_plans
                for planned_sector in planned_sectors
            ):
                warnings.append(
                    f"No new sector nodes to place: {skipped_total} node(s) "
                    "already exist in the scene (Existing Sectors: Add "
                    "Missing). Choose Replace to rebuild existing sectors."
                )
    planning_elapsed = time.perf_counter() - start_time
    progress.set(10.0, "Preparing mesh masters", force=True)

    scene_collection = bpy.context.scene.collection
    track_collection_state(scene_collection, label="scene collection")
    masters = scene_collection.children.get("MasterInstances")
    masters_was_linked = masters is not None
    if masters is None:
        masters = bpy.data.collections.get("MasterInstances")
    if masters is None:
        masters = track_created_datablock(
            "collections",
            bpy.data.collections.new("MasterInstances"),
        )
    else:
        track_collection_state(masters, label="MasterInstances")
    masters.hide_viewport = False
    # Instances render regardless; this only stops the masters themselves rendering.
    masters.hide_render = True
    session.masters = masters

    master_started = time.perf_counter()
    mesh_master_started = master_started
    try:
        session.master_assets.prepare_meshes(
            planned_sectors,
            masters,
            progress=progress.span(10.0, 15.0, label="Mesh masters"),
        )
    except Exception as error:
        message = f"Sector mesh-master preparation continued after failure: {error}"
        warn(message, exc_info=True)
        warnings.append(message)
    mesh_master_elapsed = time.perf_counter() - mesh_master_started
    progress.set(15.0, "Preparing entity masters", force=True)

    entity_dependencies = tuple(
        dependency
        for planned_sector in planned_sectors
        for plan in planned_sector.plans
        if plan.enabled
        for dependency in plan.dependencies
        if dependency.kind == "entity" and dependency.depot_path
    )
    entity_master_started = time.perf_counter()
    try:
        entity_failures = session.master_assets.entities.prepare(
            masters,
            entity_dependencies,
            progress=progress.span(15.0, 30.0, label="Entity masters"),
        )
        for message in entity_failures:
            warn(message)
            warnings.append(message)
    except Exception as error:
        message = f"Sector entity-master preparation continued after failure: {error}"
        warn(message, exc_info=True)
        warnings.append(message)

    master_inverse_stats = {
        "requested": 0,
        "pending": 0,
        "mismatches": 0,
        "max_translation_error": 0.0,
        "max_basis_error": 0.0,
    }
    temporary_master_link = False
    if pending_child_of_inverse_count():
        try:
            if scene_collection.children.get(masters.name) is not masters:
                scene_collection.children.link(masters)
                temporary_master_link = True
            master_inverse_stats = flush_pending_child_of_inverse_requests()
        finally:
            if (
                temporary_master_link
                and scene_collection.children.get(masters.name) is masters
            ):
                scene_collection.children.unlink(masters)
        _LOG.debug(
            "Entity-master Child Of native inverse: %d request(s), %d pending, "
            "%d transform mismatch(es), max translation %.6f, max basis %.6f",
            master_inverse_stats["requested"],
            master_inverse_stats["pending"],
            master_inverse_stats["mismatches"],
            master_inverse_stats["max_translation_error"],
            master_inverse_stats["max_basis_error"],
        )
        if master_inverse_stats["pending"] or master_inverse_stats["mismatches"]:
            message = (
                "Entity-master Child Of native inverse verification: "
                f"{master_inverse_stats['pending']} pending, "
                f"{master_inverse_stats['mismatches']} transform mismatch(es), "
                f"max translation {master_inverse_stats['max_translation_error']:.6f}, "
                f"max basis {master_inverse_stats['max_basis_error']:.6f}"
            )
            if master_inverse_stats.get("examples"):
                message += "; examples: " + ", ".join(master_inverse_stats["examples"])
            warn(message)
            warnings.append(message)
    entity_master_elapsed = time.perf_counter() - entity_master_started
    master_elapsed = time.perf_counter() - master_started
    progress.set(30.0, "Preparing sector placement", force=True)
    placement_operations = _create_placement_operations(warn)

    sector_collections = {}
    sector_collections_by_name = {}
    created_sector_collections = []
    replaced_content = []
    replaced_objects = 0
    replaced_sectors = 0
    matrix_collections = []
    matrix_objects = []
    sector_count = len(planned_sectors)
    placement_units = sum(
        3
        + sum(
            1
            for plan in planned_sector.ordered_placement_plans
            if (binding := NODE_HANDLERS.get(plan.node.node_type)) is not None
            and binding.has_placement
        )
        for planned_sector in planned_sectors
    )
    placement_progress = progress.span(30.0, 92.0).counter(
        "Placing sector content",
        placement_units,
    )
    placement_started = time.perf_counter()

    for sector_number, planned_sector in enumerate(planned_sectors, start=1):
        parsed = planned_sector.parsed
        sector_collection = _sector_collection_for_parsed(
            scene_collection,
            parsed,
            sector_collections,
            sector_collections_by_name,
            existing_by_path,
            defer_scene_link=True,
        )
        reused = rna_identity(sector_collection) in reused_sector_ids
        if reused:
            track_collection_state(
                sector_collection,
                label=f"sector collection {sector_collection.name}",
            )
            if options.existing_sector_mode == "REPLACE":
                detached = _detach_sector_content(sector_collection, replaced_content)
                clear_light_channel_records(sector_collection)
                replaced_objects += detached
                replaced_sectors += int(bool(detached))
            elif options.chosen("light_channel_volumes"):
                # Recorded volume nodes are placed again as objects.
                clear_light_channel_records(sector_collection, keep_components=True)
        created_sector_collections.append(sector_collection)
        _assign_sector_collection_metadata(sector_collection, parsed, options)
        for issue in parsed.composition_issues:
            warn(issue)
            warnings.append(issue)
        skipped = []
        if parsed.skipped_node_data:
            skipped.append(
                f"node data {', '.join(str(index) for index in parsed.skipped_node_data)} (the node or "
                "inner node they pick is missing)"
            )
        if parsed.skipped_instances:
            skipped.append(
                f"destructible {'instance' if len(parsed.skipped_instances) == 1 else 'instances'} "
                f"{', '.join(f'{item} of node {node}' for node, item in parsed.skipped_instances)} (not a transform)"
            )
        if skipped:
            message = f"{parsed.sector_name}: skipped {' and '.join(skipped)}"
            warn(message)
            warnings.append(message)

        _LOG.debug(
            "%d Processing %d nodes for sector %s (no %d of %d)",
            sector_number - 1,
            len(parsed.nodes),
            parsed.sector_name,
            sector_number,
            sector_count,
        )

        collection_router = _SectorCollectionRouter(
            sector_collection,
            parsed,
            flat=options.collection_layout == "SECTOR",
        )
        execution_context = SectorExecutionContext(
            session=session,
            planned_sector=planned_sector,
            sector_collection=sector_collection,
            masters_collection=masters,
            operations=placement_operations,
            blender_context=bpy.context,
            source_collection_resolver=collection_router.source_collection,
            generated_collection_resolver=collection_router.generated_collection,
            node_owned_collection_resolver=collection_router.node_owned_collection,
        )

        for plan in planned_sector.ordered_placement_plans:
            binding = NODE_HANDLERS.get(plan.node.node_type)
            if binding is None or not binding.has_placement:
                continue
            node_context = SectorNodeContext(execution=execution_context, plan=plan)
            child_state = child_import_savepoint()
            handler_started = time.perf_counter()
            try:
                binding.place(node_context)
            except Exception as error:
                rollback_error = _rollback_child_diagnostic(
                    child_state,
                    f"sector node {parsed.sector_name}:{plan.node.index}",
                )
                node_context.record_error(error)
                inner = (
                    f" inner node {plan.node.inner_index}"
                    if plan.node.inner_index >= 0
                    else ""
                )
                message = (
                    f"{parsed.sector_name}: node {plan.node.index}{inner} "
                    f"{plan.node.source_node_type} skipped: {error}"
                )
                if rollback_error:
                    message += f"; rollback incomplete: {rollback_error}"
                # A content error explains itself; anything else needs its traceback.
                warn(message, exc_info=not isinstance(error, SectorContentError))
                warnings.append(message)
            finally:
                _add_handler_time(plan, time.perf_counter() - handler_started)
                placement_progress.advance(
                    detail=f"{parsed.sector_name}: {plan.node.node_type}"
                )
        record_import_coverage(sector_collection, parsed.sector_name)

        placement_progress.note(
            f"{parsed.sector_name}: projecting decals",
            force=True,
        )
        child_state = child_import_savepoint()
        with _timed("decal_elapsed"):
            try:
                projection_summary = session.decal_assets.finalize_sector(
                    execution_context,
                )
                for error in projection_summary["errors"]:
                    message = f"{parsed.sector_name}: conformal projection {error}"
                    warn(message)
                    warnings.append(message)
                _add_decal_summary(projection_summary)
            except Exception as error:
                rollback_error = _rollback_child_diagnostic(
                    child_state,
                    f"sector decal projection {parsed.sector_name}",
                )
                message = (
                    f"{parsed.sector_name}: conformal decal projection skipped: {error}"
                )
                if rollback_error:
                    message += f"; rollback incomplete: {rollback_error}"
                warn(message, exc_info=True)
                warnings.append(message)
                session.decal_assets.invalidate_projection_cache()
        placement_progress.advance(detail=f"{parsed.sector_name}: decals")

        with _timed("validation_elapsed"):
            for issue in execution_context.validation_issues():
                warn(issue)
                warnings.append(issue)
        placement_progress.advance(detail=f"{parsed.sector_name}: validation")

        matrix_collections.extend(tuple(_sector_content_tree(sector_collection)))

        child_state = child_import_savepoint()
        with _timed("organization_elapsed"):
            try:
                _organize_sector_placements(
                    sector_collection,
                    parsed,
                    selected_variant=options.selected_variant,
                    safe_json=session.safe_json,
                    variant_lookup=collection_router.variant_lookup,
                )
            except Exception as error:
                rollback_error = _rollback_child_diagnostic(
                    child_state,
                    f"sector placement organization {parsed.sector_name}",
                )
                message = (
                    f"{parsed.sector_name}: placement organization skipped: {error}"
                )
                if rollback_error:
                    message += f"; rollback incomplete: {rollback_error}"
                warn(message, exc_info=True)
                warnings.append(message)
        placement_progress.advance(detail=f"{parsed.sector_name}: organization")
        matrix_objects.extend(execution_context.matrix_objects)
        matrix_objects.extend(_unrecorded_placements(sector_collection))

        _LOG.debug(
            "Finished %s (no %d of %d)",
            parsed.source_path,
            sector_number,
            sector_count,
        )

    placement_progress.finish(detail="Sector placement complete")
    if replaced_sectors:
        _LOG.info(
            "Existing sectors: replaced %d object(s) in %d sector(s)",
            replaced_objects,
            replaced_sectors,
        )
    placement_elapsed = time.perf_counter() - placement_started
    finalization_started = time.perf_counter()
    finalization_timing = {}
    progress.set(92.0, "Finalizing sector hierarchy", force=True)
    masters.hide_viewport = True
    if scene_collection.children.get(masters.name) is not masters:
        scene_collection.children.link(masters)
    try:
        _link_sector_composition(
            planned_sectors,
            sector_collections,
            scene_collection,
        )
    except Exception as error:
        message = f"Sector composition linking skipped: {error}"
        warn(message, exc_info=True)
        warnings.append(message)
    try:
        if options.chosen("sector_lights") and session.lighting_assets is not None:
            try:
                environment_count = (
                    session.lighting_assets.finalize_environment_registry(
                        bpy.context.scene
                    )
                )
                light_timing = session.lighting_assets.timing_stats()
                _LOG.debug(
                    "Static-light registry: %d environment light(s), %d flush(es) in %.3fs",
                    environment_count,
                    int(light_timing.get("registry_flushes", 0)),
                    float(light_timing.get("registry_flush_seconds", 0.0)),
                )
                _log_parts(
                    "Static-light creation",
                    float(light_timing.get("create_seconds", 0.0)),
                    tuple(
                        (name, float(light_timing.get(f"create_{name}_seconds", 0.0)))
                        for name in (
                            "prepare",
                            "datablocks",
                            "configure",
                            "resources",
                            "distribution",
                            "metadata",
                            "proxies",
                            "registry_queue",
                            "flicker",
                        )
                    ),
                    f"; total={float(light_timing.get('create_seconds', 0.0)):.3f}s, "
                    f"{int(light_timing.get('primary_lights', 0))} primary/"
                    f"{int(light_timing.get('proxy_lights', 0))} proxy light(s)",
                )
            except Exception as error:
                message = f"Static-light registry finalization skipped: {error}"
                warn(message, exc_info=True)
                warnings.append(message)
        evaluation_started = time.perf_counter()
        if pending_child_of_inverse_count():
            # The flush evaluates the view layer, which sets the pending inverses, then checks them.
            inverse_stats = flush_pending_child_of_inverse_requests()
            _PLACEMENT_PERF["child_of_inverse_flushes"] = 1
            _PLACEMENT_PERF["child_of_inverse_flush_elapsed"] = (
                time.perf_counter() - evaluation_started
            )
            _PLACEMENT_PERF["child_of_inverse_pending_after_flush"] = inverse_stats[
                "pending"
            ]
            _PLACEMENT_PERF["child_of_inverse_transform_mismatches"] = inverse_stats[
                "mismatches"
            ]
            _PLACEMENT_PERF["child_of_inverse_max_translation_error"] = inverse_stats[
                "max_translation_error"
            ]
            _PLACEMENT_PERF["child_of_inverse_max_basis_error"] = inverse_stats[
                "max_basis_error"
            ]
            if inverse_stats["pending"] or inverse_stats["mismatches"]:
                examples = inverse_stats.get("examples")
                warn(
                    "Child Of native inverse verification: "
                    f"{inverse_stats['pending']} request(s) still pending, "
                    f"{inverse_stats['mismatches']} transform mismatch(es), "
                    f"max translation error {inverse_stats['max_translation_error']:.6f}, "
                    f"max basis error {inverse_stats['max_basis_error']:.6f}"
                    + (f"; examples: {', '.join(examples)}" if examples else "")
                )
        else:
            bpy.context.view_layer.update()
        finalization_timing["evaluation"] = time.perf_counter() - evaluation_started
        if options.chosen("light_linking"):
            try:
                channel_summary = _relink_sector_light_channels(
                    scene_collection,
                    created_sector_collections,
                    finalization_timing,
                    retire_kept=kept_sector_content if retire_channel_volumes else None,
                )
                light_channel_log = (
                    _LOG.warning if channel_summary["unresolved"] else _LOG.debug
                )
                light_channel_log(
                    "Sector light channels: %d volume(s), %d receiver(s), "
                    "%d/%d linked, %d unresolved, %d world-unbounded",
                    channel_summary["volumes"],
                    channel_summary["receivers"],
                    channel_summary["linked"],
                    channel_summary["lights"],
                    channel_summary["unresolved"],
                    channel_summary["world_unbounded"],
                )
                if "retired" in channel_summary:
                    _LOG.debug(
                        "Sector light channels: kept %d volume(s) as records",
                        channel_summary["retired"],
                    )
                mark_registered_reflection_probes_dirty(bpy.context.scene)
            except Exception as error:
                message = f"Sector light-channel linking skipped: {error}"
                warn(message, exc_info=True)
                warnings.append(message)
        capture_started = time.perf_counter()
        _capture_import_matrices(
            matrix_collections,
            matrix_objects,
        )
        finalization_timing["matrix_capture"] = time.perf_counter() - capture_started
    except Exception as error:
        message = f"Sector import-matrix capture skipped: {error}"
        warn(message, exc_info=True)
        warnings.append(message)
    finalization_elapsed = time.perf_counter() - finalization_started
    _LOG.debug(
        "Sector finalization timing: evaluation=%.3fs, channel_scope=%.3fs, "
        "channel_links=%.3fs, matrix_capture=%.3fs, other=%.3fs; "
        "completed phases=%s",
        finalization_timing.get("evaluation", 0.0),
        finalization_timing.get("channel_scope", 0.0),
        finalization_timing.get("channel_links", 0.0),
        finalization_timing.get("matrix_capture", 0.0),
        max(0.0, finalization_elapsed - sum(finalization_timing.values())),
        ", ".join(finalization_timing) or "none",
    )
    progress.set(100.0, "Complete", force=True)
    warning_limiter.flush()
    if is_enabled("DEBUG", _LOG):
        try:
            _LOG.debug(
                "Sector phases: planning=%.3fs, masters=%.3fs "
                "(meshes=%.3fs, entities=%.3fs), placement=%.3fs, "
                "finalization=%.3fs",
                planning_elapsed,
                master_elapsed,
                mesh_master_elapsed,
                entity_master_elapsed,
                placement_elapsed,
                finalization_elapsed,
            )
            _LOG.debug(
                "Placement cache: %d blueprint build(s), %d hit(s); "
                "%d flat group(s)/%d object(s) in %.3fs "
                "(%d single, %d multi), "
                "%d lean collection(s)/%d object(s), %d full collection(s), "
                "%d Child Of native inverse request(s)/%d flush(es) in %.3fs; "
                "%d pending/%d transform mismatch(es), max translation error %.6f, "
                "max basis error %.6f",
                _PLACEMENT_PERF["blueprint_builds"],
                _PLACEMENT_PERF["blueprint_hits"],
                _PLACEMENT_PERF["flat_groups"],
                _PLACEMENT_PERF["flat_objects"],
                _PLACEMENT_PERF["flat_elapsed"],
                _PLACEMENT_PERF["flat_single_groups"],
                _PLACEMENT_PERF["flat_multi_groups"],
                _PLACEMENT_PERF["lean_collections"],
                _PLACEMENT_PERF["lean_objects"],
                _PLACEMENT_PERF["full_collections"],
                _PLACEMENT_PERF["child_of_inverse_updates"],
                _PLACEMENT_PERF["child_of_inverse_flushes"],
                _PLACEMENT_PERF["child_of_inverse_flush_elapsed"],
                _PLACEMENT_PERF["child_of_inverse_pending_after_flush"],
                _PLACEMENT_PERF["child_of_inverse_transform_mismatches"],
                _PLACEMENT_PERF["child_of_inverse_max_translation_error"],
                _PLACEMENT_PERF["child_of_inverse_max_basis_error"],
            )
            accounted = (
                _PLACEMENT_PERF["handler_elapsed"]
                + _PLACEMENT_PERF["decal_elapsed"]
                + _PLACEMENT_PERF["validation_elapsed"]
                + _PLACEMENT_PERF["organization_elapsed"]
            )
            _LOG.debug(
                "Placement detail: handlers=%.3fs, decals=%.3fs, "
                "validation=%.3fs, organization=%.3fs, residual=%.3fs; "
                "detached masters=%s, detached sectors=%d",
                _PLACEMENT_PERF["handler_elapsed"],
                _PLACEMENT_PERF["decal_elapsed"],
                _PLACEMENT_PERF["validation_elapsed"],
                _PLACEMENT_PERF["organization_elapsed"],
                max(0.0, placement_elapsed - accounted),
                str(not masters_was_linked).lower(),
                sum(
                    1
                    for collection in created_sector_collections
                    if collection is not None
                ),
            )
            _LOG.debug(
                "Decal projection detail: receiver_scan=%.3fs, "
                "triangle_collect=%.3fs, patch_build=%.3fs "
                "(geometry=%.3fs, commit=%.3fs); "
                "%d receiver(s), %d cached mesh(es), "
                "array cache %d hit(s)/%d miss(es), "
                "%d source triangle(s), %d candidate triangle(s), "
                "%d projector match(es), %d OBB pre-rejected, %d receiver batch(es), "
                "%d combined surface object(s); "
                "%d fully inside, %d boundary clipped, "
                "%d fast rejected",
                _PLACEMENT_PERF["decal_receiver_scan"],
                _PLACEMENT_PERF["decal_triangle_collect"],
                _PLACEMENT_PERF["decal_patch_build"],
                _PLACEMENT_PERF["decal_patch_geometry"],
                _PLACEMENT_PERF["decal_surface_commit"],
                _PLACEMENT_PERF["decal_receiver_count"],
                _PLACEMENT_PERF["decal_unique_meshes"],
                _PLACEMENT_PERF["decal_array_cache_hits"],
                _PLACEMENT_PERF["decal_array_cache_misses"],
                _PLACEMENT_PERF["decal_source_triangles"],
                _PLACEMENT_PERF["decal_candidate_triangles"],
                _PLACEMENT_PERF["decal_triangle_projector_matches"],
                _PLACEMENT_PERF["decal_oriented_bounds_rejected"],
                _PLACEMENT_PERF["decal_triangle_batches"],
                _PLACEMENT_PERF["decal_surface_objects"],
                _PLACEMENT_PERF["decal_fully_inside_triangles"],
                _PLACEMENT_PERF["decal_boundary_clipped_triangles"],
                _PLACEMENT_PERF["decal_fast_volume_rejected"],
            )
            for label, total, parts in (
                (
                    "Decal accepted-geometry",
                    "patch_geometry",
                    (
                        ("setup", "geometry_setup"),
                        ("classify", "geometry_classification"),
                        ("full_emit", "geometry_full_emit"),
                        ("boundary_clip", "geometry_boundary_clip"),
                        ("boundary_emit", "geometry_boundary_emit"),
                    ),
                ),
                (
                    "Decal full-emission",
                    "geometry_full_emit",
                    (
                        ("project", "geometry_full_projection"),
                        ("geometry", "geometry_full_geometry"),
                        ("attributes", "geometry_full_attributes"),
                        ("materials", "geometry_full_material"),
                    ),
                ),
                (
                    "Decal boundary-clip",
                    "geometry_boundary_clip",
                    (
                        ("select", "geometry_boundary_select"),
                        ("box", "geometry_boundary_box_clip"),
                        ("normal", "geometry_boundary_scalar_clip"),
                        ("triangulate", "geometry_boundary_triangulate"),
                        ("merge", "geometry_boundary_chunk_merge"),
                        ("materials", "geometry_boundary_material"),
                    ),
                ),
                (
                    "Decal boundary-emission",
                    "geometry_boundary_emit",
                    (
                        ("assemble", "geometry_boundary_assemble"),
                        ("surface_eval", "geometry_boundary_surface_eval"),
                        ("geometry", "geometry_boundary_geometry"),
                        ("attributes", "geometry_boundary_attributes"),
                    ),
                ),
            ):
                _log_parts(
                    label,
                    _PLACEMENT_PERF[f"decal_{total}"],
                    tuple(
                        (name, _PLACEMENT_PERF[f"decal_{key}"]) for name, key in parts
                    ),
                )
            decal_material_measured = (
                _PLACEMENT_PERF["decal_material_pointer_miss_seconds"]
                + _PLACEMENT_PERF["decal_material_composite_hit_seconds"]
                + _PLACEMENT_PERF["decal_material_composite_miss_seconds"]
                + _PLACEMENT_PERF["decal_material_fallback_seconds"]
            )
            decal_material_total = (
                _PLACEMENT_PERF["decal_geometry_full_material"]
                + _PLACEMENT_PERF["decal_geometry_boundary_material"]
            )
            _LOG.debug(
                "Decal material-resolution profile: calls=%d (overlay=%d), "
                "resolved=%d hit/%d miss, receiver_only=%d; "
                "pointer_cache=%d hit/%d miss (miss=%.3fs); composite=%d "
                "call(s), cache=%d hit/%d miss (hit=%.3fs, miss=%.3fs), "
                "none=%d; fallback=%d/%.3fs; slots=%d hit/%d miss; "
                "residual=%.3fs",
                _PLACEMENT_PERF["decal_material_index_calls"],
                _PLACEMENT_PERF["decal_material_overlay_calls"],
                _PLACEMENT_PERF["decal_material_resolved_hits"],
                _PLACEMENT_PERF["decal_material_resolved_misses"],
                _PLACEMENT_PERF["decal_material_receiver_only_resolutions"],
                _PLACEMENT_PERF["decal_material_pointer_hits"],
                _PLACEMENT_PERF["decal_material_pointer_misses"],
                _PLACEMENT_PERF["decal_material_pointer_miss_seconds"],
                _PLACEMENT_PERF["decal_material_composite_calls"],
                _PLACEMENT_PERF["decal_material_composite_cache_hits"],
                _PLACEMENT_PERF["decal_material_composite_cache_misses"],
                _PLACEMENT_PERF["decal_material_composite_hit_seconds"],
                _PLACEMENT_PERF["decal_material_composite_miss_seconds"],
                _PLACEMENT_PERF["decal_material_composite_none"],
                _PLACEMENT_PERF["decal_material_fallback_calls"],
                _PLACEMENT_PERF["decal_material_fallback_seconds"],
                _PLACEMENT_PERF["decal_material_slot_hits"],
                _PLACEMENT_PERF["decal_material_slot_misses"],
                max(0.0, decal_material_total - decal_material_measured),
            )
            if _PLACEMENT_PERF["decal_material_composite_cache_misses"]:
                _log_parts(
                    "Decal composite-build",
                    _PLACEMENT_PERF["decal_material_composite_miss_seconds"],
                    tuple(
                        (
                            phase,
                            _PLACEMENT_PERF[
                                f"decal_material_composite_{phase}_seconds"
                            ],
                        )
                        for phase in ("copy", "prepare", "factors", "adapt", "finalize")
                    ),
                    " (factors/adapt include graph cloning)",
                )
                _log_parts(
                    "Decal composite-clone (within build)",
                    _PLACEMENT_PERF["decal_material_composite_clone_seconds"],
                    tuple(
                        (
                            phase,
                            _PLACEMENT_PERF[
                                f"decal_material_composite_clone_{phase}_seconds"
                            ],
                        )
                        for phase in (
                            "create",
                            "properties",
                            "defaults",
                            "drivers",
                            "special",
                        )
                    ),
                    f"; total={_PLACEMENT_PERF['decal_material_composite_clone_seconds']:.3f}s, "
                    f"nodes={_PLACEMENT_PERF['decal_material_composite_clone_nodes']}, "
                    f"links={_PLACEMENT_PERF['decal_material_composite_clone_links']}",
                )
            decal_cache_stats = session.decal_assets.cache_stats()
            _LOG.debug(
                "Decal material cache: %d hit(s), %d miss(es), "
                "%d descriptor hit(s), %d descriptor miss(es), "
                "%d claimed, %d cloned, %d material entries, %d graph reuse(s)",
                decal_cache_stats.get("material_hits", 0),
                decal_cache_stats.get("material_misses", 0),
                decal_cache_stats.get("descriptor_hits", 0),
                decal_cache_stats.get("descriptor_misses", 0),
                decal_cache_stats.get("materials_claimed", 0),
                decal_cache_stats.get("materials_cloned", 0),
                decal_cache_stats.get("material_entries", 0),
                decal_cache_stats.get("graph_reuses", 0),
            )
            _log_decal_debug_timings(decal_cache_stats)
            if _PLACEMENT_HANDLER_PERF:
                top_handlers = sorted(
                    _PLACEMENT_HANDLER_PERF.items(),
                    key=lambda item: item[1][0],
                    reverse=True,
                )[:8]
                _LOG.debug(
                    "Placement handler hotspots: %s",
                    "; ".join(
                        f"{name}={stats[0]:.3f}s/"
                        f"{stats[1]} node(s)/{stats[2]} instance(s)"
                        for name, stats in top_handlers
                    ),
                )
        except Exception:
            debug_exception(_LOG, "Sector import diagnostics failed")

    return ImportResult(
        created_items=tuple(created_sector_collections),
        warnings=unique_messages(warnings),
        label="sector import",
    )
