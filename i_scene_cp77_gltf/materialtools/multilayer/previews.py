import logging
from dataclasses import replace
from time import perf_counter

import bpy

from ...bartmoss.scalar import (
    SRGB_DECODE_THRESHOLD,
    SRGB_GAMMA,
    SRGB_LINEAR_SCALE,
    SRGB_OFFSET,
    SRGB_SCALE,
    srgb_channel_to_linear,
)
from ...blender import shader_nodes
from ...core.log import get_logger, log_once
from ...core.notifications import report
from ...material_types.graph import add_bundle_items
from ...material_types.mat_common import find_input
from ...material_types.multilayered import LAYER_BUNDLE_ITEMS
from ...materials.blender.nodes import (
    CreateCalculateVecNormalZ,
    configure_tangent_normal_map,
)
from ..common.access import (
    material_property,
    node_input,
)
from ..common.constants import (
    PREVIOUS_OUTPUT_PROPERTY,
    ROOT_ROLE_PROPERTY,
    VIEW_MASK_DIAGNOSTIC_NODE_NAME,
    VIEW_MASK_DIAGNOSTIC_ROLE,
    VIEW_MASK_NODE_NAME,
    VIEW_MASK_ROLE,
    VIEW_MASK_SHADER_NAME,
    VIEW_MASK_SHADER_ROLE,
    VIEW_TEMPLATE_NODE_NAME,
    VIEW_TEMPLATE_OUTPUT_NAME,
    VIEW_TEMPLATE_OUTPUT_ROLE,
    VIEW_TEMPLATE_ROLE,
)
from ..common.sync import (
    material_sync_guard,
    material_syncing,
)
from .state import (
    linked_layer_states,
    matching_template_states,
    resolve_material_state,
)

_LOG = get_logger(__name__)

_MASK_DIAGNOSTIC_GROUP = "CP77 Multilayer Mask Diagnostics 1.0"
_TEMPLATE_PREVIEW_GROUP = "CP77 Multilayer Template Preview 1.0"
_MASK_PREVIEW_MODES = {
    "MASK": 0.0,
    "CONTRIBUTING": 1.0,
    "COMPLEXITY": 2.0,
}
_MASK_HEATMAP_SRGB = (
    (0.000, 0.000, 0.000),
    (0.140, 0.304, 0.607),
    (0.367, 0.414, 0.738),
    (0.663, 0.421, 0.810),
    (1.000, 0.497, 0.384),
    (0.969, 0.912, 0.353),
    (1.000, 1.000, 0.977),
)


def _active_output(nodes, exclude=None):
    for node in tuple(nodes):
        if node is exclude:
            continue
        try:
            if node.type == "OUTPUT_MATERIAL" and node.is_active_output:
                return node
        except ReferenceError:
            continue
    return None


def _restore_material_property(material, key, existed, value):
    try:
        if existed:
            material[key] = value
        elif key in material:
            del material[key]
    except (ReferenceError, RuntimeError):
        pass


def _remove_node(nodes, node):
    if node is None:
        return
    try:
        nodes.remove(node)
    except (ReferenceError, RuntimeError, ValueError):
        pass


def _restore_previous_output(state, exclude=None):
    nodes = state.node_tree.nodes
    previous_name = material_property(state.material, PREVIOUS_OUTPUT_PROPERTY, "")
    previous = nodes.get(previous_name) if previous_name else None
    if previous is None:
        previous = next(
            (
                node
                for node in tuple(nodes)
                if node is not exclude
                and getattr(node, "type", None) == "OUTPUT_MATERIAL"
                and node.name not in (VIEW_MASK_NODE_NAME, VIEW_TEMPLATE_OUTPUT_NAME)
            ),
            None,
        )
    if previous is not None:
        previous.is_active_output = True
    _restore_material_property(state.material, PREVIOUS_OUTPUT_PROPERTY, False, None)


def _remember_previous_output(state, exclude=None):
    previous = _active_output(state.node_tree.nodes, exclude=exclude)
    if previous is not None:
        state.material[PREVIOUS_OUTPUT_PROPERTY] = previous.name
    return previous


