import bpy
<<<<<<< Updated upstream
=======
import numpy as np
>>>>>>> Stashed changes

from ...blender.context import (
    get_safe_mode,
    restore_previous_context,
    safe_mode_switch,
    store_current_context,
)
<<<<<<< Updated upstream
from ...blender.shapekeys import shape_key_names
from ..model import AutofitRequest, MeshToolResult
from ..refit_catalog import resolve_refitter
from .lattice_service import add_lattice
from .shapekey_service import (
    add_key_from_mix,
    apply_modifier_as_shapekey,
    copy_key_to_basis,
    ensure_basis,
    remove_key,
)


def apply_refitter(obj):
    """Apply refitter"""
    prev_mode = obj.mode
    if prev_mode != 'OBJECT':
        safe_mode_switch('OBJECT')

    try:
        basis = ensure_basis(obj)

        names = shape_key_names(obj) or []
        auto_names = [n for n in names if 'Autofitter' in n]
        garm_names = [n for n in names if 'Garment' in n]

        temp_mix_key = None
        if auto_names:
            auto_values = {n: 1.0 for n in auto_names}
            temp_mix_key = add_key_from_mix(obj, 'TempAutofitMix', values=auto_values)

        if garm_names:
            garm_values = {n: 1.0 for n in garm_names}
            gs_key = add_key_from_mix(obj, 'TempGarmentSupport', values=garm_values)
            for n in garm_names:
                remove_key(obj, n)
            if gs_key and gs_key.name != 'GarmentSupport':
                gs_key.name = 'GarmentSupport'
            if gs_key:
                gs_key.value = 0.0

        if temp_mix_key:
            copy_key_to_basis(obj, temp_mix_key.name)
            if basis:
                remove_key(obj, 'Basis')
            temp_mix_key.name = 'Basis'
        for n in auto_names:
            remove_key(obj, n)

    finally:
        if prev_mode != 'OBJECT':
            try:
                safe_mode_switch(prev_mode)
            except Exception:
                pass


def resolve_refit_selection(context):
    """Check for existing refitters."""
    refitters, addons = [], []
    for obj in context.scene.objects:
        if obj.type == 'LATTICE':
=======
from ...blender.operator_results import OperationResult
from ...blender.selection import selected_meshes
from ...blender.shapekeys import has_shape_keys
from ...core.log import get_logger
from ...gltf.garment_support import GARMENT_SUPPORT_MORPH
from ..model import AutofitRequest
from ..refit_catalog import resolve_refitter
from .lattice_service import add_lattice
from .shapekey_service import (
    apply_modifier_as_shapekey,
    key_coordinates,
    move_with_basis,
    rest_shape,
)

_LOG = get_logger(__name__)


def apply_refitter(obj):
    """Bake the Autofitter shape keys into the mesh"""
    prev_mode = obj.mode
    if prev_mode != "OBJECT":
        safe_mode_switch("OBJECT")

    try:
        if not has_shape_keys(obj):
            return
        shape_keys = obj.data.shape_keys
        reference = shape_keys.reference_key
        base = key_coordinates(reference)
        others = [key for key in shape_keys.key_blocks if key != reference]
        autofit = [key for key in others if "Autofitter" in key.name]
        garment = [
            key for key in others if "Garment" in key.name and key not in autofit
        ]

        refit = np.zeros_like(base)
        for key in autofit:
            refit += key_coordinates(key) - base
        support = None
        if garment:
            support = base.copy()
            for key in garment:
                support += key_coordinates(key) - base

        for key in (*autofit, *garment[1:]):
            obj.shape_key_remove(key)
        if garment:
            garment[0].data.foreach_set("co", support.reshape(-1))
            garment[0].name = GARMENT_SUPPORT_MORPH
            garment[0].value = 0.0
        move_with_basis(obj, refit)

    finally:
        if prev_mode != "OBJECT":
            try:
                safe_mode_switch(prev_mode)
            except Exception as error:
                _LOG.warning(
                    "Failed to restore refit mode: mode=%s error=%s",
                    prev_mode,
                    error,
                    exc_info=True,
                )


def _deform_before_armature(mesh, modifier):
    """Move a refit modifier ahead of the first Armature modifier"""
    modifiers = mesh.modifiers
    armature = next(
        (index for index, item in enumerate(modifiers) if item.type == "ARMATURE"), None
    )
    current = modifiers.find(modifier.name)
    if armature is not None and current > armature:
        modifiers.move(current, armature)


def resolve_refit_selection(context):
    """Check for existing refitters"""
    refitters, addons = [], []
    for obj in context.scene.objects:
        if obj.type == "LATTICE":
>>>>>>> Stashed changes
            if "refitter_type" in obj:
                refitters.append(obj)
            elif "refitter_addon" in obj or "refitter_addon_type" in obj:
                addons.append(obj)
<<<<<<< Updated upstream
    print(f'Refitters: {len(refitters)}, Addons: {len(addons)}')
=======
    _LOG.debug("Refit selection: refitters=%d addons=%d", len(refitters), len(addons))
>>>>>>> Stashed changes
    return refitters, addons


def run_autofit(context, request: AutofitRequest):
    try:
        target_body_path = resolve_refitter(request.base_choice)
<<<<<<< Updated upstream
    except KeyError:
        return MeshToolResult.failure(f"Base refitter '{request.base_choice}' was not found.")
