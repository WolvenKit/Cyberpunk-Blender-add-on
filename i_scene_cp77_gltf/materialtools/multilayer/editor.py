import bpy

from ...assetio.values import coerce_float
from ...blender.identity import rna_identity
from ...blender.transactions import track_created_datablock
from ...core.log import debug_exception, get_logger, log_once
from ...core.notifications import report
from ...materials.blender.multilayer import sync_hidden_layer_links
from ..common.access import node_input
from ..common.constants import (
    ENUM_NONE,
    LAYER_EDITABLE_SOCKETS,
    LOCAL_LAYER_OWNER_PROPERTY,
    MATCH_TOLERANCE,
    OVERRIDE_ENUM_KEYS,
    OVERRIDE_SOCKET_NAMES,
    VIEW_MASK_NODE_NAME,
    VIEW_TEMPLATE_OUTPUT_NAME,
)
from ..common.sync import (
    material_sync_guard,
    material_syncing,
)
from ..depot.state import (
    ensure_material_depot_path,
    sync_palette_index,
)
from .overrides import ensure_palette_for_state
from .palette import (
    apply_override_vector,
    clear_palette_caches,
    find_matching_scalar,
    find_matching_vector,
    palette_values,
    parse_override_vector,
)
from .previews import mask_preview_mode
from .state import (
    active_palette,
    find_node_group_by_template,
    resolve_material_state,
    resolve_template_state,
)

_LOG = get_logger(__name__)

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
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_safe_active_color", type(error).__name__),
            "safe active color: fell back after %s",
            error,
            exc_info=True,
        )
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
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_set_palette", type(error).__name__),
            "set palette: fell back after %s",
            error,
            exc_info=True,
        )
        return False
    return True


def _set_props_context_flags(props, state):
    try:
        is_multilayer = (
            state.material is not None and state.material.get("MLSetup") is not None
        )
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_set_props_context_flags", type(error).__name__),
            "set props context flags: fell back after %s",
            error,
            exc_info=True,
        )
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
    except (AttributeError, ReferenceError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_set_active_palette_color 1", type(error).__name__),
            "set active palette color: fell back after %s",
            error,
            exc_info=True,
        )
        return False
    matched = None
    for color in tuple(colors):
        try:
            values = tuple(float(value) for value in color.color[:3])
        except (AttributeError, ReferenceError, TypeError, ValueError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_set_active_palette_color 2", type(error).__name__),
                "set active palette color: fell back after %s",
                error,
                exc_info=True,
            )
            continue
        if len(values) != len(target_values):
            continue
        if (
            max(
                (abs(a - b) for a, b in zip(values, target_values)),
                default=0.0,
            )
            < MATCH_TOLERANCE
        ):
            matched = color
            break
    if matched is None:
        return False
    try:
        colors.active = matched
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_set_active_palette_color 3", type(error).__name__),
            "set active palette color: fell back after %s",
            error,
            exc_info=True,
        )
        return False
    return True


def _material_identity(material):
    return str(rna_identity(material))


def _ensure_local_layer_runtime(state):
    if state is None or not state.valid_layer:
        return None
    try:
        source = state.layer_node.node_tree
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_ensure_local_layer_runtime 1", type(error).__name__),
            "ensure local layer runtime: fell back after %s",
            error,
            exc_info=True,
        )
        return None
    if source is None:
        return None
    owner_identity = _material_identity(state.material)
    try:
        if source.get(LOCAL_LAYER_OWNER_PROPERTY) == owner_identity:
            return source
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_ensure_local_layer_runtime 2", type(error).__name__),
            "ensure local layer runtime: fell back after %s",
            error,
            exc_info=True,
        )
    local = None
    try:
        local = track_created_datablock("node_groups", source.copy())
        local.name = f"{source.name} [{getattr(state.material, 'name', 'Material')}]"
        local[LOCAL_LAYER_OWNER_PROPERTY] = owner_identity
        state.layer_node.node_tree = local
        return local
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
            ("_ensure_local_layer_runtime 3", type(error).__name__),
            "ensure local layer runtime: fell back after %s",
            error,
            exc_info=True,
        )
        if local is not None:
            try:
                if local.users == 0:
                    bpy.data.node_groups.remove(local)
            except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
                log_once(
                    _LOG,
                    "DEBUG",
                    ("_ensure_local_layer_runtime 4", type(error).__name__),
                    "ensure local layer runtime: fell back after %s",
                    error,
                    exc_info=True,
                )
        return None


