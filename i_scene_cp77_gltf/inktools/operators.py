from __future__ import annotations

import json

import bpy
from bpy.props import EnumProperty, FloatProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from ..blender.operator_results import execute_operation
from ..core.log import get_logger
from ..core.notifications import import_operation, report
from . import services
from .blender import hierarchy

_LOG = get_logger(__name__)

# Blender keeps 15 characters of a file browser filter pattern, so the dot before "inkwidget" is left out:
# "*.inkwidget.json" would show no files.
_INKWIDGET_FILE_FILTER = "*inkwidget.json"
_SLOT_ITEMS = (
    ("0", "2160p", "Draw atlas parts from the UltraHD slot"),
    ("1", "1080p", "Draw atlas parts from the FullHD slot"),
    ("2", "720p", "Draw atlas parts from the HD slot"),
)


def _picked_screen(context):
    """The screen of the widget picked in the ink Widgets list, None when none is picked in the scene"""
    return hierarchy.screen_root(hierarchy.picked_widget(context.scene))


def _picked_standalone(context):
    """The standalone import of the picked widget, None when the picked widget is not one"""
    return hierarchy.standalone_root(hierarchy.picked_widget(context.scene))


class CP77_OT_ImportInkWidget(bpy.types.Operator, ImportHelper):
    bl_idname = "cp77.import_inkwidget"
    bl_label = "Import ink Widget"
    bl_description = (
        "Import a WolvenKit .inkwidget.json as a preview with a handle per widget"
    )
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ".json"
    filter_glob: StringProperty(default=_INKWIDGET_FILE_FILTER, options={"HIDDEN"})
    item: StringProperty(
        name="Item", description="The library item to import; the root item when empty"
    )
    resolution_slot: EnumProperty(name="Atlas Slot", items=_SLOT_ITEMS, default="0")
    unit_scale: FloatProperty(
        name="Unit Scale",
        description="Blender units per widget pixel",
        default=0.001,
        min=0.000001,
        max=1.0,
        precision=6,
    )

    @import_operation
    def execute(self, context):
        return execute_operation(
            self,
            "Ink widget import",
            services.import_widget,
            context,
            self.filepath,
            item=self.item.strip(),
            preferred_slot=int(self.resolution_slot),
            unit_scale=self.unit_scale,
        )


class CP77_OT_InkRefresh(bpy.types.Operator):
    bl_idname = "cp77.ink_refresh"
    bl_label = "Refresh"
    bl_description = "Take the handles' moves, turns and scales into the widget edits and redraw the preview"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _picked_standalone(context) is not None

    def execute(self, context):
        return execute_operation(
            self, "Ink widget refresh", services.refresh, _picked_standalone(context)
        )


class CP77_OT_InkExport(bpy.types.Operator):
    bl_idname = "cp77.ink_export"
    bl_label = "Export"
    bl_description = "Write the widget edits into the .inkwidget.json"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})
    filter_glob: StringProperty(default=_INKWIDGET_FILE_FILTER, options={"HIDDEN"})
    check_existing: bpy.props.BoolProperty(default=True, options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return _picked_standalone(context) is not None

    def invoke(self, context, _event):
        self.filepath = str(_picked_standalone(context)["cp77_ink_widget_json"])
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        return execute_operation(
            self,
            "Ink widget export",
            services.export,
            _picked_standalone(context),
            bpy.path.abspath(self.filepath),
        )


class CP77_OT_InkPlaySequence(bpy.types.Operator):
    bl_idname = "cp77.ink_activate_sequence"
    bl_label = "Play ink Sequence"
    bl_description = (
        "Play the ink animation sequence on the widget's screen from the current frame"
    )
    bl_options = {"REGISTER"}

    sequence_name: StringProperty(name="Sequence")

    @classmethod
    def poll(cls, context):
        return _picked_screen(context) is not None

    def execute(self, context):
        root = _picked_screen(context)
        status = execute_operation(
            self, "Ink sequence", services.play, root, self.sequence_name, context.scene
        )
        if "FINISHED" not in status:
            return status
        scene = context.scene
        try:
            duration = float(
                json.loads(
                    str(root.get("cp77_ink_animation_durations", "{}") or "{}")
                ).get(self.sequence_name, 0)
            )
        except (TypeError, ValueError):
            duration = 0.0
        fps = float(scene.render.fps) / max(1.0e-8, float(scene.render.fps_base))
        scene.frame_end = max(
            scene.frame_end, int(round(scene.frame_current + duration * fps))
        )
        if context.screen is not None and not context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()
        return status


class CP77_OT_InkStopSequence(bpy.types.Operator):
    bl_idname = "cp77.ink_stop_sequence"
    bl_label = "Stop"
    bl_description = "Stop the ink animation and show the widget switched on"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return _picked_screen(context) is not None

    def execute(self, context):
        status = execute_operation(
            self, "Ink sequence stop", services.stop, _picked_screen(context)
        )
        if context.screen is not None and context.screen.is_animation_playing:
            bpy.ops.screen.animation_play()
        return status


class CP77_OT_InkSelectByType(bpy.types.Operator):
    bl_idname = "cp77.ink_select_by_type"
    bl_label = "Select ink Widgets by Type"
    bl_description = "Select the handles of every widget of a type"
    bl_options = {"REGISTER", "UNDO"}

    widget_type: StringProperty(name="Type", default="inkImageWidget")

    def execute(self, context):
        matched = 0
        for obj in context.view_layer.objects:
            if (
                obj.get(hierarchy.WIDGET_PATH_KEY) is not None
                and obj.get("cp77_type") == self.widget_type
            ):
                obj.select_set(True)
                matched += 1
        if not matched:
            report(self, "WARNING", f"No {self.widget_type} handles", logger=_LOG)
            return {"CANCELLED"}
        return {"FINISHED"}


INK_OPERATOR_CLASSES = (
    CP77_OT_ImportInkWidget,
    CP77_OT_InkRefresh,
    CP77_OT_InkExport,
    CP77_OT_InkPlaySequence,
    CP77_OT_InkStopSequence,
    CP77_OT_InkSelectByType,
)
