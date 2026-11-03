import gpu

# Warned once a session: every import with materials would repeat it otherwise.
_SESSION = {"opengl_warned": False}


def _running_backend():
    """The GPU backend Blender draws with"""
    try:
        return gpu.platform.backend_type_get()
    except (RuntimeError, SystemError):
        return ""


def opengl_shader_warning():
    """The warning for the first import with materials of a session that runs on OpenGL"""
    if _SESSION["opengl_warned"] or _running_backend() != "OPENGL":
        return ""
    _SESSION["opengl_warned"] = True
    return (
        "Blender draws with OpenGL, where EEVEE fails to compile many imported Cyberpunk shaders. Set "
        "Preferences > System > Backend to Vulkan, or tick Set Backend to Vulkan, and restart Blender."
    )
