import json
import os
import re
import time
import traceback

import bpy

from .direct_mesh_import import import_mesh_glb, reset_shape_key_values
from .common.cache import acquire_json_cache, release_json_cache
from .common.paths import absolute_path_key
from .common.material_appearances import requested_material_names_by_submesh
from ..jsontool import JSONTool
from ..main.bartmoss_functions import UV_by_bounds
from ..main.common import exclusion_cache, show_message
from ..main.setup import MaterialBuilder, material_cache_stats, warm_material_cache_index


MATERIAL_PREPARATION_VERSION = 2


def _is_direct_animation_armature(obj):
    return (
        obj is not None
        and getattr(obj, "type", None) == "ARMATURE"
        and str(obj.data.get("cp77_rig_space_contract", ""))
        == "CP77_RE_MODEL_BL_BONE_X_NEGZ_Y_Y_Z_X_V1"
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
    from .direct_anim_import import (
        UnsupportedDirectAnimation,
        import_anims_glb_to_armature,
    )

    direct_target = _resolve_direct_animation_target(context, animation_target)
    if direct_target is None:
        raise UnsupportedDirectAnimation(
            "Select a read_rig armature or a mesh bound to one before importing an .anims.glb file."
        )

    summary = import_anims_glb_to_armature(
        filepath,
        direct_target,
        import_tracks=import_tracks,
        verbose=verbose,
    )
    exclusion_cache.clear_cache()
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
):
    """Build requested materials once and attach only each submesh's candidates."""
    prefs = bpy.context.preferences.addons[
        "i_scene_cp77_gltf"
    ].preferences
    verbose = not prefs.non_verbose
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


def _load_material_json(base_path, error_messages):
    material_path = base_path + ".Material.json"
    if not os.path.exists(material_path):
        return None, {}, [], False
    depot_path, raw_apps, mats = JSONTool.jsonload(material_path, error_messages)
    return depot_path, _normalize_json_apps(dict(raw_apps or {})), list(mats or ()), True


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
    depot_path, json_apps, mats, has_material_json = _load_material_json(
        base_path,
        error_messages,
    )
    if not has_material_json:
        return {"updated": False, "reason": "no_material_json"}

    prefs = bpy.context.preferences.addons["i_scene_cp77_gltf"].preferences
    depot_path = _resolved_depot_path(
        depot_path,
        prefs,
        remap_depot,
        not prefs.non_verbose,
    )
    if depot_path is None:
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
    builder = MaterialBuilder(
        mats,
        depot_path,
        str(image_format),
        base_path,
    )
    built = {}
    failures = []
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


def CP77GLBimport(
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
):
    prefs = bpy.context.preferences.addons["i_scene_cp77_gltf"].preferences
    verbose = not prefs.non_verbose
    context = bpy.context
    appearances = appearances or []
    files = files or []

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
    cache_before = material_cache_stats()
    owns_json_cache = acquire_json_cache(JSONTool)

    try:
        for entry in loadfiles:
            file_name = _entry_name(entry)
            file_path = os.path.join(directory, file_name)
            lower_path = file_path.lower()

            if lower_path.endswith(".anims.glb"):
                bpy.context.scene.render.fps = 30
                if verbose:
                    print("\n-------------------- Beginning Cyberpunk Animation Import --------------------")
                    print(f"Importing Animations From: {file_name}")
                _try_direct_animation_import(
                    file_path,
                    context,
                    animation_target,
                    import_tracks,
                    verbose,
                )
                continue

            if verbose:
                print("\n-------------------- Beginning Cyberpunk Model Import --------------------")
                suffix = " with materials" if with_materials else ""
                print(f"Importing: {file_name}{suffix}")
                if with_materials:
                    print(f"Appearances to Import: {appearances}")

            result = import_mesh_glb(
                file_path,
                import_garment_support=import_garmentsupport,
                hide_armature=hide_armatures,
            )
            exclusion_cache.clear_cache()

            if file_name.startswith("terrain"):
                UV_by_bounds(result["objects"])

            materials_imported = False
            if with_materials:
                material_stem = _material_asset_stem(file_name)
                current_file_base_path = os.path.join(directory, material_stem)
                depot_path, json_apps, mats, has_material_json = _load_material_json(
                    current_file_base_path,
                    error_messages,
                )
                if not has_material_json:
                    print(
                        "Material.json not found; imported geometry without materials: "
                        f"{current_file_base_path}.Material.json"
                    )
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
                        verbose,
                    )
                    if depot_path is None:
                        print("Failed to resolve DepotPath; imported geometry without materials")
                    else:
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
                        )
                        if (
                            not material_result.get("failures")
                            and not material_result.get("unprepared")
                        ):
                            _record_collection_material_coverage(
                                result["collection"],
                                file_path,
                                appearances,
                            )
                        materials_imported = True

            if generate_overrides and materials_imported:
                from ..exporters.mlsetup_export import cp77_mlsetup_generateoverrides

                cp77_mlsetup_generateoverrides(None, bpy.context)

            reset_shape_key_values(result["objects"])
            imported_results.append(result)

        if error_messages:
            show_message("\n".join(error_messages))
        if verbose:
            cache_after = material_cache_stats()
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
                f"{cache_after['entries']} live exact entries"
            )
            print(f"GLB Import Time: {time.time() - start_time:.3f} Seconds")
            print("-------------------- Finished importing Cyberpunk 2077 Model --------------------\n")
    finally:
        release_json_cache(JSONTool, owns_json_cache)

    return tuple(imported_results)


def reload_mats(self, context):
    active_obj = bpy.context.active_object
    active_material = active_obj.active_material
    if active_material is None:
        self.report({"ERROR"}, "No active material selected")
        return {"CANCELLED"}

    orig_mat_name = active_material.name
    if "m" in active_material:
        orig_mat_name = str(active_material["m"]["Name"])

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

    error_messages = []
    material_path = base_path + ".Material.json"
    if not os.path.exists(material_path):
        self.report({"ERROR"}, "Material.json not found: " + material_path)
        return {"CANCELLED"}

    owns_json_cache = acquire_json_cache(JSONTool)

    try:
        _, _, mats = JSONTool.jsonload(material_path, error_messages)
        builder = MaterialBuilder(mats, depot_path, "png", base_path)
    finally:
        release_json_cache(JSONTool, owns_json_cache)

    if error_messages:
        show_message("\n".join(error_messages))

    new_material = None
    old_base_name = orig_mat_name.split(".")[0]
    for index, raw_material in enumerate(mats):
        if raw_material.get("Name") == old_base_name:
            new_material = builder.create(mats, index, force_rebuild=True)
            break

    if new_material is None:
        self.report({"ERROR"}, "New material not created")
        return {"CANCELLED"}

    for key in active_material.keys():
        if key in ("BaseMaterial", "DiffuseMap", "GlobalNormal", "MultilayerMask"):
            new_material[key] = active_material[key]

    old_material = active_material
    active_obj.material_slots[active_obj.active_material_index].material = new_material
    if old_material.users == 0:
        bpy.data.materials.remove(
            old_material,
            do_unlink=True,
            do_id_user=True,
            do_ui_user=True,
        )
    return new_material
