from __future__ import annotations

import json
import os

from ...assetio.documents import DocumentSession
from ...assetio.index import IndexPolicy, build_asset_index
from ...assetio.paths import normalize_local_path, split_source_raw_root
from ...blender.operator_results import OperationResult
from ...core.addon_identity import get_addon_preferences
from ...core.log import debug_exception, get_logger
from ...physics.domain.vehicle.game_data import (
    entity_appearance_names,
    entity_vehicle_data,
    entity_vehicle_records,
    player_vehicle_records,
    resolve_vehicle_game_data,
    vehicle_record_label,
    vehicle_variants,
)
from ...physics.model.vehicle.archetypes import ARCHETYPES, archetype
from ...physics.services.vehicle_curves import (
    VEHICLE_CURVE_EXTENSIONS,
    vehicle_curve_loader,
)
from ...physics.services.vehicle_tweaks import (
    load_vehicle_tweak_database,
    vehicle_tweak_sources,
)
from ..blender.vehicle_authoring_state import ensure_axle_authoring
from ..blender.vehicle_gears import populate_gear_collection

_LOG = get_logger(__name__)
_base_vehicle_choices = {}
_record_variants = {}


def _entity_collection(vehicle):
    collection = vehicle.appearance_collection
    if collection is None or not collection.get("cp77_entity_imported", False):
        raise ValueError(
            "Resolve an imported entity appearance from the vehicle MetaRig first"
        )
    return collection


def _entity_source(collection):
    entity_source = str(collection.get("cp77_entity_source", "") or "")
    if not entity_source:
        raise ValueError("The imported entity collection has no source document path")
    return entity_source


def game_directory(context=None):
    preferences = get_addon_preferences(context, required=False)
    return (
        str(getattr(preferences, "game_directory", "") or "")
        if preferences is not None
        else ""
    )


def project_source(vehicle):
    """The exported entity the vehicle was imported from, or ''"""
    collection = getattr(vehicle, "appearance_collection", None)
    if collection is None:
        return ""
    return str(collection.get("cp77_entity_source", "") or "")


def _tweak_sources(vehicle, context):
    """The vehicle's tweak sources"""
    return vehicle_tweak_sources(
        game_directory(context), vehicle.vehicle_tweak_root, project_source(vehicle)
    )


def _resource_root(vehicle):
    """The folder vehicle curves are read from"""
    source = project_source(vehicle)
    root = vehicle.vehicle_resource_root or (
        split_source_raw_root(source)[0] if source else ""
    )
    return normalize_local_path(root) if root else ""


def _imported_entity(vehicle):
    """(depot path, appearance, exported entity) of the imported entity, or None"""
    collection = getattr(vehicle, "appearance_collection", None)
    if collection is None or not collection.get("cp77_entity_imported", False):
        return None
    entity_path = str(collection.get("depotPath", "") or "")
    if not entity_path:
        return None
    return (
        entity_path,
        str(collection.get("appearanceName", "") or ""),
        str(collection.get("cp77_entity_source", "") or ""),
    )


def _imported_appearance_names(entity):
    """The entity's names for the imported appearance"""
    _entity_path, appearance, source = entity
    if not appearance or not source:
        return ()
    try:
        with DocumentSession() as documents:
            return entity_appearance_names(documents.payload(source), appearance)
    except Exception:
        debug_exception(_LOG, "Could not read the appearances of %s", source)
        return ()


def _entity_record(database, entity):
    """The best guess at the imported entity's record, or ''"""
    records = entity_vehicle_records(
        database, entity[0], _imported_appearance_names(entity)
    )
    return records[0].record_id if records else ""


def _base_vehicles(vehicle, context):
    """(choices, imported record) for the vehicle's kind"""
    kind = str(getattr(vehicle, "vehicle_kind", "CAR") or "CAR")
    try:
        sources = _tweak_sources(vehicle, context)
    except ValueError:
        return tuple(
            (item.record_id, item.label)
            for item in ARCHETYPES.values()
            if item.kind == kind
        ), ""
    entity = _imported_entity(vehicle)
    key = (
        sources.base_key,
        sources.override_files,
        sources.compiled_tweakdb,
        kind,
        entity,
    )
    cached = _base_vehicle_choices.get(key)
    if cached is None:
        database = load_vehicle_tweak_database(sources)
        choices = sorted(
            (
                (record_id, vehicle_record_label(record_id))
                for record_id in player_vehicle_records(database, kind)
            ),
            key=lambda choice: (choice[1].casefold(), choice[0]),
        )
        imported = _entity_record(database, entity) if entity else ""
        if imported:
            choices = [(imported, vehicle_record_label(imported))] + [
                c for c in choices if c[0] != imported
            ]
        cached = (tuple(choices), imported)
        _base_vehicle_choices.clear()
        _base_vehicle_choices[key] = cached
    return cached


