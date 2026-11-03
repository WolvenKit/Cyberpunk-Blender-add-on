from __future__ import annotations

from bpy.props import IntProperty, StringProperty
from bpy.types import Operator

from ...blender.operator_results import execute_operation
from ..services import appearances
from ..services.selection import current_collection, current_component


def _has_appearance(context):
    return (
        getattr(context.scene, "cp77_entity_tools", None) is not None
        and current_collection(context) is not None
    )


class _AppearanceNameDialog:
    name: StringProperty(
        name="Name", description="The appearance's name in the .app (name)"
    )
    entry_name: StringProperty(
        name="Entry Name", description="The entity's appearance entry name (name)"
    )

    @classmethod
    def poll(cls, context):
        return _has_appearance(context)


class CP77_OT_EntityDuplicateAppearance(_AppearanceNameDialog, Operator):
    bl_idname = "cp77.entity_duplicate_appearance"
    bl_label = "Duplicate Appearance"
    bl_description = "Make a new appearance from a copy of this one"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        state = current_collection(context).cp77_entity_state
        self.name = f"{state.name}_copy"
        self.entry_name = appearances.copied_entry_name(state, self.name)
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        return execute_operation(
            self,
            "Duplicate appearance",
            appearances.duplicate_appearance,
            context,
            current_collection(context),
            self.name,
            self.entry_name,
        )


class CP77_OT_EntityRenameAppearance(_AppearanceNameDialog, Operator):
    bl_idname = "cp77.entity_rename_appearance"
    bl_label = "Rename Appearance"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        state = current_collection(context).cp77_entity_state
        self.name, self.entry_name = state.name, state.entry_name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        return execute_operation(
            self,
            "Rename appearance",
            appearances.rename_appearance,
            current_collection(context),
            self.name,
            self.entry_name,
        )


class CP77_OT_EntityRemoveAppearance(Operator):
    bl_idname = "cp77.entity_remove_appearance"
    bl_label = "Remove Appearance"
    bl_description = "Leave this appearance out of the exported entity"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _has_appearance(context)

    def execute(self, context):
        return execute_operation(
            self,
            "Remove appearance",
            appearances.remove_appearance,
            current_collection(context),
        )


class CP77_OT_EntityMakeDefault(Operator):
    bl_idname = "cp77.entity_make_default"
    bl_label = "Make Default"
    bl_description = "Make this the entity's default appearance (defaultAppearance)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _has_appearance(context)

    def execute(self, context):
        return execute_operation(
            self, "Make default", appearances.make_default, current_collection(context)
        )


class CP77_OT_EntityNewMeshAppearance(Operator):
    bl_idname = "cp77.entity_new_mesh_appearance"
    bl_label = "New Mesh Appearance"
    bl_description = "Make a new mesh appearance from a copy of the current one"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(name="Name")

    @classmethod
    def poll(cls, context):
        return current_component(context)[1] is not None

    def invoke(self, context, event):
        self.name = f"{current_component(context)[1].mesh_appearance}_copy"
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        collection, _item, index = current_component(context)
        return execute_operation(
            self,
            "New mesh appearance",
            appearances.new_mesh_appearance,
            collection,
            index,
            self.name,
        )


class CP77_OT_EntityRemoveMeshAppearance(Operator):
    bl_idname = "cp77.entity_remove_mesh_appearance"
    bl_label = "Remove Mesh Appearance"
    bl_description = "Remove a mesh appearance from the mesh"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(name="Name")

    @classmethod
    def poll(cls, context):
        return current_component(context)[1] is not None

    def execute(self, context):
        collection, _item, index = current_component(context)
        return execute_operation(
            self,
            "Remove mesh appearance",
            appearances.remove_mesh_appearance,
            collection,
            index,
            self.name,
        )


class CP77_OT_EntitySelectIssue(Operator):
    bl_idname = "cp77.entity_select_issue"
    bl_label = "Show Problem"
    bl_description = "Select the component this problem is about"
    bl_options = {"INTERNAL"}

    index: IntProperty()

    def execute(self, context):
        context.scene.cp77_entity_tools.issue_index = self.index
        return {"FINISHED"}


APPEARANCE_OPERATOR_CLASSES = (
    CP77_OT_EntityDuplicateAppearance,
    CP77_OT_EntityRenameAppearance,
    CP77_OT_EntityRemoveAppearance,
    CP77_OT_EntityMakeDefault,
    CP77_OT_EntityNewMeshAppearance,
    CP77_OT_EntityRemoveMeshAppearance,
    CP77_OT_EntitySelectIssue,
)
