from ...blender.collections import get_collection_children
from ...blender.context import (
    get_safe_mode,
    restore_previous_context,
    safe_mode_switch,
    store_current_context,
)
from ...blender.operator_results import OperationResult
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
from .shapekey_service import (
    add_positions_as_shape_key,
    key_coordinates,
    modifier_positions,
    move_with_basis,
)

_LOG = get_logger(__name__)


def _apply_positions(obj, name, positions, as_garment_support):
    keyless = not has_shape_keys(obj)
    if as_garment_support:
        # Only the GarmentSupport key is replaced; morphs and other keys stay.
        existing = shape_key_by_name(obj, GARMENT_SUPPORT_MORPH)
        if existing:
            obj.shape_key_remove(existing)
        add_positions_as_shape_key(obj, name, positions)
    elif keyless:
        obj.data.vertices.foreach_set("co", positions.reshape(-1))
        obj.data.update()
    else:
        # Apply into the basis and move every other key with it, so each keeps its offset.
        move_with_basis(
            obj, positions - key_coordinates(obj.data.shape_keys.reference_key)
        )


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
        pending = []
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
            if request.apply_immediately:
                applied_meshes.add(obj.data.as_pointer())
                pending.append((obj, modifier))

        if pending:
            positions = modifier_positions(context, pending)
            for (obj, modifier), shrunk in zip(pending, positions):
                name = modifier.name
                obj.modifiers.remove(modifier)
                _apply_positions(obj, name, shrunk, request.as_garment_support)

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
