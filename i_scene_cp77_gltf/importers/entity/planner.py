from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from .model import (
    AppearanceRequestResolution,
    EntityAppearancePlan,
    EntityImportPlan,
    EntityMeshRequirement,
    EntityRigComponentPlan,
    EntityRigPlan,
)
from ..common.entity_data import (
    ent_appearance_name,
    resolve_ent_appearance_alias,
    resolve_requested_appearance_name,
)
from ..common.entity_data import component_name
from ..common.handles import build_embedded_handle_lookup
from ..common.paths import depot_path_key, depot_path_value, depot_to_local_path
from .policy import (
    APPEARANCE_PROXY_COMPONENT_TYPES,
    LIGHT_RELATED_COMPONENT_TYPES,
    is_excluded_mesh,
    STATIC_OCCLUDER_COMPONENT_TYPES,
    ZERO_MASK_CULLED_COMPONENT_TYPES,
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
    return resolve_ent_appearance_alias(
        app_name, ent_apps, by_appearance, by_name
    )[0] >= 0


def normalize_appearance_requests(
    parsed_entity: Any,
    requested_appearances: Iterable[str],
    entity_name: str,
    choose: Callable[[Sequence[str]], str],
) -> AppearanceRequestResolution:
    """Normalize authored appearance-request semantics without Blender state."""
    appearances = list(requested_appearances or ("",))
    if not appearances:
        appearances = [""]

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

    if ent_default == "random":
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

    if appearances and (
        len(appearances[0]) == 0 or appearances[0].upper() == "ALL"
    ):
        appearances = list(dict.fromkeys(ent_applist))
    if not appearances:
        appearances.append("default")

    return AppearanceRequestResolution(
        appearances=tuple(appearances),
        default_appearance=ent_default,
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
    default_appearance: str,
    source_root: str,
    asset_index: Any,
    load_app: Callable[[str], Any | None],
    component_mesh_info: Callable[[dict], tuple[str, str, str, str, bool]],
    excluded_meshes: set[str] | frozenset[str],
    include_occluders: bool = False,
    include_proxies: bool = False,
    include_lights: bool = False,
    resolve_export: Callable[[str, Any], str] | None = None,
) -> EntityImportPlan:
    """Compile the appearance, mesh, and rig plan."""
    resource_resolver = resolve_export or asset_index.resolve_export

    ent_apps = parsed_entity.appearances
    ent_components = parsed_entity.component_dicts
    ent_component_data = parsed_entity.component_data
    by_appearance = parsed_entity.appearances_by_appearance
    by_name = parsed_entity.appearances_by_name

    appearance_plans: list[EntityAppearancePlan] = []
    messages: list[str] = []
    mesh_entries: dict[str, dict[str, Any]] = {}
    mesh_appearance_sets: dict[str, set[str]] = {}
    seen_mesh_components: set[int] = set()

    for requested_name in appearances:
        display_name = resolve_requested_appearance_name(
            requested_name, default_appearance, ent_apps, by_appearance, by_name
        )
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

        if requested_name == "BASE_COMPONENTS_ONLY":
            chunks = tuple(ent_component_data or ()) or None
        elif not ent_apps and ent_component_data:
            chunks = tuple(ent_component_data)
        elif ent_apps:
            entity_appearance_index, resolved_name, resolve_messages = _resolve_ent_app(
                resolved_name, ent_apps, by_appearance, by_name, default_appearance
            )
            messages.extend(resolve_messages)
            ent_app = ent_apps[entity_appearance_index]
            app_resource_depot = depot_path_value(
                ent_app,
                "appearanceResource",
            )
            app_resource_path = (
                resource_resolver(app_resource_depot, ".app.json") or ""
            )
            if not app_resource_path:
                messages.append(
                    "app file not found - "
                    + depot_to_local_path(source_root, app_resource_depot)
                    + ".json"
                )
            else:
                parsed_app = load_app(app_resource_path)
                if parsed_app is not None:
                    app_index = parsed_app.appearances_by_name.get(resolved_name)
                    if app_index is None:
                        available = ", ".join(parsed_app.appearance_names)
                        messages.append(
                            f"appearance '{resolved_name}' not found in "
                            f"{os.path.basename(app_resource_path)}; available: {available}"
                        )
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
            chunks=tuple(chunks or ()),
            used_root_fallback=used_root_fallback,
        )
        appearance_plans.append(plan)

        for component in merged_components:
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
                if (
                    component_type in LIGHT_RELATED_COMPONENT_TYPES
                    and not include_lights
                ):
                    continue
            if _is_zero_mask_culled(component):
                continue
            component_id = id(component)
            if component_id in seen_mesh_components:
                continue
            seen_mesh_components.add(component_id)
            depot_path, mesh_name, mesh_path, mesh_appearance, _enabled = (
                component_mesh_info(component)
            )
            if (
                not depot_path
                or not mesh_name
                or not mesh_path
                or is_excluded_mesh(
                    depot_path,
                    mesh_path,
                    mesh_name,
                    excluded_meshes,
                )
            ):
                continue
            mesh_key = depot_to_local_path(source_root, depot_path)
            canonical_mesh_key = depot_path_key(depot_path)
            entry = mesh_entries.get(canonical_mesh_key)
            if entry is None:
                mesh_entries[canonical_mesh_key] = {
                    "key": mesh_key,
                    "depot_path": depot_path,
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

    ordered_rig_components: list[dict] = []
    seen_rig_components: set[int] = set()
    control_targets: dict[int, str] = {}

    def append_rig_components(
        source_components: Iterable[dict],
        control_binding_lookup: Mapping[Any, dict] | None,
    ) -> None:
        for component in source_components or ():
            if not is_animated_rig_component(component):
                continue
            component_id = id(component)
            if component_id in seen_rig_components:
                continue
            seen_rig_components.add(component_id)
            ordered_rig_components.append(component)
            control_targets[component_id] = animated_component_control_target(
                component, control_binding_lookup
            )

    root_control_lookup = build_embedded_handle_lookup(
        ent_component_data,
        "controlBinding",
    )
    append_rig_components(ent_components, root_control_lookup)
    app_control_lookups: dict[tuple[int, str], dict[Any, dict]] = {}
    for appearance_plan in appearance_plans:
        if appearance_plan.parsed_app is not None:
            lookup_key = (id(appearance_plan.parsed_app), appearance_plan.parsed_app_name)
            control_lookup = app_control_lookups.get(lookup_key)
            if control_lookup is None:
                app_chunks = appearance_plan.parsed_app.chunks_by_appearance_name.get(
                    appearance_plan.parsed_app_name, ()
                )
                control_lookup = build_embedded_handle_lookup(
                    app_chunks,
                    "controlBinding",
                )
                app_control_lookups[lookup_key] = control_lookup
        else:
            control_lookup = None
        append_rig_components(
            appearance_plan.appearance_components,
            control_lookup,
        )

    ordered_rig_components, ordering_messages = order_animated_rig_components(
        ordered_rig_components, control_targets
    )
    messages.extend(ordering_messages)

    ordered_by_name = {
        component_name(component): component for component in ordered_rig_components
    }
    deformation_authorities: list[str] = []
    deformation_authority_set: set[str] = set()
    rig_component_plans: list[EntityRigComponentPlan] = []
    for component in ordered_rig_components:
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
        rig_component_plans.append(
            EntityRigComponentPlan(
                component=component,
                component_name=name,
                rig_depot_path=depot_path_value(component, "rig"),
                control_target=target,
                is_deformation_rig=deformation,
            )
        )

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
        ),
        messages=tuple(messages),
    )