def _socket_value(layer_node, name, default=None):
    socket = node_input(layer_node, name)
    if socket is None:
        return default
    try:
        return socket.default_value
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_socket_value", type(error).__name__),
            "socket value: fell back after %s",
            error,
            exc_info=True,
        )
        return default


def _node_exists(node_tree, name):
    try:
        node = node_tree.nodes.get(name) if node_tree is not None else None
        return node is not None and bool(node.is_active_output)
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_node_exists", type(error).__name__),
            "node exists: fell back after %s",
            error,
            exc_info=True,
        )
        return False


def _set_override_property(props, name, value):
    try:
        setattr(props, name, value)
    except (AttributeError, ReferenceError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_set_override_property", type(error).__name__),
            "set override property: fell back after %s",
            error,
            exc_info=True,
        )


def _clear_layer_fields(props):
    props.multilayer_layergroup_string = ""
    props.multilayer_microblend_pointer = None
    props.multilayer_paint_mask_enable_bool = False
    props.multilayer_has_generated_overrides = False
    for prop_name in _OVERRIDE_PROPERTIES.values():
        _set_override_property(props, prop_name, ENUM_NONE)


def synchronize_panel(context):
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
        props.multilayer_template_preview_bool = _node_exists(
            state.node_tree,
            VIEW_TEMPLATE_OUTPUT_NAME,
        )
        if props.multilayer_view_mask_bool:
            props.multilayer_mask_preview_mode_enum = mask_preview_mode(state)
        props.multilayer_paint_mask_bool = False
        if not state.valid_layer:
            _clear_layer_fields(props)
            props.last_multilayer_index = state.layer_index
            return state

        try:
            props.multilayer_layergroup_string = state.layer_node.name
        except (AttributeError, ReferenceError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("synchronize_panel 1", type(error).__name__),
                "synchronize panel: fell back after %s",
                error,
                exc_info=True,
            )
            props.multilayer_layergroup_string = ""
        try:
            mask_image = state.mask_node.image if state.mask_node is not None else None
        except (AttributeError, ReferenceError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("synchronize_panel 2", type(error).__name__),
                "synchronize panel: fell back after %s",
                error,
                exc_info=True,
            )
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
        except (AttributeError, ReferenceError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("synchronize_panel 3", type(error).__name__),
                "synchronize panel: fell back after %s",
                error,
                exc_info=True,
            )
            props.multilayer_microblend_pointer = None
        palette = state.palette
        if template.template_path and (
            palette is None or "ColorScaleList" not in palette
        ):
            try:
                palette = ensure_palette_for_state(state)
            except Exception:
                debug_exception(
                    _LOG, "Could not find or create the palette for the panel"
                )
                palette = None
        if palette is None:
            props.multilayer_has_generated_overrides = bool(template.template_path)
            props.last_palette = None
            _set_palette(context, None)
            for prop_name in _OVERRIDE_PROPERTIES.values():
                _set_override_property(props, prop_name, ENUM_NONE)
            props.last_multilayer_index = state.layer_index
            return state

        props.multilayer_has_generated_overrides = False
        _set_palette(context, palette)
        sync_palette_index(props, palette)
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


def update_context_tracking(context):
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


def apply_color_to_shader(context):
    if material_syncing():
        return False
    state = resolve_material_state(context)
    palette = state.palette
    if palette is None:
        return False
    color = _safe_active_color(palette)
    if color is None:
        return False
    if not state.valid_layer:
        return False
    match = find_matching_vector(palette, "ColorScaleList", color, MATCH_TOLERANCE)
    if match is None:
        choices = palette_values(palette, "ColorScaleList")
        if choices:
            current = _socket_value(state.layer_node, "ColorScale", ())
            previous = find_matching_vector(
                palette, "ColorScaleList", current, MATCH_TOLERANCE
            )
            with material_sync_guard():
                palette.colors.active.color = parse_override_vector(
                    previous or choices[0]
                )[:3]
        return False
    color = parse_override_vector(match)[:3]
    socket = node_input(state.layer_node, "ColorScale")
    if socket is None:
        return False
    try:
        socket.default_value = (*color, 1.0)
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
            ("apply_color_to_shader", type(error).__name__),
            "apply color to shader: fell back after %s",
            error,
            exc_info=True,
        )
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
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_copy_default_value", type(error).__name__),
            "copy default value: fell back after %s",
            error,
            exc_info=True,
        )
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
            ("_restore_default_value", type(error).__name__),
            "restore default value: fell back after %s",
            error,
            exc_info=True,
        )


