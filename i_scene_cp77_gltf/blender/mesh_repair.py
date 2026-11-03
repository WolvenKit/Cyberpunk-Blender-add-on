from __future__ import annotations

from dataclasses import dataclass, field, replace

import bmesh
import bpy
import numpy as np

<<<<<<< Updated upstream
=======
from ..core.log import debug_exception, get_logger, log_once
from ..gltf.mesh_contract import MAX_SKIN_INFLUENCES, SKIN_WEIGHT_EPSILON
>>>>>>> Stashed changes
from .context import preserved_context
from .mesh_validation import (
    MeshValidationError,
    MeshValidationOptions,
    armature_groups,
    armature_modifier,
    collect_mesh_validation_issues,
<<<<<<< Updated upstream
=======
    deform_group_indices,
>>>>>>> Stashed changes
    format_validation_issues,
    issue_fix_enabled,
    issues_by_object,
)

<<<<<<< Updated upstream
=======
_LOG = get_logger(__name__)

>>>>>>> Stashed changes

@dataclass(slots=True)
class PreparedMeshValidation:
    source_meshes: tuple
    export_objects: list
    temp_objects: list
    temp_armatures: list
    issues_found: tuple
    remaining_issues: tuple
    fixes_applied: dict[str, list[str]]
    mesh_replacements: dict = field(default_factory=dict)
    armature_replacements: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MeshRepairCommitResult:
    mesh_count: int
    issues_found: tuple
    remaining_issues: tuple
    fixes_applied: tuple

    @property
    def fix_count(self):
        return sum(len(fixes) for _name, fixes in self.fixes_applied)


<<<<<<< Updated upstream
@dataclass(frozen=True, slots=True)
class _VertexGroupState:
    groups: tuple
    weights: tuple


=======
>>>>>>> Stashed changes
def copy_mesh_object(mesh_object):
    temporary = None
    copied_data = None
    try:
        temporary = mesh_object.copy()
        copied_data = mesh_object.data.copy()
        temporary.data = copied_data
        temporary.name = f"{mesh_object.name}_CP77_VALIDATE"
        copied_data.name = temporary.name
        bpy.context.scene.collection.objects.link(temporary)
        return temporary
    except Exception:
        cleanup_validation_temporaries(
            (temporary,) if temporary is not None else (),
            (),
        )
        _remove_orphaned_data(
            (copied_data,) if copied_data is not None else (),
            getattr(bpy.data, "meshes", None),
            "mesh",
        )
        raise


def remove_unmatched_vertex_groups(mesh_object, names):
    removed = 0
    for name in names:
        group = mesh_object.vertex_groups.get(name)
        if group is not None:
            mesh_object.vertex_groups.remove(group)
            removed += 1
    return removed


def apply_autofitter_shape_keys(mesh_object, names):
    shape_keys = getattr(mesh_object.data, "shape_keys", None)
    if shape_keys is None:
        return 0
    applied = 0
    for name in names:
        key = shape_keys.key_blocks.get(name)
        if key is None:
            continue
<<<<<<< Updated upstream
        dependents = [other.name for other in shape_keys.key_blocks if other.relative_key == key]
=======
        dependents = [
            other.name for other in shape_keys.key_blocks if other.relative_key == key
        ]
>>>>>>> Stashed changes
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


<<<<<<< Updated upstream
def dissolve_faces(mesh, face_indices):
    if not face_indices:
        return 0
=======
# Edges shorter than this, and corners this close to the opposite edge, count as collapsed.
DEGENERATE_DISTANCE = 1e-5


def dissolve_faces(mesh, degenerate_faces, uv_degenerate_faces=()):
    """Remove degenerate faces and return how many each step removed"""
    if not degenerate_faces and not uv_degenerate_faces:
        return 0, 0
>>>>>>> Stashed changes
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()
<<<<<<< Updated upstream
        faces = [bm.faces[index] for index in face_indices if 0 <= index < len(bm.faces)]
        if not faces:
            return 0
        bmesh.ops.dissolve_faces(bm, faces=faces, use_verts=True)
        bm.to_mesh(mesh)
        mesh.update(calc_edges=True, calc_edges_loose=True)
        return len(faces)
