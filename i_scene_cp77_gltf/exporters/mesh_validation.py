from __future__ import annotations

from dataclasses import dataclass

import bmesh
import bpy
import numpy as np

from ..main.common import exclusion_cache

VERT_LIMIT = 65535
WEIGHT_EPSILON = 1e-5
_QUANTIZE_SCALE = 1_000_000


@dataclass(frozen=True)
class MeshValidationOptions:
    """Optional mesh checks and temporary-copy repair controls."""

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

    geometry_epsilon: float = 1e-10
    uv_epsilon: float = 1e-17


@dataclass(frozen=True)
class ValidationIssue:
    issue_type: str
    message: str
    object_name: str
    required: bool = True
    details: tuple = ()


class MeshValidationError(ValueError):
    pass


def _armature_modifier(mesh_object):
    return next(
        (
            modifier
            for modifier in mesh_object.modifiers
            if modifier.type == "ARMATURE" and getattr(modifier, "object", None)
        ),
        None,
    )


def _autofitter_shape_keys(mesh_object):
    shape_keys = getattr(mesh_object.data, "shape_keys", None)
    if shape_keys is None:
        return []
    return [
        key
        for index, key in enumerate(shape_keys.key_blocks)
        if index > 0 and "autofitter" in key.name.casefold()
    ]


def _loop_vertex_indices(mesh):
    values = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get("vertex_index", values)
    return values


def _quantize(values):
    return np.round(values * _QUANTIZE_SCALE).astype(np.int64, copy=False)


def _count_unique_corner_signatures(vertex_indices, attribute_columns, vertex_count):
    if not attribute_columns:
        return np.ones(vertex_count, dtype=np.int32)
    signatures = np.column_stack([vertex_indices] + attribute_columns)
    unique = np.unique(signatures, axis=0)
    return np.bincount(unique[:, 0].astype(np.int32, copy=False), minlength=vertex_count)


def predicted_export_vertex_count(mesh):
    """Return the glTF vertex count after per-corner attributes split vertices."""
    mesh.calc_loop_triangles()
    vertex_count = len(mesh.vertices)
    if not mesh.loop_triangles or not mesh.loops:
        return vertex_count

    loop_vertices = _loop_vertex_indices(mesh).astype(np.int64, copy=False)
    columns = []

    for layer in getattr(mesh, "uv_layers", ()):  # every exported UV layer contributes splits
        values = np.empty(len(mesh.loops) * 2, dtype=np.float32)
        layer.data.foreach_get("uv", values)
        values = _quantize(values.reshape(-1, 2))
        columns.extend((values[:, 0], values[:, 1]))

    has_split_normals = getattr(mesh, "has_custom_normals", False) or any(
        not polygon.use_smooth for polygon in mesh.polygons
    )
    if has_split_normals:
        values = np.empty(len(mesh.loops) * 3, dtype=np.float32)
        mesh.loops.foreach_get("normal", values)
        values = _quantize(values.reshape(-1, 3))
        columns.extend((values[:, 0], values[:, 1], values[:, 2]))

    for attribute in getattr(mesh, "color_attributes", ()):
        if attribute.domain != "CORNER":
            continue
        values = np.empty(len(mesh.loops) * 4, dtype=np.float32)
        attribute.data.foreach_get("color", values)
        values = _quantize(values.reshape(-1, 4)[:, :3])
        columns.extend((values[:, 0], values[:, 1], values[:, 2]))

    counts = _count_unique_corner_signatures(loop_vertices, columns, vertex_count)
    return int(counts.sum())


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
    layer.data.foreach_get("uv", coordinates)
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


def _unweighted_vertex_indices(mesh):
    return tuple(
        vertex.index
        for vertex in mesh.vertices
        if not any(group.weight > WEIGHT_EPSILON for group in vertex.groups)
    )


