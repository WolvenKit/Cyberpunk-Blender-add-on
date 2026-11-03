import bpy


class PHYSX_UL_actor_list(bpy.types.UIList):
    """Actor list UI with bone parenting indicator"""

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        if not item.obj_ref:
            layout.label(text="<Error>", icon="ERROR")
            return
        layout.prop(item.obj_ref, "name", text="", emboss=False, icon="OBJECT_DATAMODE")
        layout.prop(item.obj_ref.physx, "actor_type", text="")
        layout.prop(
            item,
            "visualization_enabled",
            text="",
            emboss=False,
            icon="HIDE_OFF" if item.visualization_enabled else "HIDE_ON",
        )
        if item.use_bone_parent and item.target_bone != "NONE":
            bone_col = layout.column()
            bone_col.scale_x = 0.5
            bone_col.label(text="", icon="BONE_DATA")
            layout.label(text=f"{item.target_bone}", icon="DOT")


class PHYSX_UL_shape_list(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        icon_map = {
            "BOX": "MESH_CUBE",
            "SPHERE": "MESH_UVSPHERE",
            "CAPSULE": "MESH_CAPSULE",
            "CONVEX": "MESH_ICOSPHERE",
            "TRIANGLE": "MESH_DATA",
            "HEIGHTFIELD": "MESH_GRID",
        }
        shape_icon = icon_map.get(item.shape_type, "MESH_CUBE")

        layout.prop(item, "name", text="", emboss=False, icon=shape_icon)
        layout.prop(item, "shape_type", text="")


class PHYSX_UL_vehicle_gear_list(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        row = layout.row(align=True)
        row.label(text="R" if index == 0 else str(index))
        row.label(text=f"{item.min_speed * 3.6:.0f}–{item.max_speed * 3.6:.0f} km/h")
        row.label(
            text=f"{item.min_engine_rpm:.0f}–{item.max_engine_rpm:.0f} RPM"
            if index
            else f"{item.max_engine_rpm:.0f} RPM"
        )
