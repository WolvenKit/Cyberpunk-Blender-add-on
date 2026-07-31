import bpy

from .constants import (
    ENUM_NONE,
    LAYER_EDITABLE_SOCKETS,
    MATCH_TOLERANCE,
    OVERRIDE_ENUM_KEYS,
    OVERRIDE_SOCKET_NAMES,
    VIEW_MASK_NODE_NAME,
    LOCAL_LAYER_OWNER_PROPERTY,
)
from .palette import (
    apply_override_vector,
    clear_palette_caches,
    find_matching_scalar,
    find_matching_vector,
    palette_values,
)
from .reporting import report_materialtools
from .overrides import ensure_palette_for_state
from .state import (
    active_palette,
    find_node_group_by_template,
    resolve_material_state,
    resolve_template_state,
)
from .sync import material_sync_guard, material_syncing
from ..blender.transactions import track_created_datablock

_OVERRIDE_PROPERTIES = {
    "normalstr": "multilayer_normalstr_enum",
    "metalin": "multilayer_metalin_enum",
    "metalout": "multilayer_metalout_enum",
    "roughin": "multilayer_roughin_enum",
    "roughout": "multilayer_roughout_enum",
}


def _safe_active_color(palette):
    try:
        colors = palette.colors if palette is not None else None
        active = colors.active if colors is not None else None
        color = active.color if active is not None else None
    except (AttributeError, ReferenceError):
        color = None
    if color is None:
        return None
    try:
        return tuple(float(value) for value in color[:3])
    except (TypeError, ValueError):
        return None


def _set_palette(context, palette):
    paint = getattr(getattr(context, "tool_settings", None), "gpencil_paint", None)
    if paint is None:
        return False
    try:
        paint.palette = palette
    except (AttributeError, ReferenceError, RuntimeError, TypeError):
        return False
    return True


def _set_props_context_flags(props, state):
    try:
        is_multilayer = (
            state.material is not None
            and state.material.get("MLSetup") is not None
        )
    except (AttributeError, ReferenceError, TypeError):
        is_multilayer = False
    props.multilayer_object_bool = bool(is_multilayer)
    props.last_active_object = state.obj
    props.last_active_material = state.material


def _set_active_palette_color(palette, target):
    if palette is None:
        return False
    try:
        target_values = tuple(float(value) for value in target)
        colors = palette.colors
    except (AttributeError, ReferenceError, TypeError, ValueError):
        return False
    matched = None
    for color in tuple(colors):
        try:
            values = tuple(float(value) for value in color.color[:3])
        except (AttributeError, ReferenceError, TypeError, ValueError):
            continue
        if len(values) != len(target_values):
            continue
        if max(
            (abs(a - b) for a, b in zip(values, target_values)),
            default=0.0,
        ) < MATCH_TOLERANCE:
            matched = color
            break
    if matched is None:
        return False
    try:
        colors.active = matched
    except (AttributeError, ReferenceError, RuntimeError, TypeError):
        return False
    return True


def _material_identity(material):
    try:
        pointer = int(material.as_pointer())
    except (AttributeError, ReferenceError, TypeError, ValueError):
        pointer = 0
    if pointer:
        return str(pointer)
    try:
        return str(material.name_full)
    except (AttributeError, ReferenceError, TypeError):
        return "material"


def _ensure_local_layer_runtime(state):
    if state is None or not state.valid_layer:
        return None
    try:
        source = state.layer_node.node_tree
    except (AttributeError, ReferenceError):
        return None
    if source is None:
        return None
    owner_identity = _material_identity(state.material)
    try:
        if source.get(LOCAL_LAYER_OWNER_PROPERTY) == owner_identity:
            return source
    except (AttributeError, ReferenceError, TypeError):
        pass
    local = None
    try:
        local = track_created_datablock("node_groups", source.copy())
        local.name = f"{source.name} [{getattr(state.material, 'name', 'Material')}]"
        local[LOCAL_LAYER_OWNER_PROPERTY] = owner_identity
        state.layer_node.node_tree = local
        return local
    except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
        if local is not None:
            try:
                if local.users == 0:
                    bpy.data.node_groups.remove(local)
            except (AttributeError, ReferenceError, RuntimeError, TypeError):
                pass
        return None