=======
        count = len(bm.faces)
        degenerate = [
            bm.faces[index] for index in degenerate_faces if 0 <= index < count
        ]
        uv_degenerate = [
            bm.faces[index] for index in uv_degenerate_faces if 0 <= index < count
        ]
        if degenerate:
            edges = list({edge for face in degenerate for edge in face.edges})
            bmesh.ops.dissolve_degenerate(bm, dist=DEGENERATE_DISTANCE, edges=edges)
        after_geometry = len(bm.faces)
        uv_degenerate = [face for face in uv_degenerate if face.is_valid]
        if uv_degenerate:
            bmesh.ops.dissolve_faces(bm, faces=uv_degenerate, use_verts=True)
        removed = (count - after_geometry, after_geometry - len(bm.faces))
        if any(removed):
            bm.to_mesh(mesh)
            mesh.update(calc_edges=True, calc_edges_loose=True)
        return removed
>>>>>>> Stashed changes
    finally:
        bm.free()


def assign_unweighted_vertices(mesh_object, armature, indices):
    if not indices:
        return 0
    if not armature.data.bones:
        raise MeshValidationError(
            f"Cannot assign unweighted vertices on '{mesh_object.name}': armature has no bones."
        )
    root_name = armature.data.bones[0].name
<<<<<<< Updated upstream
    group = mesh_object.vertex_groups.get(root_name) or mesh_object.vertex_groups.new(name=root_name)
=======
    group = mesh_object.vertex_groups.get(root_name) or mesh_object.vertex_groups.new(
        name=root_name
    )
>>>>>>> Stashed changes
    group.add(list(indices), 0.01, "REPLACE")
    return len(indices)


<<<<<<< Updated upstream
def copy_armature_without_unused_bones(armature, unused_names):
    remove_names = set(unused_names)
    keep_names = {bone.name for bone in armature.data.bones if bone.name not in remove_names}
=======
def limit_vertex_influences(mesh_object, armature, indices, limit=MAX_SKIN_INFLUENCES):
    """Keep each listed vertex's limit strongest deform influences and normalize them"""
    groups = {group.index: group for group in mesh_object.vertex_groups}
    deform = deform_group_indices(mesh_object, armature)
    vertices = mesh_object.data.vertices
    removed = 0
    for index in indices:
        elements = sorted(
            (
                (element.weight, element.group)
                for element in vertices[index].groups
                if element.group in deform and element.weight > SKIN_WEIGHT_EPSILON
            ),
            reverse=True,
        )
        if len(elements) <= limit:
            continue
        kept = elements[:limit]
        for _weight, group_index in elements[limit:]:
            groups[group_index].remove([index])
            removed += 1
        total = sum(weight for weight, _group_index in kept)
        for weight, group_index in kept:
            groups[group_index].add([index], weight / total, "REPLACE")
    return removed


def copy_armature_without_unused_bones(armature, unused_names):
    remove_names = set(unused_names)
    keep_names = {
        bone.name for bone in armature.data.bones if bone.name not in remove_names
    }
>>>>>>> Stashed changes
    if not keep_names:
        raise MeshValidationError(
            f"Removing unused bones would leave armature '{armature.name}' empty."
        )

    temporary = None
    copied_data = None
    try:
        temporary = armature.copy()
        copied_data = armature.data.copy()
        temporary.data = copied_data
        temporary.name = f"{armature.name}_CP77_VALIDATE"
        copied_data.name = temporary.name
        bpy.context.scene.collection.objects.link(temporary)

        with preserved_context():
            if bpy.context.mode != "OBJECT":
<<<<<<< Updated upstream
                bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.select_all(action="DESELECT")
=======
                result = bpy.ops.object.mode_set(mode="OBJECT")
                if "FINISHED" not in result:
                    raise MeshValidationError(
                        "Blender cancelled the switch to Object Mode"
                    )
            result = bpy.ops.object.select_all(action="DESELECT")
            if "FINISHED" not in result:
                raise MeshValidationError("Blender cancelled object deselection")
>>>>>>> Stashed changes
            temporary.hide_set(False)
            temporary.hide_viewport = False
            temporary.hide_select = False
            temporary.select_set(True)
            bpy.context.view_layer.objects.active = temporary
<<<<<<< Updated upstream
            bpy.ops.object.mode_set(mode="EDIT")
