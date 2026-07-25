from __future__ import annotations

from collections import Counter, defaultdict

from .model import PlannedSector, SectorNodePlan
from .model import NodeCategory
from .registry import NODE_HANDLERS
from . import handlers as _handlers


_PROXY_PHASE = 30
_STANDARD_PHASE = 20


def compile_sector_plan(parsed_sector, options, registry=NODE_HANDLERS):
    plans = []
    placement_by_phase = defaultdict(list)
    skipped = Counter()
    active = set()

    for node in parsed_sector.nodes:
        skip_reason = options.node_skip_reason(node)
        enabled = not skip_reason
        if enabled:
            active.add(node.index)
        else:
            skipped[skip_reason] += 1

        binding = registry.get(node.node_type)
        phase = (
            binding.placement_phase
            if binding is not None
            else (
                _PROXY_PHASE
                if node.category is NodeCategory.PROXY
                else _STANDARD_PHASE
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
        active_node_indexes=frozenset(active),
        skipped_by_reason=dict(skipped),
    )