def _socket(layer_node, name):
    try:
        inputs = layer_node.inputs
        return inputs.get(name) if inputs is not None else None
    except (AttributeError, ReferenceError, TypeError):
        return None


def _socket_value(layer_node, name, default=None):
    socket = _socket(layer_node, name)
    if socket is None:
        return default
    try:
        return socket.default_value
    except (AttributeError, ReferenceError):
        return default


def _node_exists(node_tree, name):
    try:
        return node_tree is not None and node_tree.nodes.get(name) is not None
    except (AttributeError, ReferenceError, TypeError):
        return False


def _set_override_property(props, name, value):
    try:
        setattr(props, name, value)
    except (AttributeError, ReferenceError, TypeError, ValueError):
        pass


def _clear_layer_fields(props):
    props.multilayer_layergroup_string = ""
    props.multilayer_palette_string = ""
    props.multilayer_microblend_pointer = None
    props.multilayer_paint_mask_enable_bool = False
    props.multilayer_has_generated_overrides = False
    for prop_name in _OVERRIDE_PROPERTIES.values():
        _set_override_property(props, prop_name, ENUM_NONE)


def synchronize_panel(context=None):
    context = context or getattr(bpy, "context", None)
    props = getattr(getattr(context, "scene", None), "cp77_ml_props", None)
    if props is None:
        return None
    state = resolve_material_state(context)
    with material_sync_guard():
        _set_props_context_flags(props, state)
        props.multilayer_has_linked_layer = state.valid_layer
        props.multilayer_view_mask_bool = _node_exists(
            state.node_tree,
            VIEW_MASK_NODE_NAME,
        )
        props.multilayer_paint_mask_bool = False
        if not state.valid_layer:
            _clear_layer_fields(props)
            props.last_multilayer_index = state.layer_index
            return state

        try:
            props.multilayer_layergroup_string = state.layer_node.name
        except (AttributeError, ReferenceError):
            props.multilayer_layergroup_string = ""
        try:
            mask_image = state.mask_node.image if state.mask_node is not None else None
        except (AttributeError, ReferenceError):
            mask_image = None
        props.multilayer_paint_mask_enable_bool = mask_image is not None
        props.multilayer_paint_mask_bool = bool(
            getattr(context, "mode", "OBJECT") == "PAINT_TEXTURE"
            and mask_image is not None
        )

        template = resolve_template_state(state.layer_node)
        try:
            props.multilayer_microblend_pointer = (
                template.microblend_node.image
                if template.microblend_node is not None
                else None
            )
        except (AttributeError, ReferenceError):
            props.multilayer_microblend_pointer = None
        palette = state.palette
        if palette is None and template.template_path:
            try:
                palette = ensure_palette_for_state(state)
            except Exception:
                palette = None
        if palette is None:
            props.multilayer_has_generated_overrides = bool(template.template_path)
            props.multilayer_palette_string = ""
            props.last_palette = None
            _set_palette(context, None)
            for prop_name in _OVERRIDE_PROPERTIES.values():
                _set_override_property(props, prop_name, ENUM_NONE)
            props.last_multilayer_index = state.layer_index
            return state

        props.multilayer_has_generated_overrides = False
        _set_palette(context, palette)
        try:
            props.multilayer_palette_string = palette.name
        except (AttributeError, ReferenceError):
            props.multilayer_palette_string = ""
        colorscale = _socket_value(state.layer_node, "ColorScale")
        color_matched = (
            _set_active_palette_color(palette, tuple(colorscale[:3]))
            if colorscale is not None
            else False
        )
        scalar = _socket_value(state.layer_node, "NormalStrength")
        normal_match = (
            find_matching_scalar(
                palette,
                OVERRIDE_ENUM_KEYS["normalstr"],
                scalar,
                MATCH_TOLERANCE,
            )
            if scalar is not None
            else None
        )
        _set_override_property(
            props,
            _OVERRIDE_PROPERTIES["normalstr"],
            normal_match or ENUM_NONE,
        )
        for kind in ("metalin", "metalout", "roughin", "roughout"):
            value = _socket_value(state.layer_node, OVERRIDE_SOCKET_NAMES[kind])
            match = (
                find_matching_vector(
                    palette,
                    OVERRIDE_ENUM_KEYS[kind],
                    value,
                    MATCH_TOLERANCE,
                )
                if value is not None
                else None
            )
            _set_override_property(
                props,
                _OVERRIDE_PROPERTIES[kind],
                match or ENUM_NONE,
            )
        props.last_palette = palette
        color = _safe_active_color(palette)
        if color_matched and color is not None:
            props.last_palette_color = color
        props.last_multilayer_index = state.layer_index
        return state