def _disable_mask_preview(state, restore=True, remove=True):
    nodes = state.node_tree.nodes
    output = nodes.get(VIEW_MASK_NODE_NAME)
    was_active = (
        bool(getattr(output, "is_active_output", False))
        if output is not None
        else False
    )
    for name in (
        VIEW_MASK_NODE_NAME,
        VIEW_MASK_SHADER_NAME,
        VIEW_MASK_DIAGNOSTIC_NODE_NAME,
    ):
        if remove:
            _remove_node(nodes, nodes.get(name))
    if restore and was_active:
        _restore_previous_output(state)
    return was_active


def _disable_template_preview(state, restore=True, remove=True):
    nodes = state.node_tree.nodes
    output = nodes.get(VIEW_TEMPLATE_OUTPUT_NAME)
    was_active = (
        bool(getattr(output, "is_active_output", False))
        if output is not None
        else False
    )
    for name in (VIEW_TEMPLATE_OUTPUT_NAME, VIEW_TEMPLATE_NODE_NAME):
        if remove:
            _remove_node(nodes, nodes.get(name))
    if restore and was_active:
        _restore_previous_output(state)
    return was_active


def _linear_heatmap_color(rgb):
    return tuple(srgb_channel_to_linear(value) for value in rgb) + (1.0,)


def _mask_value_group():
    name = "CP77 Multilayer Raw Mask Preview 1.0"
    group = bpy.data.node_groups.get(name)
    if group is not None:
        return group
    group = bpy.data.node_groups.new(name, "ShaderNodeTree")
    group.interface.new_socket(
        name="Active Mask", socket_type="NodeSocketFloat", in_out="INPUT"
    )
    group.interface.new_socket(
        name="Color", socket_type="NodeSocketColor", in_out="OUTPUT"
    )
    nodes, links = group.nodes, group.links
    group_input = nodes.new("NodeGroupInput")
    group_output = nodes.new("NodeGroupOutput")
    active_low = shader_nodes.math(
        nodes, links, "DIVIDE", label="Mask sRGB Low", location=(-120, 420)
    ).node
    shader_nodes.socket_by_identifier(
        active_low.inputs, "Value_001"
    ).default_value = SRGB_LINEAR_SCALE
    links.new(group_input.outputs["Active Mask"], active_low.inputs["Value"])
    active_add = shader_nodes.math(
        nodes, links, "ADD", label="Mask sRGB Offset", location=(-120, 360)
    ).node
    shader_nodes.socket_by_identifier(
        active_add.inputs, "Value_001"
    ).default_value = SRGB_OFFSET
    links.new(group_input.outputs["Active Mask"], active_add.inputs["Value"])
    active_divide = shader_nodes.math(
        nodes, links, "DIVIDE", label="Mask sRGB Scale", location=(40, 360)
    ).node
    shader_nodes.socket_by_identifier(
        active_divide.inputs, "Value_001"
    ).default_value = SRGB_SCALE
    links.new(active_add.outputs["Value"], active_divide.inputs["Value"])
    active_high = shader_nodes.math(
        nodes, links, "POWER", label="Mask sRGB High", location=(200, 360)
    ).node
    shader_nodes.socket_by_identifier(
        active_high.inputs, "Value_001"
    ).default_value = SRGB_GAMMA
    links.new(active_divide.outputs["Value"], active_high.inputs["Value"])
    active_low_range = shader_nodes.math(
        nodes, links, "LESS_THAN", label="Mask sRGB Low Range", location=(40, 430)
    ).node
    shader_nodes.socket_by_identifier(
        active_low_range.inputs, "Value_001"
    ).default_value = SRGB_DECODE_THRESHOLD
    links.new(group_input.outputs["Active Mask"], active_low_range.inputs["Value"])
    active_delta = shader_nodes.math(
        nodes, links, "SUBTRACT", label="Mask sRGB Delta", location=(200, 430)
    ).node
    links.new(active_low.outputs["Value"], active_delta.inputs["Value"])
    links.new(
        active_high.outputs["Value"],
        shader_nodes.socket_by_identifier(active_delta.inputs, "Value_001"),
    )
    active_low_delta = shader_nodes.math(
        nodes, links, "MULTIPLY", label="Mask sRGB Select", location=(360, 430)
    ).node
    links.new(active_delta.outputs["Value"], active_low_delta.inputs["Value"])
    links.new(
        active_low_range.outputs["Value"],
        shader_nodes.socket_by_identifier(active_low_delta.inputs, "Value_001"),
    )
    active_linear = shader_nodes.math(
        nodes, links, "ADD", label="Mask Linear", location=(520, 430)
    ).node
    links.new(active_high.outputs["Value"], active_linear.inputs["Value"])
    links.new(
        active_low_delta.outputs["Value"],
        shader_nodes.socket_by_identifier(active_linear.inputs, "Value_001"),
    )

    active_color = nodes.new("ShaderNodeCombineXYZ")
    active_color.location = (540, 320)
    active_color.label = "Active Mask"
    for axis in ("X", "Y", "Z"):
        links.new(active_linear.outputs["Value"], active_color.inputs[axis])

    links.new(active_color.outputs["Vector"], group_output.inputs["Color"])
    return group


