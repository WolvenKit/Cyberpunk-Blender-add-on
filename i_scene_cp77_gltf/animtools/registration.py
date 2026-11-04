import bpy
from bpy.props import CollectionProperty, IntProperty, PointerProperty

from ..blender.animgraph import presenters, results_overlay, sm_overlay
from ..blender.animgraph.node_types import (
    REDengine_AnimGraphContainer,
    REDengine_AnimGraphNode_Generic,
)
from ..blender.animgraph.preview_settings import PREVIEW_SETTINGS_CLASSES
from ..blender.animgraph.properties import (
    REDengine_AnimArrayElement,
    REDengine_AnimArrayField,
    REDengine_AnimCurvePoint,
    REDengine_AnimFeature,
    REDengine_AnimNodeProperty,
    REDengine_AnimVariable,
    REDengine_PointConstraintWeightedTransform,
    REDengine_SimpleBounceChannelEntry,
    REDengine_SimpleBounceTrackOutput,
    REDengine_SimpleBounceTransformOutput,
)
from ..blender.animgraph.sm_properties import (
    REDengine_SMCondition,
    REDengine_SMStateRef,
    REDengine_SMTransition,
)
from ..blender.animgraph.sockets import (
    REDengine_AnimGraphSocket_Bool,
    REDengine_AnimGraphSocket_Editor,
    REDengine_AnimGraphSocket_Float,
    REDengine_AnimGraphSocket_Int,
    REDengine_AnimGraphSocket_Pose,
    REDengine_AnimGraphSocket_Quaternion,
    REDengine_AnimGraphSocket_Transform,
    REDengine_AnimGraphSocket_Transition,
    REDengine_AnimGraphSocket_TransitionOut,
    REDengine_AnimGraphSocket_Vector,
)
from ..blender.animgraph.tree import REDengine_AnimGraphTree
from ..collisiontools.runtime.dangle.preview import session_results
from ..core.log import get_logger
from ..core.registration import RegistrationLedger
from .operators.actions import ACTION_OPERATOR_CLASSES
from .operators.animgraph.add_node import REDENGINE_OT_add_node
from .operators.animgraph.curve import CURVE_OPERATOR_CLASSES
from .operators.animgraph.export import REDENGINE_OT_export_animgraph
from .operators.animgraph.navigation import (
    NAVIGATION_OPERATOR_CLASSES,
    REDENGINE_OT_enter_group,
    REDENGINE_OT_exit_group,
)
from .operators.animgraph.node_editing import NODE_EDITING_OPERATOR_CLASSES
from .operators.animgraph.node_pose import (
    NODE_POSE_OPERATOR_CLASSES,
    REDENGINE_OT_view_node_pose,
)
from .operators.animgraph.pose_preview import POSE_PREVIEW_OPERATOR_CLASSES
from .operators.animgraph.rig_part import REDENGINE_OT_bind_rig_part
from .operators.animgraph.state_machine import STATE_MACHINE_CLASSES
from .operators.animgraph.validation import REDENGINE_OT_validate_graph
from .operators.events import EVENT_OPERATOR_CLASSES
from .operators.facial import FACIAL_OPERATOR_CLASSES
from .operators.jali import JALI_OPERATOR_CLASSES
from .operators.overlay import OVERLAY_OPERATOR_CLASSES
from .operators.rig import RIG_OPERATOR_CLASSES
from .operators.rigify import RIGIFY_OPERATOR_CLASSES
from .operators.root_motion import ROOT_MOTION_OPERATOR_CLASSES
from .operators.workspace import WORKSPACE_OPERATOR_CLASSES
from .runtime import callbacks
from .ui import playback
from .ui.action_list import CP77_UL_AdditiveAnimList, CP77_UL_AnimList, CP77_UL_ClipList
from .ui.animgraph import (
    aim_constraint,
    direct_conn,
    point_constraint,
    property_draw,
    simple_bounce,
)
from .ui.animgraph.add_menu import ADD_MENU_CLASSES, menu_func_add
from .ui.animgraph.curve import REDENGINE_UL_curve_points
from .ui.animgraph.dangle import REDENGINE_PT_dangle_bridge
from .ui.animgraph.graph_tab import REDENGINE_PT_graph_source
from .ui.animgraph.header import draw_header_path
from .ui.animgraph.inputs import REDENGINE_PT_inputs
from .ui.animgraph.preview_tab import REDENGINE_PT_graph_preview
from .ui.animgraph.state_machine import STATE_MACHINE_UI_CLASSES
from .ui.animgraph.validation import REDENGINE_PT_graph_validator
from .ui.event_lists import (
    CP77_UL_AnimEventList,
    CP77_UL_ParamList,
    CP77_UL_SwitchList,
    CP77_UL_WorkspotActionList,
)
from .ui.events import CP77_PT_AnimEventsPanel
from .ui.panel import CP77_PT_AnimsPanel
from .ui.properties import (
    PROPERTY_CLASSES,
    CP77_AdditivePreviewSettings,
    CP77_AnimEventItem,
    CP77_FacialProps,
    CP77_RigAssemblyState,
    RootMotionData,
)
from .ui.rig_setup import CP77_UL_RigParts
from .ui.workspace_tabs import WORKSPACE_TAB_CLASSES