def base_vehicle_choices(vehicle, context=None):
    """(record, label) pairs of the vehicles a base can be taken from"""
    return _base_vehicles(vehicle, context)[0]


def imported_vehicle_record(vehicle, context=None):
    """The game record of the imported entity the vehicle was set up from, or ''"""
    try:
        return _base_vehicles(vehicle, context)[1]
    except Exception:
        debug_exception(_LOG, "Imported vehicle record unavailable")
        return ""


def record_override_choices(vehicle, context=None):
    """(record, label) pairs for the Vehicle Record Override"""
    sources = _tweak_sources(vehicle, context)
    base = vehicle.tweakxl_base_record.strip() or imported_vehicle_record(
        vehicle, context
    )
    if not base:
        return ()
    entity = _imported_entity(vehicle)
    key = (
        sources.base_key,
        sources.override_files,
        sources.compiled_tweakdb,
        entity,
        base,
    )
    cached = _record_variants.get(key)
    if cached is None:
        database = load_vehicle_tweak_database(sources)
        appearances = _imported_appearance_names(entity) if entity else ()
        variants = (
            vehicle_variants(database, base, appearances)
            if database.has_record(base)
            else ()
        )
        cached = tuple(
            (record.record_id, vehicle_record_label(record.record_id))
            for record in variants
        )
        _record_variants.clear()
        _record_variants[key] = cached
    return cached


def _load_vehicle_tweaks(vehicle, context):
    """(sources, database, warnings) of the vehicle's tweak database"""
    sources = _tweak_sources(vehicle, context)
    database = load_vehicle_tweak_database(sources)
    _LOG.debug("Vehicle tweaks: %s", sources.summary)
    warnings = tuple(
        line for line in database.diagnostics if line.startswith("Skipped ")
    )
    for warning in warnings:
        _LOG.info("Vehicle tweak override %s", warning)
    return sources, database, warnings


def _resolve(documents, vehicle, database, record_id):
    """The game data of record_id, its curves read through documents from the vehicle's resource root"""
    resource_root = _resource_root(vehicle)
    curve_loader = None
    if resource_root and os.path.isdir(resource_root):
        resource_index = build_asset_index(
            resource_root, VEHICLE_CURVE_EXTENSIONS, policy=IndexPolicy.REUSE
        )
        curve_loader = vehicle_curve_loader(resource_index, documents)
    return resolve_vehicle_game_data(database, record_id, curve_loader=curve_loader)


def _apply_config(vehicle, config):
    vehicle.chassis_mass = float(config["chassis_mass"])
    vehicle.total_mass = float(config.get("total_mass", config["chassis_mass"]))
    vehicle.chassis_cm_offset = tuple(config["chassis_cm_source"])
    inertia = config.get("chassis_inertia")
    vehicle.use_chassis_inertia = (
        isinstance(inertia, (list, tuple)) and len(inertia) == 3
    )
    if vehicle.use_chassis_inertia:
        vehicle.chassis_inertia = tuple(float(value) for value in inertia)
    vehicle.air_resistance_factor = float(config.get("air_resistance_factor", 1.0))
    vehicle.braking_friction_factor = float(config.get("braking_friction_factor", 1.0))
    vehicle.turning_roll_factor = float(config.get("turning_roll_factor", 1.0))
    vehicle.wheel_turn_max_add_per_second = float(
        config.get("wheel_turn_add_rate", 90.0)
    )
    vehicle.wheel_turn_max_sub_per_second = float(
        config.get("wheel_turn_sub_rate", 90.0)
    )
    vehicle.engine_peak_torque = float(config["engine_peak_torque"])
    vehicle.engine_max_omega = float(config["engine_max_omega"])
    vehicle.engine_moi = float(config.get("engine_moi", 1.0))
    vehicle.engine_resistance_torque = float(
        config.get("engine_damping_rate", 0.15)
    ) * float(config["engine_max_omega"])
    vehicle.gear_switch_time = float(config["gear_switch_time"])
    vehicle.final_gear_torque_decimation = float(
        config.get("final_gear_torque_decimation", 1.0)
    )
    vehicle.axle_authoring_initialized = False
    ensure_axle_authoring(vehicle, config)
    populate_gear_collection(vehicle, config)
    if config.get("vehicle_kind") == "BIKE":
        vehicle.bike_max_lean_angle = float(
            config.get("bike_max_lean_angle", vehicle.bike_max_lean_angle)
        )
        vehicle.bike_tilt_pid = tuple(
            config.get("bike_tilt_pid", vehicle.bike_tilt_pid)
        )
        vehicle.bike_tilt_speed = float(
            config.get("bike_tilt_speed", vehicle.bike_tilt_speed)
        )
        vehicle.bike_tilt_return_speed = float(
            config.get("bike_tilt_return_speed", vehicle.bike_tilt_return_speed)
        )
        vehicle.bike_tilt_custom_speed = float(
            config.get("bike_tilt_custom_speed", vehicle.bike_tilt_custom_speed)
        )
        vehicle.bike_max_com_long_offset = float(
            config.get("bike_max_com_long_offset", vehicle.bike_max_com_long_offset)
        )
        vehicle.bike_min_com_long_offset = float(
            config.get("bike_min_com_long_offset", vehicle.bike_min_com_long_offset)
        )
        vehicle.bike_com_offset_damp_factor = float(
            config.get(
                "bike_com_offset_damp_factor", vehicle.bike_com_offset_damp_factor
            )
        )


