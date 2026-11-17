from bpy.props import IntProperty
from bpy.types import Operator

from ...blender.mesh_appearances import (
    add_appearance,
    add_row_appearance,
    assign_to_appearance,
    display_appearance,
    record_slot_material,
    remove_appearance,
    reset_to_original,
    store_original_materials,
)


def _active_appearance(context):
    scene = context.scene
    index = scene.cp77_mesh_appearance_index
    return index if 0 <= index < len(scene.cp77_mesh_appearances) else -1


def _active_mesh(context):
    obj = context.active_object
    return obj if obj is not None and obj.type == "MESH" and obj.data else None


def _row(context, row):
    obj = _active_mesh(context)
    rows = obj.data.cp77_appearance_materials if obj else ()
    return rows[row] if 0 <= row < len(rows) else None


class CP77_OT_MeshAppearanceAdd(Operator):
    """Add an appearance to the scene"""

    bl_idname = "cp77.mesh_appearance_add"
    bl_label = "Add Appearance"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        context.scene.cp77_mesh_appearance_index = add_appearance(context.scene)
        return {"FINISHED"}


class CP77_OT_MeshAppearanceRemove(Operator):
    """Remove the active appearance from the scene and its meshes"""

    bl_idname = "cp77.mesh_appearance_remove"
    bl_label = "Remove Appearance"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active_appearance(context) >= 0

    def execute(self, context):
        scene = context.scene
        index = _active_appearance(context)
        meshes = {obj.data for obj in scene.objects if obj.type == "MESH" and obj.data}
        remove_appearance(scene, meshes, index)
        scene.cp77_mesh_appearance_index = max(
            0, min(index, len(scene.cp77_mesh_appearances) - 1)
        )
        return {"FINISHED"}


class CP77_OT_MeshAppearanceDisplay(Operator):
    """Show the active appearance's materials on every mesh in the scene"""

    bl_idname = "cp77.mesh_appearance_display"
    bl_label = "Display Appearance"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active_appearance(context) >= 0

    def execute(self, context):
        display_appearance(context.scene, _active_appearance(context))
        return {"FINISHED"}


class CP77_OT_MeshAppearanceAssign(Operator):
    """Use the selected meshes' current materials for the active appearance"""

    bl_idname = "cp77.mesh_appearance_assign"
    bl_label = "Assign to Appearance"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active_appearance(context) >= 0 and any(
            obj.type == "MESH" for obj in context.selected_objects
        )

    def execute(self, context):
        assign_to_appearance(context.selected_objects, _active_appearance(context))
        return {"FINISHED"}


class CP77_OT_MeshAppearanceReset(Operator):
    """Give every mesh in the scene back the materials it was imported with"""

    bl_idname = "cp77.mesh_appearance_reset"
    bl_label = "Reset to Original"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        reset_to_original(context.scene)
        return {"FINISHED"}


class CP77_OT_MeshAppearanceMaterialAdd(Operator):
    """Use the active slot's current material for the active appearance"""

    bl_idname = "cp77.mesh_appearance_material_add"
    bl_label = "Assign Slot to Appearance"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = _active_mesh(context)
        return (
            obj is not None
            and obj.active_material is not None
            and _active_appearance(context) >= 0
        )

    def execute(self, context):
        obj = _active_mesh(context)
        store_original_materials(obj)
        record_slot_material(
            obj.data,
            obj.active_material_index,
            obj.active_material,
            _active_appearance(context),
        )
        return {"FINISHED"}


class CP77_OT_MeshAppearanceMaterialRemove(Operator):
    """Stop using this material for the slot's appearances"""

    bl_idname = "cp77.mesh_appearance_material_remove"
    bl_label = "Remove Appearance Material"
    bl_options = {"REGISTER", "UNDO"}

    row: IntProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        if _row(context, self.row) is None:
            return {"CANCELLED"}
        _active_mesh(context).data.cp77_appearance_materials.remove(self.row)
        return {"FINISHED"}


class CP77_OT_MeshAppearanceUseAdd(Operator):
    """Use this material for the active appearance too"""

    bl_idname = "cp77.mesh_appearance_use_add"
    bl_label = "Add Active Appearance"
    bl_options = {"REGISTER", "UNDO"}

    row: IntProperty(options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return _active_appearance(context) >= 0

    def execute(self, context):
        if _row(context, self.row) is None:
            return {"CANCELLED"}
        add_row_appearance(
            _active_mesh(context).data, self.row, _active_appearance(context)
        )
        return {"FINISHED"}


class CP77_OT_MeshAppearanceUseRemove(Operator):
    """Stop using this material for the appearance"""

    bl_idname = "cp77.mesh_appearance_use_remove"
    bl_label = "Remove Appearance from Material"
    bl_options = {"REGISTER", "UNDO"}

    row: IntProperty(options={"SKIP_SAVE"})
    use: IntProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        item = _row(context, self.row)
        if item is None or not 0 <= self.use < len(item.appearances):
            return {"CANCELLED"}
        item.appearances.remove(self.use)
        return {"FINISHED"}
