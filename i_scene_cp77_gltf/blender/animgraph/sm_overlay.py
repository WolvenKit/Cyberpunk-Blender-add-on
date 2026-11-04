from __future__ import annotations

import bpy

from ...core.log import debug_exception, get_logger, log_once
from . import sm_records, sm_sockets
from .sm_sockets import IN_NAME, IN_SOCKET_ID, ROW_SOCKET_ID
from .tree import REDengine_AnimGraphTree

PALETTE = (
    (0.90, 0.62, 0.00),
    (0.34, 0.71, 0.91),
    (0.00, 0.62, 0.45),
    (0.94, 0.89, 0.26),
    (0.35, 0.50, 0.95),
    (0.84, 0.37, 0.00),
    (0.80, 0.47, 0.65),
    (0.75, 0.75, 0.75),
)

# Layout at UI scale 1 (Blender's NODE_DY is the row pitch). Calibrated against a
# real screen in Task 13; keep them as the only tuning knobs.
HEADER_DY = 20.0
ROW_DY = 22.0
FOOTER_DY = 5.0  # gap under the last input of a displayed node (NODE_DY / 4)

BEZIER_SEGMENTS = 24
HANDLE_FACTOR = 0.45
HANDLE_MIN = 60.0

DISABLED_ALPHA = 0.35
WIDTH_NORMAL = 1.5
WIDTH_ACTIVE = 3.0

_MIN_SCALE, _MAX_SCALE = 0.2, 8.0

_HANDLE = None
_LOG = get_logger(__name__)

# Container resolution cache: tree name -> (parent tree name, container node name). Names
# are re-resolved (O(1) lookups) and validated on every use, never held as references.
_CONTAINER_CACHE: dict = {}
# Trees known not to be state machine subtrees: (tree name, tree pointer) -> graph generation the
# answer was computed at. The answer holds until ``sm_records.graph_generation()`` changes (node /
# link edits, file load, undo / redo); it never expires with time, so an idle editor costs nothing.
_NOT_SM: dict = {}
_NOT_SM_GENERATION = -1

Point = tuple
Segment = tuple  # (start, end, (r, g, b, a), width)


def drawn_sockets(sockets) -> list:
    """The sockets Blender lays out, in order"""
    return [
        s
        for s in sockets
        if getattr(s, "enabled", True) and not getattr(s, "hide", False)
    ]


def _preference_scale() -> float:
    """Blender's UI_SCALE_FAC without a displayed node to measure"""
    try:
        prefs = bpy.context.preferences
        for scale in (prefs.system.ui_scale, prefs.view.ui_scale):
            scale = float(scale)
            if _MIN_SCALE <= scale <= _MAX_SCALE:
                return scale
    except (AttributeError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_preference_scale", type(error).__name__),
            "preference scale: fell back after %s",
            error,
            exc_info=True,
        )
    return 1.0


def _measured_scale(node) -> float | None:
    """dimensions.x / width of a displayed, expanded node, else None"""
    try:
        if node.hide:
            return None
        width = float(node.width)
        shown = float(node.dimensions.x)
        if width > 0.0 and shown > 0.0:
            ratio = shown / width
            if _MIN_SCALE <= ratio <= _MAX_SCALE:
                return ratio
    except (
        AttributeError,
        KeyError,
        ReferenceError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_measured_scale", type(error).__name__),
            "measured scale: fell back after %s",
            error,
            exc_info=True,
        )
    return None


def ui_scale(node) -> float:
    """View-space units per node unit for node (see the module docstring)"""
    measured = _measured_scale(node)
    return measured if measured is not None else _preference_scale()


def _scale_for(node, scale: float | None) -> float:
    return ui_scale(node) if scale is None else float(scale)


def _top_left(node, scale: float) -> tuple:
    loc = node.location_absolute
    return loc.x * scale, loc.y * scale


