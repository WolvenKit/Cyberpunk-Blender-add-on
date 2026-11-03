import bpy
from bpy.props import CollectionProperty, IntProperty

from ..blender.animgraph import presenters
from ..blender.animgraph.node_types import (
    REDengine_AnimGraphContainer,
    REDengine_AnimGraphNode_Generic,
)
from ..blender.animgraph.properties import (
    REDengine_AnimArrayElement,
    REDengine_AnimArrayField,
    REDengine_AnimCurvePoint,
    REDengine_AnimFeature,
    REDengine_AnimNodeProperty,
    REDengine_AnimVariable,
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
from .ui.animgraph.validation import REDENGINE_PT_graph_validator
from .ui.event_lists import (
    CP77_UL_AnimEventList,
    CP77_UL_ParamList,
    CP77_UL_SwitchList,
    CP77_UL_WorkspotActionList,
)
from .ui.events import CP77_PT_AnimEventsPanel
from .ui.panel import CP77_PT_AnimsPanel


ANIMGRAPH_CLASSES = (
    REDengine_AnimCurvePoint,
    REDengine_AnimArrayField,
    REDengine_AnimArrayElement,
    REDengine_AnimNodeProperty,
    REDengine_AnimVariable,
    REDengine_AnimFeature,
    REDengine_AnimGraphSocket_Pose,
    REDengine_AnimGraphSocket_Float,
    REDengine_AnimGraphSocket_Vector,
    REDengine_AnimGraphSocket_Int,
    REDengine_AnimGraphSocket_Bool,
    REDengine_AnimGraphSocket_Quaternion,
    REDengine_AnimGraphSocket_Transform,
    REDengine_AnimGraphSocket_Transition,
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
    CP77_UL_AnimEventList,
    CP77_UL_SwitchList,
    CP77_UL_ParamList,
    CP77_UL_WorkspotActionList,
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


def _remove_keymap_item(keymap, item):
    try:
        keymap.keymap_items.remove(item)
    except (ReferenceError, RuntimeError, ValueError):
        pass


def _register_animgraph_ui() -> None:
    presenters.register_node_draw_hook(presenters.NODE_DRAW_FALLBACK, draw_animgraph_node)
    _LEDGER.add_cleanup(
        "AnimGraph node draw hook",
        lambda: presenters.unregister_node_draw_hook(presenters.NODE_DRAW_FALLBACK, draw_animgraph_node),
    )
    bpy.types.NODE_MT_add.append(menu_func_add)
    _LEDGER.add_cleanup("AnimGraph add menu", lambda: bpy.types.NODE_MT_add.remove(menu_func_add))

    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is None:
        return
    keymap = keyconfig.keymaps.new(name="Node Editor", space_type="NODE_EDITOR")
    for operator, event, modifiers in (
        (REDENGINE_OT_enter_group.bl_idname, "TAB", {}),
        (REDENGINE_OT_exit_group.bl_idname, "TAB", {"ctrl": True}),
    ):
        item = keymap.keymap_items.new(operator, event, "PRESS", **modifiers)
        _LEDGER.add_cleanup(
            f"keymap {operator}",
            lambda keymap=keymap, item=item: _remove_keymap_item(keymap, item),
        )


def register_animtools() -> None:
    if _LEDGER.active:
        return
    try:
        _LEDGER.register_classes(CLASSES)
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
    except Exception:
        _LEDGER.cleanup()
        raise


def unregister_animtools() -> None:
    overlay_service.stop()
    failures = _LEDGER.cleanup()
    if failures:
        raise RuntimeError("; ".join(f"{label}: {error}" for label, error in failures))
