from __future__ import annotations

from dataclasses import dataclass

import bpy
import numpy as np

from ..bartmoss.arrays import float32_bit_keys, stable_unique_integer_rows
from ..gltf.mesh_contract import MAX_SKIN_INFLUENCES, SKIN_WEIGHT_EPSILON

VERT_LIMIT = 65535
# The checks the Mesh Tools panel and the export dialogs start with, so Try Fix repairs what Fix does.
DEFAULT_CHECKS = {
    "check_unweighted_vertices": True,
    "check_unused_bones": True,
    "check_unused_vertex_groups": True,
    "check_missing_uv": True,
    "check_degenerate_faces": True,
    "check_degenerate_uvs": False,
}


@dataclass(frozen=True, slots=True)
class MeshValidationOptions:
    """The checks to run beyond the ones export needs, and whether to fix every problem found"""

    check_unweighted_vertices: bool = False
    check_unused_bones: bool = False
    check_unused_vertex_groups: bool = False
    check_missing_uv: bool = False
    check_degenerate_faces: bool = False
    check_degenerate_uvs: bool = False

    try_fix: bool = False

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


def loop_vertex_indices(mesh):
    values = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", values)
    return values


def predicted_export_vertex_count(mesh):
    """Estimate splits from stored corners"""
    mesh.calc_loop_triangles()
    if not mesh.loop_triangles or not mesh.loops:
        return 0

    loop_vertices = loop_vertex_indices(mesh).astype(np.int64, copy=False)
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


def bone_group_indices(mesh_object, armature):
    """The indices of the object's vertex groups named for a bone of armature, the ones the skin exports"""
    bones = armature.data.bones
    return {
        group.index
        for group in mesh_object.vertex_groups
        if bones.get(group.name) is not None
    }


def weighted_group_names(mesh_object):
    """The names of the object's vertex groups that carry weight on some vertex"""
    weighted = set()
    for vertex in mesh_object.data.vertices:
        for element in vertex.groups:
            if element.weight > SKIN_WEIGHT_EPSILON:
                weighted.add(element.group)
    return {
        group.name for group in mesh_object.vertex_groups if group.index in weighted
    }


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


def unweighted_vertex_indices(mesh_object):
    """The vertices of the object that carry no weight in any vertex group"""
    # Reading vertex weights on a mesh without groups corrupts memory in Blender 5.0.0, so a groupless mesh is not read.
    if not mesh_object.vertex_groups:
        return tuple(range(len(mesh_object.data.vertices)))
    return tuple(
        vertex.index
        for vertex in mesh_object.data.vertices
        if not any(group.weight > SKIN_WEIGHT_EPSILON for group in vertex.groups)
    )


def _mandatory_mesh_issues(mesh_object, is_skinned, options):
    if not len(mesh_object.data.polygons):
        return [
            ValidationIssue(
                "empty_mesh",
                f"'{mesh_object.name}' has no faces; give it faces or leave it out of the export.",
                mesh_object.name,
            )
        ]
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
        mesh_object.data, bone_group_indices(mesh_object, modifier.object)
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

    # A submesh with no weights at all exports without a skin, which only the Ungrouped Vertices check reports; one
    # with some needs them on every vertex.
    unweighted = unweighted_vertex_indices(mesh_object)
    whole = len(unweighted) == len(mesh_object.data.vertices)
    if unweighted and (options.check_unweighted_vertices or not whole):
        issues.append(
            ValidationIssue(
                "unweighted_vertices",
                f"'{mesh_object.name}' has no vertex weights; it would not follow the armature."
                if whole
                else f"'{mesh_object.name}' has {len(unweighted)} vertices without weights; every vertex of a "
                "weighted submesh needs some.",
                mesh_object.name,
                details=unweighted,
            )
        )
    return issues


def _named(names, limit=8):
    shown = ", ".join(names[:limit])
    return f"{shown}, and {len(names) - limit} more" if len(names) > limit else shown


def _optional_mesh_issues(mesh_object, is_skinned, options):
    if not len(mesh_object.data.polygons):
        return []

    issues = []
    mesh = mesh_object.data
    if options.check_unused_vertex_groups and mesh_object.vertex_groups:
        weighted = weighted_group_names(mesh_object)
        modifier = armature_modifier(mesh_object) if is_skinned else None
        bones = modifier.object.data.bones if modifier is not None else None
        # A group without a bone is the required check's to report; this one reports empty groups.
        unused = tuple(
            group.name
            for group in mesh_object.vertex_groups
            if group.name not in weighted
            and (bones is None or bones.get(group.name) is not None)
        )
        if unused:
            issues.append(
                ValidationIssue(
                    "unused_vertex_groups",
                    f"'{mesh_object.name}' has {len(unused)} vertex groups without weights: {_named(unused)}.",
                    mesh_object.name,
                    details=unused,
                )
            )
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
    return issues


def armature_groups(meshes):
    grouped = {}
    for mesh_object in meshes:
        modifier = armature_modifier(mesh_object)
        if modifier is not None:
            grouped.setdefault(modifier.object, []).append(mesh_object)
    return grouped


def rig_weighted_group_names(armature, stand_ins=None):
    """The names of the vertex groups carrying weight on any mesh the armature deforms or parents, each temporary in stand_ins counting in place of its original"""
    stand_ins = stand_ins or {}
    originals = {temporary: original for original, temporary in stand_ins.items()}
    rig = originals.get(armature, armature)
    rigs = {rig, stand_ins.get(rig, rig)}
    return {
        name
        for mesh_object in bpy.data.objects
        if mesh_object.type == "MESH"
        and mesh_object not in stand_ins
        and (
            getattr(armature_modifier(mesh_object), "object", None) in rigs
            or mesh_object.parent in rigs
        )
        for name in weighted_group_names(mesh_object)
    }


def _unused_bone_issues(meshes, options, stand_ins):
    if not options.check_unused_bones:
        return []
    issues = []
    for armature in armature_groups(meshes):
        # Every mesh on the rig counts, not only the validated ones, so a fix keeps the bones the others use.
        weighted = rig_weighted_group_names(armature, stand_ins)
        unused = tuple(
            sorted(
                bone.name for bone in armature.data.bones if bone.name not in weighted
            )
        )
        if unused:
            issues.append(
                ValidationIssue(
                    "unused_bones",
                    f"Armature '{armature.name}' has {len(unused)} bones no mesh carries weight on: "
                    f"{_named(unused)}.",
                    armature.name,
                    details=unused,
                )
            )
    return issues


def collect_mesh_validation_issues(
    meshes, *, is_skinned=False, options=None, stand_ins=None
):
    """Every issue the options check for on meshes, any temporary in stand_ins counting in place of its original"""
    options = options or MeshValidationOptions()
    meshes = tuple(meshes)
    issues = []
    for mesh_object in meshes:
        issues.extend(_mandatory_mesh_issues(mesh_object, is_skinned, options))
        issues.extend(_optional_mesh_issues(mesh_object, is_skinned, options))
    if is_skinned:
        issues.extend(_unused_bone_issues(meshes, options, stand_ins))
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


FIXABLE_ISSUES = frozenset(
    {
        "unmatched_vertex_groups",
        "autofitter_shape_keys",
        "missing_uv",
        "degenerate_faces",
        "degenerate_uvs",
        "unweighted_vertices",
        "unused_bones",
        "unused_vertex_groups",
        "influence_limit",
    }
)


def issue_fix_enabled(issue, options):
    """Whether a fix run repairs the issue, which is every issue a repair exists for"""
    return options.try_fix and issue.issue_type in FIXABLE_ISSUES
