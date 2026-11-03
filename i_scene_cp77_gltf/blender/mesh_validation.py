from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..bartmoss.arrays import float32_bit_keys, stable_unique_integer_rows
from ..gltf.mesh_contract import MAX_SKIN_INFLUENCES, SKIN_WEIGHT_EPSILON

VERT_LIMIT = 65535
WEIGHT_EPSILON = 1e-5


@dataclass(frozen=True, slots=True)
class MeshValidationOptions:
    advanced_validation: bool = False
    check_missing_uv: bool = True
    check_degenerate_faces: bool = True
    check_degenerate_uvs: bool = False
    check_unweighted_vertices: bool = True
    check_unused_bones: bool = False

    try_fix: bool = False
    fix_remove_unmatched_vertex_groups: bool = True
    fix_apply_autofitter_shape_keys: bool = False
    fix_add_missing_uv: bool = True
    fix_dissolve_degenerate_faces: bool = True
    fix_dissolve_degenerate_uvs: bool = False
    fix_assign_unweighted_vertices: bool = False
    fix_remove_unused_bones: bool = False
    fix_limit_influences: bool = False

    geometry_epsilon: float = 1e-10
    uv_epsilon: float = 1e-17
    check_vertex_limit: bool = True


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    issue_type: str
    message: str
    object_name: str
    required: bool = True
    details: tuple = ()


class MeshValidationError(ValueError):
    pass


def armature_modifier(mesh_object):
    return next(
        (
            modifier
            for modifier in mesh_object.modifiers
            if modifier.type == "ARMATURE" and getattr(modifier, "object", None)
        ),
        None,
    )


def autofitter_shape_keys(mesh_object):
    shape_keys = getattr(mesh_object.data, "shape_keys", None)
    if shape_keys is None:
        return ()
    return tuple(
        key
        for index, key in enumerate(shape_keys.key_blocks)
        if index > 0 and "autofitter" in key.name.casefold()
    )


def _loop_vertex_indices(mesh):
    values = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", values)
    return values


def predicted_export_vertex_count(mesh):
    """Estimate splits from stored corners"""
    mesh.calc_loop_triangles()
    if not mesh.loop_triangles or not mesh.loops:
        return 0

    loop_vertices = _loop_vertex_indices(mesh).astype(np.int64, copy=False)
    columns = []

    for layer in getattr(mesh, "uv_layers", ()):
        values = np.empty(len(mesh.loops) * 2, dtype=np.float32)
        layer.uv.foreach_get("vector", values)
        values = float32_bit_keys(values.reshape(-1, 2))
        columns.extend((values[:, 0], values[:, 1]))

    has_split_normals = getattr(mesh, "normals_domain", "CORNER") != "POINT"
    if has_split_normals and len(mesh.corner_normals) == len(mesh.loops):
        values = np.empty(len(mesh.loops) * 3, dtype=np.float32)
        mesh.corner_normals.foreach_get("vector", values)
        values = float32_bit_keys(values.reshape(-1, 3))
        columns.extend((values[:, 0], values[:, 1], values[:, 2]))

    for attribute in getattr(mesh, "color_attributes", ()):
        if attribute.domain != "CORNER":
            continue
        values = np.empty(len(mesh.loops) * 4, dtype=np.float32)
        attribute.data.foreach_get(
            "color_srgb" if attribute.data_type == "BYTE_COLOR" else "color", values
        )
        values = float32_bit_keys(values.reshape(-1, 4))
        columns.extend((values[:, 0], values[:, 1], values[:, 2], values[:, 3]))

    triangle_loops = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
    mesh.loop_triangles.foreach_get("loops", triangle_loops)
    representatives, _ = stable_unique_integer_rows(
        [loop_vertices[triangle_loops]] + [column[triangle_loops] for column in columns]
    )
    return len(representatives)


def find_degenerate_faces(mesh, epsilon=1e-10):
    mesh.calc_loop_triangles()
    if not mesh.loop_triangles:
        return np.empty(0, dtype=np.int32)

    coordinates = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
    mesh.vertices.foreach_get("co", coordinates)
    coordinates = coordinates.reshape(-1, 3)

    triangle_vertices = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
    mesh.loop_triangles.foreach_get("vertices", triangle_vertices)
    triangle_vertices = triangle_vertices.reshape(-1, 3)

    polygon_indices = np.empty(len(mesh.loop_triangles), dtype=np.int32)
    mesh.loop_triangles.foreach_get("polygon_index", polygon_indices)

    edge_a = coordinates[triangle_vertices[:, 1]] - coordinates[triangle_vertices[:, 0]]
    edge_b = coordinates[triangle_vertices[:, 2]] - coordinates[triangle_vertices[:, 0]]
    areas = 0.5 * np.linalg.norm(np.cross(edge_a, edge_b), axis=1)
    bad = areas <= float(epsilon)
    if not np.any(bad):
        return np.empty(0, dtype=np.int32)

    counts = np.bincount(
        polygon_indices,
        weights=bad.astype(np.int32),
        minlength=len(mesh.polygons),
    )
    return np.flatnonzero(counts > 0)


