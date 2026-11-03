from __future__ import annotations

import os
from contextlib import contextmanager

from ..assetio.documents import DocumentLoadError
from ..assetio.paths import strip_json_suffix
from ..assetio.values import coerce_float
from ..blender.ink import screens
from ..blender.ink.images import update_texture
from ..blender.ink.screens import _FONTS, PENDING_EDITS_KEY
from ..blender.operator_results import OperationResult
from ..blender.transactions import transactional
from ..ink.domain.animation import load_animation
from ..ink.domain.text import text_content, text_key
from ..ink.domain.writeback import WidgetEdit, edits_from_json, edits_to_json, merged
from ..ink.services.export import edited_document, export_library
from ..ink.services.library import LoadedLibrary, load_library
from ..ink.services.scene import solve_library
from .blender import hierarchy
from .blender.readback import viewport_edits

_LOAD_ERRORS = (DocumentLoadError, OSError, ValueError, KeyError)
_syncing = 0


@contextmanager
def _setting_controls():
    global _syncing
    _syncing += 1
    try:
        yield
    finally:
        _syncing -= 1


def controls_syncing() -> bool:
    """True while the panel controls are being set from the widgets (their changes are no edits then)"""
    return _syncing > 0


def _set_controls(root, loaded: LoadedLibrary) -> None:
    records = {widget.path: widget for widget in loaded.item.widgets}
    with _setting_controls():
        for path, handle in hierarchy.handles(root).items():
            widget = records.get(path)
            if widget is None:
                continue
            controls = handle.cp77_ink
            if widget.type == "inkTextWidget":
                controls.text = text_key(widget.data) or text_content(widget.data)
                controls.font_size = max(
                    0, int(coerce_float(widget.data.get("fontSize"), 0.0))
                )
            controls.size = widget.size
            controls.opacity = min(1.0, max(0.0, widget.opacity))
            controls.tint = widget.tint
            controls.visible = widget.visible
            handle["inkFitToContent"] = int(widget.fit_to_content)
            handle["inkBoundProperties"] = ",".join(
                name for name, _style_path in widget.bindings
            )


def _library_name(filepath: str, item_name: str, root_item: str) -> str:
    stem = os.path.basename(strip_json_suffix(filepath)).split(".")[0] or "ink"
    return stem if item_name == root_item else f"{stem}_{item_name}"


def _warnings(loaded: LoadedLibrary) -> list[str]:
    return [f"{where}: {message}" for where, message in loaded.warnings]


@transactional("Ink widget import")
def import_widget(
    context,
    filepath: str,
    *,
    item: str = "",
    preferred_slot: int = 0,
    unit_scale: float = 0.001,
    max_dimension: int = 2048,
) -> OperationResult:
    """Import the library item at filepath as a preview with a handle per widget"""
    try:
        loaded = load_library(
            filepath, item=item or None, preferred_slot=preferred_slot
        )
    except _LOAD_ERRORS as error:
        return OperationResult.cancelled(
            f"The ink widget could not be loaded: {error}", error=error
        )
    warnings = _warnings(loaded)
    animation = None
    if loaded.animation_path:
        try:
            animation = load_animation(loaded.animation_path)
        except _LOAD_ERRORS as error:
            warnings.append(
                f"ink animation {loaded.animation_path} could not be loaded: {error}"
            )
    name = _library_name(filepath, loaded.item.name, loaded.library.item().name)
    image = screens.create_texture(
        name, screens.render(loaded, animation, max_dimension=max_dimension)
    )
    root = hierarchy.create(
        context.scene, name, solve_library(loaded, _FONTS), image, unit_scale=unit_scale
    )
    root[PENDING_EDITS_KEY] = "[]"
    screens.register(root, image, loaded, animation, max_dimension=max_dimension)
    _set_controls(root, loaded)
    context.view_layer.objects.active = root
    root.select_set(True)
    context.scene.cp77_ink_tools.widget = root
    return OperationResult.finished(
        f"Imported {len(loaded.item.widgets)} widgets from {os.path.basename(filepath)}",
        warnings=warnings,
        root=root.name,
    )


def _stored(root) -> list[WidgetEdit]:
    return edits_from_json(str(root.get(PENDING_EDITS_KEY, "") or ""))


def _redraw(root, edits: list[WidgetEdit]) -> OperationResult:
    screen = screens.screen_for(root)
    image = screen.image() if screen is not None else None
    if image is None:
        return OperationResult.cancelled("The widget's preview texture is missing")
    path, item = str(root["cp77_ink_widget_json"]), str(root["cp77_ink_widget_item"])
    try:
        document = edited_document(path, item, edits)[0] if edits else None
        loaded = load_library(
            path,
            item=item,
            preferred_slot=screen.loaded.preferred_slot,
            document=document,
        )
    except _LOAD_ERRORS as error:
        return OperationResult.cancelled(
            f"The ink widget could not be loaded: {error}", error=error
        )
    update_texture(
        image,
        screens.render(loaded, screen.animation, max_dimension=screen.max_dimension),
    )
    screens.register(
        root, image, loaded, screen.animation, max_dimension=screen.max_dimension
    )
    hierarchy.sync(root, solve_library(loaded, _FONTS))
    _set_controls(root, loaded)
    return OperationResult.finished()


def refresh(root, extra=()) -> OperationResult:
    """Take the edits made on the handles (and extra edits) into the pending edits and redraw"""
    screen = screens.screen_for(root)
    if screen is None:
        return OperationResult.cancelled(
            f"The widget library {root.get('cp77_ink_widget_json', '')} was not found"
        )
    edits = merged([*_stored(root), *viewport_edits(root, screen.loaded.item), *extra])
    root[PENDING_EDITS_KEY] = edits_to_json(edits)
    return _redraw(root, edits)


def record_edit(handle, **changes) -> OperationResult:
    """Edit the widget handle stands for (a panel control's change) and redraw at once"""
    root, path = hierarchy.standalone_root(handle), hierarchy.widget_path(handle)
    if root is None or path is None:
        return OperationResult.cancelled("Select a handle of an imported ink widget")
    return refresh(root, [WidgetEdit(path=path, **changes)])


def export(root, target: str = "") -> OperationResult:
    """Write the pending edits into the library"""
    result = refresh(root)
    if not result.ok:
        return result
    edits = _stored(root)
    try:
        written = export_library(
            str(root["cp77_ink_widget_json"]),
            str(root["cp77_ink_widget_item"]),
            edits,
            target,
        )
    except (*_LOAD_ERRORS, RuntimeError) as error:
        return OperationResult.cancelled(
            f"The ink widget could not be exported: {error}", error=error
        )
    root["cp77_ink_widget_json"] = written
    root[PENDING_EDITS_KEY] = "[]"
    result = _redraw(root, [])
    if not result.ok:
        return result
    return OperationResult.finished(f"Exported {len(edits)} widget edits to {written}")


def play(root, sequence: str, scene) -> OperationResult:
    if not screens.play(root, sequence, scene):
        return OperationResult.cancelled(f"The ink sequence {sequence} was not found")
    return OperationResult.finished()


def stop(root) -> OperationResult:
    if not screens.stop(root):
        return OperationResult.cancelled("The widget's preview texture is missing")
    return OperationResult.finished()
