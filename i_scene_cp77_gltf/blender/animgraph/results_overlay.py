from __future__ import annotations

from dataclasses import dataclass

import bpy

from ...animation.model.animgraph.handles import normalized_source_handle
from ...core.log import get_logger, log_once
from . import sm_overlay
from .rig_binding import binding_tree
from .tree import REDengine_AnimGraphTree

POSE_SOCKET_ID = "REDengine_AnimGraphSocket_Pose"
OUTPUT_RED_TYPE = "animAnimNode_Output"

# Colours and sizes at UI scale 1.
DIM = (0.0, 0.0, 0.0, 0.45)
LIT = (0.35, 0.85, 0.45, 1.0)
SOURCE = (0.95, 0.65, 0.20, 1.0)
WEIGHT = (0.85, 0.85, 0.85, 0.90)
TRACK = (1.0, 1.0, 1.0, 0.15)
OUTLINE_WIDTH = 1.5
STATE_WIDTH = 3.0
BAR_HEIGHT = 3.0
INSET = 6.0

_HANDLE = None
_RESULTS_FOR = None
_LOG = get_logger(__name__)


@dataclass(frozen=True)
class NodeDecoration:
    node_name: str
    # "ran", "idle", "running_state", "transition_source" or "transition_target".
    kind: str
    # A transition's progress, 0-1, shown on its source and target states.
    progress: float = 0.0
    # How much each drawn pose input contributes, in socket order; empty for a node that does not blend.
    weights: tuple[float, ...] = ()


def input_key(socket) -> str:
    """The input a socket stands for, as the solve results name it"""
    name = str(getattr(socket, "red_field_name", "") or "")
    index = int(getattr(socket, "red_array_index", -1))
    return f"{name}[{index}]" if index >= 0 else name


def pose_inputs(node) -> list:
    """The node's drawn pose input sockets, in order"""
    return [
        socket
        for socket in sm_overlay.drawn_sockets(node.inputs)
        if socket.bl_idname == POSE_SOCKET_ID
    ]


def _state_marks(container, results) -> dict:
    """State index -> (kind, progress) for the state machine container, when it ran in the step"""
    handle = normalized_source_handle(container.red_handle_id)
    if handle not in results.ran:
        return {}
    transition = results.transitions.get(handle)
    if transition is not None:
        source, target, progress = transition
        return {
            source: ("transition_source", progress),
            target: ("transition_target", progress),
        }
    state = results.states.get(handle)
    return {} if state is None else {state: ("running_state", 0.0)}


def decorations(tree, results) -> tuple[NodeDecoration, ...]:
    """What each node of the level tree shows for results"""
    container = sm_overlay.state_machine_of(tree)
    positions, marks = {}, {}
    if container is not None:
        positions = {
            str(ref.handle): index for index, ref in enumerate(container.red_sm_states)
        }
        marks = _state_marks(container, results)
    shown = []
    for node in tree.nodes:
        raw = str(getattr(node, "red_handle_id", "") or "")
        if not raw or getattr(node, "red_pseudo", False):
            continue
        if raw in positions:
            kind, progress = marks.get(positions[raw], ("idle", 0.0))
            shown.append(NodeDecoration(node.name, kind, float(progress)))
            continue
        handle = normalized_source_handle(raw)
        # The output is the graph's final pose: it ran whenever anything did.
        if handle not in results.ran and not (
            results.ran and getattr(node, "red_type", "") == OUTPUT_RED_TYPE
        ):
            shown.append(NodeDecoration(node.name, "idle"))
            continue
        shares = results.blend_weights.get(handle)
        weights = (
            tuple(
                float(shares.get(input_key(socket), 0.0))
                for socket in pose_inputs(node)
            )
            if shares
            else ()
        )
        shown.append(NodeDecoration(node.name, "ran", 0.0, weights))
    return tuple(shown)


def _rect(node, scale: float):
    """(left, bottom, right, top) of a displayed node in view space, else None"""
    try:
        height = float(node.dimensions.y)
        if height <= 0.0:
            return None
        location = node.location_absolute
        left, top = location.x * scale, location.y * scale
        width = float(node.dimensions.x) or float(node.width) * scale
        return left, top - height, left + width, top
    except (
        AttributeError,
        ReferenceError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_rect", type(error).__name__),
            "rect: fell back after %s",
            error,
            exc_info=True,
        )
        return None


def _bar(fills, left, bottom, length, share, colour, scale) -> None:
    """A track of length with share of it filled in colour"""
    top = bottom + BAR_HEIGHT * scale
    fills.append(((left, bottom, left + length, top), TRACK))
    fills.append(
        ((left, bottom, left + length * max(0.0, min(1.0, share)), top), colour)
    )