def find_degenerate_uv_faces(mesh, epsilon=1e-17):
    mesh.calc_loop_triangles()
    layer = getattr(mesh.uv_layers, "active", None)
    if layer is None or not mesh.loop_triangles:
        return np.empty(0, dtype=np.int32)

    coordinates = np.empty(len(mesh.loops) * 2, dtype=np.float64)
    layer.uv.foreach_get("vector", coordinates)
    coordinates = coordinates.reshape(-1, 2)

    triangle_loops = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
    mesh.loop_triangles.foreach_get("loops", triangle_loops)
    triangle_loops = triangle_loops.reshape(-1, 3)

    polygon_indices = np.empty(len(mesh.loop_triangles), dtype=np.int32)
    mesh.loop_triangles.foreach_get("polygon_index", polygon_indices)

    triangle_uvs = coordinates[triangle_loops]
    edge_a = triangle_uvs[:, 1] - triangle_uvs[:, 0]
    edge_b = triangle_uvs[:, 2] - triangle_uvs[:, 0]
    areas = 0.5 * np.abs(edge_a[:, 0] * edge_b[:, 1] - edge_a[:, 1] * edge_b[:, 0])
    bad = areas <= float(epsilon)
    if not np.any(bad):
        return np.empty(0, dtype=np.int32)

    counts = np.bincount(
        polygon_indices,
        weights=bad.astype(np.int32),
        minlength=len(mesh.polygons),
    )
    return np.flatnonzero(counts > 0)


def deform_group_indices(mesh_object, armature):
    """The indices of the object's vertex groups that bind to deform bones, the only ones the skin exports"""
    deform = {bone.name for bone in armature.data.bones if bone.use_deform}
    return {group.index for group in mesh_object.vertex_groups if group.name in deform}


def crowded_vertex_indices(mesh, groups, limit=MAX_SKIN_INFLUENCES):
    """The vertices weighted to more than limit of the vertex groups groups, and the most any vertex has"""
    crowded = []
    most = 0
    for vertex in mesh.vertices:
        count = sum(
            1
            for element in vertex.groups
            if element.group in groups and element.weight > SKIN_WEIGHT_EPSILON
        )
        if count > limit:
            crowded.append(vertex.index)
            most = max(most, count)
    return tuple(crowded), most


def unweighted_vertex_indices(mesh):
    return tuple(
        vertex.index
        for vertex in mesh.vertices
        if not any(group.weight > WEIGHT_EPSILON for group in vertex.groups)
    )


def _mandatory_mesh_issues(mesh_object, is_skinned, options):
    issues = []
    export_count = (
        predicted_export_vertex_count(mesh_object.data)
        if options.check_vertex_limit
        else 0
    )
    if export_count > VERT_LIMIT:
        issues.append(
            ValidationIssue(
                "vertex_limit",
                f"'{mesh_object.name}' exports as approximately {export_count} vertices; "
                f"each submesh must remain at or below {VERT_LIMIT}.",
                mesh_object.name,
                details=(export_count,),
            )
        )

    autofitter_keys = autofitter_shape_keys(mesh_object)
    if autofitter_keys:
        names = tuple(key.name for key in autofitter_keys)
        issues.append(
            ValidationIssue(
                "autofitter_shape_keys",
                f"'{mesh_object.name}' still has Autofitter shape keys: {', '.join(names)}.",
                mesh_object.name,
                details=names,
            )
        )

    if not is_skinned:
        return issues

    modifier = armature_modifier(mesh_object)
    if modifier is None and not mesh_object.vertex_groups:
        # A submesh with no weights at all is a static part of the skinned mesh and exports without a skin.
        return issues
    if modifier is None:
        issues.append(
            ValidationIssue(
                "missing_armature",
                f"'{mesh_object.name}' is marked skinned but has no armature modifier with a target.",
                mesh_object.name,
            )
        )
        return issues

    bone_names = {bone.name for bone in modifier.object.data.bones}
    unmatched_groups = tuple(
        sorted(
            group.name
            for group in mesh_object.vertex_groups
            if group.name not in bone_names
        )
    )
    if unmatched_groups:
        issues.append(
            ValidationIssue(
                "unmatched_vertex_groups",
                f"'{mesh_object.name}' has vertex groups without matching bones: "
                f"{', '.join(unmatched_groups)}.",
                mesh_object.name,
                details=unmatched_groups,
            )
        )

    crowded, most = crowded_vertex_indices(
        mesh_object.data, deform_group_indices(mesh_object, modifier.object)
    )
    if crowded:
        issues.append(
            ValidationIssue(
                "influence_limit",
                f"'{mesh_object.name}' has {len(crowded)} vertices with more than {MAX_SKIN_INFLUENCES} bone "
                f"influences (the most is {most}); the export supports {MAX_SKIN_INFLUENCES}.",
                mesh_object.name,
                details=crowded,
            )
        )
    return issues


