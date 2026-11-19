from __future__ import annotations

import json
import os
import random
import time
import uuid
from dataclasses import dataclass, field
from functools import partial
from typing import Any

import bpy

from ...assetio.paths import depot_path, local_path_key, split_source_raw_root
from ...assetio.values import cname_value
from ...blender.collections import remap_copied_object_references
from ...blender.entity.skinning import (
    bind_skinned_objects_to_rig,
    clear_skinning_caches,
    component_skin_attachment_matrix,
)
from ...blender.entity.transforms import (
    EntityTransformResolver,
    build_slot_lookup,
    build_slot_owner_binding_maps,
    clear_pending_child_of_inverse_requests,
    clear_transform_caches,
    component_local_matrix,
    component_uses_skinning,
    configure_child_of_constraint,
    flush_pending_child_of_inverse_requests,
    is_live_armature_object,
    visual_scale_matrix,
)
from ...blender.facial.session import preload, stored_paths
from ...blender.light_channels import (
    rebuild_light_channel_links,
    retire_light_channel_volumes,
)
from ...blender.light_near_shadows import unblock_near_geometry
from ...blender.mesh_appearances import (
    APPEARANCE_NAME_KEY,
    record_collection_appearances,
)
from ...blender.reflection_probe_registry import mark_registered_reflection_probes_dirty
from ...blender.transactions import (
    BlenderImportTransaction,
    child_import_savepoint,
    raise_if_rollback_incomplete,
    rollback_import_child,
    rollback_report_message,
    track_created_datablock,
)
from ...core.log import get_logger, log_once, operation
from ...core.notifications import import_message
from ...entity.domain.entity_data import component_name
from ...gltf.submesh import submesh_index_for_object
from ...materials.blender.images import (
    begin_image_failure_capture,
    end_image_failure_capture,
    image_load_failure_message,
)
from ...materials.blender.multilayer import override_palette_batched
from ...materials.blender.skin_runtime import bind_skin_materials_for_object
from ...physics.services.repository import physics_resources_from_mesh_root
from ..common.cache import acquire_material_cache, release_material_cache
from ..common.destruction_chunks import (
    apply_to_master_sources,
    configured_depot_root,
    log_result,
    unresolved_warning,
)
from ..common.mesh_assets import (
    clear_submesh_index_cache,
    get_group,
    meshes_from_mesheswapps,
)
from ..common.progress import NO_PROGRESS, BlenderImportProgress
from ..common.results import ImportResult, summarize_messages, unique_messages
from .collisions import (
    AppearanceColliders,
    EntityCollisionRuntime,
    EntityCollisionService,
    collect_collider_components,
)
from .context import AppearanceExecutionContext, EntityHandlerOperations
from .execution_cache import (
    ComponentHandleLookup,
    build_chunk_lookup,
    build_component_pass_index,
    merge_component_groups,
)
from .handlers.animators import (
    EntityTransformAnimatorHandler,
    EntityTransformAnimatorService,
)
from .handlers.lights import (
    collect_light_channel_components,
    collect_light_components,
    create_auxiliary_component_registry,
)
from .handlers.meshes import (
    EntityMeshHandler,
    EntityMeshService,
    EntitySkinnedMeshOperations,
    EntitySkinnedMeshService,
    EntityStaticMeshOperations,
    EntityStaticMeshService,
)
from .handlers.widgets import create_widget_component_registry
from .options import EntityImportRequest
from .planner import compile_entity_import_plan, normalize_appearance_requests
from .policy import (
    APPEARANCE_PROXY_COMPONENT_TYPES,
    NON_VISUAL_MESH_COMPONENT_TYPES,
    chunk_mask_value,
    component_is_zero_mask_culled,
    is_component_enabled,
    is_excluded_mesh,
    is_shadow_mesh,
    light_component_skipped,
)
from .records import record_imported_appearance
from .registry import EntityComponentHandlerRegistry
from .resources import entity_index_extensions
from .rig_planning import is_animated_rig_component
from .rigs import EntityRigRuntime, EntityRigService, clear_rig_caches
from .session import EntityImportSession
from .transform_animator import (
    build_anim_impl_lookup,
    build_transform_animator_lookup,
)

_LOG = get_logger(__name__)


_ENTITY_COMPONENT_HANDLERS = EntityComponentHandlerRegistry()
_ENTITY_COMPONENT_HANDLERS.register(
    EntityTransformAnimatorHandler.component_types,
    EntityTransformAnimatorHandler(),
)
_ENTITY_COMPONENT_HANDLERS.register(
    EntityMeshHandler.component_types,
    EntityMeshHandler(),
)


def clear_transient_import_caches():
    clear_submesh_index_cache()
    clear_transform_caches()
    clear_skinning_caches()
    clear_rig_caches()


@dataclass(slots=True)
class _EntityRun:
    request: EntityImportRequest
    session: Any
    ent_name: str
    parsed_ent: Any
    appearances: list
    appearance_resolution: Any
    entity_source_path: str
    import_id: str
    coll_scene: Any
    parent_collection: Any
    vehicle_slot_components: list
    vehicle_slot_component_ids: set
    vehicle_slots: Any
    vehicle_slot_lookup: Any
    animation_files: Any
    masters: Any = None
    entity_plan: Any = None
    rig: Any = None
    rig_runtime: Any = None
    signature_mesh_cache: dict = field(default_factory=dict)
    embedded_physx_candidates: list = field(default_factory=list)
    appearance_colliders: Any = None

    @property
    def warnings(self):
        return self.session.warnings

    @property
    def cache(self):
        return self.session.execution_cache

    def mesh_is_excluded(self, depot_path, mesh_path, mesh_name, excluded):
        return self.session.execution_cache.mesh_excluded(
            depot_path,
            mesh_path,
            mesh_name,
            excluded,
            is_excluded_mesh,
        )

    def local_matrix(self, component):
        return self.session.execution_cache.component_local_matrix(
            component,
            component_local_matrix,
        )

    def visual_scale(self, component):
        return self.session.execution_cache.component_visual_scale(
            component,
            visual_scale_matrix,
        )


