import bpy

<<<<<<< Updated upstream
from ....blender.animgraph.property_codec import reset_curve_property_from_raw_json, sort_curve_points
from ....blender.animgraph import curve_mapping

def _active_curve_property(context, index):
    node = getattr(context, 'active_node', None)
    if node is None:
        return None
    props = getattr(node, 'red_properties', None)
    if props is None or index < 0 or index >= len(props):
        return None
    item = props[index]
    if item.value_kind != 'CURVE_FLOAT':
        return None
    return item

class REDENGINE_UL_curve_points(bpy.types.UIList):
    bl_idname = 'REDENGINE_UL_curve_points'

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.label(text=str(index))
            row.prop(item, 'point', text='Point')
            row.prop(item, 'value', text='Value')

class REDENGINE_OT_enter_editor_subgraph(bpy.types.Operator):
    bl_idname = 'redengine.enter_editor_subgraph'
    bl_label = 'Enter Editor Subgraph'
    bl_options = {'REGISTER', 'UNDO'}

    tree_name: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        space = context.space_data
        return space is not None and space.type == 'NODE_EDITOR'

    def execute(self, context):
        tree = bpy.data.node_groups.get(self.tree_name) if self.tree_name else None
        if tree is None:
            self.report({'WARNING'}, 'Editor subgraph not found')
            return {'CANCELLED'}
        try:
            context.space_data.path.append(tree)
        except TypeError:


            context.space_data.node_tree = tree
        return {'FINISHED'}

class REDENGINE_OT_curve_point_add(bpy.types.Operator):
    bl_idname = 'redengine.curve_point_add'
    bl_label = 'Add Curve Point'
    bl_options = {'REGISTER', 'UNDO'}

    property_index: bpy.props.IntProperty()

    def execute(self, context):
        item = _active_curve_property(context, self.property_index)
        if item is None:
            self.report({'WARNING'}, 'No active REDengine curve property')
            return {'CANCELLED'}

        count = len(item.curve_points)
        idx = max(0, min(item.curve_points_index, count - 1)) if count else 0
        if count == 0:
            x, y = 0.0, 0.0
        elif idx < count - 1:
            a = item.curve_points[idx]
            b = item.curve_points[idx + 1]
            x = (float(a.point) + float(b.point)) * 0.5
            y = (float(a.value) + float(b.value)) * 0.5
        else:
            a = item.curve_points[idx]
            step = 0.1
            if count >= 2:
                prev = item.curve_points[idx - 1]
                step = max(0.01, min(1.0, abs(float(a.point) - float(prev.point))))
            x = float(a.point) + step
            y = float(a.value)

        point = item.curve_points.add()
        point.point = x
        point.value = y
        item.curve_points_index = len(item.curve_points) - 1
        return {'FINISHED'}

class REDENGINE_OT_curve_point_remove(bpy.types.Operator):
    bl_idname = 'redengine.curve_point_remove'
    bl_label = 'Remove Curve Point'
    bl_options = {'REGISTER', 'UNDO'}

    property_index: bpy.props.IntProperty()

    def execute(self, context):
        item = _active_curve_property(context, self.property_index)
        if item is None or not item.curve_points:
            return {'CANCELLED'}
        idx = max(0, min(item.curve_points_index, len(item.curve_points) - 1))
        item.curve_points.remove(idx)
        item.curve_points_index = min(idx, max(0, len(item.curve_points) - 1))
        return {'FINISHED'}

class REDENGINE_OT_curve_points_sort(bpy.types.Operator):
    bl_idname = 'redengine.curve_points_sort'
    bl_label = 'Sort Curve Points'
    bl_options = {'REGISTER', 'UNDO'}

    property_index: bpy.props.IntProperty()

    def execute(self, context):
        item = _active_curve_property(context, self.property_index)
        if item is None:
            return {'CANCELLED'}
        sort_curve_points(item)
        return {'FINISHED'}

