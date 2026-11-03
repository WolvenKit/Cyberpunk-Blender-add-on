from __future__ import annotations

import bpy
from bpy.app.handlers import persistent

from ....blender.identity import rna_is_live

# The file's dangle rigs and the object count they were found at.
_RIGS: list = [(), -1]


@persistent
def clear_dangle_rigs(_unused=None):
    _RIGS[:] = ((), -1)


def dangle_rigs() -> tuple:
    """The file's armatures enabled as dangle rigs"""
    rigs, count = _RIGS
    if count != len(bpy.data.objects) or not all(rna_is_live(rig) for rig in rigs):
        rigs = tuple(
            obj
            for obj in bpy.data.objects
            if obj.type == "ARMATURE" and obj.dangle_state.is_dangle_rig
        )
        _RIGS[:] = (rigs, len(bpy.data.objects))
    return rigs
