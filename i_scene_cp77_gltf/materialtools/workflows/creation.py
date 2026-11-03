import copy
import os
from pathlib import Path

import bmesh
import bpy

from ...assetio.documents import load_json_payload
from ...assetio.index import IndexPolicy
from ...assetio.paths import LocalPath, split_source_tree_root
from ...assetio.resources import MULTILAYER_DEFAULT_SETUP, get_multilayer_defaults_dir
from ...bartmoss.scalar import clamp_scalar
from ...blender.operator_results import OperationResult
from ...blender.transactions import new_tracked_datablock, track_mutation, transactional
from ...core.log import get_logger, log_once
from ...core.notifications import report
from ...materials.blender.builder import MaterialBuilder
from ..application.options import (
    MATERIAL_TOOL_RESOURCE_EXTENSIONS,
    MaterialToolsRequest,
)
from ..application.session import MaterialToolsSession
from ..common.access import active_mesh
from ..common.constants import MAX_LAYERS
from ..multilayer.editor import synchronize_panel
from ..painting.masks import generate_mask_images

_LOG = get_logger(__name__)

# What the game's multilayered material instances reference beside their setup.
_BASE_MATERIAL = "engine\\materials\\multilayered.mt"
_DEFAULT_MASK = "engine\\materials\\defaults\\multilayer_default.mlmask"
_DEFAULT_NORMAL = "engine\\textures\\editor\\normal.xbm"


def _default_setup(path):
    """The game's default multilayer setup filled out to the most layers a material can have"""
    payload = load_json_payload(path)
    root = payload["Data"]["RootChunk"]
    first, second = root["layers"][:2]
    root["layers"] = [
        first,
        *(copy.deepcopy(second) for _index in range(MAX_LAYERS - 1)),
    ]
    return payload


def _default_material():
    """A multilayered material built from the game defaults the add-on bundles, never from the depot"""
    defaults = get_multilayer_defaults_dir()
    setup = os.path.join(defaults, *MULTILAYER_DEFAULT_SETUP.split("\\")) + ".json"
    raw_material = {
        "Name": "Multilayer Default",
        "BaseMaterial": _BASE_MATERIAL,
        "MaterialTemplate": _BASE_MATERIAL,
        "EnableMask": False,
        "Data": {
            "MultilayerSetup": MULTILAYER_DEFAULT_SETUP,
            "MultilayerMask": _DEFAULT_MASK,
            "GlobalNormal": _DEFAULT_NORMAL,
        },
    }
    request = MaterialToolsRequest(
        root=defaults,
        extensions=MATERIAL_TOOL_RESOURCE_EXTENSIONS,
        index_policy=IndexPolicy.REUSE,
    )
    with MaterialToolsSession(request) as session:
        # The build reads the filled-out setup in place of the bundled one.
        session.material_resources.provide(setup, _default_setup(setup))
        materials = (raw_material,)
        material = MaterialBuilder(materials, defaults, "png", "").create(
            materials, 0, force_rebuild=True
        )
    if material is None:
        raise RuntimeError("The bundled multilayer defaults did not produce a material")
    material["BaseMaterial"] = _BASE_MATERIAL
    material["GlobalNormal"] = _DEFAULT_NORMAL
    material["MultilayerMask"] = _DEFAULT_MASK
    # It has no setup of its own until one is exported, and no depot until its layers use the depot's templates.
    material["MLSetup"] = ""
    material["DepotPath"] = ""
    material["sourcePath"] = ""
    material["cp77_project_path"] = ""
    return material


def _restore_material_slot(obj, index, material, active_index):
    """Show the slot's material again, or remove the slot added to a mesh that had none"""
    try:
        if index is None:
            obj.data.materials.clear()
        else:
            obj.material_slots[index].material = material
        obj.active_material_index = active_index
    except (
        AttributeError,
        IndexError,
        ReferenceError,
        RuntimeError,
        TypeError,
    ) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_restore_material_slot", type(error).__name__),
            "restore material slot: fell back after %s",
            error,
            exc_info=True,
        )


def _material_slot_matches(obj, index, material, active_index):
    try:
        shown = (
            not obj.material_slots
            if index is None
            else obj.material_slots[index].material == material
        )
        return shown and int(obj.active_material_index) == active_index
    except (AttributeError, IndexError, ReferenceError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_material_slot_matches", type(error).__name__),
            "material slot matches: fell back after %s",
            error,
            exc_info=True,
        )
        return False


@transactional("Multilayer material creation")
def create_multilayer_material(context, dimensions=1024):
    """Give the active mesh's active slot a multilayer material built from the game defaults"""
    obj = active_mesh(context)
    if obj is None:
        return OperationResult.cancelled("Select a mesh object first.")

    try:
        mesh = obj.data
        slots = obj.material_slots
        original_index = int(obj.active_material_index)
        slot_index = (
            int(clamp_scalar(original_index, 0, len(slots) - 1)) if len(slots) else None
        )
        original_material = (
            slots[slot_index].material if slot_index is not None else None
        )
    except (AttributeError, IndexError, ReferenceError, TypeError, ValueError) as error:
        raise RuntimeError("The active mesh data is unavailable.") from error

    track_mutation(
        ("materialtools_slots", id(obj)),
        lambda obj=obj, index=slot_index, material=original_material, active=original_index: (
            _restore_material_slot(obj, index, material, active)
        ),
        verify=lambda obj=obj, index=slot_index, material=original_material, active=original_index: (
            _material_slot_matches(obj, index, material, active)
        ),
        label=f"material slots {obj.name}",
    )
    new_material = _default_material()
    if slot_index is None:
        mesh.materials.append(new_material)
        obj.active_material_index = 0
    else:
        # Set through the slot: a slot linked to the object (as an imported mesh's appearance slots are) shows
        # the object's material, not the mesh's.
        obj.material_slots[slot_index].material = new_material
        obj.active_material_index = slot_index
    synchronize_panel(context)
    masks = generate_mask_images(context, dimensions, obj=obj)
    if not masks.ok:
        return masks
    return OperationResult.finished(warnings=masks.warnings, material=new_material)