def update_context_tracking(context=None):
    context = context or getattr(bpy, "context", None)
    props = getattr(getattr(context, "scene", None), "cp77_ml_props", None)
    if props is None:
        return
    state = resolve_material_state(context)
    with material_sync_guard():
        _set_props_context_flags(props, state)
        palette = state.palette
        props.last_palette = palette
        if palette is None:
            _set_palette(context, None)
        color = _safe_active_color(palette)
        if color is not None:
            props.last_palette_color = color
        if props.multilayer_object_bool:
            props.multilayer_index_int = 1
        props.last_multilayer_index = props.multilayer_index_int


def apply_color_to_shader(context=None):
    if material_syncing():
        return False
    context = context or getattr(bpy, "context", None)
    state = resolve_material_state(context)
    palette = state.palette
    if palette is None:
        return False
    color = _safe_active_color(palette)
    if color is None:
        return False
    if not state.valid_layer:
        return False
    socket = _socket(state.layer_node, "ColorScale")
    if socket is None:
        return False
    try:
        socket.default_value = (*color, 1.0)
    except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
        return False
    if state.props is not None:
        with material_sync_guard():
            state.props.last_palette_color = color
            state.props.last_palette = palette
    return True


def _first_palette_value(palette, key):
    values = palette_values(palette, key)
    return str(values[0]) if values else None


def _copy_default_value(socket):
    try:
        value = socket.default_value
    except (AttributeError, ReferenceError):
        return None
    try:
        return tuple(value)
    except TypeError:
        return value


def _restore_default_value(socket, value):
    if socket is None:
        return
    try:
        socket.default_value = value
    except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
        pass


