import typing

import bpy

from ....animation.animgraph_constants import ANIMGRAPH_TREE_ID

class REDENGINE_PT_inputs(bpy.types.Panel):
    bl_idname = "REDENGINE_PT_inputs"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "AnimGraph"
    bl_label = "Inputs"

    @classmethod
    def poll(cls, context):
        space = context.space_data
        if space is None or space.type != 'NODE_EDITOR':
            return False
        tree = space.node_tree
        return tree is not None and tree.bl_idname == ANIMGRAPH_TREE_ID

    @staticmethod
    def _root_tree(tree):
        try:
            from ....blender.animgraph import variables
            return variables.root_tree_for(tree) or tree
        except Exception:
            return tree

    def _draw_variable_value(self, layout, var):
        vt = var.var_type
        if vt == 'Bool':
            row = layout.row(align=True)
            row.prop(var, 'current_bool', text='Value')
            row.prop(var, 'default_bool', text='Default')
        elif vt == 'Int':
            row = layout.row(align=True)
            row.prop(var, 'current_int', text='Value')
            row.prop(var, 'default_int', text='Default')
        elif vt == 'Float':
            if var.has_float_range:
                layout.label(text=f'Allowed range: {var.min_float:g} .. {var.max_float:g}', icon='DRIVER_DISTANCE')
            row = layout.row(align=True)
            row.prop(var, 'current_float', text='Value')
            row.prop(var, 'default_float', text='Default')
            if var.has_float_range:
                row = layout.row(align=True)
                row.label(text='Range')
                row.prop(var, 'min_float', text='Min')
                row.prop(var, 'max_float', text='Max')
        elif vt in {'Vector', 'Quaternion'}:
            labels = ('i', 'j', 'k', 'r') if vt == 'Quaternion' else ('X', 'Y', 'Z', 'W')
            row = layout.row(align=True)
            row.label(text='Value')
            for idx, label in enumerate(labels):
                row.prop(var, 'current_vector', index=idx, text=label)
            row = layout.row(align=True)
            row.label(text='Default')
            for idx, label in enumerate(labels):
                row.prop(var, 'default_vector', index=idx, text=label)
        else:
            layout.prop(var, 'current_value', text='Value')
            layout.prop(var, 'default_value', text='Default')

    _VARIABLE_GROUPS = (
        ('Bool', 'variables_bool_expanded'),
        ('Int', 'variables_int_expanded'),
        ('Float', 'variables_float_expanded'),
        ('Vector', 'variables_vector_expanded'),
        ('Quaternion', 'variables_quaternion_expanded'),
        ('Transform', 'variables_transform_expanded'),
    )

    def _draw_variable_group_header(self, box, tree, var_type: str, expanded_prop: str):
        row = box.row(align=True)
        expanded = bool(getattr(tree, expanded_prop, True))
        icon = 'TRIA_DOWN' if expanded else 'TRIA_RIGHT'
        row.prop(tree, expanded_prop, text='', icon=icon, emboss=False)
        row.label(text=var_type)
        return expanded

    def _draw_variable_entry(self, layout, var):
        vbox = layout.box()
        row = vbox.row(align=True)
        icon = 'TRIA_DOWN' if var.expanded else 'TRIA_RIGHT'
        row.prop(var, 'expanded', text='', icon=icon, emboss=False)
        row.prop(var, 'name', text='')
        if not var.expanded:
            return
        detail = vbox.column(align=True)
        meta = detail.row(align=True)
        meta.label(text=f"HandleId: {var.handle_id or '<none>'}")
        meta.label(text=f"Source: {var.source_array or '-'}")
        detail.prop(var, 'enable_debug', text='Enable Debug')
        self._draw_variable_value(detail, var)
        if var.consumer_handles:
            detail.label(text=f"Consumers: {var.consumer_handles}", icon='NODE')
        else:
            detail.label(text='No matching Variable nodes found.', icon='INFO')

    def _draw_variables(self, layout, tree):
        by_type: typing.Dict[str, typing.List[object]] = {var_type: [] for var_type, _ in self._VARIABLE_GROUPS}
        for var in getattr(tree, 'variables', []) or []:
            by_type.setdefault(str(getattr(var, 'var_type', '')), []).append(var)

        for var_type, expanded_prop in self._VARIABLE_GROUPS:
            entries = by_type.get(var_type, [])
            box = layout.box()
            expanded = self._draw_variable_group_header(box, tree, var_type, expanded_prop)
            if not expanded:
                continue
            body = box.column(align=True)
            if not entries:
                body.label(text='No variables declared.', icon='INFO')
                continue
            for var in entries:
                self._draw_variable_entry(body, var)

    def _draw_features(self, layout, tree):
        if not tree.features:
            layout.label(text="No anim features declared.", icon='INFO')
            return
        for feature in tree.features:
            box = layout.box()
            row = box.row(align=True)
            row.label(text=feature.name or "<unnamed>", icon='MODIFIER')
            detail = box.column(align=True)
            if feature.class_name:
                detail.label(text=f"Class: {feature.class_name}")
            detail.label(text=f"Debug enabled: {'Yes' if feature.debug_enabled else 'No'}")
            detail.label(text=f"Force allocate: {'Yes' if feature.force_allocate else 'No'}")

    def draw(self, context):
        layout = self.layout
        tree = self._root_tree(context.space_data.node_tree)
        if tree is None:
            layout.label(text="No AnimGraph tree.", icon='INFO')
            return

        if tree is not context.space_data.node_tree:
            layout.label(text=f"Root graph: {tree.name}", icon='NODETREE')

        try:
            layout.prop(tree, 'inputs_tab', expand=True)
            tab = tree.inputs_tab
        except Exception:
            tab = 'VARIABLES'

        if tab == 'FEATURES':
            self._draw_features(layout, tree)
        else:
            self._draw_variables(layout, tree)
