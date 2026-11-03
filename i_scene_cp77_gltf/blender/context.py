from contextlib import contextmanager
from contextvars import ContextVar

import bpy

from ..core.log import debug_exception, get_logger
from .identity import rna_is_live
from .operator_results import require_finished

_LOG = get_logger(__name__)


_MODE_MAP = {
    "OBJECT": "OBJECT",
    "EDIT_ARMATURE": "EDIT",
    "POSE": "POSE",
    "EDIT_MESH": "EDIT",
    "EDIT_CURVE": "EDIT",
    "EDIT_CURVES": "EDIT",
    "EDIT_SURFACE": "EDIT",
    "EDIT_TEXT": "EDIT",
    "EDIT_METABALL": "EDIT",
    "EDIT_LATTICE": "EDIT",
    "EDIT_GREASE_PENCIL": "EDIT",
    "EDIT_POINT_CLOUD": "EDIT",
    "EDIT_GPENCIL": "EDIT",
    "SCULPT": "SCULPT",
    "SCULPT_CURVES": "SCULPT",
    "SCULPT_GPENCIL": "SCULPT",
    "SCULPT_GREASE_PENCIL": "SCULPT",
    "PAINT_WEIGHT": "WEIGHT_PAINT",
    "PAINT_VERTEX": "VERTEX_PAINT",
    "PAINT_TEXTURE": "TEXTURE_PAINT",
    "PAINT_GPENCIL": "PAINT_GPENCIL",
    "PAINT_GREASE_PENCIL": "PAINT_GREASE_PENCIL",
    "WEIGHT_GPENCIL": "WEIGHT_PAINT",
    "WEIGHT_GREASE_PENCIL": "WEIGHT_PAINT",
    "VERTEX_GPENCIL": "VERTEX_PAINT",
    "VERTEX_GREASE_PENCIL": "VERTEX_PAINT",
    "PARTICLE": "PARTICLE_EDIT",
}

_stored_contexts = ContextVar("cp77_blender_context_stack", default=())


class BlenderContextSnapshot:
    def __init__(self):
        self.mode = None
        self.active_object = None
        self.active_layer_collection = None
        self.selected_objects = []
        self.object_visibility = {}
        self.cursor_location = None
        self._stored = False

    def __enter__(self):
        self.store()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.restore()
        return False

    def store(self):
        context = bpy.context
        self.mode = context.mode
        self.active_object = context.view_layer.objects.active
        self.active_layer_collection = getattr(
            context.view_layer,
            "active_layer_collection",
            None,
        )
        self.selected_objects = list(context.selected_objects)

        for obj in self.selected_objects:
            if obj:
                self.object_visibility[obj.name] = {
                    "hide_viewport": obj.hide_viewport,
                    "hide_select": obj.hide_select,
                    "hide_get": obj.hide_get(),
                }

        if self.active_object and self.active_object.name not in self.object_visibility:
            self.object_visibility[self.active_object.name] = {
                "hide_viewport": self.active_object.hide_viewport,
                "hide_select": self.active_object.hide_select,
                "hide_get": self.active_object.hide_get(),
            }

        self.cursor_location = tuple(context.scene.cursor.location)
        self._stored = True
        return self

    def restore(self):
        if not self._stored:
            return
        context = bpy.context

        if _MODE_MAP.get(context.mode, context.mode) != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except Exception:
                debug_exception(
                    _LOG, "Could not return to Object Mode while restoring the context"
                )

        for obj_name, vis_state in self.object_visibility.items():
            if obj_name in bpy.data.objects:
                obj = bpy.data.objects[obj_name]
                try:
                    obj.hide_viewport = vis_state["hide_viewport"]
                    obj.hide_select = vis_state["hide_select"]
                    obj.hide_set(vis_state["hide_get"])
                except Exception:
                    debug_exception(
                        _LOG,
                        "Could not restore an object's visibility while restoring the context",
                    )

        try:
            bpy.ops.object.select_all(action="DESELECT")
        except Exception:
            debug_exception(
                _LOG, "Could not clear the selection while restoring the context"
            )
        # Objects removed since the context was stored (joined into another, say) are left out.
        for obj in self.selected_objects:
            if rna_is_live(obj):
                try:
                    obj.select_set(True)
                except RuntimeError:
                    pass

        if rna_is_live(self.active_object):
            try:
                context.view_layer.objects.active = self.active_object
            except (RuntimeError, ValueError):
                pass
        if self.active_layer_collection is not None:
            try:
                context.view_layer.active_layer_collection = (
                    self.active_layer_collection
                )
            except (ReferenceError, RuntimeError, TypeError):
                pass

        if self.cursor_location:
            context.scene.cursor.location = self.cursor_location

        if self.mode:
            target_mode = _MODE_MAP.get(self.mode, self.mode)
            current_mode = _MODE_MAP.get(context.mode, context.mode)
            if current_mode != target_mode:
                try:
                    bpy.ops.object.mode_set(mode=target_mode)
                except Exception:
                    debug_exception(
                        _LOG,
                        "Could not restore %s mode while restoring the context",
                        target_mode,
                    )
        self._stored = False


