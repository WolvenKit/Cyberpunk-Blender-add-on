import bpy

from ...blender.collections import get_collection_children
from ...blender.context import (
    get_safe_mode,
    restore_previous_context,
    safe_mode_switch,
    store_current_context,
)
from ...blender.identity import real_users
from ...blender.operator_results import OperationResult, require_finished
from ...blender.shapekeys import has_shape_keys, shape_key_by_name
from ...blender.transactions import (
    track_mesh_object,
    track_new_modifier,
    transactional,
)
from ...core.log import get_logger
from ...gltf.garment_support import GARMENT_SUPPORT_MORPH
from ..model import ShrinkwrapRequest
from .mesh_cleanup_service import create_color_attributes
from .shapekey_service import key_coordinates, move_with_basis, rest_shape

_LOG = get_logger(__name__)


@transactional("Shrinkwrap")
def add_shrinkwrap(context, request: ShrinkwrapRequest):
    targets = get_collection_children(request.target_collection_name, "MESH")
    if targets is None:
        return OperationResult.cancelled(
            f"Target collection '{request.target_collection_name}' was not found."
        )
    if not targets:
        return OperationResult.cancelled(
            f"Target collection '{request.target_collection_name}' contains no meshes."
        )

    target_mesh = targets[0]
    selected = [
        obj
        for obj in context.selected_objects
        if obj.type == "MESH" and obj != target_mesh
    ]
    if not selected:
        return OperationResult.cancelled(
            "No source meshes are selected, or only the target mesh is selected."
        )

    key_name = GARMENT_SUPPORT_MORPH if request.as_garment_support else "Shrinkwrap"
    warnings = []
    if len(targets) > 1:
        warnings.append(
            f"Target collection contains {len(targets)} meshes; using {target_mesh.name}."
        )

    if request.apply_immediately:
        store_current_context()
    try:
        if request.apply_immediately and get_safe_mode() != "OBJECT":
            safe_mode_switch("OBJECT")
        changed = 0
        applied_meshes = set()
        for obj in selected:
            if request.vertex_group and request.vertex_group not in obj.vertex_groups:
                warnings.append(
                    f"{obj.name}: vertex group '{request.vertex_group}' was not found."
                )
                continue
            if request.apply_immediately and obj.data.as_pointer() in applied_meshes:
                # Its mesh, shared with an object selected before it, is already shrinkwrapped.
                changed += 1
                continue

            track_mesh_object(obj)
            modifier = obj.modifiers.new(name=key_name, type="SHRINKWRAP")
            track_new_modifier(obj, modifier)
            if request.vertex_group:
                modifier.vertex_group = request.vertex_group
            if request.as_garment_support:
                create_color_attributes(obj)

            modifier.target = target_mesh
            modifier.wrap_method = request.wrap_method
            modifier.wrap_mode = "ABOVE_SURFACE"
            modifier.offset = request.offset
            changed += 1
            if not request.apply_immediately:
                continue

            applied_meshes.add(obj.data.as_pointer())
            context.view_layer.objects.active = obj
            modifier_name = modifier.name
            keyless = not has_shape_keys(obj)
            # Blender applies modifiers to a shared mesh only as shape keys.
            if keyless and real_users(obj.data) == 1:
                if request.as_garment_support:
                    require_finished(
                        bpy.ops.object.modifier_apply_as_shapekey(
                            modifier=modifier_name
                        ),
                        f"Apply {modifier_name} as shape key on {obj.name}",
                    )
                else:
                    require_finished(
                        bpy.ops.object.modifier_apply(modifier=modifier_name),
                        f"Apply {modifier_name} on {obj.name}",
                    )
            elif request.as_garment_support:
                # Only the GarmentSupport key is replaced; morphs and other keys stay.
                existing = shape_key_by_name(obj, GARMENT_SUPPORT_MORPH)
                if existing:
                    obj.shape_key_remove(existing)
                with rest_shape(obj):
                    require_finished(
                        bpy.ops.object.modifier_apply_as_shapekey(
                            modifier=modifier_name
                        ),
                        f"Apply {modifier_name} as shape key on {obj.name}",
                    )
            else:
                # Apply into the basis and move every other key with it, so each keeps its offset.
                with rest_shape(obj):
                    require_finished(
                        bpy.ops.object.modifier_apply_as_shapekey(
                            modifier=modifier_name
                        ),
                        f"Apply {modifier_name} as shape key on {obj.name}",
                    )
                shape_keys = obj.data.shape_keys
                applied = shape_keys.key_blocks[-1]
                displacement = key_coordinates(applied) - key_coordinates(
                    shape_keys.reference_key
                )
                obj.shape_key_remove(applied)
                move_with_basis(obj, displacement)
                if keyless:
                    obj.shape_key_clear()

        if changed == 0:
            return OperationResult.cancelled("No selected mesh could be shrinkwrapped.")
        result = OperationResult.finished(
            f"Applied {key_name} to {changed} mesh(es).",
            payload=changed,
        )
        if warnings:
            return OperationResult.finished(
                result.message, level="WARNING", warnings=warnings, payload=changed
            )
        return result
    except Exception as error:
        return OperationResult.cancelled(f"Shrinkwrap failed: {error}", error=error)
    finally:
        if request.apply_immediately:
            restore_previous_context()
