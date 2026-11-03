from __future__ import annotations
<<<<<<< Updated upstream
from ...blender.transactions import track_created_datablock

import os
import random
import time
import traceback

import bpy
from ...addon_identity import get_addon_preferences
from .planner import compile_entity_import_plan, normalize_appearance_requests
from .policy import (
    APPEARANCE_PROXY_COMPONENT_TYPES,
    LIGHT_RELATED_COMPONENT_TYPES,
    NON_VISUAL_MESH_COMPONENT_TYPES,
    chunk_mask_value,
    component_is_zero_mask_culled,
    is_component_enabled,
    is_excluded_mesh,
)
from .session import EntityImportSession
from .resources import split_source_raw_root
=======

import json
import os
import random
import time
import uuid

import bpy

from ...assetio.paths import local_path_key, split_source_raw_root
from ...assetio.values import cname_value
from ...blender.facial.session import preload, stored_paths
from ...blender.transactions import (
    BlenderImportTransaction,
    child_import_savepoint,
    raise_if_rollback_incomplete,
    rollback_import_child,
    rollback_report_message,
    track_created_datablock,
)
from ...core.log import debug_exception, get_logger, log_once, operation
from ...core.notifications import import_message
from ...materials.blender.images import (
    begin_image_failure_capture,
    end_image_failure_capture,
    image_load_failure_message,
)
from ...materials.blender.multilayer import override_palette_batched
from ...physics.services.repository import physics_resources_from_mesh_root
from ..common.cache import acquire_material_cache, release_material_cache
from ..common.collections import remap_copied_object_references
from ..common.entity_data import component_name
from ..common.light_channels import (
    rebuild_light_channel_links,
    retire_light_channel_volumes,
)
from ..common.mesh_assets import (
    clear_submesh_index_cache,
    get_group,
    meshes_from_mesheswapps,
    submesh_index_for_object,
)
from ..common.paths import depot_path
from ..common.progress import NO_PROGRESS, BlenderImportProgress
from ..common.reflection_probe_registry import mark_registered_reflection_probes_dirty
from ..common.results import ImportResult, summarize_messages, unique_messages
from .context import AppearanceExecutionContext, EntityHandlerOperations
>>>>>>> Stashed changes
from .execution_cache import (
    ComponentHandleLookup,
    build_chunk_lookup,
    build_component_pass_index,
    merge_component_groups,
)
<<<<<<< Updated upstream
from .options import EntityImportRequest
from .context import AppearanceExecutionContext, EntityHandlerOperations
from .handlers.animators import (
    EntityTransformAnimatorHandler,
    EntityTransformAnimatorService,
    build_anim_impl_lookup,
    build_transform_animator_lookup,
=======
from .handlers.animators import (
    EntityTransformAnimatorHandler,
    EntityTransformAnimatorService,
>>>>>>> Stashed changes
)
from .handlers.meshes import (
    EntityMeshHandler,
    EntityMeshService,
    EntitySkinnedMeshOperations,
    EntitySkinnedMeshService,
    EntityStaticMeshOperations,
    EntityStaticMeshService,
)
<<<<<<< Updated upstream
from .registry import EntityComponentHandlerRegistry
from .rigs import EntityRigRuntime, EntityRigService, clear_rig_caches
from .rig_planning import is_animated_rig_component
from ..common.entity_data import component_name
from ..common.paths import depot_path_value
from ...assetio.values import cname_value
=======
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
>>>>>>> Stashed changes
from .skinning import (
    bind_skinned_objects_to_rig,
    clear_skinning_caches,
    component_skin_attachment_matrix,
)
<<<<<<< Updated upstream
=======
from .transform_animator import (
    build_anim_impl_lookup,
    build_transform_animator_lookup,
)
>>>>>>> Stashed changes
from .transforms import (
    EntityTransformResolver,
    build_slot_lookup,
    build_slot_owner_binding_maps,
<<<<<<< Updated upstream
    clear_transform_caches,
    child_of_inverse_matrix,
    component_uses_skinning,
    configure_child_of_constraint,
    visual_scale_matrix,
)
from ..common.collections import _remap_copied_object_references
from ..common.cache import acquire_material_cache, release_material_cache
from ..common.results import ImportResult, unique_messages
from ...blender.transactions import (
    BlenderImportTransaction,
    child_import_savepoint,
    rollback_import_child,
)
from ..common.mesh_assets import (
    clear_submesh_index_cache,
    get_group,
    meshes_from_mesheswapps,
    submesh_index_for_object,
)
from ...meshes import MESH_GLB_EXTENSIONS
from ...notifications import show_message
=======
    clear_pending_child_of_inverse_requests,
    clear_transform_caches,
    component_local_matrix,
    component_uses_skinning,
    configure_child_of_constraint,
    flush_pending_child_of_inverse_requests,
    is_live_armature_object,
    visual_scale_matrix,
)

_LOG = get_logger(__name__)
>>>>>>> Stashed changes


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


<<<<<<< Updated upstream
def _import_entity_impl(request: EntityImportRequest):
    """Import one entity from a normalized request."""
=======
@override_palette_batched
def _import_entity_impl(request: EntityImportRequest, *, progress=NO_PROGRESS):
    """Import one entity from a normalized request"""
>>>>>>> Stashed changes

    if not isinstance(request, EntityImportRequest):
        raise TypeError("request must be an EntityImportRequest")

    with_materials = request.with_materials
    filepath = request.filepath
    appearances = list(request.appearances)
    excluded_meshes = request.excluded_meshes
    include_collisions = request.include_collisions
    include_phys = request.include_phys
    include_entity_colliders = request.include_entity_colliders
<<<<<<< Updated upstream
    include_occluders = request.include_occluders
    include_proxies = request.include_proxies
    include_lights = request.include_lights
    parent_collection_name = request.parent_collection_name
    provided_mesh_files = request.mesh_files
    app_files = request.app_files
=======
    include_mesh_colliders = request.include_mesh_colliders
    include_occluders = request.include_occluders
    include_proxies = request.include_proxies
    include_lights = request.include_lights
    include_light_channels = request.light_channels_included
    include_inkwidgets = request.include_inkwidgets
    include_facial_setup = request.include_facial_setup
    parent_collection_name = request.parent_collection_name
>>>>>>> Stashed changes
    animation_files = request.animation_files
    include_animations = request.include_animations
    generate_overrides = request.generate_overrides
    parsed_entity = request.parsed_entity
    imported_collections_out = request.imported_collections_out
<<<<<<< Updated upstream
    manage_master_visibility = request.manage_master_visibility

    cp77_addon_prefs = get_addon_preferences()
    if not cp77_addon_prefs.non_verbose:
        print('\n-------------------- Importing Cyberpunk 2077 Entity --------------------')
    C = bpy.context
    coll_scene = C.scene.collection
    parent_collection = (
        coll_scene.children.get(parent_collection_name)
        if parent_collection_name
        else None
    )
    start_time = time.time()
=======
    imported_rigs_out = request.imported_rigs_out
    existing_rig = request.existing_rig
    manage_master_visibility = request.manage_master_visibility

    C = bpy.context
    coll_scene = C.scene.collection
    parent_collection = (
        bpy.data.collections.get(parent_collection_name)
        if parent_collection_name
        else None
    )
