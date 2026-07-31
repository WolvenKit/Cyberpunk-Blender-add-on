import bpy
from bpy.types import Operator

from ..services.facial import runtime, session


class FACIAL_OT_ToggleSolver(Operator):
    bl_idname = "cp77_facial.toggle_solver"
    bl_label = "Toggle Solver"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return any(obj.type == "ARMATURE" and session.is_bound(obj) for obj in context.scene.objects)

    def execute(self, context):
        if runtime.is_solver_active():
            runtime.disable_solver(context)
            self.report({"INFO"}, "CP77 Facial Solver: disabled")
        else:
            runtime.enable_solver(context)
            self.report({"INFO"}, "CP77 Facial Solver: enabled")
        return {"FINISHED"}


class FACIAL_OT_SolveNow(Operator):
    bl_idname = "cp77_facial.solve_now"
    bl_label = "Solve Now"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return any(obj.type == "ARMATURE" and session.is_bound(obj) for obj in context.scene.objects)

    def execute(self, context):
        runtime.solve_frame(context.scene)
        timing = bpy.app.driver_namespace.get("cp77_facial_last_ms", {})
        if timing:
            message = ", ".join(f"'{name}': {value:.1f} ms" for name, value in timing.items())
            self.report({"INFO"}, "Solved — " + message)
        else:
            self.report({"INFO"}, "Solve complete")
        return {"FINISHED"}
