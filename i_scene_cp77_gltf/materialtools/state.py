from dataclasses import dataclass

import bpy

from .constants import (
    BASE_MATERIAL_ROLE,
    GROUP_INPUT_ROLE,
    LAYER_INTERNAL_ROLE_PROPERTY,
    MAX_LAYERS,
    MICROBLEND_ROLE,
    ROOT_NODE_NAME,
    ROOT_ROLE,
    ROOT_ROLE_PROPERTY,
)


@dataclass(frozen=True, slots=True)
class MaterialToolState:
    context: object = None
    scene: object = None
    props: object = None
    obj: object = None
    material: object = None
    node_tree: object = None
    root_node: object = None
    layer_index: int = 1
    layer_socket: object = None
    layer_node: object = None
    mask_node: object = None
    template_path: str = ""
    palette: object = None
    errors: tuple = ()

    @property
    def valid_material(self):
        if self.obj is None or getattr(self.obj, "type", None) != "MESH":
            return False
        if self.material is None or self.node_tree is None or self.root_node is None:
            return False
        try:
            return (
                bool(getattr(self.material, "use_nodes", False))
                and self.material.get("MLSetup") is not None
            )
        except (AttributeError, ReferenceError, TypeError):
            return False

    @property
    def valid_layer(self):
        return (
            self.valid_material
            and self.layer_socket is not None
            and self.layer_node is not None
        )

    @property
    def error_message(self):
        return "; ".join(self.errors)


@dataclass(frozen=True, slots=True)
class TemplateState:
    layer_node: object = None
    layer_tree: object = None
    base_node: object = None
    template_tree: object = None
    group_input: object = None
    microblend_node: object = None
    template_path: str = ""
    errors: tuple = ()

    @property
    def valid(self):
        return not self.errors and self.base_node is not None and self.template_tree is not None

    @property
    def error_message(self):
        return "; ".join(self.errors)


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


def _safe_id_property(owner, name, default=None):
    try:
        return owner.get(name, default) if owner is not None else default
    except (AttributeError, ReferenceError, TypeError):
        return default


def _find_root_node(node_tree):
    nodes = getattr(node_tree, "nodes", None) if node_tree is not None else None
    if nodes is None:
        return None
    for node in tuple(nodes):
        if _safe_id_property(node, ROOT_ROLE_PROPERTY) == ROOT_ROLE:
            return node
    try:
        node = nodes.get(ROOT_NODE_NAME)
    except (AttributeError, ReferenceError, TypeError):
        node = None
    if node is not None:
        return node
    for node in tuple(nodes):
        try:
            inputs = getattr(node, "inputs", None)
            if inputs is not None and inputs.get("Layer 1") is not None:
                return node
        except (AttributeError, ReferenceError, TypeError):
            continue
    return None


def _linked_source(socket):
    if socket is None:
        return None
    try:
        if not socket.is_linked:
            return None
        links = tuple(socket.links)
    except (AttributeError, ReferenceError, TypeError):
        return None
    return getattr(links[0], "from_node", None) if links else None


def _safe_layer_index(value):
    try:
        return max(1, min(MAX_LAYERS, int(value)))
    except (TypeError, ValueError):
        return 1


def resolve_material_state(context=None, layer_index=None, obj=None):
    context = context or getattr(bpy, "context", None)
    errors = []
    scene = getattr(context, "scene", None) if context is not None else None
    props = scene_props(context)
    obj = obj or (getattr(context, "active_object", None) if context is not None else None)
    if obj is None:
        return MaterialToolState(
            context=context,
            scene=scene,
            props=props,
            errors=("No active object",),
        )
    try:
        object_type = obj.type
    except (AttributeError, ReferenceError):
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
        material = obj.active_material
    except (AttributeError, ReferenceError):
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
    except (AttributeError, ReferenceError):
        use_nodes = False
        node_tree = None
    if not use_nodes or node_tree is None:
        errors.append("Active material has no editable node tree")
    if _safe_id_property(material, "MLSetup") is None:
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
        except (AttributeError, ReferenceError, TypeError):
            layer_socket = None
        if layer_socket is None:
            errors.append(f"Layer {index} socket not found")
        else:
            layer_node = _linked_source(layer_socket)
            if layer_node is None:
                errors.append(f"Layer {index} is not linked")
            else:
                try:
                    inputs = layer_node.inputs
                    mask_socket = inputs.get("Mask") if inputs is not None else None
                except (AttributeError, ReferenceError, TypeError):
                    mask_socket = None
                mask_node = _linked_source(mask_socket)
    template_path = ""
    palette = None
    if layer_node is not None:
        template_state = resolve_template_state(layer_node)
        template_path = template_state.template_path
        if template_path:
            palette = find_palette_by_template(template_path)
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
        if _safe_id_property(node, LAYER_INTERNAL_ROLE_PROPERTY) == role:
            return node
    if not fallback_name:
        return None
    try:
        return nodes.get(fallback_name)
    except (AttributeError, ReferenceError, TypeError):
        return None


def resolve_template_state(layer_node):
    if layer_node is None:
        return TemplateState(errors=("Layer node is unavailable",))
    try:
        layer_tree = layer_node.node_tree
    except (AttributeError, ReferenceError):
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
    except (AttributeError, ReferenceError):
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
                _safe_id_property(
                    group_input,
                    "mlTemplate",
                    _safe_id_property(template_tree, "mlTemplate", ""),
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


def find_palette_by_template(template_path):
    normalized = normalize_depot_path(template_path)
    if not normalized:
        return None
    for palette in tuple(getattr(bpy.data, "palettes", ())):
        if normalize_depot_path(_safe_id_property(palette, "MLTemplatePath", "")) == normalized:
            return palette
    return None


def find_node_group_by_template(template_path):
    normalized = normalize_depot_path(template_path)
    if not normalized:
        return None
    for group in tuple(getattr(bpy.data, "node_groups", ())):
        if normalize_depot_path(_safe_id_property(group, "mlTemplate", "")) == normalized:
            return group
    return None


def normalize_depot_path(value):
    return str(value or "").strip().replace("/", "\\").casefold()


def linked_layer_states(context=None, obj=None):
    base = resolve_material_state(context=context, layer_index=1, obj=obj)
    root = base.root_node
    if root is None:
        return ()
    try:
        inputs = root.inputs
    except (AttributeError, ReferenceError):
        return ()
    result = []
    for index in range(1, MAX_LAYERS + 1):
        try:
            socket = inputs.get(f"Layer {index}") if inputs is not None else None
        except (AttributeError, ReferenceError, TypeError):
            socket = None
        layer = _linked_source(socket)
        if layer is not None:
            result.append((index, layer))
    return tuple(result)
