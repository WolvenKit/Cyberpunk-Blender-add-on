from __future__ import annotations

import bpy

from .common.results import ImportResult
from .entity.execution import import_entity
from .entity.options import EntityImportRequest
from .mesh.orchestration import import_cyberpunk_glb


def _appearance_tuple(appearances):
    if appearances is None:
        return ("default",)
    if isinstance(appearances, str):
        return (appearances or "default",)
    values = tuple(str(value) for value in appearances if str(value))
    return values or ("default",)


def _raise_on_failure(result: ImportResult) -> ImportResult:
    if result.failures:
        raise RuntimeError("; ".join(result.failures))
    return result


def import_glb_for_script(
    filepath,
    *,
    appearances=("default",),
    with_materials=False,
    image_format="png",
    hide_armatures=True,
    import_garmentsupport=True,
    import_tracks=True,
    animation_target="AUTO",
):
    context = bpy.context
    panel_props = getattr(context.scene, "cp77_panel_props", None)
    remap_depot = bool(getattr(panel_props, "remap_depot", False))
    result = import_cyberpunk_glb(
        with_materials=with_materials,
        remap_depot=remap_depot,
        image_format=image_format,
        filepath=str(filepath),
        hide_armatures=hide_armatures,
        import_garmentsupport=import_garmentsupport,
        appearances=_appearance_tuple(appearances),
        import_tracks=import_tracks,
        animation_target=animation_target,
    )
    return _raise_on_failure(result)


def import_entity_for_script(
    filepath,
    *,
    appearances=("default",),
    with_materials=False,
    parent_collection_name="",
    depot_root="",
    include_facial_setup=False,
):
    result = import_entity(
        EntityImportRequest(
            with_materials=with_materials,
            filepath=str(filepath),
            appearances=_appearance_tuple(appearances),
            parent_collection_name=parent_collection_name,
            depot_root=depot_root,
            include_facial_setup=include_facial_setup,
        )
    )
    return _raise_on_failure(result)
