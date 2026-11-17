from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

from .multilayer import override_palette_batch_scope

_BULK_MATERIAL_IMPORT = ContextVar(
    "cp77_bulk_material_import",
    default=False,
)


def bulk_material_import_active() -> bool:
    return bool(_BULK_MATERIAL_IMPORT.get())


@contextmanager
def bulk_material_import_scope(enabled: bool = True, owner=None):
    if not enabled:
        if owner is None:
            yield False
            return

        with override_palette_batch_scope(owner):
            yield False
        return
    outermost = not bulk_material_import_active()
    token = _BULK_MATERIAL_IMPORT.set(True)
    try:
        if outermost:
            with override_palette_batch_scope(owner):
                yield True
        else:
            yield True
    finally:
        _BULK_MATERIAL_IMPORT.reset(token)