def _restore_selection(context, selected, active):
    for candidate in tuple(getattr(context, "selected_objects", ())):
        try:
            candidate.select_set(False)
        except (AttributeError, ReferenceError, RuntimeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_restore_selection 1", type(error).__name__),
                "restore selection: fell back after %s",
                error,
                exc_info=True,
            )
    for candidate in selected:
        try:
            candidate.select_set(True)
        except (AttributeError, ReferenceError, RuntimeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_restore_selection 2", type(error).__name__),
                "restore selection: fell back after %s",
                error,
                exc_info=True,
            )
    try:
        context.view_layer.objects.active = active
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_restore_selection 3", type(error).__name__),
            "restore selection: fell back after %s",
            error,
            exc_info=True,
        )


def _selection_matches(context, selected, active):
    try:
        return (
            tuple(context.selected_objects) == tuple(selected)
            and context.view_layer.objects.active is active
        )
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_selection_matches", type(error).__name__),
            "selection matches: fell back after %s",
            error,
            exc_info=True,
        )
        return False


def _sphere(context):
    """A smooth-shaded UV sphere at the 3D cursor, in the active collection"""
    mesh = new_tracked_datablock("meshes", "Multilayer Sphere")
    sphere = bmesh.new()
    try:
        sphere.loops.layers.uv.verify()
        bmesh.ops.create_uvsphere(
            sphere, u_segments=32, v_segments=16, radius=1.0, calc_uvs=True
        )
        sphere.to_mesh(mesh)
    finally:
        sphere.free()
    mesh.shade_smooth()
    obj = new_tracked_datablock("objects", "Multilayer Sphere", mesh)
    obj.location = context.scene.cursor.location
    context.collection.objects.link(obj)
    return obj


@transactional("Multilayer object creation")
def create_multilayer_object(context, dimensions=1024):
    """Add a smooth sphere with a multilayer material built from the game defaults"""
    previous_selected = tuple(getattr(context, "selected_objects", ()))
    previous_active = getattr(getattr(context, "view_layer", None), "objects", None)
    previous_active = getattr(previous_active, "active", None)
    track_mutation(
        ("materialtools_selection", id(context)),
        lambda context=context, selected=previous_selected, active=previous_active: (
            _restore_selection(
                context,
                selected,
                active,
            )
        ),
        verify=lambda context=context, selected=previous_selected, active=previous_active: (
            _selection_matches(
                context,
                selected,
                active,
            )
        ),
        label="MaterialTools selection",
    )
    obj = _sphere(context)
    _restore_selection(context, (obj,), obj)
    return create_multilayer_material(context, dimensions)


def _restore_material_paths(
    material, mesh_existed, mesh_path, project_existed, project_path
):
    try:
        if mesh_existed:
            material["sourcePath"] = mesh_path
        elif "sourcePath" in material:
            del material["sourcePath"]
        if project_existed:
            material["cp77_project_path"] = project_path
        elif "cp77_project_path" in material:
            del material["cp77_project_path"]
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_restore_material_paths", type(error).__name__),
            "restore material paths: fell back after %s",
            error,
            exc_info=True,
        )


def relocate_mesh_material(owner, context, filepath):
    obj = active_mesh(context)
    try:
        material = obj.active_material if obj is not None else None
    except (AttributeError, ReferenceError) as exc:
        log_once(
            _LOG,
            "DEBUG",
            ("relocate_mesh_material", type(exc).__name__),
            "relocate mesh material: fell back after %s",
            exc,
            exc_info=True,
        )
        material = None
    if material is None:
        report(owner, "ERROR", "The active object has no material.", logger=_LOG)
        return {"CANCELLED"}
    path = Path(
        LocalPath.from_value(bpy.path.abspath(str(filepath or ""))).value
    ).expanduser()
    if path.suffix.casefold() != ".glb":
        report(owner, "ERROR", "Select a GLB file.", logger=_LOG)
        return {"CANCELLED"}
    if not path.is_file():
        report(owner, "ERROR", "The selected GLB file does not exist.", logger=_LOG)
        return {"CANCELLED"}
    project_raw, source_relative = split_source_tree_root(str(path), "raw")
    if not project_raw or not source_relative:
        report(
            owner,
            "ERROR",
            "The GLB must be inside a source/raw directory.",
            logger=_LOG,
        )
        return {"CANCELLED"}
    mesh_existed = "sourcePath" in material
    project_existed = "cp77_project_path" in material
    mesh_original = material.get("sourcePath")
    project_original = material.get("cp77_project_path")
    try:
        mesh_path = path.with_suffix("")
        material["sourcePath"] = str(mesh_path)
        material["cp77_project_path"] = str(project_raw) + os.sep
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        _restore_material_paths(
            material,
            mesh_existed,
            mesh_original,
            project_existed,
            project_original,
        )
        report(
            owner,
            "ERROR",
            f"Could not update material paths: {error}",
            logger=_LOG,
            error=error,
        )
        return {"CANCELLED"}
    report(owner, "INFO", f"Source file relocated to: {path}", logger=_LOG)
    return {"FINISHED"}
