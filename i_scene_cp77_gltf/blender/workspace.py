import os

import bpy

from ..assetio.resources import get_workspace_dir
from ..core.log import get_logger, log_once

_LOG = get_logger(__name__)

ANIMATION_WORKSPACE_NAME = "Cyberpunk Animation"
ANIMATION_WORKSPACE_FLAG = "cp77_animation_workspace"
TEMPLATE_PATH = os.path.join(get_workspace_dir(), "cyberpunk_animation.blend")


def _flagged(workspace) -> bool:
    try:
        return bool(
            workspace.get(ANIMATION_WORKSPACE_FLAG, False)
            or workspace.owner_ids.get(ANIMATION_WORKSPACE_FLAG) is not None
        )
    except (AttributeError, ReferenceError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_flagged", type(error).__name__),
            "flagged: fell back after %s",
            error,
            exc_info=True,
        )
        return False


def mark_animation_workspace(workspace) -> None:
    """Flag workspace as the animation workspace"""
    workspace[ANIMATION_WORKSPACE_FLAG] = True
    if workspace.owner_ids.get(ANIMATION_WORKSPACE_FLAG) is None:
        workspace.owner_ids.new(ANIMATION_WORKSPACE_FLAG)


def is_animation_workspace(context) -> bool:
    return _flagged(getattr(context, "workspace", None))


def animation_workspace():
    return next(
        (workspace for workspace in bpy.data.workspaces if _flagged(workspace)), None
    )


def ensure_animation_workspace():
    """The file's animation workspace, appended from the template when the file has none"""
    workspace = animation_workspace()
    if workspace is not None:
        return workspace
    with bpy.data.libraries.load(TEMPLATE_PATH, link=False) as (source, target):
        if ANIMATION_WORKSPACE_NAME not in source.workspaces:
            raise RuntimeError(
                f"{TEMPLATE_PATH} holds no {ANIMATION_WORKSPACE_NAME} workspace"
            )
        target.workspaces = [ANIMATION_WORKSPACE_NAME]
    workspace = target.workspaces[0]
    mark_animation_workspace(workspace)
    return workspace


def workspace_space(workspace, space_type: str):
    """The active space of the workspace's first area of space_type, else None"""
    for screen in workspace.screens:
        for area in screen.areas:
            if area.type == space_type:
                return area.spaces.active
    return None


def open_animation_workspace(context):
    workspace = ensure_animation_workspace()
    window = getattr(context, "window", None)
    if window is not None:
        window.workspace = workspace
    return workspace


def show_graph(context, tree) -> None:
    """Open the Animation workspace with tree in its graph editor"""
    space = workspace_space(open_animation_workspace(context), "NODE_EDITOR")
    if space is not None:
        space.node_tree = tree
