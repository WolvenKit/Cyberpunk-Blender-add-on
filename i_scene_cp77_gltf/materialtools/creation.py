import os
import shutil
import tempfile
from pathlib import Path

import bpy

from ..addon_identity import get_addon_preferences
from ..blender.transactions import (
    DatablockImportTransaction,
    current_import_transaction,
    new_tracked_datablock,
    rollback_report_message,
    track_mutation,
)
from ..importers.mesh import import_cyberpunk_glb, reload_materials
from .editor import synchronize_panel
from .masks import generate_mask_images
from .reporting import report_materialtools


def _atomic_copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(
        prefix=destination.name + ".",
        suffix=".tmp",
        dir=destination.parent,
    )
    os.close(handle)
    temp_path = Path(temp_name)
    try:
        shutil.copy2(source, temp_path)
        os.replace(temp_path, destination)
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass


def _restore_material_slots(mesh, materials, active_object, active_index):
    try:
        mesh.materials.clear()
        for material in materials:
            mesh.materials.append(material)
        active_object.active_material_index = active_index
    except (AttributeError, ReferenceError, RuntimeError, TypeError):
        pass


def _material_slots_match(mesh, materials, active_object, active_index):
    try:
        return (
            tuple(mesh.materials) == materials
            and int(active_object.active_material_index) == active_index
        )
    except (AttributeError, ReferenceError, TypeError, ValueError):
        return False


def _active_mesh(context):
    obj = getattr(context, "active_object", None)
    try:
        return obj if obj is not None and obj.type == "MESH" else None
    except (AttributeError, ReferenceError):
        return None


def create_multilayer_material(owner, context=None):
    context = context or bpy.context
    obj = _active_mesh(context)
    if obj is None:
        report_materialtools(owner, "ERROR", "Select a mesh object first.")
        return None
    prefs = get_addon_preferences(context)
    depot_value = str(getattr(prefs, "depotfolder_path", "") or "")
    depot = Path(bpy.path.abspath(depot_value)).expanduser()
    if depot_value in ("", "//MaterialDepot") or not depot.is_dir():
        report_materialtools(
            owner,
            "ERROR",
            "Set a valid Depot Path in the add-on preferences.",
        )
        return None
    resource_root = Path(__file__).resolve().parents[1] / "resources"
    resource_glb = resource_root / "all_multilayered_resources.glb"
    default_setup = resource_root / "default.mlsetup.json"
    material_json = resource_root / "all_multilayered_resources.Material.json"
    if not resource_glb.is_file() or not default_setup.is_file() or not material_json.is_file():
        report_materialtools(
            owner,
            "ERROR",
            "Bundled multilayer resources are missing.",
        )
        return None
    depot_setup = depot / "default.mlsetup.json"
    if not depot_setup.exists():
        try:
            _atomic_copy(default_setup, depot_setup)
        except OSError as error:
            report_materialtools(
                owner,
                "ERROR",
                f"Could not install default MLSETUP: {error}",
            )
            return None
    try:
        mesh = obj.data
        original_slots = tuple(mesh.materials)
        original_index = int(obj.active_material_index)
    except (AttributeError, ReferenceError, TypeError, ValueError):
        report_materialtools(owner, "ERROR", "The active mesh data is unavailable.")
        return None

    transaction = current_import_transaction()
    owns_transaction = transaction is None
    transaction = transaction or DatablockImportTransaction()
    savepoint = transaction.savepoint()
    scope = transaction.scope() if owns_transaction else None
    try:
        if scope is not None:
            scope.__enter__()
        track_mutation(
            ("materialtools_slots", id(mesh)),
            lambda mesh=mesh, materials=original_slots, obj=obj, index=original_index: _restore_material_slots(
                mesh,
                materials,
                obj,
                index,
            ),
            verify=lambda mesh=mesh, materials=original_slots, obj=obj, index=original_index: _material_slots_match(
                mesh,
                materials,
                obj,
                index,
            ),
            label=f"material slots {obj.name}",
        )
        dummy = new_tracked_datablock("materials", "Multilayer Default")
        dummy["MeshPath"] = str(resource_glb.with_suffix(""))
        dummy["DepotPath"] = str(depot)
        metadata = {
            "Name": "Multilayer Default",
            "BaseMaterial": "engine\\materials\\multilayered.mt",
            "GlobalNormal": "engine\\textures\\editor\\normal.xbm",
            "MultilayerMask": "default.mlmask",
            "DiffuseMap": "None",
        }
        dummy["m"] = metadata
        if mesh.materials:
            index = max(0, min(original_index, len(mesh.materials) - 1))
            mesh.materials[index] = dummy
            obj.active_material_index = index
        else:
            mesh.materials.append(dummy)
            obj.active_material_index = 0
        new_material = reload_materials(owner, context)
        if not hasattr(new_material, "node_tree"):
            raise RuntimeError("Material reload did not create a material")
        if getattr(obj, "active_material", None) is not new_material:
            raise RuntimeError("Material reload did not assign the created material")
        new_material["BaseMaterial"] = metadata["BaseMaterial"]
        new_material["DiffuseMap"] = metadata["DiffuseMap"]
        new_material["GlobalNormal"] = metadata["GlobalNormal"]
        new_material["MultilayerMask"] = metadata["MultilayerMask"]
        new_material["m"] = metadata
        new_material["MeshPath"] = ""
        new_material["ProjPath"] = ""
        synchronize_panel(context)
        if owns_transaction:
            transaction.commit()
        return new_material
    except Exception as error:
        report = (
            transaction.rollback()
            if owns_transaction
            else transaction.rollback_to(savepoint)
        )
        detail = rollback_report_message(report)
        message = (
            f"Could not create multilayer material: "
            f"{type(error).__name__}: {error}"
        )
        if detail:
            message += f"; rollback incomplete: {detail}"
        report_materialtools(owner, "ERROR", message)
        return None
    finally:
        if scope is not None:
            scope.__exit__(None, None, None)


