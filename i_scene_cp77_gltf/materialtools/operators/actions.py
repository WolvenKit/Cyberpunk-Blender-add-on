import os

import bpy
from bpy.props import (
    EnumProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import Operator

from ...blender.operator_results import execute_operation
from ...blender.transactions import (
    DatablockImportTransaction,
    rollback_report_message,
)
from ...core.log import get_logger, log_once
from ...core.notifications import (
    import_operation,
    report,
)
from ...importers.mesh.orchestration import MaterialReloadError, reload_materials
from ...materials.blender import multilayer as multilayer_service
from ..application.execution import (
    create_material_from_template,
    load_depot_microblends,
    load_multilayer_template,
    scan_multilayer_templates,
)
from ..application.options import (
    MATERIAL_TEMPLATE_COOKED_EXTENSION,
    MATERIAL_TEMPLATE_EXTENSION,
    MULTILAYER_TEMPLATE_EXTENSION,
)
from ..common.access import (
    active_material,
    active_mesh,
)
from ..common.sync import material_sync_guard
from ..depot.paths import resolve_template_json_path
from ..depot.state import (
    ensure_material_depot_path,
    selected_template_palette,
    sync_palette_index,
)
from ..multilayer.editor import apply_template_to_shader, synchronize_panel
from ..multilayer.palette import clear_palette_caches
from ..multilayer.state import resolve_material_state
from ..painting.masks import (
    generate_mask_images,
    toggle_texture_paint,
)
from ..workflows.creation import (
    create_multilayer_material,
    create_multilayer_object,
    relocate_mesh_material,
)

_LOG = get_logger(__name__)

_MASK_DIMENSION_ITEMS = [
    ("128", "128", "128 x 128"),
    ("256", "256", "256 x 256"),
    ("512", "512", "512 x 512"),
    ("1024", "1024", "1024 x 1024"),
    ("2048", "2048", "2048 x 2048"),
    (
        "4096",
        "4096 (recommended to downscale before export)",
        "4096 x 4096 (recommended to downscale before export)",
    ),
]


def _rollback_operator_transaction(owner, transaction, message):
    summary = transaction.rollback()
    detail = rollback_report_message(summary)
    if detail:
        report(owner, "ERROR", f"{message}; rollback incomplete: {detail}", logger=_LOG)
    return {"CANCELLED"}


def _run_override_generation(owner, callback):
    transaction = DatablockImportTransaction()
    try:
        with transaction.scope():
            result = callback()
        if not isinstance(result, set):
            report(
                owner,
                "ERROR",
                "Override generation returned an invalid operator status.",
                logger=_LOG,
            )
            return _rollback_operator_transaction(
                owner, transaction, "Override generation failed"
            )
        if "FINISHED" not in result:
            return _rollback_operator_transaction(
                owner, transaction, "Override generation was cancelled"
            )
        transaction.commit()
        return result
    except Exception as error:
        report(
            owner,
            "ERROR",
            f"Override generation failed: {error}",
            logger=_LOG,
            error=error,
        )
        return _rollback_operator_transaction(
            owner, transaction, "Override generation failed"
        )


def _multilayer_material(context):
    material = active_material(context)
    if material is None:
        return None
    try:
        if not material.use_nodes or material.node_tree is None:
            return None
        return material if material.get("MLSetup") is not None else None
    except (AttributeError, ReferenceError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_multilayer_material", type(error).__name__),
            "multilayer material: fell back after %s",
            error,
            exc_info=True,
        )
        return None


class CP77MlSetupSelectLayer(Operator):
    bl_idname = "cp77.select_multilayer_layer"
    bl_label = "Select Multilayer Layer"
    bl_description = "Make this linked multilayer layer active in Material Tools"

    layer_index: IntProperty(name="Layer", min=1, max=20, default=1)

    @classmethod
    def poll(cls, context):
        return _multilayer_material(context) is not None

    def execute(self, context):
        state = resolve_material_state(context, layer_index=self.layer_index)
        if state.layer_node is None:
            report(
                self, "WARNING", f"Layer {self.layer_index} is not linked.", logger=_LOG
            )
            return {"CANCELLED"}
        context.scene.cp77_ml_props.multilayer_index_int = self.layer_index
        synchronize_panel(context)
        return {"FINISHED"}


class CP77MlSetupGenerateOverrides(Operator):
    bl_idname = "generate_layer_overrides.mlsetup"
    bl_label = "Rebuild Override Palettes"
    bl_description = "Rebuild multilayer override palettes for the active material"

    @classmethod
    def poll(cls, context):
        return _multilayer_material(context) is not None

    def execute(self, context):
        result = _run_override_generation(
            self,
            lambda: multilayer_service.cp77_mlsetup_generateoverrides(self, context),
        )
        clear_palette_caches()
        synchronize_panel(context)
        return result


class CP77MlSetupGenerateOverridesDisconnected(Operator):
    bl_idname = "generate_layer_overrides_disconnected.mlsetup"
    bl_label = "Rebuild All Override Palettes"
    bl_description = "Rebuild multilayer override palettes for all layer nodes in the active material"

    @classmethod
    def poll(cls, context):
        return _multilayer_material(context) is not None

    def execute(self, context):
        result = _run_override_generation(
            self,
            lambda: multilayer_service.cp77_mlsetup_generateoverrides(
                self,
                context,
                objs=(context.active_object,),
                include_disconnected=True,
            ),
        )
        clear_palette_caches()
        synchronize_panel(context)
        return result


class CP77MlSetupRefreshOverrides(Operator):
    bl_idname = "refresh_layer.mlsetup"
    bl_label = "Refresh Layer"
    bl_description = "Refresh the active multilayer layer data"

    @classmethod
    def poll(cls, context):
        return _multilayer_material(context) is not None

    def execute(self, context):
        synchronize_panel(context)
        return {"FINISHED"}


class CP77MlSetupEnterTexturePaint(Operator):
    bl_idname = "enter_texture_paint.mlsetup"
    bl_label = "Paint Mask"
    bl_description = (
        "Enter or leave Texture Paint mode for the selected multilayer mask"
    )

    @classmethod
    def poll(cls, context):
        if context.mode == "PAINT_TEXTURE":
            return True
        state = resolve_material_state(context)
        return state.valid_layer and state.mask_node is not None

    def execute(self, context):
        return toggle_texture_paint(self, context)


class CP77MlSetupGenerateActiveMask(Operator):
    bl_idname = "generate_active_mask.mlsetup"
    bl_label = "Create Active Layer Mask"
    bl_description = "Create an image mask for the active multilayer layer"
    bl_options = {"REGISTER", "UNDO"}

    dimensions: EnumProperty(
        name="Mask Resolution",
        description="Sets the generated mask image dimensions",
        items=_MASK_DIMENSION_ITEMS,
        default="1024",
    )

    @classmethod
    def poll(cls, context):
        state = resolve_material_state(context)
        return state.valid_layer and state.layer_index > 1

    def execute(self, context):
        state = resolve_material_state(context)
        if not state.valid_layer or state.layer_index <= 1:
            report(self, "WARNING", "Select a non-base multilayer layer.", logger=_LOG)
            return {"CANCELLED"}
        return execute_operation(
            self,
            "Mask generation",
            generate_mask_images,
            context,
            self.dimensions,
            layer_indices={state.layer_index},
        )


class CP77MlSetupGenerateMasks(Operator):
    bl_idname = "generate_masks.mlsetup"
    bl_label = "Generate Layer Masks"
    bl_description = "Create missing image masks for linked multilayer layers"
    bl_options = {"REGISTER", "UNDO"}

    dimensions: EnumProperty(
        name="Mask Resolution",
        description="Sets the generated mask image dimensions",
        items=_MASK_DIMENSION_ITEMS,
        default="1024",
    )

    @classmethod
    def poll(cls, context):
        return _multilayer_material(context) is not None

    def execute(self, context):
        return execute_operation(
            self, "Mask generation", generate_mask_images, context, self.dimensions
        )


class CP77MlSetupCreateMultilayerObject(Operator):
    bl_idname = "create_multilayer_object.mlsetup"
    bl_label = "Create Multilayer Object"
    bl_description = "Create an object with a material ready for multilayer editing"
    bl_options = {"REGISTER", "UNDO"}

    dimensions: EnumProperty(
        name="Mask Resolution",
        description="Sets the generated mask image dimensions",
        items=_MASK_DIMENSION_ITEMS,
        default="1024",
    )

    @classmethod
    def poll(cls, context):
        return getattr(context, "mode", "OBJECT") == "OBJECT"

    @import_operation
    def execute(self, context):
        return execute_operation(
            self,
            "Multilayer object creation",
            create_multilayer_object,
            context,
            self.dimensions,
        )


class CP77MlSetupCreateMultilayerMaterial(Operator):
    bl_idname = "create_multilayer_material.mlsetup"
    bl_label = "Create Multilayer Material"
    bl_description = (
        "Create a material ready for multilayer editing on the active object"
    )
    bl_options = {"REGISTER", "UNDO"}

    dimensions: EnumProperty(
        name="Mask Resolution",
        description="Sets the generated mask image dimensions",
        items=_MASK_DIMENSION_ITEMS,
        default="1024",
    )

    @classmethod
    def poll(cls, context):
        return (
            getattr(context, "mode", "OBJECT") == "OBJECT"
            and active_mesh(context) is not None
        )

    def execute(self, context):
        return execute_operation(
            self,
            "Multilayer material creation",
            create_multilayer_material,
            context,
            self.dimensions,
        )


class CP77MlSetupRelocateMesh(Operator):
    bl_idname = "relocate_mesh.mlsetup"
    bl_label = "Relocate Mesh"
    bl_description = "Relocate the GLB and update material source paths"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(
        name="File Path",
        description="Path to the GLB file",
        subtype="FILE_PATH",
    )
    filter_glob: StringProperty(default="*.glb", options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return active_material(context) is not None

    def execute(self, context):
        return relocate_mesh_material(self, context, self.filepath)

    def invoke(self, context, _event):
        if not self.poll(context):
            report(self, "ERROR", "Select a mesh with an active material.", logger=_LOG)
            return {"CANCELLED"}
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class CP77_OT_LoadMaterialTemplate(Operator):
    bl_idname = "cp77.load_material_template"
    bl_label = "Load Material Template"
    bl_description = "Create a Blender material from an exported Cyberpunk .mt template"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(name="Material Template", subtype="FILE_PATH")
    filter_glob: StringProperty(
        default=f"*{MATERIAL_TEMPLATE_EXTENSION};*{MATERIAL_TEMPLATE_COOKED_EXTENSION}",
        options={"HIDDEN"},
    )

    def invoke(self, context, _event):
        depot_root = ensure_material_depot_path(context)
        if depot_root and os.path.isdir(depot_root):
            self.filepath = os.path.join(depot_root, "")
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    @import_operation
    def execute(self, context):
        try:
            template_json = resolve_template_json_path(self.filepath)
            props = context.scene.cp77_ml_props
            depot_root = ensure_material_depot_path(context, props)
            result = create_material_from_template(context, template_json, depot_root)
            props.material_depot_path = result.depot_root
            if result.assigned_count:
                report(
                    self,
                    "INFO",
                    f"Created {result.material.name} and assigned it to "
                    f"{result.assigned_count} mesh object(s).",
                    logger=_LOG,
                )
            else:
                report(
                    self,
                    "INFO",
                    f"Created {result.material.name}; select a mesh to assign it.",
                    logger=_LOG,
                )
            return {"FINISHED"}
        except Exception as error:
            report(self, "ERROR", str(error), logger=_LOG, error=error)
            return {"CANCELLED"}


class CP77_OT_LoadDepotMicroblends(Operator):
    bl_idname = "cp77.load_depot_microblends"
    bl_label = "Load Depot Microblends"
    bl_description = "Scan the Material Tools depot and load every image whose path contains microblend"
    bl_options = {"REGISTER", "UNDO"}

    @import_operation
    def execute(self, context):
        props = context.scene.cp77_ml_props
        root = ensure_material_depot_path(context, props)
        if not os.path.isdir(root):
            report(
                self,
                "ERROR",
                "Select a valid material depot folder in Material Tools.",
                logger=_LOG,
            )
            return {"CANCELLED"}
        try:
            result = load_depot_microblends(root)
        except Exception as error:
            report(self, "ERROR", str(error), logger=_LOG, error=error)
            return {"CANCELLED"}
        if not result.succeeded and not result.failures:
            report(
                self,
                "WARNING",
                "No microblend images were found in the depot",
                logger=_LOG,
            )
            return {"CANCELLED"}

        failure_text = f"; {len(result.failures)} failed" if result.failures else ""
        collision_text = (
            f"; {result.collision_count} path collision(s)"
            if result.collision_count
            else ""
        )
        message = (
            f"Loaded {result.loaded_count} microblend image(s); "
            f"{result.existing_count} already present{failure_text}{collision_text}"
        )
        if result.failures:
            _LOG.warning(
                "Microblend image scan: %d failure(s); first: %s",
                len(result.failures),
                "; ".join(result.failures[:3]),
            )
            _LOG.debug(
                "Microblend image scan failures:\n  %s", "\n  ".join(result.failures)
            )
        report(self, {"WARNING"} if result.failures else {"INFO"}, message, logger=_LOG)
        return {"FINISHED"} if result.succeeded else {"CANCELLED"}


class CP77_OT_LoadMultilayerTemplate(Operator):
    bl_idname = "cp77.load_multilayer_template"
    bl_label = "Add Multilayer Template"
    bl_description = (
        "Load one exported Cyberpunk .mltemplate.json into the Material Tools library"
    )
    bl_options = {"REGISTER"}

    filepath: StringProperty(name="Multilayer Template", subtype="FILE_PATH")
    filter_glob: StringProperty(
        default=f"*{MULTILAYER_TEMPLATE_EXTENSION}", options={"HIDDEN"}
    )

    def invoke(self, context, _event):
        root = ensure_material_depot_path(context)
        if root and os.path.isdir(root):
            self.filepath = os.path.join(root, "")
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    @import_operation
    def execute(self, context):
        try:
            props = context.scene.cp77_ml_props
            root = ensure_material_depot_path(context, props)
            result = load_multilayer_template(self.filepath, root)
            with material_sync_guard():
                sync_palette_index(props, result.palette)
            report(self, "INFO", f"Loaded {result.template_path}", logger=_LOG)
            return {"FINISHED"}
        except Exception as error:
            report(self, "ERROR", str(error), logger=_LOG, error=error)
            return {"CANCELLED"}


class CP77_OT_ApplyMultilayerTemplate(Operator):
    bl_idname = "cp77.apply_multilayer_template"
    bl_label = "Apply Multilayer Template"
    bl_description = (
        "Apply the selected Cyberpunk multilayer template to the active layer"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        props = getattr(getattr(context, "scene", None), "cp77_ml_props", None)
        return (
            props is not None
            and resolve_material_state(context).valid_layer
            and selected_template_palette(props) is not None
        )

    def execute(self, context):
        props = context.scene.cp77_ml_props
        palette = selected_template_palette(props)
        if palette is None:
            report(self, "WARNING", "Select a multilayer template first.", logger=_LOG)
            return {"CANCELLED"}
        result = apply_template_to_shader(self, context, palette=palette)
        if isinstance(result, set) and "FINISHED" in result:
            synchronize_panel(context)
        return result if isinstance(result, set) else {"CANCELLED"}


class CP77_OT_ScanMaterialDepot(Operator):
    bl_idname = "cp77.scan_material_depot"
    bl_label = "Scan Multilayer Template Depot"
    bl_options = {"REGISTER"}

    def execute(self, context):
        props = context.scene.cp77_ml_props
        root = ensure_material_depot_path(context, props)
        if not os.path.isdir(root):
            report(
                self,
                "ERROR",
                "Select a valid material depot folder in Material Tools.",
                logger=_LOG,
            )
            return {"CANCELLED"}
        try:
            result = scan_multilayer_templates(root)
        except Exception as error:
            report(self, "ERROR", str(error), logger=_LOG, error=error)
            return {"CANCELLED"}

        state = synchronize_panel(context)
        selected = (
            getattr(state, "palette", None)
            or selected_template_palette(props)
            or result.first_palette
        )
        with material_sync_guard():
            sync_palette_index(props, selected)
        collision_text = (
            f"; {result.collision_count} path collisions"
            if result.collision_count
            else ""
        )
        failure_text = f"; {len(result.failures)} failed" if result.failures else ""
        message = (
            f"Found {result.setup_count} MLSETUP files; "
            f"loaded {result.loaded_count} MLTEMPLATE files"
            f"{failure_text}{collision_text}"
        )
        if result.failures:
            _LOG.warning(
                "Multilayer template scan: %d failure(s); first: %s",
                len(result.failures),
                "; ".join(result.failures[:3]),
            )
            _LOG.debug(
                "Multilayer template scan failures:\n  %s", "\n  ".join(result.failures)
            )
        report(self, "WARNING" if result.failures else "INFO", message, logger=_LOG)
        return {"FINISHED"} if result.succeeded else {"CANCELLED"}


class CP77MaterialReload(Operator):
    bl_idname = "reload_material.cp77"
    bl_label = "Reload Material"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Reload the active material from json."

    @import_operation
    def execute(self, context):
        active_object = context.active_object
        if not active_object:
            report(self, "ERROR_INVALID_CONTEXT", "No active object", logger=_LOG)
            return {"CANCELLED"}
        active_material = active_object.active_material
        if not active_material:
            report(
                self,
                "ERROR_INVALID_CONTEXT",
                "Active object has no material",
                logger=_LOG,
            )
            return {"CANCELLED"}
        if not active_material.get("sourcePath"):
            report(
                self,
                "ERROR",
                "Material was not reloaded: Use Locate Mesh to find a valid source file within a WolvenKit project",
                logger=_LOG,
            )
            return {"CANCELLED"}

        old_mat = active_material
        old_mat_idx = active_object.active_material_index

        try:
            new_mat = reload_materials(context)
        except MaterialReloadError as error:
            report(
                self,
                "ERROR",
                f"Material failed to reload: {error}",
                logger=_LOG,
                error=error,
            )
            return {"CANCELLED"}

        active_object.active_material = new_mat
        active_object.active_material_index = old_mat_idx

        synchronize_panel(context)

        try:
            if old_mat.users == 0:
                bpy.data.materials.remove(
                    old_mat,
                    do_unlink=True,
                    do_id_user=True,
                    do_ui_user=True,
                )
        except (ReferenceError, RuntimeError, TypeError):
            pass

        return {"FINISHED"}


MATERIAL_OPERATOR_CLASSES = (
    CP77MlSetupSelectLayer,
    CP77MlSetupGenerateOverrides,
    CP77MlSetupGenerateOverridesDisconnected,
    CP77MlSetupRefreshOverrides,
    CP77MlSetupEnterTexturePaint,
    CP77MlSetupGenerateActiveMask,
    CP77MlSetupGenerateMasks,
    CP77MlSetupCreateMultilayerObject,
    CP77MlSetupCreateMultilayerMaterial,
    CP77MlSetupRelocateMesh,
    CP77_OT_LoadMaterialTemplate,
    CP77_OT_LoadDepotMicroblends,
    CP77_OT_LoadMultilayerTemplate,
    CP77_OT_ApplyMultilayerTemplate,
    CP77_OT_ScanMaterialDepot,
    CP77MaterialReload,
)
