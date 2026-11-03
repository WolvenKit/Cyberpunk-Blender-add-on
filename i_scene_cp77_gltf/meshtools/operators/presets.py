from bpy.props import FloatVectorProperty, StringProperty
from bpy.types import Operator

from ..services.preset_service import (
    add_vertex_color_preset,
    apply_vertex_color_preset,
    delete_vertex_color_preset,
)
from .result import finish_operator


class CP77DeleteVertexcolorPreset(Operator):
    bl_idname = "cp77.delete_vertex_color_preset"
    bl_label = "Delete Vertex Colour Preset"

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        name = context.scene.cp77_panel_props.vertex_color_presets
        return finish_operator(self, delete_vertex_color_preset(name))

    def draw(self, context):
        props = context.scene.cp77_panel_props
        row = self.layout.row(align=True)
        split = row.split(factor=0.275, align=True)
        split.label(text="Preset:")
        split.prop(props, "vertex_color_presets", text="")


class CP77AddVertexcolorPreset(Operator):
    bl_idname = "cp77.add_vertex_color_preset"
    bl_label = "Save Vertex Colour Preset"
    bl_parent_id = "CP77_PT_MeshTools"

    preset_name: StringProperty(name="Preset Name")
    color: FloatVectorProperty(
        name="Color",
        subtype="COLOR",
        min=0.0,
        max=1.0,
        size=4,
        default=(1.0, 1.0, 1.0, 1.0),
    )

    def execute(self, context):
        return finish_operator(self, add_vertex_color_preset(self.preset_name, self.color))

    def invoke(self, context, event):
        paint = context.tool_settings.vertex_paint
        brush = getattr(paint, "brush", None)
        if brush is not None:
            self.color = (*brush.color[:3], brush.strength)
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "color", text="")
        row = layout.row(align=True)
        split = row.split(factor=0.3, align=True)
        split.label(text="Preset Name:")
        split.prop(self, "preset_name", text="")


class CP77ApplyVertexcolorPreset(Operator):
    bl_idname = "cp77.apply_vertex_color_preset"
    bl_label = "Apply Vertex Colour Preset"

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        name = context.scene.cp77_panel_props.vertex_color_presets
        return finish_operator(self, apply_vertex_color_preset(context, name))

    def draw(self, context):
        props = context.scene.cp77_panel_props
        row = self.layout.row(align=True)
        split = row.split(factor=0.275, align=True)
        split.label(text="Preset:")
        split.prop(props, "vertex_color_presets", text="")