def _mandatory_mesh_issues(mesh_object, is_skinned):
    issues = []
    export_count = predicted_export_vertex_count(mesh_object.data)
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

    autofitter_keys = _autofitter_shape_keys(mesh_object)
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

    modifier = _armature_modifier(mesh_object)
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
        sorted(group.name for group in mesh_object.vertex_groups if group.name not in bone_names)
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
        indices = tuple(int(value) for value in find_degenerate_faces(mesh, options.geometry_epsilon))
        if indices:
            issues.append(
                ValidationIssue(
                    "degenerate_faces",
                    f"'{mesh_object.name}' has {len(indices)} degenerate geometry faces.",
                    mesh_object.name,
                    details=indices,
                )
            )

    if options.check_degenerate_uvs and getattr(mesh.uv_layers, "active", None) is not None:
        indices = tuple(int(value) for value in find_degenerate_uv_faces(mesh, options.uv_epsilon))
        if indices:
            issues.append(
                ValidationIssue(
                    "degenerate_uvs",
                    f"'{mesh_object.name}' has {len(indices)} UV-degenerate faces.",
                    mesh_object.name,
                    details=indices,
                )
            )

    if is_skinned and options.check_unweighted_vertices and _armature_modifier(mesh_object):
        indices = _unweighted_vertex_indices(mesh)
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


def _armature_groups(meshes):
    grouped = {}
    for mesh_object in meshes:
        modifier = _armature_modifier(mesh_object)
        if modifier is not None:
            grouped.setdefault(modifier.object, []).append(mesh_object)
    return grouped


def _unused_bone_issues(meshes, options):
    if not options.advanced_validation or not options.check_unused_bones:
        return []
    issues = []
    for armature, bound_meshes in _armature_groups(meshes).items():
        group_names = {
            group.name
            for mesh_object in bound_meshes
            for group in mesh_object.vertex_groups
        }
        unused = tuple(sorted(bone.name for bone in armature.data.bones if bone.name not in group_names))
        if unused:
            issues.append(
                ValidationIssue(
                    "unused_bones",
                    f"Armature '{armature.name}' has {len(unused)} bones with no matching vertex "
                    f"group across the exported submeshes: {', '.join(unused)}.",
                    armature.name,
                    details=unused,
                )
            )
    return issues


def _fix_enabled(issue, options):
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
    }.get(issue.issue_type, False)


def _copy_mesh_object(mesh_object):
    temporary = mesh_object.copy()
    temporary.data = mesh_object.data.copy()
    temporary.name = f"{mesh_object.name}_CP77_EXPORT"
    temporary.data.name = temporary.name
    bpy.context.scene.collection.objects.link(temporary)
    return temporary


def _remove_unmatched_vertex_groups(mesh_object, names):
    removed = 0
    for name in names:
        group = mesh_object.vertex_groups.get(name)
        if group is not None:
            mesh_object.vertex_groups.remove(group)
            removed += 1
    return removed


def _apply_autofitter_shape_keys(mesh_object, names):
    shape_keys = getattr(mesh_object.data, "shape_keys", None)
    if shape_keys is None:
        return 0
    applied = 0
    for name in names:
        key = shape_keys.key_blocks.get(name)
        if key is None:
            continue
        dependents = [other.name for other in shape_keys.key_blocks if other.relative_key == key]
        if dependents:
            raise MeshValidationError(
                f"Cannot bake Autofitter key '{name}' on '{mesh_object.name}' because these "
                f"shape keys are relative to it: {', '.join(dependents)}."
            )
        relative = key.relative_key
        count = len(key.data)
        key_coordinates = np.empty(count * 3, dtype=np.float32)
        relative_coordinates = np.empty(count * 3, dtype=np.float32)
        key.data.foreach_get("co", key_coordinates)
        relative.data.foreach_get("co", relative_coordinates)
        delta = (key_coordinates - relative_coordinates) * float(key.value)
        for other in list(shape_keys.key_blocks):
            if other == key:
                continue
            coordinates = np.empty(count * 3, dtype=np.float32)
            other.data.foreach_get("co", coordinates)
            coordinates += delta
            other.data.foreach_set("co", coordinates)
        mesh_object.shape_key_remove(key)
        applied += 1
    mesh_object.data.update()
    return applied


def _dissolve_faces(mesh, face_indices):
    if not face_indices:
        return 0
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()
        faces = [bm.faces[index] for index in face_indices if 0 <= index < len(bm.faces)]
        if not faces:
            return 0
        bmesh.ops.dissolve_faces(bm, faces=faces, use_verts=True)
        bm.to_mesh(mesh)
        mesh.update(calc_edges=True, calc_edges_loose=True)
        return len(faces)
    finally:
        bm.free()


def _assign_unweighted_vertices(mesh_object, armature, indices):
    if not indices:
        return 0
    if not armature.data.bones:
        raise MeshValidationError(
            f"Cannot assign unweighted vertices on '{mesh_object.name}': armature has no bones."
        )
    root_name = armature.data.bones[0].name
    group = mesh_object.vertex_groups.get(root_name) or mesh_object.vertex_groups.new(name=root_name)
    group.add(list(indices), 0.01, "REPLACE")
    return len(indices)


