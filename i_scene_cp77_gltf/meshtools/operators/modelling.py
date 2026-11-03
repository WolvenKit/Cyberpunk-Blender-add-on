from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty
from bpy.types import Operator

<<<<<<< Updated upstream
from ...blender.transforms import rotate_quat_180
from ..services.armature_service import delete_unused_bones
from ..services.mesh_cleanup_service import prepare_submesh, set_armature_target
from ..services.mirror_service import mirror_selected_meshes_x, mirror_selected_vertex_groups
from ..services.submesh_service import safe_join, safe_split
from ..model import ShrinkwrapRequest
from ..services.shrinkwrap_service import add_shrinkwrap
from .result import finish_operator


class CP77GarmentSupport(Operator):
    bl_idname = 'cp77.shrinkwrap'
    bl_label = "Cyberpunk 2077 Shrinkwrap Tool"
    bl_description = "Shrinkwrap selection on top of another mesh"
    bl_options = {'REGISTER', 'UNDO'}
=======
from ...blender.operator_results import OperationResult, finish_operator
from ...blender.transforms import rotate_quat_180
from ..model import ShrinkwrapRequest
from ..services.armature_service import delete_orphan_bones, delete_unused_bones
from ..services.mesh_cleanup_service import prepare_submesh, set_armature_target
from ..services.mirror_service import (
    mirror_selected_meshes_x,
    mirror_selected_vertex_groups,
)
from ..services.shrinkwrap_service import add_shrinkwrap
from ..services.submesh_service import safe_join, safe_split


class CP77GarmentSupport(Operator):
    bl_idname = "cp77.shrinkwrap"
    bl_label = "Cyberpunk 2077 Shrinkwrap Tool"
    bl_description = "Shrinkwrap selection on top of another mesh"
    bl_options = {"REGISTER", "UNDO"}
>>>>>>> Stashed changes

    mesh_target: StringProperty(name="Mesh Target")

    as_garment_support: BoolProperty(
<<<<<<< Updated upstream
            name="As Garment Support",
            description="Modifier is GarmentSupport",
            default=True
            )

    apply_immediately: BoolProperty(
            name="Apply immediately",
            description="Unchecking this box will preserve the modifier",
            default=True
            )

    offset: FloatProperty(
            name="Offset",
            description="Offset distance for shrinkwrap",
            default=0.0002,
            step=0.0001,
            precision=5,
            )

    wrap_method: EnumProperty(

            description="How to wrap your mesh?",
            items=[
                ('NEAREST_SURFACEPOINT', "Nearest Surface Point", "Shrink the mesh to the nearest target surface."),
                ('PROJECT', "Project", "Shrink the mesh to the nearest target surface along a given axis."),
                ('NEAREST_VERTEX', "Nearest Vertex", "Shrink the mesh to the nearest target vertex."),
                ('TARGET_PROJECT', "Target Normal Project",
                 "Shrink the mesh to the nearest target surface along the interpolated vertex normals of the target.")
                ],
            default='NEAREST_SURFACEPOINT'
            )

    def invoke(self, context, event):
        try:
            context.scene.vertex_group_props.presets = ''  # Reset to trigger refresh
        except Exception:
            pass

=======
        name="As Garment Support",
        description="Modifier is GarmentSupport",
        default=True,
    )

    apply_immediately: BoolProperty(
        name="Apply immediately",
        description="Unchecking this box will preserve the modifier",
        default=True,
    )

    offset: FloatProperty(
        name="Offset",
        description="Offset distance for shrinkwrap",
        default=0.0002,
        step=0.0001,
        precision=5,
    )

    wrap_method: EnumProperty(
        description="How to wrap your mesh?",
        items=[
            (
                "NEAREST_SURFACEPOINT",
                "Nearest Surface Point",
                "Shrink the mesh to the nearest target surface.",
            ),
            (
                "PROJECT",
                "Project",
                "Shrink the mesh to the nearest target surface along a given axis.",
            ),
            (
                "NEAREST_VERTEX",
                "Nearest Vertex",
                "Shrink the mesh to the nearest target vertex.",
            ),
            (
                "TARGET_PROJECT",
                "Target Normal Project",
                "Shrink the mesh to the nearest target surface along the interpolated vertex normals of the target.",
            ),
        ],
        default="NEAREST_SURFACEPOINT",
    )

    def invoke(self, context, event):
        context.scene.vertex_group_props.presets = "None"
