import json
<<<<<<< Updated upstream
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
=======
import logging
import os
import time

import bpy
import numpy as np

from ...assetio.documents import DocumentSession, FileIdentity
from ...assetio.paths import (
    absolute_local_path_key,
    backslash_depot_key,
    material_sidecar_path,
    split_source_raw_root,
)
from ...assetio.values import json_array, json_object
from ...blender import selection
from ...blender.context import BlenderContextSnapshot
from ...blender.identity import rna_identity, rna_is_live
from ...blender.mesh import (
    ensure_color_attribute_alias,
    refresh_tangent_sign_attributes,
    set_constant_float_attribute,
)
from ...blender.transactions import (
    DatablockImportTransaction,
    current_import_transaction,
    raise_if_rollback_incomplete,
    track_collection_state,
    track_mutation,
)
from ...core.addon_identity import get_addon_preferences
from ...core.log import debug_exception, get_logger, log_once, operation
from ...core.notifications import import_message
from ...gltf.provenance import inspect_glb
from ...gltf.submesh import submesh_index_for_object, submesh_index_from_name
from ...material_types.circuit_wires import WIRE_COLOR_PRESENCE_ATTRIBUTE
from ...material_types.hud_markers import VERTEX_COLOR_PRESENT_ATTRIBUTE
from ...material_types.vehicle_decal_dirt import (
    prepare_vehicle_dirt_mesh,
    vehicle_dirt_material_needs_rebuild,
)
from ...materials.blender.builder import MaterialBuilder
from ...materials.blender.bulk import bulk_material_import_scope
from ...materials.blender.cache import (
    material_cache_counters,
    material_cache_stats,
    warm_material_cache_index,
)
from ...materials.blender.images import (
    begin_image_failure_capture,
    end_image_failure_capture,
    image_load_failure_message,
)
from ...materials.blender.skin_runtime import bind_skin_materials_for_object
from ...materials.prefetch import prefetch_multilayer_documents
from ...materials.repository import MaterialRepository, MaterialResourceRepository
from ...materials.resources import material_resource_scope
from ...materials.shadow_policy import object_shadow_policy
from ...meshes.repository import is_physical_scene
from ...redSpace.contracts import RIG_SPACE_CONTRACT_CURRENT
from ..common.material_appearances import requested_material_names_by_submesh
from ..common.results import ImportResult, summarize_messages, unique_messages
from .appearances import create_mesh_appearance_variants
from .decal_receivers import bind_mesh_decals
from .document import decode_mesh_glb
from .scene import (
    ensure_metalbase_vertex_rm_attribute,
    ensure_source_frame_attributes,
    import_mesh_glb,
    source_frame_attributes_available,
)
from .terrain_uv import apply_terrain_generated_uvs

_LOG = get_logger(__name__)


MATERIAL_PREPARATION_VERSION = 9
_WINDOW_PARALLAX_VERTICAL_THRESHOLD = 0.5

_WINDOW_PARALLAX_SOURCE_FRAME_TEMPLATES = frozenset(
    backslash_depot_key(path)
    for path in (
        "base\\materials\\window_parallax_interior.mt",
        "base\\materials\\window_parallax_interior_proxy.mt",
        "base\\materials\\window_parallax_interior_proxy_buffer.mt",
    )
)


def _material_requires_source_frame(material):
    if material is None:
        return False
    return (
        backslash_depot_key(material.get("MaterialTemplate", ""))
        in _WINDOW_PARALLAX_SOURCE_FRAME_TEMPLATES
    )


def _object_requires_source_frame(obj):
    mesh = getattr(obj, "data", None)
    if mesh is None:
        return False
    return any(
        _material_requires_source_frame(material)
        for material in mesh.materials
        if material is not None
    )


def _material_flag(material, name):
    if material is None:
        return False
    try:
        return bool(material.get(name))
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_material_flag", type(error).__name__),
            "material flag: fell back after %s",
            error,
            exc_info=True,
        )
        return False


def _prepare_circuit_wire_color_contract(obj, materials):
    circuit_materials = [
        material
        for material in materials
        if _material_flag(material, "cp77_circuit_wires_vertex_color_layer")
    ]
    if not circuit_materials:
        return ""
    mesh = getattr(obj, "data", None)
    if mesh is None:
        return ""
    source_name = ensure_color_attribute_alias(
        mesh,
        canonical="Color",
        aliases=("COLOR_0",),
    )
    set_constant_float_attribute(
        mesh,
        WIRE_COLOR_PRESENCE_ATTRIBUTE,
        1.0 if source_name else 0.0,
    )
    if source_name:
        return ""
    return (
        f"Circuit-wires material on {getattr(obj, 'name', '<unnamed>')} has no "
        "vertex color attribute; using the shader's non-vertex-color fallback "
        "without bevel/debug/segment-ID behavior."
    )


def _prepare_hud_marker_color_contract(obj, materials):
    """Distinguish absent HUD vertex colors from authored transparent vertices"""
    if not any(
        _material_flag(material, "cp77_hud_markers_version")
        or _material_flag(material, "cp77_hud_color_required")
        for material in materials
    ):
        return
    mesh = getattr(obj, "data", None)
    if mesh is None:
        return
    source_name = ensure_color_attribute_alias(
        mesh, canonical="Color", aliases=("COLOR_0",)
    )
    set_constant_float_attribute(
        mesh,
        VERTEX_COLOR_PRESENT_ATTRIBUTE,
        1.0 if source_name else 0.0,
    )


def _apply_object_shadow_policy(obj, materials):
    attached = tuple(material for material in materials if material is not None)
    visible_shadow, _mixed = object_shadow_policy(
        _material_flag(material, "cp77_no_shadows") for material in attached
    )
    obj.visible_shadow = visible_shadow
    return ""


def _sign_counts(values):
    values = np.asarray(values, dtype=np.float32).reshape(-1)
    return (
        int(np.count_nonzero(values < -1.0e-5)),
        int(np.count_nonzero(np.abs(values) <= 1.0e-5)),
        int(np.count_nonzero(values > 1.0e-5)),
    )


