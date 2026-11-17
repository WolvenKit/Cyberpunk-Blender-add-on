from __future__ import annotations

from contextlib import contextmanager

_SUSPENDED = 0
_SYNCING = 0


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


@contextmanager
def syncing():
    """Selection changes made by the tool itself"""
    global _SYNCING
    _SYNCING += 1
    try:
        yield
    finally:
        _SYNCING -= 1


def selection_syncing() -> bool:
    return _SYNCING > 0


def reset_syncing() -> None:
    global _SYNCING
    _SYNCING = 0
