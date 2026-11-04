from __future__ import annotations

from contextlib import contextmanager

_SUSPENDED = 0


@contextmanager
def suspended():
    global _SUSPENDED
    _SUSPENDED += 1
    try:
        yield
    finally:
        _SUSPENDED -= 1


def updates_suspended() -> bool:
    return _SUSPENDED > 0
