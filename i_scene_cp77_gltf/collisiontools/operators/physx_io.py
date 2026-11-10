import bpy

from ...blender.operator_results import OperationResult, finish_operator
from ...blender.physics.cooked_shapes import import_cooked_shape, import_native_scene
from ...blender.physics.resources import import_phys, import_phys_to_actor
from ...core.notifications import import_operation
from ...exporters.collision.heightfield import export_selected_heightfields
from ...exporters.collision.physx_actor import export_actor_item_to_phys
from ...exporters.collision.physx_binary import export_cooked_shape, export_native_scene
from ...physics.domain.resource_paths import normalize_phys_json_path


class PHYSX_OT_export_phys(bpy.types.Operator):
    bl_idname = "physx.export_phys"
    bl_label = "Export .phys (Cyberpunk)"
    bl_options = {"REGISTER", "UNDO"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filename_ext = ".phys.json"
    filter_glob: bpy.props.StringProperty(default="*.phys.json", options={"HIDDEN"})

    def check(self, context):
        normalized = normalize_phys_json_path(self.filepath)
        if normalized == self.filepath:
            return False
        self.filepath = normalized
        return True

    def execute(self, context):
        px_scene = context.scene.physx
        index = px_scene.actor_list_index
        if not px_scene.actors:
            return finish_operator(
                self, OperationResult.cancelled("Actor list is empty.")
            )
        if index < 0 or index >= len(px_scene.actors):
            return finish_operator(
                self, OperationResult.cancelled("No actor selected in list.")
            )
        actor = px_scene.actors[index]
        if not actor.obj_ref:
            return finish_operator(
                self, OperationResult.cancelled("Actor object is missing.")
            )
        try:
            export_actor_item_to_phys(actor, self.filepath)
        except Exception as error:
            return finish_operator(
                self, OperationResult.cancelled(str(error), error=error)
            )
        return finish_operator(
            self, OperationResult.finished(f"Exported: {actor.obj_ref.name}")
        )

    def invoke(self, context, event):
        px_scene = context.scene.physx
        if px_scene.actors and 0 <= px_scene.actor_list_index < len(px_scene.actors):
            actor = px_scene.actors[px_scene.actor_list_index]
            if actor.obj_ref:
                self.filepath = actor.obj_ref.name + ".phys.json"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class PHYSX_OT_import_phys(bpy.types.Operator):
    bl_idname = "physx.import_phys"
    bl_label = "Import .phys Actors"
    bl_description = "Import a Cyberpunk .phys.json resource as PhysX actors"
    bl_options = {"REGISTER", "UNDO"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(
        default="*.phys.json;*.json", options={"HIDDEN"}
    )

    @import_operation
    def execute(self, context):
        try:
            actor_count, shape_count = import_phys(self.filepath, context=context)
        except Exception as error:
            return finish_operator(
                self, OperationResult.cancelled(str(error), error=error)
            )
        if not actor_count or not shape_count:
            return finish_operator(
                self,
                OperationResult.cancelled("No supported physics actors were imported."),
            )
        context.scene.physx.ui_tab = "ACTORS"
        return finish_operator(
            self,
            OperationResult.finished(
                f"Imported {actor_count} .phys actor(s) with {shape_count} shape(s)"
            ),
        )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class PHYSX_OT_confirm_import_to_actor(bpy.types.Operator):
    bl_idname = "physx.confirm_import_to_actor"
    bl_label = "Select Target Object"
    bl_options = {"REGISTER", "INTERNAL"}

    filepath: bpy.props.StringProperty()
    target_obj_name: bpy.props.StringProperty(name="Target Object")

    def invoke(self, context, event):
        if context.active_object:
            self.target_obj_name = context.active_object.name
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.label(text="Attach physics shapes to:")
        self.layout.prop_search(self, "target_obj_name", context.scene, "objects")

    @import_operation
    def execute(self, context):
        obj = context.scene.objects.get(self.target_obj_name)
        if obj is None:
            return finish_operator(
                self, OperationResult.cancelled("Target object does not exist.")
            )
        if not import_phys_to_actor(self.filepath, obj, context):
            return finish_operator(
                self,
                OperationResult.cancelled("Import failed. Check the log for details."),
            )
        obj.select_set(True)
        context.view_layer.objects.active = obj
        context.scene.physx.ui_tab = "ACTORS"
        return finish_operator(
            self, OperationResult.finished(f"Imported physics shapes to {obj.name}")
        )


class PHYSX_OT_import_phys_to_actor(bpy.types.Operator):
    bl_idname = "physx.import_phys_to_actor"
    bl_label = "Attach .phys to Object"
    bl_description = (
        "Import shapes from a Cyberpunk .phys.json resource onto an existing object"
    )
    bl_options = {"REGISTER", "UNDO"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(
        default="*.phys.json;*.json", options={"HIDDEN"}
    )

    @import_operation
    def execute(self, context):
        try:
            result = bpy.ops.physx.confirm_import_to_actor(
                "INVOKE_DEFAULT", filepath=self.filepath
            )
        except RuntimeError as error:
            return finish_operator(
                self, OperationResult.cancelled(str(error), error=error)
            )
        return {"CANCELLED"} if "CANCELLED" in result else {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class PHYSX_OT_export_heightfields(bpy.types.Operator):
    bl_idname = "physx.export_heightfields"
    bl_label = "Export Heightfields"
    bl_description = "Export selected canonical PhysX HEIGHTFIELD shapes as worldTerrainCollisionNode records"
    bl_options = {"REGISTER"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(
        default="*.streamingsector.json", options={"HIDDEN"}
    )

    def execute(self, context):
        try:
            count, filepath = export_selected_heightfields(context, self.filepath)
        except Exception as error:
            return finish_operator(
                self, OperationResult.cancelled(str(error), error=error)
            )
        return finish_operator(
            self,
            OperationResult.finished(
                f"Exported {count} heightfield shape(s) to {filepath}"
            ),
        )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class PHYSX_OT_save_cooked(bpy.types.Operator):
    bl_idname = "physx.save_cooked"
    bl_label = "Export Cooked Geometry"
    bl_description = "Save the selected shape's opaque PhysX cooked geometry buffer"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        obj = context.object
        if not obj or not obj.physx.shapes:
            return {"CANCELLED"}
        shape = obj.physx.shapes[obj.physx.shape_index]
        try:
            byte_count = export_cooked_shape(shape, self.filepath)
        except Exception as error:
            return finish_operator(
                self, OperationResult.cancelled(str(error), error=error)
            )
        return finish_operator(
            self, OperationResult.finished(f"Saved cooked geometry: {byte_count} bytes")
        )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class PHYSX_OT_load_cooked(bpy.types.Operator):
    bl_idname = "physx.load_cooked"
    bl_label = "Import Cooked Geometry"
    bl_description = (
        "Load an opaque PhysX cooked geometry buffer into the selected shape"
    )

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    @import_operation
    def execute(self, context):
        obj = context.object
        if not obj or not obj.physx.shapes:
            return {"CANCELLED"}
        shape = obj.physx.shapes[obj.physx.shape_index]
        try:
            byte_count = import_cooked_shape(shape, self.filepath)
        except Exception as error:
            return finish_operator(
                self, OperationResult.cancelled(str(error), error=error)
            )
        return finish_operator(
            self,
            OperationResult.finished(f"Loaded cooked geometry: {byte_count} bytes"),
        )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class PHYSX_OT_export_scene(bpy.types.Operator):
    bl_idname = "physx.export_scene"
    bl_label = "Export Binary"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        try:
            export_native_scene(self.filepath, context)
        except Exception as error:
            return finish_operator(
                self, OperationResult.cancelled(str(error), error=error)
            )
        return finish_operator(
            self, OperationResult.finished(f"Scene Exported to {self.filepath}")
        )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class PHYSX_OT_import_scene(bpy.types.Operator):
    bl_idname = "physx.import_scene"
    bl_label = "Import Binary"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    @import_operation
    def execute(self, context):
        try:
            import_native_scene(self.filepath, context)
        except Exception as error:
            return finish_operator(
                self, OperationResult.cancelled(str(error), error=error)
            )
        return finish_operator(
            self, OperationResult.finished("Scene Imported successfully")
        )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
