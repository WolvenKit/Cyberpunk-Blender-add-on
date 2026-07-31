from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math

from mathutils import Matrix, Quaternion, Vector

from ....assetio.catalog import ResourceKind
from ..context import FoliageResourceError
from ...common.paths import absolute_path_key
from ....assetio.values import axis_value, first_dict_value as _first_dict_value




def _position(data):
    value = _first_dict_value(
        data,
        "Position",
        "position",
        "Translation",
        "translation",
    )
    return (
        float(axis_value(value, "X")),
        float(axis_value(value, "Y")),
        float(axis_value(value, "Z")),
    )


def _rotation(data):
    value = _first_dict_value(
        data,
        "Orientation",
        "orientation",
        "Rotation",
        "rotation",
    )
    return (
        float(axis_value(value, "r", 1.0)),
        float(axis_value(value, "i")),
        float(axis_value(value, "j")),
        float(axis_value(value, "k")),
    )


def _scale(data):
    value = _first_dict_value(data, "Scale", "scale")
    if value:
        return (
            float(axis_value(value, "X", 1.0)),
            float(axis_value(value, "Y", 1.0)),
            float(axis_value(value, "Z", 1.0)),
        )
    scalar = data.get("Scale", data.get("scale", 1.0))
    try:
        scalar = float(scalar)
    except (TypeError, ValueError):
        scalar = 1.0
    return (scalar, scalar, scalar)


def _integer_field(data, *keys, default=0):
    if not isinstance(data, dict):
        return int(default)
    for key in keys:
        if key not in data:
            continue
        value = data[key]
        if isinstance(value, dict):
            value = value.get(
                "$value",
                value.get("Value", value.get("value", default)),
            )
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return int(default)


@dataclass(slots=True, frozen=True)
class FoliageResourceData:
    resolved_path: str
    buckets: tuple
    populations: tuple
    declared_bucket_count: int
    declared_population_count: int
    bucket_population_count: int
    version: int


@dataclass(slots=True, frozen=True)
class FoliagePopulationSelection:
    resource: FoliageResourceData
    depot_path: str
    active: tuple
    inactive: tuple
    bucket_begin: int
    bucket_count: int
    instances_begin: int
    instances_count: int
    inactive_digest: str

    @property
    def resolved_count(self):
        return len(self.active) + len(self.inactive)

    @property
    def active_count(self):
        return len(self.active)


