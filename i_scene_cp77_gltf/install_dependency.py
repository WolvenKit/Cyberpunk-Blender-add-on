import bpy

def install_dependency(dependency_name):
    print(f"required package: {dependency_name} not found")
    from pip import _internal as pip
    print(f"Attempting to install {dependency_name}")
    try:
        pip.main(['install', dependency_name])
        print(f"Successfully installed {dependency_name}")
    except Exception as e:
        print(f"Failed to install {dependency_name}: {e}")