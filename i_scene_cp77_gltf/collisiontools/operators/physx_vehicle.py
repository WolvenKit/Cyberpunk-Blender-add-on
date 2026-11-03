import bpy

from ...blender.operator_results import OperationResult, finish_operator
from ...blender.physics.vehicle_phys import load_vehicle_phys, vehicle_phys_preflight
from ...core.log import debug_exception, get_logger, log_once
from ...core.notifications import import_operation, report
from ..blender.vehicle_config import validate_vehicle
from ..services.scene import build_vehicle_preview, reset_vehicle_session
from ..services.vehicle import (
    autofit_vehicle_configuration,
    setup_vehicle_manual,
    setup_vehicle_selection,
    validate_vehicle_configuration,
)
from ..services.vehicle_authoring import (
    add_vehicle_gear,
    default_tweakxl_export_path,
    export_vehicle_tweakxl,
    move_vehicle_gear,
    refresh_bike,
    remove_vehicle_gear,
    reset_vehicle_gears,
    setup_bike_manual,
    setup_bike_selection,
)
from ..services.vehicle_resolver import (
    apply_base_vehicle,
    base_vehicle_choices,
    clear_resolved_vehicle_data,
    imported_vehicle_record,
    resolve_vehicle_data,
)

_LOG = get_logger(__name__)


def _store_validation_state(vehicle):
    errors, warnings = validate_vehicle(vehicle)
    vehicle.validation_errors = "\n".join(errors)
    vehicle.validation_warnings = "\n".join(warnings)
    if errors:
        vehicle.validation_state = "ERROR"
    elif warnings:
        vehicle.validation_state = "WARNING"
    else:
        vehicle.validation_state = "VALID"
    return errors, warnings


class PHYSX_OT_vehicle_setup_selection(bpy.types.Operator):
    bl_idname = "physx.vehicle_setup_selection"
    bl_label = "Set Up from Selected Rig"
    bl_description = "Resolve the vehicle frame, wheel bones, appearance meshes, and dimensions from the active imported MetaRig"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.active_object is not None
            and context.active_object.type == "ARMATURE"
        )

    def execute(self, context):
        vehicle = context.scene.physx_vehicle
        if vehicle.vehicle_kind == "BIKE":
            result = setup_bike_selection(context)
        else:
            result = setup_vehicle_selection(context)
        if result.ok:
            # The imported entity's own record is the vehicle the export builds on.
            vehicle.tweakxl_base_record = (
                imported_vehicle_record(vehicle, context) or vehicle.tweakxl_base_record
            )
        return finish_operator(self, result)

    def invoke(self, context, event):
        return self.execute(context)


class PHYSX_OT_vehicle_setup_manual(bpy.types.Operator):
    bl_idname = "physx.vehicle_setup_manual"
    bl_label = "Set Up from Meshes"
    bl_description = "Use the active chassis mesh and the selected wheel meshes"

    def execute(self, context):
        if context.scene.physx_vehicle.vehicle_kind == "BIKE":
            return finish_operator(self, setup_bike_manual(context))
        return finish_operator(self, setup_vehicle_manual(context))


class PHYSX_OT_vehicle_autofit(bpy.types.Operator):
    bl_idname = "physx.vehicle_autofit"
    bl_label = "Refresh and Fit"

    def execute(self, context):
        if context.scene.physx_vehicle.vehicle_kind == "BIKE":
            try:
                refresh_bike(context.scene.physx_vehicle)
            except Exception as error:
                return finish_operator(
                    self, OperationResult.cancelled(str(error), error=error)
                )
            return finish_operator(
                self, OperationResult.finished("Bike geometry refreshed")
            )
        return finish_operator(self, autofit_vehicle_configuration(context))


_base_vehicle_items = []


def _base_vehicle_enum_items(_self, context):
    """The search list of base vehicles"""
    try:
        choices = base_vehicle_choices(context.scene.physx_vehicle, context)
    except Exception as error:
        log_once(
            _LOG,
            "DEBUG",
            ("base vehicles", type(error).__name__),
            "Base vehicle list failed",
            exc_info=True,
        )
        _base_vehicle_items[:] = [("", f"Vehicles unavailable: {error}", "")]
        return _base_vehicle_items
    _base_vehicle_items[:] = [
        (record_id, label, record_id) for record_id, label in choices
    ]
    return _base_vehicle_items


