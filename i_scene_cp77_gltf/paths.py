import os
import shutil
import tempfile

try:
    import bpy
except ImportError:
    bpy = None


_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
_RESOURCES_DIR = os.path.join(_PLUGIN_DIR, "resources")


def get_resources_dir():
    return _RESOURCES_DIR


def get_icon_dir():
    return os.path.join(_PLUGIN_DIR, "icons")


def get_refit_dir():
    return os.path.join(_RESOURCES_DIR, "refitters")


def get_char_dir():
    return os.path.join(_RESOURCES_DIR, "characters")


def get_script_dir():
    path = None
    if bpy is not None:
        try:
            value = bpy.utils.user_resource(
                "SCRIPTS",
                path="cp77_io_suite/scripts",
                create=True,
            )
            if isinstance(value, (str, bytes, os.PathLike)) and value:
                path = os.path.abspath(os.fspath(value))
        except (AttributeError, OSError, TypeError):
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
    bundled = os.path.join(_RESOURCES_DIR, "scripts")
    if os.path.isdir(bundled):
        for name in os.listdir(bundled):
            if not name.casefold().endswith(".py"):
                continue
            source = os.path.join(bundled, name)
            target = os.path.join(destination, name)
            if os.path.isfile(source) and not os.path.exists(target):
                shutil.copy2(source, target)
    return destination


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
    root = os.path.realpath(ensure_user_script_dir())
    candidate = os.path.realpath(os.path.join(root, name))
    if os.path.commonpath((root, candidate)) != root:
        raise ValueError("Script path escapes the user script directory.")
    return candidate


def get_rig_dir():
    return os.path.join(_RESOURCES_DIR, "rigs")