def _collapsed_edges(node, scale: float) -> tuple:
    """(left x, right x, middle y) of a collapsed node"""
    left, top = _top_left(node, scale)
    height = float(node.dimensions.y)
    if height <= 0.0:
        height = HEADER_DY * scale
    shown = float(node.dimensions.x)
    right = left + (shown if shown > 0.0 else float(node.width) * scale)
    return left, right, top - height * 0.5


def socket_anchor(node, output_index: int, scale: float | None = None) -> tuple:
    """View-space point where a wire leaves output output_index of node"""
    s = _scale_for(node, scale)
    if node.hide:
        _left, right, mid = _collapsed_edges(node, s)
        return right, mid
    left, top = _top_left(node, s)
    return left + float(node.width) * s, top - (
        HEADER_DY + (output_index + 0.5) * ROW_DY
    ) * s


def input_anchor(node, scale: float | None = None) -> tuple:
    """View-space point where a wire arrives at the In socket of node"""
    s = _scale_for(node, scale)
    if node.hide:
        left, _right, mid = _collapsed_edges(node, s)
        return left, mid
    left, top = _top_left(node, s)
    inputs = drawn_sockets(node.inputs)
    position = next(
        (
            i
            for i, sock in enumerate(inputs)
            if sock.name == IN_NAME and sock.bl_idname == IN_SOCKET_ID
        ),
        0,
    )
    height = float(node.dimensions.y)
    if height > 0.0:
        bottom = top - height
        return left, bottom + (FOOTER_DY + (len(inputs) - position - 0.5) * ROW_DY) * s
    outputs = len(drawn_sockets(node.outputs))
    return left, top - (HEADER_DY + (outputs + position + 0.5) * ROW_DY) * s


def handle_length(dx: float, scale: float = 1.0) -> float:
    return max(HANDLE_FACTOR * abs(dx), HANDLE_MIN * scale)


def bezier_points(
    start, end, scale: float = 1.0, segments: int = BEZIER_SEGMENTS
) -> list:
    """segments + 1 points of the cubic bezier from start to end"""
    (x0, y0), (x3, y3) = start, end
    h = handle_length(x3 - x0, scale)
    x1, y1 = x0 + h, y0
    x2, y2 = x3 - h, y3
    points = []
    for i in range(segments + 1):
        t = i / segments
        u = 1.0 - t
        a, b, c, d = u * u * u, 3.0 * u * u * t, 3.0 * u * t * t, t * t * t
        points.append(
            (a * x0 + b * x1 + c * x2 + d * x3, a * y0 + b * y1 + c * y2 + d * y3)
        )
    points[0], points[-1] = (x0, y0), (x3, y3)
    return points


def _row_anchor_index(owner, record_index: int) -> int | None:
    """Index of owner's row socket for record record_index among its drawn outputs"""
    for position, sock in enumerate(drawn_sockets(owner.outputs)):
        if (
            sock.bl_idname == ROW_SOCKET_ID
            and int(getattr(sock, "red_row_index", -1)) == record_index
        ):
            return position
    return None


def _owner_segments(owner, state_index: dict, active, scale: float = 1.0) -> list:
    segments = []
    handle = str(getattr(owner, "red_handle_id", "") or "")
    active_row = owner.red_transitions_index if owner == active else -1
    for index, rec in enumerate(owner.red_transitions):
        target_handle = str(rec.target_handle or "")
        if not target_handle or target_handle not in state_index:
            continue
        target, position = state_index[target_handle]
        if target == owner or (handle and target_handle == handle):
            continue
        anchor_index = _row_anchor_index(owner, index)
        if anchor_index is None:
            continue
        start = socket_anchor(owner, anchor_index, scale)
        end = input_anchor(target, scale)
        colour = PALETTE[position % len(PALETTE)]
        alpha = 1.0 if rec.enabled else DISABLED_ALPHA
        width = WIDTH_ACTIVE if index == active_row else WIDTH_NORMAL
        segments.append((start, end, (colour[0], colour[1], colour[2], alpha), width))
    return segments


def reset_caches() -> None:
    _CONTAINER_CACHE.clear()
    _NOT_SM.clear()
    sm_records.bump_graph_generation()