def _window_parallax_signs_from_local_up(submesh):
    tangents = submesh.tangents
    normals = submesh.normals
    if tangents is None or normals is None or len(normals) != len(tangents):
        return None, np.zeros(0, dtype=bool)

    decoded = np.ascontiguousarray(tangents[:, 3], dtype=np.float32)
    cross = np.cross(
        np.asarray(normals, dtype=np.float64),
        np.asarray(tangents[:, :3], dtype=np.float64),
    )
    length = np.linalg.norm(cross, axis=1)
    vertical_component = np.zeros(len(decoded), dtype=np.float64)
    finite = np.isfinite(length) & (length > 1.0e-8)
    vertical_component[finite] = cross[finite, 2] / length[finite]
    vertical = (
        finite
        & np.isfinite(vertical_component)
        & (np.abs(vertical_component) > _WINDOW_PARALLAX_VERTICAL_THRESHOLD)
    )

    result = decoded.copy()
    result[vertical] = np.where(vertical_component[vertical] > 0.0, -1.0, 1.0)
    return result, vertical


def _debug_window_source_frame(obj, submesh):
    if not _LOG.isEnabledFor(logging.DEBUG) or submesh.tangents is None:
        return
    try:
        decoded = np.asarray(submesh.tangents[:, 3], dtype=np.float32)
        parallax, vertical = _window_parallax_signs_from_local_up(submesh)
        if parallax is None:
            parallax = decoded
            vertical = np.zeros(len(decoded), dtype=bool)

        adjusted = vertical & (np.sign(decoded) != np.sign(parallax))
        if submesh.normals is not None and len(submesh.normals) == len(
            submesh.tangents
        ):
            normals = np.asarray(submesh.normals, dtype=np.float64)
            tangents = np.asarray(submesh.tangents[:, :3], dtype=np.float64)
            cross = np.cross(normals, tangents)
            basis_y_before = -cross * decoded[:, None]
            basis_y_after = -cross * parallax[:, None]
            y_down_before = int(
                np.count_nonzero(vertical & (basis_y_before[:, 2] < -1.0e-5))
            )
            y_down_after = int(
                np.count_nonzero(vertical & (basis_y_after[:, 2] < -1.0e-5))
            )
        else:
            y_down_before = 0
            y_down_after = 0

        linear = np.asarray(submesh.node_matrix_red[:3, :3], dtype=np.float64)
        scale = np.linalg.norm(linear, axis=0)
        _LOG.debug(
            "Window source frame %s: vertices=%d decoded_sign[-/0/+]=%s "
            "parallax_sign[-/0/+]=%s vertical=%d/%d adjusted=%d "
            "basis_y_down=%d->%d node_det=%.6f node_scale=(%.6f, %.6f, %.6f)",
            getattr(obj, "name", "<unnamed>"),
            len(decoded),
            _sign_counts(decoded),
            _sign_counts(parallax),
            int(np.count_nonzero(vertical)),
            len(decoded),
            int(np.count_nonzero(adjusted)),
            y_down_before,
            y_down_after,
            float(np.linalg.det(linear)),
            float(scale[0]),
            float(scale[1]),
            float(scale[2]),
        )
    except Exception:
        debug_exception(
            _LOG,
            "Window source-frame diagnostics failed for %s",
            getattr(obj, "name", "<unnamed>"),
        )


def _ensure_required_source_frame(obj, submesh):
    if not _object_requires_source_frame(obj):
        return False
    mesh = obj.data
    if source_frame_attributes_available(mesh):
        _debug_window_source_frame(obj, submesh)
        return True
    if ensure_source_frame_attributes(mesh, submesh):
        _debug_window_source_frame(obj, submesh)
        return True
    refresh_tangent_sign_attributes(mesh)
    _debug_window_source_frame(obj, submesh)
    _LOG.warning(
        "Source tangent frame unavailable for window parallax submesh %s; "
        "using generated tangent fallback",
        getattr(obj, "name", "<unnamed>"),
    )
    return False


def _record_timing(timing, phase, started):
    if timing is None:
        return
    timing[phase] = timing.get(phase, 0.0) + max(
        0.0,
        time.perf_counter() - started,
    )
>>>>>>> Stashed changes


def _is_direct_animation_armature(obj):
    return (
        obj is not None
        and getattr(obj, "type", None) == "ARMATURE"
        and str(obj.data.get("cp77_rig_space_contract", ""))
        == RIG_SPACE_CONTRACT_CURRENT
    )


<<<<<<< Updated upstream
def _resolve_direct_animation_target(context, explicit_target=None):
    auto_target = explicit_target is None or explicit_target is True or explicit_target == "AUTO"
=======
def resolve_direct_animation_target(context, explicit_target=None):
    auto_target = (
        explicit_target is None
        or explicit_target is True
        or explicit_target in ("AUTO", "SELECTED")
    )
>>>>>>> Stashed changes
    target = None if auto_target else explicit_target
    if isinstance(target, str):
        target = bpy.data.objects.get(target)
    if _is_direct_animation_armature(target):
        return target
    if not auto_target:
        return None

<<<<<<< Updated upstream
    active = context.active_object
=======
    selected_objects = tuple(context.selected_objects)
    active = (
        context.active_object if context.active_object in selected_objects else None
    )
>>>>>>> Stashed changes
    if _is_direct_animation_armature(active):
        return active
    if active is not None and getattr(active, "type", None) == "MESH":
        for modifier in active.modifiers:
<<<<<<< Updated upstream
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
=======
            if modifier.type == "ARMATURE" and _is_direct_animation_armature(
                modifier.object
            ):
                return modifier.object

    candidates = []
    for obj in selected_objects:
        if _is_direct_animation_armature(obj):
            candidates.append(obj)
        elif obj.type == "MESH":
            candidates.extend(
                modifier.object
                for modifier in obj.modifiers
                if modifier.type == "ARMATURE"
                and _is_direct_animation_armature(modifier.object)
            )
    candidates = tuple(dict.fromkeys(candidates))
    return candidates[0] if len(candidates) == 1 else None


def _try_direct_animation_import(
    filepath, context, animation_target, import_tracks, verbose
):
    from ..animation.document import import_anims_glb_to_armature

    target = (
        None
        if animation_target == "NEW"
        else resolve_direct_animation_target(context, animation_target)
    )
    if animation_target != "NEW" and target is None:
        selected_rigs = [
            obj for obj in context.selected_objects if obj.type == "ARMATURE"
        ]
        if (
            animation_target == "SELECTED"
            or selected_rigs
            or animation_target not in (None, True, "AUTO")
        ):
            raise ValueError(
                "Select one CP77 rig or choose Reconstruct Rig for animation import."
            )
    return import_anims_glb_to_armature(
        filepath,
        target,
        import_tracks=import_tracks,
        verbose=verbose,
    )


def _material_asset_stem(file_name):
    return material_sidecar_path(file_name)[: -len(".Material.json")]
>>>>>>> Stashed changes


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