@dataclass(frozen=True, slots=True)
class _EntityOperations:
    handlers: Any
    static_meshes: Any
    skinned_meshes: Any
    lights: Any
    widgets: Any


@dataclass(frozen=True, slots=True)
class _AppearanceComponents:
    index: Any
    resolver: Any
    lights: tuple
    light_channels: tuple


def _warn_once(warnings, message):
    if message not in warnings:
        warnings.append(message)


def _component_depot_path(request, component):
    if type(component) is not dict:
        return depot_path(component, "mesh", "graphicsMesh", normalize=False)
    skipped = (
        component.get("$type") in NON_VISUAL_MESH_COMPONENT_TYPES
        or (
            component.get("$type") in APPEARANCE_PROXY_COMPONENT_TYPES
            and not request.include_proxies
        )
        or light_component_skipped(
            component.get("$type"),
            include_lights=request.include_lights,
            include_light_channels=request.light_channels_included,
        )
        or (
            not request.include_shadow_meshes
            and is_shadow_mesh(
                depot_path(component, "mesh", "graphicsMesh", normalize=False)
            )
        )
    )
    return (
        ""
        if skipped
        else depot_path(component, "mesh", "graphicsMesh", normalize=False)
    )


def _start_entity_session(request, progress):
    session = EntityImportSession(
        filepath=request.filepath,
        split_source_root=split_source_raw_root,
        provided_asset_index=request.asset_index,
        depot_root=request.depot_root,
        index_policy=request.index_policy,
        documents=request.documents,
        provided_material_resources=request.material_resources,
        clear_transient_caches=clear_transient_import_caches,
        component_depot_path=partial(_component_depot_path, request),
        component_mesh_appearance=lambda component: cname_value(
            component.get("meshAppearance") if type(component) is dict else None,
            "default",
        ),
        component_enabled=is_component_enabled,
        manage_master_visibility=request.manage_master_visibility,
        imported_collections_out=request.imported_collections_out,
        imported_rigs_out=request.imported_rigs_out,
        with_materials=request.with_materials,
        required_extensions=entity_index_extensions(
            include_animations=request.include_animations
            or request.include_facial_animations,
            include_physics=request.include_phys,
            include_inkwidgets=request.include_inkwidgets,
            include_facial_setup=request.include_facial_setup,
            include_lights=request.include_lights,
        ),
    )
    progress.set(0.0, "Preparing resources", force=True)
    try:
        session.start()
    except Exception:
        try:
            session.close()
        except Exception as close_error:
            _LOG.debug(
                "Entity session close after a failed start also failed: %s",
                close_error,
                exc_info=True,
            )
        raise
    progress.set(10.0, "Loading entity", force=True)
    return session


def _load_entity_run(request, session):
    filepath = request.filepath
    appearances = list(request.appearances)
    ent_name = os.path.basename(filepath)[:-9]
    _LOG.info(
        "Importing appearance(s) %s from entity %s",
        ", ".join(appearances),
        ent_name,
    )
    resources = session.resources
    parsed_ent = request.parsed_entity
    if parsed_ent is None and filepath is not None:
        parsed_ent = resources.load_entity(filepath)
    if parsed_ent is None:
        issues = resources.entities.issues
        reason = issues[-1].message if issues else filepath
        return ImportResult(
            failures=(f"Failed to load entity document: {reason}",),
            label="entity import",
        )

    # Seeded by the entity and the request, so importing the same entity with the same request repeats its choice.
    appearance_resolution = normalize_appearance_requests(
        parsed_ent,
        appearances,
        ent_name,
        choose=random.Random(f"{ent_name}|{'|'.join(map(str, appearances))}").choice,
    )
    for message in appearance_resolution.messages:
        _LOG.debug(message)

    slot_component = parsed_ent.vehicle_slot_component
    vehicle_slots = slot_component.get("slots") if slot_component else None
    parent_name = request.parent_collection_name
    return _EntityRun(
        request=request,
        session=session,
        ent_name=ent_name,
        parsed_ent=parsed_ent,
        appearances=list(appearance_resolution.appearances),
        appearance_resolution=appearance_resolution,
        entity_source_path=os.path.abspath(filepath),
        import_id=request.import_id or uuid.uuid4().hex,
        coll_scene=bpy.context.scene.collection,
        parent_collection=bpy.data.collections.get(parent_name)
        if parent_name
        else None,
        vehicle_slot_components=[slot_component] if slot_component else [],
        vehicle_slot_component_ids={id(slot_component)} if slot_component else set(),
        vehicle_slots=vehicle_slots,
        vehicle_slot_lookup=session.execution_cache.slot_lookup(
            vehicle_slots,
            build_slot_lookup,
        ),
        animation_files=(
            resources.files(".anims.glb", request.animation_files)
            if request.include_animations and request.animation_files is not None
            else ()
        ),
    )


def _plan_entity(run, progress):
    request, session = run.request, run.session
    resources = session.resources
    run.masters = session.ensure_masters(bpy, run.coll_scene)
    progress.set(15.0, "Planning entity", force=True)
    entity_plan = compile_entity_import_plan(
        parsed_entity=run.parsed_ent,
        appearances=run.appearances,
        appearance_indices=run.appearance_resolution.appearance_indices,
        default_appearance=run.appearance_resolution.default_appearance,
        source_root=session.source_root,
        asset_index=session.asset_index,
        load_app=resources.load_app,
        resolve_export=resources.resolve_export,
        component_mesh_info=resources.component_mesh_info,
        excluded_meshes=request.excluded_meshes,
        include_occluders=request.include_occluders,
        include_proxies=request.include_proxies,
        include_lights=request.include_lights,
        include_light_channels=request.light_channels_included,
        mesh_is_excluded=run.mesh_is_excluded,
    )
    for message in entity_plan.messages:
        _LOG.debug(message)
    run.warnings.extend(entity_plan.warnings)
    if not entity_plan.mesh_requirements:
        _LOG.debug(
            "No resolved mesh exports required by this entity; continuing "
            "with non-mesh components"
        )
    run.appearances = list(entity_plan.appearances)
    run.entity_plan = entity_plan


