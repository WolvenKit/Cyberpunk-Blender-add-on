import bpy

from . import sm_records
from .preview_settings import REDengine_GraphPreviewSettings
from .properties import REDengine_AnimFeature, REDengine_AnimVariable
from .rig_binding import armature_poll

# Callbacks run on every AnimGraph tree update; tool layers register theirs when they register.
_TREE_CHANGE_HOOKS = []


def register_tree_change_hook(callback) -> None:
    if callback not in _TREE_CHANGE_HOOKS:
        _TREE_CHANGE_HOOKS.append(callback)


def unregister_tree_change_hook(callback) -> None:
    while callback in _TREE_CHANGE_HOOKS:
        _TREE_CHANGE_HOOKS.remove(callback)


def _on_bound_armature_updated(tree, context):
    from .variables import bind_all_variables

    bind_all_variables(tree)


class REDengine_AnimGraphTree(bpy.types.NodeTree):
    bl_idname = "REDengine_AnimGraphTree"
    bl_label = "REDengine AnimGraph"
    bl_icon = "ACTION"

    variables: bpy.props.CollectionProperty(type=REDengine_AnimVariable)
    variables_index: bpy.props.IntProperty()
    red_variable_sync_suspended: bpy.props.BoolProperty(
        default=False, options={"HIDDEN"}
    )
    features: bpy.props.CollectionProperty(type=REDengine_AnimFeature)
    features_index: bpy.props.IntProperty()
    red_bound_armature: bpy.props.PointerProperty(
        name="Bound Armature",
        description="Persistent armature used for AnimGraph transform selectors and runtime previews",
        type=bpy.types.Object,
        poll=armature_poll,
        update=_on_bound_armature_updated,
    )
    red_rig_part: bpy.props.StringProperty(
        name="Rig Part",
        description="MetaRig part of the bound armature the graph animates; empty uses the part an entity's "
        "component binds the graph to, else the one whose rig file name matches the graph's",
    )
    red_source_text: bpy.props.StringProperty(
        name="Source Text",
        description="Hidden text holding the complete imported WolvenKit document",
        options={"HIDDEN"},
    )
    red_source_path: bpy.props.StringProperty(
        name="Source Path", subtype="FILE_PATH", options={"HIDDEN"}
    )
    red_preview: bpy.props.PointerProperty(type=REDengine_GraphPreviewSettings)
    red_pose_preview_armature: bpy.props.PointerProperty(
        type=bpy.types.Object,
        poll=armature_poll,
        options={"HIDDEN", "SKIP_SAVE"},
    )
    red_pose_preview_snapshot_json: bpy.props.StringProperty(
        options={"HIDDEN", "SKIP_SAVE"}
    )
    red_pose_preview_status: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    red_pose_preview_node: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    red_pose_preview_boundary: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    inputs_tab: bpy.props.EnumProperty(
        name="Inputs Tab",
        description="Active Inputs panel tab",
        items=(
            ("VARIABLES", "Variables", "Graph variable declarations"),
            ("FEATURES", "Features", "Anim feature declarations"),
        ),
        default="VARIABLES",
        options={"HIDDEN"},
    )

    variables_bool_expanded: bpy.props.BoolProperty(
        name="Bool Variables Expanded", default=True, options={"HIDDEN"}
    )
    variables_int_expanded: bpy.props.BoolProperty(
        name="Int Variables Expanded", default=True, options={"HIDDEN"}
    )
    variables_float_expanded: bpy.props.BoolProperty(
        name="Float Variables Expanded", default=True, options={"HIDDEN"}
    )
    variables_vector_expanded: bpy.props.BoolProperty(
        name="Vector Variables Expanded", default=True, options={"HIDDEN"}
    )
    variables_quaternion_expanded: bpy.props.BoolProperty(
        name="Quaternion Variables Expanded", default=True, options={"HIDDEN"}
    )
    variables_transform_expanded: bpy.props.BoolProperty(
        name="Transform Variables Expanded", default=True, options={"HIDDEN"}
    )

    def update(self):
        # sm_links reaches this module through sm_overlay, so it is imported here.
        from . import sm_links

        sm_records.bump_graph_generation()
        try:
            sm_links.schedule_consume(self)
        except (ReferenceError, RuntimeError, TypeError, ValueError):
            pass
        for callback in tuple(_TREE_CHANGE_HOOKS):
            try:
                callback(self)
            except (ReferenceError, RuntimeError, TypeError, ValueError):
                return

    @classmethod
    def poll(cls, context):
        return True