<<<<<<< Updated upstream
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
=======
def _submesh_indices_by_import_order(direct_result):
    return tuple(
        submesh_index_from_name(submesh.name, fallback_index)
        for fallback_index, submesh in enumerate(direct_result["mesh_data"].submeshes)
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
=======
        previous = records.get(name)
        if previous is not None:
            if mats[previous[0]] != material_data:
                raise ValueError(
                    f"Ambiguous material name {name!r}: distinct source payloads share the same name."
                )
            continue
>>>>>>> Stashed changes
        metadata = _material_metadata(material_data)
        if metadata is not None:
            records[name] = (index, metadata)
    return records


def _apply_material_metadata(material, metadata):
<<<<<<< Updated upstream
    material["m"] = metadata
    material["BaseMaterial"] = metadata["BaseMaterial"]
    material["GlobalNormal"] = metadata["GlobalNormal"]
    material["MultilayerMask"] = metadata["MultilayerMask"]
    material["DiffuseMap"] = metadata["DiffuseMap"]
=======
    """Preserve source metadata without retagging unchanged shared materials"""
    values = {
        "cp77_source_material_name": metadata["Name"],
        "BaseMaterial": metadata["BaseMaterial"],
        "GlobalNormal": metadata["GlobalNormal"],
        "MultilayerMask": metadata["MultilayerMask"],
        "DiffuseMap": metadata["DiffuseMap"],
    }
    for key, value in values.items():
        if key not in material or material.get(key) != value:
            material[key] = value
>>>>>>> Stashed changes


def _unique_names(values):
    return tuple(dict.fromkeys(str(value) for value in values if value))


<<<<<<< Updated upstream
=======
def _unsupported_material_warning(raw_material):
    if MaterialBuilder.material_rule(raw_material) is not None:
        return ""
    template = raw_material.get("MaterialTemplate", "")
    name = raw_material.get("Name", "")
    return f"Unsupported material template '{template}' for {name!r}; a basic fallback graph was used."


>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
):
    """Build requested materials once and attach only each submesh's candidates."""
    if log_timing is None:
        prefs = get_addon_preferences()
        verbose = not prefs.non_verbose
    else:
        verbose = bool(log_timing)
    start_time = time.time()
    failed = []
=======
    timing=None,
    material_resources=None,
):
    """Build requested materials once and attach only each submesh's candidates"""
    if log_timing is None:
        verbose = _LOG.isEnabledFor(logging.DEBUG)
    else:
        verbose = bool(log_timing)
    start_time = time.perf_counter()
    failed = []
    warnings = []
    plan_started = time.perf_counter()
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
        raw_plan = tuple(
            _unique_names(submesh.material_names)
            for submesh in submeshes
        )
=======
        raw_plan = tuple(_unique_names(submesh.material_names) for submesh in submeshes)
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
        material_names = tuple(
            name
            for name in raw_names
            if name in records
        )
=======
        material_names = tuple(name for name in raw_names if name in records)
>>>>>>> Stashed changes
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

<<<<<<< Updated upstream
    built = {}
=======
    _record_timing(timing, "material_plan", plan_started)

    if material_resources is not None and required_names:
        prefetch_started = time.perf_counter()
        try:
            prefetch_indices = builder.material_prefetch_indices(
                mats,
                tuple(records[name][0] for name in required_names),
            )
            prefetch_stats = prefetch_multilayer_documents(
                material_resources,
                mats,
                prefetch_indices,
                project_root=builder.ProjPath,
                depot_root=builder.BasePath,
            )
            if timing is not None:
                timing["material_prefetch_setup_documents"] = timing.get(
                    "material_prefetch_setup_documents", 0
                ) + prefetch_stats.get("setup_documents", 0)
                timing["material_prefetch_template_documents"] = timing.get(
                    "material_prefetch_template_documents", 0
                ) + prefetch_stats.get("template_documents", 0)
                timing["material_prefetch_bytes"] = (
                    timing.get("material_prefetch_bytes", 0)
                    + prefetch_stats.get("setup_bytes", 0)
                    + prefetch_stats.get("template_bytes", 0)
                )
                timing["material_prefetch_mask_files"] = timing.get(
                    "material_prefetch_mask_files", 0
                ) + prefetch_stats.get("mask_files", 0)
                timing["material_prefetch_mask_bytes"] = timing.get(
                    "material_prefetch_mask_bytes", 0
                ) + prefetch_stats.get("mask_bytes", 0)
        finally:
            _record_timing(timing, "material_prefetch", prefetch_started)

    built = {}
    build_started = time.perf_counter()
>>>>>>> Stashed changes
    for name in required_names:
        index, metadata = records[name]
        try:
            material = builder.create(mats, index)
            if material is None:
                continue
            _apply_material_metadata(material, metadata)
            built[name] = material