class PHYSX_OT_vehicle_apply_archetype(bpy.types.Operator):
    bl_idname = "physx.vehicle_apply_archetype"
    bl_label = "Apply Base Vehicle"
    bl_description = (
        "Take the handling of a game vehicle, keeping the vehicle's own geometry"
    )
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "record"

    record: bpy.props.EnumProperty(name="Vehicle", items=_base_vehicle_enum_items)

    def execute(self, context):
        # Without a chosen record (a script call) the selected built-in preset applies.
        record = self.record if self.properties.is_property_set("record") else ""
        return finish_operator(self, apply_base_vehicle(context, record))

    def invoke(self, context, event):
        imported = imported_vehicle_record(context.scene.physx_vehicle, context)
        if imported:
            self.record = imported
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class PHYSX_OT_vehicle_gear_add(bpy.types.Operator):
    bl_idname = "physx.vehicle_gear_add"
    bl_label = "Add Forward Gear"
    bl_description = "Add an authored forward gear to the vehicle gearbox"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return finish_operator(self, add_vehicle_gear(context.scene.physx_vehicle))


class PHYSX_OT_vehicle_gear_remove(bpy.types.Operator):
    bl_idname = "physx.vehicle_gear_remove"
    bl_label = "Remove Forward Gear"
    bl_description = "Remove the selected forward gear"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return finish_operator(self, remove_vehicle_gear(context.scene.physx_vehicle))


class PHYSX_OT_vehicle_gear_move(bpy.types.Operator):
    bl_idname = "physx.vehicle_gear_move"
    bl_label = "Move Forward Gear"
    bl_description = "Change the selected forward gear's order in the transmission"
    bl_options = {"REGISTER", "UNDO"}

    direction: bpy.props.EnumProperty(
        items=(
            ("UP", "Earlier", "Move the selected gear earlier in the gearbox"),
            ("DOWN", "Later", "Move the selected gear later in the gearbox"),
        ),
        default="UP",
    )

    def execute(self, context):
        return finish_operator(
            self,
            move_vehicle_gear(context.scene.physx_vehicle, self.direction),
        )


class PHYSX_OT_vehicle_gear_reset(bpy.types.Operator):
    bl_idname = "physx.vehicle_gear_reset"
    bl_label = "Restore Gearbox"
    bl_description = "Restore the resolved Cyberpunk gearbox when available, otherwise create the production starter gearbox"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return finish_operator(self, reset_vehicle_gears(context.scene.physx_vehicle))


class PHYSX_OT_vehicle_export_tweakxl(bpy.types.Operator):
    bl_idname = "physx.vehicle_export_tweakxl"
    bl_label = "Export TweakXL Vehicle YAML"
    bl_description = "Export the configured vehicle as a TweakXL YAML record"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filename_ext = ".yaml"
    filter_glob: bpy.props.StringProperty(default="*.yaml;*.yml", options={"HIDDEN"})

    def check(self, context):
        if self.filepath.casefold().endswith((".yaml", ".yml")):
            return False
        self.filepath += ".yaml"
        return True

    def execute(self, context):
        return finish_operator(
            self, export_vehicle_tweakxl(context.scene.physx_vehicle, self.filepath)
        )

    def invoke(self, context, event):
        self.filepath = default_tweakxl_export_path(context.scene.physx_vehicle)
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class PHYSX_OT_vehicle_validate(bpy.types.Operator):
    bl_idname = "physx.vehicle_validate"
    bl_label = "Validate Vehicle"
    bl_description = "Run production validation and keep the result visible in the vehicle authoring workspace"

    def execute(self, context):
        vehicle = context.scene.physx_vehicle
        try:
            _store_validation_state(vehicle)
        except Exception as error:
            vehicle.validation_state = "ERROR"
            vehicle.validation_errors = str(error)
            vehicle.validation_warnings = ""
            return finish_operator(
                self, OperationResult.cancelled(str(error), error=error)
            )
        return finish_operator(self, validate_vehicle_configuration(context))


