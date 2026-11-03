from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from ...assetio.paths import depot_path_key
from ...assetio.values import build_embedded_handle_lookup
from ..common.entity_data import (
    component_name,
    ent_appearance_name,
    resolve_ent_appearance_alias,
    resolve_requested_appearance_name,
)
from ..common.paths import depot_path, depot_to_local_path
from .execution_cache import build_component_pass_index
from .model import (
    AppearanceRequestResolution,
    EntityAppearancePlan,
    EntityImportPlan,
    EntityMeshRequirement,
    EntityRigComponentPlan,
    EntityRigPlan,
)
from .policy import (
    APPEARANCE_PROXY_COMPONENT_TYPES,
    STATIC_OCCLUDER_COMPONENT_TYPES,
    ZERO_MASK_CULLED_COMPONENT_TYPES,
    is_excluded_mesh,
    light_component_skipped,
)
from .rig_planning import (
    animated_component_control_target,
    is_animated_rig_component,
    is_deformation_rig_component,
    order_animated_rig_components,
)


def appearance_request_is_known(
    app_name: str,
    ent_default: str,
    ent_apps: Sequence[dict],
    by_appearance: Mapping[str, Any],
    by_name: Mapping[str, Any],
) -> bool:
    if not app_name or app_name == "BASE_COMPONENTS_ONLY" or app_name.upper() == "ALL":
        return True
    if app_name == "default":
        return (
            not ent_apps
            or not ent_default
            or resolve_ent_appearance_alias(
                ent_default, ent_apps, by_appearance, by_name
            )[0]
            >= 0
        )
    return (
        resolve_ent_appearance_alias(app_name, ent_apps, by_appearance, by_name)[0] >= 0
    )


def normalize_appearance_requests(
    parsed_entity: Any,
    requested_appearances: Iterable[str],
    entity_name: str,
    choose: Callable[[Sequence[str]], str],
) -> AppearanceRequestResolution:
    """Normalize authored appearance-request semantics without Blender state"""
    appearances = list(requested_appearances or ("",))
    if not appearances:
        appearances = [""]
    import_all = not appearances[0] or str(appearances[0]).upper() == "ALL"

    ent_apps = parsed_entity.appearances
    ent_default = parsed_entity.default_appearance
    ent_applist = parsed_entity.appearance_names
    by_appearance = parsed_entity.appearances_by_appearance
    by_name = parsed_entity.appearances_by_name
    messages: list[str] = []

    if not ent_applist:
        messages.append(
            f"No appearances found in entity file {entity_name}. "
            "Imported objects may be incomplete or missing."
        )

    if ent_default == "random" and not import_all:
        if ent_applist:
            ent_default = choose(ent_applist)
            messages.append(f"Default appearance set to random choice: {ent_default}")
        else:
            ent_default = "default"
            messages.append(
                "No explicit appearances available; using the implicit default appearance."
            )

    for index, app in enumerate(appearances):
        app = str(app)
        if app.lower() == "random":
            if ent_applist:
                appearances[index] = choose(ent_applist)
                messages.append(
                    f"Random appearance requested: using {appearances[index]}"
                )
            else:
                appearances[index] = "default"
                messages.append(
                    "No explicit appearances available; random resolved to the "
                    "implicit default appearance."
                )
            continue

        if app == "default":
            if ent_default:
                resolved_default = resolve_requested_appearance_name(
                    app, ent_default, ent_apps, by_appearance, by_name
                )
                messages.append(
                    f"Using default appearance {resolved_default} for entity {entity_name}."
                )
                continue
            if ent_applist:
                ent_default = ent_applist[0]
                messages.append(
                    f"No default appearance specified in entity {entity_name}. "
                    f"Using first available appearance {ent_default}."
                )
                continue
            appearances[index] = "default"
            messages.append(
                f"No explicit appearances specified in entity {entity_name}. "
                "Using the implicit default appearance."
            )
            continue

        if not appearance_request_is_known(
            app, ent_default, ent_apps, by_appearance, by_name
        ):
            messages.append(
                f"Appearance {app} not found in entity {entity_name}. "
                f"Available appearances: {', '.join(ent_applist)}"
            )

    if import_all:
        appearances = [ent_appearance_name(app) for app in ent_apps]
        appearance_indices = tuple(range(len(ent_apps)))
    else:
        appearance_indices = (None,) * len(appearances)
    if not appearances:
        appearances.append("default")
        appearance_indices = (None,)

    return AppearanceRequestResolution(
        appearances=tuple(appearances),
        default_appearance=ent_default,
        appearance_indices=appearance_indices,
        messages=tuple(messages),
    )