>>>>>>> Stashed changes
    session = EntityImportSession(
        filepath=filepath,
        split_source_root=split_source_raw_root,
        provided_asset_index=request.asset_index,
<<<<<<< Updated upstream
=======
        depot_root=request.depot_root,
>>>>>>> Stashed changes
        index_policy=request.index_policy,
        documents=request.documents,
        provided_material_resources=request.material_resources,
        clear_transient_caches=clear_transient_import_caches,
        component_depot_path=lambda component: (
<<<<<<< Updated upstream
            ''
            if (
                type(component) is dict
                and (
                    component.get('$type') in NON_VISUAL_MESH_COMPONENT_TYPES
                    or (
                        component.get('$type') in APPEARANCE_PROXY_COMPONENT_TYPES
                        and not include_proxies
                    )
                    or (
                        component.get('$type') in LIGHT_RELATED_COMPONENT_TYPES
                        and not include_lights
                    )
                )
            )
            else depot_path_value(component, 'mesh', 'graphicsMesh')
            ),
        component_mesh_appearance=lambda component: cname_value(
            component.get('meshAppearance') if type(component) is dict else None,
            'default',
            ),
        component_enabled=is_component_enabled,
        manage_master_visibility=manage_master_visibility,
        imported_collections_out=imported_collections_out,
        with_materials=with_materials,
        )
=======
            ""
            if (
                type(component) is dict
                and (
                    component.get("$type") in NON_VISUAL_MESH_COMPONENT_TYPES
                    or (
                        component.get("$type") in APPEARANCE_PROXY_COMPONENT_TYPES
                        and not include_proxies
                    )
                    or light_component_skipped(
                        component.get("$type"),
                        include_lights=include_lights,
                        include_light_channels=include_light_channels,
                    )
                    or (
                        not request.include_shadow_meshes
                        and is_shadow_mesh(
                            depot_path(
                                component, "mesh", "graphicsMesh", normalize=False
                            )
                        )
                    )
                )
            )
            else depot_path(component, "mesh", "graphicsMesh", normalize=False)
        ),
        component_mesh_appearance=lambda component: cname_value(
            component.get("meshAppearance") if type(component) is dict else None,
            "default",
        ),
        component_enabled=is_component_enabled,
        manage_master_visibility=manage_master_visibility,
        imported_collections_out=imported_collections_out,
        imported_rigs_out=imported_rigs_out,
        with_materials=with_materials,
        required_extensions=entity_index_extensions(
            include_animations=include_animations or request.include_facial_animations,
            include_physics=include_phys,
            include_inkwidgets=include_inkwidgets,
            include_facial_setup=include_facial_setup,
            include_lights=include_lights,
        ),
    )
    progress.set(0.0, "Preparing resources", force=True)
>>>>>>> Stashed changes
    try:
        session.start()
    except Exception:
        try:
            session.close()
<<<<<<< Updated upstream
        except Exception:
            pass
        raise
=======
        except Exception as close_error:
            _LOG.debug(
                "Entity session close after a failed start also failed: %s",
                close_error,
                exc_info=True,
            )
        raise
    progress.set(10.0, "Loading entity", force=True)
>>>>>>> Stashed changes
    path = session.source_root
    after = session.source_relative_path
    asset_index = session.asset_index
    resources = session.resources
    execution_cache = session.execution_cache
    warning_messages = session.warnings

    rig = None
    Masters = None
    material_cache_acquired = False
<<<<<<< Updated upstream
    try:
        material_cache_acquired = acquire_material_cache(with_materials)
        ent_name = os.path.basename(filepath)[:-9]
        if not cp77_addon_prefs.non_verbose:
            print(f"Importing appearance: {', '.join(appearances)} from entity: {ent_name}")
=======
    image_failures = begin_image_failure_capture()
    try:
        material_cache_acquired = acquire_material_cache(with_materials)
        ent_name = os.path.basename(filepath)[:-9]
        _LOG.info(
            "Importing appearance(s) %s from entity %s",
            ", ".join(appearances),
            ent_name,
        )
>>>>>>> Stashed changes
        parsed_ent = parsed_entity
        if parsed_ent is None and filepath is not None:
            parsed_ent = resources.load_entity(filepath)
        if parsed_ent is None:
<<<<<<< Updated upstream
            return ImportResult(
                failures=(f"Failed to load entity document: {filepath}",),
=======
            issues = resources.entities.issues
            reason = issues[-1].message if issues else filepath
            return ImportResult(
                failures=(f"Failed to load entity document: {reason}",),
>>>>>>> Stashed changes
                label="entity import",
            )

        ent_apps = parsed_ent.appearances
        ent_components = parsed_ent.component_dicts
        ent_component_data = parsed_ent.component_data
        ent_default = parsed_ent.default_appearance
<<<<<<< Updated upstream
        ent_app_index_by_name = parsed_ent.appearance_index_by_name

=======
        entity_source_path = os.path.abspath(filepath)
        import_id = request.import_id or uuid.uuid4().hex

        # Seeded by the entity and the request, so importing the same entity with the same request repeats its choice.
>>>>>>> Stashed changes
        appearance_resolution = normalize_appearance_requests(
            parsed_ent,
            appearances,
            ent_name,
<<<<<<< Updated upstream
            choose=random.choice,
            )
        appearances = list(appearance_resolution.appearances)
        ent_default = appearance_resolution.default_appearance
        for message in appearance_resolution.messages:
            print(message)

        initial_vehicle_slot_component = parsed_ent.vehicle_slot_component
        VS = [initial_vehicle_slot_component] if initial_vehicle_slot_component else []
        vehicle_slot_component_ids = {id(initial_vehicle_slot_component)} if initial_vehicle_slot_component else set()
        vehicle_slots = initial_vehicle_slot_component.get('slots') if initial_vehicle_slot_component else None
=======
            choose=random.Random(
                f"{ent_name}|{'|'.join(map(str, appearances))}"
            ).choice,
        )
        appearances = list(appearance_resolution.appearances)
        ent_default = appearance_resolution.default_appearance
        for message in appearance_resolution.messages:
            _LOG.debug(message)

        initial_vehicle_slot_component = parsed_ent.vehicle_slot_component
        VS = [initial_vehicle_slot_component] if initial_vehicle_slot_component else []
        vehicle_slot_component_ids = (
            {id(initial_vehicle_slot_component)}
            if initial_vehicle_slot_component
            else set()
        )
        vehicle_slots = (
            initial_vehicle_slot_component.get("slots")
            if initial_vehicle_slot_component
            else None
        )
>>>>>>> Stashed changes
        vehicle_slot_lookup = execution_cache.slot_lookup(
            vehicle_slots,
            build_slot_lookup,
        )