def apply_template_to_shader(owner, context=None):
    if material_syncing():
        return {"FINISHED"}
    context = context or getattr(bpy, "context", None)
    props = getattr(getattr(context, "scene", None), "cp77_ml_props", None)
    if props is None:
        return {"CANCELLED"}
    try:
        palette = bpy.data.palettes.get(props.multilayer_palette_string)
    except (AttributeError, ReferenceError, TypeError):
        palette = None
    if palette is None:
        report_materialtools(
            owner,
            "WARNING",
            "The selected multilayer palette no longer exists.",
        )
        return {"CANCELLED"}
    try:
        template_path = palette.get("MLTemplatePath")
    except (AttributeError, ReferenceError, TypeError):
        template_path = None
    group = find_node_group_by_template(template_path)
    state = resolve_material_state(context)
    if state.valid_layer and _ensure_local_layer_runtime(state) is not None:
        state = resolve_material_state(context)
    template = resolve_template_state(state.layer_node)
    if not state.valid_layer or template.base_node is None:
        report_materialtools(
            owner,
            "WARNING",
            state.error_message or template.error_message,
        )
        return {"CANCELLED"}
    if group is None:
        report_materialtools(
            owner,
            "WARNING",
            "A node group matching the palette template path was not found.",
        )
        return {"CANCELLED"}

    planned = {}
    snapshots = {}
    for kind, prop_name in _OVERRIDE_PROPERTIES.items():
        value = _first_palette_value(palette, OVERRIDE_ENUM_KEYS[kind])
        planned[kind] = (prop_name, value)
        if value is None:
            continue
        socket = _socket(state.layer_node, OVERRIDE_SOCKET_NAMES[kind])
        if socket is None:
            report_materialtools(
                owner,
                "WARNING",
                f"The selected layer has no {OVERRIDE_SOCKET_NAMES[kind]} input.",
            )
            return {"CANCELLED"}
        snapshots[kind] = (socket, _copy_default_value(socket))
    color_socket = _socket(state.layer_node, "ColorScale")
    color_snapshot = _copy_default_value(color_socket)
    previous_palette = active_palette(context)
    try:
        previous_group = template.base_node.node_tree
    except (AttributeError, ReferenceError):
        previous_group = None

    try:
        template.base_node.node_tree = group
        if not _set_palette(context, palette):
            raise RuntimeError("The selected palette could not be activated")
        with material_sync_guard():
            props.last_palette = palette
            for kind, (prop_name, value) in planned.items():
                _set_override_property(props, prop_name, value or ENUM_NONE)
                if value is not None and not apply_override_to_shader(
                    kind,
                    value=value,
                    context=context,
                    bypass_guard=True,
                ):
                    raise RuntimeError(
                        f"The {OVERRIDE_SOCKET_NAMES[kind]} override could not be applied"
                    )
        if _safe_active_color(palette) is not None and not apply_color_to_shader(context):
            raise RuntimeError("The palette colour could not be applied")
        synchronize_panel(context)
        return {"FINISHED"}
    except Exception as error:
        try:
            template.base_node.node_tree = previous_group
        except (AttributeError, ReferenceError, RuntimeError, TypeError):
            pass
        for socket, value in snapshots.values():
            _restore_default_value(socket, value)
        _restore_default_value(color_socket, color_snapshot)
        _set_palette(context, previous_palette)
        synchronize_panel(context)
        report_materialtools(
            owner,
            "WARNING",
            f"The layer template could not be changed: {error}",
        )
        return {"CANCELLED"}


def apply_microblend_to_shader(context=None):
    if material_syncing():
        return False
    context = context or getattr(bpy, "context", None)
    props = getattr(getattr(context, "scene", None), "cp77_ml_props", None)
    state = resolve_material_state(context)
    if state.valid_layer and _ensure_local_layer_runtime(state) is not None:
        state = resolve_material_state(context)
    template = resolve_template_state(state.layer_node)
    if props is None or template.microblend_node is None:
        return False
    try:
        template.microblend_node.image = props.multilayer_microblend_pointer
    except (AttributeError, ReferenceError, RuntimeError, TypeError):
        return False
    return True


def apply_override_to_shader(
    kind,
    value=None,
    context=None,
    bypass_guard=False,
):
    if material_syncing() and not bypass_guard:
        return False
    if kind not in _OVERRIDE_PROPERTIES:
        return False
    context = context or getattr(bpy, "context", None)
    props = getattr(getattr(context, "scene", None), "cp77_ml_props", None)
    if props is None:
        return False
    state = resolve_material_state(context)
    if not state.valid_layer:
        return False
    try:
        value = value if value is not None else getattr(
            props,
            _OVERRIDE_PROPERTIES[kind],
        )
    except (AttributeError, ReferenceError):
        return False
    if value == ENUM_NONE:
        return False
    socket_name = OVERRIDE_SOCKET_NAMES[kind]
    if kind == "normalstr":
        socket = _socket(state.layer_node, socket_name)
        if socket is None:
            return False
        try:
            socket.default_value = float(value)
        except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
            return False
        return True
    try:
        return apply_override_vector(state.layer_node, socket_name, value)
    except (AttributeError, ReferenceError, RuntimeError, SyntaxError, TypeError, ValueError):
        return False


def editable_layer_sockets(state):
    result = []
    missing = []
    for name, label in LAYER_EDITABLE_SOCKETS:
        socket = _socket(state.layer_node, name)
        if socket is None:
            missing.append(name)
        else:
            result.append((socket, label))
    return tuple(result), tuple(missing)


def reset_runtime_state():
    clear_palette_caches()