def _build_entity_rig(run, progress):
    request, resources = run.request, run.session.resources
    parsed_ent = run.parsed_ent
    progress.set(20.0, "Preparing rig", force=True)
    appearance_component_payloads = tuple(
        plan.appearance_components for plan in run.entity_plan.appearance_plans
    )
    # Animation GLBs are imported later for their animation data only. The entity rig
    # is always constructed exclusively from JSON rigs.
    rig_service = EntityRigService(
        resources=resources,
        source_root=run.session.source_root,
        entity_name=run.ent_name,
        animation_files=run.animation_files,
        animation_files_provider=(
            (lambda: resources.files(".anims.glb"))
            if request.include_animations and request.animation_files is None
            else None
        ),
        import_animations=request.include_animations,
        component_payloads=(
            parsed_ent.component_dicts,
            parsed_ent.component_data,
            *appearance_component_payloads,
        ),
        warnings=run.warnings,
    )
    rig_state = child_import_savepoint()
    try:
        rig_runtime = rig_service.build(
            run.entity_plan.rig, existing_rig=request.existing_rig
        )
    except Exception as error:
        if is_live_armature_object(request.existing_rig):
            raise
        # A rig that failed part-way is removed before the import continues without it.
        rollback_import_child(rig_state, f"entity rig for {run.ent_name}")
        message = (
            f"Entity rig setup skipped for {run.ent_name}: "
            f"{type(error).__name__}: {error}"
        )
        _LOG.warning("%s", message, exc_info=True)
        _warn_once(run.warnings, message)
        rig_runtime = EntityRigRuntime(
            ordered_components=tuple(run.entity_plan.rig.ordered_components),
        )
    run.rig = run.session.register_rig(rig_runtime.rig)
    run.rig_runtime = rig_runtime
    if request.include_facial_setup and is_live_armature_object(run.rig):
        _preload_facial_setup(
            run,
            rig_service,
            (parsed_ent.component_data, *appearance_component_payloads),
        )


def _preload_facial_setup(run, rig_service, payloads):
    try:
        facial_warning = preload(run.rig, run.session.resources, payloads)
    except (
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        KeyError,
    ) as error:
        facial_warning = f"Facial setup preload failed: {error}"
    if facial_warning:
        run.warnings.append(facial_warning)
        _LOG.warning("%s", facial_warning)
    elif run.request.include_facial_animations:
        _setup_path, face_rig_path = stored_paths(run.rig)
        if face_rig_path:
            rig_service.import_facial_animations(run.rig_runtime, face_rig_path)


def _import_mesh_masters(run, progress):
    session = run.session
    progress.set(30.0, "Preparing mesh masters", force=True)
    meshes_w_apps = {
        requirement.key: {
            "apps": [list(requirement.appearances)],
            "sectors": [requirement.sector] if requirement.sector else [],
            "meshpath": requirement.mesh_path,
        }
        for requirement in run.entity_plan.mesh_requirements
    }
    mesh_import_failures = meshes_from_mesheswapps(
        meshes_w_apps,
        asset_index=session.asset_index,
        from_mesh_no=0,
        to_mesh_no=10000000,
        with_mats=run.request.with_materials,
        Masters=run.masters,
        mesh_repository=session.resources.meshes,
        document_session=session.documents,
        material_resources=session.material_resources,
        progress=progress.span(30.0, 50.0),
    )
    for message in mesh_import_failures:
        _warn_once(run.warnings, message)
    destruction = apply_to_master_sources(
        run.masters,
        run.request.destruction_chunks,
        (requirement.mesh_path for requirement in run.entity_plan.mesh_requirements),
        depot_root=configured_depot_root(run.request.depot_root),
    )
    log_result(destruction, "Entity")
    if warning := unresolved_warning(destruction["unresolved"]):
        _warn_once(run.warnings, warning)


def _entity_operations(run):
    request, resources = run.request, run.session.resources
    mesh_helpers = {
        "component_mesh_info": resources.component_mesh_info,
        "resolve_master_group": resources.resolve_master_group,
        "master_group_plan": resources.master_group_plan,
        "master_group_submesh_indexes": resources.master_group_submesh_indexes,
        "get_group": get_group,
        "is_excluded_mesh": run.mesh_is_excluded,
        "remap_copied_object_references": remap_copied_object_references,
        "component_is_zero_mask_culled": component_is_zero_mask_culled,
        "chunk_mask_value": chunk_mask_value,
        "submesh_index_for_object": submesh_index_for_object,
        "visual_scale_matrix": run.visual_scale,
    }
    return _EntityOperations(
        handlers=EntityHandlerOperations(
            is_component_enabled=is_component_enabled,
            configure_child_of_constraint=configure_child_of_constraint,
            visual_scale_matrix=run.visual_scale,
        ),
        static_meshes=EntityStaticMeshOperations(
            **mesh_helpers,
            configure_child_of_constraint=configure_child_of_constraint,
        ),
        skinned_meshes=EntitySkinnedMeshOperations(
            **mesh_helpers,
            bind_skinned_objects_to_rig=partial(
                bind_skinned_objects_to_rig,
                bind_materials=bind_skin_materials_for_object,
            ),
        ),
        lights=(
            create_auxiliary_component_registry()
            if request.include_lights or request.light_channels_included
            else None
        ),
        widgets=(
            create_widget_component_registry() if request.include_inkwidgets else None
        ),
    )