def invalidate_not_state_machine() -> None:
    """Forget every "not a state machine" answer"""
    sm_records.bump_graph_generation()


@bpy.app.handlers.persistent
def on_file_loaded(*_args) -> None:
    """Forget cached trees after a file loads"""
    try:
        reset_caches()
    except Exception:
        debug_exception(_LOG, "AnimGraph overlay cache reset details")


@bpy.app.handlers.persistent
def on_undo_redo(*_args) -> None:
    """Forget cached trees after undo or redo"""
    try:
        invalidate_not_state_machine()
    except Exception:
        debug_exception(_LOG, "AnimGraph overlay invalidation details")


def _cached_container(tree):
    key = _CONTAINER_CACHE.get(tree.name)
    if key is None:
        return None
    try:
        parent = bpy.data.node_groups.get(key[0])
        node = parent.nodes.get(key[1]) if parent is not None else None
        if node is not None and node.node_tree == tree:
            return node
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_cached_container", type(error).__name__),
            "cached container: fell back after %s",
            error,
            exc_info=True,
        )
    _CONTAINER_CACHE.pop(tree.name, None)
    return None


def _path_container(space, tree):
    """The node the editor entered to reach tree, found among its parent tree's nodes"""
    path = getattr(space, "path", None)
    if path is None or len(path) < 2:
        return None
    parent = path[len(path) - 2].node_tree
    if parent is None:
        return None
    active = parent.nodes.active
    if active is not None and getattr(active, "node_tree", None) == tree:
        return active
    for node in parent.nodes:
        if getattr(node, "node_tree", None) == tree:
            return node
    return None


def _container_for(tree, space=None):
    """The state machine container node of tree, or None"""
    global _NOT_SM_GENERATION
    node = _cached_container(tree)
    if node is not None:
        return node
    generation = sm_records.graph_generation()
    if generation != _NOT_SM_GENERATION:
        _NOT_SM.clear()
        _NOT_SM_GENERATION = generation
    key = (tree.name, tree.as_pointer())
    if key in _NOT_SM:
        return None
    node = _path_container(space, tree) if space is not None else None
    if node is None:
        node = sm_records.sm_container_for(tree)
    if node is None or not sm_sockets.is_state_machine(node):
        _NOT_SM[key] = generation
        return None
    _NOT_SM.pop(key, None)
    _CONTAINER_CACHE[tree.name] = (node.id_data.name, node.name)
    return node


def state_machine_of(tree, space=None):
    """The cached state machine container node of tree"""
    if tree is None:
        return None
    return _container_for(tree, space)


def _scan(tree, container) -> tuple:
    """(states, entry, any, measured scale) of tree in one pass"""
    by_handle = {}
    entry = any_state = None
    scale = None
    entry_type, any_type = sm_records.ENTRY_RED_TYPE, sm_records.ANY_RED_TYPE
    for node in tree.nodes:
        if getattr(node, "red_pseudo", False):
            red_type = getattr(node, "red_type", "")
            if red_type == entry_type and entry is None:
                entry = node
            elif red_type == any_type and any_state is None:
                any_state = node
        else:
            handle = getattr(node, "red_handle_id", "")
            if handle:
                by_handle.setdefault(handle, node)
        if scale is None:
            scale = _measured_scale(node)
    states = [
        by_handle[ref.handle]
        for ref in container.red_sm_states
        if ref.handle in by_handle
    ]
    return states, entry, any_state, scale


