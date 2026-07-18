import importlib
import subprocess
import sys


def install_dependency(pip_name: str, import_name: str) -> bool:
    """
    Executes a subprocess to install a Python package via pip and 
    returns a boolean indicating execution success.
    """
    if sys.platform != 'win32':
        return False

    python_executable = sys.executable

    try:
        subprocess.check_call(
                [python_executable, "-m", "pip", "install", pip_name]
                )

    except subprocess.CalledProcessError:
        pass

    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False
