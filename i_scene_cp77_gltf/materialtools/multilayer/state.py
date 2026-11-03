import bpy

from ...assetio.paths import depot_path_key
from ...assetio.values import coerce_int
from ...bartmoss.scalar import clamp_scalar
from ...core.log import get_logger, log_once
from ...materials.blender.multilayer import find_override_palette, linked_source
from ..application.model import (
    MaterialToolState,
    TemplateState,
)
from ..common.constants import (
    BASE_MATERIAL_ROLE,
    GROUP_INPUT_ROLE,
    LAYER_INTERNAL_ROLE_PROPERTY,
    MAX_LAYERS,
    MICROBLEND_ROLE,
    ROOT_NODE_NAME,
    ROOT_ROLE,
    ROOT_ROLE_PROPERTY,
)

_LOG = get_logger(__name__)


def active_palette(context):
    if context is None:
        return None
    tool_settings = getattr(context, "tool_settings", None)
    gpencil_paint = getattr(tool_settings, "gpencil_paint", None)
    try:
        return getattr(gpencil_paint, "palette", None)
    except ReferenceError:
        return None


def scene_props(context):
    scene = getattr(context, "scene", None) if context is not None else None
    try:
        return getattr(scene, "cp77_ml_props", None) if scene is not None else None
    except ReferenceError:
        return None


def id_property(owner, name, default=None):
    try:
        return owner.get(name, default) if owner is not None else default
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("id_property", type(error).__name__),
            "id property: fell back after %s",
            error,
            exc_info=True,
        )
        return default


def _find_root_node(node_tree):
    nodes = getattr(node_tree, "nodes", None) if node_tree is not None else None
    if nodes is None:
        return None
    for node in tuple(nodes):
        if id_property(node, ROOT_ROLE_PROPERTY) == ROOT_ROLE:
            return node
    try:
        node = nodes.get(ROOT_NODE_NAME)
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_find_root_node 1", type(error).__name__),
            "find root node: fell back after %s",
            error,
            exc_info=True,
        )
        node = None
    if node is not None:
        return node
    for node in tuple(nodes):
        try:
            inputs = getattr(node, "inputs", None)
            if inputs is not None and inputs.get("Layer 1") is not None:
                return node
        except (AttributeError, ReferenceError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_find_root_node 2", type(error).__name__),
                "find root node: fell back after %s",
                error,
                exc_info=True,
            )
            continue
    return None


def _safe_layer_index(value):
    return coerce_int(clamp_scalar(int(value), 1, MAX_LAYERS), 1, unwrap=False)


def resolve_material_state(context, layer_index=None, obj=None, material=None):
    errors = []
    scene = getattr(context, "scene", None) if context is not None else None
    props = scene_props(context)
    obj = obj or (
        getattr(context, "active_object", None) if context is not None else None
    )
    if obj is None:
        return MaterialToolState(
            context=context,
            scene=scene,
            props=props,
            errors=("No active object",),
        )
    try:
        object_type = obj.type
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("resolve_material_state 1", type(error).__name__),
            "resolve material state: fell back after %s",
            error,
            exc_info=True,
        )
        object_type = None
    if object_type != "MESH":
        return MaterialToolState(
            context=context,
            scene=scene,
            props=props,
            obj=obj,
            errors=("Active object is not a mesh",),
        )
    try:
        material = material if material is not None else obj.active_material
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("resolve_material_state 2", type(error).__name__),
            "resolve material state: fell back after %s",
            error,
            exc_info=True,
        )
        material = None
    if material is None:
        return MaterialToolState(
            context=context,
            scene=scene,
            props=props,
            obj=obj,
            errors=("Active object has no material",),
        )
    try:
        use_nodes = bool(material.use_nodes)
        node_tree = material.node_tree
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("resolve_material_state 3", type(error).__name__),
            "resolve material state: fell back after %s",
            error,
            exc_info=True,
        )
        use_nodes = False
        node_tree = None
    if not use_nodes or node_tree is None:
        errors.append("Active material has no editable node tree")
    if id_property(material, "MLSetup") is None:
        errors.append("Active material is not multilayered")
    root_node = _find_root_node(node_tree)
    if root_node is None:
        errors.append("Multilayer root node not found")
    requested_index = (
        layer_index
        if layer_index is not None
        else getattr(props, "multilayer_index_int", 1)
    )
    index = _safe_layer_index(requested_index)
    layer_socket = None
    layer_node = None
    mask_node = None
    if root_node is not None:
        try:
            inputs = root_node.inputs
            layer_socket = inputs.get(f"Layer {index}") if inputs is not None else None
        except (AttributeError, ReferenceError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("resolve_material_state 4", type(error).__name__),
                "resolve material state: fell back after %s",
                error,
                exc_info=True,
            )
            layer_socket = None
        if layer_socket is None:
            errors.append(f"Layer {index} socket not found")
        else:
            layer_node = linked_source(layer_socket)
            if layer_node is None:
                errors.append(f"Layer {index} is not linked")
            else:
                try:
                    inputs = layer_node.inputs
                    mask_socket = inputs.get("Mask") if inputs is not None else None
                except (AttributeError, ReferenceError, TypeError) as error:
                    log_once(
                        _LOG,
                        "DEBUG",
                        ("resolve_material_state 5", type(error).__name__),
                        "resolve material state: fell back after %s",
                        error,
                        exc_info=True,
                    )
                    mask_socket = None
                mask_node = linked_source(mask_socket)
    template_path = ""
    palette = None
    if layer_node is not None:
        template_state = resolve_template_state(layer_node)
        template_path = template_state.template_path
        if template_path:
            palette = find_override_palette(template_path)
    return MaterialToolState(
        context=context,
        scene=scene,
        props=props,
        obj=obj,
        material=material,
        node_tree=node_tree,
        root_node=root_node,
        layer_index=index,
        layer_socket=layer_socket,
        layer_node=layer_node,
        mask_node=mask_node,
        template_path=template_path,
        palette=palette,
        errors=tuple(errors),
    )


