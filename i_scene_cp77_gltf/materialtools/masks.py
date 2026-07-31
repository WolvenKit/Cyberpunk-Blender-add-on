import bpy

from ..blender.transactions import (
    DatablockImportTransaction,
    current_import_transaction,
    new_tracked_datablock,
    rollback_report_message,
    track_mutation,
)
from .constants import (
    MASK_LAYER_PROPERTY,
    MASK_NODE_ROLE,
    MASK_OWNER_PROPERTY,
    PREVIOUS_OUTPUT_PROPERTY,
    ROOT_ROLE_PROPERTY,
    VIEW_MASK_NODE_NAME,
    VIEW_MASK_ROLE,
)
from .editor import synchronize_panel
from .reporting import report_materialtools
from .state import linked_layer_states, resolve_material_state
from .sync import material_sync_guard, material_syncing


def _active_output(nodes, exclude=None):
    for node in tuple(nodes):
        if node is exclude:
            continue
        try:
            if node.type == "OUTPUT_MATERIAL" and node.is_active_output:
                return node
        except (AttributeError, ReferenceError):
            continue
    return None


def _material_property(material, key, default=None):
    try:
        return material.get(key, default)
    except (AttributeError, ReferenceError, TypeError):
        return default


def _restore_material_property(material, key, existed, value):
    try:
        if existed:
            material[key] = value
        elif key in material:
            del material[key]
    except (AttributeError, ReferenceError, RuntimeError, TypeError):
        pass


def _preview_links(links, preview, surface):
    result = []
    for link in tuple(links):
        try:
            if link.to_node is preview and link.to_socket is surface:
                result.append((link.from_socket, link.to_socket))
        except (AttributeError, ReferenceError):
            continue
    return tuple(result)


def _remove_preview_links(links, preview, surface):
    for link in tuple(links):
        try:
            if link.to_node is preview and link.to_socket is surface:
                links.remove(link)
        except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
            continue


def set_view_mask_enabled(owner, context=None, enabled=None):
    if material_syncing():
        return False
    context = context or bpy.context
    state = resolve_material_state(context)
    props = state.props
    enabled = bool(
        props.multilayer_view_mask_bool
        if enabled is None and props is not None
        else enabled
    )
    if not state.valid_layer:
        if props is not None:
            with material_sync_guard():
                props.multilayer_view_mask_bool = False
        report_materialtools(
            owner,
            "WARNING",
            state.error_message or "No linked multilayer layer",
        )
        return False
    try:
        layer_outputs = state.layer_node.outputs
        layer_mask = layer_outputs.get("Layer Mask") if layer_outputs is not None else None
        nodes = state.node_tree.nodes
        links = state.node_tree.links
    except (AttributeError, ReferenceError, TypeError):
        layer_mask = None
        nodes = None
        links = None
    if layer_mask is None or nodes is None or links is None:
        if props is not None:
            with material_sync_guard():
                props.multilayer_view_mask_bool = False
        report_materialtools(
            owner,
            "WARNING",
            "The selected layer has no usable Layer Mask output.",
        )
        return False

    preview = None
    created_preview = None
    surface = None
    original_links = ()
    original_active = _active_output(nodes)
    property_existed = PREVIOUS_OUTPUT_PROPERTY in state.material
    property_value = _material_property(
        state.material,
        PREVIOUS_OUTPUT_PROPERTY,
        "",
    )
    try:
        preview = nodes.get(VIEW_MASK_NODE_NAME)
        if enabled:
            if preview is None:
                preview = nodes.new(type="ShaderNodeOutputMaterial")
                created_preview = preview
                preview.name = VIEW_MASK_NODE_NAME
                preview.location = (-200, 400)
                preview[ROOT_ROLE_PROPERTY] = VIEW_MASK_ROLE
            preview_inputs = preview.inputs
            surface = preview_inputs[0] if preview_inputs is not None and len(preview_inputs) else None
            if surface is None:
                raise RuntimeError("Preview material output has no surface input")
            original_links = _preview_links(links, preview, surface)
            previous = _active_output(nodes, exclude=preview)
            if previous is not None:
                state.material[PREVIOUS_OUTPUT_PROPERTY] = previous.name
            _remove_preview_links(links, preview, surface)
            links.new(layer_mask, surface)
            preview.is_active_output = True
            return True

        previous_name = _material_property(
            state.material,
            PREVIOUS_OUTPUT_PROPERTY,
            "",
        )
        previous = nodes.get(previous_name) if previous_name else None
        if previous is None:
            previous = next(
                (
                    node
                    for node in tuple(nodes)
                    if node is not preview
                    and getattr(node, "type", None) == "OUTPUT_MATERIAL"
                ),
                None,
            )
        if previous is not None:
            previous.is_active_output = True
        if preview is not None:
            nodes.remove(preview)
        _restore_material_property(
            state.material,
            PREVIOUS_OUTPUT_PROPERTY,
            False,
            None,
        )
        return True
    except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError) as error:
        if preview is not None and surface is not None:
            _remove_preview_links(links, preview, surface)
            for from_socket, to_socket in original_links:
                try:
                    links.new(from_socket, to_socket)
                except (AttributeError, ReferenceError, RuntimeError, TypeError):
                    pass
        if created_preview is not None:
            try:
                nodes.remove(created_preview)
            except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
                pass
        if original_active is not None:
            try:
                original_active.is_active_output = True
            except (AttributeError, ReferenceError, RuntimeError, TypeError):
                pass
        _restore_material_property(
            state.material,
            PREVIOUS_OUTPUT_PROPERTY,
            property_existed,
            property_value,
        )
        if props is not None:
            with material_sync_guard():
                props.multilayer_view_mask_bool = False
        report_materialtools(
            owner,
            "WARNING",
            f"Could not update the mask preview: {error}",
        )
        return False


