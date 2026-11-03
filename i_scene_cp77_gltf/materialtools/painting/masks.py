import bpy

from ...assetio.values import coerce_int
from ...blender.operator_results import OperationResult
from ...blender.transactions import new_tracked_datablock, track_mutation, transactional
from ...core.log import get_logger, log_once
from ...core.notifications import report
from ..common.constants import (
    MASK_LAYER_PROPERTY,
    MASK_NODE_ROLE,
    MASK_OWNER_PROPERTY,
    ROOT_ROLE_PROPERTY,
)
from ..common.sync import material_sync_guard
from ..multilayer.editor import synchronize_panel
from ..multilayer.previews import set_shared_preview
from ..multilayer.state import (
    linked_layer_states,
    matching_template_states,
    resolve_material_state,
)
from .surface import (
    configure_surface_paint,
    restore_surface_paint,
)

_LOG = get_logger(__name__)


def _existing_mask_images(material, dimensions):
    material_name = getattr(material, "name", "")
    result = {}
    for image in tuple(getattr(bpy.data, "images", ())):
        try:
            if image.get(MASK_OWNER_PROPERTY) != material_name:
                continue
            layer_index = int(image.get(MASK_LAYER_PROPERTY, -1))
            size = tuple(image.size)
        except (AttributeError, ReferenceError, TypeError, ValueError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_existing_mask_images", type(error).__name__),
                "existing mask images: fell back after %s",
                error,
                exc_info=True,
            )
            continue
        if (
            layer_index >= 0
            and layer_index not in result
            and len(size) >= 2
            and tuple(size[:2]) == (dimensions, dimensions)
        ):
            result[layer_index] = image
    return result


def _remove_node(node_tree, node):
    try:
        node_tree.nodes.remove(node)
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
            ("_remove_node", type(error).__name__),
            "remove node: fell back after %s",
            error,
            exc_info=True,
        )


def _node_removed(node_tree, node):
    try:
        return all(candidate is not node for candidate in tuple(node_tree.nodes))
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_node_removed", type(error).__name__),
            "node removed: fell back after %s",
            error,
            exc_info=True,
        )
        return True


@transactional("Mask generation")
def generate_mask_images(context, dimensions=1024, obj=None, layer_indices=None):
    """Link a blank mask image to each linked layer past the first whose mask has none"""
    dimensions = coerce_int(dimensions, 0, unwrap=False)
    if not 1 <= dimensions <= 16384:
        return OperationResult.cancelled("Mask resolution is invalid.")
    state = resolve_material_state(context, obj=obj)
    if not state.valid_material:
        return OperationResult.cancelled(state.error_message)
    targets = None if layer_indices is None else {int(value) for value in layer_indices}
    existing_images = _existing_mask_images(state.material, dimensions)
    warnings = []
    for layer_index, layer_node in linked_layer_states(context, obj=state.obj):
        if layer_index == 1 or (targets is not None and layer_index not in targets):
            continue
        try:
            inputs = layer_node.inputs
            mask_socket = inputs.get("Mask") if inputs is not None else None
        except (AttributeError, ReferenceError, TypeError) as exc:
            log_once(
                _LOG,
                "DEBUG",
                ("generate_mask_images 1", type(exc).__name__),
                "generate mask images: fell back after %s",
                exc,
                exc_info=True,
            )
            mask_socket = None
        if mask_socket is None:
            continue
        try:
            socket_links = tuple(mask_socket.links)
        except (AttributeError, ReferenceError, TypeError) as exc:
            log_once(
                _LOG,
                "DEBUG",
                ("generate_mask_images 2", type(exc).__name__),
                "generate mask images: fell back after %s",
                exc,
                exc_info=True,
            )
            socket_links = ()
        source = getattr(socket_links[0], "from_node", None) if socket_links else None
        if (
            source is not None
            and getattr(source, "type", None) == "TEX_IMAGE"
            and getattr(source, "image", None) is not None
        ):
            continue
        if source is not None:
            warnings.append(
                f"Layer {layer_index} mask is linked to a non-image node and was left unchanged."
            )
            continue
        image = existing_images.get(layer_index)
        if image is None:
            image = new_tracked_datablock(
                "images",
                f"{state.material.name}_mlmask_{layer_index:02d}",
                width=dimensions,
                height=dimensions,
                alpha=False,
            )
            image.source = "GENERATED"
            image.generated_type = "BLANK"
            image.colorspace_settings.name = "Non-Color"
            image[MASK_OWNER_PROPERTY] = state.material.name
            image[MASK_LAYER_PROPERTY] = layer_index
            existing_images[layer_index] = image
        node = state.node_tree.nodes.new(type="ShaderNodeTexImage")
        track_mutation(
            ("materialtools_mask_node", id(state.node_tree), id(node)),
            lambda node_tree=state.node_tree, node=node: _remove_node(
                node_tree,
                node,
            ),
            verify=lambda node_tree=state.node_tree, node=node: _node_removed(
                node_tree,
                node,
            ),
            label=f"mask node {state.material.name} layer {layer_index}",
        )
        node.location = (-1250, 800 - (400 * layer_index))
        node.width = 300
        node.image = image
        node[ROOT_ROLE_PROPERTY] = MASK_NODE_ROLE
        state.node_tree.links.new(node.outputs["Color"], mask_socket)
    synchronize_panel(context)
    return OperationResult.finished(warnings=warnings)