def apply_template_to_shader(owner, context, palette=None):
    if material_syncing():
        return {"FINISHED"}
    props = getattr(getattr(context, "scene", None), "cp77_ml_props", None)
    if props is None:
        return {"CANCELLED"}
    if palette is None:
        report(
            owner,
            "WARNING",
            "The selected multilayer palette no longer exists.",
            logger=_LOG,
        )
        return {"CANCELLED"}
    try:
        template_path = palette.get("MLTemplatePath")
    except (AttributeError, ReferenceError, TypeError) as exc:
        log_once(
            _LOG,
            "DEBUG",
            ("apply_template_to_shader 1", type(exc).__name__),
            "apply template to shader: fell back after %s",
            exc,
            exc_info=True,
        )
        template_path = None
    state = resolve_material_state(context)
    if state.valid_layer and _ensure_local_layer_runtime(state) is not None:
        state = resolve_material_state(context)
    template = resolve_template_state(state.layer_node)
    group = find_node_group_by_template(template_path)
    depot_root = ensure_material_depot_path(context, props)
    if group is None and state.valid_layer:
        try:
            from ...material_types.multilayered import Multilayered

            project_root = str(state.material.get("cp77_project_path", "") or "")
            runtime = Multilayered(depot_root, "png", project_root)
            group = runtime.ensure_template_group(template_path)
        except Exception as error:
            report(
                owner,
                "WARNING",
                f"The selected multilayer template could not be loaded: {error}",
                logger=_LOG,
                error=error,
            )
            return {"CANCELLED"}
    if not state.valid_layer or template.base_node is None:
        report(
            owner, "WARNING", state.error_message or template.error_message, logger=_LOG
        )
        return {"CANCELLED"}
    if group is None:
        report(
            owner,
            "WARNING",
            "The selected multilayer template did not produce a node group.",
            logger=_LOG,
        )
        return {"CANCELLED"}

    planned = {}
    snapshots = {}
    for kind, prop_name in _OVERRIDE_PROPERTIES.items():
        value = _first_palette_value(palette, OVERRIDE_ENUM_KEYS[kind])
        planned[kind] = (prop_name, value)
        if value is None:
            continue
        socket = node_input(state.layer_node, OVERRIDE_SOCKET_NAMES[kind])
        if socket is None:
            report(
                owner,
                "WARNING",
                f"The selected layer has no {OVERRIDE_SOCKET_NAMES[kind]} input.",
                logger=_LOG,
            )
            return {"CANCELLED"}
        snapshots[kind] = (socket, _copy_default_value(socket))
    color_socket = node_input(state.layer_node, "ColorScale")
    color_snapshot = _copy_default_value(color_socket)
    previous_palette = active_palette(context)
    try:
        previous_group = template.base_node.node_tree
    except (AttributeError, ReferenceError) as exc:
        log_once(
            _LOG,
            "DEBUG",
            ("apply_template_to_shader 2", type(exc).__name__),
            "apply template to shader: fell back after %s",
            exc,
            exc_info=True,
        )
        previous_group = None
    try:
        previous_template_path = state.layer_node.get("cp77_ml_template")
    except (AttributeError, ReferenceError, TypeError) as exc:
        log_once(
            _LOG,
            "DEBUG",
            ("apply_template_to_shader 3", type(exc).__name__),
            "apply template to shader: fell back after %s",
            exc,
            exc_info=True,
        )
        previous_template_path = None
    # A created material has no depot until one of its layers uses a template from the depot.
    records_depot = bool(depot_root) and not state.material.get("DepotPath")

    try:
        template.base_node.node_tree = group
        state.layer_node["cp77_ml_template"] = str(template_path)
        if records_depot:
            state.material["DepotPath"] = depot_root
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
            # The layer takes the template's default colour, or its first when the template names none.
            default_color = palette.get(
                "cp77_default_color_scale"
            ) or _first_palette_value(palette, "ColorScaleList")
            if default_color is not None:
                _set_active_palette_color(
                    palette, parse_override_vector(default_color)[:3]
                )
        if _safe_active_color(palette) is not None and not apply_color_to_shader(
            context
        ):
            raise RuntimeError("The palette colour could not be applied")
        synchronize_panel(context)
        return {"FINISHED"}
    except Exception as error:
        try:
            template.base_node.node_tree = previous_group
            if previous_template_path is None:
                state.layer_node.pop("cp77_ml_template", None)
            else:
                state.layer_node["cp77_ml_template"] = previous_template_path
            if records_depot:
                state.material["DepotPath"] = ""
        except (AttributeError, ReferenceError, RuntimeError, TypeError) as exc:
            log_once(
                _LOG,
                "DEBUG",
                ("apply_template_to_shader 4", type(exc).__name__),
                "apply template to shader: fell back after %s",
                exc,
                exc_info=True,
            )
        for socket, value in snapshots.values():
            _restore_default_value(socket, value)
        _restore_default_value(color_socket, color_snapshot)
        _set_palette(context, previous_palette)
        synchronize_panel(context)
        report(
            owner,
            "WARNING",
            f"The layer template could not be changed: {error}",
            logger=_LOG,
            error=error,
        )
        return {"CANCELLED"}


