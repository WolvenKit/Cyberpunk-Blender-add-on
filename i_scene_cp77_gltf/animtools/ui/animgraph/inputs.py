
import bpy

from ....animation.model.animgraph.constants import ANIMGRAPH_TREE_ID
from ....blender.animgraph import rig_binding
from ....blender.animgraph.variables import root_tree_for
from .node_widgets import draw_binding_box
from .variable_widgets import draw_variable_value


class REDENGINE_PT_inputs(bpy.types.Panel):
    bl_idname = "REDENGINE_PT_inputs"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Inputs"
    bl_label = "Inputs"

    @classmethod
    def poll(cls, context):
        space = context.space_data
        if space is None or space.type != "NODE_EDITOR":
            return False
        tree = space.node_tree
        return tree is not None and tree.bl_idname == ANIMGRAPH_TREE_ID

    _VARIABLE_GROUPS = (
        ("Bool", "variables_bool_expanded"),
        ("Int", "variables_int_expanded"),
        ("Float", "variables_float_expanded"),
        ("Vector", "variables_vector_expanded"),
        ("Quaternion", "variables_quaternion_expanded"),
        ("Transform", "variables_transform_expanded"),
    )

    def _draw_variable_group_header(self, box, tree, var_type: str, expanded_prop: str):
        row = box.row(align=True)
        expanded = bool(getattr(tree, expanded_prop, True))
        icon = "TRIA_DOWN" if expanded else "TRIA_RIGHT"
        row.prop(tree, expanded_prop, text="", icon=icon, emboss=False)
        row.label(text=var_type)
        return expanded

    def _draw_variable_entry(self, layout, var):
        vbox = layout.box()
        row = vbox.row(align=True)
        icon = "TRIA_DOWN" if var.expanded else "TRIA_RIGHT"
        row.prop(var, "expanded", text="", icon=icon, emboss=False)
        row.prop(var, "name", text="")
        if not var.expanded:
            return
        detail = vbox.column(align=True)
        detail.prop(var, "enable_debug", text="Enable Debug")
        draw_variable_value(detail, var)

    def _draw_variables(self, layout, tree):
        by_type: dict[str, list[object]] = {
            var_type: [] for var_type, _ in self._VARIABLE_GROUPS
        }
        for var in getattr(tree, "variables", []) or []:
            by_type.setdefault(str(getattr(var, "var_type", "")), []).append(var)

        for var_type, expanded_prop in self._VARIABLE_GROUPS:
            entries = by_type.get(var_type, [])
            box = layout.box()
            expanded = self._draw_variable_group_header(
                box, tree, var_type, expanded_prop
            )
            if not expanded:
                continue
            body = box.column(align=True)
            if not entries:
                body.label(text="No variables declared.", icon="INFO")
                continue
            for var in entries:
                self._draw_variable_entry(body, var)

    def _draw_features(self, layout, tree):
        if not tree.features:
            layout.label(text="No anim features declared.", icon="INFO")
            return
        for feature in tree.features:
            box = layout.box()
            row = box.row(align=True)
            row.label(text=feature.name or "<unnamed>", icon="MODIFIER")

    def draw(self, context):
        layout = self.layout
        tree = (
            root_tree_for(context.space_data.node_tree) or context.space_data.node_tree
        )
        if tree is None:
            layout.label(text="No AnimGraph tree.", icon="INFO")
            return

        draw_binding_box(
            layout, tree, context, armature=rig_binding.bound_armature(tree)
        )

        layout.prop(tree, "inputs_tab", expand=True)
        if tree.inputs_tab == "FEATURES":
            self._draw_features(layout, tree)
        else:
            self._draw_variables(layout, tree)