class PHYSX_OT_vehicle_load_game_data(bpy.types.Operator):
    bl_idname = "physx.vehicle_load_game_data"
    bl_label = "Load Game Data"
    bl_description = (
        "Load the imported vehicle's handling from the game and your project's tweaks, "
        "and its chassis collision"
    )
    bl_options = {"REGISTER", "UNDO"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filename_ext = ".phys.json"
    filter_glob: bpy.props.StringProperty(default="*.phys.json", options={"HIDDEN"})
    handling_loaded: bpy.props.BoolProperty(
        default=False, options={"HIDDEN", "SKIP_SAVE"}
    )

    @classmethod
    def poll(cls, context):
        vehicle = getattr(context.scene, "physx_vehicle", None)
        return (
            vehicle is not None
            and vehicle.rig is not None
            and vehicle.rig.type == "ARMATURE"
        )

    def _load_handling(self, context):
        result = resolve_vehicle_data(context)
        self.handling_loaded = result.ok
        return result

    def _finish(self, context, collision):
        vehicle = context.scene.physx_vehicle
        name = vehicle.game_data_record.rsplit(".", 1)[-1] or "the vehicle"
        message = f"Loaded {name}" + (
            " with its chassis collision" if collision else ""
        )
        report(self, "INFO", message, logger=_LOG)
        for warning in vehicle.game_data_warnings.splitlines():
            if warning:
                report(self, "WARNING", warning, logger=_LOG)
        return {"FINISHED"}

    @import_operation
    def execute(self, context):
        if not self.handling_loaded:
            result = self._load_handling(context)
            if not result.ok:
                return finish_operator(self, result)
        rig = context.scene.physx_vehicle.rig
        try:
            missing = vehicle_phys_preflight(context, rig)
            if missing is None:
                return self._finish(context, False)
            filepath = self.filepath or missing.get("local_path", "")
            if not filepath:
                return finish_operator(
                    self,
                    OperationResult.cancelled(
                        "Choose the chassis .phys.json the vehicle uses"
                    ),
                )
            load_vehicle_phys(
                context, rig, filepath, target_collection=missing.get("collection")
            )
        except Exception as error:
            return finish_operator(
                self, OperationResult.cancelled(str(error), error=error)
            )
        return self._finish(context, True)

    def invoke(self, context, event):
        result = self._load_handling(context)
        if not result.ok:
            return finish_operator(self, result)
        try:
            missing = vehicle_phys_preflight(context, context.scene.physx_vehicle.rig)
        except Exception as error:
            return finish_operator(
                self, OperationResult.cancelled(str(error), error=error)
            )
        if missing is None or missing.get("local_path"):
            return self.execute(context)
        depot_path = str(missing.get("depot_path", "") or "").replace("\\", "/")
        if depot_path:
            self.filepath = depot_path.rsplit("/", 1)[-1] + ".json"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class PHYSX_OT_vehicle_clear_data(bpy.types.Operator):
    bl_idname = "physx.vehicle_clear_data"
    bl_label = "Clear Game Data"

    def execute(self, context):
        clear_resolved_vehicle_data(context.scene.physx_vehicle)
        report(self, "INFO", "Resolved vehicle game data cleared", logger=_LOG)
        return {"FINISHED"}


class PHYSX_OT_vehicle_build(bpy.types.Operator):
    bl_idname = "physx.vehicle_build"
    bl_label = "Build Vehicle Preview"

    def execute(self, context):
        result = build_vehicle_preview(context)
        if result.ok:
            vehicle = context.scene.physx_vehicle
            try:
                _store_validation_state(vehicle)
            except Exception as error:
                debug_exception(_LOG, "Could not store the vehicle validation state")
                vehicle.validation_state = "ERROR"
                vehicle.validation_errors = str(error)
                vehicle.validation_warnings = ""
        return finish_operator(self, result)


class PHYSX_OT_vehicle_reset(bpy.types.Operator):
    bl_idname = "physx.vehicle_reset"
    bl_label = "Reset Vehicle Preview"

    def execute(self, context):
        return finish_operator(self, reset_vehicle_session(context))
