import bpy
from bpy.app.handlers import persistent

from ...core.log import get_logger, log_once
from ...materials.blender.cache import clear_material_cache
from ...materials.blender.images import clear_image_load_failures
from ..common.sync import (
    material_sync_guard,
    material_syncing,
)
from ..depot.state import clear_depot_state_cache
from ..multilayer.editor import (
    apply_color_to_shader,
    apply_layer_opacity,
    apply_microblend_to_shader,
    apply_override_to_shader,
    layer_opacity,
    synchronize_panel,
    update_context_tracking,
)
from ..multilayer.palette import (
    clear_palette_caches,
    override_enum_items,
)
from ..multilayer.previews import set_shared_preview
from ..multilayer.state import resolve_material_state
from ..painting.masks import (
    activate_selected_mask,
    toggle_texture_paint,
)

_LOG = get_logger(__name__)

_MSGBUS_OBJECT_OWNER = object()
_MSGBUS_COLOR_OWNER = object()
_MSGBUS_MATERIAL_OWNER = object()
_COLOR_TIMER_ACTIVE = False
_REFRESH_TIMER_ACTIVE = False


def _callback_warning(label, error):
    _LOG.warning(
        "%s failed: %s: %s",
        label,
        type(error).__name__,
        error,
        exc_info=(type(error), error, error.__traceback__),
        stacklevel=2,
    )


def _run_callback(label, callback, *args, default=None, **kwargs):
    try:
        return callback(*args, **kwargs)
    except Exception as error:
        _callback_warning(label, error)
        return default


def get_normalstr_ovrd(_owner, context):
    return _run_callback(
        "NormalStrength enum",
        override_enum_items,
        "normalstr",
        context,
        default=[("__CP77_NONE__", "Unavailable", "No override data")],
    )


def get_metalin_ovrd(_owner, context):
    return _run_callback(
        "MetalLevelsIn enum",
        override_enum_items,
        "metalin",
        context,
        default=[("__CP77_NONE__", "Unavailable", "No override data")],
    )


def get_metalout_ovrd(_owner, context):
    return _run_callback(
        "MetalLevelsOut enum",
        override_enum_items,
        "metalout",
        context,
        default=[("__CP77_NONE__", "Unavailable", "No override data")],
    )


def get_roughin_ovrd(_owner, context):
    return _run_callback(
        "RoughLevelsIn enum",
        override_enum_items,
        "roughin",
        context,
        default=[("__CP77_NONE__", "Unavailable", "No override data")],
    )


def get_roughout_ovrd(_owner, context):
    return _run_callback(
        "RoughLevelsOut enum",
        override_enum_items,
        "roughout",
        context,
        default=[("__CP77_NONE__", "Unavailable", "No override data")],
    )


def load_panel_data(owner, context):
    if material_syncing():
        return
    _run_callback("panel synchronization", synchronize_panel, context)
    props = getattr(getattr(context, "scene", None), "cp77_ml_props", None)
    if bool(getattr(props, "multilayer_view_mask_bool", False)):
        _run_callback(
            "view-mask layer refresh",
            set_shared_preview,
            owner,
            context,
            True,
            mask=True,
        )
    elif bool(getattr(props, "multilayer_template_preview_bool", False)):
        _run_callback(
            "MLTemplate preview layer refresh",
            set_shared_preview,
            owner,
            context,
            True,
            mask=False,
        )
    if getattr(context, "mode", "OBJECT") == "PAINT_TEXTURE":
        if not _run_callback(
            "paint-mask layer refresh", activate_selected_mask, context
        ):
            _run_callback("paint-mask exit", toggle_texture_paint, owner, context)


def get_layer_opacity(_owner):
    return _run_callback("layer opacity", layer_opacity, bpy.context, default=0.0)


def set_layer_opacity(_owner, value):
    _run_callback("layer opacity update", apply_layer_opacity, bpy.context, value)


def apply_microblend_mlsetup(_owner, context):
    if material_syncing():
        return
    _run_callback("microblend update", apply_microblend_to_shader, context)


def apply_normalstr_ovrd(_owner, context):
    if material_syncing():
        return
    _run_callback(
        "NormalStrength update", apply_override_to_shader, "normalstr", context=context
    )


def apply_metalin_ovrd(_owner, context):
    if material_syncing():
        return
    _run_callback(
        "MetalLevelsIn update", apply_override_to_shader, "metalin", context=context
    )


def apply_metalout_ovrd(_owner, context):
    if material_syncing():
        return
    _run_callback(
        "MetalLevelsOut update", apply_override_to_shader, "metalout", context=context
    )


def apply_roughin_ovrd(_owner, context):
    if material_syncing():
        return
    _run_callback(
        "RoughLevelsIn update", apply_override_to_shader, "roughin", context=context
    )


def apply_roughout_ovrd(_owner, context):
    if material_syncing():
        return
    _run_callback(
        "RoughLevelsOut update", apply_override_to_shader, "roughout", context=context
    )


def apply_view_mask(owner, context):
    if material_syncing():
        return
    _run_callback("view-mask update", set_shared_preview, owner, context, mask=True)


def apply_view_mask_mode(owner, context):
    if material_syncing():
        return
    props = getattr(getattr(context, "scene", None), "cp77_ml_props", None)
    if bool(getattr(props, "multilayer_view_mask_bool", False)):
        _run_callback(
            "view-mask mode update", set_shared_preview, owner, context, True, mask=True
        )


def apply_template_preview(owner, context):
    if material_syncing():
        return
    _run_callback(
        "MLTemplate preview update",
        set_shared_preview,
        owner,
        context,
        mask=False,
    )


