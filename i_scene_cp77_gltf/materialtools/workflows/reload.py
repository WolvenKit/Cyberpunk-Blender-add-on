import os

import bpy

from ...assetio.documents import DocumentSession
from ...blender.identity import rna_identity
from ...blender.transactions import (
    DatablockImportTransaction,
    current_import_transaction,
    raise_if_rollback_incomplete,
    track_mutation,
)
from ...material_types.multilayered import fresh_multilayer_runtime
from ...materials.blender.builder import MaterialBuilder
from ...materials.blender.images import DEFAULT_IMAGE_FORMAT
from ...materials.blender.metadata import apply_material_metadata, material_metadata
from ...materials.repository import MaterialRepository, MaterialResourceRepository
from ...materials.resources import material_resource_scope


def _material_user_slots(material):
    """Locate actual slot users through Blender's native datablock references"""
    direct = bpy.data.user_map(subset={material}).get(material, set())
    objects = {value for value in direct if isinstance(value, bpy.types.Object)}
    data_users = direct - objects
    if data_users:
        for owners in bpy.data.user_map(
            subset=data_users, value_types={"OBJECT"}
        ).values():
            objects.update(owners)
    return tuple(
        (obj, index, slot)
        for obj in sorted(objects, key=lambda value: value.name)
        for index, slot in enumerate(obj.material_slots)
        if slot.material is material
    )


class MaterialReloadError(RuntimeError):
    """The active material could not be rebuilt from its source"""


def reload_materials(context):
    """Rebuild the active object's active material from its source .Material.json"""
    active_obj = context.active_object
    active_material = active_obj.active_material if active_obj is not None else None
    if active_material is None:
        raise MaterialReloadError("No active material selected")

    orig_mat_name = str(
        active_material.get("cp77_source_material_name", active_material.name)
    )

    base_path = active_material.get("sourcePath")
    depot_path = active_material.get("DepotPath")
    project_path = active_material.get("cp77_project_path")
    if base_path is None and project_path:
        mesh_path = next(
            (
                collection.get("mesh")
                for collection in active_obj.users_collection
                if collection.get("mesh")
            ),
            None,
        )
        if mesh_path:
            base_path = os.path.join(project_path, mesh_path[: mesh_path.rfind(".")])
    if base_path is None:
        raise MaterialReloadError("Could not resolve material base path")

    material_path = base_path + ".Material.json"
    if not os.path.exists(material_path):
        raise MaterialReloadError("Material.json not found: " + material_path)

    owner = current_import_transaction()
    owns_transaction = owner is None
    owner = owner or DatablockImportTransaction()
    savepoint = owner.savepoint()
    scope = owner.scope() if owns_transaction else None
    if scope is not None:
        scope.__enter__()
    old_material = active_material
    slot_index = active_obj.active_material_index
    user_slots = _material_user_slots(old_material)
    if not user_slots:
        slot = active_obj.material_slots[slot_index]
        user_slots = ((active_obj, slot_index, slot),)
    try:
        for user_obj, user_index, user_slot in user_slots:
            track_mutation(
                ("material_slot", rna_identity(user_obj), user_index),
                lambda slot=user_slot, old_material=old_material: setattr(
                    slot,
                    "material",
                    old_material,
                ),
                verify=lambda slot=user_slot, old_material=old_material: (
                    slot.material is old_material
                ),
                label=f"material slot {user_obj.name}[{user_index}]",
            )
        with DocumentSession() as documents:
            bundle_repository = MaterialRepository(documents)
            material_resources = MaterialResourceRepository(documents)
            bundle = bundle_repository.load(material_path)
            if bundle is None:
                messages = [issue.message for issue in bundle_repository.issues]
                raise RuntimeError(
                    "; ".join(messages) or "Material bundle could not be loaded"
                )
            mats = list(bundle.materials)
            with material_resource_scope(material_resources):
                image_format = str(
                    active_material.get("cp77_image_format", "") or DEFAULT_IMAGE_FORMAT
                )
                builder = MaterialBuilder(None, depot_path, image_format, base_path)
                source_name = orig_mat_name
                source_index = next(
                    (
                        index
                        for index, raw_material in enumerate(mats)
                        if raw_material.get("Name") == source_name
                    ),
                    None,
                )
                if source_index is None:
                    source_name = orig_mat_name.rsplit(".", 1)[0]
                    source_index = next(
                        (
                            index
                            for index, raw_material in enumerate(mats)
                            if raw_material.get("Name") == source_name
                        ),
                        None,
                    )
                new_material = None
                source_raw_material = None
                if source_index is not None:
                    source_raw_material = mats[source_index]
                    with fresh_multilayer_runtime():
                        new_material = builder.create(
                            mats,
                            source_index,
                            force_rebuild=True,
                        )
                if new_material is None or source_raw_material is None:
                    raise RuntimeError(f"Source material '{source_name}' was not found")
                metadata = material_metadata(source_raw_material)
                if metadata is not None:
                    apply_material_metadata(new_material, metadata)
                for _user_obj, _user_index, user_slot in user_slots:
                    user_slot.material = new_material
        if owns_transaction:
            owner.commit()
    except Exception as error:
        report = owner.rollback() if owns_transaction else owner.rollback_to(savepoint)
        raise_if_rollback_incomplete(report, error, error_type=MaterialReloadError)
        raise MaterialReloadError(str(error)) from error
    finally:
        if scope is not None:
            scope.__exit__(None, None, None)

    return new_material
