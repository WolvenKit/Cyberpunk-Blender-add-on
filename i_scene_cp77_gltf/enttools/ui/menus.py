from __future__ import annotations

from bpy.types import Menu

from ...gltf.submesh import submesh_index_for_object
from ..blender import apply, mesh_appearance
from ..blender.scene import component_objects
from ..operators.appearances import CP77_OT_EntityRemoveMeshAppearance
from ..operators.components import (
    CP77_OT_EntityDuplicateComponent,
    CP77_OT_EntityMeshAppearance,
    CP77_OT_EntityPartMaterial,
    CP77_OT_EntityReplaceMesh,
)
from ..services.components import NEW_MATERIAL
from ..services.selection import current_component

PART_CONTEXT_KEY = "cp77_entity_part"


def _component_objects(context):
    collection, item, _index = current_component(context)
    return component_objects(collection, item.name) if item is not None else ()


class CP77_MT_EntityComponentMore(Menu):
    bl_idname = "CP77_MT_entity_component_more"
    bl_label = "Component"

    def draw(self, context):
        self.layout.operator(
            CP77_OT_EntityDuplicateComponent.bl_idname, icon="DUPLICATE"
        )
        self.layout.operator(CP77_OT_EntityReplaceMesh.bl_idname, icon="FILE_REFRESH")


class CP77_MT_EntityMeshAppearance(Menu):
    bl_idname = "CP77_MT_entity_mesh_appearance"
    bl_label = "Mesh Appearance"

    def draw(self, context):
        for name in mesh_appearance.mesh_appearance_names(_component_objects(context)):
            self.layout.operator(
                CP77_OT_EntityMeshAppearance.bl_idname, text=name
            ).name = name


class CP77_MT_EntityRemoveMeshAppearance(Menu):
    bl_idname = "CP77_MT_entity_remove_mesh_appearance"
    bl_label = "Remove Mesh Appearance"

    def draw(self, context):
        _collection, item, _index = current_component(context)
        for name in mesh_appearance.mesh_appearance_names(_component_objects(context)):
            if item is not None and name != item.mesh_appearance:
                self.layout.operator(
                    CP77_OT_EntityRemoveMeshAppearance.bl_idname,
                    text=name,
                    icon="REMOVE",
                ).name = name


class CP77_MT_EntityPartMaterial(Menu):
    bl_idname = "CP77_MT_entity_part_material"
    bl_label = "Material"

    def draw(self, context):
        part_object = getattr(context, PART_CONTEXT_KEY, None)
        if part_object is None:
            return
        part = submesh_index_for_object(part_object)
        names = sorted(
            {
                name
                for found in apply.parts(_component_objects(context))
                for name in found.material_names
                if name
            }
        )
        for name in names:
            operator = self.layout.operator(
                CP77_OT_EntityPartMaterial.bl_idname, text=name
            )
            operator.part, operator.material = part, name
        self.layout.separator()
        operator = self.layout.operator(
            CP77_OT_EntityPartMaterial.bl_idname, text="New Material…", icon="ADD"
        )
        operator.part, operator.material = part, NEW_MATERIAL


ENTITY_MENU_CLASSES = (
    CP77_MT_EntityComponentMore,
    CP77_MT_EntityMeshAppearance,
    CP77_MT_EntityRemoveMeshAppearance,
    CP77_MT_EntityPartMaterial,
)