def _import_appearances(run, operations, progress):
    include_inkwidgets = run.request.include_inkwidgets
    appearance_plans = run.entity_plan.appearance_plans
    appearance_units = sum(
        1
        + len(plan.component_index.transform_animator_components)
        + len(plan.component_index.mesh_components)
        + (len(plan.component_index.widget_components) if include_inkwidgets else 0)
        for plan in appearance_plans
    )
    appearance_progress = progress.span(50.0, 88.0).counter(
        "Importing appearance components",
        appearance_units,
    )
    collections = [
        _import_appearance(run, operations, index, appearance_plan, appearance_progress)
        for index, appearance_plan in enumerate(appearance_plans)
    ]
    appearance_progress.finish(detail="Appearances complete")
    if len(collections) > 1:
        # Like a mesh's appearances, only the default shows until another is displayed from the Appearances tab.
        default = run.appearance_resolution.default_appearance
        shown = next(
            (
                collection
                for collection, plan in zip(collections, appearance_plans)
                if default in (plan.resolved_name, plan.display_name)
            ),
            collections[0],
        )
        record_collection_appearances(
            bpy.context.scene, run.import_id, collections, shown
        )


def _appearance_collection(run, index, appearance_plan):
    display_app_name = appearance_plan.display_name
    ent_coll = track_created_datablock(
        "collections",
        bpy.data.collections.new(run.ent_name + "_" + display_app_name),
    )
    (run.parent_collection or run.coll_scene).children.link(ent_coll)
    ent_coll["depotPath"] = run.session.source_relative_path
    ent_coll["cp77_entity_imported"] = True
    ent_coll["cp77_entity_source"] = run.entity_source_path
    run.session.register_collection(ent_coll)
    ent_coll["appearanceName"] = appearance_plan.resolved_name
    ent_coll["cp77_requested_appearance_name"] = appearance_plan.requested_name
    ent_coll[APPEARANCE_NAME_KEY] = display_app_name
    if is_live_armature_object(run.rig):
        _record_rig_source_order(run, index, appearance_plan, ent_coll)
    return ent_coll


def _record_rig_source_order(run, index, appearance_plan, ent_coll):
    rig_runtime = run.rig_runtime
    base_source_order = tuple(rig_runtime.base_source_rig_paths)
    overlay_source_order = []
    seen_overlay_paths = set()
    for rig_component in appearance_plan.appearance_components:
        if not is_animated_rig_component(rig_component):
            continue
        rig_depot = depot_path(rig_component, "rig", normalize=False)
        rig_path = run.session.resources.resolve_rig(rig_depot) or ""
        rig_key = local_path_key(rig_path) if rig_path else ""
        if not rig_path or rig_key in seen_overlay_paths:
            continue
        seen_overlay_paths.add(rig_key)
        overlay_source_order.append(rig_path)
    source_order = tuple(dict.fromkeys((*base_source_order, *overlay_source_order)))
    if source_order:
        ent_coll["cp77_rig_source_order"] = json.dumps(
            list(source_order), separators=(",", ":")
        )
    ent_coll["cp77_rig_base_source_order"] = json.dumps(
        list(base_source_order), separators=(",", ":")
    )
    ent_coll["cp77_rig_overlay_source_order"] = json.dumps(
        list(overlay_source_order), separators=(",", ":")
    )
    if index == 0 and rig_runtime.ordered_rig_paths:
        ent_coll["cp77_rig_merge_order"] = json.dumps(
            list(rig_runtime.ordered_rig_paths), separators=(",", ":")
        )


def _appearance_lookups(run, appearance_plan, chunks):
    if appearance_plan.parsed_app is None:
        return (
            build_chunk_lookup(chunks, "parentTransform", cache=run.cache),
            build_chunk_lookup(chunks, "skinning", cache=run.cache),
            build_chunk_lookup(chunks, "shape", cache=run.cache),
            (),
        )
    parsed_app = appearance_plan.parsed_app
    name = appearance_plan.parsed_app_name
    return (
        parsed_app.parent_transform_lookup_by_appearance_name.get(name, {}),
        parsed_app.skinning_lookup_by_appearance_name.get(name, {}),
        parsed_app.shape_lookup_by_appearance_name.get(name, {}),
        parsed_app.light_channels_by_appearance_name.get(name, ()),
    )


def _appearance_components(run, appearance_plan, chunks, app_light_channels):
    request, parsed_ent = run.request, run.parsed_ent
    appearance_index = appearance_plan.component_index
    light_channel_components = ()
    light_components = ()
    if request.light_channels_included:
        light_channel_components = run.cache.collect_components(
            "light_channels",
            (
                app_light_channels,
                chunks,
                appearance_index.components,
                parsed_ent.light_channel_components,
            ),
            collect_light_channel_components,
        )
    if request.include_lights:
        light_components = run.cache.collect_components(
            "lights",
            (parsed_ent.component_data, chunks, appearance_index.components),
            collect_light_components,
        )
    resolver_components, resolver_component_token = merge_component_groups(
        appearance_index.components,
        light_channel_components,
        light_components,
    )
    return _AppearanceComponents(
        index=appearance_index,
        resolver=build_component_pass_index(
            resolver_components,
            run.cache,
            identity_token=resolver_component_token,
        ),
        lights=light_components,
        light_channels=light_channel_components,
    )


def _appearance_handle_lookups(run, components, lookups):
    parsed_ent = run.parsed_ent
    root_component_ids = parsed_ent.component_ids | parsed_ent.component_data_ids
    parent_transform_lookup = ComponentHandleLookup(lookups[0])
    skinning_lookup = ComponentHandleLookup(lookups[1])
    shape_lookup = ComponentHandleLookup(lookups[2])
    for comp in components.resolver.components:
        if id(comp) in root_component_ids:
            parent_transform_lookup.set_component_lookup(
                comp, parsed_ent.parent_transform_lookup
            )
            skinning_lookup.set_component_lookup(comp, parsed_ent.skinning_lookup)
            shape_lookup.set_component_lookup(comp, parsed_ent.shape_lookup)
    rig_json_paths = run.rig_runtime.rig_json_path_by_component_name
    for comp in components.resolver.rig_components:
        rig_name = component_name(comp)
        if rig_name and rig_name not in rig_json_paths:
            _LOG.warning(
                "animated component '%s' was not present in the ordered JSON rig prepass; leaving it unmerged",
                rig_name,
            )
    return parent_transform_lookup, skinning_lookup, shape_lookup


