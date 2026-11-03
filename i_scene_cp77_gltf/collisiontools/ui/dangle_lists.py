import bpy

from ..runtime.dangle.rigs import dangle_rigs


class DANGLE_UL_rigs(bpy.types.UIList):
    def filter_items(self, context, data, property):
        objects = getattr(data, property)
        flags = [0] * len(objects)
        for rig in dangle_rigs():
            index = objects.find(rig.name)
            if index >= 0 and objects[index] == rig:
                flags[index] = self.bitflag_filter_item
        return flags, []

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        layout.prop(item, "name", text="", emboss=False, icon="ARMATURE_DATA")


class DANGLE_UL_dangle_nodes(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        layout.prop(item, "name", text="", emboss=False, icon="PHYSICS")


class DANGLE_UL_chains(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        layout.prop(item, "name", text="", emboss=False, icon="LINKED")


class DANGLE_UL_particles(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        layout.label(text=item.bone_name or "Unassigned", icon="BONE_DATA")
        layout.prop(
            item,
            "is_pinned",
            text="",
            icon="PINNED" if item.is_pinned else "UNPINNED",
        )


class DANGLE_UL_collision_shapes(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        shape_icon = {
            "CAPSULE": "MESH_CAPSULE",
            "ROUNDED_BOX": "MESH_CUBE",
        }.get(item.shape_type, "MESH_UVSPHERE")
        layout.label(text=item.name, icon=shape_icon)
        layout.prop(item, "bone_name", text="", emboss=False)
