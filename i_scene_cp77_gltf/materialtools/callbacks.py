import bpy
from bpy.app.handlers import persistent

from .palette import clear_palette_caches, override_enum_items
from .editor import (
    apply_color_to_shader,
    apply_microblend_to_shader,
    apply_override_to_shader,
    apply_template_to_shader,
    synchronize_panel,
    update_context_tracking,
)
from .masks import activate_selected_mask, set_view_mask_enabled
from .state import resolve_material_state
from .sync import material_sync_guard, material_syncing

_MSGBUS_OBJECT_OWNER = object()
_MSGBUS_COLOR_OWNER = object()
_MSGBUS_MATERIAL_OWNER = object()
_COLOR_TIMER_ACTIVE = False
_REFRESH_TIMER_ACTIVE = False


def _callback_warning(label, error):
    print(f"[CP77 MaterialTools] WARNING: {label} failed: {type(error).__name__}: {error}")


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
    props = getattr(getattr(context, "scene", None), "cp77_ml_props", None)
    view_mask_enabled = bool(
        getattr(props, "multilayer_view_mask_bool", False)
        if props is not None
        else False
    )
    _run_callback("panel synchronization", synchronize_panel, context)
    if view_mask_enabled:
        _run_callback(
            "view-mask layer refresh",
            set_view_mask_enabled,
            owner,
            context,
            True,
        )
    if getattr(context, "mode", "OBJECT") == "PAINT_TEXTURE":
        _run_callback("paint-mask layer refresh", activate_selected_mask, context)


def apply_mltemplate(owner, context):
    if material_syncing():
        return
    _run_callback("MLTemplate update", apply_template_to_shader, owner, context)


def apply_microblend_mlsetup(_owner, context):
    if material_syncing():
        return
    _run_callback("microblend update", apply_microblend_to_shader, context)


def apply_normalstr_ovrd(_owner, context):
    if material_syncing():
        return
    _run_callback("NormalStrength update", apply_override_to_shader, "normalstr", context=context)


def apply_metalin_ovrd(_owner, context):
    if material_syncing():
        return
    _run_callback("MetalLevelsIn update", apply_override_to_shader, "metalin", context=context)


def apply_metalout_ovrd(_owner, context):
    if material_syncing():
        return
    _run_callback("MetalLevelsOut update", apply_override_to_shader, "metalout", context=context)


def apply_roughin_ovrd(_owner, context):
    if material_syncing():
        return
    _run_callback("RoughLevelsIn update", apply_override_to_shader, "roughin", context=context)


def apply_roughout_ovrd(_owner, context):
    if material_syncing():
        return
    _run_callback("RoughLevelsOut update", apply_override_to_shader, "roughout", context=context)


def apply_view_mask(owner, context):
    if material_syncing():
        return
    _run_callback("view-mask update", set_view_mask_enabled, owner, context)


def apply_paint_mask(_owner, _context):
    return


def microblend_filter(_owner, image):
    context = getattr(bpy, "context", None)
    props = getattr(getattr(context, "scene", None), "cp77_ml_props", None)
    if props is None or not props.multilayer_microblend_filter_bool:
        return True
    try:
        return "microblend" in bpy.path.abspath(image.filepath).casefold()
    except (AttributeError, ReferenceError, TypeError):
        return False


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
    return None


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
    return None


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
    except (AttributeError, ReferenceError, TypeError, ValueError):
        return
    try:
        previous = tuple(props.last_palette_color)
    except (AttributeError, ReferenceError, TypeError):
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


@persistent
def load_pre_handler(_dummy):
    stop_timers()
    clear_palette_caches()
    clear_msgbus()


@persistent
def load_post_handler(_dummy):
    stop_timers()
    clear_palette_caches()
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
