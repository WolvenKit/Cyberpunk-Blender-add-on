import textwrap

import bpy
from bpy.props import StringProperty
from bpy.types import Operator

from .registration import register_owned_classes, unregister_owned_classes


class ShowMessageBox(Operator):
    bl_idname = "cp77.message_box"
    bl_label = "Cyberpunk 2077 IO Suite"

    message: StringProperty(default="")

    def execute(self, context):
        self.report({'INFO'}, self.message)
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw_header(self, context):
        self.layout.label(text="Cyberpunk 2077 IO Suite")

    def draw(self, context):
        for line in textwrap.TextWrapper(width=70).wrap(text=self.message):
            row = self.layout.row(align=True)
            row.alignment = 'EXPAND'
            row.label(text=line)


def show_message(message):
    bpy.ops.cp77.message_box('INVOKE_DEFAULT', message=message)


_registered_classes = []


def register_notifications():
    if not _registered_classes:
        _registered_classes[:] = register_owned_classes((ShowMessageBox,))


def unregister_notifications():
    failures = unregister_owned_classes(reversed(_registered_classes))
    if not failures:
        _registered_classes.clear()
    if failures:
        raise RuntimeError("; ".join(f"{cls.__name__}: {error}" for cls, error in failures))