=======
            result = bpy.ops.object.mode_set(mode="EDIT")
            if "FINISHED" not in result:
                raise MeshValidationError(
                    "Blender cancelled the switch to Armature Edit Mode"
                )
>>>>>>> Stashed changes
            edit_bones = temporary.data.edit_bones
            matrices = {bone.name: bone.matrix.copy() for bone in edit_bones}
            original_parent = {
                bone.name: bone.parent.name if bone.parent is not None else None
                for bone in armature.data.bones
            }

            for name in keep_names:
                edit_bone = edit_bones.get(name)
                if edit_bone is None:
                    continue
                parent_name = original_parent.get(name)
                while parent_name is not None and parent_name not in keep_names:
                    parent_name = original_parent.get(parent_name)
                edit_bone.parent = edit_bones.get(parent_name) if parent_name else None
                edit_bone.matrix = matrices[name]

            for name in remove_names:
                edit_bone = edit_bones.get(name)
                if edit_bone is not None:
                    edit_bones.remove(edit_bone)
<<<<<<< Updated upstream
            bpy.ops.object.mode_set(mode="OBJECT")
=======
            result = bpy.ops.object.mode_set(mode="OBJECT")
            if "FINISHED" not in result:
                raise MeshValidationError("Blender cancelled the return to Object Mode")
>>>>>>> Stashed changes
        return temporary
    except Exception:
        cleanup_validation_temporaries(
            (),
            (temporary,) if temporary is not None else (),
        )
        _remove_orphaned_data(
            (copied_data,) if copied_data is not None else (),
            getattr(bpy.data, "armatures", None),
            "armature",
        )
        raise


<<<<<<< Updated upstream
def apply_mesh_issue_fixes(mesh_object, issues, options):
=======
def apply_mesh_issue_fixes(mesh_object, issues):
>>>>>>> Stashed changes
    fixes = []
    modifier = armature_modifier(mesh_object)
    geometry_faces = set()
    uv_faces = set()
    for issue in issues:
        if issue.issue_type == "unmatched_vertex_groups":
            count = remove_unmatched_vertex_groups(mesh_object, issue.details)
            fixes.append(f"Removed {count} vertex groups without matching bones")
        elif issue.issue_type == "autofitter_shape_keys":
            count = apply_autofitter_shape_keys(mesh_object, issue.details)
<<<<<<< Updated upstream
            fixes.append(f"Baked and removed {count} Autofitter shape keys at their current values")
=======
            fixes.append(
                f"Baked and removed {count} Autofitter shape keys at their current values"
            )
>>>>>>> Stashed changes
        elif issue.issue_type == "missing_uv":
            mesh_object.data.uv_layers.new(name="UVMap", do_init=True)
            fixes.append("Added a default UV layer")
        elif issue.issue_type == "degenerate_faces":
            geometry_faces.update(issue.details)
        elif issue.issue_type == "degenerate_uvs":
            uv_faces.update(issue.details)
        elif issue.issue_type == "unweighted_vertices":
            if modifier is None:
                raise MeshValidationError(
                    f"Cannot assign weights on '{mesh_object.name}' without an armature modifier."
                )
<<<<<<< Updated upstream
            count = assign_unweighted_vertices(mesh_object, modifier.object, issue.details)
            fixes.append(
                f"Assigned {count} unweighted vertices to '{modifier.object.data.bones[0].name}'"
            )

    dissolve_indices = geometry_faces | uv_faces
    if dissolve_indices:
        count = dissolve_faces(mesh_object.data, sorted(dissolve_indices))
        labels = []
        if geometry_faces:
            labels.append("geometry-degenerate")
        if uv_faces:
            labels.append("UV-degenerate")
        fixes.append(f"Dissolved {count} {' and '.join(labels)} faces and associated vertices")
