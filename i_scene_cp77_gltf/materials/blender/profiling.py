<<<<<<< Updated upstream
from time import perf_counter
from typing import Any, Mapping

_MATERIAL_PROFILING_ENABLED = False
=======
import contextvars
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

_MATERIAL_PROFILING_ENABLED = False
_PROFILE_DETAILS_KEY = "__material_builds__"
_SLOW_BUILD_LIMIT = 5
_IMAGE_PHASES = frozenset(
    {
        "material.image_lookup",
        "material.image_resolve",
        "material.image_create",
    }
)
_ACTIVE_COLLECTOR = contextvars.ContextVar(
    "cp77_material_profiling_collector",
    default=None,
)
_ACTIVE_BUILD = contextvars.ContextVar(
    "cp77_material_profiling_build",
    default=None,
)


@dataclass(slots=True)
class MaterialPhaseAggregate:
    seconds: float = 0.0
    count: int = 0
    maximum: float = 0.0

    def record(self, seconds: float) -> None:
        elapsed = max(0.0, float(seconds))
        self.seconds += elapsed
        self.count += 1
        self.maximum = max(self.maximum, elapsed)

    def snapshot(self) -> dict[str, float | int]:
        return {
            "seconds": self.seconds,
            "count": self.count,
            "maximum": self.maximum,
        }


@dataclass(slots=True)
class MaterialBuildAggregate(MaterialPhaseAggregate):
    body_seconds: float = 0.0
    organization_seconds: float = 0.0
    residual_seconds: float = 0.0
    node_seconds: float = 0.0
    link_seconds: float = 0.0
    image_seconds: float = 0.0
    node_group_seconds: float = 0.0
    nodes_added: int = 0
    links_added: int = 0
    node_groups_added: int = 0

    def record_build(self, build) -> None:
        self.record(build.seconds)
        self.body_seconds += build.body_seconds
        self.organization_seconds += build.organization_seconds
        self.residual_seconds += build.residual_seconds
        self.node_seconds += build.node_seconds
        self.link_seconds += build.link_seconds
        self.image_seconds += build.image_seconds
        self.node_group_seconds += build.node_group_seconds
        self.nodes_added += build.nodes_added
        self.links_added += build.links_added
        self.node_groups_added += build.node_groups_added

    def snapshot(self) -> dict[str, float | int]:
        return {
            **MaterialPhaseAggregate.snapshot(self),
            "body_seconds": self.body_seconds,
            "organization_seconds": self.organization_seconds,
            "residual_seconds": self.residual_seconds,
            "node_seconds": self.node_seconds,
            "link_seconds": self.link_seconds,
            "image_seconds": self.image_seconds,
            "node_group_seconds": self.node_group_seconds,
            "nodes_added": self.nodes_added,
            "links_added": self.links_added,
            "node_groups_added": self.node_groups_added,
        }


@dataclass(slots=True)
class MaterialBuildRecord:
    material: str
    template: str
    handler: str
    decal: bool = False
    seconds: float = 0.0
    body_seconds: float = 0.0
    organization_seconds: float = 0.0
    residual_seconds: float = 0.0
    node_seconds: float = 0.0
    link_seconds: float = 0.0
    image_seconds: float = 0.0
    node_group_seconds: float = 0.0
    nodes_added: int = 0
    links_added: int = 0
    node_groups_added: int = 0
    succeeded: bool = False
    nested_phases: dict[str, float] = field(default_factory=dict)

    def record_nested(self, phase: str, seconds: float) -> None:
        self.nested_phases[phase] = self.nested_phases.get(phase, 0.0) + max(
            0.0, float(seconds)
        )

    def finalize(
        self,
        *,
        seconds: float,
        body_seconds: float,
        organization_seconds: float,
        nodes_added: int,
        links_added: int,
        node_groups_added: int,
        succeeded: bool,
    ) -> None:
        self.seconds = max(0.0, float(seconds))
        self.body_seconds = max(0.0, float(body_seconds))
        self.organization_seconds = max(0.0, float(organization_seconds))
        self.node_seconds = self.nested_phases.get(
            "material.node_create",
            0.0,
        )
        self.link_seconds = self.nested_phases.get(
            "material.link_create",
            0.0,
        )
        self.image_seconds = sum(
            self.nested_phases.get(phase, 0.0) for phase in _IMAGE_PHASES
        )
        self.node_group_seconds = self.nested_phases.get(
            "material.node_group_cold_build",
            0.0,
        )
        accounted = min(
            self.body_seconds,
            self.node_seconds + self.link_seconds + self.image_seconds,
        )
        self.residual_seconds = max(0.0, self.body_seconds - accounted)
        self.nodes_added = max(0, int(nodes_added))
        self.links_added = max(0, int(links_added))
        self.node_groups_added = max(0, int(node_groups_added))
        self.succeeded = bool(succeeded)

    def snapshot(self) -> dict[str, Any]:
        return {
            "material": self.material,
            "template": self.template,
            "handler": self.handler,
            "decal": self.decal,
            "seconds": self.seconds,
            "body_seconds": self.body_seconds,
            "organization_seconds": self.organization_seconds,
            "residual_seconds": self.residual_seconds,
            "node_seconds": self.node_seconds,
            "link_seconds": self.link_seconds,
            "image_seconds": self.image_seconds,
            "node_group_seconds": self.node_group_seconds,
            "nodes_added": self.nodes_added,
            "links_added": self.links_added,
            "node_groups_added": self.node_groups_added,
            "succeeded": self.succeeded,
        }