>>>>>>> Stashed changes
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        vertex_group = None

<<<<<<< Updated upstream
        # read vertex group dropdown value
        if context.scene.vertex_group_props.presets and context.scene.vertex_group_props.presets != 'None':
=======
        if (
            context.scene.vertex_group_props.presets
            and context.scene.vertex_group_props.presets != "None"
        ):
>>>>>>> Stashed changes
            vertex_group = context.scene.vertex_group_props.presets

        request = ShrinkwrapRequest(
            target_collection_name=context.scene.cp77_panel_props.mesh_target,
            offset=self.offset,
            wrap_method=self.wrap_method,
            as_garment_support=self.as_garment_support,
            apply_immediately=self.apply_immediately,
            vertex_group=vertex_group,
        )
        return finish_operator(self, add_shrinkwrap(context, request))

    def draw(self, context):
        props = context.scene.cp77_panel_props
        vg_props = context.scene.vertex_group_props
        layout = self.layout

        row = layout.row(align=True)
        split = row.split(factor=0.3, align=True)
        split.label(text="Target Mesh:")
        split.prop(props, "mesh_target", text="")

        row = layout.row(align=True)
        split = row.split(factor=0.3, align=True)
        split.label(text="As Garment Support:")
        split.prop(self, "as_garment_support")

        row = layout.row(align=True)
        split = row.split(factor=0.3, align=True)
        split.label(text="Apply immediately:")
        split.prop(self, "apply_immediately")

        row = layout.row(align=True)
        split = row.split(factor=0.3, align=True)
        split.label(text="Offset:")
        split.prop(self, "offset")

        row = layout.row(align=True)
        split = row.split(factor=0.3, align=True)
        split.label(text="Wrap Method:")
        split.prop(self, "wrap_method", text="")

        row = layout.row(align=True)
        split = row.split(factor=0.3, align=True)
        split.label(text="Vertex Group:")
        split.prop(vg_props, "presets", text="")


class CP77SafeJoin(Operator):
    bl_idname = "cp77.safe_join"
    bl_label = "Join Selected Meshes"
    bl_description = "Join selected meshes while preserving submesh information"
<<<<<<< Updated upstream
    bl_options = {'REGISTER', 'UNDO'}

    # Show a confirmation window before triggering the function
    # def invoke(self, context, event):
    #     return context.window_manager.invoke_props_dialog(self)
=======
    bl_options = {"REGISTER", "UNDO"}
>>>>>>> Stashed changes

    def execute(self, context):
        return finish_operator(self, safe_join(context))


class CP77SafeSplit(Operator):
    bl_idname = "cp77.safe_split"
    bl_label = "Split Selected Meshes"
    bl_description = "Split selected mesh back into submeshes"
<<<<<<< Updated upstream
    bl_options = {'REGISTER', 'UNDO'}

    # Show a confirmation window before triggering the function
    # def invoke(self, context, event):
    #     return context.window_manager.invoke_props_dialog(self)
=======
    bl_options = {"REGISTER", "UNDO"}
>>>>>>> Stashed changes

    def execute(self, context):
        return finish_operator(self, safe_split(context))


class CP77SetArmature(Operator):
    bl_idname = "cp77.set_armature"
    bl_label = "Change Armature Target"
    bl_parent_id = "CP77_PT_MeshTools"
    bl_description = "Change the armature modifier on selected meshes to the target"

    reparent: BoolProperty(
<<<<<<< Updated upstream
            name="Also Reparent Selected Meshes to the Armature",
            default=True
            )
=======
        name="Parent to Armature",
        description="Also parent the selected meshes to the target armature",
        default=True,
    )
