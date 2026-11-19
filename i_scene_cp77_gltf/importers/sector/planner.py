from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from ...assetio.sector_model import (
    PROXY_PHASE,
    STANDARD_PHASE,
    NodeCategory,
    PlannedSector,
    SectorNodePlan,
)
from .handlers import register_default_handlers
from .options import classify_node_type
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


def _trim_instances(planned_sector, kept_instances, skip_reason):
    """Trim each enabled plan to kept_instances(node): the instances to keep, or None to leave the plan alone

    Plans left with no instances are disabled with skip_reason. Returns the revised plan and the (plan, kept) pairs
    that changed.
    """
    changed = []
    revised = {}
    for plan in planned_sector.plans:
        if not plan.enabled:
            continue
        node = plan.node
        kept = kept_instances(node)
        if kept is None:
            continue
        changed.append((plan, kept))
        if kept:
            revised[id(plan)] = replace(plan, node=replace(node, instances=kept))
        else:
            revised[id(plan)] = replace(
                plan, enabled=False, skip_reason=str(skip_reason), dependencies=()
            )
    if not revised:
        return planned_sector, ()
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
    ), tuple(changed)


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
                PROXY_PHASE
                if classify_node_type(node.node_type) is NodeCategory.PROXY
                else STANDARD_PHASE
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

    def missing_instances(node):
        if not node.instances:
            return () if node.index in placed.entryless_nodes else None
        if node.index in placed.recorded_nodes:
            return ()
        missing = tuple(
            instance
            for instance in node.instances
            if instance.index not in placed.node_data
        )
        return missing if len(missing) < len(node.instances) else None

    planned_sector, changed = _trim_instances(
        planned_sector, missing_instances, skip_reason
    )
    return planned_sector, sum(1 for _plan, kept in changed if not kept)


def _variant_lookup(variant_indices, node_data_count):
    """The variant of each node data entry: None for the always-on base nodes, k for the nodes of variant k

    variantIndices[k] is where variant k's entries start; variant 0 is the base, and the last variant runs to the end
    of nodeData. variantNodes[k - 1] describes variant k.
    """
    if len(variant_indices) < 2 or node_data_count <= 0:
        return ()
    lookup = [None] * node_data_count
    ends = (*variant_indices[1:], node_data_count)
    for variant_index in range(1, len(variant_indices)):
        start = max(0, int(variant_indices[variant_index]))
        end = min(node_data_count, int(ends[variant_index]))
        for index in range(start, end):
            lookup[index] = variant_index
    return tuple(lookup)


def exclude_variant_entries(planned_sector):
    """Drop the node data entries of the sector's quest variants, keeping its always-on base nodes

    Returns the revised plan and the number of entries dropped.
    """
    parsed = planned_sector.parsed
    lookup = _variant_lookup(parsed.variant_indices, parsed.node_data_count)
    if not lookup:
        return planned_sector, 0

    def base_instances(node):
        if not node.instances:
            return None
        kept = tuple(
            instance
            for instance in node.instances
            if not (
                0 <= instance.index < len(lookup) and lookup[instance.index] is not None
            )
        )
        return kept if len(kept) < len(node.instances) else None

    planned_sector, changed = _trim_instances(planned_sector, base_instances, "variant")
    return planned_sector, sum(
        len(plan.node.instances) - len(kept) for plan, kept in changed
    )