_PAINT_PREVIOUS_NODE = "cp77MaterialToolsPaintPreviousNode"


def _restore_paint_targets(keep=()):
    for material in bpy.data.materials:
        if material in keep or _PAINT_PREVIOUS_NODE not in material:
            continue
        if not getattr(material, "is_editable", True):
            continue
        if material.node_tree is not None:
            material.node_tree.nodes.active = material.node_tree.nodes.get(
                material[_PAINT_PREVIOUS_NODE]
            )
        del material[_PAINT_PREVIOUS_NODE]


def activate_selected_mask(context):
    active = resolve_material_state(context)
    if (
        not active.valid_layer
        or active.mask_node is None
        or active.mask_node.type != "TEX_IMAGE"
        or active.mask_node.image is None
    ):
        return False
    configure_surface_paint(context, active)
    states = matching_template_states(context, active)
    valid = [
        state
        for state in states
        if state.mask_node is not None
        and state.mask_node.type == "TEX_IMAGE"
        and state.mask_node.image is not None
        and getattr(state.material, "is_editable", True)
    ]
    _restore_paint_targets(tuple(state.material for state in valid))
    for state in valid:
        nodes = state.node_tree.nodes
        if _PAINT_PREVIOUS_NODE not in state.material:
            state.material[_PAINT_PREVIOUS_NODE] = (
                nodes.active.name if nodes.active is not None else ""
            )
        if nodes.active != state.mask_node:
            nodes.active = state.mask_node
    return bool(valid)


def switch_texture_brush(brush_name, context):
    brush_name = str(brush_name or "Draw")
    brushes = getattr(bpy.data, "brushes", None)
    brush = brushes.get(brush_name) if brushes is not None else None
    operator = getattr(getattr(bpy.ops, "brush", None), "asset_activate", None)
    if operator is not None:
        identifier = (
            "brushes\\essentials_brushes-mesh_texture.blend\\Brush\\" + brush_name
        )
        try:
            result = operator(
                asset_library_type="ESSENTIALS",
                asset_library_identifier="",
                relative_asset_identifier=identifier,
            )
            if isinstance(result, set) and "FINISHED" in result:
                return True, ""
        except (AttributeError, RuntimeError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("switch_texture_brush 1", type(error).__name__),
                "switch texture brush: fell back after %s",
                error,
                exc_info=True,
            )
            activation_error = str(error)
        else:
            activation_error = f"Brush activation returned {sorted(result)}"
    else:
        activation_error = "Brush asset activation is unavailable"
    image_paint = getattr(
        getattr(context, "tool_settings", None),
        "image_paint",
        None,
    )
    if brush is not None and image_paint is not None:
        try:
            image_paint.brush = brush
            return True, ""
        except (AttributeError, ReferenceError, RuntimeError, TypeError) as exc:
            log_once(
                _LOG,
                "DEBUG",
                ("switch_texture_brush 2", type(exc).__name__),
                "switch texture brush: fell back after %s",
                exc,
                exc_info=True,
            )
    if brush is None:
        return False, f"Brush '{brush_name}' was not found"
    return False, activation_error