def _created_mesh_objects(result):
    objects = []
    for item in getattr(result, "created_items", ()):
        if not isinstance(item, dict):
            continue
        for candidate in item.get("objects", ()):
            try:
                if candidate.type == "MESH" and candidate.active_material is not None:
                    objects.append(candidate)
            except (AttributeError, ReferenceError):
                continue
    return tuple(objects)


def _restore_selection(context, selected, active):
    for candidate in tuple(getattr(context, "selected_objects", ())):
        try:
            candidate.select_set(False)
        except (AttributeError, ReferenceError, RuntimeError):
            pass
    for candidate in selected:
        try:
            candidate.select_set(True)
        except (AttributeError, ReferenceError, RuntimeError):
            pass
    try:
        context.view_layer.objects.active = active
    except (AttributeError, ReferenceError, RuntimeError, TypeError):
        pass


def _selection_matches(context, selected, active):
    try:
        return (
            tuple(context.selected_objects) == tuple(selected)
            and context.view_layer.objects.active is active
        )
    except (AttributeError, ReferenceError, TypeError):
        return False


def _material_paths_match(material, mesh_existed, mesh_path, project_existed, project_path):
    try:
        return (
            ("MeshPath" in material) == mesh_existed
            and (not mesh_existed or material.get("MeshPath") == mesh_path)
            and ("ProjPath" in material) == project_existed
            and (not project_existed or material.get("ProjPath") == project_path)
        )
    except (AttributeError, ReferenceError, TypeError):
        return False


