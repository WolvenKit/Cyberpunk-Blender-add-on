from __future__ import annotations

from ...animation.domain.jali.capability import dependency_status
from ...icons.cp77_icons import get_icon


def draw_panel(layout, loaded: bool) -> None:
    header, panel = layout.panel("facial_jali", default_closed=True)
    header.label(text="JALI Lipsync", icon_value=get_icon("RELIC"))
    if panel is None:
        return
    status = dependency_status()
    if not status.parselmouth:
        panel.label(text="Reinstall the add-on to use lipsync", icon="ERROR")
        return
    if not loaded:
        panel.label(text="Load a facial setup first.", icon="INFO")
        return
    if not status.g2p:
        panel.label(text="Reinstall the add-on to use transcripts", icon="INFO")
    column = panel.column(align=True)
    column.operator("cp77.generate_jali_lipsync", text="Generate JALI Lipsync")
    column.operator("cp77.preview_facial_pose", text="Preview JALI Pose")
