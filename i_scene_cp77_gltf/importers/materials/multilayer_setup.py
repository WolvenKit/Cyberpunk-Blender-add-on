import bpy
from bpy_extras.io_utils import ImportHelper

from ...blender.operator_results import execute_operation
from ...core.notifications import import_operation
from .multilayer_setup_service import import_multilayer_setup


class CP77ImportMLSetup(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.mlsetup"
    bl_label = "Import MLSetup and Create Plane"
    filename_ext = ".json"

    filter_glob: bpy.props.StringProperty(
        default="*.mlsetup.json",
        options={"HIDDEN"},
    )

    @import_operation
    def execute(self, context):
        return execute_operation(
            self, "MLSetup import", import_multilayer_setup, context, self.filepath
        )
