from __future__ import annotations
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
from .execution_cache import (
    ComponentHandleLookup,
    build_chunk_lookup,
    build_component_pass_index,
    merge_component_groups,
)
from .options import EntityImportRequest
from .context import AppearanceExecutionContext, EntityHandlerOperations
from .handlers.animators import (
    EntityTransformAnimatorHandler,
    EntityTransformAnimatorService,
    build_anim_impl_lookup,
    build_transform_animator_lookup,
)
from .handlers.meshes import (
    EntityMeshHandler,
    EntityMeshService,
    EntitySkinnedMeshOperations,
    EntitySkinnedMeshService,
    EntityStaticMeshOperations,
    EntityStaticMeshService,
)
from .registry import EntityComponentHandlerRegistry
from .rigs import EntityRigRuntime, EntityRigService, clear_rig_caches
from .rig_planning import is_animated_rig_component
from ..common.entity_data import component_name
from ..common.paths import depot_path_value
from ...assetio.values import cname_value
from .skinning import (
    bind_skinned_objects_to_rig,
    clear_skinning_caches,
    component_skin_attachment_matrix,
)
from .transforms import (
    EntityTransformResolver,
    build_slot_lookup,
    build_slot_owner_binding_maps,
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


def _import_entity_impl(request: EntityImportRequest):
    """Import one entity from a normalized request."""

    if not isinstance(request, EntityImportRequest):
        raise TypeError("request must be an EntityImportRequest")

    with_materials = request.with_materials
    filepath = request.filepath
    appearances = list(request.appearances)
    excluded_meshes = request.excluded_meshes
    include_collisions = request.include_collisions
    include_phys = request.include_phys
    include_entity_colliders = request.include_entity_colliders
    include_occluders = request.include_occluders
    include_proxies = request.include_proxies
    include_lights = request.include_lights
    parent_collection_name = request.parent_collection_name
    provided_mesh_files = request.mesh_files
    app_files = request.app_files
    animation_files = request.animation_files
    include_animations = request.include_animations
    generate_overrides = request.generate_overrides
    parsed_entity = request.parsed_entity
    imported_collections_out = request.imported_collections_out
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
    session = EntityImportSession(
        filepath=filepath,
        split_source_root=split_source_raw_root,
        provided_asset_index=request.asset_index,
        index_policy=request.index_policy,
        documents=request.documents,
        provided_material_resources=request.material_resources,
        clear_transient_caches=clear_transient_import_caches,
        component_depot_path=lambda component: (
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
    try:
        session.start()
    except Exception:
        try:
            session.close()
        except Exception:
            pass
        raise
    path = session.source_root
    after = session.source_relative_path
    asset_index = session.asset_index
    resources = session.resources
    execution_cache = session.execution_cache
    warning_messages = session.warnings

    rig = None
    Masters = None
    material_cache_acquired = False
    try:
        material_cache_acquired = acquire_material_cache(with_materials)
        ent_name = os.path.basename(filepath)[:-9]
        if not cp77_addon_prefs.non_verbose:
            print(f"Importing appearance: {', '.join(appearances)} from entity: {ent_name}")
        parsed_ent = parsed_entity
        if parsed_ent is None and filepath is not None:
            parsed_ent = resources.load_entity(filepath)
        if parsed_ent is None:
            return ImportResult(
                failures=(f"Failed to load entity document: {filepath}",),
                label="entity import",
            )

        ent_apps = parsed_ent.appearances
        ent_components = parsed_ent.component_dicts
        ent_component_data = parsed_ent.component_data
        ent_default = parsed_ent.default_appearance
        ent_app_index_by_name = parsed_ent.appearance_index_by_name

        appearance_resolution = normalize_appearance_requests(
            parsed_ent,
            appearances,
            ent_name,
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
        vehicle_slot_lookup = execution_cache.slot_lookup(
            vehicle_slots,
            build_slot_lookup,
        )

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
            else ()
        )

        # Animation GLBs are imported later for their animation data only. The entity rig
        # is always constructed exclusively from JSON rigs.
        rig_j = None
        rig_bone_index = {}

        if not app_files and len(ent_components) < 1:
            message = (
                "The entity contains no importable components and no appearance "
                "documents were found"
            )
            print(message)
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
            master_group_objects = resources.master_group_objects

            entity_plan = compile_entity_import_plan(
                parsed_entity=parsed_ent,
                appearances=appearances,
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
                message = (
                    f"Entity rig setup skipped for {ent_name}: "
                    f"{type(error).__name__}: {error}"
                )
                print(message)
                print(traceback.format_exc())
                if message not in warning_messages:
                    warning_messages.append(message)
                rig_runtime = EntityRigRuntime(
                    ordered_components=tuple(entity_plan.rig.ordered_components),
                )
            rig = session.register_rig(rig_runtime.rig)
            rig_j = rig_runtime.rig_json
            rig_bone_index = rig_runtime.rig_bone_index
            rig_json_by_component_name = rig_runtime.rig_json_by_component_name
            rig_json_path_by_component_name = rig_runtime.rig_json_path_by_component_name
            armature_by_component_name = rig_runtime.armature_by_component_name
            rig_json_by_bone_name = rig_runtime.rig_json_by_bone_name
            rig_component_names = frozenset(rig_json_by_component_name)

            meshes_w_apps = {
                requirement.key: {
                    'apps': [list(requirement.appearances)],
                    'sectors': [requirement.sector] if requirement.sector else [],
                    'meshpath': requirement.mesh_path,
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
                generate_overrides=generate_overrides,
                mesh_repository=resources.meshes,
                document_session=session.documents,
                material_resources=session.material_resources,
            )
            for message in mesh_import_failures:
                if message not in warning_messages:
                    warning_messages.append(message)

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
                configure_child_of_constraint=configure_child_of_constraint,
            )
            skinned_mesh_operations = EntitySkinnedMeshOperations(
                component_mesh_info=component_mesh_info,
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
                from .handlers.lights import (
                    collect_light_channel_components,
                    collect_light_components,
                    create_auxiliary_component_registry,
                )

                light_handler_registry = create_auxiliary_component_registry()

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
                    )
                    app_shape_lookup = parsed_app.shape_lookup_by_appearance_name.get(
                        parsed_app_name, {}
                    )
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
                )
                resolver_index = build_component_pass_index(
                    resolver_components,
                    execution_cache,
                    identity_token=resolver_component_token,
                )

                parent_transform_lookup = ComponentHandleLookup(app_parent_transform_lookup)
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
                )
                anim_impl_lookup = build_anim_impl_lookup(chunks)
                transform_animator_lookup = build_transform_animator_lookup(
                    resolver_index.transform_animator_components,
                    anim_impl_lookup,
                )

                for c in appearance_index.slot_components:
                    if (
                        component_name(c) in ('vehicle_slots', 'slot', 'slots')
                        and id(c) not in vehicle_slot_component_ids
                    ):
                        VS.append(c)
                        vehicle_slot_component_ids.add(id(c))

                if not vehicle_slots and VS:
                    vehicle_slots = VS[0]['slots']
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
                        comp.get('slots'),
                        build_slot_lookup,
                    )

                component_skin_placements = {}
                component_skin_placement_info = {}
                if rig_j is not None:
                    for component in resolver_index.mesh_components:
                        if not execution_cache.uses_skinning(
                            component,
                            skinning_lookup,
                            component_uses_skinning,
                        ):
                            continue
                        placement, root_bone, status = execution_cache.skin_attachment(
                            component,
                            rig_j,
                            component_mesh_json,
                            component_skin_attachment_matrix,
                        )
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
                    app_resource=current_app_resource,
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
                    lambda component: execution_cache.uses_skinning(
                        component,
                        skinning_lookup,
                        component_uses_skinning,
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
                )
                for c in appearance_index.transform_animator_components:
                    comp_name = component_name(c)
                    child_state = child_import_savepoint()
                    try:
                        _ENTITY_COMPONENT_HANDLERS.execute(c, handler_context)
                    except Exception as error:
                        rollback_import_child(child_state, f"animator component {comp_name}")
                        print('Failed on animator component ', comp_name)
                        print(traceback.format_exc())
                        message = (
                            f"Animator component failed for {comp_name}: "
                            f"{type(error).__name__}: {error}"
                        )
                        if message not in warning_messages:
                            warning_messages.append(message)

                for c in appearance_index.mesh_components:
                    if (
                        not include_lights
                        and c.get("$type") in LIGHT_RELATED_COMPONENT_TYPES
                    ):
                        continue
                    comp_name = component_name(c)
                    child_state = child_import_savepoint()
                    try:
                        handler = _ENTITY_COMPONENT_HANDLERS.handler_for(c)
                        if handler is None and light_handler_registry is not None:
                            handler = light_handler_registry.handler_for(c)
                        if handler is None:
                            mesh_service.execute(c)
                        else:
                            handler.execute(c, handler_context)
                    except Exception as error:
                        rollback_import_child(child_state, f"entity component {comp_name}")
                        message = (
                            f"Entity component skipped for {comp_name}: "
                            f"{type(error).__name__}: {error}"
                        )
                        print(message)
                        print(traceback.format_exc())
                        if message not in warning_messages:
                            warning_messages.append(message)

                if light_handler_registry is not None:
                    for c in (*light_components, *light_channel_components):
                        comp_name = component_name(c)
                        child_state = child_import_savepoint()
                        try:
                            light_handler_registry.execute(c, handler_context)
                        except Exception as error:
                            rollback_import_child(child_state, f"light component {comp_name}")
                            message = (
                                f"Light component skipped for {comp_name}: "
                                f"{type(error).__name__}: {error}"
                            )
                            print(message)
                            print(traceback.format_exc())
                            if message not in warning_messages:
                                warning_messages.append(message)
                print('Appearance import time:', time.time() - app_start_time, 'Seconds')

            if include_collisions:
                from .collisions import EntityCollisionRuntime, EntityCollisionService

                collision_target_collection = imported_appearance_collections[
                    0] if imported_appearance_collections else coll_scene
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
                        target_collection=collision_target_collection,
                        blender_context=bpy.context,
                        operations=handler_operations,
                        handler_registry=_ENTITY_COMPONENT_HANDLERS,
                    )
                )
                child_state = child_import_savepoint()
                try:
                    collision_service.execute(
                        include_collisions=include_collisions,
                        include_phys=include_phys,
                        include_entity_colliders=include_entity_colliders,
                    )
                except Exception as error:
                    rollback_import_child(child_state, f"entity collision import {ent_name}")
                    message = (
                        f"Entity collision import skipped for {ent_name}: "
                        f"{type(error).__name__}: {error}"
                    )
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
        try:
            session.close(rig)
        finally:
            release_material_cache(material_cache_acquired)
    return ImportResult(
        created_items=created_collections,
        warnings=warnings,
        label="entity import",
    )


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
        failures = list(result.failures)
        rollback_error = rollback_report_message(report)
        if rollback_error:
            failures.append("Rollback incomplete: " + rollback_error)
        return ImportResult(
            created_items=(),
            warnings=result.warnings,
            failures=tuple(failures),
            label=result.label,
        )
    transaction.commit()
    return result


__all__ = ("EntityImportRequest", "import_entity")
