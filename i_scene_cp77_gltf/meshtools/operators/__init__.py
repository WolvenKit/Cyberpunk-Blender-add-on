from .modelling import (
    CP77_OT_MirrorVertexGroups,
    CP77_OT_MirrorXAxis,
    CP77_OT_submesh_prep,
    CP77DeleteOrphanBones,
    CP77DeleteUnusedBones,
    CP77GarmentSupport,
    CP77RotateObj,
    CP77SafeJoin,
    CP77SafeSplit,
    CP77SetArmature,
)
from .presets import (
    CP77AddVertexcolorPreset,
    CP77ApplyVertexcolorPreset,
    CP77DeleteVertexcolorPreset,
)
from .refit import CP77Autofitter
from .uv import CP77UVCheckRemover, CP77UVDensity, CP77UVDensityRemover, CP77UVTool
from .validation import CP77_OT_FixGLBMeshes, CP77_OT_ValidateGLBMeshes
from .vertex_groups import CP77DeleteVertGroups, CP77GroupVerts, CP77WeightTransfer

MESH_OPERATOR_CLASSES = (
    CP77DeleteVertexcolorPreset,
    CP77AddVertexcolorPreset,
    CP77GarmentSupport,
    CP77SafeJoin,
    CP77SafeSplit,
    CP77WeightTransfer,
    CP77ApplyVertexcolorPreset,
    CP77GroupVerts,
    CP77DeleteVertGroups,
    CP77Autofitter,
    CP77UVTool,
    CP77UVCheckRemover,
    CP77UVDensity,
    CP77UVDensityRemover,
    CP77_OT_ValidateGLBMeshes,
    CP77_OT_FixGLBMeshes,
    CP77SetArmature,
    CP77_OT_submesh_prep,
    CP77RotateObj,
    CP77_OT_MirrorVertexGroups,
    CP77_OT_MirrorXAxis,
    CP77DeleteUnusedBones,
    CP77DeleteOrphanBones,
)