def _link_input(tree, target, source=None, default=0.0):
    links = tuple(target.links)
    if source is not None and len(links) == 1 and links[0].from_socket == source:
        return
    for link in links:
        tree.links.remove(link)
    if source is not None:
        tree.links.new(source, target)
    elif target.default_value != default:
        target.default_value = default


def _mask_diagnostic_group():
    group = bpy.data.node_groups.get(_MASK_DIAGNOSTIC_GROUP)
    if group is not None:
        return group

    group = bpy.data.node_groups.new(_MASK_DIAGNOSTIC_GROUP, "ShaderNodeTree")
    group.interface.new_socket(
        name="Mode", socket_type="NodeSocketFloat", in_out="INPUT"
    )
    group.interface.new_socket(
        name="Active Mask", socket_type="NodeSocketFloat", in_out="INPUT"
    )
    for index in range(2, 21):
        group.interface.new_socket(
            name=f"Layer {index} Mask",
            socket_type="NodeSocketFloat",
            in_out="INPUT",
        )
        group.interface.new_socket(
            name=f"Layer {index} Storage Weight",
            socket_type="NodeSocketFloat",
            in_out="INPUT",
        )
    group.interface.new_socket(
        name="Color", socket_type="NodeSocketColor", in_out="OUTPUT"
    )

    nodes = group.nodes
    links = group.links
    group_input = nodes.new("NodeGroupInput")
    group_input.location = (-1600, 0)
    group_output = nodes.new("NodeGroupOutput")
    group_output.location = (900, 0)

    active_color = nodes.new("ShaderNodeGroup")
    active_color.node_tree = _mask_value_group()
    links.new(group_input.outputs["Active Mask"], active_color.inputs["Active Mask"])

    count = nodes.new("ShaderNodeValue")
    count.location = (-1350, 260)
    count.label = "Base Layer"
    count.outputs["Value"].default_value = 1.0
    complexity = nodes.new("ShaderNodeValue")
    complexity.location = (-1350, -260)
    complexity.label = "Stored Mask Complexity"
    complexity.outputs["Value"].default_value = 0.0

    count_socket = count.outputs["Value"]
    complexity_socket = complexity.outputs["Value"]
    for offset, index in enumerate(range(2, 21)):
        y = 140 - offset * 68
        present = shader_nodes.math(
            nodes,
            links,
            "GREATER_THAN",
            label=f"Layer {index} Present",
            location=(-1080, y),
        ).node
        shader_nodes.socket_by_identifier(
            present.inputs, "Value_001"
        ).default_value = 0.0
        links.new(group_input.outputs[f"Layer {index} Mask"], present.inputs["Value"])

        count_add = shader_nodes.math(
            nodes,
            links,
            "ADD",
            label=f"Count Layer {index}",
            location=(-820, 260 - offset * 12),
        ).node
        links.new(count_socket, count_add.inputs["Value"])
        links.new(
            present.outputs["Value"],
            shader_nodes.socket_by_identifier(count_add.inputs, "Value_001"),
        )
        count_socket = count_add.outputs["Value"]

        weighted = shader_nodes.math(
            nodes,
            links,
            "MULTIPLY",
            label=f"Layer {index} Storage",
            location=(-820, y - 24),
        ).node
        links.new(present.outputs["Value"], weighted.inputs["Value"])
        links.new(
            group_input.outputs[f"Layer {index} Storage Weight"],
            shader_nodes.socket_by_identifier(weighted.inputs, "Value_001"),
        )
        complexity_add = shader_nodes.math(
            nodes,
            links,
            "ADD",
            label=f"Complexity Layer {index}",
            location=(-560, -260 - offset * 12),
        ).node
        links.new(complexity_socket, complexity_add.inputs["Value"])
        links.new(
            weighted.outputs["Value"],
            shader_nodes.socket_by_identifier(complexity_add.inputs, "Value_001"),
        )
        complexity_socket = complexity_add.outputs["Value"]

    count_limit = shader_nodes.math(
        nodes, links, "MINIMUM", label="Clamp Layer Count", location=(-260, 180)
    ).node
    shader_nodes.socket_by_identifier(
        count_limit.inputs, "Value_001"
    ).default_value = 6.0
    links.new(count_socket, count_limit.inputs["Value"])

    complexity_ceil = shader_nodes.math(
        nodes, links, "CEIL", label="Round Complexity Up", location=(-300, -180)
    ).node
    links.new(complexity_socket, complexity_ceil.inputs["Value"])
    complexity_limit = shader_nodes.math(
        nodes, links, "MINIMUM", label="Clamp Complexity", location=(-80, -180)
    ).node
    shader_nodes.socket_by_identifier(
        complexity_limit.inputs, "Value_001"
    ).default_value = 6.0
    links.new(complexity_ceil.outputs["Value"], complexity_limit.inputs["Value"])

    count_mode = shader_nodes.math(
        nodes, links, "COMPARE", label="Contributing Layers Mode", location=(-60, 40)
    ).node
    shader_nodes.socket_by_identifier(
        count_mode.inputs, "Value_001"
    ).default_value = 1.0
    shader_nodes.socket_by_identifier(
        count_mode.inputs, "Value_002"
    ).default_value = 0.1
    links.new(group_input.outputs["Mode"], count_mode.inputs["Value"])

    delta = shader_nodes.math(
        nodes, links, "SUBTRACT", label="Count Minus Complexity", location=(140, -60)
    ).node
    links.new(count_limit.outputs["Value"], delta.inputs["Value"])
    links.new(
        complexity_limit.outputs["Value"],
        shader_nodes.socket_by_identifier(delta.inputs, "Value_001"),
    )
    selected_delta = shader_nodes.math(
        nodes, links, "MULTIPLY", label="Select Count", location=(330, -60)
    ).node
    links.new(delta.outputs["Value"], selected_delta.inputs["Value"])
    links.new(
        count_mode.outputs["Value"],
        shader_nodes.socket_by_identifier(selected_delta.inputs, "Value_001"),
    )
    selected_value = shader_nodes.math(
        nodes, links, "ADD", label="Diagnostic Value", location=(500, -60)
    ).node
    links.new(complexity_limit.outputs["Value"], selected_value.inputs["Value"])
    links.new(
        selected_delta.outputs["Value"],
        shader_nodes.socket_by_identifier(selected_value.inputs, "Value_001"),
    )

    normalize = shader_nodes.math(
        nodes, links, "MULTIPLY", label="Normalize Diagnostic", location=(500, 80)
    ).node
    shader_nodes.socket_by_identifier(normalize.inputs, "Value_001").default_value = (
        1.0 / 6.0
    )
    links.new(selected_value.outputs["Value"], normalize.inputs["Value"])

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (680, 80)
    ramp.label = "Layer Diagnostic Heatmap"
    ramp.color_ramp.interpolation = "CONSTANT"
    elements = ramp.color_ramp.elements
    elements[0].position = 0.0
    elements[0].color = _linear_heatmap_color(_MASK_HEATMAP_SRGB[0])
    elements[1].position = 1.0 / 12.0
    elements[1].color = _linear_heatmap_color(_MASK_HEATMAP_SRGB[1])
    for index in range(2, 7):
        element = elements.new((index - 0.5) / 6.0)
        element.color = _linear_heatmap_color(_MASK_HEATMAP_SRGB[index])
    links.new(normalize.outputs["Value"], ramp.inputs["Factor"])

    active_mode = shader_nodes.math(
        nodes, links, "COMPARE", label="Active Mask Mode", location=(300, 250)
    ).node
    shader_nodes.socket_by_identifier(
        active_mode.inputs, "Value_001"
    ).default_value = 0.0
    shader_nodes.socket_by_identifier(
        active_mode.inputs, "Value_002"
    ).default_value = 0.1
    links.new(group_input.outputs["Mode"], active_mode.inputs["Value"])

    result = nodes.new("ShaderNodeMix")
    result.location = (680, 300)
    result.label = "Preview Mode"
    result.data_type = "RGBA"
    links.new(
        active_mode.outputs["Value"],
        shader_nodes.socket_by_identifier(result.inputs, "Factor_Float"),
    )
    links.new(
        ramp.outputs["Color"],
        shader_nodes.socket_by_identifier(result.inputs, "A_Color"),
    )
    links.new(
        active_color.outputs["Color"],
        shader_nodes.socket_by_identifier(result.inputs, "B_Color"),
    )
    links.new(
        shader_nodes.socket_by_identifier(result.outputs, "Result_Color"),
        group_output.inputs["Color"],
    )
    return group


