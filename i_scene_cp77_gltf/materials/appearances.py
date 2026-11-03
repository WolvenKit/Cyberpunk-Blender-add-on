from __future__ import annotations


def normalize_material_appearances(appearances):
    """Remove WolvenKit's ordered disambiguation suffix once at the sidecar boundary"""
    if not isinstance(appearances, dict):
        raise ValueError("Material.json Appearances must be an object.")
    indexed = bool(appearances) and all(
        str(name).endswith(str(index)) and len(str(name)) > len(str(index))
        for index, name in enumerate(appearances)
    )
    normalized = {}
    for index, (name, materials) in enumerate(appearances.items()):
        name = str(name)
        if indexed:
            name = name[: -len(str(index))]
        if name in normalized:
            raise ValueError(f"Material.json contains duplicate appearance {name!r}.")
        if not isinstance(materials, (list, tuple)) or any(
            not isinstance(value, str) for value in materials
        ):
            raise ValueError(
                f"Appearance {name!r} must contain an array of material names."
            )
        normalized[name] = tuple(materials)
    return normalized