=======
    except KeyError as error:
        return OperationResult.cancelled(
            f"Base refitter '{request.base_choice}' was not found.", error=error
        )
>>>>>>> Stashed changes

    addon_path = None
    addon_choice = request.addon_choice
    if request.use_addon:
        try:
            addon_path = resolve_refitter(addon_choice, addon=True)
<<<<<<< Updated upstream
        except KeyError:
            return MeshToolResult.failure(f"Addon refitter '{addon_choice}' was not found.")
=======
        except KeyError as error:
            return OperationResult.cancelled(
                f"Addon refitter '{addon_choice}' was not found.", error=error
            )
>>>>>>> Stashed changes

    refitters, addons = resolve_refit_selection(context)
    store_current_context()
    try:
        return _run_autofit(
            context=context,
            refitters=refitters,
            addons=addons,
            target_body_path=target_body_path,
            target_body_name=request.base_choice,
            use_addon=request.use_addon,
            addon_target_body_path=addon_path,
            addon_target_body_name=addon_choice,
            fbx_rotation=request.fbx_rotation,
            try_auto_apply=request.try_auto_apply,
        )
    finally:
        restore_previous_context()


def _run_autofit(
    context,
    refitters,
    addons,
    target_body_path,
    target_body_name,
    use_addon,
    addon_target_body_path,
    addon_target_body_name,
    fbx_rotation,
    try_auto_apply,
):
    if get_safe_mode() != "OBJECT":
        safe_mode_switch("OBJECT")
<<<<<<< Updated upstream
    selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
    if not selected:
        return MeshToolResult.failure("No meshes selected.")
=======
    selected = selected_meshes(context)
    if not selected:
        return OperationResult.cancelled("No meshes selected.")
>>>>>>> Stashed changes

    collection = context.scene.collection.children.get("Refitters")
    if collection is None:
        collection = bpy.data.collections.new("Refitters")
        context.scene.collection.children.link(collection)

    main_lattice = next(
        (obj for obj in refitters if obj.get("refitter_type") == target_body_name),
        None,
    )
    if main_lattice is None and target_body_name and target_body_name != "None":
        main_lattice = add_lattice(
<<<<<<< Updated upstream
            target_body_path, collection, fbx_rotation, target_body_name
=======
            context, target_body_path, collection, fbx_rotation, target_body_name
>>>>>>> Stashed changes
        )

    addon_lattice = None
    if use_addon:
        addon_lattice = next(
            (
<<<<<<< Updated upstream
                obj for obj in addons
=======
                obj
                for obj in addons
>>>>>>> Stashed changes
                if obj.get("refitter_addon_type") == addon_target_body_name
            ),
            None,
        )
        if addon_lattice is None and addon_target_body_path:
            addon_lattice = add_lattice(
<<<<<<< Updated upstream
=======
                context,
>>>>>>> Stashed changes
                addon_target_body_path,
                collection,
                fbx_rotation,
                addon_target_body_name,
            )
            if addon_lattice:
                addon_lattice["refitter_addon_type"] = addon_target_body_name

    modified = 0
<<<<<<< Updated upstream
    for mesh in selected:
=======
    refitted = set()
    for mesh in selected:
        if try_auto_apply and mesh.data.as_pointer() in refitted:
            # Its mesh, shared with an object selected before it, is already refitted.
            modified += 1
            continue
>>>>>>> Stashed changes
        added = []
        if main_lattice and not any(
            mod.type == "LATTICE" and mod.object == main_lattice
            for mod in mesh.modifiers
        ):
            modifier = mesh.modifiers.new(main_lattice.name, "LATTICE")
            modifier.object = main_lattice
<<<<<<< Updated upstream
=======
            _deform_before_armature(mesh, modifier)
>>>>>>> Stashed changes
            added.append(modifier.name)
        if addon_lattice and not any(
            mod.type == "LATTICE" and mod.object == addon_lattice
            for mod in mesh.modifiers
        ):
            modifier = mesh.modifiers.new(addon_lattice.name, "LATTICE")
            modifier.object = addon_lattice
<<<<<<< Updated upstream
=======
            _deform_before_armature(mesh, modifier)
>>>>>>> Stashed changes
            added.append(modifier.name)
        if not added:
            continue
        modified += 1
        if try_auto_apply:
<<<<<<< Updated upstream
            for modifier_name in added:
                apply_modifier_as_shapekey(mesh, modifier_name)
            apply_refitter(mesh)

    if modified == 0:
        return MeshToolResult.failure(
=======
            refitted.add(mesh.data.as_pointer())
            for modifier_name in added:
                with rest_shape(mesh):
                    apply_modifier_as_shapekey(context, mesh, modifier_name)
            apply_refitter(mesh)

    if modified == 0:
        return OperationResult.cancelled(
>>>>>>> Stashed changes
            "All selected meshes already have the requested refitter modifiers."
        )

    for obj in context.scene.objects:
        obj.select_set(False)
    for obj in selected:
        obj.select_set(True)
    context.view_layer.objects.active = selected[0]
<<<<<<< Updated upstream
    return MeshToolResult.success(f"Refitted {modified} mesh(es).", payload=modified)
=======
    return OperationResult.finished(f"Refitted {modified} mesh(es).", payload=modified)
>>>>>>> Stashed changes
