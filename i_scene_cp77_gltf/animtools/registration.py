import bpy
<<<<<<< Updated upstream
from bpy.props import CollectionProperty, IntProperty

from ..blender.animgraph import presenters
=======
from bpy.props import CollectionProperty, IntProperty, PointerProperty

from ..blender.animgraph import presenters, results_overlay, sm_overlay
>>>>>>> Stashed changes
from ..blender.animgraph.node_types import (
    REDengine_AnimGraphContainer,
    REDengine_AnimGraphNode_Generic,
)
<<<<<<< Updated upstream
=======
from ..blender.animgraph.preview_settings import PREVIEW_SETTINGS_CLASSES
>>>>>>> Stashed changes
from ..blender.animgraph.properties import (
    REDengine_AnimArrayElement,
    REDengine_AnimArrayField,
    REDengine_AnimCurvePoint,
    REDengine_AnimFeature,
    REDengine_AnimNodeProperty,
    REDengine_AnimVariable,
<<<<<<< Updated upstream
=======
    REDengine_PointConstraintWeightedTransform,
    REDengine_SimpleBounceChannelEntry,
    REDengine_SimpleBounceTrackOutput,
    REDengine_SimpleBounceTransformOutput,
)
from ..blender.animgraph.sm_properties import (
    REDengine_SMCondition,
    REDengine_SMStateRef,
    REDengine_SMTransition,
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
    REDengine_AnimGraphSocket_Vector,
)
from ..blender.animgraph.tree import REDengine_AnimGraphTree
from ..registration import RegistrationLedger
from .properties import (
    CP77_AnimEventItem,
    CP77_AnimEventParamItem,
    CP77_AnimEventSwitchItem,
    CP77_WorkspotActionItem,
)
from .operators import actions, events, facial_bake, facial_preview, facial_runtime, facial_setup
from .operators import jali, overlay, rig, rigify, root_motion
from .operators.animgraph.add_node import add_classes, menu_func_add
from .operators.animgraph.curve import curve_editor_classes
from .operators.animgraph.navigation import REDENGINE_OT_enter_group, REDENGINE_OT_exit_group
from .operators.animgraph.validation import REDENGINE_OT_validate_graph
from .services import overlay as overlay_service
from .services.facial import runtime as facial_runtime_service
from .services.facial import session as facial_session
from .services.rigify import sync as rigify_sync
from .ui.action_list import CP77_UL_AnimList
from .ui.animgraph.dangle import REDENGINE_PT_dangle_bridge
from .ui.animgraph.inputs import REDENGINE_PT_inputs
from .ui.animgraph.navigation import REDENGINE_PT_subgraph_nav
from .ui.animgraph.property_draw import draw_node as draw_animgraph_node
=======
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
>>>>>>> Stashed changes
from .ui.animgraph.validation import REDENGINE_PT_graph_validator
from .ui.event_lists import (
    CP77_UL_AnimEventList,
    CP77_UL_ParamList,
    CP77_UL_SwitchList,
    CP77_UL_WorkspotActionList,
)
from .ui.events import CP77_PT_AnimEventsPanel
from .ui.panel import CP77_PT_AnimsPanel
<<<<<<< Updated upstream


ANIMGRAPH_CLASSES = (
=======
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
>>>>>>> Stashed changes
    REDengine_AnimCurvePoint,
    REDengine_AnimArrayField,
    REDengine_AnimArrayElement,
    REDengine_AnimNodeProperty,
    REDengine_AnimVariable,
    REDengine_AnimFeature,
<<<<<<< Updated upstream
=======
    REDengine_SimpleBounceChannelEntry,
    REDengine_SimpleBounceTransformOutput,
    REDengine_SimpleBounceTrackOutput,
    REDengine_PointConstraintWeightedTransform,
    REDengine_SMCondition,
    REDengine_SMTransition,
    REDengine_SMStateRef,
>>>>>>> Stashed changes
    REDengine_AnimGraphSocket_Pose,
    REDengine_AnimGraphSocket_Float,
    REDengine_AnimGraphSocket_Vector,
    REDengine_AnimGraphSocket_Int,
    REDengine_AnimGraphSocket_Bool,
    REDengine_AnimGraphSocket_Quaternion,
    REDengine_AnimGraphSocket_Transform,
    REDengine_AnimGraphSocket_Transition,
<<<<<<< Updated upstream
    REDengine_AnimGraphSocket_Editor,
    REDengine_AnimGraphTree,
    REDengine_AnimGraphNode_Generic,
    REDengine_AnimGraphContainer,
    REDENGINE_OT_enter_group,
    REDENGINE_OT_exit_group,
    REDENGINE_PT_inputs,
    REDENGINE_PT_subgraph_nav,
    REDENGINE_PT_graph_validator,
    REDENGINE_PT_dangle_bridge,
    REDENGINE_OT_validate_graph,
    *curve_editor_classes,
    *add_classes,
)