def _shapes(tree, shown) -> tuple[list, list]:
    """Filled rectangles (rect, rgba) and outlines (rect, rgba, width) for the decorations shown"""
    fills, outlines = [], []
    nodes = tree.nodes
    for item in shown:
        node = nodes.get(item.node_name)
        scale = sm_overlay.ui_scale(node) if node is not None else 1.0
        rect = _rect(node, scale) if node is not None else None
        if rect is None:
            continue
        if item.kind == "idle":
            fills.append((rect, DIM))
            continue
        colour = SOURCE if item.kind == "transition_source" else LIT
        outlines.append(
            (rect, colour, OUTLINE_WIDTH if item.kind == "ran" else STATE_WIDTH)
        )
        left, bottom, right, _top = rect
        inset = INSET * scale
        length = max(0.0, right - left - 2.0 * inset)
        if item.kind in ("transition_source", "transition_target"):
            share = (
                1.0 - item.progress
                if item.kind == "transition_source"
                else item.progress
            )
            _bar(
                fills, left + inset, bottom + 2.0 * scale, length, share, colour, scale
            )
        if item.weights and not node.hide:
            # Inputs stack at the bottom of a node; each weight underlines its socket's row.
            inputs = sm_overlay.drawn_sockets(node.inputs)
            weights = iter(item.weights)
            for position, socket in enumerate(inputs):
                if socket.bl_idname != POSE_SOCKET_ID:
                    continue
                rows = (
                    sm_overlay.FOOTER_DY
                    + (len(inputs) - position - 1.0) * sm_overlay.ROW_DY
                    + 1.0
                )
                _bar(
                    fills,
                    left + inset,
                    bottom + rows * scale,
                    length,
                    next(weights, 0.0),
                    WEIGHT,
                    scale,
                )
    return fills, outlines


def _draw(fills, outlines, viewport) -> None:
    import gpu
    from gpu_extras.batch import batch_for_shader

    previous_blend = gpu.state.blend_get()
    gpu.state.blend_set("ALPHA")
    try:
        if fills:
            positions, colours = [], []
            for (x0, y0, x1, y1), colour in fills:
                positions.extend(
                    (
                        (x0, y0, 0.0),
                        (x1, y0, 0.0),
                        (x1, y1, 0.0),
                        (x0, y0, 0.0),
                        (x1, y1, 0.0),
                        (x0, y1, 0.0),
                    )
                )
                colours.extend((colour,) * 6)
            shader = gpu.shader.from_builtin("SMOOTH_COLOR")
            batch_for_shader(shader, "TRIS", {"pos": positions, "color": colours}).draw(
                shader
            )
        if outlines:
            shader = gpu.shader.from_builtin("POLYLINE_SMOOTH_COLOR")
            shader.bind()
            shader.uniform_float("viewportSize", viewport)
            by_width = {}
            for (x0, y0, x1, y1), colour, width in outlines:
                corners = ((x0, y0, 0.0), (x1, y0, 0.0), (x1, y1, 0.0), (x0, y1, 0.0))
                positions, colours = by_width.setdefault(width, ([], []))
                for start, end in zip(corners, corners[1:] + corners[:1]):
                    positions.extend((start, end))
                    colours.extend((colour, colour))
            for width, (positions, colours) in by_width.items():
                shader.uniform_float("lineWidth", width)
                batch_for_shader(
                    shader, "LINES", {"pos": positions, "color": colours}
                ).draw(shader)
    finally:
        gpu.state.blend_set(previous_blend)


def draw_callback() -> None:
    """Draw the results on the level the node editor shows while a preview plays it"""
    try:
        space = getattr(bpy.context, "space_data", None)
        if (
            _RESULTS_FOR is None
            or space is None
            or getattr(space, "type", "") != "NODE_EDITOR"
        ):
            return
        tree = getattr(space, "edit_tree", None)
        if (
            tree is None
            or getattr(tree, "bl_idname", "") != REDengine_AnimGraphTree.bl_idname
        ):
            return
        results = _RESULTS_FOR(binding_tree(tree))
        if results is None:
            return
        fills, outlines = _shapes(tree, decorations(tree, results))
        if not fills and not outlines:
            return
        import gpu

        viewport = gpu.state.viewport_get()
        _draw(fills, outlines, (float(viewport[2]), float(viewport[3])))
    except Exception:
        log_once(
            _LOG,
            "ERROR",
            "draw",
            "AnimGraph results overlay failed; further errors are not logged",
            exc_info=True,
        )


def redraw_editors(window_manager, root_name: str) -> None:
    """Tag every node editor showing a level of the graph root_name for redraw"""
    for window in window_manager.windows:
        screen = window.screen
        for area in screen.areas if screen is not None else ():
            if area.type != "NODE_EDITOR":
                continue
            tree = getattr(area.spaces.active, "edit_tree", None)
            if getattr(tree, "bl_idname", "") != REDengine_AnimGraphTree.bl_idname:
                continue
            if binding_tree(tree).name == root_name:
                area.tag_redraw()


def register(results_for) -> None:
    """Draw the results results_for(root tree) returns"""
    global _HANDLE, _RESULTS_FOR
    _RESULTS_FOR = results_for
    if _HANDLE is not None or bpy.app.background:
        return
    _HANDLE = bpy.types.SpaceNodeEditor.draw_handler_add(
        draw_callback, (), "WINDOW", "POST_VIEW"
    )


def unregister() -> None:
    global _HANDLE, _RESULTS_FOR
    _RESULTS_FOR = None
    handle, _HANDLE = _HANDLE, None
    if handle is None:
        return
    try:
        bpy.types.SpaceNodeEditor.draw_handler_remove(handle, "WINDOW")
    except (RuntimeError, ValueError):
        pass
