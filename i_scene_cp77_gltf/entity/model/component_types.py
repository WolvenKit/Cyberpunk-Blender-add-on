from __future__ import annotations

MESH_TYPES: dict[str, str] = {
    "MESH": "entMeshComponent",
    "SKINNED": "entSkinnedMeshComponent",
    "GARMENT": "entGarmentSkinnedMeshComponent",
    "PHYSICAL": "entPhysicalMeshComponent",
    "PHYSICAL_SKINNED": "entPhysicalSkinnedMeshComponent",
}

TYPE_LABELS: dict[str, str] = {
    "MESH": "Mesh",
    "SKINNED": "Skinned Mesh",
    "GARMENT": "Garment",
    "PHYSICAL": "Physical Mesh",
    "PHYSICAL_SKINNED": "Physical Skinned Mesh",
}

SKINNED_TYPES = frozenset({"SKINNED", "GARMENT", "PHYSICAL_SKINNED"})

_KEYS_BY_TYPE = {red_type: key for key, red_type in MESH_TYPES.items()}


def type_key(red_type: str) -> str | None:
    """The mesh type key of a component $type, or None for components that are not meshes"""
    return _KEYS_BY_TYPE.get(str(red_type or ""))