def _find_existing_mask_image(material, layer_index, dimensions):
    material_name = getattr(material, "name", "")
    for image in tuple(getattr(bpy.data, "images", ())):
        try:
            if image.get(MASK_OWNER_PROPERTY) != material_name:
                continue
            if int(image.get(MASK_LAYER_PROPERTY, -1)) != int(layer_index):
                continue
            size = tuple(image.size)
        except (AttributeError, ReferenceError, TypeError, ValueError):
            continue
        if len(size) >= 2 and tuple(size[:2]) == (dimensions, dimensions):
            return image
    return None


def _remove_node(node_tree, node):
    try:
        node_tree.nodes.remove(node)
    except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
        pass


def _node_removed(node_tree, node):
    try:
        return all(candidate is not node for candidate in tuple(node_tree.nodes))
    except (AttributeError, ReferenceError, TypeError):
        return True


def generate_mask_images(owner, context=None, dimensions=1024, obj=None):
    context = context or bpy.context
    try:
        dimensions = int(dimensions)
    except (TypeError, ValueError):
        dimensions = 0
    if not 1 <= dimensions <= 16384:
        report_materialtools(owner, "ERROR", "Mask resolution is invalid.")
        return {"CANCELLED"}
    state = resolve_material_state(context, obj=obj)
    if not state.valid_material:
        report_materialtools(owner, "ERROR", state.error_message)
        return {"CANCELLED"}
    transaction = current_import_transaction()
    owns_transaction = transaction is None
    transaction = transaction or DatablockImportTransaction()
    savepoint = transaction.savepoint()
    scope = transaction.scope() if owns_transaction else None
    try:
        if scope is not None:
            scope.__enter__()
        for layer_index, layer_node in linked_layer_states(context, obj=state.obj):
            if layer_index == 1:
                continue
            try:
                inputs = layer_node.inputs
                mask_socket = inputs.get("Mask") if inputs is not None else None
            except (AttributeError, ReferenceError, TypeError):
                mask_socket = None
            if mask_socket is None:
                continue
            try:
                socket_links = tuple(mask_socket.links)
            except (AttributeError, ReferenceError, TypeError):
                socket_links = ()
            source = getattr(socket_links[0], "from_node", None) if socket_links else None
            if (
                source is not None
                and getattr(source, "type", None) == "TEX_IMAGE"
                and getattr(source, "image", None) is not None
            ):
                continue
            if source is not None:
                report_materialtools(
                    owner,
                    "WARNING",
                    f"Layer {layer_index} mask is linked to a non-image node and was left unchanged.",
                )
                continue
            image = _find_existing_mask_image(
                state.material,
                layer_index,
                dimensions,
            )
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
            state.node_tree.links.new(node.outputs[0], mask_socket)
        synchronize_panel(context)
        if owns_transaction:
            transaction.commit()
        return {"FINISHED"}
    except Exception as error:
        report = (
            transaction.rollback()
            if owns_transaction
            else transaction.rollback_to(savepoint)
        )
        detail = rollback_report_message(report)
        message = f"Mask generation failed: {type(error).__name__}: {error}"
        if detail:
            message += f"; rollback incomplete: {detail}"
        report_materialtools(owner, "ERROR", message)
        return {"CANCELLED"}
    finally:
        if scope is not None:
            scope.__exit__(None, None, None)