def _template_preview_group():
    group = bpy.data.node_groups.get(_TEMPLATE_PREVIEW_GROUP)
    if group is not None:
        return group

    group = bpy.data.node_groups.new(_TEMPLATE_PREVIEW_GROUP, "ShaderNodeTree")
    group.interface.new_socket(
        name="Layer", socket_type="NodeSocketBundle", in_out="INPUT"
    )
    group.interface.new_socket(
        name="Shader", socket_type="NodeSocketShader", in_out="OUTPUT"
    )

    nodes = group.nodes
    links = group.links
    group_input = nodes.new("NodeGroupInput")
    group_input.location = (-800, 0)
    group_output = nodes.new("NodeGroupOutput")
    group_output.location = (500, 0)

    separate = nodes.new("NodeSeparateBundle")
    separate.location = (-580, 0)
    separate.label = "Selected MLTemplate"
    add_bundle_items(separate, LAYER_BUNDLE_ITEMS)
    links.new(group_input.outputs["Layer"], separate.inputs["Bundle"])

    rebuild = CreateCalculateVecNormalZ(
        group, -260, -220, "CP77 MLTemplate Preview Normal"
    )
    normal_map = configure_tangent_normal_map(nodes.new("ShaderNodeNormalMap"))
    normal_map.location = (0, -220)
    links.new(separate.outputs["Normal"], rebuild.inputs["Image"])
    links.new(rebuild.outputs["Image"], normal_map.inputs["Color"])

    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (180, 20)
    principled.label = "Selected MLTemplate"
    for source_name, target_name in (
        ("Color", "Base Color"),
        ("Metalness", "Metallic"),
        ("Roughness", "Roughness"),
    ):
        target = find_input(principled, target_name)
        if target is not None:
            links.new(separate.outputs[source_name], target)
    normal = find_input(principled, "Normal")
    if normal is not None:
        links.new(normal_map.outputs["Normal"], normal)
    links.new(principled.outputs["BSDF"], group_output.inputs["Shader"])
    return group


