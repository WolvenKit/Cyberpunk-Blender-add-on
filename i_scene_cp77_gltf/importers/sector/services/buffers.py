from __future__ import annotations

from mathutils import Matrix, Quaternion, Vector

from ....assetio.streaming_sector import destructible_transforms, transform_range
from ....assetio.transform_values import (
    quaternion_wxyz_from_wkit,
    vector3_from_data,
    world_position_from_data,
)
from ....assetio.values import nested_dict


def column_matrix(x_axis, y_axis, z_axis, translation):
    """The affine matrix whose columns are the three axes and the translation"""
    columns = (
        vector3_from_data(x_axis, (1.0, 0.0, 0.0)),
        vector3_from_data(y_axis, (0.0, 1.0, 0.0)),
        vector3_from_data(z_axis, (0.0, 0.0, 1.0)),
        vector3_from_data(translation),
    )
    return Matrix(
        (
            *(tuple(column[row] for column in columns) for row in range(3)),
            (0.0, 0.0, 0.0, 1.0),
        )
    )


def _matrix(position, orientation, scale=(1.0, 1.0, 1.0), scale_factor=1.0):
    scale = Vector(scale)
    if scale_factor != 1:
        scale /= scale_factor
    return Matrix.LocRotScale(
        Vector(world_position_from_data(position)),
        Quaternion(quaternion_wxyz_from_wkit(orientation)),
        scale,
    )


class TransformBufferService:
    @staticmethod
    def instanced_mesh_matrices(node_data, inner_index, scale_factor=1.0):
        """The world matrices of the transforms one TransformRanges entry covers"""
        span = transform_range(node_data, inner_index)
        if span is None:
            return ()
        transforms = nested_dict(node_data, "cookedWorldTransformsBuffer", "Data")[
            "Transforms"
        ]
        matrices = []
        for index in span:
            record = transforms[index] if isinstance(transforms[index], dict) else {}
            transform = nested_dict(record, "transform")
            matrices.append(
                _matrix(
                    transform.get("Position"),
                    transform.get("Orientation"),
                    vector3_from_data(record.get("scale"), (1.0, 1.0, 1.0)),
                    scale_factor,
                )
            )
        return tuple(matrices)

    @staticmethod
    def destructible_matrices(node_data):
        """(item index, matrix) of each instanceTransforms item that is a transform"""
        return tuple(
            (index, _matrix(transform.get("position"), transform.get("orientation")))
            for index, transform in enumerate(destructible_transforms(node_data))
            if transform is not None
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

        return column_matrix(*columns)