def _build(sm_tree, space=None) -> tuple:
    """(segments, tree scale) for sm_tree (see wire_segments)"""
    if sm_tree is None:
        return [], 1.0
    try:
        container = _container_for(sm_tree, space)
        if container is None:
            return [], 1.0
        states, entry, any_state, measured = _scan(sm_tree, container)
    except Exception:
        log_once(
            _LOG,
            "ERROR",
            "draw",
            "AnimGraph transition overlay failed in %s; further errors are not logged",
            "state machine lookup",
            exc_info=True,
        )
        return [], 1.0
    scale = measured if measured is not None else _preference_scale()
    if not states:
        return [], scale
    state_index = {}
    for position, node in enumerate(states):
        state_index.setdefault(str(node.red_handle_id), (node, position))
    try:
        active = sm_tree.nodes.active
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_build", type(error).__name__),
            "build: fell back after %s",
            error,
            exc_info=True,
        )
        active = None
    owners = list(states) + [node for node in (entry, any_state) if node is not None]
    segments = []
    for owner in owners:
        try:
            segments.extend(_owner_segments(owner, state_index, active, scale))
        except Exception:
            log_once(
                _LOG,
                "ERROR",
                "draw",
                "AnimGraph transition overlay failed in %s; further errors are not logged",
                "wire_segments",
                exc_info=True,
            )
            continue
    return segments, scale


def wire_segments(sm_tree, space=None) -> list:
    """One (start, end, rgba, width) per transition that has a distinct, known target"""
    return _build(sm_tree, space)[0]


def _current_tree():
    """The AnimGraph tree shown by the node editor being drawn, else None"""
    space = getattr(bpy.context, "space_data", None)
    if space is None or getattr(space, "type", "") != "NODE_EDITOR":
        return None
    tree = getattr(space, "edit_tree", None)
    if (
        tree is None
        or getattr(tree, "bl_idname", "") != REDengine_AnimGraphTree.bl_idname
    ):
        return None
    return tree


def _draw_batches(segments, viewport, scale: float) -> None:
    import gpu
    from gpu_extras.batch import batch_for_shader

    shader = gpu.shader.from_builtin("POLYLINE_SMOOTH_COLOR")
    shader.bind()
    shader.uniform_float("viewportSize", viewport)
    previous_blend = gpu.state.blend_get()
    gpu.state.blend_set("ALPHA")
    try:
        # One batch of independent line pairs per width for opaque wires. Translucent
        # wires are drawn as their own strip so overlapping joints do not darken them.
        opaque = {}
        translucent = []
        for segment in segments:
            points = [
                (x, y, 0.0) for x, y in bezier_points(segment[0], segment[1], scale)
            ]
            colour, width = segment[2], segment[3]
            if colour[3] >= 1.0:
                bucket = opaque.setdefault(width, ([], []))
                for a, b in zip(points, points[1:]):
                    bucket[0].extend((a, b))
                    bucket[1].extend((colour, colour))
            else:
                translucent.append((points, colour, width))
        for width, (positions, colours) in opaque.items():
            shader.uniform_float("lineWidth", width)
            batch_for_shader(
                shader, "LINES", {"pos": positions, "color": colours}
            ).draw(shader)
        for points, colour, width in translucent:
            shader.uniform_float("lineWidth", width)
            batch_for_shader(
                shader, "LINE_STRIP", {"pos": points, "color": [colour] * len(points)}
            ).draw(shader)
    finally:
        gpu.state.blend_set(previous_blend)


def draw_callback() -> None:
    """Draw the wires of the state machine in the active node editor"""
    try:
        tree = _current_tree()
        if tree is None:
            return
        segments, scale = _build(tree, getattr(bpy.context, "space_data", None))
        if not segments:
            return
        import gpu

        viewport = gpu.state.viewport_get()
        _draw_batches(segments, (float(viewport[2]), float(viewport[3])), scale)
    except Exception:
        log_once(
            _LOG,
            "ERROR",
            "draw",
            "AnimGraph transition overlay failed in %s; further errors are not logged",
            "draw_callback",
            exc_info=True,
        )


def register() -> None:
    global _HANDLE
    reset_caches()
    if _HANDLE is not None or bpy.app.background:
        return
    _HANDLE = bpy.types.SpaceNodeEditor.draw_handler_add(
        draw_callback, (), "WINDOW", "POST_VIEW"
    )


def unregister() -> None:
    global _HANDLE
    reset_caches()
    handle, _HANDLE = _HANDLE, None
    if handle is None:
        return
    try:
        bpy.types.SpaceNodeEditor.draw_handler_remove(handle, "WINDOW")
    except (RuntimeError, ValueError):
        pass
