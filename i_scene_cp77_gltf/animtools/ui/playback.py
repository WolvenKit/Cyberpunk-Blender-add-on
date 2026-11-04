def draw_mix_face(layout, context) -> None:
    row = layout.row(align=True)
    row.prop(
        context.scene.cp77_additive_preview, "mixer_enabled", text="Mix", toggle=True
    )
    row.prop(context.scene.cp77_facial, "solver_active", text="Face", toggle=True)


def draw_timeline_header(self, context) -> None:
    if getattr(context.space_data, "mode", "") != "TIMELINE":
        return
    self.layout.separator()
    draw_mix_face(self.layout, context)


def draw_playback_footer(self, context) -> None:
    self.layout.separator()
    draw_mix_face(self.layout, context)