def merge_components_first_wins(
    primary: Iterable[dict] | None,
    secondary: Iterable[dict] | None,
) -> tuple[dict, ...]:
    merged = list(primary or ())
    seen: set[str] = set()
    for component in merged:
        name = component_name(component)
        if name:
            seen.add(name)
    for component in secondary or ():
        name = component_name(component)
        if name and name in seen:
            continue
        if name:
            seen.add(name)
        merged.append(component)
    return tuple(merged)


def _resolve_ent_app(
    app_name: str,
    ent_apps: Sequence[dict],
    by_appearance: Mapping[str, Any],
    by_name: Mapping[str, Any],
    ent_default: str | None,
) -> tuple[int, str, tuple[str, ...]]:
    candidates: list[tuple[str, str]] = []
    if app_name and app_name != "default":
        candidates.append((app_name, app_name))
    if ent_default and ent_default not in {"default", "None"}:
        candidates.append((ent_default, app_name))

    seen: set[str] = set()
    messages: list[str] = []
    for search_term, fallback_name in candidates:
        if search_term in seen:
            continue
        seen.add(search_term)
        ent_app_idx, resolved_name = resolve_ent_appearance_alias(
            search_term, ent_apps, by_appearance, by_name
        )
        if ent_app_idx >= 0:
            messages.append(f"appearance matched, id =  {ent_app_idx}")
            if search_term != resolved_name and search_term != fallback_name:
                messages.append(
                    f"appearance alias resolved: {search_term} -> {resolved_name}"
                )
            return ent_app_idx, resolved_name or fallback_name, tuple(messages)

    fallback = ent_appearance_name(ent_apps[0], app_name) if ent_apps else app_name
    return 0, fallback, tuple(messages)


def _is_zero_mask_culled(component: Any) -> bool:
    if type(component) is not dict:
        return False
    if component.get("$type") not in ZERO_MASK_CULLED_COMPONENT_TYPES:
        return False
    try:
        return int(component.get("chunkMask")) == 0
    except (TypeError, ValueError):
        return False