<<<<<<< Updated upstream
        app_files = resources.files('.app.json', app_files)
        if ent_apps and not app_files:
            print('No Appearance file JSONs found in path, run the Ent export script first')

        mesh_files = (
            resources.files('.glb', provided_mesh_files)
            if provided_mesh_files is not None
            else tuple(
                path
                for extension in MESH_GLB_EXTENSIONS
                for path in resources.files(extension)
            )
        )
        if len(mesh_files) == 0:
            print(
                'No mesh GLBs found in path; continuing so non-mesh entity '
                'components can still be imported'
            )

        animation_files = (
            resources.files('.anims.glb', animation_files)
            if include_animations
=======
        animation_files = (
            resources.files(".anims.glb", animation_files)
            if include_animations and animation_files is not None
>>>>>>> Stashed changes
            else ()
        )

        # Animation GLBs are imported later for their animation data only. The entity rig
        # is always constructed exclusively from JSON rigs.
        rig_j = None
        rig_bone_index = {}

<<<<<<< Updated upstream
        if not app_files and len(ent_components) < 1:
=======
        if not ent_apps and len(ent_components) < 1 and not ent_component_data:
>>>>>>> Stashed changes
            message = (
                "The entity contains no importable components and no appearance "
                "documents were found"
            )
<<<<<<< Updated upstream
            print(message)
=======
            _LOG.warning("%s", message)
>>>>>>> Stashed changes
            return ImportResult(
                warnings=(message,),
                label="entity import",
            )

        else:
            Masters = session.ensure_masters(bpy, coll_scene)

            ent_component_ids = parsed_ent.component_ids
            ent_component_data_ids = parsed_ent.component_data_ids
            root_component_ids = ent_component_ids | ent_component_data_ids
            ent_parent_transform_lookup = parsed_ent.parent_transform_lookup
            ent_skinning_lookup = parsed_ent.skinning_lookup
            ent_shape_lookup = parsed_ent.shape_lookup
            base_slot_component_lookups = parsed_ent.slot_component_lookups

            component_mesh_info = resources.component_mesh_info
            component_mesh_json = resources.component_mesh_json
<<<<<<< Updated upstream
            master_group_objects = resources.master_group_objects

            entity_plan = compile_entity_import_plan(
                parsed_entity=parsed_ent,
                appearances=appearances,
=======
            resolve_master_group = resources.resolve_master_group
            master_group_plan = resources.master_group_plan
            master_group_submesh_indexes = resources.master_group_submesh_indexes

            def cached_is_excluded_mesh(
                depot_path,
                mesh_path,
                mesh_name,
                excluded,
            ):
                return execution_cache.mesh_excluded(
                    depot_path,
                    mesh_path,
                    mesh_name,
                    excluded,
                    is_excluded_mesh,
                )

            progress.set(15.0, "Planning entity", force=True)
            entity_plan = compile_entity_import_plan(
                parsed_entity=parsed_ent,
                appearances=appearances,
                appearance_indices=appearance_resolution.appearance_indices,
>>>>>>> Stashed changes
                default_appearance=ent_default,
                source_root=path,
                asset_index=asset_index,
                load_app=resources.load_app,
                resolve_export=resources.resolve_export,
                component_mesh_info=component_mesh_info,
                excluded_meshes=excluded_meshes,
                include_occluders=include_occluders,
                include_proxies=include_proxies,
                include_lights=include_lights,
<<<<<<< Updated upstream
                )
            for message in entity_plan.messages:
                print(message)

            appearances = list(entity_plan.appearances)
            appearance_plans = entity_plan.appearance_plans
            try:
                rig_runtime = EntityRigService(
                    resources=resources,
                    source_root=path,
                    entity_name=ent_name,
                    animation_files=animation_files,
                    import_animations=include_animations,
                    warnings=warning_messages,
                ).build(entity_plan.rig)
            except Exception as error:
=======
                include_light_channels=include_light_channels,
                mesh_is_excluded=cached_is_excluded_mesh,
            )
            for message in entity_plan.messages:
                _LOG.debug(message)
            warning_messages.extend(entity_plan.warnings)
            if not entity_plan.mesh_requirements:
                _LOG.debug(
                    "No resolved mesh exports required by this entity; continuing "
                    "with non-mesh components"
                )

            appearances = list(entity_plan.appearances)
            appearance_plans = entity_plan.appearance_plans
            progress.set(20.0, "Preparing rig", force=True)
            appearance_component_payloads = tuple(
                plan.appearance_components for plan in appearance_plans
            )
            rig_service = EntityRigService(
                resources=resources,
                source_root=path,
                entity_name=ent_name,
                animation_files=animation_files,
                animation_files_provider=(
                    (lambda: resources.files(".anims.glb"))
                    if include_animations and request.animation_files is None
                    else None
                ),
                import_animations=include_animations,
                component_payloads=(
                    ent_components,
                    ent_component_data,
                    *appearance_component_payloads,
                ),
                warnings=warning_messages,
            )
            rig_state = child_import_savepoint()
            try:
                rig_runtime = rig_service.build(
                    entity_plan.rig, existing_rig=existing_rig
                )
            except Exception as error:
                if is_live_armature_object(existing_rig):
                    raise
                # A rig that failed part-way is removed before the import continues without it.
                rollback_import_child(rig_state, f"entity rig for {ent_name}")
>>>>>>> Stashed changes
                message = (
                    f"Entity rig setup skipped for {ent_name}: "
                    f"{type(error).__name__}: {error}"
                )
<<<<<<< Updated upstream
                print(message)
                print(traceback.format_exc())
=======
                _LOG.warning("%s", message)
                debug_exception(_LOG, "Exception details")
>>>>>>> Stashed changes
                if message not in warning_messages:
                    warning_messages.append(message)
                rig_runtime = EntityRigRuntime(
                    ordered_components=tuple(entity_plan.rig.ordered_components),
                )
            rig = session.register_rig(rig_runtime.rig)
            rig_j = rig_runtime.rig_json
            rig_bone_index = rig_runtime.rig_bone_index
            rig_json_by_component_name = rig_runtime.rig_json_by_component_name
<<<<<<< Updated upstream
            rig_json_path_by_component_name = rig_runtime.rig_json_path_by_component_name
            armature_by_component_name = rig_runtime.armature_by_component_name
            rig_json_by_bone_name = rig_runtime.rig_json_by_bone_name
            rig_component_names = frozenset(rig_json_by_component_name)

            meshes_w_apps = {
                requirement.key: {
                    'apps': [list(requirement.appearances)],
                    'sectors': [requirement.sector] if requirement.sector else [],
                    'meshpath': requirement.mesh_path,
=======
            rig_json_path_by_component_name = (
                rig_runtime.rig_json_path_by_component_name
            )
            armature_by_component_name = rig_runtime.armature_by_component_name
            rig_json_by_bone_name = rig_runtime.rig_json_by_bone_name
            rig_component_names = frozenset(rig_json_by_component_name)
            base_source_order = tuple(rig_runtime.base_source_rig_paths)
            base_source_order_json = json.dumps(
                list(base_source_order), separators=(",", ":")
            )
            rig_merge_order_json = (
                json.dumps(list(rig_runtime.ordered_rig_paths), separators=(",", ":"))
                if rig_runtime.ordered_rig_paths
                else ""
            )
            if include_facial_setup and is_live_armature_object(rig):
                try:
                    facial_warning = preload(
                        rig,
                        resources,
                        (
                            ent_component_data,
                            *appearance_component_payloads,
                        ),
                    )
                except (
                    OSError,
                    RuntimeError,
                    TypeError,
                    ValueError,
                    KeyError,
                ) as error:
                    facial_warning = f"Facial setup preload failed: {error}"
                if facial_warning:
                    warning_messages.append(facial_warning)
                    _LOG.warning("%s", facial_warning)
                elif request.include_facial_animations:
                    _setup_path, face_rig_path = stored_paths(rig)
                    if face_rig_path:
                        rig_service.import_facial_animations(rig_runtime, face_rig_path)
            progress.set(30.0, "Preparing mesh masters", force=True)

            meshes_w_apps = {
                requirement.key: {
                    "apps": [list(requirement.appearances)],
                    "sectors": [requirement.sector] if requirement.sector else [],
                    "meshpath": requirement.mesh_path,
>>>>>>> Stashed changes
                }
                for requirement in entity_plan.mesh_requirements
            }
            mesh_import_failures = meshes_from_mesheswapps(
                meshes_w_apps,
                asset_index=session.asset_index,
                from_mesh_no=0,
                to_mesh_no=10000000,
                with_mats=with_materials,
                Masters=Masters,
<<<<<<< Updated upstream
                generate_overrides=generate_overrides,
                mesh_repository=resources.meshes,
                document_session=session.documents,
                material_resources=session.material_resources,
=======
                mesh_repository=resources.meshes,
                document_session=session.documents,
                material_resources=session.material_resources,
                progress=progress.span(30.0, 50.0),
>>>>>>> Stashed changes
            )
            for message in mesh_import_failures:
                if message not in warning_messages:
                    warning_messages.append(message)

<<<<<<< Updated upstream
            handler_operations = EntityHandlerOperations(
                is_component_enabled=is_component_enabled,
                child_of_inverse_matrix=child_of_inverse_matrix,
                configure_child_of_constraint=configure_child_of_constraint,
            )
            static_mesh_operations = EntityStaticMeshOperations(
                component_mesh_info=component_mesh_info,
                master_group_objects=master_group_objects,
                get_group=get_group,
                is_excluded_mesh=is_excluded_mesh,
                remap_copied_object_references=_remap_copied_object_references,
                component_is_zero_mask_culled=component_is_zero_mask_culled,
                chunk_mask_value=chunk_mask_value,
                submesh_index_for_object=submesh_index_for_object,
                visual_scale_matrix=visual_scale_matrix,
                child_of_inverse_matrix=child_of_inverse_matrix,
=======
            def cached_component_local_matrix(component):
                return execution_cache.component_local_matrix(
                    component,
                    component_local_matrix,
                )

            def cached_visual_scale_matrix(component):
                return execution_cache.component_visual_scale(
                    component,
                    visual_scale_matrix,
                )

            handler_operations = EntityHandlerOperations(
                is_component_enabled=is_component_enabled,
                configure_child_of_constraint=configure_child_of_constraint,
                visual_scale_matrix=cached_visual_scale_matrix,
            )
            static_mesh_operations = EntityStaticMeshOperations(
                component_mesh_info=component_mesh_info,
                resolve_master_group=resolve_master_group,
                master_group_plan=master_group_plan,
                master_group_submesh_indexes=master_group_submesh_indexes,
                get_group=get_group,
                is_excluded_mesh=cached_is_excluded_mesh,
                remap_copied_object_references=remap_copied_object_references,
                component_is_zero_mask_culled=component_is_zero_mask_culled,
                chunk_mask_value=chunk_mask_value,
                submesh_index_for_object=submesh_index_for_object,
                visual_scale_matrix=cached_visual_scale_matrix,
>>>>>>> Stashed changes
                configure_child_of_constraint=configure_child_of_constraint,
            )
            skinned_mesh_operations = EntitySkinnedMeshOperations(
                component_mesh_info=component_mesh_info,
<<<<<<< Updated upstream
                master_group_objects=master_group_objects,
                get_group=get_group,
                is_excluded_mesh=is_excluded_mesh,
                remap_copied_object_references=_remap_copied_object_references,
                component_is_zero_mask_culled=component_is_zero_mask_culled,
                chunk_mask_value=chunk_mask_value,
                submesh_index_for_object=submesh_index_for_object,
                visual_scale_matrix=visual_scale_matrix,
                bind_skinned_objects_to_rig=bind_skinned_objects_to_rig,
            )


            light_handler_registry = None
            collect_light_channel_components = None
            collect_light_components = None
            if include_lights:
=======
                resolve_master_group=resolve_master_group,
                master_group_plan=master_group_plan,
                master_group_submesh_indexes=master_group_submesh_indexes,
                get_group=get_group,
                is_excluded_mesh=cached_is_excluded_mesh,
                remap_copied_object_references=remap_copied_object_references,
                component_is_zero_mask_culled=component_is_zero_mask_culled,
                chunk_mask_value=chunk_mask_value,
                submesh_index_for_object=submesh_index_for_object,
                visual_scale_matrix=cached_visual_scale_matrix,
                bind_skinned_objects_to_rig=bind_skinned_objects_to_rig,
            )

            light_handler_registry = None
            collect_light_channel_components = None
            collect_light_components = None
            if include_lights or include_light_channels:
>>>>>>> Stashed changes
                from .handlers.lights import (
                    collect_light_channel_components,
                    collect_light_components,
                    create_auxiliary_component_registry,
                )

                light_handler_registry = create_auxiliary_component_registry()

<<<<<<< Updated upstream
            imported_appearance_collections = session.imported_collections
            appearance_count = len(appearance_plans)
            for x, appearance_plan in enumerate(appearance_plans):
                display_app_name = appearance_plan.display_name
                app_name = appearance_plan.resolved_name
                print(f"\nImporting appearance {x + 1} of {appearance_count}: {display_app_name}")
                app_start_time = time.time()
                ent_coll = track_created_datablock("collections", bpy.data.collections.new(ent_name + '_' + display_app_name))
                (parent_collection or coll_scene).children.link(ent_coll)
                ent_coll['depotPath'] = after
                session.register_collection(ent_coll)
                chunks = appearance_plan.chunks or ent_component_data
                current_app_resource = (
                    appearance_plan.app_resource_path
                    or appearance_plan.app_resource_depot
                )
                ent_coll['appearanceName'] = app_name
                ent_coll['importLights'] = bool(include_lights)
                ent_coll['appearanceIndex'] = (
                    appearance_plan.entity_appearance_index
                    if appearance_plan.entity_appearance_index is not None
                    else ent_app_index_by_name.get(app_name, 0)
                )
                if current_app_resource:
                    ent_coll['appResource'] = current_app_resource

                comps = appearance_plan.merged_components or ent_components
                appearance_index = build_component_pass_index(comps, execution_cache)
                if appearance_plan.parsed_app is not None:
                    parsed_app = appearance_plan.parsed_app
                    parsed_app_name = appearance_plan.parsed_app_name
                    app_parent_transform_lookup = parsed_app.parent_transform_lookup_by_appearance_name.get(
                        parsed_app_name, {}
                    )
                    app_skinning_lookup = parsed_app.skinning_lookup_by_appearance_name.get(
                        parsed_app_name, {}
=======
            widget_handler_registry = None
            if include_inkwidgets:
                from .handlers.widgets import create_widget_component_registry

                widget_handler_registry = create_widget_component_registry()

            imported_appearance_collections = session.imported_collections
            # Appearances share mesh data; each mesh is fingerprinted once for the import.
            signature_mesh_cache = {}
            embedded_physx_candidates = []
            appearance_colliders = None
            appearance_count = len(appearance_plans)
            appearance_units = sum(
                1
                + len(plan.component_index.transform_animator_components)
                + len(plan.component_index.mesh_components)
                + (
                    len(plan.component_index.widget_components)
                    if include_inkwidgets
                    else 0
                )
                for plan in appearance_plans
            )
            appearance_progress = progress.span(50.0, 88.0).counter(
                "Importing appearance components",
                appearance_units,
            )
            for x, appearance_plan in enumerate(appearance_plans):
                display_app_name = appearance_plan.display_name
                app_name = appearance_plan.resolved_name
                _LOG.info(
                    "Importing appearance %d of %d: %s",
                    x + 1,
                    appearance_count,
                    display_app_name,
                )
                appearance_progress.note(display_app_name, force=True)
                app_start_time = time.time()
                ent_coll = track_created_datablock(
                    "collections",
                    bpy.data.collections.new(ent_name + "_" + display_app_name),
                )
                (parent_collection or coll_scene).children.link(ent_coll)
                ent_coll["depotPath"] = after
                ent_coll["cp77_entity_imported"] = True
                ent_coll["cp77_entity_source"] = entity_source_path
                session.register_collection(ent_coll)
                chunks = appearance_plan.chunks or ent_component_data
                ent_coll["appearanceName"] = app_name
                ent_coll["cp77_requested_appearance_name"] = (
                    appearance_plan.requested_name
                )
                ent_coll["cp77_display_appearance_name"] = display_app_name
                if is_live_armature_object(rig):
                    overlay_source_order = []
                    seen_overlay_paths = set()
                    for rig_component in appearance_plan.appearance_components:
                        if not is_animated_rig_component(rig_component):
                            continue
                        rig_depot = depot_path(rig_component, "rig", normalize=False)
                        rig_path = resources.resolve_rig(rig_depot) or ""
                        rig_key = local_path_key(rig_path) if rig_path else ""
                        if not rig_path or rig_key in seen_overlay_paths:
                            continue
                        seen_overlay_paths.add(rig_key)
                        overlay_source_order.append(rig_path)
                    source_order = tuple(
                        dict.fromkeys((*base_source_order, *overlay_source_order))
                    )
                    if source_order:
                        ent_coll["cp77_rig_source_order"] = json.dumps(
                            list(source_order), separators=(",", ":")
                        )
                    ent_coll["cp77_rig_base_source_order"] = base_source_order_json
                    ent_coll["cp77_rig_overlay_source_order"] = json.dumps(
                        list(overlay_source_order), separators=(",", ":")
                    )
                    if x == 0 and rig_merge_order_json:
                        ent_coll["cp77_rig_merge_order"] = rig_merge_order_json
                appearance_index = appearance_plan.component_index
                if appearance_plan.parsed_app is not None:
                    parsed_app = appearance_plan.parsed_app
                    parsed_app_name = appearance_plan.parsed_app_name
                    app_parent_transform_lookup = (
                        parsed_app.parent_transform_lookup_by_appearance_name.get(
                            parsed_app_name, {}
                        )
                    )
                    app_skinning_lookup = (
                        parsed_app.skinning_lookup_by_appearance_name.get(
                            parsed_app_name, {}
                        )
>>>>>>> Stashed changes
                    )
                    app_shape_lookup = parsed_app.shape_lookup_by_appearance_name.get(
                        parsed_app_name, {}
                    )
<<<<<<< Updated upstream
                    app_light_channels = parsed_app.light_channels_by_appearance_name.get(
                        parsed_app_name, ()
                    )
                else:
                    app_parent_transform_lookup = build_chunk_lookup(
                        chunks, 'parentTransform', cache=execution_cache
                    )
                    app_skinning_lookup = build_chunk_lookup(
                        chunks, 'skinning', cache=execution_cache
                    )
                    app_shape_lookup = build_chunk_lookup(
                        chunks, 'shape', cache=execution_cache
                    )
                    app_light_channels = ()

                if include_lights:
                    light_channel_components = execution_cache.collect_components(
                        'light_channels',
                        (
                            app_light_channels,
                            chunks,
                            comps,
                            parsed_ent.light_channel_components,
                            ent_components,
                        ),
                        collect_light_channel_components,
                    )
                    light_components = execution_cache.collect_components(
                        'lights',
                        (ent_component_data, ent_components, chunks, comps),
                        collect_light_components,
                    )
                else:
                    light_channel_components = ()
                    light_components = ()

                auxiliary_components = light_channel_components + light_components
                resolver_components, resolver_component_token = merge_component_groups(
                    ent_components,
                    appearance_index.components,
                    auxiliary_components,
=======
                    app_light_channels = (
                        parsed_app.light_channels_by_appearance_name.get(
                            parsed_app_name, ()
                        )
                    )
                else:
                    app_parent_transform_lookup = build_chunk_lookup(
                        chunks, "parentTransform", cache=execution_cache
                    )
                    app_skinning_lookup = build_chunk_lookup(
                        chunks, "skinning", cache=execution_cache
                    )
                    app_shape_lookup = build_chunk_lookup(
                        chunks, "shape", cache=execution_cache
                    )
                    app_light_channels = ()

                light_channel_components = ()
                light_components = ()
                if include_light_channels:
                    light_channel_components = execution_cache.collect_components(
                        "light_channels",
                        (
                            app_light_channels,
                            chunks,
                            appearance_index.components,
                            parsed_ent.light_channel_components,
                        ),
                        collect_light_channel_components,
                    )
                if include_lights:
                    light_components = execution_cache.collect_components(
                        "lights",
                        (ent_component_data, chunks, appearance_index.components),
                        collect_light_components,
                    )

                resolver_components, resolver_component_token = merge_component_groups(
                    appearance_index.components,
                    light_channel_components,
                    light_components,
>>>>>>> Stashed changes
                )
                resolver_index = build_component_pass_index(
                    resolver_components,
                    execution_cache,
                    identity_token=resolver_component_token,
                )

<<<<<<< Updated upstream
                parent_transform_lookup = ComponentHandleLookup(app_parent_transform_lookup)
=======
                parent_transform_lookup = ComponentHandleLookup(
                    app_parent_transform_lookup
                )
>>>>>>> Stashed changes
                skinning_lookup = ComponentHandleLookup(app_skinning_lookup)
                shape_lookup = ComponentHandleLookup(app_shape_lookup)
                set_parent_lookup = parent_transform_lookup.set_component_lookup
                set_skinning_lookup = skinning_lookup.set_component_lookup
                set_shape_lookup = shape_lookup.set_component_lookup
                for comp in resolver_index.components:
                    if id(comp) in root_component_ids:
                        set_parent_lookup(comp, ent_parent_transform_lookup)
                        set_skinning_lookup(comp, ent_skinning_lookup)
                        set_shape_lookup(comp, ent_shape_lookup)

                for comp in resolver_index.rig_components:
<<<<<<< Updated upstream
                    if not is_animated_rig_component(comp):
                        continue
                    rig_name = component_name(comp)
                    if rig_name and rig_name not in rig_json_path_by_component_name:
                        print(
                            f"animated component '{rig_name}' was not present in the ordered JSON rig prepass; leaving it unmerged"
                        )

                slot_owner_rig_jsons, slot_owner_rig_owner_names = build_slot_owner_binding_maps(
                    resolver_index.slot_components,
                    parent_transform_lookup,
                    rig_json_by_component_name,
                    rig_component_names,
=======
                    rig_name = component_name(comp)
                    if rig_name and rig_name not in rig_json_path_by_component_name:
                        _LOG.warning(
                            "animated component '%s' was not present in the ordered JSON rig prepass; leaving it unmerged",
                            rig_name,
                        )

                slot_owner_rig_jsons, slot_owner_rig_owner_names = (
                    build_slot_owner_binding_maps(
                        resolver_index.slot_components,
                        parent_transform_lookup,
                        rig_json_by_component_name,
                        rig_component_names,
                    )
>>>>>>> Stashed changes
                )
                anim_impl_lookup = build_anim_impl_lookup(chunks)
                transform_animator_lookup = build_transform_animator_lookup(
                    resolver_index.transform_animator_components,
                    anim_impl_lookup,
                )

                for c in appearance_index.slot_components:
                    if (
<<<<<<< Updated upstream
                        component_name(c) in ('vehicle_slots', 'slot', 'slots')
=======
                        component_name(c) in ("vehicle_slots", "slot", "slots")
>>>>>>> Stashed changes
                        and id(c) not in vehicle_slot_component_ids
                    ):
                        VS.append(c)
                        vehicle_slot_component_ids.add(id(c))

                if not vehicle_slots and VS:
<<<<<<< Updated upstream
                    vehicle_slots = VS[0]['slots']
=======
                    vehicle_slots = VS[0]["slots"]
>>>>>>> Stashed changes
                    vehicle_slot_lookup = execution_cache.slot_lookup(
                        vehicle_slots,
                        build_slot_lookup,
                    )

                resolver_components_by_name = resolver_index.by_name
                resolver_slot_component_lookups = dict(base_slot_component_lookups)
                for comp in resolver_index.slot_components:
                    name = component_name(comp)
                    if not name:
                        continue
                    if (
                        id(comp) in ent_component_ids
                        and name in base_slot_component_lookups
                    ):
                        continue
                    resolver_slot_component_lookups[name] = execution_cache.slot_lookup(
<<<<<<< Updated upstream
                        comp.get('slots'),
                        build_slot_lookup,
                    )

=======
                        comp.get("slots"),
                        build_slot_lookup,
                    )

                skinned_components_by_id = {
                    id(component): component
                    for component in resolver_index.mesh_components
                    if execution_cache.uses_skinning(
                        component,
                        skinning_lookup,
                        component_uses_skinning,
                    )
                }
>>>>>>> Stashed changes
                component_skin_placements = {}
                component_skin_placement_info = {}
                if rig_j is not None:
                    for component in resolver_index.mesh_components:
<<<<<<< Updated upstream
                        if not execution_cache.uses_skinning(
                            component,
                            skinning_lookup,
                            component_uses_skinning,
                        ):
=======
                        component_id = id(component)
                        if component_id not in skinned_components_by_id:
>>>>>>> Stashed changes
                            continue
                        placement, root_bone, status = execution_cache.skin_attachment(
                            component,
                            rig_j,
                            component_mesh_json,
                            component_skin_attachment_matrix,
                        )
<<<<<<< Updated upstream
                        component_skin_placement_info[id(component)] = (root_bone, status)
                        if placement is not None:
                            component_skin_placements[id(component)] = placement

                transform_resolver = EntityTransformResolver(
                        resolver_components,
                        parent_transform_lookup,
                        skinning_lookup=skinning_lookup,
                        rig=rig,
                        rig_j=rig_j,
                        rig_bone_index=rig_bone_index,
                        default_slot_lookup=vehicle_slot_lookup,
                        slot_owner_rig_jsons=slot_owner_rig_jsons,
                        rig_json_by_component_name=rig_json_by_component_name,
                        rig_json_by_bone_name=rig_json_by_bone_name,
                        armature_by_component_name=armature_by_component_name,
                        slot_owner_rig_owner_names=slot_owner_rig_owner_names,
                        components_by_name=resolver_components_by_name,
                        slot_component_lookups=resolver_slot_component_lookups,
                        component_skin_placements=component_skin_placements,
                        )

                transform_animators = EntityTransformAnimatorService(
                        ent_coll,
                        parent_transform_lookup,
                        transform_animator_lookup,
                        )
                static_meshes = EntityStaticMeshService(
                    entity_collection=ent_coll,
                    appearance_name=app_name,
                    app_resource=current_app_resource,
=======
                        component_skin_placement_info[component_id] = (
                            root_bone,
                            status,
                        )
                        if placement is not None:
                            component_skin_placements[component_id] = placement

                transform_resolver = EntityTransformResolver(
                    resolver_components,
                    parent_transform_lookup,
                    skinning_lookup=skinning_lookup,
                    rig=rig,
                    rig_j=rig_j,
                    rig_bone_index=rig_bone_index,
                    default_slot_lookup=vehicle_slot_lookup,
                    slot_owner_rig_jsons=slot_owner_rig_jsons,
                    rig_json_by_component_name=rig_json_by_component_name,
                    rig_json_by_bone_name=rig_json_by_bone_name,
                    armature_by_component_name=armature_by_component_name,
                    slot_owner_rig_owner_names=slot_owner_rig_owner_names,
                    components_by_name=resolver_components_by_name,
                    slot_component_lookups=resolver_slot_component_lookups,
                    component_skin_placements=component_skin_placements,
                    local_matrix_resolver=cached_component_local_matrix,
                )

                if x == 0 and include_collisions and include_mesh_colliders:
                    for component in resolver_index.mesh_components:
                        mesh_depot_path, _mesh_name, mesh_path, _appearance, enabled = (
                            component_mesh_info(component)
                        )
                        if not enabled:
                            continue
                        mesh_root = component_mesh_json(component)
                        resources_in_mesh = physics_resources_from_mesh_root(
                            mesh_root,
                            mesh_path or mesh_depot_path,
                        )
                        if not resources_in_mesh:
                            continue
                        component_matrix = transform_resolver.resolve_component_matrix(
                            component
                        )[0]
                        for physics_resource in resources_in_mesh:
                            embedded_physx_candidates.append(
                                (physics_resource, component_matrix.copy())
                            )

                if x == 0 and include_collisions and include_entity_colliders:
                    from .collisions import (
                        AppearanceColliders,
                        collect_collider_components,
                    )

                    # A collider both files carry imports once, from the entity.
                    colliders = tuple(
                        component
                        for component in execution_cache.collect_components(
                            "colliders",
                            (ent_component_data, chunks, appearance_index.components),
                            collect_collider_components,
                        )
                        if id(component) not in root_component_ids
                    )
                    if colliders:
                        appearance_colliders = AppearanceColliders(
                            components=colliders,
                            transform_resolver=transform_resolver,
                            handle_sources=(
                                appearance_plan.appearance_components,
                                appearance_plan.chunks,
                            ),
                        )

                transform_animators = EntityTransformAnimatorService(
                    ent_coll,
                    parent_transform_lookup,
                    transform_animator_lookup,
                    transform_resolver,
                    configure_child_of_constraint,
                )
                static_meshes = EntityStaticMeshService(
                    entity_collection=ent_coll,
                    appearance_name=app_name,
>>>>>>> Stashed changes
                    masters=Masters,
                    excluded_meshes=excluded_meshes,
                    transform_resolver=transform_resolver,
                    transform_animators=transform_animators,
                    operations=static_mesh_operations,
                    warnings=warning_messages,
                )
                skinned_meshes = EntitySkinnedMeshService(
                    entity_collection=ent_coll,
                    appearance_name=app_name,
<<<<<<< Updated upstream
                    app_resource=current_app_resource,
=======
>>>>>>> Stashed changes
                    masters=Masters,
                    excluded_meshes=excluded_meshes,
                    transform_resolver=transform_resolver,
                    transform_animators=transform_animators,
                    rig=rig,
                    component_skin_placement_info=component_skin_placement_info,
                    operations=skinned_mesh_operations,
                    warnings=warning_messages,
                )
                mesh_service = EntityMeshService(
                    static_meshes,
                    skinned_meshes,
<<<<<<< Updated upstream
                    lambda component: execution_cache.uses_skinning(
                        component,
                        skinning_lookup,
                        component_uses_skinning,
=======
                    lambda component, components=skinned_components_by_id: (
                        components.get(id(component)) is component
>>>>>>> Stashed changes
                    ),
                    include_occluders=include_occluders,
                    include_proxies=include_proxies,
                )
                handler_context = AppearanceExecutionContext(
                    filepath=filepath,
                    appearance_name=app_name,
                    entity_collection=ent_coll,
                    transform_resolver=transform_resolver,
                    shape_lookup=shape_lookup,
                    transform_animators=transform_animators,
                    meshes=mesh_service,
                    static_meshes=static_meshes,
                    skinned_meshes=skinned_meshes,
                    operations=handler_operations,
<<<<<<< Updated upstream
                )
=======
                    resolve_export=resources.resolve_export,
                )
                appearance_progress.advance(detail=f"{display_app_name}: setup")
>>>>>>> Stashed changes
                for c in appearance_index.transform_animator_components:
                    comp_name = component_name(c)
                    child_state = child_import_savepoint()
                    try:
                        _ENTITY_COMPONENT_HANDLERS.execute(c, handler_context)
                    except Exception as error:
<<<<<<< Updated upstream
                        rollback_import_child(child_state, f"animator component {comp_name}")
                        print('Failed on animator component ', comp_name)
                        print(traceback.format_exc())
=======
                        rollback_import_child(
                            child_state, f"animator component {comp_name}"
                        )
                        _LOG.error(
                            "Failed on animator component %s", comp_name, exc_info=True
                        )
>>>>>>> Stashed changes
                        message = (
                            f"Animator component failed for {comp_name}: "
                            f"{type(error).__name__}: {error}"
                        )
                        if message not in warning_messages:
                            warning_messages.append(message)
<<<<<<< Updated upstream

                for c in appearance_index.mesh_components:
                    if (
                        not include_lights
                        and c.get("$type") in LIGHT_RELATED_COMPONENT_TYPES
                    ):
=======
                    finally:
                        appearance_progress.advance(
                            detail=f"{display_app_name}: {comp_name or 'animator'}"
                        )

                for c in appearance_index.mesh_components:
                    if light_component_skipped(
                        c.get("$type"),
                        include_lights=include_lights,
                        include_light_channels=include_light_channels,
                    ):
                        appearance_progress.advance(
                            detail=f"{display_app_name}: skipped light mesh"
                        )
>>>>>>> Stashed changes
                        continue
                    comp_name = component_name(c)
                    child_state = child_import_savepoint()
                    try:
                        handler = _ENTITY_COMPONENT_HANDLERS.handler_for(c)
                        if handler is None and light_handler_registry is not None:
                            handler = light_handler_registry.handler_for(c)
                        if handler is None:
<<<<<<< Updated upstream
                            mesh_service.execute(c)
                        else:
                            handler.execute(c, handler_context)
                    except Exception as error:
                        rollback_import_child(child_state, f"entity component {comp_name}")
=======
                            component_result = mesh_service.execute(c)
                        else:
                            component_result = handler.execute(c, handler_context)
                        if comp_name and isinstance(
                            component_result, bpy.types.Collection
                        ):
                            handler_context.state.setdefault(
                                "component_collections", {}
                            )[comp_name] = component_result
                    except Exception as error:
                        rollback_import_child(
                            child_state, f"entity component {comp_name}"
                        )
>>>>>>> Stashed changes
                        message = (
                            f"Entity component skipped for {comp_name}: "
                            f"{type(error).__name__}: {error}"
                        )
<<<<<<< Updated upstream
                        print(message)
                        print(traceback.format_exc())
=======
                        # Handlers name the asset they were importing in the exception's notes.
                        for note in getattr(error, "__notes__", ()):
                            message += f"; {note}"
                        _LOG.warning("%s", message, exc_info=True)
                        if message not in warning_messages:
                            warning_messages.append(message)
                    finally:
                        appearance_progress.advance(
                            detail=f"{display_app_name}: {comp_name or 'component'}"
                        )

                if widget_handler_registry is not None:
                    for c in appearance_index.widget_components:
                        comp_name = component_name(c)
                        child_state = child_import_savepoint()
                        try:
                            widget_handler_registry.execute(c, handler_context)
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
                            if message not in warning_messages:
                                warning_messages.append(message)
                        finally:
                            appearance_progress.advance(
                                detail=f"{display_app_name}: {comp_name or 'ink widget'}"
                            )
                    for message in handler_context.state.get("widget_warnings", ()):
>>>>>>> Stashed changes
                        if message not in warning_messages:
                            warning_messages.append(message)

                if light_handler_registry is not None:
<<<<<<< Updated upstream
=======
                    appearance_progress.note(
                        f"{display_app_name}: lights",
                        force=True,
                    )
>>>>>>> Stashed changes
                    for c in (*light_components, *light_channel_components):
                        comp_name = component_name(c)
                        child_state = child_import_savepoint()
                        try:
                            light_handler_registry.execute(c, handler_context)
                        except Exception as error:
<<<<<<< Updated upstream
                            rollback_import_child(child_state, f"light component {comp_name}")
=======
                            rollback_import_child(
                                child_state, f"light component {comp_name}"
                            )
>>>>>>> Stashed changes
                            message = (
                                f"Light component skipped for {comp_name}: "
                                f"{type(error).__name__}: {error}"
                            )
<<<<<<< Updated upstream
                            print(message)
                            print(traceback.format_exc())
                            if message not in warning_messages:
                                warning_messages.append(message)
                print('Appearance import time:', time.time() - app_start_time, 'Seconds')

            if include_collisions:
                from .collisions import EntityCollisionRuntime, EntityCollisionService

                collision_target_collection = imported_appearance_collections[
                    0] if imported_appearance_collections else coll_scene
=======
                            _LOG.warning("%s", message, exc_info=True)
                            if message not in warning_messages:
                                warning_messages.append(message)
                entry_index = appearance_plan.entity_appearance_index
                record_imported_appearance(
                    ent_coll,
                    import_id=import_id,
                    ent_path=entity_source_path,
                    app_path=appearance_plan.app_resource_path,
                    app_depot=appearance_plan.app_resource_depot,
                    appearance=app_name,
                    entry_name=(
                        cname_value(ent_apps[entry_index].get("name"), "")
                        if entry_index is not None and 0 <= entry_index < len(ent_apps)
                        else ""
                    ),
                    mesh_cache=signature_mesh_cache,
                )
                _LOG.debug(
                    "Appearance %s imported in %.3f seconds",
                    display_app_name,
                    time.time() - app_start_time,
                )

            appearance_progress.finish(detail="Appearances complete")
            progress.set(88.0, "Importing collisions", force=True)
            if include_collisions:
                from .collisions import EntityCollisionRuntime, EntityCollisionService

                physx_target_collection = (
                    imported_appearance_collections[0]
                    if imported_appearance_collections
                    else coll_scene
                )
>>>>>>> Stashed changes
                collision_service = EntityCollisionService(
                    EntityCollisionRuntime(
                        parsed_entity=parsed_ent,
                        resources=resources,
                        rig=rig,
                        rig_json=rig_j,
                        rig_bone_index=rig_bone_index,
                        vehicle_slot_lookup=vehicle_slot_lookup,
                        rig_json_by_component_name=rig_json_by_component_name,
                        rig_json_by_bone_name=rig_json_by_bone_name,
                        armature_by_component_name=armature_by_component_name,
                        lookup_factory=ComponentHandleLookup,
<<<<<<< Updated upstream
                        target_collection=collision_target_collection,
                        blender_context=bpy.context,
                        operations=handler_operations,
                        handler_registry=_ENTITY_COMPONENT_HANDLERS,
=======
                        target_collection=physx_target_collection,
                        blender_context=bpy.context,
                        operations=handler_operations,
                        embedded_physics=tuple(embedded_physx_candidates),
                        appearance_colliders=appearance_colliders,
>>>>>>> Stashed changes
                    )
                )
                child_state = child_import_savepoint()
                try:
                    collision_service.execute(
                        include_collisions=include_collisions,
                        include_phys=include_phys,
                        include_entity_colliders=include_entity_colliders,
<<<<<<< Updated upstream
                    )
                except Exception as error:
                    rollback_import_child(child_state, f"entity collision import {ent_name}")
=======
                        include_mesh_colliders=include_mesh_colliders,
                    )
                except Exception as error:
                    rollback_import_child(
                        child_state, f"entity collision import {ent_name}"
                    )
>>>>>>> Stashed changes
                    message = (
                        f"Entity collision import skipped for {ent_name}: "
                        f"{type(error).__name__}: {error}"
                    )
<<<<<<< Updated upstream
                    print(message)
                    print(traceback.format_exc())
                    if message not in warning_messages:
                        warning_messages.append(message)
        session.collect_document_issues()
        created_collections = tuple(session.imported_collections)
        warnings = unique_messages(warning_messages)
        if warnings:
            show_message('Warnings during import:\n\t' + '\n\t'.join(warnings))
        if not cp77_addon_prefs.non_verbose:
            cache_stats = execution_cache.stats()
            print(
                'Entity execution cache: '
                f"{cache_stats['hits']} hits, {cache_stats['misses']} misses"
            )
            print(f"Imported Entity in {time.time() - start_time} Seconds from {ent_name}.ent")
            print('-------------------- Finished Importing Cyberpunk 2077 Entity --------------------\n')
    finally:
=======
                    _LOG.warning("%s", message, exc_info=True)
                    if message not in warning_messages:
                        warning_messages.append(message)
        progress.set(94.0, "Finalizing constraints", force=True)
        if not request.defer_child_of_inverse:
            inverse_stats = flush_pending_child_of_inverse_requests()
            if inverse_stats["requested"]:
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
                    if message not in warning_messages:
                        warning_messages.append(message)
        if request.lights_linked or (
            include_light_channels and not request.light_channel_volumes_kept
        ):
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
                    if not request.light_channel_volumes_kept:
                        retire_light_channel_volumes(
                            imported_collection, tuple(imported_collection.all_objects)
                        )
                mark_registered_reflection_probes_dirty(bpy.context.scene)
            except Exception as error:
                message = (
                    "Entity light-channel linking skipped: "
                    f"{type(error).__name__}: {error}"
                )
                _LOG.warning("%s", message, exc_info=True)
                if message not in warning_messages:
                    warning_messages.append(message)
        session.collect_document_issues()
        progress.set(100.0, "Complete", force=True)
        created_collections = tuple(session.imported_collections)
        if request.transactional:
            texture_message = image_load_failure_message(image_failures)
            if texture_message:
                warning_messages.append(texture_message)
        warnings = unique_messages(warning_messages)
        if warnings:
            import_message(summarize_messages(warnings, root=path), logger=_LOG)
        cache_stats = execution_cache.stats()
        _LOG.debug(
            "Entity execution cache: %d hits, %d misses",
            cache_stats["hits"],
            cache_stats["misses"],
        )
    finally:
        end_image_failure_capture(image_failures)
>>>>>>> Stashed changes
        try:
            session.close(rig)
        finally:
            release_material_cache(material_cache_acquired)
    return ImportResult(
        created_items=created_collections,
        warnings=warnings,
        label="entity import",
    )


<<<<<<< Updated upstream
def _clear_rolled_back_collection_output(request):
    output = request.imported_collections_out
    if output is None:
        return
    retained = []
    for collection in tuple(output):
        try:
            if bpy.data.collections.get(collection.name) is collection:
                retained.append(collection)
        except (AttributeError, ReferenceError, TypeError):
            pass
    try:
        output[:] = retained
    except (AttributeError, TypeError):
        pass


def import_entity(request: EntityImportRequest):
    if not isinstance(request, EntityImportRequest):
        raise TypeError("request must be an EntityImportRequest")
    if not request.transactional:
        return _import_entity_impl(request)
    transaction = BlenderImportTransaction(capture_existing_state=False)
    try:
        with transaction.scope():
            result = _import_entity_impl(request)
    except Exception as error:
        report = transaction.rollback()
        _clear_rolled_back_collection_output(request)
        rollback_error = rollback_report_message(report)
        if rollback_error:
            raise RuntimeError(
                f"{error}; rollback incomplete: {rollback_error}"
            ) from error
        raise
    if result.failures:
        report = transaction.rollback()
        _clear_rolled_back_collection_output(request)
=======
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
>>>>>>> Stashed changes
        failures = list(result.failures)
        rollback_error = rollback_report_message(report)
        if rollback_error:
            failures.append("Rollback incomplete: " + rollback_error)
<<<<<<< Updated upstream
=======
        _LOG.error(
            "Entity import failed: %s",
            "; ".join(failures[:3])
            + (f"; and {len(failures) - 3} more" if len(failures) > 3 else ""),
        )
>>>>>>> Stashed changes
        return ImportResult(
            created_items=(),
            warnings=result.warnings,
            failures=tuple(failures),
            label=result.label,
        )
    transaction.commit()
    return result


<<<<<<< Updated upstream
__all__ = ("EntityImportRequest", "import_entity")
=======
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
>>>>>>> Stashed changes