def _socket_source(socket):
    if socket is None:
        return None
    try:
        links = tuple(socket.links)
    except ReferenceError:
        return None
    return links[0].from_socket if links else None


def _socket_default(socket, default=0.0):
    if socket is None:
        return default
    try:
        return float(socket.default_value)
    except (ReferenceError, ValueError):
        return default


def _mask_image_area(layer_node):
    mask = node_input(layer_node, "Mask")
    source = _socket_source(mask)
    node = getattr(source, "node", None) if source is not None else None
    try:
        image = node.image if node is not None and node.type == "TEX_IMAGE" else None
        size = tuple(image.size) if image is not None else ()
    except ReferenceError:
        size = ()
    if len(size) < 2:
        return 0.0
    width = max(float(size[0]), 0.0)
    height = max(float(size[1]), 0.0)
    return width * height


def _configure_mask_diagnostic_node(context, state, diagnostic, mode):
    tree = state.node_tree
    if diagnostic.get("cp77MaskPreviewMode") != mode:
        diagnostic["cp77MaskPreviewMode"] = mode
    mask_input = node_input(state.layer_node, "Mask")
    _link_input(
        tree,
        diagnostic.inputs["Active Mask"],
        _socket_source(mask_input),
        _socket_default(mask_input, 1.0 if state.layer_index == 1 else 0.0),
    )
    if mode == "MASK":
        return
    value = _MASK_PREVIEW_MODES.get(mode, 0.0)
    if diagnostic.inputs["Mode"].default_value != value:
        diagnostic.inputs["Mode"].default_value = value
    layer_map = dict(
        linked_layer_states(context, obj=state.obj, material=state.material)
    )
    areas = {
        index: _mask_image_area(layer)
        for index, layer in layer_map.items()
        if index > 1
    }
    max_area = max(areas.values(), default=0.0)
    for index in range(2, 21):
        mask_input = node_input(layer_map.get(index), "Mask")
        _link_input(
            tree,
            diagnostic.inputs[f"Layer {index} Mask"],
            _socket_source(mask_input),
            _socket_default(mask_input, 0.0),
        )
        area = areas.get(index, 0.0)
        weight = area / max_area if area > 0.0 and max_area > 0.0 else 0.0
        target = diagnostic.inputs[f"Layer {index} Storage Weight"]
        if target.default_value != weight:
            target.default_value = weight