@dataclass(slots=True)
class MaterialProfilingCollector:
    phases: dict[str, MaterialPhaseAggregate] = field(default_factory=dict)
    handlers: dict[str, MaterialBuildAggregate] = field(default_factory=dict)
    templates: dict[str, MaterialBuildAggregate] = field(default_factory=dict)
    node_groups: dict[str, MaterialPhaseAggregate] = field(default_factory=dict)
    slowest_builds: list[MaterialBuildRecord] = field(default_factory=list)

    def record(
        self,
        phase: str,
        seconds: float,
        label: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        phase = str(phase or "unknown")
        if phase not in self.phases:
            self.phases[phase] = MaterialPhaseAggregate()
        self.phases[phase].record(seconds)
        build = _ACTIVE_BUILD.get()
        if build is not None:
            build.record_nested(phase, seconds)
        if phase == "material.node_group_cold_build":
            name = str(label or "<unnamed>")
            if name not in self.node_groups:
                self.node_groups[name] = MaterialPhaseAggregate()
            self.node_groups[name].record(seconds)

    def record_build(self, build: MaterialBuildRecord) -> None:
        handler = build.handler or "<unknown>"
        template = build.template or "<unknown>"
        if handler not in self.handlers:
            self.handlers[handler] = MaterialBuildAggregate()
        self.handlers[handler].record_build(build)
        if template not in self.templates:
            self.templates[template] = MaterialBuildAggregate()
        self.templates[template].record_build(build)
        self.slowest_builds.append(build)
        self.slowest_builds.sort(key=lambda item: item.seconds, reverse=True)
        del self.slowest_builds[_SLOW_BUILD_LIMIT:]

    def snapshot(self) -> dict[str, Any]:
        snapshot = {
            phase: aggregate.snapshot() for phase, aggregate in self.phases.items()
        }
        snapshot[_PROFILE_DETAILS_KEY] = {
            "handlers": {
                name: aggregate.snapshot() for name, aggregate in self.handlers.items()
            },
            "templates": {
                name: aggregate.snapshot() for name, aggregate in self.templates.items()
            },
            "node_groups": {
                name: aggregate.snapshot()
                for name, aggregate in self.node_groups.items()
            },
            "slowest_builds": [build.snapshot() for build in self.slowest_builds],
        }
        return snapshot


@dataclass(slots=True)
class MaterialProfilingSession:
    collector: MaterialProfilingCollector
    token: object
    closed: bool = False

    def finish(self) -> dict[str, Any]:
        if not self.closed:
            _ACTIVE_COLLECTOR.reset(self.token)
            self.closed = True
        return self.collector.snapshot()


@dataclass(slots=True)
class MaterialBuildSession:
    collector: MaterialProfilingCollector
    record: MaterialBuildRecord
    token: object
    closed: bool = False

    def finish(self, **values) -> None:
        if self.closed:
            return
        _ACTIVE_BUILD.reset(self.token)
        self.closed = True
        self.record.finalize(**values)
        self.collector.record_build(self.record)
>>>>>>> Stashed changes


def _emit_material_phase(
    phase: str,
    seconds: float,
    label: str = "",
    metadata: Mapping[str, Any] | None = None,
):
<<<<<<< Updated upstream
    return None


def set_material_profiling_enabled(enabled: bool) -> None:
    global _MATERIAL_PROFILING_ENABLED
    _MATERIAL_PROFILING_ENABLED = bool(enabled)


def material_profiling_enabled() -> bool:
    return _MATERIAL_PROFILING_ENABLED


def begin_material_phase():
    return perf_counter() if _MATERIAL_PROFILING_ENABLED else None
=======
    collector = _ACTIVE_COLLECTOR.get()
    if collector is not None:
        collector.record(phase, seconds, label, metadata)


def detailed_material_profiling_requested() -> bool:
    value = os.environ.get("CP77_MATERIAL_PROFILE", "")
    return str(value).strip().casefold() in {"1", "true", "yes", "on"}


def material_profiling_enabled() -> bool:
    return _MATERIAL_PROFILING_ENABLED or _ACTIVE_COLLECTOR.get() is not None


def start_material_profiling(
    enabled: bool = True,
) -> MaterialProfilingSession | None:
    if not enabled:
        return None
    collector = MaterialProfilingCollector()
    token = _ACTIVE_COLLECTOR.set(collector)
    return MaterialProfilingSession(collector, token)


def finish_material_profiling(
    session: MaterialProfilingSession | None,
) -> dict[str, Any]:
    return session.finish() if session is not None else {}


def start_material_build(
    material: str,
    template: str,
    handler: str,
    *,
    decal: bool = False,
) -> MaterialBuildSession | None:
    collector = _ACTIVE_COLLECTOR.get()
    if collector is None:
        return None
    record = MaterialBuildRecord(
        material=str(material or ""),
        template=str(template or ""),
        handler=str(handler or ""),
        decal=bool(decal),
    )
    token = _ACTIVE_BUILD.set(record)
    return MaterialBuildSession(collector, record, token)


def finish_material_build(
    session: MaterialBuildSession | None,
    **values,
) -> None:
    if session is not None:
        session.finish(**values)


def merge_material_profiles(target: dict, source: Mapping[str, Any]) -> None:
    for phase, values in source.items():
        if phase == _PROFILE_DETAILS_KEY:
            continue
        aggregate = target.setdefault(
            phase,
            {"seconds": 0.0, "count": 0, "maximum": 0.0},
        )
        aggregate["seconds"] += float(values.get("seconds", 0.0))
        aggregate["count"] += int(values.get("count", 0))
        aggregate["maximum"] = max(
            float(aggregate.get("maximum", 0.0)),
            float(values.get("maximum", 0.0)),
        )

    source_details = source.get(_PROFILE_DETAILS_KEY, {})
    target_details = target.setdefault(
        _PROFILE_DETAILS_KEY,
        {
            "handlers": {},
            "templates": {},
            "node_groups": {},
            "slowest_builds": [],
        },
    )
    for section in ("handlers", "templates"):
        for name, values in source_details.get(section, {}).items():
            aggregate = target_details[section].setdefault(
                name,
                {key: 0 for key in values},
            )
            for key, value in values.items():
                if key == "maximum":
                    aggregate[key] = max(float(aggregate[key]), float(value))
                elif key == "count" or key.endswith("_added"):
                    aggregate[key] += int(value)
                else:
                    aggregate[key] += float(value)
    for name, values in source_details.get("node_groups", {}).items():
        aggregate = target_details["node_groups"].setdefault(
            name,
            {"seconds": 0.0, "count": 0, "maximum": 0.0},
        )
        aggregate["seconds"] += float(values.get("seconds", 0.0))
        aggregate["count"] += int(values.get("count", 0))
        aggregate["maximum"] = max(
            float(aggregate["maximum"]),
            float(values.get("maximum", 0.0)),
        )
    slowest = target_details["slowest_builds"]
    slowest.extend(source_details.get("slowest_builds", ()))
    slowest.sort(
        key=lambda item: float(item.get("seconds", 0.0)),
        reverse=True,
    )
    del slowest[_SLOW_BUILD_LIMIT:]


def material_profile_details(profile: Mapping[str, Any]) -> Mapping[str, Any]:
    return profile.get(_PROFILE_DETAILS_KEY, {})


def material_profile_phase(profile: Mapping[str, Any], phase: str):
    aggregate = profile.get(phase, {})
    return (
        float(aggregate.get("seconds", 0.0)),
        int(aggregate.get("count", 0)),
        float(aggregate.get("maximum", 0.0)),
    )


def material_profile_total(details: Mapping[str, Any], field: str) -> float:
    return sum(
        float(values.get(field, 0.0)) for values in details.get("handlers", {}).values()
    )


def begin_material_phase():
    return perf_counter() if material_profiling_enabled() else None
>>>>>>> Stashed changes


def end_material_phase(
    started,
    phase: str,
    *,
    label: str = "",
    metadata: Mapping[str, Any] | None = None,
<<<<<<< Updated upstream
) -> None:
    if started is None:
        return
    _emit_material_phase(
        str(phase or "unknown"),
        max(0.0, perf_counter() - started),
        str(label or ""),
        metadata,
    )
=======
):
    if started is None:
        return 0.0
    seconds = max(0.0, perf_counter() - started)
    _emit_material_phase(
        str(phase or "unknown"),
        seconds,
        str(label or ""),
        metadata,
    )
    return seconds
>>>>>>> Stashed changes