<<<<<<< Updated upstream
        except Exception:
            traceback.print_exc()
            failed.append(name)

    submesh_indices = _submesh_indices_by_import_order(direct_result)
    unprepared = []
    for obj, submesh_index, raw_names, material_names in zip(
        objects,
=======
            warning = _unsupported_material_warning(mats[index])
            if warning:
                warnings.append(warning)
        except Exception as exc:
            _LOG.exception(
                "Material build failed for %s: %s: %s",
                name,
                type(exc).__name__,
                exc,
            )
            failed.append(name)
    _record_timing(timing, "material_build", build_started)

    submesh_indices = _submesh_indices_by_import_order(direct_result)
    armature = direct_result.get("armature")
    unprepared = []
    assignment_started = time.perf_counter()
    for obj, submesh, submesh_index, raw_names, material_names in zip(
        objects,
        direct_result["mesh_data"].submeshes,
>>>>>>> Stashed changes
        submesh_indices,
        raw_plan,
        material_names_by_submesh,
    ):
        mesh = obj.data
        mesh.materials.clear()
        attached = []
<<<<<<< Updated upstream
=======
        needs_metalbase_vertex_rm = False
>>>>>>> Stashed changes
        for name in material_names:
            material = built.get(name)
            if material is None:
                continue
<<<<<<< Updated upstream
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
=======
            needs_metalbase_vertex_rm |= bool(
                material.get("cp77_metal_base_vertex_rm_required")
            )
            mesh.materials.append(material)
            attached.append(name)
        color_warning = _prepare_circuit_wire_color_contract(obj, tuple(mesh.materials))
        _prepare_hud_marker_color_contract(obj, tuple(mesh.materials))
        prepare_vehicle_dirt_mesh(obj, tuple(mesh.materials))
        if color_warning:
            _LOG.warning("%s", color_warning)
            warnings.append(color_warning)
        shadow_warning = _apply_object_shadow_policy(obj, tuple(mesh.materials))
        if shadow_warning:
            _LOG.warning("%s", shadow_warning)
            warnings.append(shadow_warning)
        if needs_metalbase_vertex_rm:
            ensure_metalbase_vertex_rm_attribute(mesh)
        _ensure_required_source_frame(obj, submesh)
        bind_skin_materials_for_object(obj, armature)
        obj["cp77_submesh_index"] = int(submesh_index)
>>>>>>> Stashed changes
        attached_folded = {name.casefold() for name in attached if name}
        for name in raw_names:
            if name.casefold() not in attached_folded:
                unprepared.append((int(submesh_index), name))
<<<<<<< Updated upstream

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
=======
    _record_timing(timing, "material_assignment", assignment_started)
    # Deferred mesh decals preview over the submeshes they sit on.
    decal_started = time.perf_counter()
    bind_mesh_decals(objects)
    _record_timing(timing, "decal_receivers", decal_started)
    direct_result["collection"]["cp77_material_preparation_version"] = (
        MATERIAL_PREPARATION_VERSION
    )

    unique_failed = tuple(dict.fromkeys(failed))
    if unique_failed:
        preview = ", ".join(unique_failed[:3])
        if len(unique_failed) > 3:
            preview += f", and {len(unique_failed) - 3} more"
        _LOG.warning(
            "Material setup failed for %d material(s): %s",
            len(unique_failed),
            preview,
        )
        _LOG.debug("Material setup failure list: %s", unique_failed)
    if verbose:
        elapsed = time.perf_counter() - start_time
        if failed:
            _LOG.debug("Material setup failed after %.3f seconds", elapsed)
        else:
            _LOG.debug("Material setup completed in %.3f seconds", elapsed)
    return {
        "failures": unique_failed,
        "unprepared": tuple(dict.fromkeys(unprepared)),
        "warnings": tuple(dict.fromkeys(warnings)),
>>>>>>> Stashed changes
        "submeshIndices": submesh_indices,
    }


def _load_material_json(base_path, error_messages, materials):
    material_path = base_path + ".Material.json"
<<<<<<< Updated upstream
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
=======
    issue_start = len(materials.issues)
    bundle = materials.load(material_path)
    if bundle is None:
        error_messages.extend(
            issue.message
            for issue in materials.issues[issue_start:]
            if issue.code != "file.missing"
            if issue.message not in error_messages
        )
        return None, {}, [], False, None
    document = materials.documents.load(material_path)
    revision = [document.identity.mtime_ns, document.identity.size]
    return (
        bundle.depot_path,
        dict(bundle.appearances or {}),
        list(bundle.materials or ()),
        True,
        revision,
>>>>>>> Stashed changes
    )


def _resolved_depot_path(depot_path, prefs, remap_depot, verbose):
    if remap_depot and os.path.exists(prefs.depotfolder_path):
        depot_path = prefs.depotfolder_path
        if verbose:
<<<<<<< Updated upstream
            print(f"Using depot path: {depot_path}")
=======
            _LOG.debug("Resolved depot path: %s", depot_path)
>>>>>>> Stashed changes
    if depot_path is None:
        return None
    return str(depot_path).replace("\\", os.sep)


<<<<<<< Updated upstream
_SUBMESH_NAME_PATTERN = re.compile(r"submesh_(\d+)", re.IGNORECASE)


def _coverage_tokens(appearances):
    tokens = {
        str(value).casefold()
        for value in (appearances or ())
        if str(value)
    }
=======
def _coverage_tokens(appearances):
    tokens = {str(value).casefold() for value in (appearances or ()) if str(value)}
>>>>>>> Stashed changes
    if not tokens or "all" in tokens:
        return {"all"}
    return tokens


def _material_json_key(filepath):
    material_stem = _material_asset_stem(os.path.basename(filepath))
    base_path = os.path.join(os.path.dirname(filepath), material_stem)
<<<<<<< Updated upstream
    return absolute_path_key(base_path + ".Material.json")


def _coverage_values_satisfy(stored, requested):
    stored_values = {
        str(value).casefold()
        for value in (stored or ())
        if str(value)
    }
=======
    return absolute_local_path_key(base_path + ".Material.json")


def _coverage_values_satisfy(stored, requested):
    stored_values = {str(value).casefold() for value in (stored or ()) if str(value)}
>>>>>>> Stashed changes
    if "all" in requested:
        return "all" in stored_values
    return requested.issubset(stored_values) or "all" in stored_values


<<<<<<< Updated upstream
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
=======
def _material_source_revision(filepath):
    try:
        identity = FileIdentity.from_path(_material_json_key(filepath))
    except OSError:
        debug_exception(
            _LOG,
            "Could not read the material JSON of %s; its revision is unknown",
            filepath,
        )
        return None
    return [identity.mtime_ns, identity.size]


def _existing_collection_coverage_satisfies(
    collection,
    filepath,
    appearances,
):
    try:
        version = int(collection.get("cp77_material_preparation_version", 0) or 0)
        raw = collection.get("cp77_material_coverage_sources", "")
    except (AttributeError, ReferenceError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_existing_collection_coverage_satisfies", type(error).__name__),
            "existing collection coverage satisfies: fell back after %s",
            error,
            exc_info=True,
        )
        return False
    if version < MATERIAL_PREPARATION_VERSION or not raw:
        return False
    for obj in collection.all_objects:
        if getattr(obj, "type", "") == "MESH" and any(
            vehicle_dirt_material_needs_rebuild(material)
            for material in obj.data.materials
        ):
            return False
    stored = json_object(raw).get(_material_json_key(filepath), {})
    if not isinstance(stored, dict):
        return False
    revision = _material_source_revision(filepath)
    return (
        revision is not None
        and stored.get("revision") == revision
        and _coverage_values_satisfy(
            stored.get("appearances", ()), _coverage_tokens(appearances)
        )
    )


def _record_collection_material_coverage(
    collection, filepath, appearances, *, revision
):
    sources = json_object(collection.get("cp77_material_coverage_sources"))
    key = _material_json_key(filepath)
    stored = sources.get(key, {})
    if not isinstance(stored, dict):
        stored = {}
    existing = {
        str(value).casefold()
        for value in (
            stored.get("appearances", ()) if stored.get("revision") == revision else ()
        )
>>>>>>> Stashed changes
        if str(value)
    }
    requested = _coverage_tokens(appearances)
    if "all" in existing or "all" in requested:
<<<<<<< Updated upstream
        sources[key] = ["all"]
    else:
        sources[key] = sorted(existing | requested)
=======
        covered = ["all"]
    else:
        covered = sorted(existing | requested)
    sources[key] = {"revision": revision, "appearances": covered}
>>>>>>> Stashed changes
    collection["cp77_material_coverage_sources"] = json.dumps(
        sources,
        separators=(",", ":"),
        sort_keys=True,
    )

<<<<<<< Updated upstream
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

=======
>>>>>>> Stashed changes

def _existing_material_name(material):
    if material is None:
        return ""
    try:
<<<<<<< Updated upstream
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

=======
        name = material.get("cp77_source_material_name")
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_existing_material_name", type(error).__name__),
            "existing material name: fell back after %s",
            error,
            exc_info=True,
        )
        name = None
    return str(name or getattr(material, "name", "") or "")
