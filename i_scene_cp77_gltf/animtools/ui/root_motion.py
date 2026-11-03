<<<<<<< Updated upstream
def draw(layout, context, obj):
    header, panel = layout.panel("root_motion", default_closed=True)
    header.label(text="Root Motion", icon="ANIM")
    if panel is None:
        return
    data = context.scene.rm_data
    col = panel.column(align=True)
    col.label(text="Bone Configuration:", icon="BONE_DATA")
    col.prop_search(data, "root", obj.pose, "bones", text="Root")
    col.prop_search(data, "hip", obj.pose, "bones", text="Hip")
    col.separator()
    col.label(text="Transfer Options:", icon="MODIFIER")
    col.prop(data, "step")
    col.prop(data, "no_rot")
    col.prop(data, "do_vert")
    col.separator()
    col.label(text="Operations:")
    col.operator("cp77.hip_to_root_motion", text="Hip to Root Motion", icon="EXPORT")
    col.operator("cp77.root_to_hip_motion", text="Root to Hip Motion", icon="IMPORT")
    col.operator("cp77.remove_root_motion", text="Remove Root Motion", icon="X")
=======
from ...animation.domain.clip.root_motion import MOTION_EXPORT_ITEMS
from ...blender.action_metadata import action_frame_range
from ..runtime.read_models import root_motion_targets

_FORMAT_LABELS = {item[0]: item[1] for item in MOTION_EXPORT_ITEMS}
_FORMAT_LABELS.update({"None": "Disabled", "Unknown": "Unspecified"})


def _edit_button(layout, operation, text, icon="ANIM"):
    layout.operator("cp77.root_motion_edit", text=text, icon=icon).operation = operation


def draw_root_motion(layout, context, obj):
    """The Animation workspace's Root Motion tab"""
    panel = layout
    action = obj.animation_data.action if obj.animation_data else None
    if action is None:
        panel.label(text="Assign a normal action", icon="INFO")
        return
    if str(action.get("animationType", "Normal")) != "Normal":
        panel.label(text="Select a normal action", icon="INFO")
        return
    data = context.scene.rm_data
    col = panel.column(align=True)
    row = col.row(align=True)
    row.label(text=action.name, icon="ACTION")
    row.operator("cp77.root_motion_duplicate", text="", icon="DUPLICATE")
    if action.users > 1 + int(action.use_fake_user):
        col.label(text="Shared action", icon="LINKED")
    try:
        action_frame_range(action)
    except ValueError as error:
        col.label(text=str(error), icon="ERROR")
    if context.screen is not None and context.screen.is_animation_playing:
        col.label(text="Pause playback to edit", icon="PAUSE")
    root_name, source_name = root_motion_targets(obj, data.root, data.source)
    col.prop_search(data, "root", obj.pose, "bones", text="Root")
    if not data.root and root_name:
        col.label(text=f"Auto: {root_name}", icon="BONE_DATA")
    row = col.row(align=True)
    row.operator("cp77.root_motion_select", text="Root Curves", icon="GRAPH")
    row.operator("cp77.root_motion_inspect", text="Check", icon="VIEWZOOM")
    col.prop(data, "translation_axes", text="Travel", toggle=True)
    col.prop(data, "rotation_mode", expand=True)
    col.prop(data, "step")

    header, section = panel.panel("cp77_motion_transfer", default_closed=False)
    header.label(text="Extract & Transfer")
    if section is not None:
        section.prop_search(data, "source", obj.pose, "bones", text="Source")
        if not data.source:
            section.label(
                text=f"Auto: {source_name}" if source_name else "Choose a source bone",
                icon="BONE_DATA",
            )
        section.operator(
            "cp77.root_motion_extract", text="Extract Motion", icon="EXPORT"
        )
        row = section.row(align=True)
        row.operator("cp77.root_motion_integrate", text="Bake Into Pose")
        row.operator("cp77.root_motion_clear", text="Make In Place")

    header, section = panel.panel("cp77_motion_edit", default_closed=False)
    header.label(text="Edit Trajectory")
    if section is not None:
        section.prop(data, "preserve_pose", toggle=True)
        row = section.row(align=True)
        _edit_button(row, "ZERO", "Zero Start")
        _edit_button(row, "FILTER", "Keep Channels")
        section.prop(data, "travel_scale")
        section.prop(data, "direction")
        section.prop(data, "turn_scale")
        _edit_button(section, "SCALE", "Apply Travel & Turn")
        row = section.row(align=True)
        row.prop(data, "smooth_radius")
        _edit_button(row, "SMOOTH", "Smooth")

    header, section = panel.panel("cp77_motion_create", default_closed=True)
    header.label(text="Create Motion")
    if section is not None:
        section.prop(data, "preserve_pose", toggle=True)
        section.prop(data, "displacement", text="Travel (m)")
        section.prop(data, "turn")
        _edit_button(section, "GENERATE", "Create Motion", "ADD")

    header, section = panel.panel("cp77_motion_export", default_closed=False)
    header.label(text="Export")
    if section is not None:
        current = str(action.get("rootMotionType", "Unknown"))
        section.label(text=f"Current: {_FORMAT_LABELS.get(current, current)}")
        section.prop(data, "export_type", text="Format")
        section.operator(
            "cp77.root_motion_format", text="Set Export Format", icon="CHECKMARK"
        )
    if data.report and data.report_action == action.name:
        header, section = panel.panel("cp77_motion_check", default_closed=False)
        header.label(text="Last Check")
        if section is not None:
            for line in data.report.splitlines():
                section.label(text=line)
>>>>>>> Stashed changes