def _temporary_armature_without_unused_bones(armature, unused_names):
    remove_names = set(unused_names)
    keep_names = {bone.name for bone in armature.data.bones if bone.name not in remove_names}
    if not keep_names:
        raise MeshValidationError(
            f"Removing unused bones would leave armature '{armature.name}' empty."
        )

    temporary = armature.copy()
    temporary.data = armature.data.copy()
    temporary.name = f"{armature.name}_CP77_EXPORT"
    temporary.data.name = temporary.name
    bpy.context.scene.collection.objects.link(temporary)

    previous_active = bpy.context.view_layer.objects.active
    previous_selected = tuple(bpy.context.selected_objects)
    previous_mode = bpy.context.mode
    success = False
    try:
        if previous_mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        temporary.select_set(True)
        bpy.context.view_layer.objects.active = temporary
        bpy.ops.object.mode_set(mode="EDIT")
        edit_bones = temporary.data.edit_bones
        matrices = {bone.name: bone.matrix.copy() for bone in edit_bones}
        original_parent = {
            bone.name: bone.parent.name if bone.parent is not None else None
            for bone in armature.data.bones
        }

        for name in keep_names:
            edit_bone = edit_bones.get(name)
            parent_name = original_parent.get(name)
            while parent_name is not None and parent_name not in keep_names:
                parent_name = original_parent.get(parent_name)
            edit_bone.parent = edit_bones.get(parent_name) if parent_name else None
            edit_bone.matrix = matrices[name]

        for name in tuple(remove_names):
            edit_bone = edit_bones.get(name)
            if edit_bone is not None:
                edit_bones.remove(edit_bone)
        bpy.ops.object.mode_set(mode="OBJECT")
        success = True
        return temporary
    finally:
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        for obj in previous_selected:
            if obj.name in bpy.data.objects:
                obj.select_set(True)
        if previous_active and previous_active.name in bpy.data.objects:
            bpy.context.view_layer.objects.active = previous_active
        if not success and temporary.name in bpy.data.objects:
            data = temporary.data
            bpy.data.objects.remove(temporary, do_unlink=True)
            if data and data.users == 0:
                bpy.data.armatures.remove(data)


def _apply_mesh_issue_fixes(original, temporary, issues, options):
    fixes = []
    modifier = _armature_modifier(temporary)
    geometry_faces = set()
    uv_faces = set()
    for issue in issues:
        if issue.issue_type == "unmatched_vertex_groups":
            count = _remove_unmatched_vertex_groups(temporary, issue.details)
            fixes.append(f"Removed {count} vertex groups without matching bones")
        elif issue.issue_type == "autofitter_shape_keys":
            count = _apply_autofitter_shape_keys(temporary, issue.details)
            fixes.append(f"Baked and removed {count} Autofitter shape keys at their current values")
        elif issue.issue_type == "missing_uv":
            temporary.data.uv_layers.new(name="UVMap", do_init=True)
            fixes.append("Added a default UV layer")
        elif issue.issue_type == "degenerate_faces":
            geometry_faces.update(issue.details)
        elif issue.issue_type == "degenerate_uvs":
            uv_faces.update(issue.details)
        elif issue.issue_type == "unweighted_vertices":
            if modifier is None:
                raise MeshValidationError(
                    f"Cannot assign weights on '{temporary.name}' without an armature modifier."
                )
            count = _assign_unweighted_vertices(temporary, modifier.object, issue.details)
            fixes.append(f"Assigned {count} unweighted vertices to '{modifier.object.data.bones[0].name}'")

    dissolve_faces = geometry_faces | uv_faces
    if dissolve_faces:
        count = _dissolve_faces(temporary.data, sorted(dissolve_faces))
        labels = []
        if geometry_faces:
            labels.append("geometry-degenerate")
        if uv_faces:
            labels.append("UV-degenerate")
        fixes.append(
            f"Dissolved {count} {' and '.join(labels)} faces and associated vertices"
        )
    return fixes


def _issues_by_object(issues):
    result = {}
    for issue in issues:
        result.setdefault(issue.object_name, []).append(issue)
    return result


def _format_failure(issues):
    lines = ["Mesh export validation failed:"]
    for object_name, object_issues in _issues_by_object(issues).items():
        lines.append(f"  {object_name}:")
        lines.extend(f"    - {issue.message}" for issue in object_issues)
    return "\n".join(lines)