>>>>>>> Stashed changes


def _existing_material_signature(material):
    if material is None:
        return ""
    try:
        return str(material.get("_cp77_material_signature", "") or "")
<<<<<<< Updated upstream
    except (AttributeError, ReferenceError, TypeError):
=======
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_existing_material_signature", type(error).__name__),
            "existing material signature: fell back after %s",
            error,
            exc_info=True,
        )
>>>>>>> Stashed changes
        return ""


def _attach_source_local_material(obj, name, material):
<<<<<<< Updated upstream
    """Attach one source-local material without creating a name ambiguity."""
=======
    """Attach one source-local material without creating a name ambiguity"""
    if material.get("cp77_metal_base_vertex_rm_required"):
        ensure_metalbase_vertex_rm_attribute(obj.data)
>>>>>>> Stashed changes
    expected_name = str(name).casefold()
    expected_signature = _existing_material_signature(material)
    same_name_index = None
    for index, existing in enumerate(obj.data.materials):
        if existing is None:
            continue
        if existing is material:
            return False
        existing_signature = _existing_material_signature(existing)
<<<<<<< Updated upstream
        if (
            expected_signature
            and existing_signature == expected_signature
        ):
=======
        if expected_signature and existing_signature == expected_signature:
>>>>>>> Stashed changes
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

<<<<<<< Updated upstream
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
=======

def _restore_master_object_materials(obj, mesh, materials, visible_shadow):
    if not rna_is_live(mesh):
        return
    slots = mesh.materials
    while len(slots) > len(materials):
        slots.pop()
    for index, material in enumerate(materials):
        if index < len(slots):
            if slots[index] is not material:
                slots[index] = material
        else:
            slots.append(material)
    if rna_is_live(obj):
        obj.visible_shadow = visible_shadow


def _master_object_materials_restored(mesh, materials):
    if not rna_is_live(mesh):
        return True
    return len(mesh.materials) == len(materials) and all(
        current is expected for current, expected in zip(mesh.materials, materials)
    )


def _track_master_object_materials(obj):
    """Restore slots of a reused master if new materials are rolled back"""
    mesh = obj.data
    materials = tuple(mesh.materials)
    track_mutation(
        ("master_object_materials", rna_identity(mesh)),
        lambda obj=obj, mesh=mesh, materials=materials, shadow=obj.visible_shadow: (
            _restore_master_object_materials(obj, mesh, materials, shadow)
        ),
        verify=lambda mesh=mesh, materials=materials: _master_object_materials_restored(
            mesh, materials
        ),
        label=f"master materials {obj.name}",
    )


def ensure_collection_material_coverage(
    collection,
    filepath,
    appearances,
    *,
    remap_depot=False,
    image_format="png",
    document_session=None,
    material_resources=None,
    timing=None,
):
    """Append missing requested-appearance materials to a reused mesh master"""
    if collection is None or _existing_collection_coverage_satisfies(
        collection,
        filepath,
        appearances,
    ):
>>>>>>> Stashed changes
        return {"updated": False, "reason": "covered"}

    mesh_objects = {}
    for obj in tuple(getattr(collection, "all_objects", ()) or ()):
        if getattr(obj, "type", None) != "MESH" or not getattr(obj, "data", None):
            continue
<<<<<<< Updated upstream
        index = _existing_submesh_index(obj)
=======
        index = submesh_index_for_object(obj, None)
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
    depot_path, json_apps, mats, has_material_json = _load_material_json(
        base_path,
        error_messages,
        materials,
    )
=======
    documents.invalidate(base_path + ".Material.json")
    material_json_started = time.perf_counter()
    depot_path, json_apps, mats, has_material_json, source_revision = (
        _load_material_json(
            base_path,
            error_messages,
            materials,
        )
    )
    _record_timing(timing, "material_json", material_json_started)
>>>>>>> Stashed changes
    if not has_material_json:
        if owns_documents:
            documents.close()
        return {"updated": False, "reason": "no_material_json"}

    prefs = get_addon_preferences()
    depot_path = _resolved_depot_path(
        depot_path,
        prefs,
        remap_depot,
<<<<<<< Updated upstream
        not prefs.non_verbose,
=======
        _LOG.isEnabledFor(logging.DEBUG),
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
        except (AttributeError, ReferenceError, TypeError):
=======
        except (AttributeError, ReferenceError, TypeError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("ensure_collection_material_coverage 1", type(error).__name__),
                "ensure collection material coverage: fell back after %s",
                error,
                exc_info=True,
            )
>>>>>>> Stashed changes
            source_name = ""
        if not source_name and len(obj.data.materials):
            source_name = _existing_material_name(obj.data.materials[0])
        source_names.append(source_name)
        authored_indices.append(index)

<<<<<<< Updated upstream
=======
    plan_started = time.perf_counter()
>>>>>>> Stashed changes
    plan, resolved, unresolved = requested_material_names_by_submesh(
        json_apps,
        appearances,
        source_names,
        authored_indices,
    )
    valid_names = {name for names in plan for name in names if name}
    records = _material_records(mats, valid_names)
<<<<<<< Updated upstream
    built = {}
    failures = []
=======
    existing_materials = {}
    for _index, obj in mesh_entries:
        for material in getattr(obj.data, "materials", ()):
            name = _existing_material_name(material)
            if name:
                existing_materials.setdefault(name.casefold(), material)
    _record_timing(timing, "material_plan", plan_started)
    built = {}
    failures = []
    material_warnings = []
    build_started = time.perf_counter()
>>>>>>> Stashed changes
    try:
        with material_resource_scope(material_resources):
            builder = MaterialBuilder(
                mats,
                depot_path,
                str(image_format),
                base_path,
            )
            for name in _unique_names(
<<<<<<< Updated upstream
                    name for names in plan for name in names if name in records
                    ):
                record_index, metadata = records[name]
=======
                name for names in plan for name in names if name in records
            ):
                record_index, metadata = records[name]
                warning = _unsupported_material_warning(mats[record_index])
                if warning:
                    material_warnings.append(warning)
                material = existing_materials.get(name.casefold())
                if material is not None and _existing_material_signature(
                    material
                ) == builder.material_signature(mats[record_index]):
                    built[name] = material
                    continue
