import bpy


class REDENGINE_UL_curve_points(bpy.types.UIList):
    bl_idname = "REDENGINE_UL_curve_points"

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            row.label(text=str(index))
            row.prop(item, "point", text="Point")
            row.prop(item, "value", text="Value")
