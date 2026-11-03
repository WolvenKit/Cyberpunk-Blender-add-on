_HOOKS = {}


def register_helper_cache(name, *, clear, stats):
    _HOOKS[str(name)] = (clear, stats)


<<<<<<< Updated upstream
def unregister_helper_cache(name):
    _HOOKS.pop(str(name), None)


=======
>>>>>>> Stashed changes
def clear_helper_caches():
    for clear, _stats in tuple(_HOOKS.values()):
        clear()


def helper_cache_stats():
<<<<<<< Updated upstream
    return {
        name: stats()
        for name, (_clear, stats) in tuple(_HOOKS.items())
    }
=======
    return {name: stats() for name, (_clear, stats) in tuple(_HOOKS.items())}
>>>>>>> Stashed changes