=======
            count = assign_unweighted_vertices(
                mesh_object, modifier.object, issue.details
            )
            fixes.append(
                f"Assigned {count} unweighted vertices to '{modifier.object.data.bones[0].name}'"
            )
        elif issue.issue_type == "influence_limit":
            count = limit_vertex_influences(mesh_object, modifier.object, issue.details)
            fixes.append(
                f"Removed {count} weakest bone influences from {len(issue.details)} vertices and normalized the rest"
            )

    removed_geometry, removed_uv = dissolve_faces(
        mesh_object.data,
        sorted(geometry_faces),
        sorted(uv_faces - geometry_faces),
    )
    if removed_geometry:
        fixes.append(f"Dissolved {removed_geometry} geometry-degenerate faces")
    if removed_uv:
        fixes.append(f"Dissolved {removed_uv} UV-degenerate faces")
>>>>>>> Stashed changes
    return fixes


def _source_issue_names(issues, mesh_replacements, armature_replacements):
<<<<<<< Updated upstream
    names = {temporary.name: original.name for original, temporary in mesh_replacements.items()}
    names.update(
        {temporary.name: original.name for original, temporary in armature_replacements.items()}
=======
    names = {
        temporary.name: original.name
        for original, temporary in mesh_replacements.items()
    }
    names.update(
        {
            temporary.name: original.name
            for original, temporary in armature_replacements.items()
        }
>>>>>>> Stashed changes
    )
    normalized = []
    for issue in issues:
        source_name = names.get(issue.object_name)
        if source_name is None:
            normalized.append(issue)
            continue
        message = issue.message.replace(issue.object_name, source_name)
        normalized.append(replace(issue, object_name=source_name, message=message))
    return tuple(normalized)


def _apply_followup_mesh_fixes(
    export_objects,
    mesh_replacements,
    *,
    is_skinned,
    options,
    fixes_applied,
):
<<<<<<< Updated upstream
    source_by_temporary = {temporary: original for original, temporary in mesh_replacements.items()}
=======
    source_by_temporary = {
        temporary: original for original, temporary in mesh_replacements.items()
    }
>>>>>>> Stashed changes
    remaining = ()
    for _pass in range(3):
        remaining = collect_mesh_validation_issues(
            export_objects,
            is_skinned=is_skinned,
            options=options,
        )
        fixable_by_name = issues_by_object(
            issue
            for issue in remaining
            if issue.issue_type != "unused_bones" and issue_fix_enabled(issue, options)
        )
        progressed = False
        for temporary, original in source_by_temporary.items():
            object_issues = fixable_by_name.get(temporary.name, ())
            if not object_issues:
                continue
<<<<<<< Updated upstream
            fixes = apply_mesh_issue_fixes(temporary, object_issues, options)
=======
            fixes = apply_mesh_issue_fixes(temporary, object_issues)
>>>>>>> Stashed changes
            if fixes:
                fixes_applied.setdefault(original.name, []).extend(fixes)
                progressed = True
        if not progressed:
            break
    return collect_mesh_validation_issues(
        export_objects,
        is_skinned=is_skinned,
        options=options,
    )


def prepare_mesh_validation_copies(
    meshes,
    *,
    is_skinned=False,
    options=None,
    require_valid=True,
):
    options = options or MeshValidationOptions()
    meshes = tuple(meshes)
    if not meshes:
        raise MeshValidationError("No mesh objects were provided for validation.")
    if any(getattr(obj, "type", None) != "MESH" for obj in meshes):
        raise MeshValidationError("Mesh validation accepts mesh objects only.")

<<<<<<< Updated upstream
    issues = collect_mesh_validation_issues(meshes, is_skinned=is_skinned, options=options)
    fixable = tuple(issue for issue in issues if issue_fix_enabled(issue, options))
    unfixable = tuple(issue for issue in issues if issue not in fixable)
    if require_valid and unfixable:
        raise MeshValidationError(format_validation_issues(unfixable, heading="Mesh export validation failed:"))

    fixable_by_object = issues_by_object(fixable)
    mesh_issues = {
        name: tuple(issue for issue in object_issues if issue.issue_type != "unused_bones")
        for name, object_issues in fixable_by_object.items()
    }
    armature_issues = tuple(issue for issue in fixable if issue.issue_type == "unused_bones")
=======
    issues = collect_mesh_validation_issues(
        meshes, is_skinned=is_skinned, options=options
    )
    fixable = tuple(issue for issue in issues if issue_fix_enabled(issue, options))
    unfixable = tuple(issue for issue in issues if issue not in fixable)
    if require_valid and unfixable:
        raise MeshValidationError(
            format_validation_issues(
                unfixable, heading="Mesh export validation failed:"
            )
        )

    fixable_by_object = issues_by_object(fixable)
    mesh_issues = {
        name: tuple(
            issue for issue in object_issues if issue.issue_type != "unused_bones"
        )
        for name, object_issues in fixable_by_object.items()
    }
    armature_issues = tuple(
        issue for issue in fixable if issue.issue_type == "unused_bones"
    )
>>>>>>> Stashed changes
    armatures = armature_groups(meshes)
    armatures_to_replace = {
        armature
        for armature in armatures
        if any(issue.object_name == armature.name for issue in armature_issues)
    }

    temp_objects = []
    temp_armatures = []
    export_objects = []
    mesh_replacements = {}
    fixes_applied = {}

    try:
        for original in meshes:
            modifier = armature_modifier(original)
            needs_copy = bool(mesh_issues.get(original.name)) or (
                modifier is not None and modifier.object in armatures_to_replace
            )
            temporary = copy_mesh_object(original) if needs_copy else original
            if needs_copy:
                temp_objects.append(temporary)
                mesh_replacements[original] = temporary
                fixes = apply_mesh_issue_fixes(
<<<<<<< Updated upstream
                    temporary,
                    mesh_issues.get(original.name, ()),
                    options,
=======
                    temporary, mesh_issues.get(original.name, ())
>>>>>>> Stashed changes
                )
                if fixes:
                    fixes_applied[original.name] = fixes
            export_objects.append(temporary)

        armature_replacements = {}
        for issue in armature_issues:
            original_armature = next(
<<<<<<< Updated upstream
                (armature for armature in armatures_to_replace if armature.name == issue.object_name),
=======
                (
                    armature
                    for armature in armatures_to_replace
                    if armature.name == issue.object_name
                ),
>>>>>>> Stashed changes
                None,
            )
            if original_armature is None or original_armature in armature_replacements:
                continue
<<<<<<< Updated upstream
            replacement = copy_armature_without_unused_bones(original_armature, issue.details)
=======
            replacement = copy_armature_without_unused_bones(
                original_armature, issue.details
            )
>>>>>>> Stashed changes
            temp_armatures.append(replacement)
            armature_replacements[original_armature] = replacement
            fixes_applied.setdefault(original_armature.name, []).append(
                f"Removed {len(issue.details)} bones without vertex groups and reparented retained descendants"
            )

        if armature_replacements:
            for temporary in mesh_replacements.values():
                for modifier in temporary.modifiers:
<<<<<<< Updated upstream
                    if modifier.type == "ARMATURE" and modifier.object in armature_replacements:
=======
                    if (
                        modifier.type == "ARMATURE"
                        and modifier.object in armature_replacements
                    ):
>>>>>>> Stashed changes
                        modifier.object = armature_replacements[modifier.object]

        remaining = _apply_followup_mesh_fixes(
            export_objects,
            mesh_replacements,
            is_skinned=is_skinned,
            options=options,
            fixes_applied=fixes_applied,
        )
        remaining = _source_issue_names(
            remaining,
            mesh_replacements,
            armature_replacements,
        )
        if require_valid and remaining:
            raise MeshValidationError(
                format_validation_issues(
                    remaining,
                    heading="Temporary fixes did not satisfy mesh export validation:",
                )
            )

        return PreparedMeshValidation(
            source_meshes=meshes,
            export_objects=export_objects,
            temp_objects=temp_objects,
            temp_armatures=temp_armatures,
            issues_found=issues,
            remaining_issues=remaining,
            fixes_applied=fixes_applied,
            mesh_replacements=mesh_replacements,
            armature_replacements=armature_replacements,
        )
    except Exception:
        cleanup_validation_temporaries(temp_objects, temp_armatures)
        raise


<<<<<<< Updated upstream
def _capture_vertex_group_state(mesh_object):
    groups = tuple(
        (group.name, bool(getattr(group, "lock_weight", False)))
        for group in mesh_object.vertex_groups
    )
    weights = tuple(
        tuple((int(element.group), float(element.weight)) for element in vertex.groups)
        for vertex in mesh_object.data.vertices
    )
    return _VertexGroupState(groups, weights)


def _restore_vertex_group_state(mesh_object, state):
    for group in tuple(mesh_object.vertex_groups):
        mesh_object.vertex_groups.remove(group)
    created = []
    for name, lock_weight in state.groups:
        group = mesh_object.vertex_groups.new(name=name)
        if hasattr(group, "lock_weight"):
            group.lock_weight = lock_weight
        created.append(group)
    for vertex_index, assignments in enumerate(state.weights):
        for group_index, weight in assignments:
            if 0 <= group_index < len(created):
                created[group_index].add((vertex_index,), weight, "REPLACE")


=======
>>>>>>> Stashed changes
def commit_prepared_mesh_repairs(prepared, *, is_skinned=False, options=None):
    options = options or MeshValidationOptions(try_fix=True)
    mesh_backups = {}
    armature_backups = {}
    old_mesh_data = []
    old_armature_data = []
    committed_mesh_data_names = []
    committed_armature_data_names = []
    committed_meshes = []
    committed_armatures = []
    success = False
    try:
        for original, replacement in prepared.armature_replacements.items():
            armature_backups[original] = original.data
            old_armature_data.append(original.data)
            committed_armature_data_names.append((replacement.data, original.data.name))
            committed_armatures.append(original)
            original.data = replacement.data

        for original, replacement in prepared.mesh_replacements.items():
<<<<<<< Updated upstream
            original_state = _capture_vertex_group_state(original)
            replacement_state = _capture_vertex_group_state(replacement)
            mesh_backups[original] = (original.data, original_state)
            old_mesh_data.append(original.data)
            committed_mesh_data_names.append((replacement.data, original.data.name))
            committed_meshes.append(original)
            original.data = replacement.data
            _restore_vertex_group_state(original, replacement_state)
=======
            mesh_backups[original] = original.data
            old_mesh_data.append(original.data)
            committed_mesh_data_names.append((replacement.data, original.data.name))
            committed_meshes.append(original)
            # Vertex groups and their weights belong to the mesh, so the repaired mesh brings its own.
            original.data = replacement.data
>>>>>>> Stashed changes

        remaining = collect_mesh_validation_issues(
            prepared.source_meshes,
            is_skinned=is_skinned,
            options=options,
        )
        success = True
        return MeshRepairCommitResult(
            mesh_count=len(prepared.source_meshes),
            issues_found=prepared.issues_found,
            remaining_issues=remaining,
            fixes_applied=tuple(
<<<<<<< Updated upstream
                (name, tuple(fixes))
                for name, fixes in prepared.fixes_applied.items()
=======
                (name, tuple(fixes)) for name, fixes in prepared.fixes_applied.items()
>>>>>>> Stashed changes
            ),
        )
    except Exception as error:
        rollback_failures = []
        for original in reversed(committed_meshes):
<<<<<<< Updated upstream
            old_data, old_state = mesh_backups[original]
            try:
                original.data = old_data
                _restore_vertex_group_state(original, old_state)
            except Exception as rollback_error:
=======
            try:
                original.data = mesh_backups[original]
            except Exception as rollback_error:
                debug_exception(
                    _LOG,
                    "Could not restore the mesh of %s after a failed repair",
                    original.name,
                )
>>>>>>> Stashed changes
                rollback_failures.append(f"{original.name}: {rollback_error}")
        for original in reversed(committed_armatures):
            try:
                original.data = armature_backups[original]
            except Exception as rollback_error:
<<<<<<< Updated upstream
=======
                debug_exception(
                    _LOG,
                    "Could not restore the armature of %s after a failed repair",
                    original.name,
                )
>>>>>>> Stashed changes
                rollback_failures.append(f"{original.name}: {rollback_error}")
        if rollback_failures:
            raise MeshValidationError(
                "GLB mesh repair failed and rollback was incomplete: "
                + "; ".join(rollback_failures)
            ) from error
        raise
    finally:
        cleanup_validation_temporaries(prepared.temp_objects, prepared.temp_armatures)
        if success:
            _remove_orphaned_data(
                old_mesh_data,
                getattr(bpy.data, "meshes", None),
                "mesh",
            )
            _remove_orphaned_data(
                old_armature_data,
                getattr(bpy.data, "armatures", None),
                "armature",
            )
            _restore_committed_data_names(
                committed_mesh_data_names,
                getattr(bpy.data, "meshes", None),
            )
            _restore_committed_data_names(
                committed_armature_data_names,
                getattr(bpy.data, "armatures", None),
            )


def _restore_committed_data_names(values, collection):
    for data, original_name in values:
        try:
            existing = collection.get(original_name) if collection is not None else None
<<<<<<< Updated upstream
            data.name = original_name if existing in (None, data) else f"{original_name}_repaired"
        except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError) as error:
            print(
                f"[CP77 Mesh Validation] Could not restore datablock name '{original_name}': {error}"
=======
            data.name = (
                original_name
                if existing in (None, data)
                else f"{original_name}_repaired"
            )
        except (
            AttributeError,
            ReferenceError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            _LOG.warning(
                "Could not restore datablock name %r: %s",
                original_name,
                error,
                exc_info=True,
>>>>>>> Stashed changes
            )


def _remove_orphaned_data(values, collection, label):
    if collection is None:
        return ()
    failures = []
    seen = set()
    for data in values:
        identity = id(data) if data else 0
        if not identity or identity in seen:
            continue
        seen.add(identity)
        try:
            if data.users == 0 and collection.get(data.name) is data:
                collection.remove(data)
<<<<<<< Updated upstream
        except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError) as error:
            failures.append(f"{label} '{getattr(data, 'name', '<deleted>')}': {error}")
    if failures:
        print("[CP77 Mesh Validation] Orphan cleanup incomplete: " + "; ".join(failures))
=======
        except (
            AttributeError,
            ReferenceError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_remove_orphaned_data", type(error).__name__),
                "remove orphaned data: fell back after %s",
                error,
                exc_info=True,
            )
            failures.append(f"{label} '{getattr(data, 'name', '<deleted>')}': {error}")
    if failures:
        _LOG.error("Orphan cleanup incomplete: %s", "; ".join(failures))
>>>>>>> Stashed changes
    return tuple(failures)


def cleanup_validation_temporaries(temp_objects, temp_armatures):
    failures = []
    objects = getattr(bpy.data, "objects", None)
    meshes = getattr(bpy.data, "meshes", None)
    armatures = getattr(bpy.data, "armatures", None)

    for obj in tuple(temp_objects):
        object_name = getattr(obj, "name", "<deleted>")
        try:
            if not obj or objects is None or objects.get(object_name) is not obj:
                continue
            data = obj.data
            objects.remove(obj, do_unlink=True)
            if (
                data
                and data.users == 0
                and meshes is not None
                and meshes.get(data.name) is data
            ):
                meshes.remove(data)
<<<<<<< Updated upstream
        except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError) as error:
