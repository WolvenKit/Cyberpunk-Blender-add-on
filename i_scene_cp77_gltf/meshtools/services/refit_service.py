import bpy

from ...blender.context import (
    get_safe_mode,
    restore_previous_context,
    safe_mode_switch,
    store_current_context,
)
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
            if "refitter_type" in obj:
                refitters.append(obj)
            elif "refitter_addon" in obj or "refitter_addon_type" in obj:
                addons.append(obj)
    print(f'Refitters: {len(refitters)}, Addons: {len(addons)}')
    return refitters, addons


def run_autofit(context, request: AutofitRequest):
    try:
        target_body_path = resolve_refitter(request.base_choice)
    except KeyError:
        return MeshToolResult.failure(f"Base refitter '{request.base_choice}' was not found.")

    addon_path = None
    addon_choice = request.addon_choice
    if request.use_addon:
        try:
            addon_path = resolve_refitter(addon_choice, addon=True)
        except KeyError:
            return MeshToolResult.failure(f"Addon refitter '{addon_choice}' was not found.")

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
    selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
    if not selected:
        return MeshToolResult.failure("No meshes selected.")

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
            target_body_path, collection, fbx_rotation, target_body_name
        )

    addon_lattice = None
    if use_addon:
        addon_lattice = next(
            (
                obj for obj in addons
                if obj.get("refitter_addon_type") == addon_target_body_name
            ),
            None,
        )
        if addon_lattice is None and addon_target_body_path:
            addon_lattice = add_lattice(
                addon_target_body_path,
                collection,
                fbx_rotation,
                addon_target_body_name,
            )
            if addon_lattice:
                addon_lattice["refitter_addon_type"] = addon_target_body_name

    modified = 0
    for mesh in selected:
        added = []
        if main_lattice and not any(
            mod.type == "LATTICE" and mod.object == main_lattice
            for mod in mesh.modifiers
        ):
            modifier = mesh.modifiers.new(main_lattice.name, "LATTICE")
            modifier.object = main_lattice
            added.append(modifier.name)
        if addon_lattice and not any(
            mod.type == "LATTICE" and mod.object == addon_lattice
            for mod in mesh.modifiers
        ):
            modifier = mesh.modifiers.new(addon_lattice.name, "LATTICE")
            modifier.object = addon_lattice
            added.append(modifier.name)
        if not added:
            continue
        modified += 1
        if try_auto_apply:
            for modifier_name in added:
                apply_modifier_as_shapekey(mesh, modifier_name)
            apply_refitter(mesh)

    if modified == 0:
        return MeshToolResult.failure(
            "All selected meshes already have the requested refitter modifiers."
        )

    for obj in context.scene.objects:
        obj.select_set(False)
    for obj in selected:
        obj.select_set(True)
    context.view_layer.objects.active = selected[0]
    return MeshToolResult.success(f"Refitted {modified} mesh(es).", payload=modified)
