import typing

import bpy

from .constants import ANIMGRAPH_TREE_ID


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
            from . import variable_bindings
            return variable_bindings.root_tree_for(tree) or tree
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


class REDENGINE_PT_subgraph_nav(bpy.types.Panel):
    bl_idname = "REDENGINE_PT_subgraph_nav"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "AnimGraph"
    bl_label = "Subgraph"

    @classmethod
    def poll(cls, context):
        space = context.space_data
        if space is None or space.type != 'NODE_EDITOR':
            return False
        tree = space.node_tree
        return tree is not None and tree.bl_idname == ANIMGRAPH_TREE_ID

    def draw(self, context):
        layout = self.layout
        space = context.space_data
        depth = len(space.path) if space.path else 0

        active = context.active_node
        if active is not None and getattr(active, "node_tree", None) is not None:
            enter = layout.operator(
                "redengine.enter_group",
                text=f"Enter {active.label or active.name}",
                icon='NODETREE',
            )
            enter.node_name = active.name

        if depth > 1:
            layout.operator("redengine.exit_group", text="Exit Subgraph", icon='LOOP_BACK')

        layout.label(text=f"Path depth: {depth}")


def _root_animgraph_tree(tree):
    current = tree
    visited = set()
    while current is not None:
        try:
            pointer = int(current.as_pointer())
        except Exception:
            pointer = id(current)
        if pointer in visited:
            break
        visited.add(pointer)
        parent_name = str(current.get("red_parent_graph", "") or "")
        if not parent_name:
            break
        parent = bpy.data.node_groups.get(parent_name)
        if parent is None:
            break
        current = parent
    return current


class REDENGINE_PT_dangle_bridge(bpy.types.Panel):
    bl_idname = "REDENGINE_PT_dangle_bridge"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "AnimGraph"
    bl_label = "Dangle Editor"

    @classmethod
    def poll(cls, context):
        space = context.space_data
        if space is None or space.type != 'NODE_EDITOR':
            return False
        tree = _root_animgraph_tree(space.node_tree)
        return bool(
            tree is not None
            and tree.bl_idname == ANIMGRAPH_TREE_ID
            and str(tree.get("cp77_dangle_rig", "") or "")
        )

    def draw(self, context):
        layout = self.layout
        root = _root_animgraph_tree(context.space_data.node_tree)
        rig_name = str(root.get("cp77_dangle_rig", "") or "") if root else ""
        if rig_name:
            layout.label(text=f"Rig: {rig_name}", icon='ARMATURE_DATA')

        row = layout.row(align=True)
        row.operator("dangle.switch_to_editor", icon='VIEW3D', text="Editor View")

        sync_row = layout.row(align=True)
        sync_row.operator("dangle.push_to_editor", icon='EXPORT', text="Push to Editor")
        sync_row.operator("dangle.pull_from_editor", icon='IMPORT', text="Pull from Editor")


class REDENGINE_PT_graph_validator(bpy.types.Panel):
    bl_idname = "REDENGINE_PT_graph_validator"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "AnimGraph"
    bl_label = "Graph Validator"

    @classmethod
    def poll(cls, context):
        space = context.space_data
        if space is None or space.type != 'NODE_EDITOR':
            return False
        tree = space.node_tree
        return tree is not None and tree.bl_idname == ANIMGRAPH_TREE_ID

    @staticmethod
    def _metric(layout, label: str, value: str, *, icon: str = 'NONE'):
        row = layout.row(align=True)
        row.label(text=label, icon=icon)
        row.label(text=str(value))

    def draw(self, context):
        from . import graph_validator

        layout = self.layout
        tree = context.space_data.node_tree
        report = graph_validator.load_report_from_tree(tree)

        layout.operator('redengine.validate_graph', text='Validate Graph', icon='CHECKMARK')

        if not report:
            layout.label(text='No validation report yet.', icon='INFO')
            return

        ready = bool(report.get('ready', False))
        counters = report.get('counters', {}) if isinstance(report, dict) else {}
        blocking = report.get('blocking', []) if isinstance(report, dict) else []
        warnings = report.get('warnings', []) if isinstance(report, dict) else []
        summary = report.get('artist_summary', '') or report.get('summary', '')

        status = layout.box()
        status.label(text=('Graph ready for export' if ready else 'Graph needs fixes'), icon=('CHECKMARK' if ready else 'ERROR'))
        if summary:
            status.label(text=str(summary))

        metrics = layout.box()
        metrics.label(text='Validation coverage', icon='RNA')
        self._metric(metrics, 'Runtime nodes', f"{counters.get('runtime_nodes_valid', 0)} / {counters.get('runtime_nodes_total', 0)}")
        self._metric(metrics, 'Properties', f"{counters.get('properties_valid', 0)} / {counters.get('properties_total', 0)}")
        self._metric(metrics, 'Input sockets', f"{counters.get('input_sockets_valid', 0)} / {counters.get('input_sockets_total', 0)}")
        self._metric(metrics, 'Dataflow links', f"{counters.get('links_valid', 0)} / {counters.get('links_total', 0)}")
        self._metric(metrics, 'Variables', f"{counters.get('variables_valid', 0)} / {counters.get('variables_total', 0)}")
        self._metric(metrics, 'Handle refs', f"missing {counters.get('missing_handle_refs', 0)}, duplicates {counters.get('duplicate_handle_ids', 0)}")
        self._metric(metrics, 'Issues', f"{counters.get('blocking_issues', 0)} blocking, {counters.get('warnings', 0)} warnings")

        if blocking:
            err = layout.box()
            err.label(text='Fix before export', icon='ERROR')
            for item in blocking[:10]:
                err.label(text=str(item))
            if len(blocking) > 10:
                err.label(text=f"... {len(blocking) - 10} more")

        if warnings:
            warn = layout.box()
            warn.label(text='Warnings', icon='INFO')
            for item in warnings[:8]:
                warn.label(text=str(item))
            if len(warnings) > 8:
                warn.label(text=f"... {len(warnings) - 8} more")

        active = context.active_node
        if active is not None:
            details = layout.box()
            details.label(text='Active node', icon='NODE')
            details.label(text=f"HandleId: {getattr(active, 'red_handle_id', '') or '<none>'}")
            details.label(text=f"Type: {getattr(active, 'red_type', '') or '<none>'}")
            details.label(text=f"Exportable: {bool(getattr(active, 'red_exportable', False))}")