>>>>>>> Stashed changes
                try:
                    material = builder.create(mats, record_index)
                    if material is None:
                        failures.append(name)
                        continue
                    _apply_material_metadata(material, metadata)
                    built[name] = material
<<<<<<< Updated upstream
                except Exception:
                    traceback.print_exc()
=======
                except Exception as exc:
                    _LOG.exception(
                        "Material build failed for %s: %s: %s",
                        name,
                        type(exc).__name__,
                        exc,
                    )
>>>>>>> Stashed changes
                    failures.append(name)
    finally:
        if owns_documents:
            documents.close()
<<<<<<< Updated upstream

    appended = 0
    unprepared = []
    for plan_index, (index, obj) in enumerate(mesh_entries):
        requested_names = (
            plan[plan_index] if plan_index < len(plan) else ()
        )
=======
        _record_timing(timing, "material_build", build_started)

    appended = 0
    unprepared = []
    source_frame_targets = []
    assignment_started = time.perf_counter()
    track_collection_state(
        collection,
        label=f"master coverage {collection.name}",
    )
    for plan_index, (index, obj) in enumerate(mesh_entries):
        _track_master_object_materials(obj)
        requested_names = plan[plan_index] if plan_index < len(plan) else ()
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
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
=======
        color_warning = _prepare_circuit_wire_color_contract(
            obj, tuple(obj.data.materials)
        )
        _prepare_hud_marker_color_contract(obj, tuple(obj.data.materials))
        prepare_vehicle_dirt_mesh(obj, tuple(obj.data.materials))
        if color_warning:
            _LOG.warning("%s", color_warning)
            material_warnings.append(color_warning)
        shadow_warning = _apply_object_shadow_policy(obj, tuple(obj.data.materials))
        if shadow_warning:
            _LOG.warning("%s", shadow_warning)
            material_warnings.append(shadow_warning)
        obj["cp77_submesh_index"] = int(index)
        if _object_requires_source_frame(obj) and not source_frame_attributes_available(
            obj.data
        ):
            source_frame_targets.append((int(index), obj))

    if source_frame_targets:
        try:
            decoded = decode_mesh_glb(
                filepath,
                restore_red_uvs=True,
                build_binding=False,
                import_garment_support=False,
            )
            decoded_by_index = {
                submesh_index_from_name(submesh.name, fallback_index): submesh
                for fallback_index, submesh in enumerate(decoded.submeshes)
            }
            for index, obj in source_frame_targets:
                submesh = decoded_by_index.get(index)
                if submesh is None or not ensure_source_frame_attributes(
                    obj.data, submesh
                ):
                    refresh_tangent_sign_attributes(obj.data)
                    _LOG.warning(
                        "Source tangent frame unavailable for window parallax "
                        "submesh %s",
                        getattr(obj, "name", "<unnamed>"),
                    )
        except Exception as exc:
            _LOG.warning(
                "Failed to restore window parallax source tangent frame for %s: %s",
                os.path.basename(filepath),
                exc,
                exc_info=True,
            )
    _record_timing(timing, "material_assignment", assignment_started)

    vehicle_dirt_updated = appended and any(
        material is not None and material.get("cp77_vehicle_decal_dirt_version")
        for obj in mesh_objects.values()
        for material in obj.data.materials
    )
    if vehicle_dirt_updated or any(
        vehicle_dirt_material_needs_rebuild(slot.material)
        for obj in mesh_objects.values()
        for slot in obj.material_slots
    ):
        bind_mesh_decals(mesh_objects.values())
    stored_requests = json_array(collection.get("cp77_material_requested_appearances"))
>>>>>>> Stashed changes
    for appearance in appearances or ():
        value = str(appearance)
        if value and value not in stored_requests:
            stored_requests.append(value)
    if not appearances and "ALL" not in stored_requests:
        stored_requests.append("ALL")

<<<<<<< Updated upstream
    collection["json_apps"] = json.dumps(json_apps)
    collection["cp77_material_preparation_version"] = (
        MATERIAL_PREPARATION_VERSION
    )
    collection["cp77_material_submesh_indices"] = json.dumps(
        authored_indices,
        separators=(",", ":"),
    )
=======
    collection["cp77_json_apps"] = json.dumps(json_apps)
    collection["cp77_material_preparation_version"] = MATERIAL_PREPARATION_VERSION
>>>>>>> Stashed changes
    collection["cp77_material_requested_appearances"] = json.dumps(
        stored_requests,
        separators=(",", ":"),
    )
<<<<<<< Updated upstream
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
=======
    if error_messages:
        import_message("\n".join(error_messages))
>>>>>>> Stashed changes
    if not failures and not unprepared:
        _record_collection_material_coverage(
            collection,
            filepath,
            appearances,
<<<<<<< Updated upstream
=======
            revision=source_revision,
>>>>>>> Stashed changes
        )
    return {
        "updated": bool(appended),
        "appended": appended,
        "failures": tuple(dict.fromkeys(failures)),
        "unprepared": tuple(dict.fromkeys(unprepared)),
<<<<<<< Updated upstream
=======
        "warnings": tuple(dict.fromkeys(material_warnings)),
>>>>>>> Stashed changes
        "resolved": resolved,
        "unresolved": unresolved,
    }


def import_cyberpunk_glb(
<<<<<<< Updated upstream
=======
    filepath,
    *,
>>>>>>> Stashed changes
    with_materials=False,
    remap_depot=False,
    exclude_unused_mats=True,
    image_format="png",
<<<<<<< Updated upstream
    filepath="",
    hide_armatures=True,
    import_garmentsupport=False,
    files=None,
    directory="",
    appearances=None,
    scripting=False,
    import_tracks=False,
    generate_overrides=False,
=======
    hide_armatures=True,
    import_garmentsupport=False,
    appearances=None,
    import_tracks=False,
>>>>>>> Stashed changes
    animation_target=None,
    document_session=None,
    material_resources=None,
    content_kind=None,
    transaction=None,
    bulk_import=False,
<<<<<<< Updated upstream
):
    prefs = get_addon_preferences()
    verbose = not prefs.non_verbose
    detailed_logging = verbose and not bulk_import
    context = bpy.context
    appearances = appearances or []
    files = files or []