ANIMGRAPH_DATA_CLASSES = (
    REDengine_AnimCurvePoint,
    REDengine_AnimArrayField,
    REDengine_AnimArrayElement,
    REDengine_AnimNodeProperty,
    REDengine_AnimVariable,
    REDengine_AnimFeature,
    REDengine_SimpleBounceChannelEntry,
    REDengine_SimpleBounceTransformOutput,
    REDengine_SimpleBounceTrackOutput,
    REDengine_PointConstraintWeightedTransform,
    REDengine_SMCondition,
    REDengine_SMTransition,
    REDengine_SMStateRef,
    REDengine_AnimGraphSocket_Pose,
    REDengine_AnimGraphSocket_Float,
    REDengine_AnimGraphSocket_Vector,
    REDengine_AnimGraphSocket_Int,
    REDengine_AnimGraphSocket_Bool,
    REDengine_AnimGraphSocket_Quaternion,
    REDengine_AnimGraphSocket_Transform,
    REDengine_AnimGraphSocket_Transition,
    REDengine_AnimGraphSocket_TransitionOut,
    REDengine_AnimGraphSocket_Editor,
    *PREVIEW_SETTINGS_CLASSES,
    REDengine_AnimGraphTree,
    REDengine_AnimGraphNode_Generic,
    REDengine_AnimGraphContainer,
)

ANIMGRAPH_CLASSES = (
    *ANIMGRAPH_DATA_CLASSES,
    *NAVIGATION_OPERATOR_CLASSES,
    *NODE_POSE_OPERATOR_CLASSES,
    REDENGINE_PT_graph_source,
    REDENGINE_PT_graph_preview,
    REDENGINE_PT_inputs,
    REDENGINE_PT_graph_validator,
    REDENGINE_OT_bind_rig_part,
    REDENGINE_OT_export_animgraph,
    REDENGINE_PT_dangle_bridge,
    REDENGINE_OT_validate_graph,
    *NODE_EDITING_OPERATOR_CLASSES,
    *POSE_PREVIEW_OPERATOR_CLASSES,
    REDENGINE_UL_curve_points,
    *CURVE_OPERATOR_CLASSES,
    REDENGINE_OT_add_node,
    *ADD_MENU_CLASSES,
    *STATE_MACHINE_CLASSES,
    *STATE_MACHINE_UI_CLASSES,
)

CLASSES = (
    *PROPERTY_CLASSES,
    CP77_UL_RigParts,
    CP77_UL_AnimList,
    CP77_UL_AdditiveAnimList,
    CP77_UL_ClipList,
    CP77_UL_AnimEventList,
    CP77_UL_SwitchList,
    CP77_UL_ParamList,
    CP77_UL_WorkspotActionList,
    *RIG_OPERATOR_CLASSES,
    *ACTION_OPERATOR_CLASSES,
    *OVERLAY_OPERATOR_CLASSES,
    *FACIAL_OPERATOR_CLASSES,
    *JALI_OPERATOR_CLASSES,
    *RIGIFY_OPERATOR_CLASSES,
    *ROOT_MOTION_OPERATOR_CLASSES,
    *EVENT_OPERATOR_CLASSES,
    *WORKSPACE_OPERATOR_CLASSES,
    CP77_PT_AnimsPanel,
    CP77_PT_AnimEventsPanel,
    *WORKSPACE_TAB_CLASSES,
    *ANIMGRAPH_CLASSES,
)

NODE_DRAW_HOOKS = (
    ("AnimGraph", presenters.NODE_DRAW_FALLBACK, property_draw.draw_node),
    ("DirectConnConstraint", presenters.PRESENTER_DIRECT_CONN, direct_conn.draw_node),
    ("SimpleBounce", presenters.PRESENTER_SIMPLE_BOUNCE, simple_bounce.draw_node),
    (
        "PointConstraint",
        presenters.PRESENTER_POINT_CONSTRAINT,
        point_constraint.draw_node,
    ),
    ("AimConstraint", presenters.PRESENTER_AIM_CONSTRAINT, aim_constraint.draw_node),
)