def activate_selected_mask(context=None):
    context = context or bpy.context
    state = resolve_material_state(context)
    try:
        valid = (
            state.valid_layer
            and state.mask_node is not None
            and state.mask_node.type == "TEX_IMAGE"
            and state.mask_node.image is not None
        )
    except (AttributeError, ReferenceError):
        valid = False
    if not valid:
        return False
    try:
        state.node_tree.nodes.active = state.mask_node
    except (AttributeError, ReferenceError, RuntimeError, TypeError):
        return False
    return True


def switch_texture_brush(brush_name, context=None):
    context = context or bpy.context
    brush_name = str(brush_name or "Draw")
    brushes = getattr(bpy.data, "brushes", None)
    brush = brushes.get(brush_name) if brushes is not None else None
    operator = getattr(getattr(bpy.ops, "brush", None), "asset_activate", None)
    if operator is not None:
        identifier = (
            "brushes\\essentials_brushes-mesh_texture.blend\\Brush\\"
            + brush_name
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
        except (AttributeError, ReferenceError, RuntimeError, TypeError):
            pass
    if brush is None:
        return False, f"Brush '{brush_name}' was not found"
    return False, activation_error


def toggle_texture_paint(owner, context=None):
    context = context or bpy.context
    state = resolve_material_state(context)
    props = state.props
    if not state.valid_layer or props is None:
        report_materialtools(
            owner,
            "ERROR",
            state.error_message or "No active multilayer layer",
        )
        return {"CANCELLED"}
    obj = state.obj
    try:
        uv_layers = obj.data.uv_layers
    except (AttributeError, ReferenceError):
        uv_layers = None
    if uv_layers is None or len(uv_layers) == 0:
        report_materialtools(owner, "ERROR", "The active mesh has no UV map.")
        return {"CANCELLED"}
    mask_node = state.mask_node
    try:
        valid_mask = (
            mask_node is not None
            and mask_node.type == "TEX_IMAGE"
            and mask_node.image is not None
        )
    except (AttributeError, ReferenceError):
        valid_mask = False
    if not valid_mask:
        report_materialtools(
            owner,
            "ERROR",
            "No mask image is linked to the selected layer.",
        )
        return {"CANCELLED"}
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
        except (AttributeError, ReferenceError):
            current_brush_name = ""
        if current_brush_name:
            with material_sync_guard():
                props.last_paint_brush = current_brush_name
        try:
            result = bpy.ops.object.mode_set(mode="OBJECT")
        except (AttributeError, RuntimeError, TypeError) as error:
            report_materialtools(
                owner,
                "ERROR",
                f"Could not leave Texture Paint mode: {error}",
            )
            return {"CANCELLED"}
        if not isinstance(result, set) or "FINISHED" not in result:
            report_materialtools(
                owner,
                "ERROR",
                f"Leaving Texture Paint returned {sorted(result)}",
            )
            return {"CANCELLED"}
        with material_sync_guard():
            props.multilayer_paint_mask_bool = False
        return {"FINISHED"}
    if current_mode != "OBJECT":
        report_materialtools(
            owner,
            "ERROR",
            "Texture Paint can only be entered from Object mode.",
        )
        return {"CANCELLED"}
    try:
        nodes = state.node_tree.nodes
        previous_active = nodes.active
        nodes.active = mask_node
        result = bpy.ops.object.mode_set(mode="TEXTURE_PAINT")
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        try:
            nodes.active = previous_active
        except (AttributeError, UnboundLocalError, ReferenceError, RuntimeError, TypeError):
            pass
        report_materialtools(
            owner,
            "ERROR",
            f"Could not enter Texture Paint mode: {error}",
        )
        return {"CANCELLED"}
    if not isinstance(result, set) or "FINISHED" not in result:
        try:
            nodes.active = previous_active
        except (AttributeError, ReferenceError, RuntimeError, TypeError):
            pass
        report_materialtools(
            owner,
            "ERROR",
            f"Entering Texture Paint returned {sorted(result) if isinstance(result, set) else result!r}",
        )
        return {"CANCELLED"}
    brush_name = props.last_paint_brush or "Draw"
    ok, reason = switch_texture_brush(brush_name, context)
    if not ok:
        report_materialtools(owner, "WARNING", reason)
    with material_sync_guard():
        props.multilayer_paint_mask_bool = True
    return {"FINISHED"}
