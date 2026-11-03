import os

from ..common.paths import norm_path_key

NON_VISUAL_MESH_COMPONENT_TYPES = frozenset({"entVisualControllerComponent"})
STATIC_OCCLUDER_COMPONENT_TYPES = frozenset({"entStaticOccluderMeshComponent"})
APPEARANCE_PROXY_COMPONENT_TYPES = frozenset({"entAppearanceProxyMeshComponent"})
LIGHT_COMPONENT_TYPES = frozenset({
    "entLightComponent",
    "vehicleLightComponent",
    "gameLightComponent",
})
LIGHT_CHANNEL_COMPONENT_TYPES = frozenset({"entLightChannelComponent"})
LIGHT_RELATED_COMPONENT_TYPES = (
    LIGHT_COMPONENT_TYPES | LIGHT_CHANNEL_COMPONENT_TYPES
)

STATIC_MESH_COMPONENT_TYPES = (
    frozenset({"entMeshComponent", "entPhysicalMeshComponent"})
    | STATIC_OCCLUDER_COMPONENT_TYPES
    | APPEARANCE_PROXY_COMPONENT_TYPES
)

SKINNED_MESH_COMPONENT_TYPES = frozenset(
    {
        "entSkinnedMeshComponent",
        "entPhysicalSkinnedMeshComponent",
        "entGarmentSkinnedMeshComponent",
        "entMorphTargetSkinnedMeshComponent",
    }
)

MESH_COMPONENT_TYPES = STATIC_MESH_COMPONENT_TYPES | SKINNED_MESH_COMPONENT_TYPES
ZERO_MASK_CULLED_COMPONENT_TYPES = frozenset(
    {
        "entMeshComponent",
        "entPhysicalMeshComponent",
        "entSkinnedMeshComponent",
        "entPhysicalSkinnedMeshComponent",
        "entGarmentSkinnedMeshComponent",
        "entMorphTargetSkinnedMeshComponent",
    }
)


def is_component_enabled(component) -> bool:
    return component.get("isEnabled", 1) != 0 if type(component) is dict else True


def chunk_mask_value(component) -> int | None:
    raw = component.get("chunkMask") if type(component) is dict else None
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def component_is_zero_mask_culled(component) -> bool:
    return (
        type(component) is dict
        and component.get("$type") in ZERO_MASK_CULLED_COMPONENT_TYPES
        and chunk_mask_value(component) == 0
    )


def is_excluded_mesh(
    depot_path: str,
    mesh_path: str,
    mesh_name: str,
    excluded_meshes,
) -> bool:
    if not excluded_meshes:
        return False
    if mesh_path and norm_path_key(mesh_path) in excluded_meshes:
        return True
    if mesh_name and norm_path_key(mesh_name) in excluded_meshes:
        return True
    if depot_path:
        if norm_path_key(depot_path) in excluded_meshes:
            return True
        basename = os.path.basename(depot_path.replace("\\", os.sep))
        if norm_path_key(basename) in excluded_meshes:
            return True
    return False