def _update_vehicle_slots(run, components):
    for c in components.index.slot_components:
        if (
            component_name(c) in ("vehicle_slots", "slot", "slots")
            and id(c) not in run.vehicle_slot_component_ids
        ):
            run.vehicle_slot_components.append(c)
            run.vehicle_slot_component_ids.add(id(c))
    if not run.vehicle_slots and run.vehicle_slot_components:
        run.vehicle_slots = run.vehicle_slot_components[0]["slots"]
        run.vehicle_slot_lookup = run.cache.slot_lookup(
            run.vehicle_slots,
            build_slot_lookup,
        )


def _resolver_slot_lookups(run, components):
    base_slot_component_lookups = run.parsed_ent.slot_component_lookups
    lookups = dict(base_slot_component_lookups)
    for comp in components.resolver.slot_components:
        name = component_name(comp)
        if not name:
            continue
        if (
            id(comp) in run.parsed_ent.component_ids
            and name in base_slot_component_lookups
        ):
            continue
        lookups[name] = run.cache.slot_lookup(comp.get("slots"), build_slot_lookup)
    return lookups


def _skin_placements(run, components, skinned_components_by_id):
    placements, placement_info = {}, {}
    rig_j = run.rig_runtime.rig_json
    if rig_j is None:
        return placements, placement_info
    for component in components.resolver.mesh_components:
        component_id = id(component)
        if component_id not in skinned_components_by_id:
            continue
        placement, root_bone, status = run.cache.skin_attachment(
            component,
            rig_j,
            run.session.resources.component_mesh_json,
            component_skin_attachment_matrix,
        )
        placement_info[component_id] = (root_bone, status)
        if placement is not None:
            placements[component_id] = placement
    return placements, placement_info


def _appearance_transform_resolver(run, components, lookups, placements):
    parent_transform_lookup, skinning_lookup = lookups
    rig_runtime = run.rig_runtime
    rig_json_by_component_name = rig_runtime.rig_json_by_component_name
    slot_owner_rig_jsons, slot_owner_rig_owner_names = build_slot_owner_binding_maps(
        components.resolver.slot_components,
        parent_transform_lookup,
        rig_json_by_component_name,
        frozenset(rig_json_by_component_name),
    )
    _update_vehicle_slots(run, components)
    return EntityTransformResolver(
        components.resolver.components,
        parent_transform_lookup,
        skinning_lookup=skinning_lookup,
        rig=run.rig,
        rig_j=rig_runtime.rig_json,
        rig_bone_index=rig_runtime.rig_bone_index,
        default_slot_lookup=run.vehicle_slot_lookup,
        slot_owner_rig_jsons=slot_owner_rig_jsons,
        rig_json_by_component_name=rig_json_by_component_name,
        rig_json_by_bone_name=rig_runtime.rig_json_by_bone_name,
        armature_by_component_name=rig_runtime.armature_by_component_name,
        slot_owner_rig_owner_names=slot_owner_rig_owner_names,
        components_by_name=components.resolver.by_name,
        slot_component_lookups=_resolver_slot_lookups(run, components),
        component_skin_placements=placements,
        local_matrix_resolver=run.local_matrix,
    )


def _collect_embedded_physics(run, components, transform_resolver):
    resources = run.session.resources
    for component in components.resolver.mesh_components:
        mesh_depot_path, _mesh_name, mesh_path, _appearance, enabled = (
            resources.component_mesh_info(component)
        )
        if not enabled:
            continue
        resources_in_mesh = physics_resources_from_mesh_root(
            resources.component_mesh_json(component),
            mesh_path or mesh_depot_path,
        )
        if not resources_in_mesh:
            continue
        component_matrix = transform_resolver.resolve_component_matrix(component)[0]
        for physics_resource in resources_in_mesh:
            run.embedded_physx_candidates.append(
                (physics_resource, component_matrix.copy())
            )


def _collect_appearance_colliders(run, appearance_plan, chunks, transform_resolver):
    parsed_ent = run.parsed_ent
    root_component_ids = parsed_ent.component_ids | parsed_ent.component_data_ids
    # A collider both files carry imports once, from the entity.
    colliders = tuple(
        component
        for component in run.cache.collect_components(
            "colliders",
            (
                parsed_ent.component_data,
                chunks,
                appearance_plan.component_index.components,
            ),
            collect_collider_components,
        )
        if id(component) not in root_component_ids
    )
    if colliders:
        run.appearance_colliders = AppearanceColliders(
            components=colliders,
            transform_resolver=transform_resolver,
            handle_sources=(
                appearance_plan.appearance_components,
                appearance_plan.chunks,
            ),
        )