=======
        except (
            AttributeError,
            ReferenceError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("cleanup_validation_temporaries 1", type(error).__name__),
                "cleanup validation temporaries: fell back after %s",
                error,
                exc_info=True,
            )
>>>>>>> Stashed changes
            failures.append(f"mesh temporary '{object_name}': {error}")

    for armature in tuple(temp_armatures):
        object_name = getattr(armature, "name", "<deleted>")
        try:
<<<<<<< Updated upstream
            if not armature or objects is None or objects.get(object_name) is not armature:
=======
            if (
                not armature
                or objects is None
                or objects.get(object_name) is not armature
            ):
>>>>>>> Stashed changes
                continue
            data = armature.data
            objects.remove(armature, do_unlink=True)
            if (
                data
                and data.users == 0
                and armatures is not None
                and armatures.get(data.name) is data
            ):
                armatures.remove(data)
<<<<<<< Updated upstream
        except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError) as error:
            failures.append(f"armature temporary '{object_name}': {error}")

    if failures:
        print("[CP77 Mesh Validation] Temporary cleanup incomplete: " + "; ".join(failures))
=======
        except (
            AttributeError,
            ReferenceError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("cleanup_validation_temporaries 2", type(error).__name__),
                "cleanup validation temporaries: fell back after %s",
                error,
                exc_info=True,
            )
            failures.append(f"armature temporary '{object_name}': {error}")

    if failures:
        _LOG.error("Temporary cleanup incomplete: %s", "; ".join(failures))
>>>>>>> Stashed changes
    return tuple(failures)