_LEDGER = RegistrationLedger("animtools")
_LOG = get_logger(__name__)


def _remove_keymap_item(keymap, item):
    try:
        keymap.keymap_items.remove(item)
    except (ReferenceError, RuntimeError, ValueError):
        _LOG.debug("AnimGraph keymap item was already removed", exc_info=True)


def _register_properties() -> None:
    _LEDGER.add_property(
        bpy.types.Scene,
        "cp77_rig_assembly",
        PointerProperty(type=CP77_RigAssemblyState),
    )
    _LEDGER.add_property(
        bpy.types.Scene, "cp77_facial", PointerProperty(type=CP77_FacialProps)
    )
    _LEDGER.add_property(
        bpy.types.Scene, "rm_data", PointerProperty(type=RootMotionData)
    )
    _LEDGER.add_property(
        bpy.types.Scene,
        "cp77_additive_preview",
        PointerProperty(type=CP77_AdditivePreviewSettings),
    )
    _LEDGER.add_property(
        bpy.types.Action,
        "cp77_anim_events",
        CollectionProperty(type=CP77_AnimEventItem),
    )
    _LEDGER.add_property(
        bpy.types.Action,
        "cp77_anim_events_index",
        IntProperty(name="Active Event Index", default=0),
    )


def _register_animgraph_ui() -> None:
    for label, presenter, draw in NODE_DRAW_HOOKS:
        presenters.register_node_draw_hook(presenter, draw)
        _LEDGER.add_cleanup(
            f"{label} node draw hook",
            lambda presenter=presenter, draw=draw: presenters.unregister_node_draw_hook(
                presenter, draw
            ),
        )
    sm_overlay.register()
    _LEDGER.add_cleanup("AnimGraph transition overlay", sm_overlay.unregister)
    results_overlay.register(session_results)
    _LEDGER.add_cleanup("AnimGraph results overlay", results_overlay.unregister)
    bpy.types.NODE_MT_add.append(menu_func_add)
    bpy.types.NODE_HT_header.append(draw_header_path)
    _LEDGER.add_cleanup(
        "AnimGraph header path",
        lambda: bpy.types.NODE_HT_header.remove(draw_header_path),
    )
    _LEDGER.add_cleanup(
        "AnimGraph add menu", lambda: bpy.types.NODE_MT_add.remove(menu_func_add)
    )

    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is None:
        return
    keymap = keyconfig.keymaps.new(name="Node Editor", space_type="NODE_EDITOR")
    for operator, event, modifiers in (
        (REDENGINE_OT_enter_group.bl_idname, "TAB", {}),
        (REDENGINE_OT_exit_group.bl_idname, "TAB", {"ctrl": True}),
        (
            REDENGINE_OT_view_node_pose.bl_idname,
            "LEFTMOUSE",
            {"ctrl": True, "shift": True},
        ),
    ):
        item = keymap.keymap_items.new(operator, event, "PRESS", **modifiers)
        _LEDGER.add_cleanup(
            f"keymap {operator}",
            lambda keymap=keymap, item=item: _remove_keymap_item(keymap, item),
        )


def _register_playback_toggles() -> None:
    footers = (
        bpy.types.DOPESHEET_HT_playback_controls,
        bpy.types.GRAPH_HT_playback_controls,
        bpy.types.NLA_HT_playback_controls,
        bpy.types.SEQUENCER_HT_playback_controls,
    )
    for header, draw in (
        (bpy.types.DOPESHEET_HT_header, playback.draw_timeline_header),
        *((footer, playback.draw_playback_footer) for footer in footers),
    ):
        header.append(draw)
        _LEDGER.add_cleanup(
            f"{header.__name__} Mix and Face",
            lambda header=header, draw=draw: header.remove(draw),
        )


def register_animtools() -> None:
    if _LEDGER.active:
        return
    try:
        _LEDGER.register_classes(CLASSES)
        _register_properties()
        _register_animgraph_ui()
        _register_playback_toggles()
        for name, callback in callbacks.HANDLERS:
            _LEDGER.add_handler(getattr(bpy.app.handlers, name), callback)
        _LEDGER.add_cleanup("Animation Tools runtime", callbacks.shutdown)
    except Exception:
        _LEDGER.cleanup()
        raise


def unregister_animtools() -> None:
    _LEDGER.cleanup_or_raise()