def _appearance_handler_context(run, operations, setup):
    ent_coll, app_name, transform_resolver, lookups, skinned, placement_info = setup
    request = run.request
    transform_animators = EntityTransformAnimatorService(
        ent_coll,
        lookups[0],
        lookups[3],
        transform_resolver,
        configure_child_of_constraint,
    )
    static_meshes = EntityStaticMeshService(
        entity_collection=ent_coll,
        appearance_name=app_name,
        masters=run.masters,
        excluded_meshes=request.excluded_meshes,
        transform_resolver=transform_resolver,
        transform_animators=transform_animators,
        operations=operations.static_meshes,
        warnings=run.warnings,
    )
    skinned_meshes = EntitySkinnedMeshService(
        entity_collection=ent_coll,
        appearance_name=app_name,
        masters=run.masters,
        excluded_meshes=request.excluded_meshes,
        transform_resolver=transform_resolver,
        transform_animators=transform_animators,
        rig=run.rig,
        component_skin_placement_info=placement_info,
        operations=operations.skinned_meshes,
        warnings=run.warnings,
    )
    mesh_service = EntityMeshService(
        static_meshes,
        skinned_meshes,
        lambda component, components=skinned: (
            components.get(id(component)) is component
        ),
        include_occluders=request.include_occluders,
        include_proxies=request.include_proxies,
    )
    return AppearanceExecutionContext(
        filepath=request.filepath,
        appearance_name=app_name,
        entity_collection=ent_coll,
        transform_resolver=transform_resolver,
        shape_lookup=lookups[2],
        transform_animators=transform_animators,
        meshes=mesh_service,
        static_meshes=static_meshes,
        skinned_meshes=skinned_meshes,
        operations=operations.handlers,
        resolve_export=run.session.resources.resolve_export,
    )


def _import_appearance(run, operations, index, appearance_plan, appearance_progress):
    request = run.request
    display_app_name = appearance_plan.display_name
    app_name = appearance_plan.resolved_name
    _LOG.info(
        "Importing appearance %d of %d: %s",
        index + 1,
        len(run.entity_plan.appearance_plans),
        display_app_name,
    )
    appearance_progress.note(display_app_name, force=True)
    app_start_time = time.time()
    ent_coll = _appearance_collection(run, index, appearance_plan)
    chunks = appearance_plan.chunks or run.parsed_ent.component_data
    lookups = _appearance_lookups(run, appearance_plan, chunks)
    components = _appearance_components(run, appearance_plan, chunks, lookups[3])
    parent_transform_lookup, skinning_lookup, shape_lookup = _appearance_handle_lookups(
        run, components, lookups
    )
    transform_animator_lookup = build_transform_animator_lookup(
        components.resolver.transform_animator_components,
        build_anim_impl_lookup(chunks),
    )
    skinned_components_by_id = {
        id(component): component
        for component in components.resolver.mesh_components
        if run.cache.uses_skinning(component, skinning_lookup, component_uses_skinning)
    }
    placements, placement_info = _skin_placements(
        run, components, skinned_components_by_id
    )
    transform_resolver = _appearance_transform_resolver(
        run, components, (parent_transform_lookup, skinning_lookup), placements
    )
    if index == 0 and request.include_collisions and request.include_mesh_colliders:
        _collect_embedded_physics(run, components, transform_resolver)
    if index == 0 and request.include_collisions and request.include_entity_colliders:
        _collect_appearance_colliders(run, appearance_plan, chunks, transform_resolver)
    handler_context = _appearance_handler_context(
        run,
        operations,
        (
            ent_coll,
            app_name,
            transform_resolver,
            (
                parent_transform_lookup,
                skinning_lookup,
                shape_lookup,
                transform_animator_lookup,
            ),
            skinned_components_by_id,
            placement_info,
        ),
    )
    appearance_progress.advance(detail=f"{display_app_name}: setup")
    _run_animator_components(
        run, components.index, handler_context, appearance_progress, display_app_name
    )
    _run_mesh_components(
        run,
        operations,
        components.index,
        handler_context,
        (appearance_progress, display_app_name),
    )
    if operations.widgets is not None:
        _run_widget_components(
            run,
            operations,
            components.index,
            handler_context,
            (appearance_progress, display_app_name),
        )
    if operations.lights is not None:
        appearance_progress.note(f"{display_app_name}: lights", force=True)
        _run_light_components(run, operations, components, handler_context)
    _record_appearance(run, appearance_plan, ent_coll, app_name)
    _LOG.debug(
        "Appearance %s imported in %.3f seconds",
        display_app_name,
        time.time() - app_start_time,
    )
    return ent_coll


def _run_animator_components(
    run, appearance_index, handler_context, appearance_progress, display_app_name
):
    for c in appearance_index.transform_animator_components:
        comp_name = component_name(c)
        child_state = child_import_savepoint()
        try:
            _ENTITY_COMPONENT_HANDLERS.execute(c, handler_context)
        except Exception as error:
            rollback_import_child(child_state, f"animator component {comp_name}")
            _LOG.error("Failed on animator component %s", comp_name, exc_info=True)
            _warn_once(
                run.warnings,
                f"Animator component failed for {comp_name}: "
                f"{type(error).__name__}: {error}",
            )
        finally:
            appearance_progress.advance(
                detail=f"{display_app_name}: {comp_name or 'animator'}"
            )


def _run_mesh_component(operations, c, handler_context):
    handler = _ENTITY_COMPONENT_HANDLERS.handler_for(c)
    if handler is None and operations.lights is not None:
        handler = operations.lights.handler_for(c)
    if handler is None:
        return handler_context.meshes.execute(c)
    return handler.execute(c, handler_context)


def _run_mesh_components(run, operations, appearance_index, handler_context, progress):
    request = run.request
    appearance_progress, display_app_name = progress
    for c in appearance_index.mesh_components:
        if light_component_skipped(
            c.get("$type"),
            include_lights=request.include_lights,
            include_light_channels=request.light_channels_included,
        ):
            appearance_progress.advance(
                detail=f"{display_app_name}: skipped light mesh"
            )
            continue
        comp_name = component_name(c)
        child_state = child_import_savepoint()
        try:
            component_result = _run_mesh_component(operations, c, handler_context)
            if comp_name and isinstance(component_result, bpy.types.Collection):
                handler_context.state.setdefault("component_collections", {})[
                    comp_name
                ] = component_result
        except Exception as error:
            rollback_import_child(child_state, f"entity component {comp_name}")
            message = (
                f"Entity component skipped for {comp_name}: "
                f"{type(error).__name__}: {error}"
            )
            # Handlers name the asset they were importing in the exception's notes.
            for note in getattr(error, "__notes__", ()):
                message += f"; {note}"
            _LOG.warning("%s", message, exc_info=True)
            _warn_once(run.warnings, message)
        finally:
            appearance_progress.advance(
                detail=f"{display_app_name}: {comp_name or 'component'}"
            )