def _optional_mesh_issues(mesh_object, is_skinned, options):
    if not options.advanced_validation:
        return []

    issues = []
    mesh = mesh_object.data
    if options.check_missing_uv and (
        len(mesh.uv_layers) == 0 or getattr(mesh.uv_layers, "active", None) is None
    ):
        issues.append(
            ValidationIssue(
                "missing_uv",
                f"'{mesh_object.name}' has no active UV layer.",
                mesh_object.name,
            )
        )

    if options.check_degenerate_faces:
        indices = tuple(
            int(value)
            for value in find_degenerate_faces(mesh, options.geometry_epsilon)
        )
        if indices:
            issues.append(
                ValidationIssue(
                    "degenerate_faces",
                    f"'{mesh_object.name}' has {len(indices)} degenerate geometry faces.",
                    mesh_object.name,
                    details=indices,
                )
            )

    if (
        options.check_degenerate_uvs
        and getattr(mesh.uv_layers, "active", None) is not None
    ):
        indices = tuple(
            int(value) for value in find_degenerate_uv_faces(mesh, options.uv_epsilon)
        )
        if indices:
            issues.append(
                ValidationIssue(
                    "degenerate_uvs",
                    f"'{mesh_object.name}' has {len(indices)} UV-degenerate faces.",
                    mesh_object.name,
                    details=indices,
                )
            )

    if (
        is_skinned
        and options.check_unweighted_vertices
        and armature_modifier(mesh_object)
    ):
        indices = unweighted_vertex_indices(mesh)
        if indices:
            issues.append(
                ValidationIssue(
                    "unweighted_vertices",
                    f"'{mesh_object.name}' has {len(indices)} vertices without non-zero weights.",
                    mesh_object.name,
                    details=indices,
                )
            )
    return issues


def armature_groups(meshes):
    grouped = {}
    for mesh_object in meshes:
        modifier = armature_modifier(mesh_object)
        if modifier is not None:
            grouped.setdefault(modifier.object, []).append(mesh_object)
    return grouped


def _unused_bone_issues(meshes, options):
    if not options.advanced_validation or not options.check_unused_bones:
        return []
    issues = []
    for armature, bound_meshes in armature_groups(meshes).items():
        group_names = {
            group.name
            for mesh_object in bound_meshes
            for group in mesh_object.vertex_groups
        }
        unused = tuple(
            sorted(
                bone.name
                for bone in armature.data.bones
                if bone.name not in group_names
            )
        )
        if unused:
            issues.append(
                ValidationIssue(
                    "unused_bones",
                    f"Armature '{armature.name}' has {len(unused)} bones with no matching vertex "
                    f"group across the validated submeshes: {', '.join(unused)}.",
                    armature.name,
                    details=unused,
                )
            )
    return issues


def collect_mesh_validation_issues(meshes, *, is_skinned=False, options=None):
    options = options or MeshValidationOptions()
    meshes = tuple(meshes)
    issues = []
    for mesh_object in meshes:
        issues.extend(_mandatory_mesh_issues(mesh_object, is_skinned, options))
        issues.extend(_optional_mesh_issues(mesh_object, is_skinned, options))
    if is_skinned:
        issues.extend(_unused_bone_issues(meshes, options))
    return tuple(issues)


def issues_by_object(issues):
    result = {}
    for issue in issues:
        result.setdefault(issue.object_name, []).append(issue)
    return result


def format_validation_issues(issues, *, heading="Mesh validation failed:"):
    lines = [heading]
    for object_name, object_issues in issues_by_object(issues).items():
        lines.append(f"  {object_name}:")
        lines.extend(f"    - {issue.message}" for issue in object_issues)
    return "\n".join(lines)


def issue_fix_enabled(issue, options):
    if not options.try_fix:
        return False
    return {
        "unmatched_vertex_groups": options.fix_remove_unmatched_vertex_groups,
        "autofitter_shape_keys": options.fix_apply_autofitter_shape_keys,
        "missing_uv": options.fix_add_missing_uv,
        "degenerate_faces": options.fix_dissolve_degenerate_faces,
        "degenerate_uvs": options.fix_dissolve_degenerate_uvs,
        "unweighted_vertices": options.fix_assign_unweighted_vertices,
        "unused_bones": options.fix_remove_unused_bones,
        "influence_limit": options.fix_limit_influences,
    }.get(issue.issue_type, False)
