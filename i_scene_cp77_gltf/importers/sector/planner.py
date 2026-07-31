from __future__ import annotations

from collections import defaultdict

from .model import PlannedSector, SectorNodePlan
from .model import NodeCategory
from .registry import NODE_HANDLERS
from .handlers import dependencies as _dependencies
from .handlers import placement as _placement

_HANDLER_MODULES = (_dependencies, _placement)


_PROXY_PHASE = 30
_STANDARD_PHASE = 20


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
    )
