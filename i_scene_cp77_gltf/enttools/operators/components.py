from __future__ import annotations

from bpy.props import BoolProperty, IntProperty, StringProperty
from bpy.types import Operator

from ...blender.operator_results import execute_operation
from ...core.log import get_logger
from ...core.notifications import report
from ..services import components
from ..services.selection import current_component

_LOG = get_logger(__name__)


def _has_component(context):
    return (
        getattr(context.scene, "cp77_entity_tools", None) is not None
        and current_component(context)[1] is not None
    )


def _component_call(operator, context, label, function, *args):
    collection, item, index = current_component(context)
    if item is None:
        report(operator, "ERROR_INVALID_CONTEXT", "Select a component", logger=_LOG)
        return {"CANCELLED"}
    return execute_operation(
        operator, label, function, context, collection, index, *args
    )


class CP77_OT_EntityAddComponent(Operator):
    bl_idname = "cp77.entity_add_component"
    bl_label = "Add Component"
    bl_description = "Add the selected meshes to the appearance as a new component"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(name="Name")

    @classmethod
    def poll(cls, context):
        return current_component(context)[0] is not None and any(
            obj.type == "MESH" for obj in context.selected_objects
        )

    def invoke(self, context, event):
        active = context.active_object
        self.name = active.name if active is not None else ""
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        collection = current_component(context)[0]
        return execute_operation(
            self,
            "Add component",
            components.add_component,
            collection,
            list(context.selected_objects),
            name=self.name,
        )


class CP77_OT_EntityDuplicateComponent(Operator):
    bl_idname = "cp77.entity_duplicate_component"
    bl_label = "Duplicate Component"
    bl_description = (
        "Make a new component from copies of this one's objects and settings"
    )
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(name="Name")

    @classmethod
    def poll(cls, context):
        return _has_component(context)

    def invoke(self, context, event):
        self.name = f"{current_component(context)[1].name}_copy"
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        collection, _item, index = current_component(context)
        return execute_operation(
            self,
            "Duplicate component",
            components.duplicate_component,
            collection,
            index,
            name=self.name,
        )


class CP77_OT_EntityReplaceMesh(Operator):
    bl_idname = "cp77.entity_replace_mesh"
    bl_label = "Replace Mesh from Selected"
    bl_description = (
        "Use the selected meshes for this component in place of its current mesh"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _has_component(context) and any(
            obj.type == "MESH" for obj in context.selected_objects
        )

    def execute(self, context):
        return _component_call(
            self,
            context,
            "Replace mesh",
            components.replace_mesh,
            list(context.selected_objects),
        )


class CP77_OT_EntityRemoveComponent(Operator):
    bl_idname = "cp77.entity_remove_component"
    bl_label = "Remove Component"
    bl_description = "Remove the component and its objects from the appearance"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _has_component(context)

    def execute(self, context):
        return _component_call(
            self, context, "Remove component", components.remove_component
        )


class CP77_OT_EntityPartVisibility(Operator):
    bl_idname = "cp77.entity_part_visibility"
    bl_label = "Show Part"
    bl_description = "Show or hide this part of the mesh on this component (chunkMask)"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    part: IntProperty()
    visible: BoolProperty()

    def execute(self, context):
        return _component_call(
            self,
            context,
            "Part visibility",
            components.set_part_visible,
            self.part,
            self.visible,
        )


class CP77_OT_EntityShowAllParts(Operator):
    bl_idname = "cp77.entity_show_all_parts"
    bl_label = "Show All Parts"
    bl_description = "Show every part of the mesh on this component"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _has_component(context)

    def execute(self, context):
        return _component_call(
            self, context, "Show all parts", components.show_all_parts
        )


class CP77_OT_EntityPartMaterial(Operator):
    bl_idname = "cp77.entity_part_material"
    bl_label = "Part Material"
    bl_description = "Use this material for the part in the current mesh appearance"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    part: IntProperty()
    material: StringProperty()

    def execute(self, context):
        return _component_call(
            self,
            context,
            "Part material",
            components.set_part_material,
            self.part,
            self.material,
        )


class CP77_OT_EntityMeshAppearance(Operator):
    bl_idname = "cp77.entity_mesh_appearance"
    bl_label = "Mesh Appearance"
    bl_description = "Show the component with this mesh appearance (meshAppearance)"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    name: StringProperty()

    def execute(self, context):
        return _component_call(
            self,
            context,
            "Mesh appearance",
            components.set_field,
            "mesh_appearance",
            self.name,
        )


COMPONENT_OPERATOR_CLASSES = (
    CP77_OT_EntityAddComponent,
    CP77_OT_EntityDuplicateComponent,
    CP77_OT_EntityReplaceMesh,
    CP77_OT_EntityRemoveComponent,
    CP77_OT_EntityPartVisibility,
    CP77_OT_EntityShowAllParts,
    CP77_OT_EntityPartMaterial,
    CP77_OT_EntityMeshAppearance,
)
