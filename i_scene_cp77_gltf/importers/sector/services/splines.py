from __future__ import annotations
from ....blender.transactions import track_created_datablock

from dataclasses import dataclass

import bpy
from mathutils import Vector

from ....assetio.values import axis_value


SPLINE_PLACEMENT_CONTRACTS = {
    "worldSplineNode": "CP77_BEZIER_SPLINE_NODE_WORLD",
    "worldSpeedSplineNode": "CP77_SPEED_BEZIER_SPLINE_NODE_WORLD",
}


@dataclass(slots=True, frozen=True)
class SplinePointRecord:
    position: tuple
    right_tangent: tuple
    left_tangent: tuple
    rotation: dict
    automatic_tangents: bool
    continuous_tangents: bool
    point_id: int


@dataclass(slots=True, frozen=True)
class SplineAnalysis:
    node_type: str
    points: tuple[SplinePointRecord, ...]
    looped: bool
    has_direction: bool
    reversed: bool


@dataclass(slots=True, frozen=True)
class SplinePlacement:
    object: object
    curve: object
    spline: object
    analysis: SplineAnalysis


def _vector3(data):
    return (
        float(axis_value(data, "X")),
        float(axis_value(data, "Y")),
        float(axis_value(data, "Z")),
    )


def _point_position(point):
    if not isinstance(point, dict):
        return (0.0, 0.0, 0.0)
    position = point.get("Position")
    if not isinstance(position, dict):
        position = point.get("position")
    return _vector3(position)


def _point_tangents(point):
    if not isinstance(point, dict):
        return (
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
        )
    tangents = point.get("tangents", {})
    elements = (
        tangents.get("Elements", [])
        if isinstance(tangents, dict)
        else []
    )
    right = (
        _vector3(elements[0])
        if len(elements) > 0 and isinstance(elements[0], dict)
        else (0.0, 0.0, 0.0)
    )
    left = (
        _vector3(elements[1])
        if len(elements) > 1 and isinstance(elements[1], dict)
        else (0.0, 0.0, 0.0)
    )
    return right, left


class SplineService:
    @staticmethod
    def contract(node_type):
        try:
            return SPLINE_PLACEMENT_CONTRACTS[node_type]
        except KeyError as error:
            raise ValueError(
                f"Unsupported spline node type: {node_type}"
            ) from error

    @staticmethod
    def analyze(node_type, data):
        spline_data = (
            data.get("splineData", {}).get("Data", {})
            if isinstance(data, dict)
            else {}
        )
        source_points = (
            spline_data.get("points", [])
            if isinstance(spline_data, dict)
            else []
        )
        points = []
        for point in source_points:
            right_tangent, left_tangent = _point_tangents(point)
            points.append(SplinePointRecord(
                position=_point_position(point),
                right_tangent=right_tangent,
                left_tangent=left_tangent,
                rotation=(
                    point.get("rotation", {})
                    if isinstance(point, dict)
                    else {}
                ),
                automatic_tangents=bool(
                    point.get("automaticTangents", 0)
                    if isinstance(point, dict)
                    else 0
                ),
                continuous_tangents=bool(
                    point.get("continuousTangents", 0)
                    if isinstance(point, dict)
                    else 0
                ),
                point_id=int(
                    point.get("id", 0) or 0
                    if isinstance(point, dict)
                    else 0
                ),
            ))
        return SplineAnalysis(
            node_type=node_type,
            points=tuple(points),
            looped=bool(
                spline_data.get("looped", 0)
                if isinstance(spline_data, dict)
                else 0
            ),
            has_direction=bool(
                spline_data.get("hasDirection", 0)
                if isinstance(spline_data, dict)
                else 0
            ),
            reversed=bool(
                spline_data.get("reversed", 0)
                if isinstance(spline_data, dict)
                else 0
            ),
        )

    @staticmethod
    def point_metadata(analysis):
        return [
            {
                "rotation": point.rotation,
                "automaticTangents": point.automatic_tangents,
                "continuousTangents": point.continuous_tangents,
                "id": point.point_id,
            }
            for point in analysis.points
        ]

    def create(self, context, instance, instance_index):
        data = context.data
        analysis = self.analyze(
            context.node_type,
            data,
        )
        if not analysis.points:
            context.operations.warning(
                f"{context.sector_name}: spline node "
                f"{context.node_index} contains no points"
            )
            return None

        name = context.operations.trim_name(
            f"{context.node_type}_{context.node_index}_"
            f"{instance_index}"
        )
        curve = track_created_datablock("curves", bpy.data.curves.new(name, "CURVE"))
        curve.dimensions = "3D"
        curve.twist_mode = "Z_UP"
        curve.resolution_u = 24

        curve_object = track_created_datablock("objects", bpy.data.objects.new(name, curve))
        context.sector_collection.objects.link(curve_object)
        curve_object.matrix_world = context.operations.instance_matrix(
            instance,
            context.execution.scale_factor,
        )

        spline = curve.splines.new("BEZIER")
        spline.use_cyclic_u = analysis.looped
        spline.bezier_points.add(len(analysis.points) - 1)

        for point_index, point in enumerate(analysis.points):
            position = Vector(point.position)
            bezier = spline.bezier_points[point_index]
            bezier.co = position
            bezier.handle_left_type = "FREE"
            bezier.handle_right_type = "FREE"
            bezier.handle_right = (
                position + Vector(point.right_tangent)
            )
            bezier.handle_left = (
                position + Vector(point.left_tangent)
            )

        context.operations.assign_custom_properties(
            curve_object,
            data,
            context.sector_name,
            context.node_index,
            nodeDataIndex=instance["nodeDataIndex"],
            instance_idx=instance_index,
            splinePointCount=len(analysis.points),
            splineLooped=analysis.looped,
            splineHasDirection=analysis.has_direction,
            entrySnappedNode=context.operations.cname_value(
                data.get("entrySnapedNode")
            ),
            entrySnappedSocket=context.operations.cname_value(
                data.get("entrySnapedSocketName")
            ),
            destSnappedNode=context.operations.cname_value(
                data.get("destSnapedNode")
            ),
            destSnappedSocket=context.operations.cname_value(
                data.get("destSnapedSocketName")
            ),
        )
        curve_object["splinePointMetadata"] = (
            context.operations.safe_json(
                self.point_metadata(analysis)
            )
        )

        if context.node_type == "worldSpeedSplineNode":
            curve_object["speedChangeSections"] = (
                context.operations.safe_json(
                    data.get("speedChangeSections", [])
                )
            )
            curve_object["orientationChangeSections"] = (
                context.operations.safe_json(
                    data.get("orientationChangeSections", [])
                )
            )
            curve_object[
                "roadAdjustmentFactorChangeSections"
            ] = context.operations.safe_json(
                data.get(
                    "roadAdjustmentFactorChangeSections",
                    [],
                )
            )
            curve_object["deprecatedSpeedRestrictions"] = (
                context.operations.safe_json(
                    data.get("deprecatedSpeedRestrictions", [])
                )
            )
            curve_object["useDeprecated"] = bool(
                data.get("useDeprecated", 0)
            )
            curve_object["ignoreTerrain"] = bool(
                data.get("ignoreTerrain", 0)
            )

        return SplinePlacement(
            object=curve_object,
            curve=curve,
            spline=spline,
            analysis=analysis,
        )
