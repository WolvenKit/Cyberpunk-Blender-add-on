from contextlib import contextmanager

_SYNC_DEPTH = 0


@contextmanager
def material_sync_guard():
    global _SYNC_DEPTH
    _SYNC_DEPTH += 1
    try:
        yield
    finally:
        _SYNC_DEPTH = max(0, _SYNC_DEPTH - 1)


def material_syncing():
    return _SYNC_DEPTH > 0
