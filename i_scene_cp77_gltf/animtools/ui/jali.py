from __future__ import annotations

from ...animation.jali.capability import dependency_status
from ...icons.cp77_icons import get_icon


def draw_panel(layout, loaded: bool) -> None:
    header, panel = layout.panel("facial_jali", default_closed=True)
    header.label(text="JALI Lipsync", icon_value=get_icon("RELIC"))
    if panel is None:
        return
    status = dependency_status()
    if not status.parselmouth:
        box = panel.box()
        box.label(text="Dependencies required:", icon="ERROR")
        row = box.row()
        row.label(text="parselmouth", icon="X")
        row = box.row()
        row.label(text="g2p_en (optional)", icon="CHECKMARK" if status.g2p else "X")
        box.operator(
            "cp77_facial.install_jali_deps",
            text="Install Dependencies",
            icon="IMPORT",
        )
        return
    if not loaded:
        panel.label(text="Load a facial setup first.", icon="INFO")
        return
    if not status.g2p:
        panel.label(text="g2p_en not installed — transcript mode unavailable", icon="INFO")
    column = panel.column(align=True)
    column.operator("cp77.generate_jali_lipsync", text="Generate JALI Lipsync")
    column.operator("cp77.preview_facial_pose", text="Preview JALI Pose")
