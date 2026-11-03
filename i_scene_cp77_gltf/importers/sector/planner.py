from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from .handlers import register_default_handlers
from .model import (
    PROXY_PHASE,
    STANDARD_PHASE,
    NodeCategory,
    PlannedSector,
    SectorNodePlan,
)
from .registry import NODE_HANDLERS

register_default_handlers()


def _mesh_dependencies(plans):
    return tuple(
        dependency
        for plan in plans
        if plan.enabled
        for dependency in plan.dependencies
        if dependency.kind == "mesh" and dependency.depot_path
    )


def compile_sector_plan(parsed_sector, options, registry=NODE_HANDLERS):
    plans = []
    placement_by_phase = defaultdict(list)
    for node in parsed_sector.nodes:
        skip_reason = options.node_skip_reason(node)
        enabled = not skip_reason
        binding = registry.get(node.node_type)
        phase = (
            binding.placement_phase
            if binding is not None
            else (
                PROXY_PHASE if node.category is NodeCategory.PROXY else STANDARD_PHASE
            )
        )
        dependencies = (
            binding.collect_dependencies(parsed_sector, node)
            if enabled and binding is not None
            else ()
        )
        plan = SectorNodePlan(
            node=node,
            enabled=enabled,
            skip_reason=skip_reason,
            placement_phase=phase,
            handler_name=(binding.name if binding is not None else "legacy"),
            dependencies=dependencies,
        )
        plans.append(plan)
        if enabled:
            placement_by_phase[phase].append(plan)

    return PlannedSector(
        parsed=parsed_sector,
        plans=tuple(plans),
        ordered_placement_plans=tuple(
            plan
            for phase in sorted(placement_by_phase)
            for plan in placement_by_phase[phase]
        ),
        mesh_dependencies=_mesh_dependencies(plans),
    )


def exclude_placed_entries(planned_sector, placed, skip_reason):
    """Drop what placed says the scene already holds"""
    skipped = 0
    revised = {}
    for plan in planned_sector.plans:
        node = plan.node
        if not plan.enabled:
            continue
        if not node.instances:
            missing = ()
            placed_whole = node.index in placed.entryless_nodes
        else:
            missing = (
                ()
                if node.index in placed.recorded_nodes
                else tuple(
                    instance
                    for instance in node.instances
                    if instance.index not in placed.node_data
                )
            )
            placed_whole = not missing
        if placed_whole:
            revised[id(plan)] = replace(
                plan, enabled=False, skip_reason=str(skip_reason), dependencies=()
            )
            skipped += 1
        elif len(missing) < len(node.instances):
            revised[id(plan)] = replace(plan, node=replace(node, instances=missing))
    if not revised:
        return planned_sector, 0
    plans = tuple(revised.get(id(plan), plan) for plan in planned_sector.plans)
    return replace(
        planned_sector,
        plans=plans,
        ordered_placement_plans=tuple(
            plan
            for plan in (
                revised.get(id(plan), plan)
                for plan in planned_sector.ordered_placement_plans
            )
            if plan.enabled
        ),
        mesh_dependencies=_mesh_dependencies(plans),
    ), skipped