def toggle_texture_paint(owner, context):
    state = resolve_material_state(context)
    props = state.props
    current_mode = getattr(context, "mode", "OBJECT")
    if current_mode == "PAINT_TEXTURE":
        image_paint = getattr(
            getattr(context, "tool_settings", None),
            "image_paint",
            None,
        )
        current_brush = getattr(image_paint, "brush", None) if image_paint else None
        try:
            current_brush_name = current_brush.name if current_brush is not None else ""
        except (AttributeError, ReferenceError) as exc:
            log_once(
                _LOG,
                "DEBUG",
                ("toggle_texture_paint 1", type(exc).__name__),
                "toggle texture paint: fell back after %s",
                exc,
                exc_info=True,
            )
            current_brush_name = ""
        if current_brush_name and props is not None:
            with material_sync_guard():
                props.last_paint_brush = current_brush_name
        try:
            result = bpy.ops.object.mode_set(mode="OBJECT")
        except (AttributeError, RuntimeError, TypeError) as error:
            report(
                owner,
                "ERROR",
                f"Could not leave Texture Paint mode: {error}",
                logger=_LOG,
                error=error,
            )
            return {"CANCELLED"}
        if not isinstance(result, set) or "FINISHED" not in result:
            report(
                owner,
                "ERROR",
                f"Leaving Texture Paint returned {sorted(result)}",
                logger=_LOG,
            )
            return {"CANCELLED"}
        _restore_paint_targets()
        restore_surface_paint(context)
        set_shared_preview(owner, context, False, mask=True)
        if props is not None:
            with material_sync_guard():
                props.multilayer_paint_mask_bool = False
        return {"FINISHED"}
    if not state.valid_layer or props is None:
        report(
            owner,
            "ERROR",
            state.error_message or "No active multilayer layer",
            logger=_LOG,
        )
        return {"CANCELLED"}
    obj = state.obj
    try:
        uv_layers = obj.data.uv_layers
    except (AttributeError, ReferenceError) as exc:
        log_once(
            _LOG,
            "DEBUG",
            ("toggle_texture_paint 2", type(exc).__name__),
            "toggle texture paint: fell back after %s",
            exc,
            exc_info=True,
        )
        uv_layers = None
    if uv_layers is None or len(uv_layers) == 0:
        report(owner, "ERROR", "The active mesh has no UV map.", logger=_LOG)
        return {"CANCELLED"}
    mask_node = state.mask_node
    try:
        valid_mask = (
            mask_node is not None
            and mask_node.type == "TEX_IMAGE"
            and mask_node.image is not None
        )
    except (AttributeError, ReferenceError) as exc:
        log_once(
            _LOG,
            "DEBUG",
            ("toggle_texture_paint 3", type(exc).__name__),
            "toggle texture paint: fell back after %s",
            exc,
            exc_info=True,
        )
        valid_mask = False
    if not valid_mask:
        report(
            owner,
            "ERROR",
            "No mask image is linked to the selected layer.",
            logger=_LOG,
        )
        return {"CANCELLED"}
    if current_mode != "OBJECT":
        report(
            owner,
            "ERROR",
            "Texture Paint can only be entered from Object mode.",
            logger=_LOG,
        )
        return {"CANCELLED"}
    try:
        configure_surface_paint(context, state)
        nodes = state.node_tree.nodes
        previous_active = nodes.active
        nodes.active = mask_node
        result = bpy.ops.object.mode_set(mode="TEXTURE_PAINT")
    except (
        AttributeError,
        ReferenceError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        restore_surface_paint(context)
        try:
            nodes.active = previous_active
        except (
            AttributeError,
            UnboundLocalError,
            ReferenceError,
            RuntimeError,
            TypeError,
        ) as exc:
            log_once(
                _LOG,
                "DEBUG",
                ("toggle_texture_paint 4", type(exc).__name__),
                "toggle texture paint: fell back after %s",
                exc,
                exc_info=True,
            )
        report(
            owner,
            "ERROR",
            f"Could not enter Texture Paint mode: {error}",
            logger=_LOG,
            error=error,
        )
        return {"CANCELLED"}
    if not isinstance(result, set) or "FINISHED" not in result:
        restore_surface_paint(context)
        try:
            nodes.active = previous_active
        except (AttributeError, ReferenceError, RuntimeError, TypeError) as exc:
            log_once(
                _LOG,
                "DEBUG",
                ("toggle_texture_paint 5", type(exc).__name__),
                "toggle texture paint: fell back after %s",
                exc,
                exc_info=True,
            )
        report(
            owner,
            "ERROR",
            f"Entering Texture Paint returned {sorted(result) if isinstance(result, set) else result!r}",
            logger=_LOG,
        )
        return {"CANCELLED"}
    if _PAINT_PREVIOUS_NODE not in state.material:
        state.material[_PAINT_PREVIOUS_NODE] = (
            previous_active.name if previous_active is not None else ""
        )
    activate_selected_mask(context)
    set_shared_preview(owner, context, True, mask=True)
    brush_name = props.last_paint_brush or "Draw"
    ok, reason = switch_texture_brush(brush_name, context)
    if not ok:
        report(owner, "WARNING", reason, logger=_LOG)
    with material_sync_guard():
        props.multilayer_paint_mask_bool = True
    return {"FINISHED"}