def _find_role_node(nodes, role, fallback_name=None):
    if nodes is None:
        return None
    for node in tuple(nodes):
        if id_property(node, LAYER_INTERNAL_ROLE_PROPERTY) == role:
            return node
    if not fallback_name:
        return None
    try:
        return nodes.get(fallback_name)
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_find_role_node", type(error).__name__),
            "find role node: fell back after %s",
            error,
            exc_info=True,
        )
        return None


def resolve_template_state(layer_node):
    if layer_node is None:
        return TemplateState(errors=("Layer node is unavailable",))
    try:
        layer_tree = layer_node.node_tree
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("resolve_template_state 1", type(error).__name__),
            "resolve template state: fell back after %s",
            error,
            exc_info=True,
        )
        layer_tree = None
    if layer_tree is None:
        return TemplateState(
            layer_node=layer_node,
            errors=("Layer node group datablock is missing",),
        )
    errors = []
    nodes = getattr(layer_tree, "nodes", None)
    base_node = _find_role_node(nodes, BASE_MATERIAL_ROLE, "Group")
    if base_node is None:
        errors.append("Layer base-material node not found")
    try:
        template_tree = base_node.node_tree if base_node is not None else None
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("resolve_template_state 2", type(error).__name__),
            "resolve template state: fell back after %s",
            error,
            exc_info=True,
        )
        template_tree = None
    if base_node is not None and template_tree is None:
        errors.append("Layer base-material datablock is missing")
    group_input = None
    template_path = ""
    if template_tree is not None:
        group_input = _find_role_node(
            getattr(template_tree, "nodes", None),
            GROUP_INPUT_ROLE,
            "Group Input",
        )
        if group_input is None:
            errors.append("Template group input node not found")
        else:
            template_path = str(
                id_property(
                    group_input,
                    "cp77_ml_template",
                    id_property(template_tree, "cp77_ml_template", ""),
                )
                or ""
            )
            if not template_path:
                errors.append("Template path metadata is missing")
    microblend_node = _find_role_node(nodes, MICROBLEND_ROLE, "Image Texture")
    return TemplateState(
        layer_node=layer_node,
        layer_tree=layer_tree,
        base_node=base_node,
        template_tree=template_tree,
        group_input=group_input,
        microblend_node=microblend_node,
        template_path=template_path,
        errors=tuple(errors),
    )


def find_node_group_by_template(template_path):
    normalized = depot_path_key(template_path)
    if not normalized:
        return None
    for group in tuple(getattr(bpy.data, "node_groups", ())):
        if depot_path_key(id_property(group, "cp77_ml_template", "")) == normalized:
            return group
    return None


def linked_layer_states(context, obj=None, material=None):
    base = resolve_material_state(
        context=context, layer_index=1, obj=obj, material=material
    )
    root = base.root_node
    if root is None:
        return ()
    try:
        inputs = root.inputs
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("linked_layer_states 1", type(error).__name__),
            "linked layer states: fell back after %s",
            error,
            exc_info=True,
        )
        return ()
    result = []
    for index in range(1, MAX_LAYERS + 1):
        try:
            socket = inputs.get(f"Layer {index}") if inputs is not None else None
        except (AttributeError, ReferenceError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("linked_layer_states 2", type(error).__name__),
                "linked layer states: fell back after %s",
                error,
                exc_info=True,
            )
            socket = None
        layer = linked_source(socket)
        if layer is not None:
            result.append((index, layer))
    return tuple(result)


def matching_template_states(context, active=None):
    active = active or resolve_material_state(context)
    if not active.valid_layer:
        return ()
    key = depot_path_key(active.template_path)
    if not key:
        return (active,)
    result = [active]
    for material in bpy.data.materials:
        if (
            material == active.material
            or not material.users
            or id_property(material, "MLSetup") is None
        ):
            continue
        layers = linked_layer_states(context, obj=active.obj, material=material)
        matches = [
            index
            for index, layer in layers
            if depot_path_key(resolve_template_state(layer).template_path) == key
        ]
        if not matches:
            continue
        index = active.layer_index if active.layer_index in matches else matches[0]
        state = resolve_material_state(
            context, layer_index=index, obj=active.obj, material=material
        )
        if state.valid_layer:
            result.append(state)
    return tuple(result)
