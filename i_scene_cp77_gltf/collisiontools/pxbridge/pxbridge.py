from .capability import initialize_physx_capability, require_bridge


def __getattr__(name):
    return getattr(require_bridge(), name)


def __dir__():
    capability = initialize_physx_capability()
    if capability.state.value != "AVAILABLE":
        return tuple(globals())
    return tuple(sorted(set(globals()) | set(dir(require_bridge()))))