def compile_entity_import_plan(
    *,
    parsed_entity: Any,
    appearances: Sequence[str],
    appearance_indices: Sequence[int | None],
    default_appearance: str,
    source_root: str,
    asset_index: Any,
    load_app: Callable[[str], Any | None],
    component_mesh_info: Callable[[dict], tuple[str, str, str, str, bool]],
    excluded_meshes: set[str] | frozenset[str],
    include_occluders: bool = False,
    include_proxies: bool = False,
    include_lights: bool = False,
    include_light_channels: bool = False,
    resolve_export: Callable[[str, Any], str] | None = None,
    mesh_is_excluded: Callable[[str, str, str, Any], bool] = is_excluded_mesh,
) -> EntityImportPlan:
    """Compile the appearance, mesh, and rig plan"""
    resource_resolver = resolve_export or asset_index.resolve_export

    ent_apps = parsed_entity.appearances
    ent_components = parsed_entity.component_dicts
    ent_component_data = parsed_entity.component_data
    by_appearance = parsed_entity.appearances_by_appearance
    by_name = parsed_entity.appearances_by_name

    appearance_plans: list[EntityAppearancePlan] = []
    root_component_index = build_component_pass_index(ent_components)
    messages: list[str] = []
    warnings: list[str] = []
    mesh_entries: dict[str, dict[str, Any]] = {}
    mesh_appearance_sets: dict[str, set[str]] = {}
    seen_mesh_components: set[int] = set()

    for requested_name, exact_index in zip(
        appearances, appearance_indices, strict=True
    ):
        if exact_index is not None and (
            type(exact_index) is not int or not 0 <= exact_index < len(ent_apps)
        ):
            raise ValueError(
                "Entity appearance index is outside the authored appearance table."
            )
        if exact_index is None:
            display_name = resolve_requested_appearance_name(
                requested_name, default_appearance, ent_apps, by_appearance, by_name
            )
        else:
            display_name = ent_appearance_name(ent_apps[exact_index], requested_name)
        resolved_name = display_name
        entity_appearance_index: int | None = None
        app_resource_depot = ""
        app_resource_path = ""
        parsed_app = None
        parsed_app_name = ""
        appearance_components: tuple[dict, ...] = ()
        merged_components: tuple[dict, ...] = ()
        chunks: tuple[dict, ...] | None = None
        used_root_fallback = False

        if exact_index is None and requested_name == "BASE_COMPONENTS_ONLY":
            chunks = tuple(ent_component_data or ()) or None
        elif not ent_apps and ent_component_data:
            chunks = tuple(ent_component_data)
        elif ent_apps:
            if exact_index is None:
                entity_appearance_index, resolved_name, resolve_messages = (
                    _resolve_ent_app(
                        requested_name,
                        ent_apps,
                        by_appearance,
                        by_name,
                        default_appearance,
                    )
                )
            else:
                entity_appearance_index = exact_index
                resolved_name = display_name
                resolve_messages = ()
            messages.extend(resolve_messages)
            ent_app = ent_apps[entity_appearance_index]
            app_resource_depot = depot_path(
                ent_app,
                "appearanceResource",
                normalize=False,
            )
            app_resource_path = resource_resolver(app_resource_depot, ".app.json") or ""
            if not app_resource_path:
                message = (
                    "Appearance resource not found: "
                    + depot_to_local_path(source_root, app_resource_depot)
                    + ".json"
                )
                messages.append(message)
                warnings.append(message)
            else:
                parsed_app = load_app(app_resource_path)
                if parsed_app is not None:
                    app_index = parsed_app.appearances_by_name.get(resolved_name)
                    if app_index is None:
                        available = ", ".join(parsed_app.appearance_names)
                        message = (
                            f"appearance '{resolved_name}' not found in "
                            f"{os.path.basename(app_resource_path)}; available: {available}"
                        )
                        messages.append(message)
                        warnings.append(message)
                    else:
                        parsed_app_name = resolved_name
                        messages.append(f"appearance matched, id =  {app_index}")
                        appearance_components = tuple(
                            parsed_app.components_by_appearance_name.get(
                                parsed_app_name, ()
                            )
                        )
                        if appearance_components:
                            merged_components = merge_components_first_wins(
                                ent_components, appearance_components
                            )
                        app_chunks = parsed_app.chunks_by_appearance_name.get(
                            parsed_app_name
                        )
                        chunks = tuple(app_chunks) if app_chunks is not None else None
                        if chunks:
                            messages.append("Chunks found")

        if not merged_components:
            used_root_fallback = True
            merged_components = tuple(ent_components)
            messages.append("falling back to rootchunk components...")

        component_index = (
            root_component_index
            if merged_components is ent_components
            else build_component_pass_index(merged_components)
        )
        plan = EntityAppearancePlan(
            requested_name=requested_name,
            display_name=display_name,
            resolved_name=resolved_name,
            entity_appearance_index=entity_appearance_index,
            app_resource_depot=app_resource_depot,
            app_resource_path=app_resource_path,
            parsed_app=parsed_app,
            parsed_app_name=parsed_app_name,
            root_components=tuple(ent_components),
            appearance_components=appearance_components,
            merged_components=merged_components,
            component_index=component_index,
            chunks=tuple(chunks or ()),
            used_root_fallback=used_root_fallback,
        )
        appearance_plans.append(plan)

        for component in component_index.mesh_components:
            if type(component) is dict:
                component_type = component.get("$type")
                if (
                    component_type in STATIC_OCCLUDER_COMPONENT_TYPES
                    and not include_occluders
                ):
                    continue
                if (
                    component_type in APPEARANCE_PROXY_COMPONENT_TYPES
                    and not include_proxies
                ):
                    continue
                if light_component_skipped(
                    component_type,
                    include_lights=include_lights,
                    include_light_channels=include_light_channels,
                ):
                    continue
            if _is_zero_mask_culled(component):
                continue
            component_id = id(component)
            if component_id in seen_mesh_components:
                continue
            seen_mesh_components.add(component_id)
            mesh_depot_path, mesh_name, mesh_path, mesh_appearance, _enabled = (
                component_mesh_info(component)
            )
            if mesh_is_excluded(
                mesh_depot_path,
                mesh_path,
                mesh_name,
                excluded_meshes,
            ):
                continue
            if mesh_depot_path and not mesh_path:
                warnings.append(f"Mesh resource not found: {mesh_depot_path}")
            if not mesh_depot_path or not mesh_name or not mesh_path:
                continue
            mesh_key = depot_to_local_path(source_root, mesh_depot_path)
            canonical_mesh_key = depot_path_key(mesh_depot_path)
            entry = mesh_entries.get(canonical_mesh_key)
            if entry is None:
                mesh_entries[canonical_mesh_key] = {
                    "key": mesh_key,
                    "depot_path": mesh_depot_path,
                    "mesh_name": mesh_name,
                    "mesh_path": mesh_path,
                    "appearances": [mesh_appearance],
                }
                mesh_appearance_sets[canonical_mesh_key] = {mesh_appearance}
            else:
                appearance_set = mesh_appearance_sets[canonical_mesh_key]
                if mesh_appearance not in appearance_set:
                    appearance_set.add(mesh_appearance)
                    entry["appearances"].append(mesh_appearance)
                if mesh_path and not entry.get("mesh_path"):
                    entry["mesh_path"] = mesh_path

    def collect_rig_components(
        source_components: Iterable[dict],
        control_binding_lookup: Mapping[Any, dict] | None,
        output: list[dict],
        seen: set[tuple[str, str]],
        targets: dict[int, str],
    ) -> None:
        for component in source_components or ():
            if not is_animated_rig_component(component):
                continue
            key = (
                component_name(component).casefold(),
                depot_path_key(depot_path(component, "rig", normalize=False)),
            )
            if key in seen:
                continue
            seen.add(key)
            output.append(component)
            targets[id(component)] = animated_component_control_target(
                component, control_binding_lookup
            )

    root_control_lookup = build_embedded_handle_lookup(
        ent_component_data,
        "controlBinding",
    )
    base_rig_components: list[dict] = []
    active_overlay_components: list[dict] = []
    ordered_rig_components: list[dict] = []
    seen_rig_components: set[tuple[str, str]] = set()
    control_targets: dict[int, str] = {}

    collect_rig_components(
        root_component_index.rig_components,
        root_control_lookup,
        ordered_rig_components,
        seen_rig_components,
        control_targets,
    )
    base_ids = {id(component) for component in ordered_rig_components}

    active_appearance = appearance_plans[0] if appearance_plans else None
    if active_appearance is not None and active_appearance.parsed_app is not None:
        active_chunks = active_appearance.parsed_app.chunks_by_appearance_name.get(
            active_appearance.parsed_app_name, ()
        )
        active_control_lookup = build_embedded_handle_lookup(
            active_chunks,
            "controlBinding",
        )
        before_ids = {id(component) for component in ordered_rig_components}
        collect_rig_components(
            active_appearance.appearance_components,
            active_control_lookup,
            ordered_rig_components,
            seen_rig_components,
            control_targets,
        )
        active_overlay_components = [
            component
            for component in ordered_rig_components
            if id(component) not in before_ids
        ]

    ordered_rig_components, ordering_messages = order_animated_rig_components(
        ordered_rig_components, control_targets
    )
    messages.extend(ordering_messages)
    base_rig_components = [
        component for component in ordered_rig_components if id(component) in base_ids
    ]
    overlay_ids = {id(component) for component in active_overlay_components}
    active_overlay_components = [
        component
        for component in ordered_rig_components
        if id(component) in overlay_ids
    ]

    ordered_by_name = {
        component_name(component): component for component in ordered_rig_components
    }
    deformation_authorities: list[str] = []
    deformation_authority_set: set[str] = set()

    def component_plans(components):
        plans = []
        for component in components:
            name = component_name(component)
            target = control_targets.get(id(component), "")
            deformation = is_deformation_rig_component(component)
            if (
                deformation
                and target in ordered_by_name
                and target not in deformation_authority_set
            ):
                deformation_authority_set.add(target)
                deformation_authorities.append(target)
            plans.append(
                EntityRigComponentPlan(
                    component=component,
                    component_name=name,
                    rig_depot_path=depot_path(component, "rig", normalize=False),
                    control_target=target,
                    is_deformation_rig=deformation,
                )
            )
        return tuple(plans)

    rig_component_plans = component_plans(ordered_rig_components)
    base_component_plans = component_plans(base_rig_components)
    overlay_component_plans = component_plans(active_overlay_components)

    mesh_requirements = tuple(
        EntityMeshRequirement(
            key=entry["key"],
            depot_path=entry["depot_path"],
            mesh_name=entry["mesh_name"],
            mesh_path=entry["mesh_path"],
            appearances=tuple(entry["appearances"]),
        )
        for key, entry in mesh_entries.items()
    )

    return EntityImportPlan(
        appearances=tuple(appearances),
        default_appearance=default_appearance,
        appearance_plans=tuple(appearance_plans),
        mesh_requirements=mesh_requirements,
        rig=EntityRigPlan(
            components=tuple(rig_component_plans),
            deformation_authorities=tuple(deformation_authorities),
            base_components=tuple(base_component_plans),
            overlay_components=tuple(overlay_component_plans),
        ),
        warnings=tuple(dict.fromkeys(warnings)),
        messages=tuple(messages),
    )
