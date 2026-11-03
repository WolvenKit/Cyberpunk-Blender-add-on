import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from ...assetio.atomic import atomic_write_bytes
from ...assetio.files import binary_reader, read_bytes
from ...core.log import debug_exception, get_logger

_LOG = get_logger(__name__)


def blender_native_folder(blender_version):
    version = tuple(int(value) for value in tuple(blender_version)[:3])
    if version < (5, 0, 0):
        raise RuntimeError(f"Blender {version!r} is not supported by this add-on")
    return "blender51_plus" if version >= (5, 1, 0) else "blender50"


def native_python_dir(native_root, blender_version):
    return Path(native_root) / blender_native_folder(blender_version)


def native_extension_path(native_root, module_name, blender_version):
    name = str(module_name or "").strip()
    if not name or Path(name).name != name or Path(name).suffix:
        raise ValueError(
            "Native extension module names must be plain names without a suffix"
        )
    return native_python_dir(native_root, blender_version) / f"{name}.pyd"


# Windows keeps a loaded DLL locked until its process exits, and Python never unloads an extension module. Native
# binaries loaded from the add-on's own folder would block uninstalling or updating it, so they are loaded from a
# per-process copy, removed once the process has exited.
_RUNTIME_FOLDER = ("CP77 IO Suite", "native")
_watched_folders = set()

# Runs in a detached interpreter: waits for the Blender process to exit, then removes its native copies.
_CLEANUP_SCRIPT = r"""
import ctypes, os, shutil, sys, time
pid, folder = int(sys.argv[1]), sys.argv[2]
kernel = ctypes.windll.kernel32
handle = kernel.OpenProcess(0x00100000, False, pid)
if handle:
    kernel.WaitForSingleObject(handle, 0xFFFFFFFF)
    kernel.CloseHandle(handle)
for _attempt in range(50):
    shutil.rmtree(folder, ignore_errors=True)
    if not os.path.exists(folder):
        break
    time.sleep(0.2)
for parent in (os.path.dirname(folder), os.path.dirname(os.path.dirname(folder))):
    try:
        os.rmdir(parent)
    except OSError:
        break
"""


def native_runtime_root():
    """The per-user folder holding the native copies of running Blender processes"""
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    return Path(base, *_RUNTIME_FOLDER)


def _process_started(pid):
    """When the running process pid started, in 100 ns units"""
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.windll.kernel32
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        code = wintypes.DWORD()
        if (
            not kernel.GetExitCodeProcess(handle, ctypes.byref(code))
            or code.value != 259
        ):  # STILL_ACTIVE
            return None
        created, exited, kernel_time, user_time = (
            wintypes.FILETIME() for _ in range(4)
        )
        if not kernel.GetProcessTimes(
            handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        ):
            return 0
        return (created.dwHighDateTime << 32) | created.dwLowDateTime
    finally:
        kernel.CloseHandle(handle)


_current_process = None


def _current_process_mark():
    """This process's folder suffix"""
    global _current_process
    if _current_process is None:
        pid = os.getpid()
        _current_process = f"{pid}.{_process_started(pid) or 0}"
    return _current_process


def _folder_owner(folder):
    """(pid, start time or None) from a runtime folder's name"""
    pid, _, started = folder.name.rsplit("-", 1)[-1].partition(".")
    try:
        return int(pid), int(started) if started else None
    except ValueError:
        return None


def _owner_running(pid, started):
    current = _process_started(pid)
    if current is None:
        return False
    # A start time that cannot be read on either side is not evidence of reuse; keep the folder.
    return not started or not current or current == started


def sweep_native_runtime_copies():
    """Removes the native copies of Blender processes that are no longer running"""
    try:
        folders = [entry for entry in native_runtime_root().iterdir() if entry.is_dir()]
    except OSError:
        debug_exception(
            _LOG, "Could not list the native runtime copies; nothing is swept"
        )
        return
    for folder in folders:
        owner = _folder_owner(folder)
        if owner is not None and not _owner_running(*owner):
            shutil.rmtree(folder, ignore_errors=True)


def _start_cleanup_watcher(folder):
    """Starts the detached interpreter that removes folder once this process exits"""
    if folder in _watched_folders:
        return True
    interpreter = Path(sys.executable or "")
    if not interpreter.name.casefold().startswith("python"):
        # Without a standalone interpreter the folder is swept when Blender next loads the bridge.
        return False
    try:
        subprocess.Popen(
            [
                os.fspath(interpreter),
                "-I",
                "-S",
                "-c",
                _CLEANUP_SCRIPT,
                str(os.getpid()),
                os.fspath(folder),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=(
                subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.CREATE_NO_WINDOW
            ),
        )
    except OSError:
        debug_exception(_LOG, "Could not start the native runtime cleanup watcher")
        return False
    _watched_folders.add(folder)
    return True


def native_runtime_copy(sources, label):
    """Copies native binaries into this process's runtime folder and returns their paths"""
    sources = sorted(
        (Path(source) for source in sources), key=lambda path: path.name.casefold()
    )
    contents = {source.name: read_bytes(source) for source in sources}
    digest = hashlib.sha256()
    for source in sources:
        digest.update(source.name.casefold().encode("utf-8"))
        digest.update(contents[source.name])
    sweep_native_runtime_copies()
    folder = (
        native_runtime_root()
        / f"{label}-{digest.hexdigest()[:16]}-{_current_process_mark()}"
    )
    folder.mkdir(parents=True, exist_ok=True)
    _start_cleanup_watcher(folder)
    copies = {}
    for source in sources:
        data = contents[source.name]
        target = folder / source.name
        if _file_digest(target) != hashlib.sha256(data).digest():
            atomic_write_bytes(target, data)
        copies[source.name] = target
    return copies


def _file_digest(path):
    try:
        with binary_reader(path) as handle:
            return hashlib.file_digest(handle, "sha256").digest()
    except OSError:
        debug_exception(_LOG, "Could not read %s for its digest", path)
        return None


def release_native_runtime_copies():
    """Removes this process's native copies where nothing holds them"""
    for folder in tuple(_watched_folders):
        shutil.rmtree(folder, ignore_errors=True)
        if not folder.exists():
            _watched_folders.discard(folder)
    root = native_runtime_root()
    for folder in (root, root.parent):
        try:
            folder.rmdir()
        except OSError:
            debug_exception(
                _LOG, "Could not remove the native runtime copy folder %s", folder
            )
            break
