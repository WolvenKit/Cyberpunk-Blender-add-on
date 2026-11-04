import os
import sys

import bpy
from bpy.props import StringProperty
from bpy.types import Operator

from ..assetio.atomic import atomic_write_text
from ..core.log import get_logger
from ..core.notifications import report
from ..core.registration import get_classes
from .user_scripts import (
    follow_renamed_script,
    forget_deleted_script,
    is_managed_text,
    load_managed_text,
    resolve_user_script_path,
)

_LOG = get_logger(__name__)


class CP77CreateScript(Operator):
    """Operator to add a new blank .py file to the scripts directory"""

    bl_idname = "script_manager.create_script"
    bl_label = "Create New Script"
    bl_description = "Create a new script in the CP77 modding scripts directory"

    script_name: bpy.props.StringProperty(name="Script Name", default="new_script")

    def execute(self, context):
        base_name = str(self.script_name or "").strip()
        try:
            resolve_user_script_path(base_name, add_extension=True)
        except ValueError as error:
            report(self, "ERROR", str(error), logger=_LOG, error=error)
            return {"CANCELLED"}
        script_name = base_name
        if not script_name.casefold().endswith(".py"):
            script_name += ".py"
        i = 1

        while os.path.exists(resolve_user_script_path(script_name)):
            stem = os.path.splitext(base_name)[0]
            script_name = f"{stem}_{i}.py"
            i += 1

        atomic_write_text(
            resolve_user_script_path(script_name),
            "# New Script\n",
        )

        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class CP77LoadScript(Operator):
    bl_idname = "script_manager.load_script"
    bl_label = "Load Script"
    bl_description = "Click to load or switch to this script, ctrl+click to rename"

    script_file: StringProperty()
    new_name: StringProperty(name="New name", default=".py")

    def execute(self, context):
        script_name = self.script_file

        if self.new_name:
            try:
                script_path = resolve_user_script_path(script_name)
                new_script_path = resolve_user_script_path(
                    self.new_name,
                    add_extension=True,
                )
            except ValueError as error:
                report(self, "ERROR", str(error), logger=_LOG, error=error)
                return {"CANCELLED"}

            if os.path.exists(script_path):
                if not os.path.exists(new_script_path):
                    os.rename(script_path, new_script_path)
                    follow_renamed_script(script_path, new_script_path)
                    report(
                        self,
                        "INFO",
                        f"Renamed '{script_name}' to "
                        f"'{os.path.basename(new_script_path)}'",
                        logger=_LOG,
                    )
                else:
                    report(
                        self,
                        "ERROR",
                        f"A script with the name '{self.new_name}' already exists.",
                        logger=_LOG,
                    )
                    return {"CANCELLED"}
            else:
                report(self, "ERROR", f"Script not found: {script_name}", logger=_LOG)
                return {"CANCELLED"}
        else:
            try:
                script_path = resolve_user_script_path(script_name)
            except ValueError as error:
                report(self, "ERROR", str(error), logger=_LOG, error=error)
                return {"CANCELLED"}
            if not os.path.exists(script_path):
                report(self, "ERROR", f"Script not found: {script_name}", logger=_LOG)
                return {"CANCELLED"}
            # The script's own text, not another one that happens to share its name.
            context.space_data.text = load_managed_text(script_path)

        return {"FINISHED"}

    def invoke(self, context, event):
        if event.ctrl:
            return context.window_manager.invoke_props_dialog(self)
        else:
            self.new_name = ""
            return self.execute(context)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "new_name")


class CP77SaveScript(Operator):
    bl_idname = "script_manager.save_script"
    bl_label = "Save Script"
    bl_description = "Press to save this script"

    script_file: StringProperty()

    def execute(self, context):
        script_text = context.space_data.text
        if not script_text:
            report(self, "ERROR", "No active text block to save.", logger=_LOG)
            return {"CANCELLED"}
        try:
            script_path = resolve_user_script_path(self.script_file)
        except ValueError as error:
            report(self, "ERROR", str(error), logger=_LOG, error=error)
            return {"CANCELLED"}
        if not is_managed_text(script_text, script_path):
            report(
                self,
                "ERROR",
                f"Active text '{script_text.name}' is not '{self.script_file}'. Load the target script before saving.",
                logger=_LOG,
            )
            return {"CANCELLED"}
        atomic_write_text(script_path, script_text.as_string())
        report(self, "INFO", f"Saved {self.script_file}", logger=_LOG)
        return {"FINISHED"}


class CP77DeleteScript(Operator):
    bl_idname = "script_manager.delete_script"
    bl_label = "Delete Script"
    bl_description = "Press to delete this script"

    script_file: StringProperty()

    def execute(self, context):
        try:
            script_path = resolve_user_script_path(self.script_file)
        except ValueError as error:
            report(self, "ERROR", str(error), logger=_LOG, error=error)
            return {"CANCELLED"}

        if os.path.exists(script_path):
            os.remove(script_path)
            forget_deleted_script(script_path)
            return {"FINISHED"}
        report(self, "ERROR", f"Script not found: {self.script_file}", logger=_LOG)
        return {"CANCELLED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


registration_classes = get_classes(sys.modules[__name__])
