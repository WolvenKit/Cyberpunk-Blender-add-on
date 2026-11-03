from __future__ import annotations

from dataclasses import dataclass

import bpy
from mathutils import Vector

from ....assetio.transform_values import vector3_from_data
from ....blender.naming import fit_id_name
from ....blender.transactions import track_created_datablock


@dataclass(slots=True, frozen=True)
class SplinePointRecord:
    position: tuple
    right_tangent: tuple
    left_tangent: tuple


@dataclass(slots=True, frozen=True)
class SplineAnalysis:
    points: tuple[SplinePointRecord, ...]
    looped: bool


def _point_position(point):
    if not isinstance(point, dict):
        return (0.0, 0.0, 0.0)
    position = point.get("Position")
    if not isinstance(position, dict):
        position = point.get("position")
    return vector3_from_data(position)


def _point_tangents(point):
    if not isinstance(point, dict):
        return (
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0),
        )
    tangents = point.get("tangents", {})
    elements = tangents.get("Elements", []) if isinstance(tangents, dict) else []
    right = (
        vector3_from_data(elements[0])
        if len(elements) > 0 and isinstance(elements[0], dict)
        else (0.0, 0.0, 0.0)
    )
    left = (
        vector3_from_data(elements[1])
        if len(elements) > 1 and isinstance(elements[1], dict)
        else (0.0, 0.0, 0.0)
    )
    return right, left


class SplineService:
    @staticmethod
    def analyze(data):
        spline_data = (
            data.get("splineData", {}).get("Data", {}) if isinstance(data, dict) else {}
        )
        source_points = (
            spline_data.get("points", []) if isinstance(spline_data, dict) else []
        )
        points = []
        for point in source_points:
            right_tangent, left_tangent = _point_tangents(point)
            points.append(
                SplinePointRecord(
                    position=_point_position(point),
                    right_tangent=right_tangent,
                    left_tangent=left_tangent,
                )
            )
        return SplineAnalysis(
            points=tuple(points),
            looped=bool(
                spline_data.get("looped", 0) if isinstance(spline_data, dict) else 0
            ),
        )

    def create(self, context, instance, instance_index):
        """Place the spline node's curve"""
        data = context.data
        analysis = self.analyze(data)
        if not analysis.points:
            context.operations.warning(
                f"{context.sector_name}: spline node "
                f"{context.node_index} contains no points"
            )
            return None

        name = fit_id_name(f"{context.node_type}_{context.node_index}_{instance_index}")
        curve = track_created_datablock("curves", bpy.data.curves.new(name, "CURVE"))
        curve.dimensions = "3D"
        curve.twist_mode = "Z_UP"
        curve.resolution_u = 24

        curve_object = track_created_datablock(
            "objects", bpy.data.objects.new(name, curve)
        )
        context.collection_for_instance(instance).objects.link(curve_object)
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
            bezier.handle_right = position + Vector(point.right_tangent)
            bezier.handle_left = position + Vector(point.left_tangent)

        context.operations.assign_custom_properties(
            curve_object,
            context.node,
            context.sector_name,
            cp77_node_data_index=instance.index,
            cp77_instance_idx=instance_index,
        )

        if context.node_type == "worldSpeedSplineNode":
            curve_object["speedChangeSections"] = context.session.safe_json(
                data.get("speedChangeSections", [])
            )
            curve_object["orientationChangeSections"] = context.session.safe_json(
                data.get("orientationChangeSections", [])
            )
            curve_object["roadAdjustmentFactorChangeSections"] = (
                context.session.safe_json(
                    data.get(
                        "roadAdjustmentFactorChangeSections",
                        [],
                    )
                )
            )
            curve_object["deprecatedSpeedRestrictions"] = context.session.safe_json(
                data.get("deprecatedSpeedRestrictions", [])
            )
            curve_object["useDeprecated"] = bool(data.get("useDeprecated", 0))
            curve_object["ignoreTerrain"] = bool(data.get("ignoreTerrain", 0))
        return curve_object
