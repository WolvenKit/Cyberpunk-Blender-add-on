import importlib
import subprocess
import sys

import bpy


def install_dependency(pip_name: str, import_name: str) -> bool:
    """Install an explicitly requested optional dependency into Blender."""
    if sys.platform != "win32":
        return False
    if getattr(bpy.app, "online_access", True) is False:
        return False

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                pip_name,
            ],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False

    importlib.invalidate_caches()
    try:
        importlib.import_module(import_name)
    except ImportError:
        return False
    return True
