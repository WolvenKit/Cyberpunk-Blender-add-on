from __future__ import annotations

from dataclasses import dataclass

from mathutils import Matrix

from ....assetio.values import axis_value


WORLD_TRANSFORM_CONTRACT = "WORLD_TRANSFORM_BUFFER_ABSOLUTE"
COOKED_TRANSFORM_CONTRACT = "COOKED_INSTANCE_TRANSFORMS_LOCAL_TO_NODE"
OCCLUDER_TRANSFORM_CONTRACT = "EMBEDDED_OCCLUDER_MATRIX_ABSOLUTE"


@dataclass(slots=True, frozen=True)
class TransformBufferSlice:
    buffer_key: str
    start: int
    declared_count: int
    total_count: int
    entries: tuple
    reference_id: str
    contract: str

    @property
    def actual_count(self):
        return len(self.entries)

    @property
    def end(self):
        return self.start + self.declared_count


class TransformBufferService:
    @staticmethod
    def _shared_transforms(data, lookup, buffer_key):
        owner = data.get(buffer_key) if isinstance(data, dict) else None
        if not isinstance(owner, dict):
            return ()
        shared = owner.get("sharedDataBuffer")
        if not isinstance(shared, dict):
            return ()
        if "Data" in shared:
            transforms = (
                shared.get("Data", {})
                .get("buffer", {})
                .get("Data", {})
                .get("Transforms", ())
            )
            return tuple(transforms) if isinstance(transforms, list) else ()
        handle_ref = shared.get("HandleRefId")
        if handle_ref is None:
            return ()
        return tuple(lookup.get(str(handle_ref), ()))

    @staticmethod
    def reference_id(data, buffer_key):
        owner = data.get(buffer_key, {}) if isinstance(data, dict) else {}
        shared = owner.get("sharedDataBuffer", {}) if isinstance(owner, dict) else {}
        if not isinstance(shared, dict):
            return ""
        value = shared.get("HandleRefId")
        return "" if value is None else str(value)

    def slice(
        self,
        data,
        lookup,
        buffer_key,
        *,
        sector_name,
        node_index,
        contract,
        warning,
    ):
        owner = data.get(buffer_key, {}) if isinstance(data, dict) else {}
        start = int(owner.get("startIndex", 0) or 0)
        count = int(owner.get("numElements", 0) or 0)
        transforms = self._shared_transforms(data, lookup, buffer_key)
        reference_id = self.reference_id(data, buffer_key)

        if start < 0 or count < 0:
            warning(
                f"{sector_name}: node {node_index} has invalid {buffer_key} "
                f"slice start={start}, count={count}"
            )
            entries = ()
        else:
            end = start + count
            if end > len(transforms):
                warning(
                    f"{sector_name}: node {node_index} requests "
                    f"{buffer_key}[{start}:{end}] from a buffer containing "
                    f"{len(transforms)} transforms"
                )
            entries = tuple(
                (index, transforms[index])
                for index in range(start, min(end, len(transforms)))
            )

        return TransformBufferSlice(
            buffer_key=buffer_key,
            start=start,
            declared_count=count,
            total_count=len(transforms),
            entries=entries,
            reference_id=reference_id,
            contract=contract,
        )

    def world_slice(self, context):
        return self.slice(
            context.data,
            context.world_transform_buffers,
            "worldTransformsBuffer",
            sector_name=context.sector_name,
            node_index=context.node_index,
            contract=WORLD_TRANSFORM_CONTRACT,
            warning=context.operations.warning,
        )

    def cooked_slice(self, context):
        return self.slice(
            context.data,
            context.cooked_transform_buffers,
            "cookedInstanceTransforms",
            sector_name=context.sector_name,
            node_index=context.node_index,
            contract=COOKED_TRANSFORM_CONTRACT,
            warning=context.operations.warning,
        )

    @staticmethod
    def occluder_records(data):
        records = data.get("buffer", ()) if isinstance(data, dict) else ()
        return tuple(records) if isinstance(records, list) else ()

    @staticmethod
    def occluder_matrix(record):
        if not isinstance(record, dict):
            raise TypeError("occluder buffer entry must be a dictionary")
        columns = []
        for key in ("Unknown1", "Unknown2", "Unknown3", "Unknown4"):
            column = record.get(key)
            if not isinstance(column, dict):
                raise ValueError(f"occluder buffer entry has no {key}")
            columns.append(column)

        x_axis, y_axis, z_axis, translation = columns
        return Matrix((
            (
                float(axis_value(x_axis, "X", 1.0)),
                float(axis_value(y_axis, "X")),
                float(axis_value(z_axis, "X")),
                float(axis_value(translation, "X")),
            ),
            (
                float(axis_value(x_axis, "Y")),
                float(axis_value(y_axis, "Y", 1.0)),
                float(axis_value(z_axis, "Y")),
                float(axis_value(translation, "Y")),
            ),
            (
                float(axis_value(x_axis, "Z")),
                float(axis_value(y_axis, "Z")),
                float(axis_value(z_axis, "Z", 1.0)),
                float(axis_value(translation, "Z")),
            ),
            (0.0, 0.0, 0.0, 1.0),
        ))

    @staticmethod
    def has_noncanonical_homogeneous_frame(record):
        if not isinstance(record, dict):
            return False
        columns = [
            record.get(key, {})
            for key in ("Unknown1", "Unknown2", "Unknown3", "Unknown4")
        ]
        return (
            any(
                abs(float(axis_value(column, "W"))) > 1e-8
                for column in columns[:3]
            )
            or abs(
                float(axis_value(columns[3], "W", 1.0)) - 1.0
            ) > 1e-8
        )
