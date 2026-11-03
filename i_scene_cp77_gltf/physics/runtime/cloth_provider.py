_PROVIDER = None

_REQUIRED_PROVIDER_METHODS = (
    "apply_cloth_particles",
    "invalidate_cloth_object_cache",
    "mark_all_cloths_error",
    "prepare_cloth_step",
    "refresh_cloth_substep",
    "prepare_scene_cloths",
    "refresh_cloth_object_cache",
    "release_scene_cloths",
    "reset_scene_cloths",
    "restore_scene_cloths_for_rebuild",
    "set_active_cloth_state",
)


def register_cloth_runtime_provider(provider):
    global _PROVIDER
    if provider is None:
        raise ValueError("Cloth runtime provider is required")
    missing = tuple(
        name
        for name in _REQUIRED_PROVIDER_METHODS
        if not callable(getattr(provider, name, None))
    )
    if missing:
        raise TypeError(f"Cloth runtime provider is missing: {', '.join(missing)}")
    if _PROVIDER is not None and _PROVIDER is not provider:
        raise RuntimeError("A cloth runtime provider is already registered")
    _PROVIDER = provider


def unregister_cloth_runtime_provider(provider=None):
    global _PROVIDER
    if _PROVIDER is None:
        return
    if provider is not None and _PROVIDER is not provider:
        return
    _PROVIDER = None


def _call(name, *args, default=None, **kwargs):
    provider = _PROVIDER
    if provider is None:
        return default
    return getattr(provider, name)(*args, **kwargs)


def invalidate_cloth_object_cache():
    return _call("invalidate_cloth_object_cache")


def refresh_cloth_object_cache(context):
    return _call("refresh_cloth_object_cache", context)


def restore_scene_cloths_for_rebuild(context):
    return _call("restore_scene_cloths_for_rebuild", context, default=())


def release_scene_cloths(context, bridge):
    return _call("release_scene_cloths", context, bridge, default=())


def prepare_scene_cloths(context, bridge):
    return _call("prepare_scene_cloths", context, bridge, default=())


def reset_scene_cloths(context):
    return _call("reset_scene_cloths", context)


def mark_all_cloths_error(context, message):
    return _call("mark_all_cloths_error", context, message)


def prepare_cloth_step(context, bridge):
    return _call("prepare_cloth_step", context, bridge)


def refresh_cloth_substep(context, bridge):
    return _call("refresh_cloth_substep", context, bridge)


def apply_cloth_particles(context, bridge, *, tag_depsgraph=True):
    return _call(
        "apply_cloth_particles",
        context,
        bridge,
        tag_depsgraph=tag_depsgraph,
        default=0,
    )


def set_active_cloth_state(context, state, status):
    return _call("set_active_cloth_state", context, state, status)


def ensure_nvcloth_runtime(bridge):
    if not hasattr(bridge, "nvcloth_is_initialized") or not hasattr(
        bridge, "nvcloth_init"
    ):
        raise RuntimeError(
            "The selected native bridge does not expose NvCloth initialization"
        )
    if not bridge.nvcloth_is_initialized() and not bridge.nvcloth_init(False):
        raise RuntimeError("NvCloth initialization failed")


def restart_nvcloth_runtime(bridge):
    if not hasattr(bridge, "nvcloth_shutdown"):
        ensure_nvcloth_runtime(bridge)
        return
    bridge.nvcloth_shutdown()
    ensure_nvcloth_runtime(bridge)
