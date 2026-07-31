import json
import os
import re
import time
import traceback

import bpy

from ...addon_identity import get_addon_preferences
from .document import (
    import_mesh_glb,
    reset_shape_key_values,
)
from ..common.paths import absolute_path_key
from ..common.material_appearances import requested_material_names_by_submesh
from ..common.results import ImportResult, unique_messages
from ...blender.transactions import (
    DatablockImportTransaction,
    current_import_transaction,
    track_mutation,
    rollback_report_message,
)
from ...assetio.documents import DocumentSession
from ...materials.repository import MaterialRepository, MaterialResourceRepository
from ...materials.resources import material_resource_scope
from ...blender.mesh import uv_by_bounds
from ...notifications import show_message
from ...materials.blender.builder import MaterialBuilder
from ...materials.blender.cache import material_cache_counters, material_cache_stats, warm_material_cache_index
from ...redSpace.contracts import RIG_SPACE_CONTRACT_CURRENT
from ...blender.context import BlenderContextSnapshot


MATERIAL_PREPARATION_VERSION = 2


def _is_direct_animation_armature(obj):
    return (
        obj is not None
        and getattr(obj, "type", None) == "ARMATURE"
        and str(obj.data.get("cp77_rig_space_contract", ""))
        == RIG_SPACE_CONTRACT_CURRENT
    )


def _resolve_direct_animation_target(context, explicit_target=None):
    auto_target = explicit_target is None or explicit_target is True or explicit_target == "AUTO"
    target = None if auto_target else explicit_target
    if isinstance(target, str):
        target = bpy.data.objects.get(target)
    if _is_direct_animation_armature(target):
        return target
    if not auto_target:
        return None

    active = context.active_object
    if _is_direct_animation_armature(active):
        return active
    if active is not None and getattr(active, "type", None) == "MESH":
        for modifier in active.modifiers:
            if modifier.type == "ARMATURE" and _is_direct_animation_armature(modifier.object):
                return modifier.object

    selected = [
        obj
        for obj in context.selected_objects
        if _is_direct_animation_armature(obj)
    ]
    return selected[0] if len(selected) == 1 else None


def _try_direct_animation_import(
    filepath,
    context,
    animation_target,
    import_tracks,
    verbose,
):
    from ..animation import (
        UnsupportedDirectAnimation,
        import_anims_glb_to_armature,
    )

    direct_target = _resolve_direct_animation_target(context, animation_target)
    if direct_target is None:
        raise UnsupportedDirectAnimation(
            "Select a supported rig-import armature or a mesh bound to one "
            "before importing an .anims.glb file."
        )

    summary = import_anims_glb_to_armature(
        filepath,
        direct_target,
        import_tracks=import_tracks,
        verbose=verbose,
    )
    if verbose:
        target_kind = (
            "merged metarig"
            if direct_target.get("merged_rigs")
            or ";" in str(direct_target.data.get("source_rig_file", ""))
            else "rig"
        )
        print(
            f"[CP77 Direct Anim] Imported {summary['animation_count']} "
            f"animations directly onto {target_kind} {direct_target.name} in "
            f"{summary['elapsed_seconds']:.3f} seconds."
        )


def _load_file_entries(filepath, directory, files, scripting):
    if scripting or not files:
        if not filepath:
            return ()
        return ({"name": os.path.basename(filepath)},)
    return tuple(files)


def _entry_name(entry):
    name = getattr(entry, "name", None)
    return str(name if name is not None else entry["name"])


def _material_asset_stem(file_name):
    stem = os.path.splitext(os.path.basename(file_name))[0]
    return os.path.splitext(stem)[0]


def _normalize_json_apps(raw_apps):
    normalized = {}
    for index, (name, materials) in enumerate((raw_apps or {}).items()):
        key = str(name)
        suffix = str(index)
        if suffix and key.endswith(suffix):
            key = key[:-len(suffix)]
        normalized[key] = list(materials or ())
    return normalized


def _material_metadata(material_data):
    if "BaseMaterial" not in material_data:
        return None
    data = material_data.get("Data", {})
    return {
        "Name": material_data.get("Name", ""),
        "BaseMaterial": material_data["BaseMaterial"],
        "GlobalNormal": data.get("GlobalNormal", "None"),
        "MultilayerMask": data.get("MultilayerMask", "None"),
        "DiffuseMap": data.get(
            "DiffuseMap",
            data.get("BaseColor", data.get("DiffuseTexture", "None")),
        ),
    }