def _store_game_data(vehicle, game_data, warnings):
    """Give the vehicle the handling of game_data, and keep its record and warnings with warnings"""
    config = dict(game_data.config)
    _apply_config(vehicle, config)
    vehicle.game_data_config = json.dumps(config, separators=(",", ":"), sort_keys=True)
    vehicle.game_data_record = game_data.record_id
    vehicle.game_data_warnings = "\n".join((*game_data.warnings, *warnings))
    vehicle.game_data_enabled = True
    vehicle.tweakxl_base_record = game_data.record_id


def clear_resolved_vehicle_data(vehicle):
    vehicle.game_data_enabled = False
    vehicle.game_data_config = ""
    vehicle.game_data_record = ""
    vehicle.game_data_warnings = ""


def resolve_vehicle_data(context):
    vehicle = context.scene.physx_vehicle
    try:
        collection = _entity_collection(vehicle)
        entity_source = _entity_source(collection)

        progress = context.window_manager
        progress.progress_begin(0, 100)
        try:
            sources, database, override_warnings = _load_vehicle_tweaks(
                vehicle, context
            )
            progress.progress_update(60)

            entity_path = str(collection.get("depotPath", "") or "")
            appearance_name = str(collection.get("appearanceName", "") or "")
            with DocumentSession() as documents:
                entity_document = documents.payload(entity_source)
                entity_data = entity_vehicle_data(entity_document, entity_path)
                record_id = vehicle.game_data_record_override.strip()
                if record_id and not database.has_record(record_id):
                    raise ValueError(
                        f"Vehicle Record Override {record_id} is not in the vehicle tweaks"
                    )
                if not record_id:
                    records = entity_vehicle_records(
                        database,
                        entity_data.entity_path or entity_path,
                        entity_appearance_names(entity_document, appearance_name),
                    )
                    if not records:
                        raise ValueError(
                            f"No vehicle tweak record references {entity_data.entity_path or entity_path}"
                        )
                    record_id = records[0].record_id
                game_data = _resolve(documents, vehicle, database, record_id)
            progress.progress_update(90)

            vehicle.vehicle_kind = str(game_data.config.get("vehicle_kind", "CAR"))
            _store_game_data(vehicle, game_data, override_warnings)
            progress.progress_update(100)
        finally:
            progress.progress_end()
    except Exception as error:
        return OperationResult.cancelled(str(error), error=error)
    warnings = tuple(line for line in vehicle.game_data_warnings.splitlines() if line)
    if warnings:
        return OperationResult.finished(
            "Resolved vehicle game data; " + "; ".join(warnings),
            "WARNING",
            warnings=warnings,
        )
    overrides = len(sources.override_files)
    if overrides:
        return OperationResult.finished(
            f"Resolved vehicle game data with {overrides} project tweak file{'s' if overrides != 1 else ''}"
        )
    return OperationResult.finished("Resolved vehicle game data")


def apply_base_vehicle(context, record_id=""):
    """Seeds the authoring values from a game vehicle record or the selected preset"""
    vehicle = context.scene.physx_vehicle
    record_id = str(record_id or "") or archetype(vehicle.vehicle_archetype).record_id
    label = vehicle_record_label(record_id)
    try:
        _sources, database, _warnings = _load_vehicle_tweaks(vehicle, context)
        with DocumentSession() as documents:
            game_data = _resolve(documents, vehicle, database, record_id)
        kind = str(game_data.config.get("vehicle_kind", "CAR"))
        if kind != vehicle.vehicle_kind:
            raise ValueError(
                f"{label} is a {kind.lower()}; set the vehicle type to match first"
            )
        _store_game_data(vehicle, game_data, ())
    except Exception as error:
        return OperationResult.cancelled(str(error), error=error)
    return OperationResult.finished(f"Applied {label}")