def apply_microblend_to_shader(context):
    if material_syncing():
        return False
    props = getattr(getattr(context, "scene", None), "cp77_ml_props", None)
    state = resolve_material_state(context)
    if state.valid_layer and _ensure_local_layer_runtime(state) is not None:
        state = resolve_material_state(context)
    template = resolve_template_state(state.layer_node)
    if props is None or template.microblend_node is None:
        return False
    try:
        template.microblend_node.image = props.multilayer_microblend_pointer
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("apply_microblend_to_shader", type(error).__name__),
            "apply microblend to shader: fell back after %s",
            error,
            exc_info=True,
        )
        return False
    return True


def apply_override_to_shader(
    kind,
    value=None,
    *,
    context,
    bypass_guard=False,
):
    if material_syncing() and not bypass_guard:
        return False
    if kind not in _OVERRIDE_PROPERTIES:
        return False
    props = getattr(getattr(context, "scene", None), "cp77_ml_props", None)
    if props is None:
        return False
    state = resolve_material_state(context)
    if not state.valid_layer:
        return False
    try:
        value = (
            value
            if value is not None
            else getattr(
                props,
                _OVERRIDE_PROPERTIES[kind],
            )
        )
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("apply_override_to_shader 1", type(error).__name__),
            "apply override to shader: fell back after %s",
            error,
            exc_info=True,
        )
        return False
    if value == ENUM_NONE or str(value) not in {
        str(item) for item in palette_values(state.palette, OVERRIDE_ENUM_KEYS[kind])
    }:
        return False
    socket_name = OVERRIDE_SOCKET_NAMES[kind]
    if kind == "normalstr":
        socket = node_input(state.layer_node, socket_name)
        if socket is None:
            return False
        try:
            socket.default_value = float(value)
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
                ("apply_override_to_shader 2", type(error).__name__),
                "apply override to shader: fell back after %s",
                error,
                exc_info=True,
            )
            return False
        return True
    try:
        return apply_override_vector(state.layer_node, socket_name, value)
    except (
        AttributeError,
        ReferenceError,
        RuntimeError,
        SyntaxError,
        TypeError,
        ValueError,
    ) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("apply_override_to_shader 3", type(error).__name__),
            "apply override to shader: fell back after %s",
            error,
            exc_info=True,
        )
        return False


def layer_opacity(context):
    value = _socket_value(resolve_material_state(context).layer_node, "Opacity")
    return coerce_float(value, 0.0, unwrap=False, finite=False)


def apply_layer_opacity(context, value):
    """Set the selected layer's opacity and mute or unmute its link into the surface to match"""
    state = resolve_material_state(context)
    socket = node_input(state.layer_node, "Opacity")
    if socket is None or state.root_node is None:
        return False
    try:
        socket.default_value = value
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
            ("apply_layer_opacity", type(error).__name__),
            "apply layer opacity: fell back after %s",
            error,
            exc_info=True,
        )
        return False
    sync_hidden_layer_links(state.node_tree, state.root_node)
    return True


def editable_layer_sockets(state):
    result = []
    missing = []
    for name, label in LAYER_EDITABLE_SOCKETS:
        socket = node_input(state.layer_node, name)
        if socket is None:
            missing.append(name)
        else:
            result.append((socket, label))
    return tuple(result), tuple(missing)


def reset_runtime_state():
    clear_palette_caches()