def _decoded_material_names(direct_result, mats):
    names = {
        str(name)
        for submesh in direct_result["mesh_data"].submeshes
        for name in submesh.material_names
        if name
    }
    if names:
        return names
    return {str(item.get("Name")) for item in mats or () if item.get("Name")}


def _source_material_names_by_submesh(direct_result):
    return tuple(
        str(submesh.material_names[0])
        if submesh.material_names and submesh.material_names[0]
        else ""
        for submesh in direct_result["mesh_data"].submeshes
    )


def _submesh_index_from_name(name, fallback_index=None):
    match = _SUBMESH_NAME_PATTERN.search(str(name or ""))
    if match:
        return int(match.group(1))
    return fallback_index


def _submesh_indices_by_import_order(direct_result):
    return tuple(
        _submesh_index_from_name(submesh.name, fallback_index)
        for fallback_index, submesh in enumerate(
            direct_result["mesh_data"].submeshes
        )
    )


def _requested_submesh_material_plan(direct_result, json_apps, appearances):
    return requested_material_names_by_submesh(
        json_apps,
        appearances,
        _source_material_names_by_submesh(direct_result),
        _submesh_indices_by_import_order(direct_result),
    )


def _material_records(mats, valid_names):
    records = {}
    for index, material_data in enumerate(mats or ()):
        name = material_data.get("Name")
        if not name or name not in valid_names:
            continue
        metadata = _material_metadata(material_data)
        if metadata is not None:
            records[name] = (index, metadata)
    return records


def _apply_material_metadata(material, metadata):
    material["m"] = metadata
    material["BaseMaterial"] = metadata["BaseMaterial"]
    material["GlobalNormal"] = metadata["GlobalNormal"]
    material["MultilayerMask"] = metadata["MultilayerMask"]
    material["DiffuseMap"] = metadata["DiffuseMap"]


def _unique_names(values):
    return tuple(dict.fromkeys(str(value) for value in values if value))


