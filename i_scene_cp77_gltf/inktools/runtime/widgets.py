from __future__ import annotations

import bpy
from bpy.app.handlers import persistent

from ...blender.identity import rna_is_live
from ..blender.hierarchy import is_screen_root

# The file's screen roots and the object count they were found at.
_ROOTS: list = [(), -1]


@persistent
def clear_screen_roots(_unused=None):
    _ROOTS[:] = ((), -1)


def screen_roots() -> tuple:
    """The file's objects that show a widget library"""
    roots, count = _ROOTS
    if count != len(bpy.data.objects) or not all(rna_is_live(root) for root in roots):
        roots = tuple(obj for obj in bpy.data.objects if is_screen_root(obj))
        _ROOTS[:] = (roots, len(bpy.data.objects))
    return roots