def microblend_filter(_owner, image):
    try:
        filepath = bpy.path.abspath(image.filepath)
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("microblend_filter", type(error).__name__),
            "microblend filter: fell back after %s",
            error,
            exc_info=True,
        )
        return False
    return "microblend" in str(filepath or "").casefold()


def _schedule_color_update():
    global _COLOR_TIMER_ACTIVE
    if material_syncing() or _COLOR_TIMER_ACTIVE:
        return
    _COLOR_TIMER_ACTIVE = True
    try:
        bpy.app.timers.register(_apply_color_debounced, first_interval=0.1)
    except Exception as error:
        _COLOR_TIMER_ACTIVE = False
        _callback_warning("color timer registration", error)


def _apply_color_debounced():
    global _COLOR_TIMER_ACTIVE
    _COLOR_TIMER_ACTIVE = False
    _run_callback("color update", apply_color_to_shader, bpy.context)


def schedule_panel_refresh():
    global _REFRESH_TIMER_ACTIVE
    if _REFRESH_TIMER_ACTIVE:
        return
    _REFRESH_TIMER_ACTIVE = True
    try:
        bpy.app.timers.register(_refresh_debounced, first_interval=0.0)
    except Exception as error:
        _REFRESH_TIMER_ACTIVE = False
        _callback_warning("refresh timer registration", error)


def _refresh_debounced():
    global _REFRESH_TIMER_ACTIVE
    _REFRESH_TIMER_ACTIVE = False
    _run_callback("panel synchronization", synchronize_panel, bpy.context)


def color_changed_callback():
    if material_syncing():
        return
    context = getattr(bpy, "context", None)
    props = getattr(getattr(context, "scene", None), "cp77_ml_props", None)
    state = _run_callback("palette state", resolve_material_state, context)
    palette = getattr(state, "palette", None)
    colors = getattr(palette, "colors", None) if palette is not None else None
    active = getattr(colors, "active", None) if colors is not None else None
    if props is None or active is None:
        return
    try:
        color = tuple(float(value) for value in active.color[:3])
    except (AttributeError, ReferenceError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("color_changed_callback 1", type(error).__name__),
            "color changed callback: fell back after %s",
            error,
            exc_info=True,
        )
        return
    try:
        previous = tuple(props.last_palette_color)
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("color_changed_callback 2", type(error).__name__),
            "color changed callback: fell back after %s",
            error,
            exc_info=True,
        )
        previous = ()
    if color != previous:
        _schedule_color_update()
    with material_sync_guard():
        props.last_palette_color = color


def object_changed_callback():
    if material_syncing():
        return
    _run_callback("object-context update", update_context_tracking, bpy.context)
    schedule_panel_refresh()


def material_changed_callback():
    if material_syncing():
        return
    _run_callback("material-context update", update_context_tracking, bpy.context)
    schedule_panel_refresh()


def subscribe_to_color():
    bpy.msgbus.clear_by_owner(_MSGBUS_COLOR_OWNER)
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.PaletteColor, "color"),
        owner=_MSGBUS_COLOR_OWNER,
        args=(),
        notify=color_changed_callback,
    )


def subscribe_to_object():
    bpy.msgbus.clear_by_owner(_MSGBUS_OBJECT_OWNER)
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.LayerObjects, "active"),
        owner=_MSGBUS_OBJECT_OWNER,
        args=(),
        notify=object_changed_callback,
    )


def subscribe_to_material():
    bpy.msgbus.clear_by_owner(_MSGBUS_MATERIAL_OWNER)
    for key in (
        (bpy.types.Object, "active_material"),
        (bpy.types.Object, "active_material_index"),
    ):
        bpy.msgbus.subscribe_rna(
            key=key,
            owner=_MSGBUS_MATERIAL_OWNER,
            args=(),
            notify=material_changed_callback,
        )


def subscribe_all():
    clear_msgbus()
    try:
        subscribe_to_object()
        subscribe_to_color()
        subscribe_to_material()
    except Exception:
        clear_msgbus()
        raise


def clear_msgbus():
    bpy.msgbus.clear_by_owner(_MSGBUS_OBJECT_OWNER)
    bpy.msgbus.clear_by_owner(_MSGBUS_COLOR_OWNER)
    bpy.msgbus.clear_by_owner(_MSGBUS_MATERIAL_OWNER)


def stop_timers():
    global _COLOR_TIMER_ACTIVE, _REFRESH_TIMER_ACTIVE
    for callback in (_apply_color_debounced, _refresh_debounced):
        if bpy.app.timers.is_registered(callback):
            bpy.app.timers.unregister(callback)
    _COLOR_TIMER_ACTIVE = False
    _REFRESH_TIMER_ACTIVE = False


def clear_material_runtime_caches():
    from ..depot.thumbnails import clear_thumbnails
    from ..painting.surface import restore_surface_paint

    restore_surface_paint(bpy.context)
    clear_thumbnails()
    clear_material_cache(
        clear_persistent=False,
        reset_stats=False,
        clear_helpers=True,
    )
    clear_image_load_failures()


@persistent
def load_pre_handler(_dummy):
    stop_timers()
    clear_palette_caches()
    clear_depot_state_cache()
    clear_material_runtime_caches()
    clear_msgbus()


@persistent
def load_post_handler(_dummy):
    stop_timers()
    clear_palette_caches()
    clear_depot_state_cache()
    try:
        subscribe_all()
    except Exception as error:
        _callback_warning("message-bus resubscription", error)
    schedule_panel_refresh()


@persistent
def trigger_update_on_undo(scene):
    if scene is None or getattr(scene, "cp77_ml_props", None) is None:
        return
    schedule_panel_refresh()