def import_mats(
    BasePath,
    DepotPath,
    exclude_unused_mats,
    direct_result,
    image_format,
    mats,
    validmatnames,
    *,
    material_names_by_submesh=None,
    is_morphtarget=False,
    log_timing=None,
):
    """Build requested materials once and attach only each submesh's candidates."""
    if log_timing is None:
        prefs = get_addon_preferences()
        verbose = not prefs.non_verbose
    else:
        verbose = bool(log_timing)
    start_time = time.time()
    failed = []
    records = _material_records(
        mats,
        set(validmatnames or ()),
    )
    builder = MaterialBuilder(
        mats,
        DepotPath,
        str(image_format),
        BasePath,
    )

    objects = direct_result["objects"]
    submeshes = direct_result["mesh_data"].submeshes
    if len(objects) != len(submeshes):
        raise RuntimeError(
            f"Direct mesh result mismatch: {len(objects)} objects "
            f"for {len(submeshes)} submeshes."
        )

    all_record_names = _unique_names(records)
    raw_plan = material_names_by_submesh
    if raw_plan is None:
        raw_plan = tuple(
            _unique_names(submesh.material_names)
            for submesh in submeshes
        )
    else:
        raw_plan = tuple(_unique_names(names) for names in raw_plan)
    if len(raw_plan) != len(submeshes):
        raise RuntimeError(
            f"Material plan mismatch: {len(raw_plan)} submesh plans "
            f"for {len(submeshes)} submeshes."
        )

    material_names_by_submesh = []
    required_names = []
    required_name_set = set()
    for raw_names, submesh in zip(raw_plan, submeshes):
        if is_morphtarget and not raw_names and not submesh.material_names:
            raw_names = all_record_names
        material_names = tuple(
            name
            for name in raw_names
            if name in records
        )
        material_names_by_submesh.append(material_names)
        for name in material_names:
            if name not in required_name_set:
                required_name_set.add(name)
                required_names.append(name)

    if not exclude_unused_mats:
        for name in records:
            if name not in required_name_set:
                required_name_set.add(name)
                required_names.append(name)

    built = {}
    for name in required_names:
        index, metadata = records[name]
        try:
            material = builder.create(mats, index)
            if material is None:
                continue
            _apply_material_metadata(material, metadata)
            built[name] = material
        except Exception:
            traceback.print_exc()
            failed.append(name)

    submesh_indices = _submesh_indices_by_import_order(direct_result)
    unprepared = []
    for obj, submesh_index, raw_names, material_names in zip(
        objects,
        submesh_indices,
        raw_plan,
        material_names_by_submesh,
    ):
        mesh = obj.data
        mesh.materials.clear()
        attached = []
        for name in material_names:
            material = built.get(name)
            if material is None:
                continue
            mesh.materials.append(material)
            attached.append(name)
            if material.get("no_shadows"):
                obj.visible_shadow = False
        obj["cp77_submesh_index"] = int(submesh_index)
        obj["cp77_requested_material_candidates"] = json.dumps(
            list(raw_names),
            separators=(",", ":"),
        )
        obj["cp77_material_candidates"] = json.dumps(
            attached,
            separators=(",", ":"),
        )
        attached_folded = {name.casefold() for name in attached if name}
        for name in raw_names:
            if name.casefold() not in attached_folded:
                unprepared.append((int(submesh_index), name))

    direct_result["collection"][
        "cp77_material_preparation_version"
    ] = MATERIAL_PREPARATION_VERSION
    direct_result["collection"][
        "cp77_material_submesh_indices"
    ] = json.dumps(list(submesh_indices), separators=(",", ":"))
    direct_result["collection"][
        "cp77_material_submesh_plan"
    ] = json.dumps(
        [list(names) for names in raw_plan],
        separators=(",", ":"),
    )

    if verbose:
        elapsed = time.time() - start_time
        if failed:
            print(
                "Material setup failed on:\n    "
                + "\n    ".join(dict.fromkeys(failed))
            )
            print(
                f"Attempted setup for {elapsed:.3f} seconds"
            )
        else:
            print(
                f"Shader setup completed successfully in "
                f"{elapsed:.3f} seconds"
            )
    return {
        "failures": tuple(dict.fromkeys(failed)),
        "unprepared": tuple(dict.fromkeys(unprepared)),
        "submeshIndices": submesh_indices,
    }


def _load_material_json(base_path, error_messages, materials):
    material_path = base_path + ".Material.json"
    if not os.path.exists(material_path):
        return None, {}, [], False
    bundle = materials.load(material_path)
    if bundle is None:
        error_messages.extend(
            issue.message for issue in materials.issues
            if issue.message not in error_messages
        )
        return None, {}, [], False
    return (
        bundle.depot_path,
        _normalize_json_apps(dict(bundle.appearances or {})),
        list(bundle.materials or ()),
        True,
    )


def _resolved_depot_path(depot_path, prefs, remap_depot, verbose):
    if remap_depot and os.path.exists(prefs.depotfolder_path):
        depot_path = prefs.depotfolder_path
        if verbose:
            print(f"Using depot path: {depot_path}")
    if depot_path is None:
        return None
    return str(depot_path).replace("\\", os.sep)


_SUBMESH_NAME_PATTERN = re.compile(r"submesh_(\d+)", re.IGNORECASE)


def _coverage_tokens(appearances):
    tokens = {
        str(value).casefold()
        for value in (appearances or ())
        if str(value)
    }
    if not tokens or "all" in tokens:
        return {"all"}
    return tokens


def _material_json_key(filepath):
    material_stem = _material_asset_stem(os.path.basename(filepath))
    base_path = os.path.join(os.path.dirname(filepath), material_stem)
    return absolute_path_key(base_path + ".Material.json")


def _coverage_values_satisfy(stored, requested):
    stored_values = {
        str(value).casefold()
        for value in (stored or ())
        if str(value)
    }
    if "all" in requested:
        return "all" in stored_values
    return requested.issubset(stored_values) or "all" in stored_values