class FoliageResourceService:
    def __init__(self, session):
        self.session = session
        self.cache = session.caches.foliage_resources

    def resolve_path(self, depot_path):
        return self.session.resource_resolver.resolve_json(
            "foliage",
            depot_path,
            ".cfoliage.json",
        ).resolved_path

    @staticmethod
    def _as_list(value):
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for key in ("Data", "Elements", "items"):
                candidate = value.get(key)
                if isinstance(candidate, list):
                    return candidate
        return []

    def _parse(self, payload, resolved_path):
        root = (
            payload.get("Data", {}).get("RootChunk", {})
            if isinstance(payload, dict)
            else {}
        )
        buffer_data = root.get("dataBuffer", {}).get("Data", {})
        if isinstance(buffer_data.get("Data"), dict):
            buffer_data = buffer_data["Data"]

        buckets = tuple(self._as_list(buffer_data.get("Buckets")))
        populations = tuple(self._as_list(buffer_data.get("Populations")))
        declared_bucket_count = _integer_field(
            root,
            "bucketCount",
            "BucketCount",
            default=len(buckets),
        )
        declared_population_count = _integer_field(
            root,
            "populationCount",
            "PopulationCount",
            default=len(populations),
        )
        bucket_population_count = sum(
            max(
                0,
                _integer_field(
                    bucket,
                    "PopulationCount",
                    "populationCount",
                ),
            )
            for bucket in buckets
        )
        return FoliageResourceData(
            resolved_path=resolved_path,
            buckets=buckets,
            populations=populations,
            declared_bucket_count=declared_bucket_count,
            declared_population_count=declared_population_count,
            bucket_population_count=bucket_population_count,
            version=_integer_field(root, "version", "Version"),
        )

    @staticmethod
    def _validate(resource, *, sector_name, depot_path, warning):
        if resource.declared_bucket_count != len(resource.buckets):
            warning(
                f"{sector_name}: foliage resource {depot_path} declares "
                f"{resource.declared_bucket_count} buckets but contains "
                f"{len(resource.buckets)}"
            )
        if resource.declared_population_count != len(resource.populations):
            warning(
                f"{sector_name}: foliage resource {depot_path} declares "
                f"{resource.declared_population_count} populations but "
                f"contains {len(resource.populations)}"
            )
        if resource.bucket_population_count != len(resource.populations):
            warning(
                f"{sector_name}: foliage resource {depot_path} bucket counts "
                f"total {resource.bucket_population_count}, expected "
                f"{len(resource.populations)}"
            )

    def require(self, depot_path, *, sector_name, node_index, warning):
        resolved_path = self.resolve_path(depot_path)
        if not resolved_path:
            raise FoliageResourceError(
                f"{sector_name}: foliage node {node_index}: required "
                f"resource not indexed: {depot_path}"
            )

        key = absolute_path_key(resolved_path)
        resource = self.cache.get(key)
        if resource is None:
            payload = self.session.documents.payload(
                resolved_path,
                expected_kind=ResourceKind.FOLIAGE,
            )
            if not isinstance(payload, dict):
                raise FoliageResourceError(
                    f"{sector_name}: foliage node {node_index}: failed to "
                    f"parse {resolved_path}"
                )
            resource = self._parse(payload, resolved_path)
            self._validate(
                resource,
                sector_name=sector_name,
                depot_path=depot_path,
                warning=warning,
            )
            self.cache[key] = resource
        return resource

    @staticmethod
    def population_is_active(population):
        if not isinstance(population, dict):
            return False
        scale = population.get("Scale", population.get("scale", 1.0))
        if isinstance(scale, dict):
            values = _scale(population)
            return all(
                math.isfinite(value) and value > 0.0
                for value in values
            )
        try:
            value = float(scale)
        except (TypeError, ValueError):
            return False
        return math.isfinite(value) and value > 0.0

    @staticmethod
    def population_matrix(population):
        rotation = Quaternion(_rotation(population))
        if sum(float(value) * float(value) for value in rotation) <= 1e-12:
            rotation = Quaternion((1.0, 0.0, 0.0, 0.0))
        else:
            rotation.normalize()
        return Matrix.LocRotScale(
            Vector(_position(population)),
            rotation,
            Vector(_scale(population)),
        )

    @staticmethod
    def population_scale(population):
        scale = population.get("Scale", population.get("scale", 1.0))
        if isinstance(scale, dict):
            values = _scale(population)
            return float(sum(values) / 3.0)
        try:
            return float(scale)
        except (TypeError, ValueError):
            return 1.0

    @staticmethod
    def _indices(span, resource, *, sector_name, node_index, warning):
        buckets = resource.buckets
        populations = resource.populations
        bucket_begin = _integer_field(
            span,
            "bucketBegin",
            "BucketBegin",
            "cketBegin",
        )
        bucket_count = _integer_field(
            span,
            "bucketCount",
            "BucketCount",
            "cketCount",
        )
        instances_begin = _integer_field(
            span,
            "instancesBegin",
            "InstancesBegin",
            "stancesBegin",
        )
        instances_count = _integer_field(
            span,
            "instancesCount",
            "InstancesCount",
            "stancesCount",
        )
        node_end = instances_begin + max(0, instances_count)

        if (
            bucket_begin < 0
            or bucket_count < 0
            or instances_begin < 0
            or instances_count < 0
        ):
            warning(
                f"{sector_name}: foliage node {node_index} has a negative "
                f"population span: {span}"
            )
            return (), (
                bucket_begin,
                bucket_count,
                instances_begin,
                instances_count,
            )

        bucket_end = bucket_begin + bucket_count
        if bucket_end > len(buckets):
            warning(
                f"{sector_name}: foliage node {node_index} requests "
                f"buckets[{bucket_begin}:{bucket_end}] from "
                f"{len(buckets)} buckets"
            )

        selected = []
        seen_populations = set()
        seen_relative = set()
        for bucket_index in range(
            bucket_begin,
            min(bucket_end, len(buckets)),
        ):
            bucket = buckets[bucket_index]
            relative_start = _integer_field(
                bucket,
                "PopulationSubIndex",
                "populationSubIndex",
            )
            population_count = _integer_field(
                bucket,
                "PopulationCount",
                "populationCount",
            )
            if relative_start < 0 or population_count < 0:
                warning(
                    f"{sector_name}: foliage node {node_index} bucket "
                    f"{bucket_index} has a negative population span"
                )
                continue

            relative_end = relative_start + population_count
            population_start = instances_begin + relative_start
            population_end = population_start + population_count
            clipped_start = max(instances_begin, population_start, 0)
            clipped_end = min(
                node_end,
                population_end,
                len(populations),
            )
            if (
                relative_end > instances_count
                or population_end > len(populations)
            ):
                warning(
                    f"{sector_name}: foliage node {node_index} bucket "
                    f"{bucket_index} population range "
                    f"[{population_start}:{population_end}] was clipped to "
                    f"[{clipped_start}:{clipped_end}]"
                )

            relative_lower = clipped_start - instances_begin
            relative_upper = max(
                relative_lower,
                clipped_end - instances_begin,
            )
            for relative_index in range(
                relative_lower,
                relative_upper,
            ):
                if relative_index in seen_relative:
                    warning(
                        f"{sector_name}: foliage node {node_index} relative "
                        f"population {relative_index} occurs in overlapping "
                        f"buckets"
                    )
                    continue
                seen_relative.add(relative_index)
                population_index = instances_begin + relative_index
                if population_index in seen_populations:
                    warning(
                        f"{sector_name}: foliage node {node_index} "
                        f"population {population_index} occurs in "
                        f"overlapping buckets"
                    )
                    continue
                seen_populations.add(population_index)
                selected.append(
                    (bucket_index, population_index, relative_index)
                )

        expected_relative = set(range(instances_count))
        missing_relative = expected_relative - seen_relative
        extra_relative = seen_relative - expected_relative
        if missing_relative or extra_relative:
            warning(
                f"{sector_name}: foliage node {node_index} bucket-relative "
                f"population partition is incomplete: "
                f"missing={len(missing_relative)}, "
                f"extra={len(extra_relative)}"
            )
        if len(selected) != instances_count:
            warning(
                f"{sector_name}: foliage node {node_index} span declares "
                f"{instances_count} populations but {len(selected)} unique "
                f"populations were resolved from its buckets"
            )

        selected.sort(key=lambda item: item[2])
        return tuple(selected), (
            bucket_begin,
            bucket_count,
            instances_begin,
            instances_count,
        )

    def select(
        self,
        depot_path,
        span,
        *,
        sector_name,
        node_index,
        warning,
    ):
        resource = self.require(
            depot_path,
            sector_name=sector_name,
            node_index=node_index,
            warning=warning,
        )
        indices, span_values = self._indices(
            span,
            resource,
            sector_name=sector_name,
            node_index=node_index,
            warning=warning,
        )

        active = []
        inactive = []
        for item in indices:
            population = resource.populations[item[1]]
            target = (
                active
                if self.population_is_active(population)
                else inactive
            )
            target.append(item)

        digest = (
            hashlib.sha1(
                ",".join(str(item[1]) for item in inactive).encode("utf-8")
            ).hexdigest()
            if inactive
            else ""
        )
        return FoliagePopulationSelection(
            resource=resource,
            depot_path=depot_path,
            active=tuple(active),
            inactive=tuple(inactive),
            bucket_begin=span_values[0],
            bucket_count=span_values[1],
            instances_begin=span_values[2],
            instances_count=span_values[3],
            inactive_digest=digest,
        )