=======
    collection_parent=None,
    collection_name: str = "",
    select_objects: bool = True,
    decoded_mesh_data=None,
    report_owner=None,
    timing=None,
    appearance_variants=True,
):
    prefs = get_addon_preferences()
    detailed_logging = _LOG.isEnabledFor(logging.DEBUG) and not bulk_import
    context = bpy.context
    appearances = appearances or []
    imported_animation = False
    succeeded = False
>>>>>>> Stashed changes

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
<<<<<<< Updated upstream
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
=======
    image_failures = begin_image_failure_capture()
    # A bulk import (entity, sector) times each GLB at DEBUG; a GLB the user imports is an INFO operation.
    with operation(
        _LOG,
        f"GLB import {os.path.basename(os.fspath(filepath))}",
        level=logging.DEBUG if bulk_import else logging.INFO,
        materials=bool(with_materials),
        garments=bool(import_garmentsupport),
    ):
        try:
            if transaction_scope is not None:
                transaction_scope.__enter__()
                transaction_scope_entered = True
            if owns_transaction:
                context_snapshot = BlenderContextSnapshot().store()
            original_fps = (context.scene.render.fps, context.scene.render.fps_base)
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            filepath = os.path.abspath(os.fspath(filepath))
            directory = os.path.dirname(filepath)
            file_name = os.path.basename(filepath)
            file_path = filepath
            error_messages = []
            imported_results = []
            if with_materials:
                warm_material_cache_index()
            cache_before = material_cache_counters() if detailed_logging else None
            documents = document_session or DocumentSession()
            document_issue_start = len(documents.issues)
            materials = MaterialRepository(documents)
            material_resources = material_resources or MaterialResourceRepository(
                documents
            )
        except Exception as error:
            report = (
                transaction_owner.rollback()
                if owns_transaction
                else transaction_owner.rollback_to(savepoint)
            )
            if owns_documents and documents is not None:
                documents.close()
            try:
                if original_fps is not None:
                    context.scene.render.fps, context.scene.render.fps_base = (
                        original_fps
                    )
                if context_snapshot is not None:
                    context_snapshot.restore()
            finally:
                if transaction_scope_entered:
                    transaction_scope.__exit__(None, None, None)
            raise_if_rollback_incomplete(report, error)
            raise

        try:
            with (
                material_resource_scope(material_resources),
                bulk_material_import_scope(
                    bulk_import,
                    owner=report_owner,
                ),
            ):
                kind = content_kind or (
                    "mesh"
                    if decoded_mesh_data is not None
                    else inspect_glb(file_path).content_kind.value
                )
                if kind not in {"mesh", "animation", "mixed", "rig"}:
                    raise ValueError(
                        f"{file_name} contains no mesh or animation payload."
                    )
                if kind == "rig":
                    from ..rig.gltf import import_gltf_rig

                    if file_name.casefold().endswith(".anims.glb"):
                        error_messages.append(
                            f"{file_name} contains a skin but no animation clips; "
                            "imported as a rig. Re-export the animation set from "
                            "WolvenKit if clips were expected."
                        )
                    imported_results.append(import_gltf_rig(file_path))
                elif kind == "animation":
                    context.scene.render.fps = 30
                    context.scene.render.fps_base = 1.0
                    if detailed_logging:
                        _LOG.debug("Importing animation payload %s", file_name)
                    animation_result = _try_direct_animation_import(
>>>>>>> Stashed changes
                        file_path,
                        context,
                        animation_target,
                        import_tracks,
                        detailed_logging,
                    )
<<<<<<< Updated upstream
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