def _existing_collection_coverage_satisfies(
        collection,
        filepath,
        appearances,
        ):
    try:
        version = int(
            collection.get("cp77_material_preparation_version", 0) or 0
        )
        raw = collection.get("cp77_material_coverage_sources", "")
    except (AttributeError, ReferenceError, TypeError, ValueError):
        return False
    if version < MATERIAL_PREPARATION_VERSION or not raw:
        return False
    try:
        sources = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    if not isinstance(sources, dict):
        return False
    stored = sources.get(_material_json_key(filepath), ())
    return _coverage_values_satisfy(stored, _coverage_tokens(appearances))


def _record_collection_material_coverage(collection, filepath, appearances):
    try:
        raw = collection.get("cp77_material_coverage_sources", "")
        sources = json.loads(raw) if raw else {}
    except (
        AttributeError,
        ReferenceError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        sources = {}
    if not isinstance(sources, dict):
        sources = {}
    key = _material_json_key(filepath)
    existing = {
        str(value).casefold()
        for value in sources.get(key, ())
        if str(value)
    }
    requested = _coverage_tokens(appearances)
    if "all" in existing or "all" in requested:
        sources[key] = ["all"]
    else:
        sources[key] = sorted(existing | requested)
    collection["cp77_material_coverage_sources"] = json.dumps(
        sources,
        separators=(",", ":"),
        sort_keys=True,
    )

def _existing_submesh_index(obj):
    try:
        explicit_index = int(obj.get("cp77_submesh_index", -1))
    except (AttributeError, ReferenceError, TypeError, ValueError):
        explicit_index = -1
    if explicit_index >= 0:
        return explicit_index
    match = _SUBMESH_NAME_PATTERN.search(str(getattr(obj, "name", "") or ""))
    if match:
        return int(match.group(1))
    return None


def _existing_material_name(material):
    if material is None:
        return ""
    try:
        metadata = material.get("m")
    except (AttributeError, ReferenceError, TypeError):
        metadata = None
    if metadata is not None:
        try:
            name = metadata.get("Name")
        except (AttributeError, TypeError):
            name = None
        if name:
            return str(name)
    return str(getattr(material, "name", "") or "")



def _existing_material_signature(material):
    if material is None:
        return ""
    try:
        return str(material.get("_cp77_material_signature", "") or "")
    except (AttributeError, ReferenceError, TypeError):
        return ""


def _attach_source_local_material(obj, name, material):
    """Attach one source-local material without creating a name ambiguity."""
    expected_name = str(name).casefold()
    expected_signature = _existing_material_signature(material)
    same_name_index = None
    for index, existing in enumerate(obj.data.materials):
        if existing is None:
            continue
        if existing is material:
            return False
        existing_signature = _existing_material_signature(existing)
        if (
            expected_signature
            and existing_signature == expected_signature
        ):
            return False
        if _existing_material_name(existing).casefold() == expected_name:
            if same_name_index is None:
                same_name_index = index
            else:
                # Preserve the existing list for diagnostics rather than
                # silently selecting between multiple same-name candidates.
                same_name_index = -1
    if same_name_index is not None and same_name_index >= 0:
        obj.data.materials[same_name_index] = material
        return True
    obj.data.materials.append(material)
    return True

def ensure_collection_material_coverage(
        collection,
        filepath,
        appearances,
        *,
        remap_depot=False,
        image_format="png",
        document_session=None,
        material_resources=None,
        ):
    """Append missing requested-appearance materials to a reused mesh master."""
    if collection is None or _existing_collection_coverage_satisfies(
            collection,
            filepath,
            appearances,
            ):
        return {"updated": False, "reason": "covered"}

    mesh_objects = {}
    for obj in tuple(getattr(collection, "all_objects", ()) or ()):
        if getattr(obj, "type", None) != "MESH" or not getattr(obj, "data", None):
            continue
        index = _existing_submesh_index(obj)
        if index is not None:
            mesh_objects[index] = obj
    if not mesh_objects:
        return {"updated": False, "reason": "no_submeshes"}

    material_stem = _material_asset_stem(os.path.basename(filepath))
    base_path = os.path.join(os.path.dirname(filepath), material_stem)
    error_messages = []
    owns_documents = document_session is None
    documents = document_session or DocumentSession()
    materials = MaterialRepository(documents)
    material_resources = material_resources or MaterialResourceRepository(documents)
    depot_path, json_apps, mats, has_material_json = _load_material_json(
        base_path,
        error_messages,
        materials,
    )
    if not has_material_json:
        if owns_documents:
            documents.close()
        return {"updated": False, "reason": "no_material_json"}

    prefs = get_addon_preferences()
    depot_path = _resolved_depot_path(
        depot_path,
        prefs,
        remap_depot,
        not prefs.non_verbose,
    )
    if depot_path is None:
        if owns_documents:
            documents.close()
        return {"updated": False, "reason": "no_depot"}

    warm_material_cache_index()
    mesh_entries = sorted(mesh_objects.items())
    source_names = []
    authored_indices = []
    for index, obj in mesh_entries:
        try:
            source_name = str(obj.get("cp77_material_name", "") or "")
        except (AttributeError, ReferenceError, TypeError):
            source_name = ""
        if not source_name and len(obj.data.materials):
            source_name = _existing_material_name(obj.data.materials[0])
        source_names.append(source_name)
        authored_indices.append(index)

    plan, resolved, unresolved = requested_material_names_by_submesh(
        json_apps,
        appearances,
        source_names,
        authored_indices,
    )
    valid_names = {name for names in plan for name in names if name}
    records = _material_records(mats, valid_names)
    built = {}
    failures = []
    try:
        with material_resource_scope(material_resources):
            builder = MaterialBuilder(
                mats,
                depot_path,
                str(image_format),
                base_path,
            )
            for name in _unique_names(
                    name for names in plan for name in names if name in records
                    ):
                record_index, metadata = records[name]
                try:
                    material = builder.create(mats, record_index)
                    if material is None:
                        failures.append(name)
                        continue
                    _apply_material_metadata(material, metadata)
                    built[name] = material
                except Exception:
                    traceback.print_exc()
                    failures.append(name)
    finally:
        if owns_documents:
            documents.close()

    appended = 0
    unprepared = []
    for plan_index, (index, obj) in enumerate(mesh_entries):
        requested_names = (
            plan[plan_index] if plan_index < len(plan) else ()
        )
        for name in requested_names:
            material = built.get(name)
            if material is None:
                continue
            if _attach_source_local_material(obj, name, material):
                appended += 1
        attached_names = [
            _existing_material_name(material)
            for material in obj.data.materials
            if material is not None
        ]
        attached_folded = {name.casefold() for name in attached_names if name}
        for name in requested_names:
            if name.casefold() not in attached_folded:
                unprepared.append((int(index), name))
        obj["cp77_submesh_index"] = int(index)
        obj["cp77_requested_material_candidates"] = json.dumps(
            list(requested_names),
            separators=(",", ":"),
        )
        obj["cp77_material_candidates"] = json.dumps(
            attached_names,
            separators=(",", ":"),
        )

    stored_requests = []
    try:
        raw_stored = collection.get("cp77_material_requested_appearances", "")
        if raw_stored:
            stored_requests = list(json.loads(raw_stored))
    except (AttributeError, ReferenceError, TypeError, ValueError, json.JSONDecodeError):
        stored_requests = []
    for appearance in appearances or ():
        value = str(appearance)
        if value and value not in stored_requests:
            stored_requests.append(value)
    if not appearances and "ALL" not in stored_requests:
        stored_requests.append("ALL")

    collection["json_apps"] = json.dumps(json_apps)
    collection["cp77_material_preparation_version"] = (
        MATERIAL_PREPARATION_VERSION
    )
    collection["cp77_material_submesh_indices"] = json.dumps(
        authored_indices,
        separators=(",", ":"),
    )
    collection["cp77_material_requested_appearances"] = json.dumps(
        stored_requests,
        separators=(",", ":"),
    )
    collection["cp77_material_resolved_appearances"] = json.dumps(
        resolved,
        separators=(",", ":"),
    )
    collection["cp77_material_unresolved_appearances"] = json.dumps(
        list(unresolved),
        separators=(",", ":"),
    )
    collection["cp77_material_submesh_plan"] = json.dumps(
        [list(names) for names in plan],
        separators=(",", ":"),
    )
    if error_messages:
        show_message("\n".join(error_messages))
    if not failures and not unprepared:
        _record_collection_material_coverage(
            collection,
            filepath,
            appearances,
        )
    return {
        "updated": bool(appended),
        "appended": appended,
        "failures": tuple(dict.fromkeys(failures)),
        "unprepared": tuple(dict.fromkeys(unprepared)),
        "resolved": resolved,
        "unresolved": unresolved,
    }


def import_cyberpunk_glb(
    with_materials=False,
    remap_depot=False,
    exclude_unused_mats=True,
    image_format="png",
    filepath="",
    hide_armatures=True,
    import_garmentsupport=False,
    files=None,
    directory="",
    appearances=None,
    scripting=False,
    import_tracks=False,
    generate_overrides=False,
    animation_target=None,
    document_session=None,
    material_resources=None,
    content_kind=None,
    transaction=None,
    bulk_import=False,
):
    prefs = get_addon_preferences()
    verbose = not prefs.non_verbose
    detailed_logging = verbose and not bulk_import
    context = bpy.context
    appearances = appearances or []
    files = files or []

    active_transaction = current_import_transaction()
    if transaction is not None and active_transaction not in (None, transaction):
        raise RuntimeError("GLB import transaction conflicts with active transaction")
    transaction_owner = transaction or active_transaction
    owns_transaction = transaction_owner is None
    if transaction_owner is None:
        transaction_owner = DatablockImportTransaction()
    savepoint = transaction_owner.savepoint()
    transaction_scope = (
        transaction_owner.scope()
        if active_transaction is not transaction_owner
        else None
    )
    transaction_scope_entered = False
    context_snapshot = None
    original_fps = None
    owns_documents = document_session is None
    documents = None
    try:
        if transaction_scope is not None:
            transaction_scope.__enter__()
            transaction_scope_entered = True
        if owns_transaction:
            context_snapshot = BlenderContextSnapshot().store()
        original_fps = context.scene.render.fps
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        if not directory or scripting:
            directory = os.path.dirname(filepath)
        loadfiles = _load_file_entries(filepath, directory, files, scripting)
        start_time = time.time()
        error_messages = []
        imported_results = []
        if with_materials:
            warm_material_cache_index()
        cache_before = material_cache_counters() if detailed_logging else None
        documents = document_session or DocumentSession()
        materials = MaterialRepository(documents)
        material_resources = material_resources or MaterialResourceRepository(documents)
    except Exception as error:
        report = transaction_owner.rollback() if owns_transaction else transaction_owner.rollback_to(savepoint)
        rollback_error = rollback_report_message(report)
        if owns_documents and documents is not None:
            documents.close()
        try:
            if original_fps is not None:
                context.scene.render.fps = original_fps
            if context_snapshot is not None:
                context_snapshot.restore()
        finally:
            if transaction_scope_entered:
                transaction_scope.__exit__(None, None, None)
        if rollback_error:
            raise RuntimeError(
                f"{error}; rollback incomplete: {rollback_error}"
            ) from error
        raise

    try:
        with material_resource_scope(material_resources):
            for entry in loadfiles:
                file_name = _entry_name(entry)
                file_path = os.path.join(directory, file_name)
                lower_path = file_path.lower()

                is_animation = (
                    content_kind == "animation"
                    or (content_kind is None and lower_path.endswith(".anims.glb"))
                )
                if is_animation:
                    bpy.context.scene.render.fps = 30
                    if detailed_logging:
                        print("\n-------------------- Beginning Cyberpunk Animation Import --------------------")
                        print(f"Importing Animations From: {file_name}")
                    _try_direct_animation_import(
                        file_path,
                        context,
                        animation_target,
                        import_tracks,
                        detailed_logging,
                    )
                    continue

                if detailed_logging:
                    print("\n-------------------- Beginning Cyberpunk Model Import --------------------")
                    suffix = " with materials" if with_materials else ""
                    print(f"Importing: {file_name}{suffix}")
                    if with_materials:
                        print(f"Appearances to Import: {appearances}")

                result = import_mesh_glb(
                    file_path,
                    import_garment_support=import_garmentsupport,
                    hide_armature=hide_armatures,
                    transaction=transaction_owner,
                )
            
                if file_name.startswith("terrain"):
                    uv_by_bounds(result["objects"])

                materials_imported = False
                if with_materials:
                    material_stem = _material_asset_stem(file_name)
                    current_file_base_path = os.path.join(directory, material_stem)
                    depot_path, json_apps, mats, has_material_json = _load_material_json(
                        current_file_base_path,
                        error_messages,
                        materials,
                    )
                    if not has_material_json:
                        message = (
                            "Required Material.json not found: "
                            f"{current_file_base_path}.Material.json"
                        )
                        print(message)
                        error_messages.append(message)
                    else:
                        result["collection"]["json_apps"] = json.dumps(json_apps)
                        (
                            material_names_by_submesh,
                            resolved_appearances,
                            unresolved_appearances,
                        ) = _requested_submesh_material_plan(
                            result,
                            json_apps,
                            appearances,
                        )
                        valid_names = {
                            name
                            for names in material_names_by_submesh
                            for name in names
                            if name
                        }
                        if not valid_names:
                            valid_names = _decoded_material_names(result, mats)
                        result["collection"][
                            "cp77_material_requested_appearances"
                        ] = json.dumps(list(appearances), separators=(",", ":"))
                        result["collection"][
                            "cp77_material_resolved_appearances"
                        ] = json.dumps(
                            resolved_appearances,
                            separators=(",", ":"),
                        )
                        result["collection"][
                            "cp77_material_unresolved_appearances"
                        ] = json.dumps(
                            list(unresolved_appearances),
                            separators=(",", ":"),
                        )
                        depot_path = _resolved_depot_path(
                            depot_path,
                            prefs,
                            remap_depot,
                            detailed_logging,
                        )
                        if depot_path is None:
                            message = (
                                "Failed to resolve DepotPath for "
                                f"{file_name}; required materials were not imported"
                            )
                            print(message)
                            error_messages.append(message)
                        else:
                            try:
                                material_result = import_mats(
                                    current_file_base_path,
                                    depot_path,
                                    exclude_unused_mats,
                                    result,
                                    image_format,
                                    mats,
                                    valid_names,
                                    material_names_by_submesh=(
                                        material_names_by_submesh
                                    ),
                                    is_morphtarget=".morphtarget" in file_name.lower(),
                                    log_timing=detailed_logging,
                                )
                            except Exception as error:
                                material_result = {
                                    "failures": (
                                        f"{type(error).__name__}: {error}",
                                    ),
                                    "unprepared": (),
                                }
                                print(traceback.format_exc())
                            failed_materials = material_result.get("failures", ())
                            if failed_materials:
                                error_messages.append(
                                    "Material setup failed for "
                                    f"{file_name}: {', '.join(failed_materials)}"
                                )
                            unprepared_materials = material_result.get(
                                "unprepared",
                                (),
                            )
                            if unprepared_materials:
                                error_messages.append(
                                    "Submesh materials were not prepared for "
                                    f"{file_name}: "
                                    + ", ".join(
                                        f"{index}:{name}"
                                        for index, name in unprepared_materials
                                    )
                                )
                            if (
                                not failed_materials
                                and not unprepared_materials
                            ):
                                _record_collection_material_coverage(
                                    result["collection"],
                                    file_path,
                                    appearances,
                                )
                                materials_imported = True

                if generate_overrides and materials_imported:
                    from ...materials.blender.multilayer import cp77_mlsetup_generateoverrides

                    try:
                        cp77_mlsetup_generateoverrides(None, bpy.context)
                    except Exception as error:
                        message = (
                            f"Material override generation skipped for {file_name}: "
                            f"{type(error).__name__}: {error}"
                        )
                        print(message)
                        print(traceback.format_exc())
                        error_messages.append(message)

                reset_shape_key_values(result["objects"])
                imported_results.append(result)

        for issue in documents.issues:
            if issue.message not in error_messages:
                error_messages.append(issue.message)
        if error_messages and not bulk_import:
            show_message("\n".join(error_messages))
        if detailed_logging:
            cache_after = material_cache_stats(include_helpers=False)
            exact_hits = (
                cache_after["exact_hits"]
                - cache_before["exact_hits"]
            )
            prototype_hits = (
                cache_after["prototype_hits"]
                - cache_before["prototype_hits"]
            )
            cache_misses = (
                cache_after["misses"]
                - cache_before["misses"]
            )
            cache_builds = (
                cache_after["builds"]
                - cache_before["builds"]
            )
            cache_clones = (
                cache_after["clones"]
                - cache_before["clones"]
            )
            print(
                "Material Cache: "
                f"{exact_hits} exact hits, "
                f"{prototype_hits} prototype hits, "
                f"{cache_misses} shader misses, "
                f"{cache_builds} shader builds, "
                f"{cache_clones} material clones, "
                f"{cache_after['entries']} cached exact entries"
            )
            print(f"GLB Import Time: {time.time() - start_time:.3f} Seconds")
            print("-------------------- Finished importing Cyberpunk 2077 Model --------------------\n")
    except Exception as error:
        report = transaction_owner.rollback() if owns_transaction else transaction_owner.rollback_to(savepoint)
        rollback_error = rollback_report_message(report)
        if rollback_error:
            raise RuntimeError(
                f"{error}; rollback incomplete: {rollback_error}"
            ) from error
        raise
    finally:
        if owns_documents and documents is not None:
            documents.close()
        try:
            if original_fps is not None:
                context.scene.render.fps = original_fps
            if context_snapshot is not None:
                context_snapshot.restore()
        finally:
            if transaction_scope_entered:
                transaction_scope.__exit__(None, None, None)

    if owns_transaction:
        transaction_owner.commit()

    return ImportResult(
        created_items=tuple(imported_results),
        warnings=unique_messages(error_messages),
        label="direct GLB import",
    )


def _material_user_slots(material):
    slots = []
    for obj in tuple(getattr(bpy.data, "objects", ())):
        try:
            material_slots = tuple(obj.material_slots)
        except (AttributeError, ReferenceError, TypeError):
            continue
        for index, slot in enumerate(material_slots):
            try:
                if slot.material is material:
                    slots.append((obj, index, slot))
            except (AttributeError, ReferenceError):
                continue
    return tuple(slots)


def reload_materials(self, context):
    active_obj = context.active_object
    active_material = active_obj.active_material if active_obj is not None else None
    if active_material is None:
        self.report({"ERROR"}, "No active material selected")
        return {"CANCELLED"}

    orig_mat_name = str(active_material.get("SourceMaterialName", active_material.name))
    if "m" in active_material:
        try:
            orig_mat_name = str(active_material["m"]["Name"])
        except (KeyError, TypeError):
            pass

    base_path = active_material.get("MeshPath")
    depot_path = active_material.get("DepotPath")
    project_path = active_material.get("ProjPath")
    if base_path is None:
        for collection in bpy.data.collections:
            if collection.objects.get(active_obj.name) is None:
                continue
            mesh_path = collection.get("mesh")
            if mesh_path and project_path:
                mesh_path_no_suffix = mesh_path[:mesh_path.rfind(".")]
                base_path = os.path.join(project_path, mesh_path_no_suffix)
            break
    if base_path is None:
        self.report({"ERROR"}, "Could not resolve material base path")
        return {"CANCELLED"}

    material_path = base_path + ".Material.json"
    if not os.path.exists(material_path):
        self.report({"ERROR"}, "Material.json not found: " + material_path)
        return {"CANCELLED"}

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
                ("material_slot", id(user_obj), user_index),
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
                raise RuntimeError("; ".join(messages) or "Material bundle could not be loaded")
            mats = list(bundle.materials)
            with material_resource_scope(material_resources):
                builder = MaterialBuilder(mats, depot_path, "png", base_path)
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
                from ...material_types.multilayered import fresh_multilayer_runtime
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
                metadata = _material_metadata(source_raw_material)
                if metadata is not None:
                    _apply_material_metadata(new_material, metadata)
                for _user_obj, _user_index, user_slot in user_slots:
                    user_slot.material = new_material
        if owns_transaction:
            owner.commit()
    except Exception as error:
        report = owner.rollback() if owns_transaction else owner.rollback_to(savepoint)
        message = str(error)
        if not report.ok:
            message += "; rollback incomplete: " + "; ".join(
                [f"{label}: {detail}" for label, detail in report.failures]
                + list(report.leaked)
            )
        self.report({"ERROR"}, message)
        return {"CANCELLED"}
    finally:
        if scope is not None:
            scope.__exit__(None, None, None)

    return new_material