def create_multilayer_resource_object(owner, context=None, dimensions=1024):
    context = context or bpy.context
    resource_glb = (
        Path(__file__).resolve().parents[1]
        / "resources"
        / "all_multilayered_resources.glb"
    )
    if not resource_glb.is_file():
        report_materialtools(owner, "ERROR", "Bundled multilayer resources are missing.")
        return {"CANCELLED"}

    transaction = current_import_transaction()
    owns_transaction = transaction is None
    transaction = transaction or DatablockImportTransaction()
    savepoint = transaction.savepoint()
    scope = transaction.scope() if owns_transaction else None
    try:
        if scope is not None:
            scope.__enter__()
        result = import_cyberpunk_glb(
            with_materials=True,
            remap_depot=True,
            scripting=True,
            filepath=str(resource_glb),
        )
        if not result.ok:
            raise RuntimeError(
                "Resource import failed: " + "; ".join(result.failures)
            )
        obj = next(iter(_created_mesh_objects(result)), None)
        if obj is None:
            raise RuntimeError(
                "The resource import did not create a usable mesh object"
            )
        status = generate_mask_images(owner, context, dimensions, obj=obj)
        if "FINISHED" not in status:
            raise RuntimeError("Layer-mask generation was cancelled")
        try:
            material = obj.active_material
        except (AttributeError, ReferenceError):
            material = None
        if material is None:
            raise RuntimeError("The resource object has no active material")

        mesh_existed = "MeshPath" in material
        project_existed = "ProjPath" in material
        mesh_original = material.get("MeshPath")
        project_original = material.get("ProjPath")
        track_mutation(
            ("materialtools_resource_paths", id(material)),
            lambda material=material, mesh_existed=mesh_existed, mesh_original=mesh_original, project_existed=project_existed, project_original=project_original: _restore_material_paths(
                material,
                mesh_existed,
                mesh_original,
                project_existed,
                project_original,
            ),
            verify=lambda material=material, mesh_existed=mesh_existed, mesh_original=mesh_original, project_existed=project_existed, project_original=project_original: _material_paths_match(
                material,
                mesh_existed,
                mesh_original,
                project_existed,
                project_original,
            ),
            label=f"resource material paths {getattr(material, 'name', '')}",
        )
        material["MeshPath"] = ""
        material["ProjPath"] = ""

        previous_selected = tuple(getattr(context, "selected_objects", ()))
        previous_active = getattr(getattr(context, "view_layer", None), "objects", None)
        previous_active = getattr(previous_active, "active", None)
        track_mutation(
            ("materialtools_selection", id(context)),
            lambda context=context, selected=previous_selected, active=previous_active: _restore_selection(
                context,
                selected,
                active,
            ),
            verify=lambda context=context, selected=previous_selected, active=previous_active: _selection_matches(
                context,
                selected,
                active,
            ),
            label="MaterialTools selection",
        )
        _restore_selection(context, (obj,), obj)
        synchronize_panel(context)
        if owns_transaction:
            transaction.commit()
        return {"FINISHED"}
    except Exception as error:
        report = (
            transaction.rollback()
            if owns_transaction
            else transaction.rollback_to(savepoint)
        )
        detail = rollback_report_message(report)
        message = (
            f"Could not create multilayer resource object: "
            f"{type(error).__name__}: {error}"
        )
        if detail:
            message += f"; rollback incomplete: {detail}"
        report_materialtools(owner, "ERROR", message)
        return {"CANCELLED"}
    finally:
        if scope is not None:
            scope.__exit__(None, None, None)


def _restore_material_paths(material, mesh_existed, mesh_path, project_existed, project_path):
    try:
        if mesh_existed:
            material["MeshPath"] = mesh_path
        elif "MeshPath" in material:
            del material["MeshPath"]
        if project_existed:
            material["ProjPath"] = project_path
        elif "ProjPath" in material:
            del material["ProjPath"]
    except (AttributeError, ReferenceError, RuntimeError, TypeError):
        pass


def relocate_mesh_material(owner, context, filepath):
    obj = _active_mesh(context)
    try:
        material = obj.active_material if obj is not None else None
    except (AttributeError, ReferenceError):
        material = None
    if material is None:
        report_materialtools(owner, "ERROR", "The active object has no material.")
        return {"CANCELLED"}
    path = Path(bpy.path.abspath(str(filepath or ""))).expanduser()
    if path.suffix.casefold() != ".glb":
        report_materialtools(owner, "ERROR", "Select a GLB file.")
        return {"CANCELLED"}
    if not path.is_file():
        report_materialtools(owner, "ERROR", "The selected GLB file does not exist.")
        return {"CANCELLED"}
    parts = path.parts
    lowered = [part.casefold() for part in parts]
    raw_index = next(
        (
            index + 1
            for index in range(len(parts) - 1)
            if lowered[index] == "source" and lowered[index + 1] == "raw"
        ),
        None,
    )
    if raw_index is None:
        report_materialtools(
            owner,
            "ERROR",
            "The GLB must be inside a source/raw directory.",
        )
        return {"CANCELLED"}
    mesh_existed = "MeshPath" in material
    project_existed = "ProjPath" in material
    mesh_original = material.get("MeshPath")
    project_original = material.get("ProjPath")
    try:
        mesh_path = path.with_suffix("")
        project_raw = Path(*parts[: raw_index + 1])
        material["MeshPath"] = str(mesh_path)
        material["ProjPath"] = str(project_raw) + os.sep
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        _restore_material_paths(
            material,
            mesh_existed,
            mesh_original,
            project_existed,
            project_original,
        )
        report_materialtools(owner, "ERROR", f"Could not update material paths: {error}")
        return {"CANCELLED"}
    report_materialtools(owner, "INFO", f"Source file relocated to: {path}")
    return {"FINISHED"}