=======
                    error_messages.extend(animation_result.get("warnings", ()))
                    imported_results.append(animation_result)
                    imported_animation = True

                else:
                    if detailed_logging:
                        _LOG.debug(
                            "Importing model payload %s%s",
                            file_name,
                            " with materials" if with_materials else "",
                        )
                        if with_materials:
                            _LOG.debug("Appearances to import: %s", appearances)

                    mesh_started = time.perf_counter()
                    try:
                        result = import_mesh_glb(
                            file_path,
                            parent_collection=collection_parent,
                            collection_name=collection_name,
                            import_garment_support=import_garmentsupport,
                            hide_armature=hide_armatures,
                            select_objects=select_objects,
                            transaction=transaction_owner,
                            decoded_mesh_data=decoded_mesh_data,
                            bulk_master=bulk_import,
                        )
                    finally:
                        _record_timing(timing, "mesh_datablocks", mesh_started)
                    repair_warning = result["mesh_data"].repair_warning
                    if repair_warning:
                        error_messages.append(repair_warning)

                    is_terrain = file_name.casefold().startswith("terrain")
                    material_stem = _material_asset_stem(file_name)
                    current_file_base_path = os.path.join(directory, material_stem)
                    depot_path = None
                    json_apps = {}
                    mats = []
                    has_material_json = False
                    material_names_by_submesh = None
                    if with_materials or is_terrain or appearance_variants:
                        material_json_started = time.perf_counter()
                        try:
                            (
                                depot_path,
                                json_apps,
                                mats,
                                has_material_json,
                                source_revision,
                            ) = _load_material_json(
                                current_file_base_path,
                                error_messages,
                                materials,
                            )
                        finally:
                            _record_timing(
                                timing,
                                "material_json",
                                material_json_started,
                            )
                    if has_material_json:
                        material_plan_started = time.perf_counter()
                        try:
                            (
                                material_names_by_submesh,
                                _,
                                _,
                            ) = _requested_submesh_material_plan(
                                result,
                                json_apps,
                                appearances,
                            )
                        finally:
                            _record_timing(
                                timing,
                                "material_plan",
                                material_plan_started,
                            )

                    if is_terrain:
                        apply_terrain_generated_uvs(
                            result,
                            mats,
                            material_names_by_submesh,
                        )

                    if with_materials:
                        if not has_material_json:
                            if not is_physical_scene(file_name):
                                message = (
                                    "Required Material.json not found: "
                                    f"{current_file_base_path}.Material.json"
                                )
                                _LOG.warning("%s", message)
                                error_messages.append(message)
                        else:
                            result["collection"]["cp77_json_apps"] = json.dumps(
                                json_apps
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
                                _LOG.warning("%s", message)
                                error_messages.append(message)
                            else:
                                material_setup_started = time.perf_counter()
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
                                        is_morphtarget=".morphtarget"
                                        in file_name.lower(),
                                        log_timing=detailed_logging,
                                        timing=timing,
                                        material_resources=material_resources,
                                    )
                                except Exception as error:
                                    material_result = {
                                        "failures": (
                                            f"{type(error).__name__}: {error}",
                                        ),
                                        "unprepared": (),
                                    }
                                    debug_exception(_LOG, "Exception details")
                                finally:
                                    _record_timing(
                                        timing,
                                        "material_setup",
                                        material_setup_started,
                                    )
                                failed_materials = material_result.get("failures", ())
                                if failed_materials:
                                    error_messages.append(
                                        "Material setup failed for "
                                        f"{file_name}: {', '.join(failed_materials)}"
                                    )
                                material_warnings = material_result.get("warnings", ())
                                error_messages.extend(
                                    warning
                                    for warning in material_warnings
                                    if warning not in error_messages
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
                                if not failed_materials and not unprepared_materials:
                                    _record_collection_material_coverage(
                                        result["collection"],
                                        file_path,
                                        appearances,
                                        revision=source_revision,
                                    )

                    if appearance_variants:
                        create_mesh_appearance_variants(
                            result,
                            appearances,
                            json_apps,
                            parent_collection=collection_parent,
                        )
                        for obj in result["all_objects"]:
                            if obj.type == "MESH":
                                _apply_object_shadow_policy(
                                    obj,
                                    tuple(
                                        slot.material
                                        for slot in obj.material_slots
                                        if slot.material
                                    ),
                                )
                    if kind == "mixed":
                        context.scene.render.fps = 30
                        context.scene.render.fps_base = 1.0
                        animation_result = _try_direct_animation_import(
                            file_path,
                            context,
                            result.get("armature") or animation_target,
                            import_tracks,
                            detailed_logging,
                        )
                        error_messages.extend(animation_result.get("warnings", ()))
                        imported_results.append(animation_result)
                        imported_animation = True
                    imported_results.append(result)

            for issue in documents.issues[document_issue_start:]:
                if issue.code == "file.missing" and (
                    not with_materials or is_physical_scene(file_name)
                ):
                    continue
                if issue.message not in error_messages:
                    error_messages.append(issue.message)
            if not bulk_import:
                texture_message = image_load_failure_message(image_failures)
                if texture_message:
                    error_messages.append(texture_message)
            if error_messages and not bulk_import:
                import_message(
                    summarize_messages(
                        error_messages,
                        root=split_source_raw_root(file_path)[0],
                    )
                )
            if detailed_logging:
                cache_after = material_cache_stats(include_helpers=False)
                exact_hits = cache_after["exact_hits"] - cache_before["exact_hits"]
                prototype_hits = (
                    cache_after["prototype_hits"] - cache_before["prototype_hits"]
                )
                cache_misses = cache_after["misses"] - cache_before["misses"]
                cache_builds = cache_after["builds"] - cache_before["builds"]
                cache_clones = cache_after["clones"] - cache_before["clones"]
                _LOG.debug(
                    "Material cache: %d exact hits, %d prototype hits, %d shader misses, "
                    "%d shader builds, %d material clones, %d cached exact entries",
                    exact_hits,
                    prototype_hits,
                    cache_misses,
                    cache_builds,
                    cache_clones,
                    cache_after["entries"],
                )
            succeeded = True
        except Exception as error:
            raise_if_rollback_incomplete(
                transaction_owner.rollback()
                if owns_transaction
                else transaction_owner.rollback_to(savepoint),
                error,
            )
            raise
        finally:
            end_image_failure_capture(image_failures)
            if owns_documents and documents is not None:
                documents.close()
            try:
                if original_fps is not None and not (succeeded and imported_animation):
                    context.scene.render.fps, context.scene.render.fps_base = (
                        original_fps
                    )
                elif original_fps is not None and original_fps != (30, 1.0):
                    _LOG.info(
                        "Scene frame rate changed from %.3f to 30 fps to match the imported animation",
                        original_fps[0] / original_fps[1],
                    )
                if context_snapshot is not None:
                    if succeeded and select_objects:
                        context_snapshot.mode = "OBJECT"
                    context_snapshot.restore()
                    if succeeded and select_objects:
                        created = list(
                            dict.fromkeys(
                                obj
                                for item in imported_results
                                for obj in (
                                    item.get("all_objects") or (item.get("armature"),)
                                )
                                if obj is not None and not obj.hide_get()
                            )
                        )
                        if created:
                            selection.select_objects(
                                created, clear=True, context=context
                            )
            finally:
                if transaction_scope_entered:
                    transaction_scope.__exit__(None, None, None)

        if owns_transaction:
            transaction_owner.commit()

    if error_messages and not bulk_import:
        _LOG.warning("Imported GLB %s with %d issue(s)", file_name, len(error_messages))
>>>>>>> Stashed changes
    return ImportResult(
        created_items=tuple(imported_results),
        warnings=unique_messages(error_messages),
        label="direct GLB import",
    )


def _material_user_slots(material):
<<<<<<< Updated upstream
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
=======
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
>>>>>>> Stashed changes

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
<<<<<<< Updated upstream
                ("material_slot", id(user_obj), user_index),
=======
                ("material_slot", rna_identity(user_obj), user_index),
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
                raise RuntimeError("; ".join(messages) or "Material bundle could not be loaded")
            mats = list(bundle.materials)
            with material_resource_scope(material_resources):
                builder = MaterialBuilder(mats, depot_path, "png", base_path)
=======
                raise RuntimeError(
                    "; ".join(messages) or "Material bundle could not be loaded"
                )
            mats = list(bundle.materials)
            with material_resource_scope(material_resources):
                image_format = str(
                    active_material.get("cp77_image_format", "") or "png"
                )
                builder = MaterialBuilder(mats, depot_path, image_format, base_path)
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
=======

>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
        message = str(error)
        if not report.ok:
            message += "; rollback incomplete: " + "; ".join(
                [f"{label}: {detail}" for label, detail in report.failures]
                + list(report.leaked)
            )
        self.report({"ERROR"}, message)
        return {"CANCELLED"}
=======
        raise_if_rollback_incomplete(report, error, error_type=MaterialReloadError)
        raise MaterialReloadError(str(error)) from error
>>>>>>> Stashed changes
    finally:
        if scope is not None:
            scope.__exit__(None, None, None)

    return new_material