def mask_preview_mode(state):
    if state.node_tree is None:
        return "MASK"
    try:
        diagnostic = state.node_tree.nodes.get(VIEW_MASK_DIAGNOSTIC_NODE_NAME)
        mode = (
            str(diagnostic.get("cp77MaskPreviewMode", "MASK"))
            if diagnostic is not None
            else "MASK"
        )
    except ReferenceError:
        mode = "MASK"
    return mode if mode in _MASK_PREVIEW_MODES else "MASK"


def _preview_node(nodes, node_type, name, role, location):
    node = nodes.get(name)
    if node is None:
        node = nodes.new(type=node_type)
        node.name = name
        node.label = name
        node.location = location
        node[ROOT_ROLE_PROPERTY] = role
    return node


def _update_preview_state(owner, context, state, *, mask, mode):
    nodes = state.node_tree.nodes
    output_name = VIEW_MASK_NODE_NAME if mask else VIEW_TEMPLATE_OUTPUT_NAME
    output = nodes.get(output_name)
    already_active = output is not None and output.is_active_output
    try:
        if not already_active:
            if mask:
                _disable_template_preview(state, restore=True, remove=False)
            else:
                _disable_mask_preview(state, restore=True, remove=False)
            _remember_previous_output(state)
        output = _preview_node(
            nodes,
            "ShaderNodeOutputMaterial",
            output_name,
            VIEW_MASK_ROLE if mask else VIEW_TEMPLATE_OUTPUT_ROLE,
            (-100, 420),
        )
        if mask:
            shader = _preview_node(
                nodes,
                "ShaderNodeEmission",
                VIEW_MASK_SHADER_NAME,
                VIEW_MASK_SHADER_ROLE,
                (-360, 420),
            )
            if shader.inputs["Strength"].default_value != 1.0:
                shader.inputs["Strength"].default_value = 1.0
            diagnostic = _preview_node(
                nodes,
                "ShaderNodeGroup",
                VIEW_MASK_DIAGNOSTIC_NODE_NAME,
                VIEW_MASK_DIAGNOSTIC_ROLE,
                (-620, 420),
            )
            group = _mask_value_group() if mode == "MASK" else _mask_diagnostic_group()
            if diagnostic.node_tree != group:
                diagnostic.node_tree = group
            _configure_mask_diagnostic_node(context, state, diagnostic, mode)
            _link_input(
                state.node_tree, shader.inputs["Color"], diagnostic.outputs["Color"]
            )
            _link_input(
                state.node_tree, output.inputs["Surface"], shader.outputs["Emission"]
            )
        else:
            layer_bundle = state.layer_node.outputs.get("Layer")
            if layer_bundle is None:
                raise ValueError("The selected layer has no Layer output")
            preview = _preview_node(
                nodes,
                "ShaderNodeGroup",
                VIEW_TEMPLATE_NODE_NAME,
                VIEW_TEMPLATE_ROLE,
                (-420, 420),
            )
            group = _template_preview_group()
            if preview.node_tree != group:
                preview.node_tree = group
            _link_input(state.node_tree, preview.inputs["Layer"], layer_bundle)
            _link_input(
                state.node_tree, output.inputs["Surface"], preview.outputs["Shader"]
            )
        if not output.is_active_output:
            output.is_active_output = True
        return True
    except (
        AttributeError,
        ReferenceError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        log_once(
            _LOG,
            logging.DEBUG,
            "_update_preview_state",
            "_update_preview_state skipped what it could not read or write",
            exc_info=True,
        )
        if mask:
            _disable_mask_preview(state, restore=True)
        else:
            _disable_template_preview(state, restore=True)
        _restore_previous_output(state)
        report(
            owner,
            "WARNING",
            f"Could not update the material preview: {error}",
            logger=_LOG,
            error=error,
        )
        return False


_PREVIEW_SCOPE = "cp77MaterialToolsPreviewScope"


def _clear_shared_previews(active, keep=()):
    for material in bpy.data.materials:
        if material in keep:
            continue
        if material != active.material and not material.get(_PREVIEW_SCOPE):
            continue
        if not getattr(material, "is_editable", True):
            continue
        state = replace(active, material=material, node_tree=material.node_tree)
        if state.node_tree is not None:
            _disable_mask_preview(state, restore=True, remove=False)
            _disable_template_preview(state, restore=True, remove=False)
        if _PREVIEW_SCOPE in material:
            del material[_PREVIEW_SCOPE]


def set_shared_preview(owner, context, enabled=None, *, mask):
    if material_syncing():
        return False
    started = perf_counter()
    active = resolve_material_state(context)
    props = active.props
    property_name = (
        "multilayer_view_mask_bool" if mask else "multilayer_template_preview_bool"
    )
    enabled = bool(getattr(props, property_name, False) if enabled is None else enabled)
    targets = matching_template_states(context, active) if enabled else ()
    discovery_seconds = perf_counter() - started
    if enabled and not targets:
        report(
            owner,
            "WARNING",
            active.error_message or "No linked multilayer layer",
            logger=_LOG,
        )
    # One preview session follows the selected template as the artist changes layers.
    _clear_shared_previews(active, keep={state.material for state in targets})
    mode = str(getattr(props, "multilayer_mask_preview_mode_enum", "MASK"))
    success = not enabled or bool(targets)
    for state in targets:
        if not getattr(state.material, "is_editable", True):
            report(
                owner,
                "WARNING",
                f"Material {state.material.name} is read-only",
                logger=_LOG,
            )
            success = False
            break
        if not _update_preview_state(owner, context, state, mask=mask, mode=mode):
            success = False
            break
        scope = active.template_path or "active"
        if state.material.get(_PREVIEW_SCOPE) != scope:
            state.material[_PREVIEW_SCOPE] = scope
    if not success:
        _clear_shared_previews(active)
    if props is not None:
        with material_sync_guard():
            props.multilayer_view_mask_bool = bool(enabled and success and mask)
            props.multilayer_template_preview_bool = bool(
                enabled and success and not mask
            )
    _LOG.debug(
        "Multilayer preview: type=%s enabled=%s materials=%d discovery=%.3fs total=%.3fs success=%s",
        "mask" if mask else "template",
        enabled,
        len(targets),
        discovery_seconds,
        perf_counter() - started,
        success,
    )
    return success