class REDENGINE_OT_curve_points_reset(bpy.types.Operator):
    bl_idname = 'redengine.curve_points_reset'
    bl_label = 'Reset Curve From Import'
    bl_options = {'REGISTER', 'UNDO'}

    property_index: bpy.props.IntProperty()

    def execute(self, context):
        item = _active_curve_property(context, self.property_index)
        if item is None:
            return {'CANCELLED'}
        if not reset_curve_property_from_raw_json(item):
            self.report({'WARNING'}, 'The stored raw JSON is not a curveData payload')
            return {'CANCELLED'}
        return {'FINISHED'}

class REDENGINE_OT_curve_widget_init(bpy.types.Operator):
    bl_idname = 'redengine.curve_widget_init'
    bl_label = 'Initialize Native Curve Widget'
    bl_options = {'REGISTER', 'UNDO'}

    property_index: bpy.props.IntProperty()

    def execute(self, context):
        node = getattr(context, 'active_node', None)
        item = _active_curve_property(context, self.property_index)
        if node is None or item is None:
            return {'CANCELLED'}
        helper = curve_mapping.get_helper_node(node, item, create=True)
        if helper is None or not curve_mapping.sync_native_from_property(item, helper):
            self.report({'WARNING'}, 'Could not create the native Blender curve widget')
            return {'CANCELLED'}
        return {'FINISHED'}

class REDENGINE_OT_curve_widget_push(bpy.types.Operator):
    bl_idname = 'redengine.curve_widget_push'
    bl_label = 'Push Points To Native Curve'
    bl_options = {'REGISTER', 'UNDO'}

    property_index: bpy.props.IntProperty()

    def execute(self, context):
        node = getattr(context, 'active_node', None)
        item = _active_curve_property(context, self.property_index)
        if node is None or item is None:
            return {'CANCELLED'}
        helper = curve_mapping.get_helper_node(node, item, create=True)
        if helper is None or not curve_mapping.sync_native_from_property(item, helper):
            self.report({'WARNING'}, 'Could not update the native Blender curve widget')
            return {'CANCELLED'}
        return {'FINISHED'}

class REDENGINE_OT_curve_widget_apply(bpy.types.Operator):
    bl_idname = 'redengine.curve_widget_apply'
    bl_label = 'Apply Native Curve To REDengine Data'
    bl_options = {'REGISTER', 'UNDO'}

    property_index: bpy.props.IntProperty()

    def execute(self, context):
        node = getattr(context, 'active_node', None)
        item = _active_curve_property(context, self.property_index)
        if node is None or item is None:
            return {'CANCELLED'}
        helper = curve_mapping.get_helper_node(node, item, create=False)
        if helper is None or not curve_mapping.sync_property_from_native(item, helper):
            self.report({'WARNING'}, 'Could not read the native Blender curve widget')
            return {'CANCELLED'}
        return {'FINISHED'}

class REDENGINE_OT_curve_point_move(bpy.types.Operator):
    bl_idname = 'redengine.curve_point_move'
    bl_label = 'Move Curve Point'
    bl_options = {'REGISTER', 'UNDO'}

    property_index: bpy.props.IntProperty()
    direction: bpy.props.EnumProperty(
        items=(('UP', 'Up', ''), ('DOWN', 'Down', '')),
        default='UP',
    )

    def execute(self, context):
        item = _active_curve_property(context, self.property_index)
        if item is None or len(item.curve_points) < 2:
            return {'CANCELLED'}
        idx = max(0, min(item.curve_points_index, len(item.curve_points) - 1))
        new_idx = idx - 1 if self.direction == 'UP' else idx + 1
        if new_idx < 0 or new_idx >= len(item.curve_points):
            return {'CANCELLED'}
        item.curve_points.move(idx, new_idx)
        item.curve_points_index = new_idx
        return {'FINISHED'}