def store_current_context():
    snapshot = BlenderContextSnapshot().store()
    stack = _stored_contexts.get()
    _stored_contexts.set((*stack, snapshot))
    return snapshot


def restore_previous_context():
    try:
        stack = _stored_contexts.get()
        if stack:
            snapshot = stack[-1]
            _stored_contexts.set(stack[:-1])
            snapshot.restore()
        else:
            _LOG.warning("No saved context to restore")
    except Exception:
        _LOG.error("Failed to restore context", exc_info=True)


@contextmanager
def preserved_context():
    snapshot = BlenderContextSnapshot().store()
    try:
        yield snapshot
    finally:
        snapshot.restore()


def get_safe_mode():
    return _MODE_MAP.get(bpy.context.mode, "OBJECT")


def safe_mode_switch(target_mode: str):
    if not target_mode:
        return

    target_mode = _MODE_MAP.get(target_mode, target_mode)
    current_mode = get_safe_mode()
    if current_mode == target_mode:
        return

    if not bpy.context.active_object:
        if bpy.context.selected_objects:
            bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
        else:
            mesh = bpy.data.meshes.new("TempModeSwitch")
            temp = bpy.data.objects.new("TempModeSwitch", mesh)
            try:
                bpy.context.scene.collection.objects.link(temp)
                bpy.context.view_layer.objects.active = temp
                require_finished(
                    bpy.ops.object.mode_set(mode=target_mode),
                    f"The switch to {target_mode} mode",
                )
            finally:
                bpy.data.objects.remove(temp, do_unlink=True)
                bpy.data.meshes.remove(mesh)
            return

    try:
        result = bpy.ops.object.mode_set(mode=target_mode)
    except Exception as exc:
        raise RuntimeError(f"Failed to switch to mode {target_mode}: {exc}") from exc
    require_finished(result, f"The switch to {target_mode} mode")


def view3d_areas(context=None):
    """The 3D viewport areas of every open window"""
    window_manager = getattr(context or bpy.context, "window_manager", None)
    for window in getattr(window_manager, "windows", ()):
        screen = getattr(window, "screen", None)
        for area in getattr(screen, "areas", ()):
            if area.type == "VIEW_3D":
                yield area


def tag_view3d_redraw(context=None):
    """Request a redraw of every open 3D viewport"""
    for area in view3d_areas(context):
        area.tag_redraw()


def node_editor_tree(context, tree_type, *, edit=False):
    space = context.space_data
    if space is None or space.type != "NODE_EDITOR":
        return None
    tree = space.edit_tree if edit else space.node_tree
    if tree is not None and getattr(tree, "bl_idname", "") == tree_type:
        return tree
    return None