def _run_widget_components(
    run, operations, appearance_index, handler_context, progress
):
    appearance_progress, display_app_name = progress
    for c in appearance_index.widget_components:
        comp_name = component_name(c)
        child_state = child_import_savepoint()
        try:
            operations.widgets.execute(c, handler_context)
        except Exception as error:
            rollback_import_child(
                child_state,
                f"ink widget component {comp_name}",
            )
            message = (
                f"ink widget component skipped for {comp_name}: "
                f"{type(error).__name__}: {error}"
            )
            _LOG.warning("%s", message, exc_info=True)
            _warn_once(run.warnings, message)
        finally:
            appearance_progress.advance(
                detail=f"{display_app_name}: {comp_name or 'ink widget'}"
            )
    for message in handler_context.state.get("widget_warnings", ()):
        _warn_once(run.warnings, message)


def _run_light_components(run, operations, components, handler_context):
    for c in (*components.lights, *components.light_channels):
        comp_name = component_name(c)
        child_state = child_import_savepoint()
        try:
            operations.lights.execute(c, handler_context)
        except Exception as error:
            rollback_import_child(child_state, f"light component {comp_name}")
            message = (
                f"Light component skipped for {comp_name}: "
                f"{type(error).__name__}: {error}"
            )
            _LOG.warning("%s", message, exc_info=True)
            _warn_once(run.warnings, message)


def _record_appearance(run, appearance_plan, ent_coll, app_name):
    ent_apps = run.parsed_ent.appearances
    entry_index = appearance_plan.entity_appearance_index
    record_imported_appearance(
        ent_coll,
        import_id=run.import_id,
        ent_path=run.entity_source_path,
        app_path=appearance_plan.app_resource_path,
        app_depot=appearance_plan.app_resource_depot,
        appearance=app_name,
        entry_name=(
            cname_value(ent_apps[entry_index].get("name"), "")
            if entry_index is not None and 0 <= entry_index < len(ent_apps)
            else ""
        ),
        mesh_cache=run.signature_mesh_cache,
    )


def _import_entity_collisions(run, operations):
    request = run.request
    imported_collections = run.session.imported_collections
    rig_runtime = run.rig_runtime
    collision_service = EntityCollisionService(
        EntityCollisionRuntime(
            parsed_entity=run.parsed_ent,
            resources=run.session.resources,
            rig=run.rig,
            rig_json=rig_runtime.rig_json,
            rig_bone_index=rig_runtime.rig_bone_index,
            vehicle_slot_lookup=run.vehicle_slot_lookup,
            rig_json_by_component_name=rig_runtime.rig_json_by_component_name,
            rig_json_by_bone_name=rig_runtime.rig_json_by_bone_name,
            armature_by_component_name=rig_runtime.armature_by_component_name,
            lookup_factory=ComponentHandleLookup,
            target_collection=(
                imported_collections[0] if imported_collections else run.coll_scene
            ),
            blender_context=bpy.context,
            operations=operations.handlers,
            embedded_physics=tuple(run.embedded_physx_candidates),
            appearance_colliders=run.appearance_colliders,
        )
    )
    child_state = child_import_savepoint()
    try:
        collision_service.execute(
            include_collisions=request.include_collisions,
            include_phys=request.include_phys,
            include_entity_colliders=request.include_entity_colliders,
            include_mesh_colliders=request.include_mesh_colliders,
        )
    except Exception as error:
        rollback_import_child(child_state, f"entity collision import {run.ent_name}")
        message = (
            f"Entity collision import skipped for {run.ent_name}: "
            f"{type(error).__name__}: {error}"
        )
        _LOG.warning("%s", message, exc_info=True)
        _warn_once(run.warnings, message)


def _import_entity_contents(run, progress):
    _plan_entity(run, progress)
    _build_entity_rig(run, progress)
    _import_mesh_masters(run, progress)
    operations = _entity_operations(run)
    _import_appearances(run, operations, progress)
    progress.set(88.0, "Importing collisions", force=True)
    if run.request.include_collisions:
        _import_entity_collisions(run, operations)


def _finish_child_of_inverse(warnings):
    inverse_stats = flush_pending_child_of_inverse_requests()
    if not inverse_stats["requested"]:
        return
    _LOG.debug(
        "Entity Child Of native inverse: %d request(s), %d pending, "
        "%d transform mismatch(es), max translation %.6f, max basis %.6f",
        inverse_stats["requested"],
        inverse_stats["pending"],
        inverse_stats["mismatches"],
        inverse_stats["max_translation_error"],
        inverse_stats["max_basis_error"],
    )
    if inverse_stats["pending"] or inverse_stats["mismatches"]:
        message = (
            "Entity Child Of native inverse verification: "
            f"{inverse_stats['pending']} pending, "
            f"{inverse_stats['mismatches']} transform mismatch(es), "
            f"max translation {inverse_stats['max_translation_error']:.6f}, "
            f"max basis {inverse_stats['max_basis_error']:.6f}"
        )
        if inverse_stats.get("examples"):
            message += "; examples: " + ", ".join(inverse_stats["examples"])
        _LOG.warning("%s", message)
        _warn_once(warnings, message)