curve_editor_classes = (
    REDENGINE_OT_enter_editor_subgraph,
    REDENGINE_UL_curve_points,
=======
from ....blender.operator_results import finish_operator
from ....core.log import get_logger
from ....core.notifications import report
from ...services.animgraph import editing
from .context import active_curve_property

_LOG = get_logger(__name__)


class _CurvePropertyOperator:
    bl_options = {"REGISTER", "UNDO"}

    property_index: bpy.props.IntProperty()


class REDENGINE_OT_curve_point_add(_CurvePropertyOperator, bpy.types.Operator):
    bl_idname = "redengine.curve_point_add"
    bl_label = "Add Curve Point"

    def execute(self, context):
        item = active_curve_property(context, self.property_index)
        if item is None:
            report(self, "WARNING", "No active REDengine curve property", logger=_LOG)
            return {"CANCELLED"}
        return finish_operator(self, editing.add_curve_point(item))


class REDENGINE_OT_curve_point_remove(_CurvePropertyOperator, bpy.types.Operator):
    bl_idname = "redengine.curve_point_remove"
    bl_label = "Remove Curve Point"

    def execute(self, context):
        item = active_curve_property(context, self.property_index)
        if item is None:
            return {"CANCELLED"}
        return finish_operator(self, editing.remove_curve_point(item))


class REDENGINE_OT_curve_points_sort(_CurvePropertyOperator, bpy.types.Operator):
    bl_idname = "redengine.curve_points_sort"
    bl_label = "Sort Curve Points"

    def execute(self, context):
        item = active_curve_property(context, self.property_index)
        if item is None:
            return {"CANCELLED"}
        return finish_operator(self, editing.sort_curve(item))


class REDENGINE_OT_curve_points_reset(_CurvePropertyOperator, bpy.types.Operator):
    bl_idname = "redengine.curve_points_reset"
    bl_label = "Reset Curve From Import"

    def execute(self, context):
        item = active_curve_property(context, self.property_index)
        if item is None:
            return {"CANCELLED"}
        return finish_operator(self, editing.reset_curve(item))


class REDENGINE_OT_curve_widget_init(_CurvePropertyOperator, bpy.types.Operator):
    bl_idname = "redengine.curve_widget_init"
    bl_label = "Initialize Native Curve Widget"

    def execute(self, context):
        node = getattr(context, "active_node", None)
        item = active_curve_property(context, self.property_index)
        if node is None or item is None:
            return {"CANCELLED"}
        return finish_operator(
            self,
            editing.push_curve_widget(
                node, item, failure="Could not create the native Blender curve widget"
            ),
        )


class REDENGINE_OT_curve_widget_push(_CurvePropertyOperator, bpy.types.Operator):
    bl_idname = "redengine.curve_widget_push"
    bl_label = "Push Points To Native Curve"

    def execute(self, context):
        node = getattr(context, "active_node", None)
        item = active_curve_property(context, self.property_index)
        if node is None or item is None:
            return {"CANCELLED"}
        return finish_operator(
            self,
            editing.push_curve_widget(
                node, item, failure="Could not update the native Blender curve widget"
            ),
        )


class REDENGINE_OT_curve_widget_apply(_CurvePropertyOperator, bpy.types.Operator):
    bl_idname = "redengine.curve_widget_apply"
    bl_label = "Apply Native Curve To REDengine Data"

    def execute(self, context):
        node = getattr(context, "active_node", None)
        item = active_curve_property(context, self.property_index)
        if node is None or item is None:
            return {"CANCELLED"}
        return finish_operator(self, editing.apply_curve_widget(node, item))


class REDENGINE_OT_curve_point_move(_CurvePropertyOperator, bpy.types.Operator):
    bl_idname = "redengine.curve_point_move"
    bl_label = "Move Curve Point"

    direction: bpy.props.EnumProperty(
        items=(("UP", "Up", ""), ("DOWN", "Down", "")),
        default="UP",
    )

    def execute(self, context):
        item = active_curve_property(context, self.property_index)
        if item is None:
            return {"CANCELLED"}
        return finish_operator(self, editing.move_curve_point(item, self.direction))


CURVE_OPERATOR_CLASSES = (
>>>>>>> Stashed changes
    REDENGINE_OT_curve_point_add,
    REDENGINE_OT_curve_point_remove,
    REDENGINE_OT_curve_points_sort,
    REDENGINE_OT_curve_points_reset,
    REDENGINE_OT_curve_widget_init,
    REDENGINE_OT_curve_widget_push,
    REDENGINE_OT_curve_widget_apply,
    REDENGINE_OT_curve_point_move,
)
