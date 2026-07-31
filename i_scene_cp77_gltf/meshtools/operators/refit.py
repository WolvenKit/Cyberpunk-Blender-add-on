from bpy.props import BoolProperty
from bpy.types import Operator

from ..model import AutofitRequest
from ..services.refit_service import run_autofit
from .result import finish_operator


class CP77Autofitter(Operator):
    bl_idname = "cp77.auto_fitter"
    bl_label = "AKL Autofitter"
    bl_description = "Fit selected meshes to a configured body refitter"
    bl_options = {"REGISTER", "UNDO"}

    useAddon: BoolProperty(
        name="Use an Addon",
        description="Apply the selected addon after the base refitter",
        default=False,
    )
    try_auto_apply: BoolProperty(
        name="Auto Apply",
        description="Apply refitter geometry as shapekeys",
        default=False,
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        props = context.scene.cp77_panel_props
        request = AutofitRequest(
            base_choice=props.refit_json,
            addon_choice=props.refit_addon_json if self.useAddon else None,
            use_addon=self.useAddon,
            fbx_rotation=props.fbx_rot,
            try_auto_apply=self.try_auto_apply,
        )
        return finish_operator(self, run_autofit(context, request))

    def draw(self, context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        col = layout.column_flow(columns=2)
        col.prop(props, "fbx_rot", text="FBX orientation")
        col.prop(self, "useAddon", text="Use a Refitter Addon")
        layout.prop(self, "try_auto_apply", text="Apply to Mesh")
        row = layout.row(align=True)
        split = row.split(factor=0.2, align=True)
        split.label(text="Shape:")
        split.prop(props, "refit_json", text="")
        if self.useAddon:
            row = layout.row(align=True)
            split = row.split(factor=0.2, align=True)
            split.label(text="Addon:")
            split.prop(props, "refit_addon_json", text="")