def _link_entity_light_channels(request, session, warnings):
    try:
        bpy.context.view_layer.update()
        for imported_collection in session.imported_collections:
            if request.lights_linked:
                summary = rebuild_light_channel_links(
                    imported_collection,
                    mode="ENTITY",
                )
                _LOG.debug(
                    "Entity light channels %s: %d volume(s), %d receiver(s), "
                    "%d/%d linked, %d unresolved",
                    imported_collection.name,
                    summary["volumes"],
                    summary["receivers"],
                    summary["linked"],
                    summary["lights"],
                    summary["unresolved"],
                )
                unblock_near_geometry(imported_collection)
            if not request.light_channel_volumes_kept:
                retire_light_channel_volumes(
                    imported_collection, tuple(imported_collection.all_objects)
                )
        mark_registered_reflection_probes_dirty(bpy.context.scene)
    except Exception as error:
        message = (
            f"Entity light-channel linking skipped: {type(error).__name__}: {error}"
        )
        _LOG.warning("%s", message, exc_info=True)
        _warn_once(warnings, message)


def _finish_entity_import(request, session, image_failures, progress):
    warning_messages = session.warnings
    progress.set(94.0, "Finalizing constraints", force=True)
    if not request.defer_child_of_inverse:
        _finish_child_of_inverse(warning_messages)
    if request.lights_linked or (
        request.light_channels_included and not request.light_channel_volumes_kept
    ):
        _link_entity_light_channels(request, session, warning_messages)
    session.collect_document_issues()
    progress.set(100.0, "Complete", force=True)
    if request.transactional:
        texture_message = image_load_failure_message(image_failures)
        if texture_message:
            warning_messages.append(texture_message)
    warnings = unique_messages(warning_messages)
    if warnings:
        import_message(
            summarize_messages(warnings, root=session.source_root), logger=_LOG
        )
    cache_stats = session.execution_cache.stats()
    _LOG.debug(
        "Entity execution cache: %d hits, %d misses",
        cache_stats["hits"],
        cache_stats["misses"],
    )
    return ImportResult(
        created_items=tuple(session.imported_collections),
        warnings=warnings,
        label="entity import",
    )


@override_palette_batched
def _import_entity_impl(request: EntityImportRequest, *, progress=NO_PROGRESS):
    """Import one entity from a normalized request"""

    if not isinstance(request, EntityImportRequest):
        raise TypeError("request must be an EntityImportRequest")

    session = _start_entity_session(request, progress)
    rig = None
    material_cache_acquired = False
    image_failures = begin_image_failure_capture()
    try:
        material_cache_acquired = acquire_material_cache(request.with_materials)
        run = _load_entity_run(request, session)
        if isinstance(run, ImportResult):
            return run
        parsed_ent = run.parsed_ent
        if (
            not parsed_ent.appearances
            and len(parsed_ent.component_dicts) < 1
            and not parsed_ent.component_data
        ):
            message = (
                "The entity contains no importable components and no appearance "
                "documents were found"
            )
            _LOG.warning("%s", message)
            return ImportResult(
                warnings=(message,),
                label="entity import",
            )
        try:
            _import_entity_contents(run, progress)
        finally:
            rig = run.rig
        return _finish_entity_import(request, session, image_failures, progress)
    finally:
        end_image_failure_capture(image_failures)
        try:
            session.close(rig)
        finally:
            release_material_cache(material_cache_acquired)


def _retain_live_output(output, datablocks):
    if output is None:
        return
    retained = []
    for item in tuple(output):
        try:
            if datablocks.get(item.name) is item:
                retained.append(item)
        except (AttributeError, ReferenceError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_retain_live_output 1", type(error).__name__),
                "retain live output: fell back after %s",
                error,
                exc_info=True,
            )
    try:
        output[:] = retained
    except (AttributeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_retain_live_output 2", type(error).__name__),
            "retain live output: fell back after %s",
            error,
            exc_info=True,
        )


def _clear_rolled_back_outputs(request):
    _retain_live_output(request.imported_collections_out, bpy.data.collections)
    _retain_live_output(request.imported_rigs_out, bpy.data.objects)


def _import_entity_transactional(request: EntityImportRequest, *, progress=NO_PROGRESS):
    if not isinstance(request, EntityImportRequest):
        raise TypeError("request must be an EntityImportRequest")
    if not request.transactional:
        return _import_entity_impl(
            request,
            progress=progress,
            _override_palette_owner=request.report_owner,
        )
    transaction = BlenderImportTransaction(capture_existing_state=False)
    try:
        with transaction.scope():
            result = _import_entity_impl(
                request,
                progress=progress,
                _override_palette_owner=request.report_owner,
            )
    except Exception as error:
        report = transaction.rollback()
        if not request.defer_child_of_inverse:
            clear_pending_child_of_inverse_requests()
        _clear_rolled_back_outputs(request)
        raise_if_rollback_incomplete(report, error)
        raise
    if result.failures:
        report = transaction.rollback()
        if not request.defer_child_of_inverse:
            clear_pending_child_of_inverse_requests()
        _clear_rolled_back_outputs(request)
        failures = list(result.failures)
        rollback_error = rollback_report_message(report)
        if rollback_error:
            failures.append("Rollback incomplete: " + rollback_error)
        _LOG.error(
            "Entity import failed: %s",
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
    return result


def import_entity(request: EntityImportRequest, *, progress=None):
    if not isinstance(request, EntityImportRequest):
        raise TypeError("request must be an EntityImportRequest")
    filepath = getattr(request, "filepath", "") or ""
    entity_name = os.path.basename(filepath)
    entity_name = entity_name.removesuffix(".ent.json")
    appearance_values = tuple(getattr(request, "appearances", ()) or ())
    appearances = ",".join(appearance_values[:5])
    if len(appearance_values) > 5:
        appearances += f",+{len(appearance_values) - 5}"
    if not request.defer_child_of_inverse:
        clear_pending_child_of_inverse_requests()
    with operation(
        _LOG,
        f"entity import {entity_name}",
        entity=entity_name,
        appearances=appearances,
    ):
        if progress is not None:
            return _import_entity_transactional(request, progress=progress)
        with BlenderImportProgress(bpy.context, "Entity Import") as user_progress:
            return _import_entity_transactional(request, progress=user_progress)
