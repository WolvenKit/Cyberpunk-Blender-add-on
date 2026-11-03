_HOOKS = {}


def register_helper_cache(name, *, clear, stats):
    _HOOKS[str(name)] = (clear, stats)


def clear_helper_caches():
    for clear, _stats in tuple(_HOOKS.values()):
        clear()


def helper_cache_stats():
    return {name: stats() for name, (_clear, stats) in tuple(_HOOKS.items())}
