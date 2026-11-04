import os
import tempfile

import bpy

from ..assetio.atomic import atomic_write_bytes
from ..assetio.files import read_bytes
from ..assetio.index import IndexPolicy, build_asset_index
from ..assetio.paths import confined_join
from ..assetio.resources import get_bundled_script_dir
from ..core.log import debug_exception, get_logger, log_once

_LOG = get_logger(__name__)

# The script file a text was loaded from: the text of a managed script is known by its file, not by its name.
_SCRIPT_FILE_KEY = "cp77_managed_script"
# The scripts in each script folder as last read, by the folder's modification time.
_LISTINGS = {}


def get_script_dir():
    path = None
    try:
        value = bpy.utils.user_resource(
            "SCRIPTS",
            path="cp77_io_suite/scripts",
            create=True,
        )
        if isinstance(value, (str, bytes, os.PathLike)) and value:
            path = os.path.abspath(os.fspath(value))
    except (AttributeError, OSError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("get_script_dir", type(error).__name__),
            "get script dir: fell back after %s",
            error,
            exc_info=True,
        )
        path = None
    if path is None:
        path = os.path.join(
            tempfile.gettempdir(),
            "scripts",
            "cp77_io_suite",
        )
    return path


def ensure_user_script_dir():
    destination = get_script_dir()
    os.makedirs(destination, exist_ok=True)
    bundled = get_bundled_script_dir()
    if os.path.isdir(bundled):
        snapshot = build_asset_index(bundled, (".py",), policy=IndexPolicy.REUSE)
        for source in snapshot.get_files_by_extension(".py"):
            if os.path.dirname(os.path.abspath(source)) != os.path.abspath(bundled):
                continue
            target = os.path.join(destination, os.path.basename(source))
            if not os.path.exists(target):
                atomic_write_bytes(target, read_bytes(source))
    return destination


def user_script_names():
    """(folder, names) of the user's script folder and the .py files in it"""
    folder = get_script_dir()
    try:
        stamp = os.stat(folder).st_mtime_ns
    except OSError:
        debug_exception(
            _LOG, "Could not read the user script folder %s; recreating it", folder
        )
        folder = ensure_user_script_dir()
        stamp = os.stat(folder).st_mtime_ns
    listing = _LISTINGS.get(folder)
    if listing is None or listing[0] != stamp:
        with os.scandir(folder) as entries:
            names = tuple(
                sorted(
                    entry.name
                    for entry in entries
                    if entry.name.casefold().endswith(".py") and entry.is_file()
                )
            )
        listing = _LISTINGS[folder] = (stamp, names)
    return folder, listing[1]


def resolve_user_script_path(filename, *, add_extension=False):
    name = str(filename or "").strip()
    if add_extension and not name.casefold().endswith(".py"):
        name += ".py"
    if (
        not name
        or os.path.isabs(name)
        or name in {".", ".."}
        or os.path.basename(name) != name
        or "/" in name
        or "\\" in name
        or not name.casefold().endswith(".py")
    ):
        raise ValueError("Script names must be plain .py filenames.")
    try:
        return confined_join(ensure_user_script_dir(), name, resolve_links=True)
    except ValueError as error:
        raise ValueError("Script path escapes the user script directory.") from error


def _script_key(script_path):
    return os.path.normcase(os.path.realpath(script_path))


def is_managed_text(text, script_path):
    """Whether text is the one the Script Manager loaded script_path into"""
    return text is not None and text.get(_SCRIPT_FILE_KEY) == _script_key(script_path)


def managed_text(script_path):
    return next(
        (text for text in bpy.data.texts if is_managed_text(text, script_path)), None
    )


def load_managed_text(script_path):
    """The text holding script_path"""
    text = managed_text(script_path)
    if text is None:
        text = bpy.data.texts.new(name=os.path.basename(script_path))
        text.from_string(read_bytes(script_path).decode("utf-8"))
        text[_SCRIPT_FILE_KEY] = _script_key(script_path)
    return text


def follow_renamed_script(old_path, new_path):
    """Let the text of a renamed script, edits and all, follow it to its new file"""
    text = managed_text(old_path)
    if text is not None:
        text[_SCRIPT_FILE_KEY] = _script_key(new_path)
        text.name = os.path.basename(new_path)


def forget_deleted_script(script_path):
    """Let go of the text a deleted script was loaded into"""
    text = managed_text(script_path)
    if text is not None:
        del text[_SCRIPT_FILE_KEY]