def _collect_issues(meshes, is_skinned, options):
    issues = []
    for mesh_object in meshes:
        issues.extend(_mandatory_mesh_issues(mesh_object, is_skinned))
        issues.extend(_optional_mesh_issues(mesh_object, is_skinned, options))
    if is_skinned:
        issues.extend(_unused_bone_issues(meshes, options))
    return issues


def prepare_meshes_for_export(meshes, *, is_skinned=False, options=None):
    """Validate and optionally repair temporary export copies without editing source objects."""
    options = options or MeshValidationOptions()
    excluded = exclusion_cache.get_excluded_objects()
    meshes = [mesh for mesh in meshes if mesh not in excluded]
    if not meshes:
        raise MeshValidationError("No exportable meshes were provided.")

    issues = _collect_issues(meshes, is_skinned, options)
    unfixable = [issue for issue in issues if not _fix_enabled(issue, options)]
    if unfixable:
        raise MeshValidationError(_format_failure(unfixable))

    mesh_issues = {
        name: [issue for issue in object_issues if issue.issue_type != "unused_bones"]
        for name, object_issues in _issues_by_object(issues).items()
    }
    armature_issues = [issue for issue in issues if issue.issue_type == "unused_bones"]
    armatures_to_replace = {
        armature
        for armature in _armature_groups(meshes)
        if any(issue.object_name == armature.name for issue in armature_issues)
    }

    temp_objects = []
    temp_armatures = []
    export_objects = []
    original_to_temp = {}
    fixes_applied = {}

    try:
        for original in meshes:
            needs_copy = bool(mesh_issues.get(original.name))
            modifier = _armature_modifier(original)
            if modifier is not None and modifier.object in armatures_to_replace:
                needs_copy = True
            temporary = _copy_mesh_object(original) if needs_copy else original
            if needs_copy:
                temp_objects.append(temporary)
                original_to_temp[original] = temporary
                fixes = _apply_mesh_issue_fixes(
                    original,
                    temporary,
                    mesh_issues.get(original.name, ()),
                    options,
                )
                if fixes:
                    fixes_applied[original.name] = fixes
            export_objects.append(temporary)

        armature_replacements = {}
        for issue in armature_issues:
            original_armature = next(
                (armature for armature in armatures_to_replace if armature.name == issue.object_name),
                None,
            )
            if original_armature is None:
                continue
            replacement = _temporary_armature_without_unused_bones(
                original_armature,
                issue.details,
            )
            temp_armatures.append(replacement)
            armature_replacements[original_armature] = replacement
            fixes_applied.setdefault(original_armature.name, []).append(
                f"Removed {len(issue.details)} bones without vertex groups and reparented retained descendants"
            )

        if armature_replacements:
            for original, temporary in original_to_temp.items():
                for modifier in temporary.modifiers:
                    if modifier.type == "ARMATURE" and modifier.object in armature_replacements:
                        modifier.object = armature_replacements[modifier.object]

        remaining = _collect_issues(export_objects, is_skinned, options)
        if remaining:
            raise MeshValidationError(
                "Temporary fixes did not satisfy validation:\n" + _format_failure(remaining)
            )

        return {
            "valid": True,
            "export_objects": export_objects,
            "temp_objects": temp_objects,
            "temp_armatures": temp_armatures,
            "issues_found": _issues_by_object(issues),
            "fixes_applied": fixes_applied,
        }
    except Exception:
        cleanup_validation_temporaries(temp_objects, temp_armatures)
        raise


def cleanup_validation_temporaries(temp_objects, temp_armatures):
    for obj in tuple(temp_objects):
        if obj and obj.name in bpy.data.objects:
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if data and data.users == 0 and data.name in bpy.data.meshes:
                bpy.data.meshes.remove(data)
    for armature in tuple(temp_armatures):
        if armature and armature.name in bpy.data.objects:
            data = armature.data
            bpy.data.objects.remove(armature, do_unlink=True)
            if data and data.users == 0 and data.name in bpy.data.armatures:
                bpy.data.armatures.remove(data)


def format_fix_summary(result):
    if not result.get("fixes_applied"):
        return ""
    lines = ["Export used temporary mesh fixes; source objects were not changed:"]
    for object_name, fixes in result["fixes_applied"].items():
        lines.append(f"  {object_name}:")
        lines.extend(f"    - {fix}" for fix in fixes)
    return "\n".join(lines)
