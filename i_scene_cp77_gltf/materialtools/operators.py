from bpy.props import EnumProperty, StringProperty
from bpy.types import Operator

from ..materials.blender import multilayer as multilayer_service
from ..blender.transactions import DatablockImportTransaction, rollback_report_message
from .palette import clear_palette_caches
from .creation import (
    create_multilayer_material,
    create_multilayer_resource_object,
    relocate_mesh_material,
)
from .editor import synchronize_panel
from .masks import generate_mask_images, toggle_texture_paint
from .state import resolve_material_state

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
    report = transaction.rollback()
    detail = rollback_report_message(report)
    if detail:
        owner.report({"ERROR"}, f"{message}; rollback incomplete: {detail}")
    return {"CANCELLED"}


def _run_override_generation(owner, callback):
    transaction = DatablockImportTransaction()
    try:
        with transaction.scope():
            result = callback()
        if not isinstance(result, set):
            owner.report({"ERROR"}, "Override generation returned an invalid operator status.")
            return _rollback_operator_transaction(owner, transaction, "Override generation failed")
        if "FINISHED" not in result:
            return _rollback_operator_transaction(owner, transaction, "Override generation was cancelled")
        transaction.commit()
        return result
    except Exception as error:
        owner.report({"ERROR"}, f"Override generation failed: {type(error).__name__}: {error}")
        return _rollback_operator_transaction(owner, transaction, "Override generation failed")


def _active_mesh(context):
    obj = getattr(context, "active_object", None)
    return obj if obj is not None and getattr(obj, "type", None) == "MESH" else None


def _active_material(context):
    obj = _active_mesh(context)
    return getattr(obj, "active_material", None) if obj is not None else None


def _multilayer_material(context):
    material = _active_material(context)
    if material is None:
        return None
    try:
        if not material.use_nodes or material.node_tree is None:
            return None
        return material if material.get("MLSetup") is not None else None
    except (AttributeError, ReferenceError, TypeError):
        return None


class CP77MlSetupGenerateOverrides(Operator):
    bl_idname = "generate_layer_overrides.mlsetup"
    bl_label = "Generate Overrides"
    bl_description = "Create override data for layers connected to the Multilayered shader node"

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
    bl_label = "Generate Overrides for All Nodes"
    bl_description = "Create override data for layer nodes using the Mat_Mod_Layer naming scheme"

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
    bl_description = "Enter or leave Texture Paint mode for the selected multilayer mask"

    @classmethod
    def poll(cls, context):
        state = resolve_material_state(context)
        return state.valid_layer and state.mask_node is not None

    def execute(self, context):
        return toggle_texture_paint(self, context)


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
        return generate_mask_images(self, context, self.dimensions)


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

    def execute(self, context):
        transaction = DatablockImportTransaction()
        try:
            with transaction.scope():
                result = create_multilayer_resource_object(self, context, self.dimensions)
            if "FINISHED" not in result:
                return _rollback_operator_transaction(self, transaction, "Resource object creation failed")
            transaction.commit()
            return result
        except Exception as error:
            self.report({"ERROR"}, f"Resource object creation failed: {type(error).__name__}: {error}")
            return _rollback_operator_transaction(self, transaction, "Resource object creation failed")


class CP77MlSetupCreateMultilayerMaterial(Operator):
    bl_idname = "create_multilayer_material.mlsetup"
    bl_label = "Create Multilayer Material"
    bl_description = "Create a material ready for multilayer editing on the active object"
    bl_options = {"REGISTER", "UNDO"}

    dimensions: EnumProperty(
        name="Mask Resolution",
        description="Sets the generated mask image dimensions",
        items=_MASK_DIMENSION_ITEMS,
        default="1024",
    )

    @classmethod
    def poll(cls, context):
        return getattr(context, "mode", "OBJECT") == "OBJECT" and _active_mesh(context) is not None

    def execute(self, context):
        transaction = DatablockImportTransaction()
        try:
            with transaction.scope():
                material = create_multilayer_material(self, context)
                if material is None:
                    return _rollback_operator_transaction(self, transaction, "Multilayer material creation failed")
                result = generate_mask_images(self, context, self.dimensions)
            if "FINISHED" not in result:
                return _rollback_operator_transaction(self, transaction, "Multilayer material creation failed")
            transaction.commit()
            synchronize_panel(context)
            return {"FINISHED"}
        except Exception as error:
            self.report({"ERROR"}, f"Multilayer material creation failed: {type(error).__name__}: {error}")
            return _rollback_operator_transaction(self, transaction, "Multilayer material creation failed")


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
        return _active_material(context) is not None

    def execute(self, context):
        return relocate_mesh_material(self, context, self.filepath)

    def invoke(self, context, _event):
        if not self.poll(context):
            self.report({"ERROR"}, "Select a mesh with an active material.")
            return {"CANCELLED"}
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
