import logging
import textwrap
from contextvars import ContextVar
from functools import wraps

import bpy
from bpy.props import StringProperty
from bpy.types import Operator

from .log import debug_exception, get_logger, level_from_name
from .registration import RegistrationLedger

_IMPORT_NOTICE = ContextVar("cp77_import_notice", default=None)
_LOG = get_logger(__name__)


def _import_action(message):
    """Translate diagnostic details into a bounded set of recovery actions"""
    text = str(message).lower()
    if "permission" in text or "access is denied" in text:
        return "Access denied. Choose a readable file or folder and retry."
    if "exactly one glb" in text:
        return "Select one GLB file and retry."
    if "opengl" in text:
        return "Switch Blender to the Vulkan backend and restart it: EEVEE fails to compile many imported shaders on OpenGL."
    if "stop" in text and "preview" in text:
        return "Stop the animation preview and retry."
    if "material" in text and ("no active" in text or "has no material" in text):
        return "Select a mesh with an active material and retry."
    if any(
        term in text
        for term in (
            "no active",
            "nothing selected",
            "select an",
            "no actor selected",
            "actor list is empty",
        )
    ):
        return "Select the required object or rig and retry."
    # What a reader says of a file it cannot parse; checked before missing files, whose wording a damaged file shares.
    if any(
        term in text
        for term in (
            "file is empty",
            "expecting value",
            "expecting property name",
            "unterminated string",
            "extra data",
            "invalid utf-8",
            "too short to be a glb",
            "glb magic header",
            "declared length",
            "must be a list",
            "must be an object",
            "holds no widget tree",
        )
    ):
        return "The chosen file is damaged or is not the file this importer reads. Export it again and retry."
    if any(
        term in text
        for term in (
            "not found",
            "not indexed",
            "missing",
            "file does not exist",
            "unavailable",
            "could not resolve",
            "could not be loaded",
            "failed to load",
            "no such file",
            "placeholder",
        )
    ):
        return "Required files are missing or unreadable. Export the dependencies, check the depot path, and retry."
    if any(
        term in text
        for term in (
            "invalid",
            "unsupported",
            "cannot be imported",
            "could not be read",
            "malformed",
            "jsondecode",
            "glb generator",
        )
    ):
        return (
            "Check the input format, re-export the file for this importer, and retry."
        )
    return "Open the IO Suite log for the affected asset and failure details."


class _ImportNotice(logging.Handler):
    """Collect explicit import notices and unhandled ERROR records"""

    def __init__(self):
        super().__init__(logging.ERROR)
        self.actions = {}

    def add(self, message, level=logging.WARNING):
        if message and level >= logging.WARNING:
            action = _import_action(message)
            self.actions[action] = max(level, self.actions.get(action, 0))

    def emit(self, record):
        if _IMPORT_NOTICE.get() is self:
            self.add(record.getMessage(), record.levelno)

    def summary(self, cancelled):
        if not self.actions and not cancelled:
            return ""
        heading = (
            "Import did not complete." if cancelled else "Import completed with issues."
        )
        actions = sorted(self.actions, key=lambda action: -self.actions[action])
        fallback = "Open the IO Suite log for the affected asset and failure details."
        specific = [action for action in actions if action != fallback][:2]
        return " ".join((heading, *specific, fallback))


def _severity_name(severity):
    """One report type from a name or a Blender report set such as {'ERROR'}"""
    if isinstance(severity, (set, frozenset, tuple, list)):
        return max(
            (str(item).upper() for item in severity),
            key=level_from_name,
            default="INFO",
        )
    return str(severity).upper()


def report(owner, severity, message, *, error=None, logger=None, stacklevel=1):
    """Log message once at severity and show it to the user"""
    severity = _severity_name(severity)
    level = level_from_name(severity)
    exc_info = (type(error), error, error.__traceback__) if error is not None else None
    (logger or _LOG).log(
        level, "%s", message, exc_info=exc_info, stacklevel=stacklevel + 1
    )
    notice = _IMPORT_NOTICE.get()
    if notice is not None:
        notice.add(message, level)
        return
    reporter = getattr(owner, "report", None)
    if callable(reporter):
        reporter({severity}, str(message))


def import_operation(function):
    """Emit at most one issue dialog after the outermost import has unwound"""

    @wraps(function)
    def execute(operator, context, *args, **kwargs):
        if _IMPORT_NOTICE.get() is not None:
            return function(operator, context, *args, **kwargs)
        notice = _ImportNotice()
        token = _IMPORT_NOTICE.set(notice)
        logger = get_logger()
        logger.addHandler(notice)
        status = {"CANCELLED"}
        try:
            status = function(operator, context, *args, **kwargs)
        except Exception as error:
            notice.add(str(error), logging.ERROR)
            _LOG.exception("Import failed")
        finally:
            logger.removeHandler(notice)
            _IMPORT_NOTICE.reset(token)
            summary = notice.summary("CANCELLED" in status)
            if summary and not getattr(operator, "scripting", False):
                show_message(summary)
        return status

    return execute


class ShowMessageBox(Operator):
    bl_idname = "cp77.message_box"
    bl_label = "Cyberpunk 2077 IO Suite"

    message: StringProperty(default="")

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw_header(self, context):
        self.layout.label(text="Cyberpunk 2077 IO Suite")

    def draw(self, context):
        for line in textwrap.TextWrapper(width=70).wrap(text=self.message):
            row = self.layout.row(align=True)
            row.alignment = "EXPAND"
            row.label(text=line)


def show_message(message, *, severity="INFO", logger=None, stacklevel=1):
    """Log message once at severity and show it in a dialog, or in the import notice during an import"""
    level = level_from_name(severity)
    (logger or _LOG).log(level, "%s", message, stacklevel=stacklevel + 1)
    notice = _IMPORT_NOTICE.get()
    if notice is not None:
        notice.add(message, level)
        return
    _display_message(message)


def import_message(message, *, severity="WARNING", logger=None, stacklevel=1):
    """Log message once at severity and add it to the import notice"""
    level = level_from_name(severity)
    (logger or _LOG).log(level, "%s", message, stacklevel=stacklevel + 1)
    notice = _IMPORT_NOTICE.get()
    if notice is not None:
        notice.add(message, level)


def _display_message(message):
    """Open the message dialog"""
    if bpy.app.background:
        return
    try:
        bpy.ops.cp77.message_box("INVOKE_DEFAULT", message=message)
    except RuntimeError:
        debug_exception(_LOG, "The message dialog could not open")


_LEDGER = RegistrationLedger("notifications")


def register_notifications():
    if not _LEDGER.active:
        _LEDGER.register_classes((ShowMessageBox,))


def unregister_notifications():
    _LEDGER.cleanup_or_raise()
