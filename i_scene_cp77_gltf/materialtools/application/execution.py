from __future__ import annotations

import os

import bpy

from ...assetio.catalog import (
    IMAGE_EXTENSIONS,
    ResourceKind,
)
from ...assetio.index import IndexPolicy
from ...assetio.paths import LocalPath
from ...bartmoss.scalar import clamp_scalar
from ...core.log import debug_exception, get_logger
from ...material_types.vehicle_decal_dirt import prepare_vehicle_dirt_mesh
from ...materials.blender.builder import MaterialBuilder
from ...materials.blender.images import imageFromFilePath
from ...materials.blender.multilayer import cp77_create_palette
from ...materials.blender.nodes import createOverrideTable
from ..depot.paths import (
    game_path_from_local_path,
    infer_depot_root,
    relative_to_root,
    resolve_multilayer_template_json_path,
    template_defaults,
    template_game_path,
    template_name,
)
from .model import (
    MaterialDepotScanResult,
    MaterialTemplateBuildResult,
    MultilayerTemplateLoadResult,
)
from .options import (
    MATERIAL_TOOL_RESOURCE_EXTENSIONS,
    MULTILAYER_TEMPLATE_EXTENSION,
    MaterialToolsRequest,
)
from .session import MaterialToolsSession

_LOG = get_logger(__name__)


def _selected_mesh_objects(context):
    selected = []
    seen = set()
    for obj in getattr(context, "selected_objects", ()):
        if getattr(obj, "type", None) == "MESH" and id(obj) not in seen:
            selected.append(obj)
            seen.add(id(obj))
    active = getattr(context, "active_object", None)
    if getattr(active, "type", None) == "MESH" and id(active) not in seen:
        selected.append(active)
    return tuple(selected)


def _assign_material(obj, material):
    prepare_vehicle_dirt_mesh(obj, (material,))
    slots = obj.material_slots
    if not slots:
        obj.data.materials.append(material)
        obj.active_material_index = len(obj.material_slots) - 1
        return
    index = int(
        clamp_scalar(int(getattr(obj, "active_material_index", 0)), 0, len(slots) - 1)
    )
    slots[index].material = material
    obj.active_material_index = index


def _session_root_for_file(filepath, preferred_root=""):
    if preferred_root and os.path.isdir(preferred_root):
        return LocalPath.from_value(preferred_root).value
    inferred = infer_depot_root(filepath)
    if inferred and os.path.isdir(inferred):
        return LocalPath.from_value(inferred).value
    path = LocalPath.from_value(filepath).value
    return LocalPath.from_value(os.path.dirname(path)).value


def create_material_from_template(context, template_json, depot_root=""):
    session_root = _session_root_for_file(template_json, depot_root)
    request = MaterialToolsRequest(
        root=session_root,
        extensions=MATERIAL_TOOL_RESOURCE_EXTENSIONS,
        index_policy=IndexPolicy.REUSE,
    )
    with MaterialToolsSession(request) as session:
        document = session.material_resources.load(
            template_json,
            expected_kind=ResourceKind.MATERIAL_TEMPLATE,
            required=False,
        )
        if document is None:
            raise ValueError("The material template could not be loaded.")
        root = document.root
        if not isinstance(root, dict) or root.get("$type") != "CMaterialTemplate":
            raise ValueError("The selected file is not a CMaterialTemplate resource.")

        resolved_root = (
            LocalPath.from_value(depot_root).value
            if depot_root and os.path.isdir(depot_root)
            else session_root
        )
        template_path = template_game_path(
            template_json, document.payload, resolved_root
        )
        raw_material = {
            "Name": template_name(root, template_json),
            "BaseMaterial": template_path,
            "MaterialTemplate": template_path,
            "EnableMask": bool(root.get("canBeMasked", False)),
            "Data": template_defaults(root),
        }
        materials = (raw_material,)
        builder = MaterialBuilder(materials, resolved_root, "png", template_json)
        material = builder.create(materials, 0, force_rebuild=True)
        if material is None:
            raise RuntimeError(
                "The material template did not produce a Blender material."
            )
        material["BaseMaterial"] = template_path

        assigned = 0
        for obj in _selected_mesh_objects(context):
            try:
                _assign_material(obj, material)
                assigned += 1
            except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
                _LOG.warning(
                    "Could not assign %s to %s: %s",
                    material.name,
                    obj.name,
                    error,
                    exc_info=True,
                )
        if not assigned:
            material.use_fake_user = True

    return MaterialTemplateBuildResult(
        material=material,
        assigned_count=assigned,
        template_path=template_path,
        depot_root=resolved_root,
    )


def load_multilayer_template(filepath, depot_root=""):
    path = resolve_multilayer_template_json_path(filepath)
    session_root = _session_root_for_file(path, depot_root)
    request = MaterialToolsRequest(
        root=session_root,
        extensions=(),
        index_policy=IndexPolicy.REUSE,
    )
    with MaterialToolsSession(request) as session:
        document = session.material_resources.load(
            path,
            expected_kind=ResourceKind.MLTEMPLATE,
            required=False,
        )
        if document is None:
            raise ValueError("Multilayer template could not be loaded")
        template_path = relative_to_root(path, depot_root) if depot_root else ""
        if not template_path:
            template_path = game_path_from_local_path(path)
        override_table = createOverrideTable(document.root)
        palette = cp77_create_palette(template_path, override_table)
    return MultilayerTemplateLoadResult(
        palette=palette,
        template_path=template_path,
    )


def scan_material_depot(root):
    request = MaterialToolsRequest(
        root=root,
        extensions=(MULTILAYER_TEMPLATE_EXTENSION, *IMAGE_EXTENSIONS),
        index_policy=IndexPolicy.REFRESH,
        path_contains=tuple((suffix, "microblend") for suffix in IMAGE_EXTENSIONS),
    )
    failures = []
    loaded = 0
    first_palette = None
    microblends_loaded = 0
    microblends_existing = 0
    with MaterialToolsSession(request) as session:
        for path in session.files(MULTILAYER_TEMPLATE_EXTENSION):
            relative = relative_to_root(path, request.root)
            if not relative:
                failures.append(f"{path}: path is outside the selected material depot")
                continue
            template_path = relative
            try:
                document = session.material_resources.load(
                    path,
                    expected_kind=ResourceKind.MLTEMPLATE,
                    required=False,
                )
                if document is None:
                    raise ValueError("Multilayer template could not be loaded")
                override_table = createOverrideTable(document.root)
                palette = cp77_create_palette(template_path, override_table)
            except Exception as error:
                debug_exception(
                    _LOG, "Could not load the multilayer template %s", relative
                )
                failures.append(f"{relative}: {type(error).__name__}: {error}")
                continue
            loaded += 1
            if first_palette is None:
                first_palette = palette
        for path in session.files(*IMAGE_EXTENSIONS):
            try:
                before = len(bpy.data.images)
                imageFromFilePath(path, isNormal=True)
                if len(bpy.data.images) > before:
                    microblends_loaded += 1
                else:
                    microblends_existing += 1
            except Exception as error:
                debug_exception(_LOG, "Could not load the microblend %s", path)
                failures.append(f"{path}: {type(error).__name__}: {error}")
        collisions = len(session.collisions)
    return MaterialDepotScanResult(
        template_count=loaded,
        microblend_loaded_count=microblends_loaded,
        microblend_existing_count=microblends_existing,
        failures=tuple(failures),
        collision_count=collisions,
        first_palette=first_palette,
    )