>>>>>>> Stashed changes

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        return finish_operator(self, set_armature_target(context, self.reparent))

    def draw(self, context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        row = layout.row(align=True)
        split = row.split(factor=0.35, align=True)
        split.label(text="Armature Target:")
        split.prop(props, "selected_armature", text="")
        col = layout.column()
<<<<<<< Updated upstream
        col.prop(self, 'reparent')
=======
        col.prop(self, "reparent")
>>>>>>> Stashed changes


class CP77_OT_submesh_prep(Operator):
    # based on Rudolph2109's function
    bl_label = "Prep. It!"
    bl_idname = "cp77.submesh_prep"
    bl_parent_id = "CP77_PT_MeshTools"
<<<<<<< Updated upstream
    bl_options = {'REGISTER', "UNDO"}
=======
    bl_options = {"REGISTER", "UNDO"}
>>>>>>> Stashed changes
    bl_description = "Mark seams based on edges boundary loops, merge vertices, correct and smooth normals based on the direction of the faces"

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        props = context.scene.cp77_panel_props
        return finish_operator(
            self,
            prepare_submesh(context, props.smooth_factor, props.merge_distance),
        )

    def draw(self, context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        row = layout.row(align=True)
        split = row.split(factor=0.7, align=True)
        split.label(text="Merge Distance:")
        split.prop(props, "merge_distance", text="", slider=True)
        row = layout.row(align=True)
        split = row.split(factor=0.7, align=True)
<<<<<<< Updated upstream
        split.label(text="Smooth Factor:")
=======
        split.label(text="Smooth Angle:")
>>>>>>> Stashed changes
        split.prop(props, "smooth_factor", text="", slider=True)


class CP77RotateObj(Operator):
    bl_label = "Change Orientation"
    bl_idname = "cp77.rotate_obj"
    bl_description = "Rotate the selected object 180 degrees"
<<<<<<< Updated upstream

    def execute(self, context):
        rotate_quat_180(self, context)
        return {'FINISHED'}
=======
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        turned, kept = rotate_quat_180(self, context)
        if not turned:
            return finish_operator(
                self, OperationResult.cancelled("Select the objects to rotate.")
            )
        message = f"Rotated {len(turned)} object(s) 180 degrees."
        if kept:
            return finish_operator(
                self,
                OperationResult.finished(
                    f"{message} {len(kept)} share their mesh with objects that were not rotated the same way, "
                    "so their rotation stays on the object.",
                    level="WARNING",
                ),
            )
        return finish_operator(self, OperationResult.finished(message))
>>>>>>> Stashed changes


class CP77_OT_MirrorVertexGroups(Operator):
    bl_idname = "cp77.mirror_vertex_groups"
    bl_label = "Mirror vertex groups"
<<<<<<< Updated upstream
    bl_options = {'REGISTER', 'UNDO'}
=======
    bl_options = {"REGISTER", "UNDO"}
>>>>>>> Stashed changes

    def execute(self, context):
        return finish_operator(self, mirror_selected_vertex_groups(context))


class CP77_OT_MirrorXAxis(Operator):
    bl_idname = "cp77.mirror_x_axis"
    bl_label = "Safely mirror across X axis"
<<<<<<< Updated upstream
    bl_options = {'REGISTER', 'UNDO'}
=======
    bl_options = {"REGISTER", "UNDO"}
>>>>>>> Stashed changes

    def execute(self, context):
        return finish_operator(self, mirror_selected_meshes_x(context))


class CP77DeleteUnusedBones(Operator):
    bl_idname = "delete_unused_bones.cp77"
    bl_parent_id = "CP77_PT_animspanel"
    bl_label = "Delete unused bones"
<<<<<<< Updated upstream
    bl_description = "Delete all bones that aren't used by meshes parented to the armature"

    def execute(self, context):
        return finish_operator(self, delete_unused_bones(context))
=======
    bl_description = (
        "Delete all bones that aren't used by meshes parented to the armature"
    )

    def execute(self, context):
        return finish_operator(self, delete_unused_bones(context))


class CP77DeleteOrphanBones(Operator):
    bl_idname = "cp77.delete_orphan_bones"
    bl_label = "Delete Orphan Bones"
    bl_description = "Remove bones from associated armatures unless their exact name matches a vertex group in any selected mesh"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return any(obj.type == "MESH" for obj in context.selected_objects)

    def execute(self, context):
        return finish_operator(self, delete_orphan_bones(context))
>>>>>>> Stashed changes