CLASSES = (
    CP77_AnimEventSwitchItem,
    CP77_AnimEventParamItem,
    CP77_WorkspotActionItem,
    CP77_AnimEventItem,
    CP77_UL_AnimList,
=======
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
>>>>>>> Stashed changes
    CP77_UL_AnimEventList,
    CP77_UL_SwitchList,
    CP77_UL_ParamList,
    CP77_UL_WorkspotActionList,
<<<<<<< Updated upstream
    actions.CP77_OT_ToggleSIMD,
    overlay.BHLS_OT_Start,
    overlay.BHLS_OT_Stop,
    actions.CP77AnimsDelete,
    rig.LoadAPose,
    rig.LoadTPose,
    actions.CP77Animset,
    rig.CP77BoneHider,
    rig.CP77BoneUnhider,
    actions.CP77Keyframe,
    actions.CP77ResetArmature,
    actions.CP77NewAction,
    rig.CP77RigLoader,
    actions.CP77AnimNamer,
    facial_setup.CP77_OT_LoadFacial,
    facial_preview.CP77_OT_ApplyMainPose,
    facial_preview.CP77_OT_BrowsePose,
    facial_preview.CP77_OT_ClearPosePreview,
    facial_setup.CP77_OT_UnbindFacial,
    facial_setup.CP77_OT_RebuildFacialSession,
    facial_setup.CP77_OT_ResetNeutral,
    facial_setup.CP77_OT_ResetTracksToDefaults,
    facial_bake.CP77_OT_BakeFacialAnimation,
    facial_bake.CP77_OT_ClearFacialAnimation,
    facial_runtime.FACIAL_OT_ToggleSolver,
    facial_runtime.FACIAL_OT_SolveNow,
    jali.CP77_OT_PreviewFacialPose,
    jali.CP77_OT_GenerateJALILipSync,
    jali.JALI_OT_InstallDependencies,
    rigify.CP77ToRigify,
    rigify.CP77_OT_ToggleConstraintDirection,
    rigify.CP77_OT_ActivateLinkedRig,
    rigify.CP77_OT_BakeRigifyToSource,
    root_motion.CP77HipMotionToRoot,
    root_motion.CP77RootToHipMotion,
    root_motion.CP77RemoveRootMotion,
    events.CP77_OT_AnimEventAdd,
    events.CP77_OT_AnimEventRemove,
    events.CP77_OT_AnimEventGoto,
    events.CP77_OT_AnimEventMove,
    events.CP77_OT_AnimEventSyncMarkers,
    events.CP77_OT_AnimEventFromMarkers,
    events.CP77_OT_AnimEventAddSwitch,
    events.CP77_OT_AnimEventRemoveSwitch,
    events.CP77_OT_AnimEventAddParam,
    events.CP77_OT_AnimEventRemoveParam,
    events.CP77_OT_AnimEventAddWorkspotAction,
    events.CP77_OT_AnimEventRemoveWorkspotAction,
    CP77_PT_AnimsPanel,
    CP77_PT_AnimEventsPanel,
    *ANIMGRAPH_CLASSES,
)

_LEDGER = RegistrationLedger("animtools")
=======
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
>>>>>>> Stashed changes


def _remove_keymap_item(keymap, item):
    try:
        keymap.keymap_items.remove(item)
    except (ReferenceError, RuntimeError, ValueError):
<<<<<<< Updated upstream
        pass


def _register_animgraph_ui() -> None:
    presenters.register_node_draw_hook(presenters.NODE_DRAW_FALLBACK, draw_animgraph_node)
    _LEDGER.add_cleanup(
        "AnimGraph node draw hook",
        lambda: presenters.unregister_node_draw_hook(presenters.NODE_DRAW_FALLBACK, draw_animgraph_node),
    )
    bpy.types.NODE_MT_add.append(menu_func_add)
    _LEDGER.add_cleanup("AnimGraph add menu", lambda: bpy.types.NODE_MT_add.remove(menu_func_add))
=======
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
>>>>>>> Stashed changes

    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is None:
        return
    keymap = keyconfig.keymaps.new(name="Node Editor", space_type="NODE_EDITOR")
    for operator, event, modifiers in (
        (REDENGINE_OT_enter_group.bl_idname, "TAB", {}),
        (REDENGINE_OT_exit_group.bl_idname, "TAB", {"ctrl": True}),
<<<<<<< Updated upstream
=======
        (
            REDENGINE_OT_view_node_pose.bl_idname,
            "LEFTMOUSE",
            {"ctrl": True, "shift": True},
        ),
>>>>>>> Stashed changes
    ):
        item = keymap.keymap_items.new(operator, event, "PRESS", **modifiers)
        _LEDGER.add_cleanup(
            f"keymap {operator}",
            lambda keymap=keymap, item=item: _remove_keymap_item(keymap, item),
        )


<<<<<<< Updated upstream
=======
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


>>>>>>> Stashed changes
def register_animtools() -> None:
    if _LEDGER.active:
        return
    try:
        _LEDGER.register_classes(CLASSES)
<<<<<<< Updated upstream
        _register_animgraph_ui()
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
        facial_session.register()
        _LEDGER.add_cleanup("facial session", facial_session.unregister)
        facial_runtime_service.register_handlers()
        _LEDGER.add_cleanup("facial handlers", facial_runtime_service.unregister_handlers)
        rigify_sync.register()
        _LEDGER.add_cleanup("rigify sync", rigify_sync.unregister)
=======
        _register_properties()
        _register_animgraph_ui()
        _register_playback_toggles()
        for name, callback in callbacks.HANDLERS:
            _LEDGER.add_handler(getattr(bpy.app.handlers, name), callback)
        _LEDGER.add_cleanup("Animation Tools runtime", callbacks.shutdown)
>>>>>>> Stashed changes
    except Exception:
        _LEDGER.cleanup()
        raise


def unregister_animtools() -> None:
<<<<<<< Updated upstream
    overlay_service.stop()
    failures = _LEDGER.cleanup()
    if failures:
        raise RuntimeError("; ".join(f"{label}: {error}" for label, error in failures))
=======
    _LEDGER.cleanup_or_raise()
>>>>>>> Stashed changes
