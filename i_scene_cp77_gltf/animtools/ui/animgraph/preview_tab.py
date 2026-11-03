import bpy

from ....blender.animgraph.rig_binding import binding_tree
from ....collisiontools.runtime.dangle.preview import graph_tree_previewing
from ...operators.animgraph.context import animgraph_editor_poll


def _draw_conditions(layout, root, settings):
    layout.operator(
        "redengine.graph_preview_refresh_inputs", icon="FILE_REFRESH"
    ).tree_name = root.name
    layout.prop(settings, "visual_tags")
    layout.prop(settings, "component_tags")
    row = layout.row(align=True)
    row.prop(settings, "skeletal_lod")
    row.prop(settings, "performance_mode", toggle=True)
    if settings.visual_tag_requirements:
        box = layout.box()
        box.label(text="StaticSwitch Visual Tags", icon="TAG")
        present = {
            tag.strip() for tag in settings.visual_tags.split(",") if tag.strip()
        }
        for requirement in settings.visual_tag_requirements:
            op = box.operator(
                "redengine.graph_preview_toggle_tag",
                text=requirement.tag,
                depress=requirement.tag in present,
            )
            op.tree_name, op.tag = root.name, requirement.tag


def _draw_look_at(layout, settings):
    box = layout.box()
    box.prop(settings, "look_at_enabled")
    col = box.column()
    col.active = settings.look_at_enabled
    col.prop(settings, "look_at_part")
    col.prop(settings, "look_at_object")
    if settings.look_at_object is None:
        col.prop(settings, "look_at_target")
    col.prop(settings, "look_at_speed")


class REDENGINE_PT_graph_preview(bpy.types.Panel):
    bl_idname = "REDENGINE_PT_graph_preview"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Preview"
    bl_label = "Preview"

    @classmethod
    def poll(cls, context):
        return animgraph_editor_poll(context)

    def draw(self, context):
        layout = self.layout
        root = binding_tree(context.space_data.node_tree)
        settings = root.red_preview
        playing = graph_tree_previewing(root)
        row = layout.row(align=True)
        if playing:
            row.operator(
                "redengine.graph_preview_stop", text="Stop", icon="PAUSE"
            ).tree_name = root.name
        else:
            row.operator(
                "redengine.graph_preview_play", text="Play", icon="PLAY"
            ).tree_name = root.name
        if settings.view_handle:
            row.operator(
                "redengine.show_final_pose", text="Back to Final Pose", icon="LOOP_BACK"
            )

        conditions = layout.column()
        conditions.enabled = not playing
        _draw_conditions(conditions, root, settings)
        layout.prop(settings, "external_events")
        layout.prop(settings, "wrapper_variables")
        layout.prop(settings, "anim_features_json")
        if settings.look_at_parts:
            _draw_look_at(layout, settings)
        if settings.vector_inputs:
            box = layout.box()
            box.label(text="Live Inputs", icon="DRIVER")
            for item in settings.vector_inputs:
                box.prop(item, "value", text=f"{item.group} {item.input_name}".strip())
        for message in (settings.evaluation_boundary, settings.input_error):
            for line in str(message or "").splitlines():
                layout.label(text=line, icon="ERROR")
