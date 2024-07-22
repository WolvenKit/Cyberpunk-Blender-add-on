import bpy
import sys
from .main.common import show_message

_os = sys.platform

def install_dependency(dependency_name):
    if _os is not 'win32':
        print(f"required package: {dependency_name} not found but the plugin is unable to install this automatically on OS other than Windows")
        show_message(f"required package: {dependency_name} not found but the plugin is unable to install automatically on OS other than Windows")
        return('CANCELLED')
    print(f"required package: {dependency_name} not found")
    from pip import _internal as pip
    print(f"Attempting to install {dependency_name}")
    try:
        pip.main(['install', dependency_name])
        print(f"Successfully installed {dependency_name}")
    except Exception as e:
        print(f"Failed to install {dependency_name}: {e}")